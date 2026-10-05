"""MOC identities, revocable sessions and hashed partner credentials in isolation."""
import os, sys, tempfile, threading, json, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
os.environ.update(ROOSTERRUN_OPERATING_MODE='APPROVAL_DEMO',ROOSTERRUN_PREVIEW_FEEDS='0')
os.environ.pop('ROOSTERRUN_DATABASE_URL',None)
from manual_payments_server import PaymentService, RoosterRunServer, RequestHandler
from moc_engine import hash_password
from auth_engine import generate_totp_secret, totp_code
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
    service=PaymentService(Path(td),False); moc=service.moc
    assert not moc.operator_login('moc_admin','MOCAdmin@2026')['success'], 'Published default credential accepted'
    password='SyntheticMocPassword!42'
    digest,salt,iterations=hash_password(password)
    with service.connect() as db:
        for username,role in [('qa-admin','super_admin'),('qa-monitor','monitor'),('qa-tech','technician')]:
            db.execute('INSERT INTO moc_operators(username,password_hash,password_salt,password_iterations,display_name,role) VALUES(?,?,?,?,?,?)',(username,digest,salt,iterations,username,role))
    login=moc.operator_login('qa-admin',password); assert login['success']
    identity=moc.verify_operator_token(login['token']); assert identity['role']=='super_admin'
    with service.connect() as db:
        assert not db.execute("SELECT 1 FROM moc_settings WHERE key='jwt_secret'").fetchone()
        db.execute('UPDATE moc_operators SET active=0 WHERE username=?',('qa-admin',))
    assert moc.verify_operator_token(login['token']) is None
    with service.connect() as db: db.execute('UPDATE moc_operators SET active=1 WHERE username=?',('qa-admin',))
    assert moc.verify_operator_token(login['token']) is None, 'Disabled session resurrected'
    login=moc.operator_login('qa-admin',password)
    with service.connect() as db: db.execute('UPDATE moc_operators SET password_hash=? WHERE username=?',(hash_password('ChangedSyntheticPassword!')[0],'qa-admin'))
    assert moc.verify_operator_token(login['token']) is None
    with service.connect() as db: db.execute('UPDATE moc_operators SET password_hash=? WHERE username=?',(digest,'qa-admin'))
    login=moc.operator_login('qa-admin',password); moc.revoke_operator_token(login['token'])
    assert moc.verify_operator_token(login['token']) is None
    assert not moc.create_api_key(identity['operator_id'],'qa-admin','Revoked session QA',session_token=login['token'])['success']
    for username in ['qa-monitor','qa-tech']:
        op=moc.verify_operator_token(moc.operator_login(username,password)['token'])
        assert not moc.create_match(op['operator_id'],username,{'arena':'QA','title':'QA'})['success']
        assert not moc.create_api_key(op['operator_id'],username,'QA')['success']
        assert not moc.update_match_status(op['operator_id'],username,'MOC-1','CANCELLED',password)['success']
        assert not moc.declare_result(op['operator_id'],username,'MOC-1','red',password)['success']
    secret=generate_totp_secret()
    with service.connect() as db: db.execute('UPDATE moc_operators SET mfa_enabled=1,mfa_secret=? WHERE username=?',(secret,'qa-admin'))
    assert not moc.operator_login('qa-admin',password)['success']
    login=moc.operator_login('qa-admin',password,mfa_code=totp_code(secret)); assert login['success']
    op=moc.verify_operator_token(login['token'])
    monitor_login=moc.operator_login('qa-monitor',password)
    monitor_id=monitor_login['operator']['id']
    moc.update_operator(op['operator_id'],'qa-admin',monitor_id,{'active':False},session_token=login['token'])
    moc.update_operator(op['operator_id'],'qa-admin',monitor_id,{'active':True},session_token=login['token'])
    assert moc.verify_operator_token(monitor_login['token']) is None, 'Unobserved disable/enable resurrected session'
    with service.connect() as db:
        before=db.execute('SELECT COUNT(*) n FROM moc_api_keys').fetchone()['n']
        db.execute("CREATE TRIGGER qa_audit_failure BEFORE INSERT ON moc_audit_log BEGIN SELECT RAISE(ABORT,'synthetic audit failure'); END")
    assert not moc.create_api_key(op['operator_id'],'qa-admin','Audit failure QA')['success']
    with service.connect() as db:
        assert db.execute('SELECT COUNT(*) n FROM moc_api_keys').fetchone()['n']==before
        db.execute('DROP TRIGGER qa_audit_failure')
    key=moc.create_api_key(op['operator_id'],'qa-admin','QA',rate_limit=2); assert key['success']
    with service.connect() as db:
        row=db.execute('SELECT api_key,key_hash FROM moc_api_keys WHERE key_id=?',(key['key_id'],)).fetchone()
        assert row['api_key'] != key['api_key'] and key['api_key'] not in str(tuple(row))
    assert moc.verify_api_key(key['api_key'])
    service=PaymentService(Path(td),False);moc=service.moc
    assert moc.verify_api_key(key['api_key'])
    assert moc.verify_api_key(key['api_key']) is None, 'Rate window reset on restart'
    assert moc.revoke_api_key(op['operator_id'],'qa-admin',key['key_id'],'Synthetic revocation')['success']
    assert moc.verify_api_key(key['api_key']) is None
    assert not moc.create_api_key(op['operator_id'],'qa-admin','QA',permissions=['write'])['success']
    assert not moc.create_api_key(op['operator_id'],'qa-admin','QA',rate_limit='invalid')['success']
    limited=moc.create_api_key(op['operator_id'],'qa-admin','Concurrent QA',rate_limit=2)
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(bool(result) for result in pool.map(lambda _:moc.verify_api_key(limited['api_key']),range(8)))==2
    scoped=moc.create_api_key(op['operator_id'],'qa-admin','Scoped QA',allowed_ips=['192.0.2.5'],expires_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())
    assert scoped['success'] and moc.verify_api_key(scoped['api_key']) is None
    assert moc.verify_api_key(scoped['api_key'],'192.0.2.5')
    with service.connect() as db:
        db.execute('UPDATE moc_api_keys SET expires_at=? WHERE key_id=?',((datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat(),scoped['key_id']))
    assert moc.verify_api_key(scoped['api_key'],'192.0.2.5') is None
    # Actual local HTTP boundary, with no external network/provider operations.
    server=RoosterRunServer(('127.0.0.1',0),RequestHandler,service,False)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    def http(path,body=None,token=None):
        headers={'Content-Type':'application/json'}
        if token: headers['Authorization']='Bearer '+token
        request=urllib.request.Request('http://127.0.0.1:'+str(server.server_port)+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        try:
            with urllib.request.urlopen(request) as response: return response.status,json.load(response)
        except urllib.error.HTTPError as error: return error.code,json.load(error)
    try:
        status,session=http('/api/moc/auth/login/',{'username':'qa-tech','password':password});assert status==200
        assert http('/api/moc/matches/',{'title':'Unauthorized'},session['token'])[0]==403
        assert http('/api/moc/audit-log/',token=session['token'])[0]==403
        assert http('/api/moc/auth/logout/',{},session['token'])[0]==200
        assert http('/api/moc/matches/',token=session['token'])[0]==401
        assert http('/api/moc/auth/login/',{'username':'qa-admin','password':password})[0]==401
    finally:
        server.shutdown();server.server_close();worker.join()
    for i in range(8): assert not moc.operator_login('qa-monitor','incorrect','192.0.2.12')['success']
    assert not moc.operator_login('qa-monitor',password,'192.0.2.12')['success'], 'Login throttle missing'
    print('PASS: defaults disabled, live identity/role, password/logout revocation, MFA, hashed keys, durable limits and revocation')

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
    service=PaymentService(Path(td),False)
    digest,salt,iterations=hash_password('MOCAdmin@2026')
    with service.connect() as db:
        db.execute("INSERT INTO moc_operators(username,password_hash,password_salt,password_iterations,display_name,role) VALUES('moc_admin',?,?,?,'Legacy','super_admin')",(digest,salt,iterations))
        db.execute("INSERT INTO moc_settings(key,value) VALUES('jwt_secret','legacy-secret')")
        db.execute("INSERT INTO moc_operators(username,password_hash,password_salt,password_iterations,display_name,role) VALUES('existing-monitor',?,?,?,'Monitor','monitor')",(digest,salt,iterations))
    os.environ.update(ROOSTERRUN_MOC_BOOTSTRAP_USERNAME='moc_admin',ROOSTERRUN_MOC_BOOTSTRAP_PASSWORD='ReplacementSynthetic!42')
    try:
        service=PaymentService(Path(td),False)
        assert not service.moc.operator_login('moc_admin','MOCAdmin@2026')['success']
        assert service.moc.operator_login('moc_admin','ReplacementSynthetic!42')['success']
        with service.connect() as db:
            assert not db.execute("SELECT 1 FROM moc_settings WHERE key='jwt_secret'").fetchone()
        print('PASS: legacy default disabled and explicit replacement bootstrap works')
    finally:
        os.environ.pop('ROOSTERRUN_MOC_BOOTSTRAP_USERNAME',None)
        os.environ.pop('ROOSTERRUN_MOC_BOOTSTRAP_PASSWORD',None)
