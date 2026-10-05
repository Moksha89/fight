"""Authoritative MOC mirroring and interrupted settlement in isolated points."""
import os, sys, tempfile, threading
from pathlib import Path
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
os.environ.update(ROOSTERRUN_OPERATING_MODE='APPROVAL_DEMO',ROOSTERRUN_PREVIEW_FEEDS='0')
os.environ.pop('ROOSTERRUN_DATABASE_URL',None)
from manual_payments_server import PaymentService
from moc_engine import hash_password
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
    service=PaymentService(Path(td),False)
    service.moc_feed.update_settings({'enabled':True},actor='qa')
    service.moc_feed.stop_polling()
    d,s,i=hash_password('SyntheticMocPassword!42')
    with service.connect() as db:
        op=db.execute('INSERT INTO moc_operators(username,password_hash,password_salt,password_iterations,display_name,role) VALUES(?,?,?,?,?,?)',('qa',d,s,i,'QA','super_admin')).lastrowid
    now=datetime.now(timezone.utc)
    payload=dict(title='Isolated MOC QA',arena='QA Arena',scheduled_at=(now+timedelta(hours=3)).isoformat(),betting_opens_at=(now+timedelta(hours=1)).isoformat(),betting_closes_at=(now+timedelta(hours=2)).isoformat(),stream_type='OFFLINE',stream_url='',red_odds=2,blue_odds=2)
    bad=service.moc.create_match(op,'qa',{**payload,'red_odds':float('nan')})
    assert not bad['success'],'Nonfinite odds accepted'
    made=service.moc.create_match(op,'qa',payload);assert made['success'],made
    ref=made['match']['match_id']
    assert service.moc.update_match_status(op,'qa',ref,'BETTING_OPEN')['success']
    service.moc_feed.poll_once()
    with service.connect() as db:
        game=db.execute("SELECT * FROM admin_games WHERE source='MOC_FEED' AND external_ref=?",(ref,)).fetchone();assert game
    uid='moc-qa';service.ensure_user(uid)
    quote=service.cockfight.quote_bet(uid,dict(game_id=game['id'],outcome='BLUE',stake=100))
    service.cockfight.place_bet(uid,dict(quote_id=quote['quote_id']))
    quote=service.cockfight.quote_bet(uid,dict(game_id=game['id'],outcome='RED',stake=100))
    service.cockfight.place_bet(uid,dict(quote_id=quote['quote_id']))
    held_wallet=service.wallet(uid)
    assert service.moc.update_match_status(op,'qa',ref,'BETTING_CLOSED')['success']
    assert service.moc.update_match_status(op,'qa',ref,'LIVE')['success']
    with service.connect() as db:
        db.execute("CREATE TRIGGER qa_failure BEFORE UPDATE ON cockfight_bets WHEN NEW.status='LOST' BEGIN SELECT RAISE(ABORT,'synthetic interruption'); END")
    declared=service.moc.declare_result(op,'qa',ref,'blue','SyntheticMocPassword!42');assert declared['success'],declared
    assert service.wallet(uid)==held_wallet,'Interrupted settlement changed a wallet'
    with service.connect() as db:
        assert db.execute('SELECT status FROM moc_matches WHERE match_id=?',(ref,)).fetchone()['status']=='AWAITING_RESULT'
        assert db.execute("SELECT COUNT(*) n FROM cockfight_bets WHERE game_id=? AND status='PENDING'",(game['id'],)).fetchone()['n']==2
        assert db.execute("SELECT COUNT(*) n FROM wallet_holds WHERE user_id=? AND status='ACTIVE'",(uid,)).fetchone()['n']==2
        assert not db.execute("SELECT 1 FROM account_ledger WHERE entry_type IN ('BET_WIN','BET_LOSS')").fetchone()
        db.execute('DROP TRIGGER qa_failure')
    service=PaymentService(Path(td),False);service.moc_feed.poll_once();service.moc_feed.poll_once()
    assert service.wallet(uid)['bet_exposure']==0
    with service.connect() as db:
        assert db.execute('SELECT status FROM moc_matches WHERE match_id=?',(ref,)).fetchone()['status']=='COMPLETED'
        assert db.execute('SELECT COUNT(*) n FROM account_ledger WHERE reference=?',(f"BET:1:SETTLEMENT",)).fetchone()['n']==1
        assert db.execute("SELECT COUNT(*) n FROM admin_games WHERE source='MOC_FEED' AND external_ref=?",(ref,)).fetchone()['n']==1
    assert not service.moc.declare_result(op,'qa',ref,'red','SyntheticMocPassword!42')['success']
    # A committed close intent must invalidate quotes before the adapter catches up.
    made=service.moc.create_match(op,'qa',{**payload,'title':'Acceptance boundary QA'})
    race_ref=made['match']['match_id']
    assert service.moc.update_match_status(op,'qa',race_ref,'BETTING_OPEN')['success']
    with service.connect() as db:
        race_gid=db.execute('SELECT game_id FROM moc_game_links WHERE match_id=?',(race_ref,)).fetchone()['game_id']
    service.ensure_user('boundary-qa')
    pending=service.cockfight.quote_bet('boundary-qa',dict(game_id=race_gid,outcome='RED',stake=100))
    committed=threading.Event();resume=threading.Event();real_poll=service.moc_feed.poll_once
    def paused_poll():
        committed.set();assert resume.wait(5);return real_poll()
    service.moc_feed.poll_once=paused_poll
    with ThreadPoolExecutor(max_workers=1) as pool:
        close=pool.submit(service.moc.update_match_status,op,'qa',race_ref,'BETTING_CLOSED')
        assert committed.wait(5)
        with service.connect() as db:
            assert db.execute('SELECT status FROM admin_games WHERE id=?',(race_gid,)).fetchone()['status']=='BETTING_OPEN'
        for action in (lambda:service.cockfight.quote_bet('boundary-qa',dict(game_id=race_gid,outcome='RED',stake=100)),lambda:service.cockfight.place_bet('boundary-qa',dict(quote_id=pending['quote_id']))):
            try: action()
            except ValueError: pass
            else: raise AssertionError('Bet accepted after committed close intent')
        resume.set();assert close.result()['success']
    service.moc_feed.poll_once=real_poll
    # Every result is processed, even when several newer active matches exist.
    for result in ('red','blue','draw','cancelled'):
        made=service.moc.create_match(op,'qa',{**payload,'title':'Outcome QA '+result})
        assert made['success'],made
        ref=made['match']['match_id']
        assert service.moc.update_match_status(op,'qa',ref,'BETTING_OPEN')['success']
        with service.connect() as db:
            gid=db.execute('SELECT game_id FROM moc_game_links WHERE match_id=?',(ref,)).fetchone()['game_id']
        users=['moc-'+result+'-'+side for side in ('RED','BLUE','DRAW')]
        before=[]
        for user,side in zip(users,('RED','BLUE','DRAW')):
            service.ensure_user(user);before.append(service.wallet(user)['balance'])
            q=service.cockfight.quote_bet(user,dict(game_id=gid,outcome=side,stake=100))
            service.cockfight.place_bet(user,dict(quote_id=q['quote_id']))
        assert service.moc.update_match_status(op,'qa',ref,'BETTING_CLOSED')['success']
        assert service.moc.update_match_status(op,'qa',ref,'LIVE')['success']
        # Disable the immediate adapter temporarily, creating multiple durable intents.
        adapter=service.moc_feed
        service.moc_feed=type('PendingAdapter',(),{'poll_once':lambda self:None})()
        if result=='cancelled':
            assert service.moc.update_match_status(op,'qa',ref,'CANCELLED','SyntheticMocPassword!42')['success']
        else:
            assert service.moc.declare_result(op,'qa',ref,result,'SyntheticMocPassword!42')['success']
        service.moc_feed=adapter
        service.moc.create_match(op,'qa',{**payload,'title':'Newer current '+result})
        assert service.moc_feed.poll_once()['failed']==0
        summary=service.cockfight.settle_game(gid)
        for user,side,balance in zip(users,('RED','BLUE','DRAW'),before):
            delta=0 if result=='cancelled' else (500 if side=='DRAW' else 100) if side.lower()==result else -100
            wallet=service.wallet(user)
            assert wallet['balance']==balance+delta and wallet['bet_exposure']==0
        assert summary['refunded']==(3 if result=='cancelled' else 0)
        service.moc_feed.poll_once()
        assert service.cockfight.settle_game(gid)==summary
    # Invalid inputs neither allocate counters nor create durable rows.
    with service.connect() as db:
        count=db.execute('SELECT COUNT(*) n FROM moc_matches').fetchone()['n']
        counter=db.execute("SELECT value FROM moc_settings WHERE key='next_fight_number'").fetchone()['value']
    for patch in ({'status':'LIVE'},{'red_odds':float('inf')},{'red_odds':True},{'visible':'false'},{'stream_url':'javascript:bad','stream_type':'HLS'},{'betting_closes_at':payload['scheduled_at'],'scheduled_at':payload['betting_opens_at']}):
        assert not service.moc.create_match(op,'qa',{**payload,**patch})['success']
    with service.connect() as db:
        assert db.execute('SELECT COUNT(*) n FROM moc_matches').fetchone()['n']==count
        assert db.execute("SELECT value FROM moc_settings WHERE key='next_fight_number'").fetchone()['value']==counter
        db.execute("UPDATE moc_settings SET value='1' WHERE key='next_fight_number'")
    with ThreadPoolExecutor(max_workers=4) as pool:
        made=list(pool.map(lambda n:service.moc.create_match(op,'qa',{**payload,'title':f'Concurrent QA {n}'}),range(4)))
    assert all(row['success'] for row in made),made
    assert len({row['match']['fight_number'] for row in made})==4
    # Exact mapping survives descriptive title and configured category changes.
    mapped_ref=made[0]['match']['match_id']
    category=service.admin_save_game_category({'name':'MOC alternate QA','visible':True})
    with service.connect() as db:
        old_id=db.execute('SELECT game_id FROM moc_game_links WHERE match_id=?',(mapped_ref,)).fetchone()['game_id']
        db.execute('UPDATE moc_matches SET title=? WHERE match_id=?',('Renamed unrelated title',mapped_ref))
    settings=service.moc_feed.settings()
    service.moc_feed.update_settings({'category_slug':category['slug']},actor='qa')
    service.moc_feed.poll_once()
    with service.connect() as db:
        assert db.execute('SELECT game_id FROM moc_game_links WHERE match_id=?',(mapped_ref,)).fetchone()['game_id']==old_id
        assert db.execute('SELECT category_slug FROM admin_games WHERE id=?',(old_id,)).fetchone()['category_slug']==category['slug']
    service.moc_feed.update_settings({'enabled':False},actor='qa')
    with service.connect() as db:
        db.execute("CREATE TRIGGER qa_settings_failure BEFORE INSERT ON admin_audit_log WHEN NEW.module='MOC Feed' BEGIN SELECT RAISE(ABORT,'synthetic settings failure'); END")
    stable=service.moc_feed.settings()
    try: service.moc_feed.update_settings({'enabled':True},actor='qa')
    except Exception as e: assert 'synthetic settings failure' in str(e)
    else: raise AssertionError('Settings audit failure did not fire')
    assert service.moc_feed.settings()==stable and not service.moc_feed.running
    with service.connect() as db:
        assert db.execute("SELECT value FROM moc_settings WHERE key='enabled'").fetchone()['value']=='false'
        db.execute('DROP TRIGGER qa_settings_failure')
    for patch in ({'enabled':'false'},{'poll_seconds':0},{'poll_seconds':True},{'category_slug':'missing'}):
        try: service.moc_feed.update_settings(patch)
        except ValueError: pass
        else: raise AssertionError('Invalid settings accepted')
    disabled=service.moc.create_match(op,'qa',{**payload,'title':'Disabled new mirror QA'})
    disabled_ref=disabled['match']['match_id']
    with service.connect() as db:
        assert not db.execute('SELECT 1 FROM moc_game_links WHERE match_id=?',(disabled_ref,)).fetchone()
    # Existing close/cancellation still releases funds while automatic feed creation is off.
    assert service.moc.update_match_status(op,'qa',race_ref,'CANCELLED','SyntheticMocPassword!42')['success']
    with service.connect() as db:
        assert db.execute('SELECT status FROM admin_games WHERE id=?',(race_gid,)).fetchone()['status']=='SETTLED'
    service.moc_feed.update_settings({'enabled':True,'poll_seconds':1},actor='qa')
    assert service.moc_feed.running
    service.moc_feed.stop_polling();assert not service.moc_feed.running
    service=PaymentService(Path(td),False)
    service.moc_feed.start_polling();assert service.moc_feed.running
    service.moc_feed.update_settings({'enabled':False},actor='qa');assert not service.moc_feed.running
    # Generic scheduling continues for manual games, without overriding MOC intent.
    past=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
    with service.connect() as db:
        db.execute('UPDATE admin_games SET betting_opens_at=?,betting_closes_at=?,scheduled_at=? WHERE id=?',(past,past,past,old_id))
    manual=service.admin_save_game({'title':'Scheduler QA','arena':'QA Arena','status':'SCHEDULED','betting_opens_at':past,'betting_closes_at':past,'scheduled_at':past,'stream_type':'OFFLINE'})
    service.cockfight.advance_due_matches()
    with service.connect() as db:
        assert db.execute('SELECT status FROM admin_games WHERE id=?',(old_id,)).fetchone()['status']=='SCHEDULED'
        assert db.execute('SELECT status FROM admin_games WHERE id=?',(manual['id'],)).fetchone()['status']=='LIVE'
    print('PASS: MOC validation, authoritative reservation, interruption, restart, duplicate and conflicting result')
    print('PASS: All outcomes/cancellation, pending result recovery, concurrent counters, stable mapping, settings rollback and worker lifecycle')
