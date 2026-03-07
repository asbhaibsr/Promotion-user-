# ===== database.py (FINAL - WITH LIVE ACTIVITY + ALL FEATURES) =====

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
            
            # ===== INITIALIZE COLLECTIONS =====
            self.users = self.db['users']
            self.transactions = self.db['transactions']
            self.withdrawals = self.db['withdrawals']
            self.referrals = self.db['referrals']
            self.daily_searches = self.db['daily_searches']
            self.search_logs = self.db['search_logs']
            self.channel_joins = self.db['channel_joins']
            self.daily_bonus = self.db['daily_bonus']
            self.missions = self.db['missions']
            self.daily_claims = self.db['daily_claims']
            self.ads = self.db['ads']
            self.system_stats = self.db['system_stats']
            self.issues = self.db['issues']  # For support messages
            self.live_activity = self.db['live_activity']  # For live activity feed
            
            # Create indexes
            self._create_indexes()
            
            # Initialize default ads
            self._init_default_ads()
            
            self.connected = True
            logger.info("✅ MongoDB Connected Successfully!")
            
        except ConnectionFailure as e:
            logger.error(f"MongoDB Connection Error: {e}")
            self.connected = False
            raise e
    
    def _create_indexes(self):
        """Create all necessary indexes"""
        try:
            # Users collection
            self.users.create_index('user_id', unique=True)
            self.users.create_index('referrer_id')
            self.users.create_index('last_active')
            self.users.create_index('balance')
            
            # Referrals collection
            self.referrals.create_index([('referrer_id', ASCENDING), ('referred_id', ASCENDING)], unique=True)
            self.referrals.create_index('is_active')
            
            # Daily searches
            self.daily_searches.create_index([('user_id', ASCENDING), ('date', ASCENDING)], unique=True)
            
            # Search logs (auto-delete after 30 days)
            self.search_logs.create_index([('user_id', ASCENDING), ('timestamp', DESCENDING)])
            self.search_logs.create_index('timestamp', expireAfterSeconds=2592000)
            
            # Withdrawals
            self.withdrawals.create_index([('user_id', ASCENDING), ('request_date', DESCENDING)])
            self.withdrawals.create_index('status')
            
            # Channel joins
            self.channel_joins.create_index([('user_id', ASCENDING), ('channel_id', ASCENDING)], unique=True)
            
            # Daily bonus (calendar)
            self.daily_bonus.create_index([('user_id', ASCENDING), ('date', ASCENDING)], unique=True)
            self.daily_bonus.create_index('date')
            
            # Missions
            self.missions.create_index([('user_id', ASCENDING), ('date', ASCENDING)], unique=True)
            
            # Daily claims (ads)
            self.daily_claims.create_index([('user_id', ASCENDING), ('ad_id', ASCENDING), ('date', ASCENDING)], unique=True)
            self.daily_claims.create_index('date')
            
            # Ads
            self.ads.create_index('id', unique=True)
            
            # Live activity (auto-delete after 7 days)
            self.live_activity.create_index('timestamp', expireAfterSeconds=604800)
            
            # Issues
            self.issues.create_index([('user_id', ASCENDING), ('timestamp', DESCENDING)])
            self.issues.create_index('status')
            
            logger.info("✅ Database indexes created")
        except Exception as e:
            logger.error(f"Index creation error: {e}")
    
    def _init_default_ads(self):
        """Initialize default ads if not exists"""
        try:
            if self.ads.count_documents({}) == 0:
                self.ads.insert_many([
                    {'id': 1, 'title': 'Install App & Earn', 'reward': 2.0, 'link': 'https://t.me/+8SdeM5gBihoxZjU1', 'meta': '⏱️ 2 min • 1.2k completed', 'icon': '📱', 'order': 1},
                    {'id': 2, 'title': 'Watch Video', 'reward': 0.5, 'link': 'https://t.me/+8SdeM5gBihoxZjU1', 'meta': '⏱️ 30 sec • 3.4k completed', 'icon': '🎬', 'order': 2},
                    {'id': 3, 'title': 'Join Channel', 'reward': 1.0, 'link': 'https://t.me/+8SdeM5gBihoxZjU1', 'meta': '⏱️ 1 min • 5.6k completed', 'icon': '📢', 'order': 3}
                ])
                logger.info("✅ Default ads initialized")
        except Exception as e:
            logger.error(f"Error initializing ads: {e}")
    
    def ensure_connection(self):
        """Ensure database connection is alive"""
        if not self.connected:
            try:
                self.client.admin.command('ping')
                self.connected = True
            except:
                self.connected = False
        return self.connected
    
    # ========== LIVE ACTIVITY ==========
    
    def add_live_activity(self, activity_type, user_id, amount=0, description=""):
        """Add entry to live activity feed"""
        try:
            user = self.get_user(user_id)
            if not user:
                return
            
            activity = {
                'type': activity_type,  # 'join', 'withdraw', 'bonus', 'mission', 'referral', 'support'
                'user_id': user_id,
                'user_name': user.get('first_name', 'User'),
                'amount': amount,
                'description': description,
                'timestamp': datetime.now().isoformat(),
                'avatar': user.get('first_name', 'U')[0].upper() if user.get('first_name') else '👤'
            }
            
            self.live_activity.insert_one(activity)
            logger.info(f"📊 Live activity added: {activity_type} for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error adding live activity: {e}")
    
    def get_live_activity(self, limit=20):
        """Get recent live activity"""
        try:
            activities = list(self.live_activity.find().sort('timestamp', -1).limit(limit))
            
            result = []
            for act in activities:
                act['_id'] = str(act['_id'])
                
                # Format time
                time_str = act.get('timestamp', '')
                try:
                    timestamp = datetime.fromisoformat(time_str)
                    now = datetime.now()
                    diff = now - timestamp
                    
                    if diff.days > 0:
                        time_ago = f"{diff.days}d ago"
                    elif diff.seconds // 3600 > 0:
                        time_ago = f"{diff.seconds // 3600}h ago"
                    elif diff.seconds // 60 > 0:
                        time_ago = f"{diff.seconds // 60}min ago"
                    else:
                        time_ago = "just now"
                except:
                    time_ago = "recently"
                
                # Get appropriate emoji
                emoji = '👤'
                if act['type'] == 'join': emoji = '🎉'
                elif act['type'] == 'withdraw': emoji = '💰'
                elif act['type'] == 'bonus': emoji = '🎁'
                elif act['type'] == 'mission': emoji = '🏆'
                elif act['type'] == 'referral': emoji = '👥'
                elif act['type'] == 'support': emoji = '📩'
                
                # Get display text
                display_text = act.get('description', '')
                if not display_text:
                    if act['type'] == 'join':
                        display_text = f"{act['user_name']} joined the bot"
                    elif act['type'] == 'withdraw':
                        display_text = f"{act['user_name']} withdrew ₹{act['amount']}"
                    elif act['type'] == 'bonus':
                        display_text = f"{act['user_name']} claimed ₹{act['amount']} bonus"
                    elif act['type'] == 'mission':
                        display_text = f"{act['user_name']} completed missions"
                    elif act['type'] == 'referral':
                        display_text = f"{act['user_name']} got a new referral"
                    else:
                        display_text = f"{act['user_name']} was active"
                
                result.append({
                    'type': act.get('type', 'activity'),
                    'user_name': act.get('user_name', 'User'),
                    'amount': act.get('amount', 0),
                    'time': time_ago,
                    'avatar': emoji,
                    'description': display_text
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting live activity: {e}")
            return []
    
    # ========== SUPPORT MESSAGES ==========
    
    def add_support_message(self, user_id, message):
        """Add support message from user"""
        try:
            user = self.get_user(user_id)
            
            support_msg = {
                'user_id': int(user_id),
                'user_name': user.get('first_name', 'User') if user else 'User',
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'status': 'pending',
                'read': False,
                'admin_reply': None,
                'reply_date': None
            }
            
            result = self.issues.insert_one(support_msg)
            
            # Add to live activity
            self.add_live_activity('support', user_id, 0, f"Sent support message")
            
            logger.info(f"📩 Support message from user {user_id}")
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error adding support message: {e}")
            return None
    
    def get_pending_support_messages(self, limit=20):
        """Get pending support messages for admin"""
        try:
            messages = list(self.issues.find(
                {'status': 'pending'}
            ).sort('timestamp', -1).limit(limit))
            
            for msg in messages:
                msg['_id'] = str(msg['_id'])
            
            return messages
        except Exception as e:
            logger.error(f"Error getting support messages: {e}")
            return []
    
    def mark_support_replied(self, message_id, admin_id, reply_text):
        """Mark support message as replied"""
        try:
            from bson.objectid import ObjectId
            
            self.issues.update_one(
                {'_id': ObjectId(message_id)},
                {'$set': {
                    'status': 'replied',
                    'admin_id': int(admin_id),
                    'admin_reply': reply_text,
                    'reply_date': datetime.now().isoformat(),
                    'read': True
                }}
            )
            
            logger.info(f"✅ Support message {message_id} replied by admin {admin_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error marking support replied: {e}")
            return False
    
    # ========== USER MANAGEMENT ==========
    
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
                if '_id' in user:
                    user['_id'] = str(user['_id'])
                
                self.user_cache[cache_key] = user
                
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
                'join_date': now,
                'last_active': now,
                'is_admin': user_id in self.config.ADMIN_IDS,
                'suspicious_activity': False,
                'withdrawal_blocked': False,
                'notify_referrals': True,
                'notify_earnings': True,
                'notify_withdrawals': True,
                'dark_mode': False,
                'sound_enabled': True
            }
            
            self.users.insert_one(new_user)
            
            if referrer_id and referrer_id != user_id:
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
            
            self.user_cache.pop(f"user_{user_id}", None)
            if referrer_id:
                self.user_cache.pop(f"user_{referrer_id}", None)
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return False
    
    # ========== SEARCH RECORDING ==========
    
    def record_search(self, user_id):
        """Record user search"""
        if not self.ensure_connection():
            return {'success': False, 'message': 'Database error'}
        
        try:
            user_id = int(user_id)
            now = datetime.now()
            today = now.date().isoformat()
            
            user = self.get_user(user_id)
            if not user:
                return {'success': False, 'message': 'User not found'}
            
            if user.get('suspicious_activity') or user.get('withdrawal_blocked'):
                logger.warning(f"User {user_id} blocked from searches")
                return {'success': False, 'message': 'Account blocked'}
            
            daily_count = self.daily_searches.count_documents({
                'user_id': user_id,
                'date': today
            })
            
            if daily_count >= self.config.MAX_SEARCHES_PER_DAY:
                logger.warning(f"User {user_id} exceeded daily search limit")
                return {'success': False, 'message': 'Daily limit reached'}
            
            last_search = self.search_logs.find_one(
                {'user_id': user_id},
                sort=[('timestamp', DESCENDING)]
            )
            
            if last_search:
                last_time = datetime.fromisoformat(last_search['timestamp'])
                if (now - last_time).total_seconds() < self.config.MIN_TIME_BETWEEN_SEARCHES:
                    logger.warning(f"User {user_id} searching too fast")
                    return {'success': False, 'message': 'Please wait before searching again'}
            
            self.search_logs.insert_one({
                'user_id': user_id,
                'timestamp': now.isoformat(),
                'date': today
            })
            
            self.daily_searches.update_one(
                {'user_id': user_id, 'date': today},
                {'$inc': {'count': 1}},
                upsert=True
            )
            
            was_first_search = (user.get('total_searches', 0) == 0)
            
            self.users.update_one(
                {'user_id': user_id},
                {
                    '$inc': {'total_searches': 1},
                    '$set': {'last_active': now.isoformat()}
                }
            )
            
            if was_first_search:
                self.activate_referral(user_id)
            
            self.user_cache.pop(f"user_{user_id}", None)
            
            logger.info(f"✅ Search recorded for user {user_id}")
            
            return {
                'success': True,
                'message': 'Search recorded!'
            }
            
        except Exception as e:
            logger.error(f"Error recording search: {e}")
            return {'success': False, 'message': str(e)}
    
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
                
                self.add_balance(
                    referrer_id,
                    self.config.REFERRAL_BONUS,
                    f"Referral bonus for user {referred_id}"
                )
                
                self.update_user_tier(referrer_id)
                
                self.user_cache.pop(f"user_{referrer_id}", None)
                
                # Add live activity
                referrer = self.get_user(referrer_id)
                if referrer:
                    self.add_live_activity(
                        'referral',
                        referrer_id,
                        self.config.REFERRAL_BONUS,
                        f"Referral activated! Earned ₹{self.config.REFERRAL_BONUS}"
                    )
                
                logger.info(f"✅ Referral activated: {referrer_id} -> {referred_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error activating referral: {e}")
            return False
    
    # ========== DAILY REFERRAL EARNINGS ==========
    
    def process_daily_referral_earnings(self):
        """Process daily earnings for active referrals"""
        if not self.ensure_connection():
            return 0
        
        try:
            today = datetime.now().date().isoformat()
            
            active_refs = list(self.referrals.find({'is_active': True}))
            
            earnings_count = 0
            for ref in active_refs:
                try:
                    referrer_id = ref['referrer_id']
                    referred_id = ref['referred_id']
                    
                    today_search = self.daily_searches.find_one({
                        'user_id': referred_id,
                        'date': today
                    })
                    
                    if today_search:
                        referrer = self.get_user(referrer_id)
                        
                        if referrer and not referrer.get('withdrawal_blocked') and not referrer.get('suspicious_activity'):
                            tier_rate = self.config.get_tier_rate(referrer.get('tier', 1))
                            
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
    
    # ========== CHANNEL JOIN ==========
    
    def mark_channel_join(self, user_id, channel_id):
        """Mark user as joined channel"""
        try:
            user_id = int(user_id)
            
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
            
            # Add live activity
            self.add_live_activity(
                'bonus',
                user_id,
                self.config.CHANNEL_JOIN_BONUS,
                f"Joined channel and got ₹{self.config.CHANNEL_JOIN_BONUS}"
            )
            
            logger.info(f"✅ Channel join bonus given to user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error marking channel join: {e}")
            return False
    
    # ========== DAILY BONUS (CALENDAR) ==========
    
    def claim_day_bonus(self, user_id, date_str):
        """Claim bonus for specific day (calendar)"""
        try:
            user_id = int(user_id)
            user = self.get_user(user_id)
            if not user:
                return None
            
            # Check if already claimed
            existing = self.daily_bonus.find_one({
                'user_id': user_id,
                'date': date_str
            })
            
            if existing:
                logger.info(f"User {user_id} already claimed bonus for {date_str}")
                return None
            
            # Calculate bonus (increases with streak)
            streak = user.get('daily_streak', 0)
            base_bonus = self.config.DAILY_BONUS
            streak_bonus = min(streak * 0.02, 0.15)
            total_bonus = base_bonus + streak_bonus
            
            # Add balance
            self.add_balance(user_id, total_bonus, f"Daily bonus for {date_str}")
            
            # Record claim
            self.daily_bonus.insert_one({
                'user_id': user_id,
                'date': date_str,
                'bonus': total_bonus,
                'timestamp': datetime.now().isoformat()
            })
            
            # Update streak
            new_streak = streak + 1
            self.users.update_one(
                {'user_id': user_id},
                {
                    '$set': {
                        'daily_streak': new_streak,
                        'last_daily': date_str
                    }
                }
            )
            
            # Add live activity
            self.add_live_activity(
                'bonus',
                user_id,
                total_bonus,
                f"Claimed daily bonus (streak: {new_streak})"
            )
            
            # Reset after 30 days (archive old claims)
            claimed_count = self.daily_bonus.count_documents({'user_id': user_id})
            if claimed_count >= 30:
                # Keep only last 30 days
                oldest_date = (datetime.now() - timedelta(days=30)).date().isoformat()
                self.daily_bonus.delete_many({
                    'user_id': user_id,
                    'date': {'$lt': oldest_date}
                })
            
            self.user_cache.pop(f"user_{user_id}", None)
            
            logger.info(f"✅ Day bonus claimed: User {user_id} for {date_str} - ₹{total_bonus}")
            
            return {
                'bonus': total_bonus,
                'streak': new_streak,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Error claiming day bonus: {e}")
            return None
    
    def get_user_bonus_days(self, user_id):
        """Get all claimed bonus days for user"""
        try:
            user_id = int(user_id)
            claims = list(self.daily_bonus.find(
                {'user_id': user_id},
                {'date': 1, '_id': 0}
            ).sort('date', 1))
            
            return [c['date'] for c in claims]
        except Exception as e:
            logger.error(f"Error getting bonus days: {e}")
            return []
    
    # ========== MISSIONS ==========
    
    def get_user_missions(self, user_id):
        """Get user's missions for today"""
        try:
            user_id = int(user_id)
            today = datetime.now().date().isoformat()
            
            mission_data = self.missions.find_one({
                'user_id': user_id,
                'date': today
            })
            
            if not mission_data:
                # Get user data
                user = self.get_user(user_id)
                
                # Initialize missions for today
                mission_data = {
                    'user_id': user_id,
                    'date': today,
                    'mission1': {
                        'progress': user.get('active_refs', 0) if user else 0,
                        'completed': (user.get('active_refs', 0) >= 10) if user else False,
                        'total': 10
                    },
                    'mission2': {
                        'progress': 0,
                        'completed': False,
                        'total': 5
                    },
                    'reward_claimed': False
                }
                
                # Check how many bonus days claimed in last 5 days
                if user and user.get('daily_streak', 0) > 0:
                    # Get recent bonus claims
                    recent_bonus = list(self.daily_bonus.find(
                        {'user_id': user_id}
                    ).sort('date', -1).limit(5))
                    
                    mission_data['mission2']['progress'] = len(recent_bonus)
                    mission_data['mission2']['completed'] = len(recent_bonus) >= 5
                
                self.missions.insert_one(mission_data)
            
            return mission_data
            
        except Exception as e:
            logger.error(f"Error getting missions: {e}")
            return None
    
    def update_mission_progress(self, user_id, mission_type, count=1):
        """Update mission progress"""
        try:
            user_id = int(user_id)
            today = datetime.now().date().isoformat()
            
            # Get or create missions
            mission_data = self.get_user_missions(user_id)
            if not mission_data:
                return None
            
            if mission_data.get('reward_claimed'):
                return mission_data  # Don't update if reward already claimed
            
            if mission_type == 'referral' or mission_type == 'ad':
                # Mission 1: referrals/ads
                mission1 = mission_data.get('mission1', {'progress': 0, 'completed': False, 'total': 10})
                mission1['progress'] = min(mission1['progress'] + count, mission1['total'])
                mission1['completed'] = mission1['progress'] >= mission1['total']
                mission_data['mission1'] = mission1
                
            elif mission_type == 'bonus':
                # Mission 2: bonus days
                mission2 = mission_data.get('mission2', {'progress': 0, 'completed': False, 'total': 5})
                mission2['progress'] = min(mission2['progress'] + count, mission2['total'])
                mission2['completed'] = mission2['progress'] >= mission2['total']
                mission_data['mission2'] = mission2
            
            # Save
            self.missions.update_one(
                {'user_id': user_id, 'date': today},
                {'$set': mission_data},
                upsert=True
            )
            
            # Check if both completed now
            if mission_data['mission1']['completed'] and mission_data['mission2']['completed'] and not mission_data.get('reward_claimed'):
                self.add_live_activity(
                    'mission',
                    user_id,
                    5,
                    "Completed both daily missions!"
                )
            
            return mission_data
            
        except Exception as e:
            logger.error(f"Error updating mission: {e}")
            return None
    
    def claim_mission_reward(self, user_id):
        """Claim daily mission reward"""
        try:
            user_id = int(user_id)
            today = datetime.now().date().isoformat()
            
            mission_data = self.missions.find_one({
                'user_id': user_id,
                'date': today
            })
            
            if not mission_data:
                return {'success': False, 'message': 'No missions found'}
            
            if mission_data.get('reward_claimed'):
                return {'success': False, 'message': 'Reward already claimed'}
            
            mission1 = mission_data.get('mission1', {})
            mission2 = mission_data.get('mission2', {})
            
            if not mission1.get('completed') or not mission2.get('completed'):
                return {'success': False, 'message': 'Complete both missions first'}
            
            # Add ₹5 reward
            self.add_balance(user_id, 5.0, "Daily mission reward")
            
            # Mark as claimed
            self.missions.update_one(
                {'user_id': user_id, 'date': today},
                {'$set': {'reward_claimed': True}}
            )
            
            # Add live activity
            self.add_live_activity(
                'mission',
                user_id,
                5,
                "Claimed ₹5 mission reward!"
            )
            
            logger.info(f"✅ Mission reward claimed: User {user_id} got ₹5")
            
            return {'success': True, 'message': 'Reward claimed'}
            
        except Exception as e:
            logger.error(f"Error claiming mission reward: {e}")
            return {'success': False, 'message': str(e)}
    
    # ========== ADS MANAGEMENT ==========
    
    def get_all_ads(self):
        """Get all ads"""
        try:
            ads = list(self.ads.find().sort('order', 1))
            for ad in ads:
                ad['_id'] = str(ad['_id'])
            return ads
        except Exception as e:
            logger.error(f"Error getting ads: {e}")
            return []
    
    def update_ad(self, ad_id, title, reward, link, meta, icon=None):
        """Update an ad"""
        try:
            update_data = {
                'title': title,
                'reward': float(reward),
                'link': link,
                'meta': meta
            }
            if icon:
                update_data['icon'] = icon
            
            self.ads.update_one(
                {'id': int(ad_id)},
                {'$set': update_data},
                upsert=True
            )
            
            logger.info(f"✅ Ad {ad_id} updated")
            return True
        except Exception as e:
            logger.error(f"Error updating ad: {e}")
            return False
    
    def get_user_claimed_ads(self, user_id, date=None):
        """Get ads claimed by user on specific date"""
        try:
            user_id = int(user_id)
            if not date:
                date = datetime.now().date().isoformat()
            
            claims = list(self.daily_claims.find(
                {'user_id': user_id, 'date': date},
                {'ad_id': 1, '_id': 0}
            ))
            
            return [c['ad_id'] for c in claims]
        except Exception as e:
            logger.error(f"Error getting claimed ads: {e}")
            return []
    
    def claim_ad(self, user_id, ad_id, reward):
        """Record ad claim"""
        try:
            user_id = int(user_id)
            today = datetime.now().date().isoformat()
            
            # Check if already claimed today
            existing = self.daily_claims.find_one({
                'user_id': user_id,
                'ad_id': ad_id,
                'date': today
            })
            
            if existing:
                return False
            
            # Add balance
            self.add_balance(user_id, float(reward), f"Ad reward #{ad_id}")
            
            # Record claim
            self.daily_claims.insert_one({
                'user_id': user_id,
                'ad_id': ad_id,
                'date': today,
                'reward': float(reward),
                'timestamp': datetime.now().isoformat()
            })
            
            # Add live activity
            self.add_live_activity(
                'bonus',
                user_id,
                reward,
                f"Claimed ad reward ₹{reward}"
            )
            
            logger.info(f"✅ Ad {ad_id} claimed by user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error claiming ad: {e}")
            return False
    
    def reset_ad_claims(self, ad_id):
        """Reset all claims for an ad (when admin edits)"""
        try:
            self.daily_claims.delete_many({'ad_id': ad_id})
            logger.info(f"✅ Ad {ad_id} claims reset")
            return True
        except Exception as e:
            logger.error(f"Error resetting ad claims: {e}")
            return False
    
    # ========== BALANCE MANAGEMENT ==========
    
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
    
    # ========== WITHDRAWAL ==========
    
    def process_withdrawal(self, user_id, amount, method, details):
        """Process withdrawal request"""
        try:
            user_id = int(user_id)
            amount = float(amount)
            
            user = self.get_user(user_id)
            
            if not user:
                return {'success': False, 'message': 'User not found'}
            
            if user.get('suspicious_activity'):
                return {'success': False, 'message': 'Account under review for suspicious activity'}
            
            if user.get('withdrawal_blocked'):
                return {'success': False, 'message': 'Withdrawals blocked. Contact support.'}
            
            if user['balance'] < amount:
                return {'success': False, 'message': f'Insufficient balance. You have ₹{user["balance"]:.2f}'}
            
            if amount < self.config.MIN_WITHDRAWAL:
                return {'success': False, 'message': f'Minimum withdrawal is ₹{self.config.MIN_WITHDRAWAL}'}
            
            pending = self.withdrawals.find_one({
                'user_id': user_id,
                'status': 'pending'
            })
            
            if pending:
                return {'success': False, 'message': 'You already have a pending withdrawal request'}
            
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
            
            # Add live activity
            self.add_live_activity(
                'withdraw_request',
                user_id,
                amount,
                f"Requested withdrawal of ₹{amount}"
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
    
    def get_pending_withdrawals(self, limit=10):
        """Get pending withdrawals for admin"""
        try:
            withdrawals = self.withdrawals.find(
                {'status': 'pending'}
            ).sort('request_date', 1).limit(limit)
            
            result = []
            for w in withdrawals:
                w['_id'] = str(w['_id'])
                result.append(w)
            
            return result
        except Exception as e:
            logger.error(f"Error getting pending withdrawals: {e}")
            return []
    
    def approve_withdrawal(self, withdrawal_id, admin_id):
        """Approve a withdrawal"""
        try:
            from bson.objectid import ObjectId
            
            withdrawal = self.withdrawals.find_one({'_id': ObjectId(withdrawal_id)})
            if not withdrawal:
                return False
            
            self.withdrawals.update_one(
                {'_id': ObjectId(withdrawal_id)},
                {
                    '$set': {
                        'status': 'completed',
                        'processed_date': datetime.now().isoformat(),
                        'admin_id': int(admin_id)
                    }
                }
            )
            
            self.add_transaction(
                withdrawal['user_id'],
                'withdrawal_approved',
                -withdrawal['amount'],
                f"Withdrawal approved #{withdrawal_id[-8:]}"
            )
            
            # Add live activity
            self.add_live_activity(
                'withdraw',
                withdrawal['user_id'],
                withdrawal['amount'],
                f"Withdrawal approved for ₹{withdrawal['amount']}"
            )
            
            logger.info(f"✅ Withdrawal {withdrawal_id} approved")
            return True
            
        except Exception as e:
            logger.error(f"Error approving withdrawal: {e}")
            return False
    
    def reject_withdrawal(self, withdrawal_id, admin_id):
        """Reject a withdrawal and refund"""
        try:
            from bson.objectid import ObjectId
            
            withdrawal = self.withdrawals.find_one({'_id': ObjectId(withdrawal_id)})
            if not withdrawal:
                return False
            
            self.withdrawals.update_one(
                {'_id': ObjectId(withdrawal_id)},
                {
                    '$set': {
                        'status': 'rejected',
                        'processed_date': datetime.now().isoformat(),
                        'admin_id': int(admin_id)
                    }
                }
            )
            
            # Refund amount
            self.add_balance(
                withdrawal['user_id'],
                withdrawal['amount'],
                f"Refund for rejected withdrawal"
            )
            
            logger.info(f"❌ Withdrawal {withdrawal_id} rejected")
            return True
            
        except Exception as e:
            logger.error(f"Error rejecting withdrawal: {e}")
            return False
    
    # ========== TRANSACTIONS ==========
    
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
    
    # ========== TIER MANAGEMENT ==========
    
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
    
    # ========== NOTIFICATION SETTINGS ==========
    
    def update_notification_setting(self, user_id, setting, value):
        """Update user notification settings"""
        try:
            user_id = int(user_id)
            self.users.update_one(
                {'user_id': user_id},
                {'$set': {f'notify_{setting}': value}}
            )
            self.user_cache.pop(f"user_{user_id}", None)
            return True
        except Exception as e:
            logger.error(f"Error updating notification setting: {e}")
            return False
    
    # ========== LEADERBOARD ==========
    
    def get_leaderboard(self, limit=10):
        """Get leaderboard"""
        try:
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
    
    # ========== BLOCKED USERS CLEANUP (FOR BROADCAST) ==========
    
    def remove_blocked_users(self, user_ids):
        """Remove multiple users from database (for broadcast cleanup)"""
        try:
            deleted_count = 0
            for user_id in user_ids:
                user_id = int(user_id)
                
                # Delete user data
                self.users.delete_one({'user_id': user_id})
                self.transactions.delete_many({'user_id': user_id})
                self.withdrawals.delete_many({'user_id': user_id})
                self.referrals.delete_many({
                    '$or': [
                        {'referrer_id': user_id},
                        {'referred_id': user_id}
                    ]
                })
                self.daily_searches.delete_many({'user_id': user_id})
                self.search_logs.delete_many({'user_id': user_id})
                self.daily_bonus.delete_many({'user_id': user_id})
                self.missions.delete_many({'user_id': user_id})
                self.daily_claims.delete_many({'user_id': user_id})
                
                self.user_cache.pop(f"user_{user_id}", None)
                deleted_count += 1
            
            logger.info(f"🧹 Removed {deleted_count} blocked users")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error removing blocked users: {e}")
            return 0
    
    # ========== SYSTEM STATS ==========
    
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
    
    def get_system_stats(self):
        """Get basic system statistics"""
        try:
            stats = {
                'total_users': self.users.count_documents({}),
                'pending_withdrawals': self.withdrawals.count_documents({'status': 'pending'}),
                'total_searches': self.search_logs.count_documents({}),
                'pending_support': self.issues.count_documents({'status': 'pending'})
            }
            return stats
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {}
    
    # ========== CLEANUP ==========
    
    def cleanup(self):
        """Cleanup database connections"""
        try:
            if hasattr(self, 'client') and self.client:
                self.client.close()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database: {e}")
