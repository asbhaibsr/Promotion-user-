# ===== database.py (FIXED COMPLETE) =====
import logging
from datetime import datetime, timedelta
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure
from cachetools import TTLCache
import certifi

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, config):
        self.config = config
        self.connected = False
        self.user_cache = TTLCache(maxsize=1000, ttl=300)
        
        try:
            self.client = MongoClient(
                config.MONGODB_URI,
                serverSelectionTimeoutMS=5000,
                maxPoolSize=10,
                tlsCAFile=certifi.where()
            )
            
            self.client.admin.command('ping')
            self.db = self.client[config.MONGODB_DB]
            
            # Initialize collections
            self.users = self.db['users']
            self.transactions = self.db['transactions']
            self.withdrawals = self.db['withdrawals']
            self.referrals = self.db['referrals']
            self.issues = self.db['issues']
            self.daily_searches = self.db['daily_searches']
            self.search_logs = self.db['search_logs']
            self.channel_joins = self.db['channel_joins']
            self.system_stats = self.db['system_stats']
            
            # Create indexes
            self._create_indexes()
            
            self.connected = True
            logger.info("✅ MongoDB Connected Successfully!")
            
        except ConnectionFailure as e:
            logger.error(f"MongoDB Connection Error: {e}")
            self.connected = False
            raise e
    
    def _create_indexes(self):
        """Create all necessary indexes"""
        try:
            self.users.create_index('user_id', unique=True)
            self.users.create_index('referrer_id')
            self.users.create_index('last_active')
            self.users.create_index('balance')
            
            self.referrals.create_index([('referrer_id', ASCENDING), ('referred_id', ASCENDING)], unique=True)
            self.referrals.create_index('is_active')
            self.referrals.create_index('last_search_date')
            
            self.daily_searches.create_index([('user_id', ASCENDING), ('date', ASCENDING)], unique=True)
            self.search_logs.create_index([('user_id', ASCENDING), ('timestamp', DESCENDING)])
            self.search_logs.create_index('timestamp', expireAfterSeconds=2592000)  # 30 days TTL
            
            self.withdrawals.create_index([('user_id', ASCENDING), ('request_date', DESCENDING)])
            self.withdrawals.create_index('status')
            self.withdrawals.create_index('processed_date')
            
            self.channel_joins.create_index([('user_id', ASCENDING), ('channel_id', ASCENDING)], unique=True)
            
            logger.info("✅ Database indexes created")
        except Exception as e:
            logger.error(f"Index creation error: {e}")
    
    def ensure_connection(self):
        """Ensure database connection is alive"""
        if not self.connected:
            try:
                self.client.admin.command('ping')
                self.connected = True
            except:
                self.connected = False
        return self.connected
    
    def get_user(self, user_id):
        """Get user with caching"""
        if not self.ensure_connection():
            return None
        
        cache_key = f"user_{user_id}"
        if cache_key in self.user_cache:
            return self.user_cache[cache_key]
        
        try:
            user = self.users.find_one({'user_id': int(user_id)})
            if user:
                # Convert ObjectId to string for JSON
                if '_id' in user:
                    user['_id'] = str(user['_id'])
                
                self.user_cache[cache_key] = user
                
                # Update last active
                self.users.update_one(
                    {'user_id': int(user_id)},
                    {'$set': {'last_active': datetime.now().isoformat()}}
                )
                
            return user
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None
    
    def add_user(self, user_data):
        """Add new user"""
        if not self.ensure_connection():
            return False
        
        try:
            user_id = int(user_data['user_id'])
            referrer_id = user_data.get('referrer_id')
            if referrer_id:
                referrer_id = int(referrer_id)
            
            existing = self.users.find_one({'user_id': user_id})
            if existing:
                # Update existing
                self.users.update_one(
                    {'user_id': user_id},
                    {'$set': {
                        'first_name': user_data.get('first_name', ''),
                        'username': user_data.get('username', ''),
                        'last_active': datetime.now().isoformat()
                    }}
                )
                return False
            
            now = datetime.now().isoformat()
            
            new_user = {
                'user_id': user_id,
                'first_name': user_data.get('first_name', ''),
                'username': user_data.get('username', ''),
                'referrer_id': referrer_id,
                'balance': 0.0,
                'total_earned': 0.0,
                'tier': 1,
                'total_refs': 0,
                'active_refs': 0,
                'pending_refs': 1 if referrer_id else 0,
                'daily_streak': 0,
                'last_daily': None,
                'channel_joined': False,
                'total_searches': 0,
                'weekly_searches': 0,
                'join_date': now,
                'last_active': now,
                'is_admin': user_id in self.config.ADMIN_IDS,
                'suspicious_activity': False,
                'withdrawal_blocked': False,
                'warning_count': 0
            }
            
            self.users.insert_one(new_user)
            
            # Handle referral - CRITICAL FIX
            if referrer_id and referrer_id != user_id:
                # Check if referral already exists
                existing_ref = self.referrals.find_one({
                    'referrer_id': referrer_id,
                    'referred_id': user_id
                })
                
                if not existing_ref:
                    self.referrals.insert_one({
                        'referrer_id': referrer_id,
                        'referred_id': user_id,
                        'join_date': now,
                        'last_search_date': None,
                        'is_active': False,
                        'earnings': 0.0
                    })
                    
                    self.users.update_one(
                        {'user_id': referrer_id},
                        {'$inc': {'total_refs': 1, 'pending_refs': 1}}
                    )
                    
                    logger.info(f"✅ Referral recorded: {referrer_id} -> {user_id}")
            
            # Clear cache
            self.user_cache.pop(f"user_{user_id}", None)
            if referrer_id:
                self.user_cache.pop(f"user_{referrer_id}", None)
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return False
    
    def record_search(self, user_id):
        """Record user search - FIXED: Only affects referrer earnings, not user balance"""
        if not self.ensure_connection():
            return False
        
        try:
            user_id = int(user_id)
            now = datetime.now()
            today = now.date().isoformat()
            
            user = self.get_user(user_id)
            if not user:
                return False
            
            # Anti-cheat checks
            if user.get('suspicious_activity') or user.get('withdrawal_blocked'):
                logger.warning(f"User {user_id} blocked from searches")
                return False
            
            # Check daily limit
            daily_count = self.daily_searches.count_documents({
                'user_id': user_id,
                'date': today
            })
            
            if daily_count >= self.config.MAX_SEARCHES_PER_DAY:
                logger.warning(f"User {user_id} exceeded daily search limit")
                return False
            
            # Check minimum time between searches (anti-spam)
            last_search = self.search_logs.find_one(
                {'user_id': user_id},
                sort=[('timestamp', DESCENDING)]
            )
            
            if last_search:
                last_time = datetime.fromisoformat(last_search['timestamp'])
                if (now - last_time).total_seconds() < self.config.MIN_TIME_BETWEEN_SEARCHES:
                    logger.warning(f"User {user_id} searching too fast")
                    return False
            
            # Log search
            self.search_logs.insert_one({
                'user_id': user_id,
                'timestamp': now.isoformat(),
                'date': today
            })
            
            # Update daily search count
            self.daily_searches.update_one(
                {'user_id': user_id, 'date': today},
                {'$inc': {'count': 1}},
                upsert=True
            )
            
            # Update user stats (but NOT balance)
            was_first_search = (user.get('total_searches', 0) == 0)
            
            self.users.update_one(
                {'user_id': user_id},
                {
                    '$inc': {'total_searches': 1, 'weekly_searches': 1},
                    '$set': {'last_active': now.isoformat()}
                }
            )
            
            # CRITICAL FIX: Activate referral for referrer, NOT give money to searcher
            if was_first_search:
                self.activate_referral(user_id)
                # NO BALANCE ADDED FOR FIRST SEARCH - FIXED
            
            # CRITICAL FIX: Process daily earning for referrer
            referral = self.referrals.find_one({'referred_id': user_id})
            if referral and referral.get('is_active'):
                # Update last search date for this referral
                self.referrals.update_one(
                    {'_id': referral['_id']},
                    {'$set': {'last_search_date': now.isoformat()}}
                )
                
                # Check if this is first search of the day
                today_search = self.daily_searches.find_one({
                    'user_id': user_id,
                    'date': today
                })
                
                if today_search and today_search.get('count', 0) == 1:
                    # First search today - referrer will get paid at midnight
                    logger.info(f"Referral {user_id} active today for referrer {referral['referrer_id']}")
            
            # Clear cache
            self.user_cache.pop(f"user_{user_id}", None)
            if referral:
                self.user_cache.pop(f"user_{referral['referrer_id']}", None)
            
            logger.info(f"✅ Search recorded for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error recording search: {e}")
            return False
    
    def activate_referral(self, referred_id):
        """Activate referral when user searches first time"""
        try:
            referred_id = int(referred_id)
            referral = self.referrals.find_one({'referred_id': referred_id})
            
            if referral and not referral.get('is_active'):
                now = datetime.now().isoformat()
                
                self.referrals.update_one(
                    {'referred_id': referred_id},
                    {
                        '$set': {
                            'is_active': True,
                            'first_search_date': now
                        }
                    }
                )
                
                referrer_id = referral['referrer_id']
                
                self.users.update_one(
                    {'user_id': referrer_id},
                    {'$inc': {'pending_refs': -1, 'active_refs': 1}}
                )
                
                # Give referral bonus to REFERRER only
                self.add_balance(
                    referrer_id,
                    self.config.REFERRAL_BONUS,
                    f"Referral bonus for user {referred_id}"
                )
                
                self.update_user_tier(referrer_id)
                
                # Clear cache
                self.user_cache.pop(f"user_{referrer_id}", None)
                
                logger.info(f"✅ Referral activated: {referrer_id} -> {referred_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error activating referral: {e}")
            return False
    
    def process_daily_referral_earnings(self):
        """Process daily earnings for active referrals - FIXED: Only active referrers get paid"""
        if not self.ensure_connection():
            return 0
        
        try:
            today = datetime.now().date().isoformat()
            
            # Get all active referrals
            active_refs = list(self.referrals.find({'is_active': True}))
            
            earnings_count = 0
            for ref in active_refs:
                try:
                    referrer_id = ref['referrer_id']
                    referred_id = ref['referred_id']
                    
                    # Check if referred user searched today
                    today_search = self.daily_searches.find_one({
                        'user_id': referred_id,
                        'date': today
                    })
                    
                    if today_search:
                        referrer = self.get_user(referrer_id)
                        
                        # Don't pay if referrer is blocked
                        if referrer and not referrer.get('withdrawal_blocked') and not referrer.get('suspicious_activity'):
                            tier_rate = self.config.get_tier_rate(referrer.get('tier', 1))
                            
                            # Add daily earning to referrer ONLY
                            self.add_balance(
                                referrer_id,
                                tier_rate,
                                f"Daily earning from user {referred_id} on {today}"
                            )
                            
                            self.referrals.update_one(
                                {'_id': ref['_id']},
                                {
                                    '$inc': {'earnings': tier_rate},
                                    '$set': {'last_earning_date': today}
                                }
                            )
                            
                            earnings_count += 1
                            logger.info(f"Daily earning: {referrer_id} got ₹{tier_rate} from {referred_id}")
                except Exception as e:
                    logger.error(f"Error processing referral {ref.get('_id')}: {e}")
                    continue
            
            self.log_system_event('daily_earnings', f"Processed {earnings_count} earnings")
            return earnings_count
            
        except Exception as e:
            logger.error(f"Error processing daily earnings: {e}")
            return 0
    
    def mark_channel_join(self, user_id, channel_id):
        """Mark user as joined channel - FIXED: Proper verification"""
        try:
            user_id = int(user_id)
            
            # Check if already joined
            existing = self.channel_joins.find_one({
                'user_id': user_id,
                'channel_id': str(channel_id)
            })
            
            if existing:
                logger.info(f"User {user_id} already joined channel {channel_id}")
                return False
            
            self.channel_joins.insert_one({
                'user_id': user_id,
                'channel_id': str(channel_id),
                'joined_at': datetime.now().isoformat()
            })
            
            # Add bonus
            self.add_balance(
                user_id,
                self.config.CHANNEL_JOIN_BONUS,
                "Channel join bonus"
            )
            
            self.users.update_one(
                {'user_id': user_id},
                {'$set': {'channel_joined': True}}
            )
            
            self.user_cache.pop(f"user_{user_id}", None)
            
            logger.info(f"✅ Channel join bonus given to user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error marking channel join: {e}")
            return False
    
    def claim_daily_bonus(self, user_id):
        """Claim daily bonus with streak - FIXED: Works properly"""
        try:
            user_id = int(user_id)
            user = self.get_user(user_id)
            if not user:
                return None
            
            now = datetime.now()
            today = now.date().isoformat()
            
            last_daily = user.get('last_daily')
            
            # Check if already claimed today
            if last_daily and last_daily.startswith(today):
                logger.info(f"User {user_id} already claimed daily today")
                return None
            
            # Calculate streak
            streak = 1
            if last_daily:
                try:
                    last_date = datetime.fromisoformat(last_daily).date()
                    if (now.date() - last_date).days == 1:
                        streak = user.get('daily_streak', 0) + 1
                    else:
                        streak = 1
                except:
                    streak = 1
            
            # Calculate bonus
            base_bonus = self.config.DAILY_BONUS
            streak_bonus = min(streak * 0.02, 0.15)
            total_bonus = base_bonus + streak_bonus
            
            # Add balance
            self.add_balance(user_id, total_bonus, f"Daily bonus (streak: {streak})")
            
            # Update user
            self.users.update_one(
                {'user_id': user_id},
                {
                    '$inc': {'total_earned': total_bonus},
                    '$set': {
                        'daily_streak': streak,
                        'last_daily': now.isoformat()
                    }
                }
            )
            
            self.user_cache.pop(f"user_{user_id}", None)
            
            logger.info(f"✅ Daily bonus claimed: User {user_id} got ₹{total_bonus} (streak: {streak})")
            
            return {'bonus': total_bonus, 'streak': streak, 'success': True}
            
        except Exception as e:
            logger.error(f"Error claiming daily: {e}")
            return None
    
    def add_balance(self, user_id, amount, description=""):
        """Add balance to user"""
        try:
            user_id = int(user_id)
            amount = float(amount)
            
            if amount <= 0:
                return False
            
            self.users.update_one(
                {'user_id': user_id},
                {'$inc': {'balance': amount, 'total_earned': amount}}
            )
            
            self.add_transaction(user_id, 'credit', amount, description)
            self.user_cache.pop(f"user_{user_id}", None)
            
            logger.info(f"Added ₹{amount} to user {user_id}: {description}")
            return True
        except Exception as e:
            logger.error(f"Error adding balance: {e}")
            return False
    
    def process_withdrawal(self, user_id, amount, method, details):
        """Process withdrawal request"""
        try:
            user_id = int(user_id)
            amount = float(amount)
            
            user = self.get_user(user_id)
            
            if not user:
                return {'success': False, 'message': 'User not found'}
            
            # Anti-cheat checks
            if user.get('suspicious_activity'):
                return {'success': False, 'message': 'Account under review for suspicious activity'}
            
            if user.get('withdrawal_blocked'):
                return {'success': False, 'message': 'Withdrawals blocked. Contact support.'}
            
            # Balance check
            if user['balance'] < amount:
                return {'success': False, 'message': f'Insufficient balance. You have ₹{user["balance"]:.2f}'}
            
            # Minimum amount check
            if amount < self.config.MIN_WITHDRAWAL:
                return {'success': False, 'message': f'Minimum withdrawal is ₹{self.config.MIN_WITHDRAWAL}'}
            
            # Check for pending withdrawals
            pending = self.withdrawals.find_one({
                'user_id': user_id,
                'status': 'pending'
            })
            
            if pending:
                return {'success': False, 'message': 'You already have a pending withdrawal request'}
            
            # Deduct balance
            self.users.update_one(
                {'user_id': user_id},
                {'$inc': {'balance': -amount}}
            )
            
            now = datetime.now().isoformat()
            withdrawal = {
                'user_id': user_id,
                'amount': amount,
                'method': method,
                'details': details,
                'status': 'pending',
                'request_date': now,
                'processed_date': None,
                'user_name': user.get('first_name', ''),
                'username': user.get('username', ''),
                'total_searches': user.get('total_searches', 0),
                'active_refs': user.get('active_refs', 0)
            }
            
            result = self.withdrawals.insert_one(withdrawal)
            
            self.add_transaction(
                user_id,
                'withdrawal_request',
                -amount,
                f"Withdrawal request #{str(result.inserted_id)[-6:]}"
            )
            
            self.user_cache.pop(f"user_{user_id}", None)
            self.log_system_event('withdrawal_request', f"User {user_id}: ₹{amount}")
            
            logger.info(f"✅ Withdrawal request created for user {user_id}: ₹{amount}")
            
            return {
                'success': True,
                'message': 'Withdrawal request submitted successfully',
                'id': str(result.inserted_id)
            }
            
        except Exception as e:
            logger.error(f"Error processing withdrawal: {e}")
            return {'success': False, 'message': 'Internal error. Please try again.'}
    
    def get_user_withdrawals(self, user_id, limit=10):
        """Get user's withdrawal history"""
        try:
            user_id = int(user_id)
            withdrawals = self.withdrawals.find(
                {'user_id': user_id}
            ).sort('request_date', -1).limit(limit)
            
            result = []
            for w in withdrawals:
                w['_id'] = str(w['_id'])
                result.append(w)
            
            return result
        except Exception as e:
            logger.error(f"Error getting withdrawals: {e}")
            return []
    
    def add_transaction(self, user_id, type_, amount, description=""):
        """Add transaction record"""
        try:
            user_id = int(user_id)
            transaction = {
                'user_id': user_id,
                'type': type_,
                'amount': float(amount),
                'description': description,
                'timestamp': datetime.now().isoformat(),
                'status': 'completed'
            }
            self.transactions.insert_one(transaction)
            return True
        except Exception as e:
            logger.error(f"Error adding transaction: {e}")
            return False
    
    def update_user_tier(self, user_id):
        """Update user tier based on active referrals"""
        try:
            user_id = int(user_id)
            user = self.get_user(user_id)
            if not user:
                return
            
            active_refs = user.get('active_refs', 0)
            new_tier = self.config.calculate_tier(active_refs)
            
            if new_tier != user.get('tier'):
                self.users.update_one(
                    {'user_id': user_id},
                    {'$set': {'tier': new_tier}}
                )
                
                self.user_cache.pop(f"user_{user_id}", None)
                logger.info(f"User {user_id} upgraded to tier {new_tier}")
                return new_tier
            
            return user.get('tier')
            
        except Exception as e:
            logger.error(f"Error updating tier: {e}")
            return None
    
    def get_leaderboard(self, limit=10):
        """Get leaderboard - FIXED: Shows only active referrers, not searchers"""
        try:
            # Get users with active referrals, sorted by active_refs
            users = self.users.find(
                {
                    'active_refs': {'$gt': 0},
                    'suspicious_activity': False
                },
                {
                    'first_name': 1,
                    'active_refs': 1,
                    'total_earned': 1,
                    'tier': 1
                }
            ).sort('active_refs', -1).limit(limit)
            
            result = []
            for i, user in enumerate(users):
                result.append({
                    'rank': i + 1,
                    'name': user.get('first_name', 'User')[:15],
                    'active_refs': user.get('active_refs', 0),
                    'total_earned': user.get('total_earned', 0),
                    'tier': user.get('tier', 1)
                })
            
            return result
        except Exception as e:
            logger.error(f"Leaderboard error: {e}")
            return []
    
    def get_system_stats(self):
        """Get system statistics"""
        try:
            stats = {
                'total_users': self.users.count_documents({}),
                'active_today': self.users.count_documents({
                    'last_active': {'$gte': (datetime.now() - timedelta(days=1)).isoformat()}
                }),
                'pending_withdrawals': self.withdrawals.count_documents({'status': 'pending'}),
                'total_searches': self.search_logs.count_documents({}),
                'total_earnings': self.transactions.aggregate([
                    {'$match': {'amount': {'$gt': 0}}},
                    {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
                ]).next().get('total', 0) if self.transactions.count_documents({}) > 0 else 0,
                'total_withdrawn': self.transactions.aggregate([
                    {'$match': {'type': 'withdrawal_request'}},
                    {'$group': {'_id': None, 'total': {'$sum': {'$abs': '$amount'}}}}
                ]).next().get('total', 0) if self.transactions.count_documents({'type': 'withdrawal_request'}) > 0 else 0
            }
            return stats
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {}
    
    def log_system_event(self, event_type, description):
        """Log system events"""
        try:
            self.system_stats.insert_one({
                'event_type': event_type,
                'description': description,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error logging system event: {e}")
    
    def cleanup(self):
        """Cleanup database connections"""
        try:
            if hasattr(self, 'client') and self.client:
                self.client.close()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database: {e}")
