"""Recoverable MOC adapter into authoritative matches and settlement."""
import logging
import threading
from cockfight_engine import utc_now
logger=logging.getLogger(__name__)
SOURCE='MOC_FEED'

class MOCFeedEngine:
    def __init__(self,service):
        self.service=service;self.moc_engine=None;self.current_match=None;self.worker=None;self.running=False
        self._stop=threading.Event();self._poll_lock=threading.Lock();self._worker_lock=threading.Lock();self.last_error=''
        with service.connect() as db:
            db.execute("INSERT OR IGNORE INTO game_categories(slug,name,kind,created_at,updated_at) VALUES('moc-feed','Match Operations','CUSTOM',?,?)",(utc_now(),utc_now()))
            values={r['key']:r['value'] for r in db.execute('SELECT key,value FROM moc_settings').fetchall()}
        self._settings=dict(enabled=values.get('enabled')=='true',poll_seconds=int(values.get('feed_poll_interval_seconds','3')),category_slug=values.get('moc_category_slug','moc-feed'),auto_mirror=values.get('auto_mirror_matches','true')=='true',feature_current=True)

    def settings(self): return self._settings.copy()

    def update_settings(self,payload,actor='SYSTEM'):
        if not isinstance(payload,dict) or set(payload)-{'enabled','poll_seconds','category_slug','auto_mirror'}: raise ValueError('Invalid MOC feed settings.')
        candidate=self.settings();candidate.update(payload)
        if any(not isinstance(candidate[k],bool) for k in ('enabled','auto_mirror')): raise ValueError('Feed flags must be true or false.')
        n=candidate['poll_seconds']
        if isinstance(n,bool) or not isinstance(n,int) or not 1<=n<=300: raise ValueError('Poll interval must be an integer between 1 and 300.')
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not isinstance(candidate['category_slug'],str) or not db.execute('SELECT 1 FROM game_categories WHERE slug=?',(candidate['category_slug'],)).fetchone(): raise ValueError('Choose an existing category.')
            for key,field in [('enabled','enabled'),('feed_poll_interval_seconds','poll_seconds'),('moc_category_slug','category_slug'),('auto_mirror_matches','auto_mirror')]:
                value=candidate[field];encoded=('true' if value else 'false') if isinstance(value,bool) else str(value)
                db.execute('INSERT INTO moc_settings(key,value,description) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=CURRENT_TIMESTAMP',(key,encoded,'MOC feed setting'))
            self.service._audit(db,'MOC Feed','Settings updated',str(actor),'Validated feed configuration')
        self._settings=candidate
        if candidate['enabled']: self.start_polling()
        else: self.stop_polling()
        return self.settings()

    def mirror_match_to_platform(self,match):
        ref=match['match_id'];engine=self.service.cockfight
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            link=db.execute('SELECT game_id FROM moc_game_links WHERE match_id=?',(ref,)).fetchone()
            if link: game_id=int(link['game_id'])
            else:
                existing=db.execute('SELECT id FROM admin_games WHERE source=? AND external_ref=?',(SOURCE,ref)).fetchone()
                if existing: game_id=int(existing['id'])
                else:
                    row=db.execute('SELECT * FROM moc_matches WHERE match_id=?',(ref,)).fetchone()
                    game_id=int(db.execute('''INSERT INTO admin_games(title,arena,status,betting_opens_at,betting_closes_at,scheduled_at,team_a_name,team_a_odds,team_b_name,team_b_odds,draw_odds,stream_type,stream_url,source,external_ref,match_number,category_slug,visible,featured,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (row['title'],row['arena'],'DRAFT' if row['status']=='DRAFT' else 'SCHEDULED',row['betting_opens_at'],row['betting_closes_at'],row['scheduled_at'],row['red_name'],row['red_odds'],row['blue_name'],row['blue_odds'],row['draw_odds'],row['stream_type'],row['stream_url'] or '',SOURCE,ref,str(row['fight_number']),self._settings['category_slug'],row['visible'],row['featured'],utc_now(),utc_now())).lastrowid)
                db.execute('INSERT INTO moc_game_links(match_id,game_id) VALUES(?,?)',(ref,game_id))
            row=db.execute('SELECT title,arena,visible,featured,stream_type,stream_url FROM moc_matches WHERE match_id=?',(ref,)).fetchone()
            db.execute('UPDATE admin_games SET title=?,arena=?,visible=?,featured=?,stream_type=?,stream_url=?,category_slug=? WHERE id=?',
                       (row['title'],row['arena'],row['visible'],row['featured'],row['stream_type'],row['stream_url'] or '',self._settings['category_slug'],game_id))
        with self.service.connect() as db:
            odds=db.execute('SELECT 1 FROM odds_snapshots WHERE game_id=?',(game_id,)).fetchone()
            game=db.execute('SELECT * FROM admin_games WHERE id=?',(game_id,)).fetchone()
        if not odds: engine.sync_game(game_id,SOURCE)
        desired=match['status'];state=game['status'];result=match.get('result') or ('cancelled' if desired=='CANCELLED' else None)
        if state=='SETTLED':
            if result and game['result']!=result.upper(): raise ValueError('A settled result is immutable.')
        else:
            if desired!='DRAFT' and state=='DRAFT': state=engine.transition_game(game_id,'SCHEDULED',SOURCE)['status']
            steps={'BETTING_OPEN':['BETTING_OPEN'],'BETTING_CLOSED':['BETTING_CLOSED'],'LIVE':['BETTING_CLOSED','LIVE'],'AWAITING_RESULT':['BETTING_CLOSED','LIVE'],'COMPLETED':['BETTING_CLOSED','LIVE']}.get(desired,[])
            order={'SCHEDULED':0,'BETTING_OPEN':1,'BETTING_CLOSED':2,'LIVE':3,'AWAITING_RESULT':4,'CANCELLED':5,'SETTLED':6}
            for step in steps:
                if order.get(state,-1)<order[step]: state=engine.transition_game(game_id,step,SOURCE,'MOC lifecycle intent')['status']
            if result: engine.declare_result(game_id,result,SOURCE);engine.settle_game(game_id,SOURCE)
            elif desired=='AWAITING_RESULT' and state=='LIVE': engine.transition_game(game_id,'AWAITING_RESULT',SOURCE)
            elif desired=='COMPLETED': raise ValueError('Completion requires an official result.')
        with self.service.connect() as db:
            game=db.execute('SELECT * FROM admin_games WHERE id=?',(game_id,)).fetchone()
            if game['status']=='SETTLED': db.execute('UPDATE moc_matches SET status=?,result=?,settled_at=?,completed_at=?,updated_at=? WHERE match_id=?',('CANCELLED' if game['result']=='CANCELLED' else 'COMPLETED',game['result'].lower(),game['settled_at'],game['settled_at'],utc_now(),ref))
        return game_id

    def poll_once(self):
        if not self.moc_engine: return dict(processed=0,failed=0)
        processed=failed=0
        with self._poll_lock:
            with self.service.connect() as db:
                rows=db.execute("SELECT m.match_id FROM moc_matches m LEFT JOIN moc_game_links l ON l.match_id=m.match_id LEFT JOIN admin_games g ON g.id=l.game_id WHERE g.id IS NULL OR g.status!='SETTLED' OR (g.status='SETTLED' AND (m.status='AWAITING_RESULT' OR COALESCE(m.settled_at,'')='')) ORDER BY m.id").fetchall()
            for row in rows:
                with self.service.connect() as db:
                    linked=db.execute('SELECT 1 FROM moc_game_links WHERE match_id=?',(row['match_id'],)).fetchone()
                # Background enabled flag never strands existing money: linked matches
                # still close/settle. New platform links follow auto_mirror alone so
                # operator create/update still mirrors while the worker stays off.
                if not linked and not self._settings['auto_mirror']:
                    continue
                try: self.mirror_match_to_platform(self.moc_engine.get_match(row['match_id']));processed+=1
                except Exception as error:
                    failed+=1;self.last_error=str(error)[:300];logger.error('MOC integration pending for %s: %s',row['match_id'],self.last_error)
            self.current_match=self.moc_engine.feed_current_match()
        return dict(processed=processed,failed=failed)

    def poll_current_match(self): return self.moc_engine.feed_current_match() if self.moc_engine else None
    def get_current_match(self): return self.current_match
    def start_polling(self):
        with self._worker_lock:
            if self.running or not self._settings['enabled']: return
            self._stop.clear();self.running=True;self.worker=threading.Thread(target=self._poll_loop,name='moc-feed',daemon=True);self.worker.start()
    def stop_polling(self):
        with self._worker_lock: self._stop.set();worker=self.worker
        if worker and worker is not threading.current_thread(): worker.join(timeout=20)
        with self._worker_lock:
            if worker and worker.is_alive(): raise RuntimeError('MOC feed worker did not stop.')
            self.running=False;self.worker=None
    def _poll_loop(self):
        try:
            while not self._stop.is_set():
                try:
                    self.poll_once()
                except Exception as error: logger.error('MOC polling failed: %s',error)
                self._stop.wait(self._settings['poll_seconds'])
        finally: self.running=False
