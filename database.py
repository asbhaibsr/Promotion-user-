# ===== database.py (COMPLETE UPDATED VERSION) =====

import logging
import random
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
            self.issues = self.db['issues']
            self.live_activity = self.db['live_activity']
            self.game_states = self.db['game_states']

            self._create_indexes()
            self._init_default_ads()

            self.connected = True
            logger.info("MongoDB Connected Successfully!")

        except ConnectionFailure as e:
            logger.error(f"MongoDB Connection Error: {e}")
            self.connected = False
            raise e

    def _create_indexes(self):
        try:
            self.users.create_index('user_id', unique=True)
            self.users.create_index('referrer_id')
            self.users.create_index('last_active')
            self.users.create_index('balance')
            self.referrals.create_index([('referrer_id', ASCENDING), ('referred_id', ASCENDING)], unique=True)
            self.referrals.create_index('is_active')
            self.daily_searches.create_index([('user_id', ASCENDING), ('date', ASCENDING)], unique=True)
            self.search_logs.create_index([('user_id', ASCENDING), ('timestamp', DESCENDING)])
            self.search_logs.create_index('timestamp', expireAfterSeconds=2592000)
            self.withdrawals.create_index([('user_id', ASCENDING), ('request_date', DESCENDING)])
            self.withdrawals.create_index('status')
            self.channel_joins.create_index([('user_id', ASCENDING), ('channel_id', ASCENDING)], unique=True)
            self.daily_bonus.create_index([('user_id', ASCENDING), ('date', ASCENDING)], unique=True)
            self.daily_bonus.create_index('date')
            self.missions.create_index([('user_id', ASCENDING), ('date', ASCENDING)], unique=True)
            self.daily_claims.create_index([('user_id', ASCENDING), ('ad_id', ASCENDING), ('date', ASCENDING)], unique=True)
            self.daily_claims.create_index('date')
            self.ads.create_index('id', unique=True)
            self.live_activity.create_index('timestamp', expireAfterSeconds=604800)
            self.live_activity.create_index('user_id')
            self.issues.create_index([('user_id', ASCENDING), ('timestamp', DESCENDING)])
            self.issues.create_index('status')
            self.game_states.create_index([('user_id', ASCENDING), ('date', ASCENDING)], unique=True)
            logger.info("Database indexes created")
        except Exception as e:
            logger.error(f"Index creation error: {e}")

    def _init_default_ads(self):
        try:
            if self.ads.count_documents({}) == 0:
                self.ads.insert_many([
                    {'id': 1, 'title': 'Install App & Earn', 'reward': 2.0, 'link': 'https://t.me/+8SdeM5gBihoxZjU1', 'meta': '⏱️ 2 min • 1.2k completed', 'icon': '📱', 'order': 1},
                    {'id': 2, 'title': 'Watch Video', 'reward': 0.5, 'link': 'https://t.me/+8SdeM5gBihoxZjU1', 'meta': '⏱️ 30 sec • 3.4k completed', 'icon': '🎬', 'order': 2},
                    {'id': 3, 'title': 'Join Channel', 'reward': 1.0, 'link': 'https://t.me/+8SdeM5gBihoxZjU1', 'meta': '⏱️ 1 min • 5.6k completed', 'icon': '📢', 'order': 3}
                ])
                logger.info("Default ads initialized")
        except Exception as e:
            logger.error(f"Error initializing ads: {e}")

    def ensure_connection(self):
        if not self.connected:
            try:
                self.client.admin.command('ping')
                self.connected = True
            except:
                self.connected = False
        return self.connected

    # ========== LIVE ACTIVITY ==========

    def add_live_activity(self, activity_type, user_id, amount=0, description=""):
        try:
            user = self.get_user(user_id)
            if not user:
                return
            activity = {
                'type': activity_type,
                'user_id': user_id,
                'user_name': user.get('first_name', 'User'),
                'amount': amount,
                'description': description,
                'timestamp': datetime.now().isoformat(),
                'avatar': user.get('first_name', 'U')[0].upper()
            }
            self.live_activity.insert_one(activity)
        except Exception as e:
            logger.error(f"Error adding live activity: {e}")

    def get_live_activity(self, limit=20):
        try:
            activities = list(self.live_activity.find().sort('timestamp', -1).limit(limit))
            result = []
            for act in activities:
                act['_id'] = str(act['_id'])
                time_str = act.get('timestamp', '')
                try:
                    timestamp = datetime.fromisoformat(time_str)
                    diff = datetime.now() - timestamp
                    if diff.days > 0: time_ago = f"{diff.days}d ago"
                    elif diff.seconds // 3600 > 0: time_ago = f"{diff.seconds // 3600}h ago"
                    elif diff.seconds // 60 > 0: time_ago = f"{diff.seconds // 60}min ago"
                    else: time_ago = "just now"
                except:
                    time_ago = "recently"

                emoji = '👤'
                if act['type'] == 'join': emoji = '🎉'
                elif act['type'] == 'withdraw': emoji = '💰'
                elif act['type'] == 'bonus': emoji = '🎁'
                elif act['type'] == 'mission': emoji = '🏆'
                elif act['type'] == 'referral': emoji = '👥'
                elif act['type'] == 'game': emoji = '🎮'

                display_text = act.get('description', '')
                if not display_text:
                    if act['type'] == 'join': display_text = "joined the bot"
                    elif act['type'] == 'withdraw': display_text = f"withdrew ₹{act['amount']}"
                    elif act['type'] == 'bonus': display_text = f"claimed ₹{act['amount']} bonus"
                    elif act['type'] == 'mission': display_text = "completed missions"
                    elif act['type'] == 'referral': display_text = "got a new referral"
                    elif act['type'] == 'game': display_text = f"won ₹{act['amount']} in game"
                    else: display_text = "was active"

                result.append({
                    'type': act.get('type', 'activity'),
                    'user_name': act.get('user_name', 'User'),
                    'user_id': act.get('user_id', 0),
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
            self.add_live_activity('support', user_id, 0, "sent support message")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error adding support message: {e}")
            return None

    def get_pending_support_messages(self, limit=20):
        try:
            messages = list(self.issues.find({'status': 'pending'}).sort('timestamp', -1).limit(limit))
            for msg in messages:
                msg['_id'] = str(msg['_id'])
            return messages
        except Exception as e:
            logger.error(f"Error getting support messages: {e}")
            return []

    def mark_support_replied(self, message_id, admin_id, reply_text):
        try:
            from bson.objectid import ObjectId
            self.issues.update_one(
                {'_id': ObjectId(message_id)},
                {'$set': {'status': 'replied', 'admin_id': int(admin_id), 'admin_reply': reply_text, 'reply_date': datetime.now().isoformat(), 'read': True}}
            )
            return True
        except Exception as e:
            logger.error(f"Error marking support replied: {e}")
            return False

    # ========== USER MANAGEMENT ==========

    def get_user(self, user_id):
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
                self.users.update_one({'user_id': int(user_id)}, {'$set': {'last_active': datetime.now().isoformat()}})
            return user
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None

    def add_user(self, user_data):
        if not self.ensure_connection():
            return False
        try:
            user_id = int(user_data['user_id'])
            referrer_id = user_data.get('referrer_id')
            if referrer_id:
                referrer_id = int(referrer_id)

            existing = self.users.find_one({'user_id': user_id})
            if existing:
                self.users.update_one({'user_id': user_id}, {'$set': {'first_name': user_data.get('first_name', ''), 'username': user_data.get('username', ''), 'last_active': datetime.now().isoformat()}})
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
                'dark_mode': True,
                'sound_enabled': True,
                'games_won': 0,
                'total_game_earned': 0.0,
                'passes': 5  # New users get 5 passes to start
            }

            self.users.insert_one(new_user)

            if referrer_id and referrer_id != user_id:
                existing_ref = self.referrals.find_one({'referrer_id': referrer_id, 'referred_id': user_id})
                if not existing_ref:
                    self.referrals.insert_one({
                        'referrer_id': referrer_id,
                        'referred_id': user_id,
                        'join_date': now,
                        'last_search_date': None,
                        'is_active': False,
                        'earnings': 0.0
                    })
                    self.users.update_one({'user_id': referrer_id}, {'$inc': {'total_refs': 1, 'pending_refs': 1}})
                    # Give referrer 3 passes
                    self.add_passes(referrer_id, 3, "Referral bonus passes")

            self.user_cache.pop(f"user_{user_id}", None)
            if referrer_id:
                self.user_cache.pop(f"user_{referrer_id}", None)
            return True
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return False

    # ========== PASSES SYSTEM ==========

    def add_passes(self, user_id, count, description=""):
        """Add game passes to user"""
        try:
            user_id = int(user_id)
            self.users.update_one({'user_id': user_id}, {'$inc': {'passes': count}})
            self.user_cache.pop(f"user_{user_id}", None)
            logger.info(f"Added {count} passes to user {user_id}: {description}")
            return True
        except Exception as e:
            logger.error(f"Error adding passes: {e}")
            return False

    def deduct_pass(self, user_id):
        """Deduct 1 pass from user"""
        try:
            user_id = int(user_id)
            user = self.get_user(user_id)
            if not user or user.get('passes', 0) <= 0:
                return False
            self.users.update_one({'user_id': user_id}, {'$inc': {'passes': -1}})
            self.user_cache.pop(f"user_{user_id}", None)
            return True
        except Exception as e:
            logger.error(f"Error deducting pass: {e}")
            return False

    # ========== REF ACTIVITY ==========

    def get_ref_activity(self, referrer_id, limit=20):
        """Get activity of referred users (movie searches, shortlinks)"""
        try:
            referrer_id = int(referrer_id)
            refs = list(self.referrals.find({'referrer_id': referrer_id}).limit(limit))
            result = []
            today = datetime.now().date().isoformat()
            for ref in refs:
                referred_user = self.get_user(ref['referred_id'])
                if not referred_user:
                    continue
                # Check if they searched today
                today_search = self.daily_searches.find_one({'user_id': ref['referred_id'], 'date': today})
                last_search_log = self.search_logs.find_one({'user_id': ref['referred_id']}, sort=[('timestamp', DESCENDING)])
                last_search_str = "No activity yet"
                if last_search_log:
                    try:
                        ts = datetime.fromisoformat(last_search_log['timestamp'])
                        diff = datetime.now() - ts
                        if diff.days > 0: last_search_str = f"Searched {diff.days}d ago"
                        elif diff.seconds // 3600 > 0: last_search_str = f"Searched {diff.seconds // 3600}h ago"
                        else: last_search_str = f"Searched {diff.seconds // 60}min ago"
                    except:
                        last_search_str = "Searched recently"
                result.append({
                    'user_id': ref['referred_id'],
                    'first_name': referred_user.get('first_name', 'User'),
                    'is_active': ref.get('is_active', False),
                    'last_search': last_search_str,
                    'searched_today': bool(today_search),
                    'join_date': ref.get('join_date', '')
                })
            return result
        except Exception as e:
            logger.error(f"Error getting ref activity: {e}")
            return []

    # ========== SEARCH RECORDING ==========

    def record_search(self, user_id):
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
                return {'success': False, 'message': 'Account blocked'}
            daily_count = self.daily_searches.count_documents({'user_id': user_id, 'date': today})
            if daily_count >= self.config.MAX_SEARCHES_PER_DAY:
                return {'success': False, 'message': 'Daily limit reached'}
            last_search = self.search_logs.find_one({'user_id': user_id}, sort=[('timestamp', DESCENDING)])
            if last_search:
                last_time = datetime.fromisoformat(last_search['timestamp'])
                if (now - last_time).total_seconds() < self.config.MIN_TIME_BETWEEN_SEARCHES:
                    return {'success': False, 'message': 'Please wait before searching again'}
            self.search_logs.insert_one({'user_id': user_id, 'timestamp': now.isoformat(), 'date': today})
            self.daily_searches.update_one({'user_id': user_id, 'date': today}, {'$inc': {'count': 1}}, upsert=True)
            was_first_search = (user.get('total_searches', 0) == 0)
            self.users.update_one({'user_id': user_id}, {'$inc': {'total_searches': 1}, '$set': {'last_active': now.isoformat()}})
            if was_first_search:
                self.activate_referral(user_id)
            self.user_cache.pop(f"user_{user_id}", None)
            return {'success': True, 'message': 'Search recorded!'}
        except Exception as e:
            logger.error(f"Error recording search: {e}")
            return {'success': False, 'message': str(e)}

    def activate_referral(self, referred_id):
        try:
            referred_id = int(referred_id)
            referral = self.referrals.find_one({'referred_id': referred_id})
            if referral and not referral.get('is_active'):
                now = datetime.now().isoformat()
                self.referrals.update_one({'referred_id': referred_id}, {'$set': {'is_active': True, 'first_search_date': now}})
                referrer_id = referral['referrer_id']
                self.users.update_one({'user_id': referrer_id}, {'$inc': {'pending_refs': -1, 'active_refs': 1}})
                self.add_balance(referrer_id, self.config.REFERRAL_BONUS, f"Referral bonus for user {referred_id}")
                self.update_user_tier(referrer_id)
                self.user_cache.pop(f"user_{referrer_id}", None)
                self.add_live_activity('referral', referrer_id, self.config.REFERRAL_BONUS, f"got referral bonus ₹{self.config.REFERRAL_BONUS}")
                return True
        except Exception as e:
            logger.error(f"Error activating referral: {e}")
            return False

    def process_daily_referral_earnings(self):
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
                    today_search = self.daily_searches.find_one({'user_id': referred_id, 'date': today})
                    if today_search:
                        referrer = self.get_user(referrer_id)
                        if referrer and not referrer.get('withdrawal_blocked') and not referrer.get('suspicious_activity'):
                            tier_rate = self.config.get_tier_rate(referrer.get('tier', 1))
                            self.add_balance(referrer_id, tier_rate, f"Daily earning from user {referred_id} on {today}")
                            self.referrals.update_one({'_id': ref['_id']}, {'$inc': {'earnings': tier_rate}, '$set': {'last_earning_date': today}})
                            earnings_count += 1
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
        try:
            user_id = int(user_id)
            existing = self.channel_joins.find_one({'user_id': user_id, 'channel_id': str(channel_id)})
            if existing:
                return False
            self.channel_joins.insert_one({'user_id': user_id, 'channel_id': str(channel_id), 'joined_at': datetime.now().isoformat()})
            self.add_balance(user_id, self.config.CHANNEL_JOIN_BONUS, "Channel join bonus")
            self.users.update_one({'user_id': user_id}, {'$set': {'channel_joined': True}})
            self.user_cache.pop(f"user_{user_id}", None)
            self.add_live_activity('bonus', user_id, self.config.CHANNEL_JOIN_BONUS, f"joined channel and got ₹{self.config.CHANNEL_JOIN_BONUS}")
            return True
        except Exception as e:
            logger.error(f"Error marking channel join: {e}")
            return False

    # ========== DAILY BONUS ==========

    def claim_day_bonus(self, user_id, date_str):
        try:
            user_id = int(user_id)
            user = self.get_user(user_id)
            if not user:
                return None
            try:
                claim_date = datetime.fromisoformat(date_str).date()
            except:
                logger.error(f"Invalid date format: {date_str}")
                return None
            today = datetime.now().date()
            if claim_date != today:
                return None
            existing = self.daily_bonus.find_one({'user_id': user_id, 'date': date_str})
            if existing:
                return None
            streak = user.get('daily_streak', 0)
            base_bonus = self.config.DAILY_BONUS
            streak_bonus = min(streak * 0.02, 0.15)
            total_bonus = base_bonus + streak_bonus
            self.add_balance(user_id, total_bonus, f"Daily bonus for {date_str}")
            # Add 1 pass for daily bonus
            self.add_passes(user_id, 1, "Daily bonus pass")
            self.daily_bonus.insert_one({'user_id': user_id, 'date': date_str, 'bonus': total_bonus, 'timestamp': datetime.now().isoformat()})
            new_streak = streak + 1
            self.users.update_one({'user_id': user_id}, {'$set': {'daily_streak': new_streak, 'last_daily': date_str}})
            self.add_live_activity('bonus', user_id, total_bonus, f"claimed daily bonus (streak: {new_streak})")
            self.user_cache.pop(f"user_{user_id}", None)
            return {'bonus': total_bonus, 'streak': new_streak, 'success': True}
        except Exception as e:
            logger.error(f"Error claiming day bonus: {e}")
            return None

    def get_user_bonus_days(self, user_id):
        try:
            user_id = int(user_id)
            claims = list(self.daily_bonus.find({'user_id': user_id}, {'date': 1, '_id': 0}).sort('date', 1))
            return [c['date'] for c in claims]
        except Exception as e:
            logger.error(f"Error getting bonus days: {e}")
            return []

    # ========== MISSIONS ==========

    def get_user_missions(self, user_id):
        try:
            user_id = int(user_id)
            today = datetime.now().date().isoformat()
            mission_data = self.missions.find_one({'user_id': user_id, 'date': today})
            if not mission_data:
                user = self.get_user(user_id)
                five_days_ago = (datetime.now() - timedelta(days=5)).date().isoformat()
                bonus_count = self.daily_bonus.count_documents({'user_id': user_id, 'date': {'$gte': five_days_ago}})
                mission_data = {
                    'user_id': user_id, 'date': today,
                    'mission1': {'progress': user.get('active_refs', 0) if user else 0, 'completed': (user.get('active_refs', 0) >= 10) if user else False, 'total': 10},
                    'mission2': {'progress': bonus_count, 'completed': bonus_count >= 5, 'total': 5},
                    'reward_claimed': False
                }
                self.missions.insert_one(mission_data)
            return mission_data
        except Exception as e:
            logger.error(f"Error getting missions: {e}")
            return None

    def update_mission_progress(self, user_id, mission_type, count=1):
        try:
            user_id = int(user_id)
            today = datetime.now().date().isoformat()
            mission_data = self.get_user_missions(user_id)
            if not mission_data:
                return None
            if mission_data.get('reward_claimed'):
                return mission_data
            if mission_type in ['referral', 'ad']:
                m = mission_data.get('mission1', {'progress': 0, 'completed': False, 'total': 10})
                m['progress'] = min(m['progress'] + count, m['total'])
                m['completed'] = m['progress'] >= m['total']
                mission_data['mission1'] = m
            elif mission_type == 'bonus':
                m = mission_data.get('mission2', {'progress': 0, 'completed': False, 'total': 5})
                m['progress'] = min(m['progress'] + count, m['total'])
                m['completed'] = m['progress'] >= m['total']
                mission_data['mission2'] = m
            self.missions.update_one({'user_id': user_id, 'date': today}, {'$set': mission_data}, upsert=True)
            return mission_data
        except Exception as e:
            logger.error(f"Error updating mission: {e}")
            return None

    def claim_mission_reward(self, user_id):
        try:
            user_id = int(user_id)
            today = datetime.now().date().isoformat()
            mission_data = self.missions.find_one({'user_id': user_id, 'date': today})
            if not mission_data:
                return {'success': False, 'message': 'No missions found'}
            if mission_data.get('reward_claimed'):
                return {'success': False, 'message': 'Reward already claimed'}
            m1 = mission_data.get('mission1', {})
            m2 = mission_data.get('mission2', {})
            if not m1.get('completed') or not m2.get('completed'):
                return {'success': False, 'message': 'Complete both missions first'}
            self.add_balance(user_id, 5.0, "Daily mission reward")
            self.missions.update_one({'user_id': user_id, 'date': today}, {'$set': {'reward_claimed': True}})
            self.add_live_activity('mission', user_id, 5, "claimed ₹5 mission reward!")
            return {'success': True, 'message': 'Reward claimed'}
        except Exception as e:
            logger.error(f"Error claiming mission reward: {e}")
            return {'success': False, 'message': str(e)}

    # ========== ADS MANAGEMENT ==========

    def get_all_ads(self):
        try:
            ads = list(self.ads.find().sort('order', 1))
            for ad in ads:
                ad['_id'] = str(ad['_id'])
            return ads
        except Exception as e:
            logger.error(f"Error getting ads: {e}")
            return []

    def get_ad(self, ad_id):
        try:
            ad = self.ads.find_one({'id': int(ad_id)})
            if ad:
                ad['_id'] = str(ad['_id'])
            return ad
        except Exception as e:
            logger.error(f"Error getting ad: {e}")
            return None

    def update_ad(self, ad_id, title, reward, link, meta, icon=None):
        try:
            update_data = {'title': title, 'reward': float(reward), 'link': link, 'meta': meta}
            if icon:
                update_data['icon'] = icon
            self.ads.update_one({'id': int(ad_id)}, {'$set': update_data}, upsert=True)
            return True
        except Exception as e:
            logger.error(f"Error updating ad: {e}")
            return False

    def delete_ad(self, ad_id):
        try:
            result = self.ads.delete_one({'id': int(ad_id)})
            if result.deleted_count > 0:
                self.daily_claims.delete_many({'ad_id': ad_id})
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting ad: {e}")
            return False

    def get_user_claimed_ads(self, user_id, date=None):
        try:
            user_id = int(user_id)
            if not date:
                date = datetime.now().date().isoformat()
            claims = list(self.daily_claims.find({'user_id': user_id, 'date': date}, {'ad_id': 1, '_id': 0}))
            return [c['ad_id'] for c in claims]
        except Exception as e:
            logger.error(f"Error getting claimed ads: {e}")
            return []

    def claim_ad(self, user_id, ad_id, reward):
        try:
            user_id = int(user_id)
            today = datetime.now().date().isoformat()
            existing = self.daily_claims.find_one({'user_id': user_id, 'ad_id': ad_id, 'date': today})
            if existing:
                return False
            self.add_balance(user_id, float(reward), f"Ad reward #{ad_id}")
            self.daily_claims.insert_one({'user_id': user_id, 'ad_id': ad_id, 'date': today, 'reward': float(reward), 'timestamp': datetime.now().isoformat()})
            self.add_live_activity('bonus', user_id, reward, f"claimed ad reward ₹{reward}")
            return True
        except Exception as e:
            logger.error(f"Error claiming ad: {e}")
            return False

    def reset_ad_claims(self, ad_id):
        try:
            self.daily_claims.delete_many({'ad_id': ad_id})
            return True
        except Exception as e:
            logger.error(f"Error resetting ad claims: {e}")
            return False

    # ========== BALANCE MANAGEMENT ==========

    def add_balance(self, user_id, amount, description=""):
        try:
            user_id = int(user_id)
            amount = float(amount)
            if amount <= 0:
                return False
            self.users.update_one({'user_id': user_id}, {'$inc': {'balance': amount, 'total_earned': amount}})
            self.add_transaction(user_id, 'credit', amount, description)
            self.user_cache.pop(f"user_{user_id}", None)
            return True
        except Exception as e:
            logger.error(f"Error adding balance: {e}")
            return False

    # ========== WITHDRAWAL ==========

    def process_withdrawal(self, user_id, amount, method, details):
        try:
            user_id = int(user_id)
            amount = float(amount)
            user = self.get_user(user_id)
            if not user:
                return {'success': False, 'message': 'User not found'}
            if user.get('suspicious_activity'):
                return {'success': False, 'message': 'Account under review'}
            if user.get('withdrawal_blocked'):
                return {'success': False, 'message': 'Withdrawals blocked. Contact support.'}
            if user['balance'] < amount:
                return {'success': False, 'message': f'Insufficient balance. You have ₹{user["balance"]:.2f}'}
            if amount < self.config.MIN_WITHDRAWAL:
                return {'success': False, 'message': f'Minimum withdrawal is ₹{self.config.MIN_WITHDRAWAL}'}
            pending = self.withdrawals.find_one({'user_id': user_id, 'status': 'pending'})
            if pending:
                return {'success': False, 'message': 'You already have a pending withdrawal'}
            self.users.update_one({'user_id': user_id}, {'$inc': {'balance': -amount}})
            now = datetime.now().isoformat()
            withdrawal = {
                'user_id': user_id, 'amount': amount, 'method': method, 'details': details,
                'status': 'pending', 'request_date': now, 'processed_date': None,
                'user_name': user.get('first_name', ''), 'username': user.get('username', ''),
                'total_searches': user.get('total_searches', 0), 'active_refs': user.get('active_refs', 0)
            }
            result = self.withdrawals.insert_one(withdrawal)
            self.add_transaction(user_id, 'withdrawal_request', -amount, f"Withdrawal request #{str(result.inserted_id)[-6:]}")
            self.add_live_activity('withdraw_request', user_id, amount, f"requested withdrawal of ₹{amount}")
            self.user_cache.pop(f"user_{user_id}", None)
            self.log_system_event('withdrawal_request', f"User {user_id}: ₹{amount}")
            return {'success': True, 'message': 'Withdrawal request submitted successfully', 'id': str(result.inserted_id)}
        except Exception as e:
            logger.error(f"Error processing withdrawal: {e}")
            return {'success': False, 'message': 'Internal error. Please try again.'}

    def get_user_withdrawals(self, user_id, limit=10):
        try:
            user_id = int(user_id)
            withdrawals = self.withdrawals.find({'user_id': user_id}).sort('request_date', -1).limit(limit)
            result = []
            for w in withdrawals:
                w['_id'] = str(w['_id'])
                result.append(w)
            return result
        except Exception as e:
            logger.error(f"Error getting withdrawals: {e}")
            return []

    def get_pending_withdrawals(self, limit=10):
        try:
            withdrawals = self.withdrawals.find({'status': 'pending'}).sort('request_date', 1).limit(limit)
            result = []
            for w in withdrawals:
                w['_id'] = str(w['_id'])
                result.append(w)
            return result
        except Exception as e:
            logger.error(f"Error getting pending withdrawals: {e}")
            return []

    def approve_withdrawal(self, withdrawal_id, admin_id):
        try:
            from bson.objectid import ObjectId
            withdrawal = self.withdrawals.find_one({'_id': ObjectId(withdrawal_id)})
            if not withdrawal:
                return False
            self.withdrawals.update_one({'_id': ObjectId(withdrawal_id)}, {'$set': {'status': 'completed', 'processed_date': datetime.now().isoformat(), 'admin_id': int(admin_id)}})
            self.add_transaction(withdrawal['user_id'], 'withdrawal_approved', -withdrawal['amount'], f"Withdrawal approved #{withdrawal_id[-8:]}")
            self.add_live_activity('withdraw', withdrawal['user_id'], withdrawal['amount'], f"withdrew ₹{withdrawal['amount']}")
            return True
        except Exception as e:
            logger.error(f"Error approving withdrawal: {e}")
            return False

    def reject_withdrawal(self, withdrawal_id, admin_id):
        try:
            from bson.objectid import ObjectId
            withdrawal = self.withdrawals.find_one({'_id': ObjectId(withdrawal_id)})
            if not withdrawal:
                return False
            self.withdrawals.update_one({'_id': ObjectId(withdrawal_id)}, {'$set': {'status': 'rejected', 'processed_date': datetime.now().isoformat(), 'admin_id': int(admin_id)}})
            self.add_balance(withdrawal['user_id'], withdrawal['amount'], "Refund for rejected withdrawal")
            return True
        except Exception as e:
            logger.error(f"Error rejecting withdrawal: {e}")
            return False

    # ========== TRANSACTIONS ==========

    def add_transaction(self, user_id, type_, amount, description=""):
        try:
            user_id = int(user_id)
            transaction = {'user_id': user_id, 'type': type_, 'amount': float(amount), 'description': description, 'timestamp': datetime.now().isoformat(), 'status': 'completed'}
            self.transactions.insert_one(transaction)
            return True
        except Exception as e:
            logger.error(f"Error adding transaction: {e}")
            return False

    # ========== TIER MANAGEMENT ==========

    def update_user_tier(self, user_id):
        try:
            user_id = int(user_id)
            user = self.get_user(user_id)
            if not user:
                return
            active_refs = user.get('active_refs', 0)
            new_tier = self.config.calculate_tier(active_refs)
            if new_tier != user.get('tier'):
                self.users.update_one({'user_id': user_id}, {'$set': {'tier': new_tier}})
                self.user_cache.pop(f"user_{user_id}", None)
                return new_tier
            return user.get('tier')
        except Exception as e:
            logger.error(f"Error updating tier: {e}")
            return None

    def update_notification_setting(self, user_id, setting, value):
        try:
            user_id = int(user_id)
            self.users.update_one({'user_id': user_id}, {'$set': {f'notify_{setting}': value}})
            self.user_cache.pop(f"user_{user_id}", None)
            return True
        except Exception as e:
            logger.error(f"Error updating notification setting: {e}")
            return False

    # ========== LEADERBOARD ==========

    def get_leaderboard(self, limit=10):
        try:
            users = self.users.find(
                {'active_refs': {'$gt': 0}, 'suspicious_activity': False},
                {'first_name': 1, 'active_refs': 1, 'total_earned': 1, 'tier': 1}
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

    # ============================================================
    # ========== GAME FUNCTIONS ==========
    # ============================================================

    DAILY_GAME_LIMIT = 999999.0  # No limit — owner profits from 60% loss rate
    SPIN_COST = 0  # 1 pass (deducted separately)
    SPIN_SEGMENTS = [
        {'label': '₹0.50', 'value': 0.5},
        {'label': '₹1',    'value': 1.0},
        {'label': '₹0.25', 'value': 0.25},
        {'label': '₹2',    'value': 2.0},
        {'label': '₹0.10', 'value': 0.1},
        {'label': '₹5',    'value': 5.0},
        {'label': '₹0.50', 'value': 0.5},
        {'label': '₹1',    'value': 1.0},
    ]
    # Weighted: lower values appear more often (60% loss/low win rate for owner profit)
    SPIN_WEIGHTS = [5, 4, 6, 2, 7, 1, 5, 4]  # ₹0.10 and ₹0.25 most common

    def get_game_state(self, user_id, date=None):
        try:
            user_id = int(user_id)
            if not date:
                date = datetime.now().date().isoformat()
            state = self.game_states.find_one({'user_id': user_id, 'date': date})
            if not state:
                state = {
                    'user_id': user_id, 'date': date,
                    'spin_left': 5, 'guess_left': 3, 'coin_left': 5, 'scratch_left': 2,
                    'today_game_earned': 0.0, 'wins': 0, 'win_streak': 0,
                    'guess_secret': random.randint(1, 10), 'guess_attempts_used': 0
                }
                self.game_states.insert_one(state)
            if '_id' in state:
                state['_id'] = str(state['_id'])
            return state
        except Exception as e:
            logger.error(f"Error getting game state: {e}")
            return {'spin_left': 5, 'guess_left': 3, 'coin_left': 5, 'scratch_left': 2, 'today_game_earned': 0.0, 'wins': 0, 'win_streak': 0}

    def add_game_earning(self, user_id, amount, game_type='game', description='Game reward'):
        """Add game earning to user balance — winnings save to wallet"""
        try:
            user_id = int(user_id)
            amount = float(amount)
            today = datetime.now().date().isoformat()
            state = self.get_game_state(user_id, today)
            already_earned = state.get('today_game_earned', 0.0)

            # Add to balance
            self.add_balance(user_id, amount, description)

            # Update game state
            new_earned = already_earned + amount
            self.game_states.update_one(
                {'user_id': user_id, 'date': today},
                {'$set': {'today_game_earned': new_earned}, '$inc': {'wins': 1}},
                upsert=True
            )

            # Update user game stats
            self.users.update_one({'user_id': user_id}, {'$inc': {'games_won': 1, 'total_game_earned': amount}})
            self.user_cache.pop(f"user_{user_id}", None)
            self.add_live_activity('game', user_id, amount, f"won ₹{amount:.2f} in {game_type}")

            return {'success': True, 'earned': amount, 'today_total': new_earned}
        except Exception as e:
            logger.error(f"Error adding game earning: {e}")
            return {'success': False, 'message': str(e), 'earned': 0}

    def deduct_game_balance(self, user_id, amount, game_type='game'):
        """Deduct bet from user balance"""
        try:
            user_id = int(user_id)
            amount = float(amount)
            user = self.get_user(user_id)
            if not user:
                return {'success': False, 'message': 'User not found'}
            if user.get('balance', 0) < amount:
                return {'success': False, 'message': 'Insufficient balance'}
            self.users.update_one({'user_id': user_id}, {'$inc': {'balance': -amount}})
            self.add_transaction(user_id, 'game_bet', -amount, f"Game bet in {game_type}")
            self.user_cache.pop(f"user_{user_id}", None)
            return {'success': True, 'deducted': amount}
        except Exception as e:
            logger.error(f"Error deducting game balance: {e}")
            return {'success': False, 'message': str(e)}

    def process_game_spin(self, user_id):
        """Spin wheel — costs 1 pass, winnings go to wallet"""
        try:
            user_id = int(user_id)
            today = datetime.now().date().isoformat()
            state = self.get_game_state(user_id, today)
            if state.get('spin_left', 0) <= 0:
                return {'success': False, 'message': 'Aaj ke spins khatam! Kal aao'}

            # Check & deduct pass
            user = self.get_user(user_id)
            if not user or user.get('passes', 0) <= 0:
                return {'success': False, 'message': 'Passes nahi hain! Refer karo ya daily bonus lo'}
            if not self.deduct_pass(user_id):
                return {'success': False, 'message': 'Pass deduct nahi hua'}

            # Weighted random segment — 60% skewed to lower rewards
            weights = self.SPIN_WEIGHTS
            total_w = sum(weights)
            r = random.random() * total_w
            selected = 0
            for i, w in enumerate(weights):
                r -= w
                if r <= 0:
                    selected = i
                    break

            reward = self.SPIN_SEGMENTS[selected]['value']
            reward_label = self.SPIN_SEGMENTS[selected]['label']

            # Win goes directly to wallet
            earn_result = self.add_game_earning(user_id, reward, 'spin', f"Spin reward {reward_label}")

            new_spin_left = max(0, state.get('spin_left', 5) - 1)
            self.game_states.update_one({'user_id': user_id, 'date': today}, {'$set': {'spin_left': new_spin_left}})

            return {
                'success': True, 'reward': earn_result.get('earned', reward),
                'reward_label': reward_label, 'segment_index': selected,
                'spin_left': new_spin_left, 'today_earned': earn_result.get('today_total', 0)
            }
        except Exception as e:
            logger.error(f"Error processing spin: {e}")
            return {'success': False, 'message': str(e)}

    def process_game_guess(self, user_id, guess, bet):
        """Number guess — costs 1 pass per game (not per attempt), bets from balance"""
        try:
            user_id = int(user_id)
            today = datetime.now().date().isoformat()
            state = self.get_game_state(user_id, today)
            if state.get('guess_left', 0) <= 0:
                return {'success': False, 'message': 'Aaj ke tries khatam! Kal aao'}

            user = self.get_user(user_id)
            if not user or user.get('passes', 0) <= 0:
                return {'success': False, 'message': 'Passes nahi hain!'}

            # Deduct bet from balance
            deduct_result = self.deduct_game_balance(user_id, bet, 'guess')
            if not deduct_result.get('success'):
                return deduct_result

            secret = state.get('guess_secret', random.randint(1, 10))
            attempts_used = state.get('guess_attempts_used', 0) + 1
            is_correct = (guess == secret)
            is_last_attempt = (attempts_used >= 3)

            result = {
                'success': True, 'correct': is_correct,
                'secret': secret if (is_correct or is_last_attempt) else None,
                'attempts_used': attempts_used, 'guess': guess, 'reward': 0,
                'guess_left': state.get('guess_left', 3)
            }

            if is_correct:
                reward = bet * 8
                earn_result = self.add_game_earning(user_id, reward, 'guess', f"Guess correct! x8")
                result['reward'] = earn_result.get('earned', 0)
                result['today_earned'] = earn_result.get('today_total', 0)
                # Deduct 1 pass on correct (game over)
                self.deduct_pass(user_id)
                new_guess_left = max(0, state.get('guess_left', 3) - 1)
                self.game_states.update_one({'user_id': user_id, 'date': today}, {'$set': {'guess_left': new_guess_left, 'guess_secret': random.randint(1, 10), 'guess_attempts_used': 0}})
                result['guess_left'] = new_guess_left
            elif is_last_attempt:
                # Wrong and out of attempts — deduct pass
                self.deduct_pass(user_id)
                new_guess_left = max(0, state.get('guess_left', 3) - 1)
                self.game_states.update_one({'user_id': user_id, 'date': today}, {'$set': {'guess_left': new_guess_left, 'guess_secret': random.randint(1, 10), 'guess_attempts_used': 0}})
                result['guess_left'] = new_guess_left
            else:
                diff = abs(guess - secret)
                if diff <= 1: hint = '🔥 Bahut paas!'
                elif diff <= 3: hint = '♨️ Kaafi paas'
                elif diff <= 5: hint = '🌡️ Thoda door'
                else: hint = '❄️ Bahut door!'
                hint += ' (Kam karo)' if guess > secret else ' (Zyada karo)'
                result['hint'] = hint
                result['diff'] = diff
                self.game_states.update_one({'user_id': user_id, 'date': today}, {'$set': {'guess_attempts_used': attempts_used}})

            return result
        except Exception as e:
            logger.error(f"Error processing guess: {e}")
            return {'success': False, 'message': str(e)}

    def process_game_coin(self, user_id, choice, bet):
        """Coin flip — costs 1 pass, bet from balance, 60% house edge"""
        try:
            user_id = int(user_id)
            today = datetime.now().date().isoformat()
            state = self.get_game_state(user_id, today)
            if state.get('coin_left', 0) <= 0:
                return {'success': False, 'message': 'Aaj ke flips khatam! Kal aao'}

            user = self.get_user(user_id)
            if not user or user.get('passes', 0) <= 0:
                return {'success': False, 'message': 'Passes nahi hain!'}

            # Deduct bet
            deduct_result = self.deduct_game_balance(user_id, bet, 'coin')
            if not deduct_result.get('success'):
                return deduct_result

            # Deduct 1 pass
            self.deduct_pass(user_id)

            # 40% win chance (house edge)
            actual_result = 'heads' if random.random() < 0.5 else 'tails'
            won = (choice == actual_result)

            new_coin_left = max(0, state.get('coin_left', 5) - 1)
            self.game_states.update_one({'user_id': user_id, 'date': today}, {'$set': {'coin_left': new_coin_left}})

            result = {'success': True, 'won': won, 'result': actual_result, 'choice': choice, 'bet': bet, 'coin_left': new_coin_left, 'reward': 0}

            if won:
                reward = bet * 2
                earn_result = self.add_game_earning(user_id, reward, 'coin', f"Coin flip win ₹{reward}")
                result['reward'] = earn_result.get('earned', 0)
                result['today_earned'] = earn_result.get('today_total', 0)

            return result
        except Exception as e:
            logger.error(f"Error processing coin flip: {e}")
            return {'success': False, 'message': str(e)}

    def process_game_scratch(self, user_id):
        """Scratch card — costs 1 pass, winnings to wallet"""
        try:
            user_id = int(user_id)
            today = datetime.now().date().isoformat()
            state = self.get_game_state(user_id, today)
            if state.get('scratch_left', 0) <= 0:
                return {'success': False, 'message': 'Aaj ke cards khatam! Kal aao'}

            user = self.get_user(user_id)
            if not user or user.get('passes', 0) <= 0:
                return {'success': False, 'message': 'Passes nahi hain!'}

            # Deduct 1 pass
            self.deduct_pass(user_id)

            # Weighted reward — 60% are low rewards
            roll = random.random()
            if roll < 0.35: reward = 0.1
            elif roll < 0.58: reward = 0.25
            elif roll < 0.75: reward = 0.5
            elif roll < 0.87: reward = 1.0
            elif roll < 0.94: reward = 2.0
            elif roll < 0.98: reward = 5.0
            else: reward = 10.0

            earn_result = self.add_game_earning(user_id, reward, 'scratch', f"Scratch card ₹{reward}")
            new_scratch_left = max(0, state.get('scratch_left', 2) - 1)
            self.game_states.update_one({'user_id': user_id, 'date': today}, {'$set': {'scratch_left': new_scratch_left}})

            return {
                'success': True, 'reward': earn_result.get('earned', reward),
                'scratch_left': new_scratch_left, 'today_earned': earn_result.get('today_total', 0)
            }
        except Exception as e:
            logger.error(f"Error processing scratch: {e}")
            return {'success': False, 'message': str(e)}

    # ========== SYSTEM & CLEANUP ==========

    def remove_blocked_users(self, user_ids, progress_callback=None):
        try:
            deleted_count = 0
            failed_count = 0
            total = len(user_ids)
            for i, user_id in enumerate(user_ids):
                try:
                    user_id = int(user_id)
                    self.users.delete_one({'user_id': user_id})
                    self.transactions.delete_many({'user_id': user_id})
                    self.withdrawals.delete_many({'user_id': user_id})
                    self.referrals.delete_many({'$or': [{'referrer_id': user_id}, {'referred_id': user_id}]})
                    self.daily_searches.delete_many({'user_id': user_id})
                    self.search_logs.delete_many({'user_id': user_id})
                    self.daily_bonus.delete_many({'user_id': user_id})
                    self.missions.delete_many({'user_id': user_id})
                    self.daily_claims.delete_many({'user_id': user_id})
                    self.issues.delete_many({'user_id': user_id})
                    self.live_activity.delete_many({'user_id': user_id})
                    self.game_states.delete_many({'user_id': user_id})
                    self.user_cache.pop(f"user_{user_id}", None)
                    deleted_count += 1
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Error deleting user {user_id}: {e}")
                if progress_callback and (i + 1) % 10 == 0:
                    progress_callback(i + 1, total)
            return deleted_count, failed_count
        except Exception as e:
            logger.error(f"Error removing blocked users: {e}")
            return 0, len(user_ids)

    def log_system_event(self, event_type, description):
        try:
            self.system_stats.insert_one({'event_type': event_type, 'description': description, 'timestamp': datetime.now().isoformat()})
        except Exception as e:
            logger.error(f"Error logging system event: {e}")

    def get_system_stats(self):
        try:
            return {
                'total_users': self.users.count_documents({}),
                'pending_withdrawals': self.withdrawals.count_documents({'status': 'pending'}),
                'total_searches': self.search_logs.count_documents({}),
                'pending_support': self.issues.count_documents({'status': 'pending'})
            }
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {}

    def cleanup(self):
        try:
            if hasattr(self, 'client') and self.client:
                self.client.close()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database: {e}")
