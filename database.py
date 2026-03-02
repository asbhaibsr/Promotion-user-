# ===== database.py =====
import sqlite3
import json
import logging
from datetime import datetime, timedelta
import random

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, config):
        self.config = config
        self.db_path = config.DB_PATH
        self.init_db()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                username TEXT,
                referrer_id INTEGER,
                balance REAL DEFAULT 0,
                total_earned REAL DEFAULT 0,
                spins INTEGER DEFAULT 3,
                tier INTEGER DEFAULT 1,
                total_refs INTEGER DEFAULT 0,
                active_refs INTEGER DEFAULT 0,
                pending_refs INTEGER DEFAULT 0,
                monthly_refs INTEGER DEFAULT 0,
                daily_streak INTEGER DEFAULT 0,
                last_daily TEXT,
                channel_joined INTEGER DEFAULT 0,
                payment_method TEXT,
                payment_details TEXT,
                total_searches INTEGER DEFAULT 0,
                join_date TEXT,
                last_active TEXT,
                is_admin INTEGER DEFAULT 0,
                FOREIGN KEY (referrer_id) REFERENCES users (user_id)
            )
        ''')
        
        # Transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT,
                amount REAL,
                description TEXT,
                timestamp TEXT,
                status TEXT DEFAULT 'completed',
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Withdrawals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                method TEXT,
                details TEXT,
                status TEXT DEFAULT 'pending',
                request_date TEXT,
                processed_date TEXT,
                admin_note TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Referrals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER UNIQUE,
                join_date TEXT,
                last_search TEXT,
                earnings REAL DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (referrer_id) REFERENCES users (user_id),
                FOREIGN KEY (referred_id) REFERENCES users (user_id)
            )
        ''')
        
        # Daily earnings table (for referral commissions)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_earnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                date TEXT,
                source TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Issues table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                issue TEXT,
                report_date TEXT,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Spin history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS spin_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                prize REAL,
                prize_name TEXT,
                spin_date TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Config table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized")
    
    def add_user(self, user_data):
        """Add new user to database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_data['user_id'],))
        existing = cursor.fetchone()
        
        if existing:
            # Update last_active
            cursor.execute(
                "UPDATE users SET last_active = ? WHERE user_id = ?",
                (datetime.now().isoformat(), user_data['user_id'])
            )
            conn.commit()
            conn.close()
            return False
        
        # Add new user
        now = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO users (
                user_id, first_name, username, referrer_id, 
                balance, total_earned, spins, tier,
                total_refs, active_refs, pending_refs, monthly_refs,
                daily_streak, last_daily, channel_joined, 
                total_searches, join_date, last_active, is_admin
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_data['user_id'],
            user_data.get('first_name', ''),
            user_data.get('username', ''),
            user_data.get('referrer_id'),
            5.0,  # Welcome bonus
            5.0,  # Total earned starts with welcome
            3,    # Starting spins
            1,    # Starting tier
            0, 0, 0, 0,  # ref counts
            0,  # streak
            None,  # last daily
            0,  # channel joined
            0,  # total searches
            now,  # join date
            now,  # last active
            1 if user_data['user_id'] in self.config.ADMIN_IDS else 0
        ))
        
        # Add transaction for welcome bonus
        cursor.execute('''
            INSERT INTO transactions (user_id, type, amount, description, timestamp, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            user_data['user_id'],
            'welcome_bonus',
            5.0,
            'Welcome bonus',
            now,
            'completed'
        ))
        
        # Handle referral
        if user_data.get('referrer_id'):
            # Add to referrals table
            cursor.execute('''
                INSERT INTO referrals (referrer_id, referred_id, join_date, is_active)
                VALUES (?, ?, ?, ?)
            ''', (
                user_data['referrer_id'],
                user_data['user_id'],
                now,
                1
            ))
            
            # Update referrer counts
            cursor.execute('''
                UPDATE users 
                SET total_refs = total_refs + 1,
                    pending_refs = pending_refs + 1,
                    monthly_refs = monthly_refs + 1
                WHERE user_id = ?
            ''', (user_data['referrer_id'],))
        
        conn.commit()
        conn.close()
        return True
    
    def get_user(self, user_id):
        """Get user data"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def update_user(self, user_id, updates):
        """Update user data"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        set_clause = ', '.join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values()) + [user_id]
        
        cursor.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", values)
        conn.commit()
        conn.close()
        
        return True
    
    def add_balance(self, user_id, amount, description=""):
        """Add balance to user"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users 
            SET balance = balance + ?,
                total_earned = total_earned + ?
            WHERE user_id = ?
        ''', (amount, amount, user_id))
        
        # Add transaction
        cursor.execute('''
            INSERT INTO transactions (user_id, type, amount, description, timestamp, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            'credit',
            amount,
            description or 'Balance added',
            datetime.now().isoformat(),
            'completed'
        ))
        
        conn.commit()
        conn.close()
        return True
    
    def add_transaction(self, user_id, type_, amount, description=""):
        """Add transaction record"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO transactions (user_id, type, amount, description, timestamp, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            type_,
            amount,
            description,
            datetime.now().isoformat(),
            'completed'
        ))
        
        conn.commit()
        conn.close()
        return True
    
    def process_spin(self, user_id):
        """Process spin and return prize"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check user spins
        cursor.execute("SELECT spins, balance FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user or user['spins'] <= 0:
            conn.close()
            return None
        
        # Define prizes (probability weighted)
        prizes = [
            {'prize': 0, 'name': 'Better luck next time', 'prob': 40},
            {'prize': 0.05, 'name': '₹0.05', 'prob': 20},
            {'prize': 0.10, 'name': '₹0.10', 'prob': 15},
            {'prize': 0.20, 'name': '₹0.20', 'prob': 10},
            {'prize': 0.50, 'name': '₹0.50', 'prob': 7},
            {'prize': 1.00, 'name': '₹1.00', 'prob': 5},
            {'prize': 2.00, 'name': '₹2.00', 'prob': 2},
            {'prize': 5.00, 'name': '₹5.00 JACKPOT! 🎉', 'prob': 1}
        ]
        
        # Select prize based on probability
        rand_val = random.randint(1, 100)
        cumulative = 0
        selected_prize = prizes[0]  # Default
        
        for prize in prizes:
            cumulative += prize['prob']
            if rand_val <= cumulative:
                selected_prize = prize
                break
        
        # Update spins and balance
        cursor.execute('''
            UPDATE users 
            SET spins = spins - 1,
                balance = balance + ?,
                total_earned = total_earned + ?
            WHERE user_id = ?
        ''', (selected_prize['prize'], selected_prize['prize'], user_id))
        
        # Record spin
        cursor.execute('''
            INSERT INTO spin_history (user_id, prize, prize_name, spin_date)
            VALUES (?, ?, ?, ?)
        ''', (
            user_id,
            selected_prize['prize'],
            selected_prize['name'],
            datetime.now().isoformat()
        ))
        
        # Add transaction if won
        if selected_prize['prize'] > 0:
            cursor.execute('''
                INSERT INTO transactions (user_id, type, amount, description, timestamp, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                'spin_win',
                selected_prize['prize'],
                f"Spin win: {selected_prize['name']}",
                datetime.now().isoformat(),
                'completed'
            ))
        
        # Get remaining spins
        cursor.execute("SELECT spins FROM users WHERE user_id = ?", (user_id,))
        remaining = cursor.fetchone()['spins']
        
        conn.commit()
        conn.close()
        
        return {
            'prize': selected_prize['prize'],
            'prize_name': selected_prize['name'],
            'remaining_spins': remaining
        }
    
    def claim_daily_bonus(self, user_id):
        """Claim daily bonus"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT last_daily, daily_streak FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return None
        
        now = datetime.now()
        today = now.date().isoformat()
        
        # Check if already claimed today
        if user['last_daily'] and user['last_daily'].startswith(today):
            conn.close()
            return None
        
        # Calculate streak
        streak = 1
        if user['last_daily']:
            last_date = datetime.fromisoformat(user['last_daily']).date()
            if (now.date() - last_date).days == 1:
                streak = user['daily_streak'] + 1
            else:
                streak = 1
        else:
            streak = 1
        
        # Calculate bonus amount
        base_bonus = self.config.DAILY_BONUS
        streak_bonus = min(streak * 0.02, 0.10)  # Max extra ₹0.10
        total_bonus = base_bonus + streak_bonus
        
        # Update user
        cursor.execute('''
            UPDATE users 
            SET balance = balance + ?,
                total_earned = total_earned + ?,
                daily_streak = ?,
                last_daily = ?
            WHERE user_id = ?
        ''', (total_bonus, total_bonus, streak, now.isoformat(), user_id))
        
        # Add transaction
        cursor.execute('''
            INSERT INTO transactions (user_id, type, amount, description, timestamp, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            'daily_bonus',
            total_bonus,
            f"Daily bonus (streak: {streak})",
            now.isoformat(),
            'completed'
        ))
        
        conn.commit()
        conn.close()
        
        return {
            'bonus': total_bonus,
            'streak': streak,
            'success': True
        }
    
    def process_withdrawal(self, user_id, amount, method, details):
        """Process withdrawal request"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check user balance
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return {'success': False, 'message': 'User not found'}
        
        if user['balance'] < amount:
            conn.close()
            return {'success': False, 'message': 'Insufficient balance'}
        
        if amount < self.config.MIN_WITHDRAWAL:
            conn.close()
            return {'success': False, 'message': f'Minimum withdrawal is ₹{self.config.MIN_WITHDRAWAL}'}
        
        # Deduct balance
        cursor.execute('''
            UPDATE users SET balance = balance - ? WHERE user_id = ?
        ''', (amount, user_id))
        
        # Create withdrawal record
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO withdrawals (user_id, amount, method, details, status, request_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, amount, method, details, 'pending', now))
        
        # Add transaction
        cursor.execute('''
            INSERT INTO transactions (user_id, type, amount, description, timestamp, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            'withdrawal_request',
            -amount,
            f"Withdrawal request via {method}",
            now,
            'pending'
        ))
        
        conn.commit()
        conn.close()
        
        return {'success': True, 'message': 'Withdrawal request submitted'}
    
    def increment_search_count(self, user_id):
        """Increment user's search count and process referral earnings"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users SET total_searches = total_searches + 1,
                           last_active = ?
            WHERE user_id = ?
        ''', (datetime.now().isoformat(), user_id))
        
        # Update referral's last search
        cursor.execute('''
            UPDATE referrals SET last_search = ? WHERE referred_id = ?
        ''', (datetime.now().isoformat(), user_id))
        
        conn.commit()
        conn.close()
    
    def process_daily_referral_earnings(self):
        """CRON job: Process daily earnings for referrals"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        today = datetime.now().date().isoformat()
        
        # Get all active referrals (users who searched in last 24h)
        cursor.execute('''
            SELECT r.referrer_id, r.referred_id, u.tier, u.tier_rate
            FROM referrals r
            JOIN users u ON u.user_id = r.referrer_id
            WHERE r.is_active = 1 AND 
                  r.last_search IS NOT NULL AND
                  date(r.last_search) = date('now')
        ''')
        
        earnings_by_referrer = {}
        
        for row in cursor.fetchall():
            referrer_id = row['referrer_id']
            rate = self.config.get_tier_rate(row['tier'])
            earnings_by_referrer[referrer_id] = earnings_by_referrer.get(referrer_id, 0) + rate
        
        # Apply earnings
        for referrer_id, amount in earnings_by_referrer.items():
            cursor.execute('''
                UPDATE users 
                SET balance = balance + ?,
                    total_earned = total_earned + ?
                WHERE user_id = ?
            ''', (amount, amount, referrer_id))
            
            cursor.execute('''
                INSERT INTO daily_earnings (user_id, amount, date, source)
                VALUES (?, ?, ?, ?)
            ''', (referrer_id, amount, today, 'referral_commissions'))
            
            cursor.execute('''
                INSERT INTO transactions (user_id, type, amount, description, timestamp, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                referrer_id,
                'referral_commission',
                amount,
                f'Daily referral earnings for {today}',
                datetime.now().isoformat(),
                'completed'
            ))
        
        conn.commit()
        conn.close()
        
        return len(earnings_by_referrer)
    
    def get_leaderboard(self, limit=10):
        """Get top users by balance"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, first_name, balance, total_refs, total_earned
            FROM users
            ORDER BY balance DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for i, row in enumerate(rows):
            user = dict(row)
            user['rank'] = i + 1
            user['name'] = user['first_name'][:10]  # Truncate long names
            result.append(user)
        
        return result
    
    def get_user_missions(self, user_id):
        """Get user missions and progress"""
        user = self.get_user(user_id)
        
        if not user:
            return {}
        
        missions = {
            'daily_search': {
                'name': 'Daily Searches',
                'icon': '🔍',
                'count': user.get('total_searches', 0),
                'target': 5,
                'reward': 0.25,
                'completed': user.get('total_searches', 0) >= 5
            },
            'referral': {
                'name': 'Get Referrals',
                'icon': '👥',
                'count': user.get('total_refs', 0),
                'target': 3,
                'reward': 1.0,
                'completed': user.get('total_refs', 0) >= 3
            },
            'spin_master': {
                'name': 'Spin Wheel',
                'icon': '🎡',
                'count': 0,  # Would need to query spin history
                'target': 10,
                'reward': 0.50,
                'completed': False
            },
            'streak': {
                'name': 'Daily Streak',
                'icon': '🔥',
                'count': user.get('daily_streak', 0),
                'target': 7,
                'reward': 2.0,
                'completed': user.get('daily_streak', 0) >= 7
            }
        }
        
        return missions
    
    def add_issue_report(self, user_id, issue):
        """Add issue report"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO issues (user_id, issue, report_date, status)
            VALUES (?, ?, ?, ?)
        ''', (user_id, issue, datetime.now().isoformat(), 'pending'))
        
        conn.commit()
        conn.close()
        
        return True
    
    def update_withdrawal_status(self, withdrawal_id, status):
        """Update withdrawal status"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE withdrawals 
            SET status = ?, processed_date = ?
            WHERE id = ?
        ''', (status, datetime.now().isoformat(), withdrawal_id))
        
        conn.commit()
        conn.close()
        
        return True
