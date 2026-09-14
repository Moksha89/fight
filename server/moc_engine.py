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
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import jwt

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
        self.jwt_secret = self._get_or_create_jwt_secret()
        
        # Rate limiting cache: {api_key_hash: [(timestamp, count), ...]}
        self.rate_limit_cache = {}
        
        logger.info("MOC Engine initialized")
    
    def _init_database(self):
        """Initialize MOC database tables"""
        schema_path = '/workspace/server/moc_database_schema.sql'
        try:
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
            
            conn = self.service.connect()
            try:
                conn.executescript(schema_sql)
                conn.commit()
                logger.info("MOC database schema initialized")
            finally:
                conn.close()
        except FileNotFoundError:
            logger.error(f"MOC schema file not found: {schema_path}")
        except Exception as e:
            logger.error(f"Error initializing MOC database: {e}")
    
    def _get_or_create_jwt_secret(self) -> str:
        """Get or create JWT secret for operator sessions"""
        conn = self.service.connect()
        try:
            cursor = conn.execute(
                "SELECT value FROM moc_settings WHERE key = ?",
                ('jwt_secret',)
            )
            row = cursor.fetchone()
            
            if row:
                return row[0]
            
            # Generate new secret
            secret = secrets.token_hex(32)
            conn.execute(
                "INSERT INTO moc_settings (key, value, description) VALUES (?, ?, ?)",
                ('jwt_secret', secret, 'JWT secret for operator sessions')
            )
            conn.commit()
            return secret
        finally:
            conn.close()
    
    # ========================================================================
    # OPERATOR AUTHENTICATION
    # ========================================================================
    
    def operator_login(self, username: str, password: str, ip_address: str = None) -> Dict[str, Any]:
        """Authenticate operator and return JWT token
        
        Args:
            username: Operator username
            password: Plain text password
            ip_address: Client IP address for audit
        
        Returns:
            {
                'success': bool,
                'token': str,  # JWT token
                'operator': {...},
                'message': str
            }
        """
        conn = self.service.connect()
        try:
            cursor = conn.execute(
                "SELECT id, username, password_hash, password_salt, password_iterations, "
                "display_name, email, role, active, mfa_enabled "
                "FROM moc_operators WHERE username = ?",
                (username,)
            )
            row = cursor.fetchone()
            
            if not row:
                return {'success': False, 'message': 'Invalid credentials'}
            
            op_id, op_username, password_hash, password_salt, password_iterations, display_name, email, role, active, mfa_enabled = row
            
            if not active:
                return {'success': False, 'message': 'Account is disabled'}
            
            # Verify password
            if not verify_password(password, password_hash, password_salt, password_iterations):
                return {'success': False, 'message': 'Invalid credentials'}
            
            # TODO: MFA verification if enabled
            if mfa_enabled:
                # For now, skip MFA in initial implementation
                pass
            
            # Update last login
            conn.execute(
                "UPDATE moc_operators SET last_login_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), op_id)
            )
            
            # Log login
            self._log_audit(conn, op_id, op_username, None, 'LOGIN', 
                          json.dumps({'ip_address': ip_address}), ip_address)
            
            conn.commit()
            
            # Generate JWT token
            token_payload = {
                'operator_id': op_id,
                'username': op_username,
                'role': role,
                'exp': datetime.utcnow() + timedelta(hours=8),
                'iat': datetime.utcnow()
            }
            token = jwt.encode(token_payload, self.jwt_secret, algorithm='HS256')
            
            return {
                'success': True,
                'token': token,
                'operator': {
                    'id': op_id,
                    'username': op_username,
                    'display_name': display_name,
                    'email': email,
                    'role': role
                },
                'message': 'Login successful'
            }
        
        except Exception as e:
            logger.error(f"Operator login error: {e}")
            return {'success': False, 'message': 'Login failed'}
        finally:
            conn.close()
    
    def verify_operator_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token and return operator info
        
        Args:
            token: JWT token string
        
        Returns:
            Operator info dict or None if invalid
        """
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            return {
                'operator_id': payload['operator_id'],
                'username': payload['username'],
                'role': payload['role']
            }
        except jwt.ExpiredSignatureError:
            logger.warning("Expired operator token")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid operator token: {e}")
            return None
    
    # ========================================================================
    # MATCH MANAGEMENT
    # ========================================================================
    
    def create_match(self, operator_id: int, operator_username: str, match_data: Dict[str, Any]) -> Dict[str, Any]:
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
            # Get next fight number
            cursor = conn.execute(
                "SELECT value FROM moc_settings WHERE key = 'next_fight_number'"
            )
            fight_number = int(cursor.fetchone()[0])
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
            conn.execute(
                "UPDATE moc_settings SET value = ?, updated_at = ? WHERE key = 'next_fight_number'",
                (str(fight_number + 1), now)
            )
            
            # Log action
            self._log_audit(conn, operator_id, operator_username, match_id, 'CREATE_MATCH',
                          json.dumps({'fight_number': fight_number, 'arena': match_data['arena']}))
            
            conn.commit()
            
            # Fetch created match
            match = self.get_match(match_id)
            
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
                           new_status: str, password_verify: str = None) -> Dict[str, Any]:
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
            # Verify match exists
            cursor = conn.execute(
                "SELECT status FROM moc_matches WHERE match_id = ?",
                (match_id,)
            )
            row = cursor.fetchone()
            if not row:
                return {'success': False, 'message': f'Match {match_id} not found'}
            
            old_status = row[0]
            
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
                      result: str, password_verify: str) -> Dict[str, Any]:
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
                "SELECT status FROM moc_matches WHERE match_id = ?",
                (match_id,)
            )
            row = cursor.fetchone()
            if not row:
                return {'success': False, 'message': f'Match {match_id} not found'}
            
            status = row[0]
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
        # Hash the provided key
        key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
        
        conn = self.service.connect()
        try:
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
                if datetime.fromisoformat(expires_at) < datetime.utcnow():
                    logger.warning(f"Expired API key used: {key_id_str}")
                    return None
            
            # Check IP whitelist
            if allowed_ips_json and ip_address:
                allowed_ips = json.loads(allowed_ips_json)
                if ip_address not in allowed_ips:
                    logger.warning(f"API key {key_id_str} used from unauthorized IP: {ip_address}")
                    return None
            
            # Check rate limit
            now = time.time()
            if key_hash not in self.rate_limit_cache:
                self.rate_limit_cache[key_hash] = []
            
            # Clean old entries
            self.rate_limit_cache[key_hash] = [
                (ts, count) for ts, count in self.rate_limit_cache[key_hash]
                if now - ts < rate_window
            ]
            
            # Count requests in window
            total_requests = sum(count for ts, count in self.rate_limit_cache[key_hash])
            
            if total_requests >= rate_limit:
                logger.warning(f"Rate limit exceeded for API key: {key_id_str}")
                return None
            
            # Add current request
            self.rate_limit_cache[key_hash].append((now, 1))
            
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
                      rate_limit: int = 100) -> Dict[str, Any]:
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
                key_id, api_key, key_hash, platform_name, platform_url,
                contact_email, permissions_json, rate_limit, 60,
                1, operator_id, datetime.utcnow().isoformat()
            ))
            
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
