# ===== database.py =====
import logging
from datetime import datetime, timedelta
import random
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, config):
        self.config = config
        
        # MongoDB Connection
        try:
            self.client = MongoClient(config.MONGODB_URI)
            self.db = self.client[config.MONGODB_DB]
            
            # Test connection
            self.client.admin.command('ping')
            logger.info("✅ MongoDB Connected Successfully!")
            
            # Initialize collections
            self.users = self.db['users']
            self.transactions = self.db['transactions']
            self.withdrawals = self.db['withdrawals']
            self.referrals = self.db['referrals']
            self.issues = self.db['issues']
            self.spin_history = self.db['spin_history']
            
            # Create indexes
            self.users.create_index('user_id', unique=True)
            self.referrals.create_index('referred_id', unique=True)
            self.transactions.create_index('user_id')
            self.withdrawals.create_index('user_id')
            self.withdrawals.create_index('status')
            
        except ConnectionFailure as e:
            logger.error(f"MongoDB Connection Error: {e}")
            raise e
    
    def get_user(self, user_id):
        """Get user data"""
        try:
            user = self.users.find_one({'user_id': user_id})
            if user:
                user['_id'] = str(user['_id'])
            return user
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None
    
    def add_user(self, user_data):
        """Add new user"""
        try:
            # Check if user exists
            existing = self.users.find_one({'user_id': user_data['user_id']})
            if existing:
                self.users.update_one(
                    {'user_id': user_data['user_id']},
                    {'$set': {'last_active': datetime.now().isoformat()}}
                )
                return False
            
            # Add new user
            now = datetime.now().isoformat()
            
            new_user = {
                'user_id': user_data['user_id'],
                'first_name': user_data.get('first_name', ''),
                'username': user_data.get('username', ''),
                'referrer_id': user_data.get('referrer_id'),
                'balance': 5.0,
                'total_earned': 5.0,
                'spins': 3,
                'tier': 1,
                'total_refs': 0,
                'active_refs': 0,
                'pending_refs': 0,
                'monthly_refs': 0,
                'daily_streak': 0,
                'last_daily': None,
                'channel_joined': False,
                'payment_method': None,
                'payment_details': None,
                'total_searches': 0,
                'join_date': now,
                'last_active': now,
                'is_admin': user_data['user_id'] in self.config.ADMIN_IDS
            }
            
            self.users.insert_one(new_user)
            
            self.add_transaction(
                user_data['user_id'],
                'welcome_bonus',
                5.0,
                'Welcome bonus'
            )
            
            if user_data.get('referrer_id'):
                self.referrals.insert_one({
                    'referrer_id': user_data['referrer_id'],
                    'referred_id': user_data['user_id'],
                    'join_date': now,
                    'last_search': None,
                    'earnings': 0,
                    'is_active': True
                })
                
                self.users.update_one(
                    {'user_id': user_data['referrer_id']},
                    {
                        '$inc': {
                            'total_refs': 1,
                            'pending_refs': 1,
                            'monthly_refs': 1
                        }
                    }
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return False
    
    def update_user(self, user_id, updates):
        """Update user data"""
        try:
            self.users.update_one(
                {'user_id': user_id},
                {'$set': updates}
            )
            return True
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            return False
    
    def add_balance(self, user_id, amount, description=""):
        """Add balance to user"""
        try:
            self.users.update_one(
                {'user_id': user_id},
                {
                    '$inc': {
                        'balance': amount,
                        'total_earned': amount
                    }
                }
            )
            
            self.add_transaction(
                user_id,
                'credit',
                amount,
                description or 'Balance added'
            )
            
            return True
        except Exception as e:
            logger.error(f"Error adding balance: {e}")
            return False
    
    def add_transaction(self, user_id, type_, amount, description=""):
        """Add transaction"""
        try:
            transaction = {
                'user_id': user_id,
                'type': type_,
                'amount': amount,
                'description': description,
                'timestamp': datetime.now().isoformat(),
                'status': 'completed'
            }
            self.transactions.insert_one(transaction)
            return True
        except Exception as e:
            logger.error(f"Error adding transaction: {e}")
            return False
    
    def process_spin(self, user_id):
        """Process spin"""
        try:
            user = self.get_user(user_id)
            if not user or user.get('spins', 0) <= 0:
                return None
            
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
            
            rand_val = random.randint(1, 100)
            cumulative = 0
            selected = prizes[0]
            
            for prize in prizes:
                cumulative += prize['prob']
                if rand_val <= cumulative:
                    selected = prize
                    break
            
            self.users.update_one(
                {'user_id': user_id},
                {
                    '$inc': {
                        'spins': -1,
                        'balance': selected['prize'],
                        'total_earned': selected['prize']
                    }
                }
            )
            
            self.spin_history.insert_one({
                'user_id': user_id,
                'prize': selected['prize'],
                'prize_name': selected['name'],
                'spin_date': datetime.now().isoformat()
            })
            
            if selected['prize'] > 0:
                self.add_transaction(
                    user_id,
                    'spin_win',
                    selected['prize'],
                    f"Spin win: {selected['name']}"
                )
            
            updated = self.get_user(user_id)
            
            return {
                'prize': selected['prize'],
                'prize_name': selected['name'],
                'remaining_spins': updated.get('spins', 0)
            }
            
        except Exception as e:
            logger.error(f"Error processing spin: {e}")
            return None
    
    def claim_daily_bonus(self, user_id):
        """Claim daily bonus"""
        try:
            user = self.get_user(user_id)
            if not user:
                return None
            
            now = datetime.now()
            today = now.date().isoformat()
            
            last_daily = user.get('last_daily')
            if last_daily and last_daily.startswith(today):
                return None
            
            streak = 1
            if last_daily:
                try:
                    last_date = datetime.fromisoformat(last_daily).date()
                    if (now.date() - last_date).days == 1:
                        streak = user.get('daily_streak', 0) + 1
                except:
                    streak = 1
            
            base_bonus = self.config.DAILY_BONUS
            streak_bonus = min(streak * 0.02, 0.10)
            total_bonus = base_bonus + streak_bonus
            
            self.users.update_one(
                {'user_id': user_id},
                {
                    '$inc': {
                        'balance': total_bonus,
                        'total_earned': total_bonus
                    },
                    '$set': {
                        'daily_streak': streak,
                        'last_daily': now.isoformat()
                    }
                }
            )
            
            self.add_transaction(
                user_id,
                'daily_bonus',
                total_bonus,
                f"Daily bonus (streak: {streak})"
            )
            
            return {
                'bonus': total_bonus,
                'streak': streak,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Error claiming daily: {e}")
            return None
    
    def process_withdrawal(self, user_id, amount, method, details):
        """Process withdrawal request"""
        try:
            user = self.get_user(user_id)
            
            if not user:
                return {'success': False, 'message': 'User not found'}
            
            if user['balance'] < amount:
                return {'success': False, 'message': 'Insufficient balance'}
            
            if amount < self.config.MIN_WITHDRAWAL:
                return {'success': False, 'message': f'Minimum withdrawal is ₹{self.config.MIN_WITHDRAWAL}'}
            
            self.users.update_one(
                {'user_id': user_id},
                {'$inc': {'balance': -amount}}
            )
            
            now = datetime.now().isoformat()
            self.withdrawals.insert_one({
                'user_id': user_id,
                'amount': amount,
                'method': method,
                'details': details,
                'status': 'pending',
                'request_date': now,
                'processed_date': None,
                'admin_note': None
            })
            
            self.add_transaction(
                user_id,
                'withdrawal_request',
                -amount,
                f"Withdrawal request via {method}"
            )
            
            return {'success': True, 'message': 'Withdrawal request submitted'}
            
        except Exception as e:
            logger.error(f"Error processing withdrawal: {e}")
            return {'success': False, 'message': 'Internal error'}
    
    def increment_search_count(self, user_id):
        """Increment user's search count"""
        try:
            self.users.update_one(
                {'user_id': user_id},
                {
                    '$inc': {'total_searches': 1},
                    '$set': {'last_active': datetime.now().isoformat()}
                }
            )
            
            self.referrals.update_one(
                {'referred_id': user_id},
                {'$set': {'last_search': datetime.now().isoformat()}}
            )
        except Exception as e:
            logger.error(f"Error incrementing search: {e}")
    
    def get_leaderboard(self, limit=10):
        """Get leaderboard"""
        try:
            users = self.users.find(
                {},
                {'user_id': 1, 'first_name': 1, 'balance': 1, 'total_refs': 1}
            ).sort('balance', -1).limit(limit)
            
            result = []
            for i, user in enumerate(users):
                result.append({
                    'rank': i + 1,
                    'name': user.get('first_name', 'User')[:10],
                    'balance': user.get('balance', 0),
                    'total_refs': user.get('total_refs', 0)
                })
            
            return result
        except Exception as e:
            logger.error(f"Leaderboard error: {e}")
            return []
    
    def get_user_missions(self, user_id):
        """Get user missions"""
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
        try:
            self.issues.insert_one({
                'user_id': user_id,
                'issue': issue,
                'report_date': datetime.now().isoformat(),
                'status': 'pending'
            })
            return True
        except Exception as e:
            logger.error(f"Error adding issue: {e}")
            return False
    
    def update_withdrawal_status(self, withdrawal_id, status):
        """Update withdrawal status"""
        try:
            from bson.objectid import ObjectId
            self.withdrawals.update_one(
                {'_id': ObjectId(withdrawal_id)},
                {
                    '$set': {
                        'status': status,
                        'processed_date': datetime.now().isoformat()
                    }
                }
            )
            return True
        except Exception as e:
            logger.error(f"Error updating withdrawal: {e}")
            return False
    
    def get_pending_withdrawals(self):
        """Get pending withdrawals"""
        try:
            withdrawals = self.withdrawals.find({'status': 'pending'}).sort('request_date', 1)
            result = []
            for w in withdrawals:
                w['_id'] = str(w['_id'])
                result.append(w)
            return result
        except Exception as e:
            logger.error(f"Error getting withdrawals: {e}")
            return []
