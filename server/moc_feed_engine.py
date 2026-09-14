"""
MOC Feed Engine

Integrates MOC (Match Operations Center) with main RoosterRun platform
Polls MOC API and mirrors matches to main platform

Similar to ChinaFeedEngine but for internal MOC matches

Author: RoosterRun Development Team
Created: 2026-09-14
"""

import logging
import requests
import threading
import time
import json
from datetime import datetime
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class MOCFeedEngine:
    """MOC Feed Integration Engine"""
    
    def __init__(self, payment_service):
        """Initialize MOC Feed Engine
        
        Args:
            payment_service: Parent PaymentService instance
        """
        self.service = payment_service
        self.db_path = payment_service.db_path
        self.moc_engine = None  # Will be set to payment_service.moc
        self.current_match = None
        self.worker = None
        self.running = False
        
        # Load settings
        self._settings = self._load_settings()
        
        logger.info("MOC Feed Engine initialized")
    
    def _load_settings(self) -> Dict[str, Any]:
        """Load MOC feed settings from database"""
        conn = self.service.connect()
        try:
            cursor = conn.execute("""
                SELECT key, value FROM moc_settings 
                WHERE key IN (
                    'enabled', 'feed_poll_interval_seconds', 
                    'moc_category_slug', 'auto_mirror_matches'
                )
            """)
            rows = cursor.fetchall()
            
            settings = {
                'enabled': False,
                'poll_seconds': 3,
                'category_slug': 'moc-feed',
                'auto_mirror': True,
                'feature_current': True
            }
            
            for key, value in rows:
                if key == 'enabled':
                    settings['enabled'] = value.lower() == 'true'
                elif key == 'feed_poll_interval_seconds':
                    settings['poll_seconds'] = int(value)
                elif key == 'moc_category_slug':
                    settings['category_slug'] = value
            
            return settings
        finally:
            conn.close()
    
    def settings(self) -> Dict[str, Any]:
        """Get current settings"""
        return self._settings.copy()
    
    def update_settings(self, new_settings: Dict[str, Any], actor: str = 'SYSTEM'):
        """Update MOC feed settings
        
        Args:
            new_settings: Settings to update
            actor: Who made the change (for logging)
        """
        conn = self.service.connect()
        try:
            if 'enabled' in new_settings:
                enabled = bool(new_settings['enabled'])
                conn.execute(
                    "UPDATE moc_settings SET value = ?, updated_at = ? WHERE key = 'enabled'",
                    ('true' if enabled else 'false', datetime.utcnow().isoformat())
                )
                self._settings['enabled'] = enabled
                
                # Start or stop polling based on enabled status
                if enabled and not self.running:
                    self.start_polling()
                elif not enabled and self.running:
                    self.stop_polling()
            
            if 'poll_seconds' in new_settings:
                poll_seconds = int(new_settings['poll_seconds'])
                conn.execute(
                    "UPDATE moc_settings SET value = ?, updated_at = ? WHERE key = 'feed_poll_interval_seconds'",
                    (str(poll_seconds), datetime.utcnow().isoformat())
                )
                self._settings['poll_seconds'] = poll_seconds
            
            if 'category_slug' in new_settings:
                category_slug = str(new_settings['category_slug'])
                conn.execute(
                    "UPDATE moc_settings SET value = ?, updated_at = ? WHERE key = 'moc_category_slug'",
                    (category_slug, datetime.utcnow().isoformat())
                )
                self._settings['category_slug'] = category_slug
            
            conn.commit()
            logger.info(f"MOC feed settings updated by {actor}: {new_settings}")
        
        except Exception as e:
            logger.error(f"Error updating MOC feed settings: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def poll_current_match(self) -> Optional[Dict[str, Any]]:
        """Poll MOC for current match
        
        Returns:
            Current match dict or None
        """
        if not self.moc_engine:
            logger.error("MOC engine not initialized")
            return None
        
        try:
            # Get current match directly from MOC engine
            match = self.moc_engine.feed_current_match()
            return match
        except Exception as e:
            logger.error(f"Error polling MOC current match: {e}")
            return None
    
    def mirror_match_to_platform(self, moc_match: Dict[str, Any]):
        """Mirror MOC match to main platform games table
        
        Args:
            moc_match: MOC match dict
        """
        conn = self.service.connect()
        try:
            # Check if game already exists (by MOC match_id)
            cursor = conn.execute("""
                SELECT id, status FROM games 
                WHERE category_slug = ? AND title LIKE ?
            """, (self._settings['category_slug'], f"%{moc_match['match_id']}%"))
            
            existing = cursor.fetchone()
            
            # Map MOC status to platform status
            status_map = {
                'DRAFT': 'SCHEDULED',
                'SCHEDULED': 'SCHEDULED',
                'BETTING_OPEN': 'BETTING_OPEN',
                'BETTING_CLOSED': 'BETTING_CLOSED',
                'LIVE': 'LIVE',
                'AWAITING_RESULT': 'AWAITING_RESULT',
                'COMPLETED': 'SETTLED',
                'CANCELLED': 'CANCELLED'
            }
            
            platform_status = status_map.get(moc_match['status'], 'SCHEDULED')
            
            # Prepare game data
            now = datetime.utcnow().isoformat()
            title = f"{moc_match['title']} ({moc_match['match_id']})"
            
            if existing:
                # Update existing game
                game_id, current_status = existing
                
                # Only update if status changed or stats updated
                cursor.execute("""
                    UPDATE games SET
                        status = ?,
                        team_a_name = ?,
                        team_a_odds = ?,
                        team_b_name = ?,
                        team_b_odds = ?,
                        draw_odds = ?,
                        stream_type = ?,
                        stream_url = ?,
                        result = ?,
                        result_declared_at = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    platform_status,
                    moc_match['outcomes']['red']['name'],
                    moc_match['outcomes']['red']['odds'],
                    moc_match['outcomes']['blue']['name'],
                    moc_match['outcomes']['blue']['odds'],
                    moc_match['outcomes']['draw']['odds'],
                    moc_match['stream']['type'],
                    moc_match['stream']['url'],
                    moc_match.get('result'),
                    moc_match.get('result_declared_at'),
                    now,
                    game_id
                ))
                
                logger.debug(f"Updated platform game {game_id} from MOC match {moc_match['match_id']}")
            
            else:
                # Create new game
                cursor.execute("""
                    INSERT INTO games (
                        title, arena, category_slug, status,
                        team_a_name, team_a_odds, team_b_name, team_b_odds, draw_odds,
                        stream_type, stream_url, scheduled_at,
                        featured, visible, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    title,
                    moc_match['arena'],
                    self._settings['category_slug'],
                    platform_status,
                    moc_match['outcomes']['red']['name'],
                    moc_match['outcomes']['red']['odds'],
                    moc_match['outcomes']['blue']['name'],
                    moc_match['outcomes']['blue']['odds'],
                    moc_match['outcomes']['draw']['odds'],
                    moc_match['stream']['type'],
                    moc_match['stream']['url'],
                    moc_match.get('scheduled_at'),
                    1 if self._settings['feature_current'] else 0,
                    1,
                    now,
                    now
                ))
                
                game_id = cursor.lastrowid
                logger.info(f"Created platform game {game_id} from MOC match {moc_match['match_id']}")
            
            conn.commit()
            
            # If result declared, trigger settlement
            if moc_match.get('result') and platform_status == 'SETTLED':
                self._settle_game_bets(game_id, moc_match['result'])
        
        except Exception as e:
            logger.error(f"Error mirroring MOC match to platform: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def _settle_game_bets(self, game_id: int, result: str):
        """Settle all bets for a game
        
        Args:
            game_id: Platform game ID
            result: 'red', 'blue', 'draw', or 'cancelled'
        """
        conn = self.service.connect()
        try:
            # Map result to win_team
            result_map = {
                'red': 1,
                'blue': 2,
                'draw': 3,
                'cancelled': 4
            }
            
            win_team = result_map.get(result)
            if not win_team:
                logger.error(f"Invalid result for settlement: {result}")
                return
            
            # Update game result
            conn.execute("""
                UPDATE games SET win_team = ?, result_declared_at = ?, updated_at = ?
                WHERE id = ?
            """, (win_team, datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), game_id))
            
            # Get all pending bets for this game
            cursor = conn.execute("""
                SELECT id, user_id, outcome, stake, potential_payout
                FROM bets
                WHERE game_id = ? AND status = 'PENDING'
            """, (game_id,))
            
            bets = cursor.fetchall()
            
            for bet_id, user_id, outcome, stake, potential_payout in bets:
                # Map outcome to team number
                outcome_map = {'RED': 1, 'BLUE': 2, 'DRAW': 3}
                bet_team = outcome_map.get(outcome.upper())
                
                if result == 'cancelled':
                    # Refund stake
                    conn.execute("""
                        UPDATE bets SET status = 'CANCELLED', payout = ?, settled_at = ?
                        WHERE id = ?
                    """, (stake, datetime.utcnow().isoformat(), bet_id))
                    
                    # Credit wallet
                    conn.execute("""
                        UPDATE wallets SET wallet_balance = wallet_balance + ?
                        WHERE user_id = ?
                    """, (stake, user_id))
                    
                    logger.info(f"Refunded bet {bet_id} (₹{stake}) to user {user_id}")
                
                elif bet_team == win_team:
                    # Winning bet
                    conn.execute("""
                        UPDATE bets SET status = 'WON', payout = ?, settled_at = ?
                        WHERE id = ?
                    """, (potential_payout, datetime.utcnow().isoformat(), bet_id))
                    
                    # Credit wallet
                    conn.execute("""
                        UPDATE wallets SET wallet_balance = wallet_balance + ?
                        WHERE user_id = ?
                    """, (potential_payout, user_id))
                    
                    logger.info(f"Settled winning bet {bet_id} (₹{potential_payout}) to user {user_id}")
                
                else:
                    # Losing bet
                    conn.execute("""
                        UPDATE bets SET status = 'LOST', payout = 0, settled_at = ?
                        WHERE id = ?
                    """, (datetime.utcnow().isoformat(), bet_id))
                    
                    logger.info(f"Settled losing bet {bet_id} for user {user_id}")
            
            conn.commit()
            logger.info(f"Settled {len(bets)} bets for game {game_id} with result: {result}")
        
        except Exception as e:
            logger.error(f"Error settling game bets: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def start_polling(self):
        """Start background polling worker"""
        if self.running:
            logger.warning("MOC feed polling already running")
            return
        
        if not self._settings['enabled']:
            logger.info("MOC feed disabled, not starting polling")
            return
        
        self.running = True
        self.worker = threading.Thread(target=self._poll_loop, daemon=True)
        self.worker.start()
        logger.info(f"MOC feed polling started (interval: {self._settings['poll_seconds']}s)")
    
    def stop_polling(self):
        """Stop background polling worker"""
        if not self.running:
            return
        
        self.running = False
        if self.worker:
            self.worker.join(timeout=5)
        
        logger.info("MOC feed polling stopped")
    
    def _poll_loop(self):
        """Background polling loop"""
        while self.running:
            try:
                # Poll current match
                match = self.poll_current_match()
                
                if match:
                    self.current_match = match
                    
                    # Mirror to platform if auto-mirror enabled
                    if self._settings['auto_mirror']:
                        self.mirror_match_to_platform(match)
                
                else:
                    self.current_match = None
            
            except Exception as e:
                logger.error(f"Error in MOC feed poll loop: {e}")
            
            # Sleep for poll interval
            time.sleep(self._settings['poll_seconds'])
    
    def get_current_match(self) -> Optional[Dict[str, Any]]:
        """Get currently cached match
        
        Returns:
            Current match dict or None
        """
        return self.current_match
