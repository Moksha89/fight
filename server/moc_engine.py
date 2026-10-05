"""
Match Operations Center (MOC) Engine

Purpose: Dedicated operator dashboard for match control with external API feed access
Features:
- Operator authentication with MFA
- Match creation and lifecycle management
- Real-time statistics tracking
- External API feed for other platforms
- API key management and rate limiting
- Complete audit trail

Author: RoosterRun Development Team
Created: 2026-09-14
"""

import sqlite3
import hashlib
import secrets
import json
import logging
import time
import math
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any
import os
import ipaddress
from auth_engine import verify_totp, validate_password

logger = logging.getLogger(__name__)

# Password hashing settings (matching auth_engine.py)
PASSWORD_ITERATIONS = 600_000


def hash_password(password: str, salt: bytes = None, iterations: int = PASSWORD_ITERATIONS) -> tuple[str, str, int]:
    """Hash password using PBKDF2-HMAC-SHA256 (matching auth_engine)"""
    chosen_salt = salt if salt is not None else secrets.token_bytes(32)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), chosen_salt, iterations, dklen=32)
    return digest.hex(), chosen_salt.hex(), iterations


def verify_password(password: str, encoded_digest: str, encoded_salt: str, iterations: int) -> bool:
    """Verify password against stored hash (matching auth_engine)"""
    salt = bytes.fromhex(encoded_salt)
    digest, _, _ = hash_password(password, salt, int(iterations or PASSWORD_ITERATIONS))
    return secrets.compare_digest(digest, encoded_digest)


class MOCEngine:
    """Match Operations Center Engine"""
    
    def __init__(self, payment_service):
        """Initialize MOC Engine
        
        Args:
            payment_service: Parent PaymentService instance
        """
        self.service = payment_service
        self.db_path = payment_service.db_path
        self._init_database()
        self._secure_bootstrap()
        
        logger.info("MOC Engine initialized")
    
    def _init_database(self):
        """Initialize MOC database tables"""
        schema_path = Path(__file__).with_name('moc_database_schema.sql')
        with self.service.connect() as conn:
            conn.executescript(schema_path.read_text(encoding='utf-8'))

    @staticmethod
    def _credential_hash(row):
        return hashlib.sha256(f"{row['password_hash']}:{row['password_salt']}:{row['password_iterations']}:{row['mfa_enabled']}:{row['mfa_secret']}".encode()).hexdigest()

    def _secure_bootstrap(self):
        with self.service.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            legacy = conn.execute("SELECT * FROM moc_operators WHERE username='moc_admin'").fetchone()
            if legacy and verify_password('MOCAdmin@2026', legacy['password_hash'], legacy['password_salt'], legacy['password_iterations']):
                conn.execute("UPDATE moc_operators SET active=0 WHERE id=?", (legacy['id'],))
            conn.execute("DELETE FROM moc_settings WHERE key='jwt_secret'")
            # Preserve digest verification and FK references without retaining bearer secrets.
            conn.execute("UPDATE moc_api_keys SET api_key='redacted:' || key_id WHERE api_key NOT LIKE 'redacted:%'")
            username = os.environ.get('ROOSTERRUN_MOC_BOOTSTRAP_USERNAME','').strip()
            password = os.environ.get('ROOSTERRUN_MOC_BOOTSTRAP_PASSWORD','')
            if username or password:
                if not username or len(username)>80:
                    raise ValueError('MOC bootstrap requires a valid username and password.')
                validate_password(password)
                if password == 'MOCAdmin@2026':
                    raise ValueError('The published MOC password is prohibited.')
                if not conn.execute("SELECT 1 FROM moc_operators WHERE active=1 AND role='super_admin' LIMIT 1").fetchone():
                    digest,salt,iterations=hash_password(password)
                    if legacy and legacy['username']==username and verify_password('MOCAdmin@2026',legacy['password_hash'],legacy['password_salt'],legacy['password_iterations']):
                        conn.execute("UPDATE moc_operators SET password_hash=?,password_salt=?,password_iterations=?,active=1,role='super_admin',mfa_enabled=0,mfa_secret=NULL WHERE id=?",(digest,salt,iterations,legacy['id']))
                    else:
                        if conn.execute('SELECT 1 FROM moc_operators WHERE username=?',(username,)).fetchone():
                            raise ValueError('MOC bootstrap username already belongs to an existing account; choose a new username or use authenticated operator management.')
                        conn.execute("INSERT INTO moc_operators(username,password_hash,password_salt,password_iterations,display_name,role) VALUES(?,?,?,?,?,'super_admin')",(username,digest,salt,iterations,username))

    def _authorize(self, conn, operator_id, username, roles, session_token=None):
        row=conn.execute('SELECT * FROM moc_operators WHERE id=?',(operator_id,)).fetchone()
        if not row or not row['active'] or row['username']!=username or row['role'] not in roles:
            raise ValueError('Operator is not authorized for this action.')
        if session_token is not None:
            session=conn.execute("SELECT * FROM moc_sessions WHERE token_hash=? AND operator_id=? AND revoked_at='' AND expires_at>?",(hashlib.sha256(session_token.encode()).hexdigest(),operator_id,datetime.utcnow().isoformat())).fetchone()
            if not session or not secrets.compare_digest(session['credential_hash'],self._credential_hash(row)):
                raise ValueError('Operator session is no longer valid.')
        return row

    @staticmethod
    def _reserve_rate(conn, scope, limit, window):
        now=time.time()
        conn.execute('DELETE FROM moc_rate_events WHERE created_at<?',(now-86400,))
        count=conn.execute('SELECT COUNT(*) n FROM moc_rate_events WHERE scope=? AND created_at>?',(scope,now-window)).fetchone()['n']
        if count>=limit:
            return False
        conn.execute('INSERT INTO moc_rate_events(scope,created_at) VALUES(?,?)',(scope,now))
        return True

    # ========================================================================
    # OPERATOR AUTHENTICATION
    # ========================================================================
    
    def operator_login(self, username: str, password: str, ip_address: str = None, mfa_code: str = None) -> Dict[str, Any]:
        failure={'success':False,'message':'Invalid credentials or authentication temporarily unavailable'}
        if not isinstance(username,str) or not isinstance(password,str) or not 1<=len(username)<=80 or not 1<=len(password)<=1024:
            return failure
        with self.service.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            allowed=self._reserve_rate(conn,'login-ip:'+str(ip_address or 'unknown'),30,900)
            account_allowed=self._reserve_rate(conn,'login-user:'+username.casefold(),8,900)
            if not allowed or not account_allowed:
                return failure
            # Persist throttles even for a failed authentication.
            conn.commit()
            conn.execute('BEGIN IMMEDIATE')
            row=conn.execute('SELECT * FROM moc_operators WHERE username=?',(username,)).fetchone()
            if not row or not row['active'] or not verify_password(password,row['password_hash'],row['password_salt'],row['password_iterations']):
                return failure
            if row['mfa_enabled'] and (not row['mfa_secret'] or not verify_totp(row['mfa_secret'],mfa_code)):
                return failure
            token=secrets.token_urlsafe(48)
            conn.execute('INSERT INTO moc_sessions(token_hash,operator_id,credential_hash,expires_at) VALUES(?,?,?,?)',
                         (hashlib.sha256(token.encode()).hexdigest(),row['id'],self._credential_hash(row),(datetime.utcnow()+timedelta(hours=4)).isoformat()))
            conn.execute('UPDATE moc_operators SET last_login_at=? WHERE id=?',(datetime.utcnow().isoformat(),row['id']))
            self._log_audit(conn,row['id'],row['username'],None,'LOGIN',json.dumps({'ip_address':ip_address}),ip_address)
            return {'success':True,'token':token,'operator':{'id':row['id'],'username':row['username'],'display_name':row['display_name'],'email':row['email'],'role':row['role']},'message':'Login successful'}

    def verify_operator_token(self, token: str) -> Optional[Dict[str, Any]]:
        if not isinstance(token,str) or not 20<=len(token)<=256:
            return None
        with self.service.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            session=conn.execute("SELECT * FROM moc_sessions WHERE token_hash=? AND revoked_at='' AND expires_at>?",(hashlib.sha256(token.encode()).hexdigest(),datetime.utcnow().isoformat())).fetchone()
            if not session:
                return None
            row=conn.execute('SELECT * FROM moc_operators WHERE id=?',(session['operator_id'],)).fetchone()
            if not row or not row['active'] or not secrets.compare_digest(session['credential_hash'],self._credential_hash(row)):
                conn.execute('UPDATE moc_sessions SET revoked_at=? WHERE token_hash=?',(datetime.utcnow().isoformat(),session['token_hash']))
                return None
            return {'operator_id':row['id'],'username':row['username'],'role':row['role']}

    def revoke_operator_token(self, token):
        with self.service.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row=conn.execute("SELECT operator_id FROM moc_sessions WHERE token_hash=? AND revoked_at=''",(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
            conn.execute('UPDATE moc_sessions SET revoked_at=? WHERE token_hash=?',(datetime.utcnow().isoformat(),hashlib.sha256(token.encode()).hexdigest()))
            if row:
                op=conn.execute('SELECT username FROM moc_operators WHERE id=?',(row['operator_id'],)).fetchone()
                self._log_audit(conn,row['operator_id'],op['username'],None,'LOGOUT','{}')

    # ========================================================================
    # MATCH MANAGEMENT
    # ========================================================================
    
    def create_match(self, operator_id: int, operator_username: str, match_data: Dict[str, Any], session_token=None) -> Dict[str, Any]:
        """Create new MOC match
        
        Args:
            operator_id: ID of operator creating match
            operator_username: Username for audit
            match_data: Match details
                {
                    'arena': str,
                    'title': str,
                    'description': str (optional),
                    'scheduled_at': ISO timestamp,
                    'betting_opens_at': ISO timestamp (optional),
                    'betting_closes_at': ISO timestamp (optional),
                    'red_name': str (default: 'Meron'),
                    'red_odds': float (default: 1.85),
                    'blue_name': str (default: 'Wala'),
                    'blue_odds': float (default: 1.85),
                    'draw_odds': float (default: 6.00),
                    'stream_type': str (default: 'HLS'),
                    'stream_url': str (optional),
                    'status': str (default: 'SCHEDULED')
                }
        
        Returns:
            {
                'success': bool,
                'match': {...},
                'message': str
            }
        """
        conn = self.service.connect()
        try:
            from manual_payments_server import clean_text, clean_media_url
            from cockfight_engine import timestamp, parse_timestamp
            match_data=dict(match_data)
            for key,label,minimum,maximum,default in [('title','Game title',3,90,None),('arena','Arena',2,60,None),('red_name','Red corner name',1,50,'Meron'),('blue_name','Blue corner name',1,50,'Wala')]:
                value=match_data.get(key,default)
                if not isinstance(value,str): raise ValueError(f'{label} must be text.')
                match_data[key]=clean_text(value,label,minimum,maximum)
            status=match_data.get('status','SCHEDULED')
            if status not in {'DRAFT','SCHEDULED'}: raise ValueError('A new match must begin as draft or scheduled.')
            for key,default in [('red_odds',1.85),('blue_odds',1.85),('draw_odds',6)]:
                raw=match_data.get(key,default)
                if isinstance(raw,bool): raise ValueError('Enter valid decimal odds.')
                value=float(raw)
                if not math.isfinite(value) or not 1.01<=value<=100: raise ValueError('Odds must be finite and between 1.01 and 100.')
                match_data[key]=round(value,2)
            for key in ('scheduled_at','betting_opens_at','betting_closes_at'):
                match_data[key]=timestamp(match_data.get(key),key)
            if not parse_timestamp(match_data['betting_opens_at'])<=parse_timestamp(match_data['betting_closes_at'])<=parse_timestamp(match_data['scheduled_at']): raise ValueError('Betting must open and close before the match starts.')
            stream=match_data.get('stream_type','OFFLINE')
            if stream not in {'HLS','YOUTUBE','VIDEO','WHEP','OFFLINE'}: raise ValueError('Invalid stream type.')
            match_data['stream_type']=stream
            match_data['stream_url']=clean_media_url(match_data.get('stream_url',''),'Playback URL')
            if stream!='OFFLINE' and not match_data['stream_url']: raise ValueError('Playback URL is required.')
            for key in ('visible','featured'):
                if key in match_data and not isinstance(match_data[key],bool): raise ValueError(f'{key} must be true or false.')
            if match_data.get('description') is not None:
                if not isinstance(match_data['description'],str) or len(match_data['description'])>1000: raise ValueError('Description must be text of at most 1000 characters.')
            conn.execute("BEGIN IMMEDIATE")
            operator = self._authorize(conn, operator_id, operator_username, {'operator','super_admin'}, session_token)
            # Get next fight number
            cursor = conn.execute(
                "SELECT value FROM moc_settings WHERE key = 'next_fight_number'"
            )
            counter=cursor.fetchone()
            highest=conn.execute('SELECT COALESCE(MAX(fight_number),0) AS n FROM moc_matches').fetchone()['n']
            fight_number = max(int(counter[0]) if counter else 1,int(highest)+1)
            match_id = f"MOC-{fight_number}"
            
            # Prepare match data
            now = datetime.utcnow().isoformat()
            status = match_data.get('status', 'SCHEDULED')
            
            cursor = conn.execute("""
                INSERT INTO moc_matches (
                    match_id, fight_number, arena, title, description,
                    status, scheduled_at, betting_opens_at, betting_closes_at,
                    red_name, red_odds, blue_name, blue_odds, draw_odds,
                    stream_type, stream_url, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                match_id,
                fight_number,
                match_data['arena'],
                match_data['title'],
                match_data.get('description'),
                status,
                match_data.get('scheduled_at'),
                match_data.get('betting_opens_at'),
                match_data.get('betting_closes_at'),
                match_data.get('red_name', 'Meron'),
                match_data.get('red_odds', 1.85),
                match_data.get('blue_name', 'Wala'),
                match_data.get('blue_odds', 1.85),
                match_data.get('draw_odds', 6.00),
                match_data.get('stream_type', 'HLS'),
                match_data.get('stream_url'),
                operator_id,
                now,
                now
            ))
            
            # Increment fight number
            conn.execute('UPDATE moc_matches SET visible=?,featured=? WHERE match_id=?',(int(match_data.get('visible',True)),int(match_data.get('featured',False)),match_id))
            conn.execute(
                "INSERT INTO moc_settings(value,updated_at,key) VALUES(?,?,'next_fight_number') ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
                (str(fight_number + 1), now)
            )
            
            # Log action
            self._log_audit(conn, operator_id, operator_username, match_id, 'CREATE_MATCH',
                          json.dumps({'fight_number': fight_number, 'arena': match_data['arena']}))
            
            conn.commit()
            
            # Fetch created match
            match = self.get_match(match_id)
            if hasattr(self.service,'moc_feed'):
                self.service.moc_feed.poll_once()
            
            return {
                'success': True,
                'match': match,
                'message': f'Match {match_id} created successfully'
            }
        
        except Exception as e:
            logger.error(f"Error creating match: {e}")
            conn.rollback()
            return {'success': False, 'message': f'Failed to create match: {str(e)}'}
        finally:
            conn.close()
    
    def update_match_status(self, operator_id: int, operator_username: str, match_id: str, 
                           new_status: str, password_verify: str = None, session_token=None) -> Dict[str, Any]:
        """Update match status (lifecycle control)
        
        Args:
            operator_id: ID of operator
            operator_username: Username for audit
            match_id: Match ID (e.g., 'MOC-42')
            new_status: New status to set
            password_verify: Required for sensitive actions (declare result)
        
        Returns:
            {
                'success': bool,
                'match': {...},
                'message': str
            }
        """
        conn = self.service.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            operator = self._authorize(conn, operator_id, operator_username, {'operator','super_admin'}, session_token)
            if new_status in {'CANCELLED','COMPLETED'} and not verify_password(str(password_verify or ''),operator['password_hash'],operator['password_salt'],operator['password_iterations']):
                raise ValueError('Password confirmation is required.')
            # Verify match exists
            cursor = conn.execute(
                "SELECT status FROM moc_matches WHERE match_id = ?",
                (match_id,)
            )
            row = cursor.fetchone()
            if not row:
                return {'success': False, 'message': f'Match {match_id} not found'}
            
            old_status = row[0]
            if new_status=='COMPLETED':
                result_row=conn.execute('SELECT result FROM moc_matches WHERE match_id=?',(match_id,)).fetchone()
                if not result_row['result']: raise ValueError('Completion requires an official result.')
                # Completion is an authoritative settlement outcome, never an operator flag.
                conn.commit()
                self.service.moc_feed.poll_once()
                match=self.get_match(match_id)
                return {'success':match['status']=='COMPLETED','match':match,'message':'Settlement completed' if match['status']=='COMPLETED' else 'Settlement remains pending'}
            
            # Validate status transition
            valid_transitions = {
                'DRAFT': ['SCHEDULED', 'CANCELLED'],
                'SCHEDULED': ['BETTING_OPEN', 'CANCELLED'],
                'BETTING_OPEN': ['BETTING_CLOSED', 'CANCELLED'],
                'BETTING_CLOSED': ['LIVE', 'CANCELLED'],
                'LIVE': ['AWAITING_RESULT', 'CANCELLED'],
                'AWAITING_RESULT': ['COMPLETED'],
            }
            
            if old_status not in valid_transitions or new_status not in valid_transitions[old_status]:
                return {
                    'success': False,
                    'message': f'Invalid status transition: {old_status} → {new_status}'
                }
            
            # Update status
            now = datetime.utcnow().isoformat()
            update_fields = {'status': new_status, 'updated_at': now}
            
            if new_status == 'BETTING_OPEN':
                update_fields['betting_opens_at'] = now
            elif new_status == 'BETTING_CLOSED':
                update_fields['betting_closes_at'] = now
            elif new_status == 'LIVE':
                update_fields['started_at'] = now
            elif new_status == 'COMPLETED':
                update_fields['completed_at'] = now
            
            # Build UPDATE query
            set_clause = ', '.join([f"{k} = ?" for k in update_fields.keys()])
            values = list(update_fields.values()) + [match_id]
            
            conn.execute(
                f"UPDATE moc_matches SET {set_clause} WHERE match_id = ?",
                values
            )
            if new_status=='CANCELLED': conn.execute("UPDATE moc_matches SET result='cancelled',result_declared_at=? WHERE match_id=?",(now,match_id))
            
            # Log action
            action_name = {
                'BETTING_OPEN': 'OPEN_BETTING',
                'BETTING_CLOSED': 'CLOSE_BETTING',
                'LIVE': 'START_MATCH',
                'COMPLETED': 'SETTLE_MATCH',
                'CANCELLED': 'CANCEL_MATCH'
            }.get(new_status, 'UPDATE_MATCH')
            
            self._log_audit(conn, operator_id, operator_username, match_id, action_name,
                          json.dumps({'old_status': old_status, 'new_status': new_status}))
            
            conn.commit()
            
            # Fetch updated match
            self.service.moc_feed.poll_once()
            match = self.get_match(match_id)
            
            return {
                'success': True,
                'match': match,
                'message': f'Match {match_id} status updated to {new_status}'
            }
        
        except Exception as e:
            logger.error(f"Error updating match status: {e}")
            conn.rollback()
            return {'success': False, 'message': f'Failed to update status: {str(e)}'}
        finally:
            conn.close()
    
    def declare_result(self, operator_id: int, operator_username: str, match_id: str, 
                      result: str, password_verify: str, session_token=None) -> Dict[str, Any]:
        """Declare match result
        
        Args:
            operator_id: ID of operator
            operator_username: Username for audit
            match_id: Match ID
            result: 'red', 'blue', 'draw', or 'cancelled'
            password_verify: Operator password for confirmation
        
        Returns:
            {
                'success': bool,
                'match': {...},
                'settlement': {...},
                'message': str
            }
        """
        conn = self.service.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            operator = self._authorize(conn, operator_id, operator_username, {'operator','super_admin'}, session_token)
            # Verify operator password
            cursor = conn.execute(
                "SELECT password_hash, password_salt, password_iterations FROM moc_operators WHERE id = ?",
                (operator_id,)
            )
            row = cursor.fetchone()
            if not row or not verify_password(password_verify, row[0], row[1], row[2]):
                return {'success': False, 'message': 'Invalid password confirmation'}
            
            # Verify match status
            cursor = conn.execute(
                "SELECT status,result FROM moc_matches WHERE match_id = ?",
                (match_id,)
            )
            row = cursor.fetchone()
            if not row:
                return {'success': False, 'message': f'Match {match_id} not found'}
            
            status = row[0]
            if row[1] and row[1]!=result: raise ValueError('An official result is immutable.')
            if row[1]==result:
                conn.commit()
                self.service.moc_feed.poll_once()
                return {'success':True,'match':self.get_match(match_id),'message':'Official result already recorded.'}
            if status not in ['LIVE', 'AWAITING_RESULT']:
                return {'success': False, 'message': f'Cannot declare result for match in {status} status'}
            
            # Validate result
            if result not in ['red', 'blue', 'draw', 'cancelled']:
                return {'success': False, 'message': f'Invalid result: {result}'}
            
            # Update match with result
            now = datetime.utcnow().isoformat()
            conn.execute("""
                UPDATE moc_matches 
                SET result = ?, result_declared_at = ?, result_declared_by = ?,
                    status = 'AWAITING_RESULT', updated_at = ?
                WHERE match_id = ?
            """, (result, now, operator_id, now, match_id))
            
            # Log action
            self._log_audit(conn, operator_id, operator_username, match_id, 'DECLARE_RESULT',
                          json.dumps({'result': result}))
            
            conn.commit()
            
            # Fetch updated match
            self.service.moc_feed.poll_once()
            match = self.get_match(match_id)
            
            # TODO: Trigger settlement in main platform
            # The MOCFeedEngine will pick this up and settle bets
            
            return {
                'success': True,
                'match': match,
                'message': f'Result declared: {result}. Settlement will be processed automatically.'
            }
        
        except Exception as e:
            logger.error(f"Error declaring result: {e}")
            conn.rollback()
            return {'success': False, 'message': f'Failed to declare result: {str(e)}'}
        finally:
            conn.close()
    
    def get_match(self, match_id: str) -> Optional[Dict[str, Any]]:
        """Get single match by ID
        
        Args:
            match_id: Match ID (e.g., 'MOC-42')
        
        Returns:
            Match dict or None
        """
        conn = self.service.connect()
        try:
            cursor = conn.execute("""
                SELECT 
                    id, match_id, fight_number, arena, title, description,
                    status, betting_opens_at, betting_closes_at, scheduled_at,
                    started_at, completed_at,
                    red_name, red_odds, blue_name, blue_odds, draw_odds,
                    result, result_declared_at, result_declared_by,
                    stream_type, stream_url, stream_health,
                    total_bets, total_stakes, red_bets, red_stakes,
                    blue_bets, blue_stakes, draw_bets, draw_stakes,
                    total_payout, visible, featured, created_by, created_at
                FROM moc_matches WHERE match_id = ?
            """, (match_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return self._format_match_row(row)
        finally:
            conn.close()
    
    def list_matches(self, filters: Dict[str, Any] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """List matches with filters
        
        Args:
            filters: Optional filters
                {
                    'status': str or List[str],
                    'visible': bool,
                    'created_by': int,
                    'date_from': ISO timestamp,
                    'date_to': ISO timestamp
                }
            limit: Max matches to return
        
        Returns:
            List of match dicts
        """
        conn = self.service.connect()
        try:
            query = """
                SELECT 
                    id, match_id, fight_number, arena, title, description,
                    status, betting_opens_at, betting_closes_at, scheduled_at,
                    started_at, completed_at,
                    red_name, red_odds, blue_name, blue_odds, draw_odds,
                    result, result_declared_at, result_declared_by,
                    stream_type, stream_url, stream_health,
                    total_bets, total_stakes, red_bets, red_stakes,
                    blue_bets, blue_stakes, draw_bets, draw_stakes,
                    total_payout, visible, featured, created_by, created_at
                FROM moc_matches
                WHERE 1=1
            """
            params = []
            
            if filters:
                if 'status' in filters:
                    if isinstance(filters['status'], list):
                        placeholders = ','.join(['?' for _ in filters['status']])
                        query += f" AND status IN ({placeholders})"
                        params.extend(filters['status'])
                    else:
                        query += " AND status = ?"
                        params.append(filters['status'])
                
                if 'visible' in filters:
                    query += " AND visible = ?"
                    params.append(1 if filters['visible'] else 0)
                
                if 'created_by' in filters:
                    query += " AND created_by = ?"
                    params.append(filters['created_by'])
            
            query += " ORDER BY fight_number DESC LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            
            return [self._format_match_row(row) for row in rows]
        finally:
            conn.close()
    
    def _format_match_row(self, row) -> Dict[str, Any]:
        """Format match database row as dict"""
        return {
            'id': row[0],
            'match_id': row[1],
            'fight_number': row[2],
            'arena': row[3],
            'title': row[4],
            'description': row[5],
            'status': row[6],
            'betting_opens_at': row[7],
            'betting_closes_at': row[8],
            'scheduled_at': row[9],
            'started_at': row[10],
            'completed_at': row[11],
            'outcomes': {
                'red': {
                    'name': row[12],
                    'odds': row[13],
                    'bet_count': row[23] or 0,
                    'total_stakes': row[24] or 0.0
                },
                'blue': {
                    'name': row[14],
                    'odds': row[15],
                    'bet_count': row[25] or 0,
                    'total_stakes': row[26] or 0.0
                },
                'draw': {
                    'odds': row[16],
                    'bet_count': row[27] or 0,
                    'total_stakes': row[28] or 0.0
                }
            },
            'result': row[17],
            'result_declared_at': row[18],
            'result_declared_by': row[19],
            'stream': {
                'type': row[20],
                'url': row[21],
                'health': row[22]
            },
            'stats': {
                'total_bets': row[23] or 0,
                'total_stakes': row[24] or 0.0,
                'total_payout': row[29] or 0.0
            },
            'visible': bool(row[30]),
            'featured': bool(row[31]),
            'created_by': row[32],
            'created_at': row[33]
        }
    
    # ========================================================================
    # MOC FEED API (For External Platforms)
    # ========================================================================
    
    def verify_api_key(self, api_key: str, ip_address: str = None) -> Optional[Dict[str, Any]]:
        """Verify API key and check rate limits
        
        Args:
            api_key: Full API key string
            ip_address: Client IP for logging
        
        Returns:
            API key info dict or None if invalid/rate limited
        """
        if not isinstance(api_key, str) or not 20 <= len(api_key) <= 256:
            return None
        # Hash the provided key
        key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
        
        conn = self.service.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute("""
                SELECT id, key_id, platform_name, permissions, rate_limit, 
                       rate_window_seconds, active, expires_at, allowed_ips
                FROM moc_api_keys
                WHERE key_hash = ?
            """, (key_hash,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            key_id, key_id_str, platform_name, permissions_json, rate_limit, rate_window, active, expires_at, allowed_ips_json = row
            
            # Check if active
            if not active:
                logger.warning(f"Inactive API key used: {key_id_str}")
                return None
            
            # Check expiration
            if expires_at:
                expiry = datetime.fromisoformat(expires_at)
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry.astimezone(timezone.utc) <= datetime.now(timezone.utc):
                    logger.warning(f"Expired API key used: {key_id_str}")
                    return None
            
            # Check IP whitelist
            if allowed_ips_json:
                allowed_ips = json.loads(allowed_ips_json)
                if allowed_ips and ip_address not in allowed_ips:
                    logger.warning(f"API key {key_id_str} used from unauthorized IP: {ip_address}")
                    return None
            
            # Durable, transactionally serialized partner request quota.
            if not self._reserve_rate(conn,'api:'+key_hash,int(rate_limit),int(rate_window)):
                return None

            # Update usage
            conn.execute("""
                UPDATE moc_api_keys 
                SET usage_count = usage_count + 1, last_used_at = ?
                WHERE id = ?
            """, (datetime.utcnow().isoformat(), key_id))
            conn.commit()
            
            return {
                'key_id': key_id,
                'key_id_str': key_id_str,
                'platform_name': platform_name,
                'permissions': json.loads(permissions_json) if permissions_json else ['read']
            }
        
        finally:
            conn.close()
    
    def log_api_usage(self, api_key_id: int, endpoint: str, method: str, 
                     status_code: int, response_time_ms: int, 
                     ip_address: str = None, user_agent: str = None):
        """Log API key usage
        
        Args:
            api_key_id: API key ID
            endpoint: Endpoint path
            method: HTTP method
            status_code: Response status code
            response_time_ms: Response time in milliseconds
            ip_address: Client IP
            user_agent: Client user agent
        """
        conn = self.service.connect()
        try:
            retention = conn.execute("SELECT value FROM moc_settings WHERE key='audit_log_retention_days'").fetchone()
            days = max(1,min(3650,int(retention[0] if retention else 365)))
            conn.execute('DELETE FROM moc_api_key_usage WHERE created_at<?',((datetime.utcnow()-timedelta(days=days)).isoformat(),))
            conn.execute("""
                INSERT INTO moc_api_key_usage (
                    api_key_id, endpoint, method, status_code, response_time_ms,
                    ip_address, user_agent, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                api_key_id, endpoint, method, status_code, response_time_ms,
                ip_address, user_agent, datetime.utcnow().isoformat()
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"Error logging API usage: {e}")
        finally:
            conn.close()
    
    def feed_current_match(self) -> Optional[Dict[str, Any]]:
        """Get current active match for feed API
        
        Returns:
            Current match dict or None
        """
        matches = self.list_matches(
            filters={'status': ['BETTING_OPEN', 'BETTING_CLOSED', 'LIVE']},
            limit=1
        )
        
        if matches:
            return matches[0]
        
        # If no active match, return next scheduled
        matches = self.list_matches(
            filters={'status': 'SCHEDULED'},
            limit=1
        )
        return matches[0] if matches else None
    
    def feed_upcoming_matches(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get upcoming scheduled matches for feed API
        
        Args:
            limit: Max matches to return
        
        Returns:
            List of match dicts
        """
        return self.list_matches(
            filters={'status': 'SCHEDULED', 'visible': True},
            limit=limit
        )
    
    def feed_recent_results(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent completed matches for feed API
        
        Args:
            limit: Max matches to return
        
        Returns:
            List of match dicts
        """
        return self.list_matches(
            filters={'status': 'COMPLETED', 'visible': True},
            limit=limit
        )
    
    # ========================================================================
    # API KEY MANAGEMENT
    # ========================================================================
    
    def create_api_key(self, operator_id: int, operator_username: str, 
                      platform_name: str, platform_url: str = None,
                      contact_email: str = None, permissions: List[str] = None,
                      rate_limit: int = 100, allowed_ips=None, expires_at=None, session_token=None) -> Dict[str, Any]:
        """Create new API key for external platform
        
        Args:
            operator_id: ID of operator creating key
            operator_username: Username for audit
            platform_name: Name of platform
            platform_url: Platform URL (optional)
            contact_email: Contact email (optional)
            permissions: List of permissions (default: ['read'])
            rate_limit: Requests per minute (default: 100)
        
        Returns:
            {
                'success': bool,
                'api_key': str,  # Full API key (show once!)
                'key_id': str,
                'message': str
            }
        """
        conn = self.service.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            operator = self._authorize(conn, operator_id, operator_username, {'super_admin'}, session_token)
            if not isinstance(rate_limit,int) or isinstance(rate_limit,bool) or not 1<=rate_limit<=10000:
                raise ValueError('Rate limit must be an integer between 1 and 10000.')
            if permissions is not None and (not isinstance(permissions,list) or not permissions or any(p!='read' for p in permissions)):
                raise ValueError('Only read permission is supported.')
            if not isinstance(platform_name, str) or not 1 <= len(platform_name.strip()) <= 100:
                raise ValueError('A bounded platform name is required.')
            if allowed_ips is None:
                allowed_ips = []
            if not isinstance(allowed_ips, list) or len(allowed_ips) > 100:
                raise ValueError('Allowed IPs must be a bounded list.')
            allowed_ips = [str(ipaddress.ip_address(value)) for value in allowed_ips]
            if expires_at:
                expiry = datetime.fromisoformat(str(expires_at).replace('Z', '+00:00'))
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                expiry = expiry.astimezone(timezone.utc)
                if expiry <= datetime.now(timezone.utc):
                    raise ValueError('Expiry must be in the future.')
                expires_at = expiry.isoformat()
            # Generate API key
            key_id = f"moc_key_{secrets.token_hex(8)}"
            api_key = f"moc_sk_{secrets.token_hex(32)}"
            key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
            
            # Prepare permissions
            if permissions is None:
                permissions = ['read']
            permissions_json = json.dumps(permissions)
            
            # Insert API key
            conn.execute("""
                INSERT INTO moc_api_keys (
                    key_id, api_key, key_hash, platform_name, platform_url,
                    contact_email, permissions, rate_limit, rate_window_seconds,
                    active, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                key_id, "redacted:"+key_id, key_hash, platform_name, platform_url,
                contact_email, permissions_json, rate_limit, 60,
                1, operator_id, datetime.utcnow().isoformat()
            ))
            
            conn.execute('UPDATE moc_api_keys SET allowed_ips=?,expires_at=? WHERE key_id=?',(json.dumps(allowed_ips),expires_at,key_id))

            # Log action
            self._log_audit(conn, operator_id, operator_username, None, 'CREATE_API_KEY',
                          json.dumps({'key_id': key_id, 'platform_name': platform_name}))
            
            conn.commit()
            
            return {
                'success': True,
                'api_key': api_key,
                'key_id': key_id,
                'message': 'API key created successfully. Save this key - it will not be shown again!'
            }
        
        except Exception as e:
            logger.error(f"Error creating API key: {e}")
            conn.rollback()
            return {'success': False, 'message': f'Failed to create API key: {str(e)}'}
        finally:
            conn.close()
    
    # ========================================================================
    # AUDIT LOGGING
    # ========================================================================
    
    def revoke_api_key(self, operator_id, operator_username, key_id, reason, session_token=None):
        with self.service.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            self._authorize(conn,operator_id,operator_username,{'super_admin'},session_token)
            if not isinstance(reason,str) or not 3<=len(reason)<=300:
                raise ValueError('A revocation reason is required.')
            row=conn.execute('SELECT id FROM moc_api_keys WHERE key_id=?',(key_id,)).fetchone()
            if not row:
                return {'success':False,'message':'Key not found'}
            conn.execute('UPDATE moc_api_keys SET active=0,revoked_at=?,revoked_by=?,revoked_reason=? WHERE id=?',(datetime.utcnow().isoformat(),operator_id,reason,row['id']))
            self._log_audit(conn,operator_id,operator_username,None,'REVOKE_API_KEY',json.dumps({'key_id':key_id,'reason':reason}))
            return {'success':True}

    def update_operator(self, operator_id, operator_username, target_id, payload, session_token=None):
        """Authorized account changes revoke every target session in the same transaction."""
        with self.service.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            self._authorize(conn,operator_id,operator_username,{'super_admin'},session_token)
            target=conn.execute('SELECT * FROM moc_operators WHERE id=?',(target_id,)).fetchone()
            if not target:
                raise ValueError('Operator not found.')
            active=payload.get('active',bool(target['active']))
            role=payload.get('role',target['role'])
            if not isinstance(active,bool) or role not in {'super_admin','operator','monitor','technician'}:
                raise ValueError('Invalid operator status or role.')
            if target['active'] and target['role']=='super_admin' and (not active or role!='super_admin'):
                others=conn.execute("SELECT COUNT(*) n FROM moc_operators WHERE active=1 AND role='super_admin' AND id<>?",(target_id,)).fetchone()['n']
                if not others:
                    raise ValueError('The last active super admin must be preserved.')
            digest,salt,iterations=target['password_hash'],target['password_salt'],target['password_iterations']
            if 'password' in payload:
                password=validate_password(payload['password'])
                if password=='MOCAdmin@2026':
                    raise ValueError('The published MOC password is prohibited.')
                digest,salt,iterations=hash_password(password)
            now=datetime.utcnow().isoformat()
            conn.execute('UPDATE moc_operators SET active=?,role=?,password_hash=?,password_salt=?,password_iterations=?,updated_at=? WHERE id=?',(int(active),role,digest,salt,iterations,now,target_id))
            conn.execute("UPDATE moc_sessions SET revoked_at=? WHERE operator_id=? AND revoked_at=''",(now,target_id))
            self._log_audit(conn,operator_id,operator_username,None,'UPDATE_OPERATOR',json.dumps({'target_id':target_id,'active':active,'role':role,'password_changed':'password' in payload}))
            return {'success':True}

    def _log_audit(self, conn: sqlite3.Connection, operator_id: int,
                   operator_username: str, match_id: str, action: str, 
                   details: str = None, ip_address: str = None, 
                   user_agent: str = None):
        """Log operator action to audit trail
        
        Args:
            conn: Database connection
            operator_id: Operator ID
            operator_username: Operator username
            match_id: Match ID (optional)
            action: Action name
            details: JSON details (optional)
            ip_address: Client IP (optional)
            user_agent: Client user agent (optional)
        """
        try:
            conn.execute("""
                INSERT INTO moc_audit_log (
                    operator_id, operator_username, match_id, action,
                    details, ip_address, user_agent, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                operator_id, operator_username, match_id, action,
                details, ip_address, user_agent, datetime.utcnow().isoformat()
            ))
        except Exception as e:
            logger.error(f"Error logging audit: {e}")
            raise
    
    def get_audit_log(self, filters: Dict[str, Any] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit log entries
        
        Args:
            filters: Optional filters
                {
                    'operator_id': int,
                    'match_id': str,
                    'action': str,
                    'date_from': ISO timestamp,
                    'date_to': ISO timestamp
                }
            limit: Max entries to return
        
        Returns:
            List of audit log entries
        """
        conn = self.service.connect()
        try:
            query = """
                SELECT id, operator_id, operator_username, match_id, action,
                       details, ip_address, user_agent, created_at
                FROM moc_audit_log
                WHERE 1=1
            """
            params = []
            
            if filters:
                if 'operator_id' in filters:
                    query += " AND operator_id = ?"
                    params.append(filters['operator_id'])
                
                if 'match_id' in filters:
                    query += " AND match_id = ?"
                    params.append(filters['match_id'])
                
                if 'action' in filters:
                    query += " AND action = ?"
                    params.append(filters['action'])
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            
            return [
                {
                    'id': row[0],
                    'operator_id': row[1],
                    'operator_username': row[2],
                    'match_id': row[3],
                    'action': row[4],
                    'details': json.loads(row[5]) if row[5] else None,
                    'ip_address': row[6],
                    'user_agent': row[7],
                    'created_at': row[8]
                }
                for row in rows
            ]
        finally:
            conn.close()
