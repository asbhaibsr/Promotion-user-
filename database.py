# ═══════════════════════════════════════════════════════════
# EarnZone / FilmyFund — Telegram Mini App
# Owner   : @asbhaibsr
# Channel : @asbhai_bsr
# Contact : https://t.me/asbhaibsr
# ⚠️  Unauthorized modification or redistribution prohibited.
# © 2025 @asbhaibsr — All Rights Reserved
# ═══════════════════════════════════════════════════════════

# ===== database.py (FULLY UPDATED) =====

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
            self.pass_requests = self.db['pass_requests']
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
            self.referrals.create_index('activation_date')  # NEW: for month_active_refs query
            self.daily_searches.create_index([('user_id', ASCENDING), ('date', ASCENDING)], unique=True)
            self.search_logs.create_index([('user_id', ASCENDING), ('timestamp', DESCENDING)])
            self.search_logs.create_index('timestamp', expireAfterSeconds=2592000)
            self.withdrawals.create_index([('user_id', ASCENDING), ('request_date', DESCENDING)])
            self.withdrawals.create_index('status')
            self.channel_joins.create_index([('user_id', ASCENDING), ('channel_id', ASCENDING)], unique=True)
            self.daily_bonus.create_index([('user_id', ASCENDING), ('date', ASCENDING)], unique=True)
            self.daily_bonus.create_index('date')
            self.missions.create_index([('user_id', ASCENDING), ('date', ASCENDING), ('mission_id', ASCENDING)], unique=True)
            self.daily_claims.create_index([('user_id', ASCENDING), ('ad_id', ASCENDING)], unique=True)
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
                    {'id': 1, 'title': 'Install App & Earn', 'reward': 2.0, 'link': 'https://t.me/+8SdeM5gBihoxZjU1', 'meta': '⏱️ 2 min • 1.2k completed', 'icon': '📱', 'order': 1, 'edited_at': None, 'claim_code': None, 'timer_seconds': 0},
                    {'id': 2, 'title': 'Watch Video', 'reward': 0.5, 'link': 'https://t.me/+8SdeM5gBihoxZjU1', 'meta': '⏱️ 30 sec • 3.4k completed', 'icon': '🎬', 'order': 2, 'edited_at': None, 'claim_code': None, 'timer_seconds': 0},
                    {'id': 3, 'title': 'Join Channel', 'reward': 1.0, 'link': 'https://t.me/+8SdeM5gBihoxZjU1', 'meta': '⏱️ 1 min • 5.6k completed', 'icon': '📢', 'order': 3, 'edited_at': None, 'claim_code': None, 'timer_seconds': 0}
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

    def add_live_activity(self, activity_type, user_id, amount=0, description="", extra=None):
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
            if extra:
                activity.update(extra)
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

                emoji_map = {
                    'join': '🎉', 'withdraw': '💰', 'bonus': '🎁',
                    'mission': '🏆', 'referral': '👥', 'game': '🎮',
                    'support': '📩', 'daily_search': '🎬'
                }
                emoji = emoji_map.get(act['type'], '👤')

                display_text = act.get('description', '')
                if not display_text:
                    desc_map = {
                        'join': 'joined the bot',
                        'withdraw': f"withdrew ₹{act.get('amount', 0)}",
                        'bonus': f"claimed ₹{act.get('amount', 0)} bonus",
                        'mission': 'completed a mission',
                        'referral': 'got a new referral',
                        'game': f"won ₹{act.get('amount', 0)} in game",
                        'daily_search': 'searched movie today'
                    }
                    display_text = desc_map.get(act['type'], 'was active')

                result.append({
                    'type': act.get('type', 'activity'),
                    'user_name': act.get('user_name', 'User'),
                    'user_id': act.get('user_id', 0),
                    'amount': act.get('amount', 0),
                    'time': time_ago,
                    'avatar': emoji,
                    'description': display_text,
                    'referred_name': act.get('referred_name', ''),
                    'referrer_name': act.get('referrer_name', '')
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
                'username': user.get('username', '') if user else '',
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'status': 'pending',
                'read': False,
                'admin_reply': None,
                'reply_date': None
            }
            result = self.issues.insert_one(support_msg)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error adding support message: {e}")
            return None

    def get_pending_support_messages(self, limit=20):
        try:
            messages = list(self.issues.find().sort('timestamp', -1).limit(limit))
            for msg in messages:
                msg['_id'] = str(msg['_id'])
                user = self.get_user(msg.get('user_id'))
                if user:
                    msg['user_name'] = user.get('first_name', 'User')
                    msg['username'] = user.get('username', '')
            return messages
        except Exception as e:
            logger.error(f"Error getting support messages: {e}")
            return []

    def mark_support_replied(self, message_id, admin_id, reply_text):
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
            return True
        except Exception as e:
            logger.error(f"Error marking support replied: {e}")
            return False

    def delete_support_message(self, message_id):
        """Delete a support message by ID."""
        try:
            from bson.objectid import ObjectId
            result = self.issues.delete_one({'_id': ObjectId(message_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting support message: {e}")
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
                self.users.update_one(
                    {'user_id': user_id},
                    {'$set': {
                        'first_name': user_data.get('first_name', ''),
                        'username': user_data.get('username', ''),
                        'last_active': datetime.now().isoformat()
                    }}
                )
                # Check if someone is trying to refer an existing user
                if referrer_id and referrer_id != user_id:
                    # Find who originally referred this user
                    original_ref = self.referrals.find_one({'referred_id': user_id})
                    original_referrer_id = original_ref.get('referrer_id') if original_ref else None
                    return {
                        'is_new': False,
                        'already_on_bot': True,
                        'user_id': user_id,
                        'first_name': existing.get('first_name', 'User'),
                        'username': existing.get('username', ''),
                        'join_date': existing.get('join_date', '')[:10] if existing.get('join_date') else 'Unknown',
                        'active_refs': existing.get('active_refs', 0),
                        'balance': existing.get('balance', 0),
                        'original_referrer_id': original_referrer_id
                    }
                return False

            now = datetime.now().isoformat()
            new_user = {
                'user_id': user_id,
                'first_name': user_data.get('first_name', ''),
                'username': user_data.get('username', ''),
                'referrer_id': referrer_id,
                'balance': 0.0,
                'total_earned': 0.0,
                'today_earned': 0.0,
                'today_date': now[:10],
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
                'passes': 3
            }

            self.users.insert_one(new_user)

            if referrer_id and referrer_id != user_id:
                existing_ref = self.referrals.find_one({'referrer_id': referrer_id, 'referred_id': user_id})
                if not existing_ref:
                    self.referrals.insert_one({
                        'referrer_id': referrer_id,
                        'referred_id': user_id,
                        'referred_name': user_data.get('first_name', 'User'),
                        'referrer_name': '',
                        'join_date': now,
                        'last_search_date': None,
                        'is_active': False,
                        'earnings': 0.0
                    })
                    self.users.update_one({'user_id': referrer_id}, {'$inc': {'total_refs': 1, 'pending_refs': 1}})

            self.user_cache.pop(f"user_{user_id}", None)
            if referrer_id:
                self.user_cache.pop(f"user_{referrer_id}", None)
            return True
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return False

    # ========== NEW: MONTH ACTIVE REFS ==========

    def get_month_active_refs(self, referrer_id):
        """
        Count referrals that were ACTIVATED this calendar month.
        Used for withdrawal condition (user needs 20 this month).
        """
        try:
            referrer_id = int(referrer_id)
            now = datetime.now()
            # First day of current month
            month_start = datetime(now.year, now.month, 1).isoformat()

            count = self.referrals.count_documents({
                'referrer_id': referrer_id,
                'is_active': True,
                'activation_date': {'$gte': month_start}
            })
            return count
        except Exception as e:
            logger.error(f"Error getting month active refs: {e}")
            return 0

    # ========== LOG CHANNEL ACTIVATION ==========

    def activate_referral_by_log_channel(self, referred_id):
        try:
            referred_id = int(referred_id)
            referral = self.referrals.find_one({'referred_id': referred_id})

            if not referral:
                logger.info(f"No referral found for user {referred_id}")
                return {'activated': False, 'reason': 'no_referral'}

            if referral.get('is_active'):
                logger.info(f"Referral for {referred_id} already active")
                return {'activated': False, 'reason': 'already_active'}

            now = datetime.now().isoformat()
            referrer_id = referral['referrer_id']

            referrer = self.get_user(referrer_id)
            referred = self.get_user(referred_id)
            referrer_name = referrer.get('first_name', 'Unknown') if referrer else 'Unknown'
            referred_name = referred.get('first_name', 'Unknown') if referred else 'Unknown'

            self.referrals.update_one(
                {'referred_id': referred_id},
                {'$set': {
                    'is_active': True,
                    'activation_date': now,
                    'referrer_name': referrer_name
                }}
            )

            self.users.update_one(
                {'user_id': referrer_id},
                {'$inc': {'pending_refs': -1, 'active_refs': 1}}
            )

            self.add_balance(referrer_id, self.config.REFERRAL_BONUS, f"Referral bonus for user {referred_id}")
            self.add_passes(referrer_id, 3, f"Referral passes for user {referred_id}")
            self.update_user_tier(referrer_id)
            self.user_cache.pop(f"user_{referrer_id}", None)

            self.add_live_activity(
                'referral', referrer_id,
                self.config.REFERRAL_BONUS,
                f"referred {referred_name} → +₹{self.config.REFERRAL_BONUS} +3 Passes",
                extra={'referred_name': referred_name, 'referred_id': referred_id}
            )

            logger.info(f"✅ Referral activated: {referred_id} -> {referrer_id}")
            return {'activated': True, 'referrer_id': referrer_id, 'referred_id': referred_id, 'referrer_name': referrer_name, 'referred_name': referred_name}

        except Exception as e:
            logger.error(f"Error activating referral by log channel: {e}")
            return {'activated': False, 'reason': str(e)}

    # ========== DAILY SEARCH TRACKING ==========

    def record_daily_search(self, referred_user_id):
        try:
            referred_user_id = int(referred_user_id)
            today = datetime.now().date().isoformat()

            referral = self.referrals.find_one({'referred_id': referred_user_id, 'is_active': True})
            if not referral:
                return {'success': False, 'reason': 'no_active_referral'}

            referrer_id = referral['referrer_id']

            existing = self.daily_searches.find_one({'user_id': referred_user_id, 'date': today})
            if existing:
                return {'success': False, 'reason': 'already_credited_today'}

            self.daily_searches.insert_one({
                'user_id': referred_user_id,
                'referrer_id': referrer_id,
                'date': today,
                'timestamp': datetime.now().isoformat()
            })

            self.referrals.update_one(
                {'referred_id': referred_user_id},
                {'$set': {'last_search_date': today, 'today_searched': True}}
            )

            DAILY_SEARCH_EARNING = 0.30
            self.add_balance(referrer_id, DAILY_SEARCH_EARNING, f"Daily search earning from user {referred_user_id}")
            self.users.update_one({'user_id': referred_user_id}, {'$inc': {'total_searches': 1}})

            referred = self.get_user(referred_user_id)
            referrer = self.get_user(referrer_id)
            referred_name = referred.get('first_name', 'User') if referred else 'User'
            referrer_name = referrer.get('first_name', 'User') if referrer else 'User'

            self.add_live_activity(
                'daily_search', referrer_id,
                DAILY_SEARCH_EARNING,
                f"{referred_name} searched movie → +{int(DAILY_SEARCH_EARNING*100)} pts",
                extra={'referred_name': referred_name, 'referrer_name': referrer_name, 'referred_id': referred_user_id}
            )

            logger.info(f"✅ Daily search credited: referred={referred_user_id} referrer={referrer_id} +₹{DAILY_SEARCH_EARNING}")
            return {
                'success': True,
                'referrer_id': referrer_id,
                'referred_id': referred_user_id,
                'earning': DAILY_SEARCH_EARNING
            }

        except Exception as e:
            logger.error(f"Error recording daily search: {e}")
            return {'success': False, 'reason': str(e)}

    # ========== USER SELF-SEARCH (48 hour reset) ==========

    def record_self_search(self, user_id):
        """
        User khud movie search karta hai → 48 ghnte mein ek baar
        user ko bhi points milte hain (30 pts = ₹0.30)
        """
        try:
            user_id = int(user_id)
            now = datetime.now()
            now_iso = now.isoformat()

            user = self.get_user(user_id)
            if not user:
                return {'success': False, 'reason': 'user_not_found'}

            # Check last self search time
            last_self = user.get('last_self_search')
            if last_self:
                try:
                    last_dt = datetime.fromisoformat(last_self)
                    elapsed_hours = (now - last_dt).total_seconds() / 3600
                    if elapsed_hours < 48:
                        remaining_h = int(48 - elapsed_hours)
                        remaining_m = int((48 - elapsed_hours - remaining_h) * 60)
                        return {
                            'success': False,
                            'reason': 'too_soon',
                            'next_in_hours': remaining_h,
                            'next_in_minutes': remaining_m
                        }
                except:
                    pass

            # Credit 30 pts (₹0.30) to user themselves
            SELF_SEARCH_EARNING = 0.30
            self.add_balance(user_id, SELF_SEARCH_EARNING, "Self movie search bonus (48hr)")
            self.users.update_one(
                {'user_id': user_id},
                {
                    '$set': {'last_self_search': now_iso},
                    '$inc': {'total_searches': 1, 'self_search_count': 1}
                }
            )
            self.user_cache.pop(f"user_{user_id}", None)

            # Update mission progress
            self._update_single_mission_progress(user_id, 'm_self_search', 1)

            self.add_live_activity(
                'bonus', user_id, SELF_SEARCH_EARNING,
                "Movie search ki → +30 pts (48hr bonus)"
            )

            logger.info(f"✅ Self search: user={user_id} +₹{SELF_SEARCH_EARNING}")
            return {
                'success': True,
                'earning': SELF_SEARCH_EARNING,
                'points': int(SELF_SEARCH_EARNING * 100)
            }

        except Exception as e:
            logger.error(f"Self search error: {e}")
            return {'success': False, 'reason': str(e)}

    def get_self_search_status(self, user_id):
        """Check how many hours until next self search"""
        try:
            user_id = int(user_id)
            user = self.get_user(user_id)
            if not user:
                return {'can_search': False}

            last_self = user.get('last_self_search')
            if not last_self:
                return {'can_search': True, 'hours_left': 0}

            now = datetime.now()
            try:
                last_dt = datetime.fromisoformat(last_self)
                elapsed = (now - last_dt).total_seconds() / 3600
                if elapsed >= 48:
                    return {'can_search': True, 'hours_left': 0}
                h_left = int(48 - elapsed)
                m_left = int((48 - elapsed - h_left) * 60)
                return {
                    'can_search': False,
                    'hours_left': h_left,
                    'minutes_left': m_left,
                    'last_search': last_self
                }
            except:
                return {'can_search': True, 'hours_left': 0}

        except Exception as e:
            logger.error(f"Self search status error: {e}")
            return {'can_search': True, 'hours_left': 0}

    def get_pending_reminders(self):
        """Get users who haven't claimed bonus/missions today — for daily reminder"""
        try:
            today = datetime.now().date().isoformat()
            now_hour = datetime.now().hour

            # Only send reminders in evening (7-10 PM)
            if not (19 <= now_hour <= 22):
                return []

            # Find users who haven't claimed bonus today
            claimed_today = set(
                doc['user_id'] for doc in
                self.daily_bonus.find({'date': today}, {'user_id': 1})
            )

            # Get active users (active in last 7 days)
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            active_users = list(self.users.find(
                {'last_active': {'$gte': week_ago}},
                {'user_id': 1, 'first_name': 1}
            ).limit(500))

            pending = []
            for u in active_users:
                uid = u['user_id']
                if uid not in claimed_today:
                    # Check if already reminded today
                    last_reminded = u.get('last_reminded', '')
                    if last_reminded[:10] != today:
                        pending.append({'user_id': uid, 'first_name': u.get('first_name', 'User')})

            return pending[:200]  # max 200 per run

        except Exception as e:
            logger.error(f"Get pending reminders error: {e}")
            return []

    def mark_user_reminded(self, user_id):
        """Mark user as reminded today"""
        try:
            self.users.update_one(
                {'user_id': int(user_id)},
                {'$set': {'last_reminded': datetime.now().isoformat()}}
            )
        except:
            pass

    # ========== PASSES SYSTEM ==========

    def add_passes(self, user_id, count, description=""):
        try:
            user_id = int(user_id)
            self.users.update_one({'user_id': user_id}, {'$inc': {'passes': count}})
            self.user_cache.pop(f"user_{user_id}", None)
            logger.info(f"Added {count} passes to user {user_id}: {description}")
            return True
        except Exception as e:
            logger.error(f"Error adding passes: {e}")
            return False

    # ========== MILESTONE BONUSES ==========
    MILESTONES = [
        {'refs': 5,   'reward': 2.0},
        {'refs': 10,  'reward': 5.0},
        {'refs': 25,  'reward': 15.0},
        {'refs': 50,  'reward': 40.0},
        {'refs': 100, 'reward': 100.0},
    ]

    def claim_milestone(self, user_id, refs_required, reward):
        try:
            user_id = int(user_id)
            refs_required = int(refs_required)
            reward = float(reward)

            # Validate milestone exists
            valid = any(m['refs'] == refs_required for m in self.MILESTONES)
            if not valid:
                return {'success': False, 'message': 'Invalid milestone'}

            user = self.get_user(user_id)
            if not user:
                return {'success': False, 'message': 'User not found'}

            # Check refs requirement
            if user.get('active_refs', 0) < refs_required:
                return {'success': False, 'message': f'{refs_required} active refs chahiye'}

            # Check not already claimed — atomic update
            result = self.users.find_one_and_update(
                {
                    'user_id': user_id,
                    'active_refs': {'$gte': refs_required},
                    f'milestone_claimed_{refs_required}': {'$ne': True}
                },
                {'$set': {f'milestone_claimed_{refs_required}': True}}
            )
            if not result:
                return {'success': False, 'message': 'Already claimed or not eligible'}

            self.add_balance(user_id, reward, f"Milestone bonus: {refs_required} refs")
            self.add_live_activity('milestone', user_id, reward, f"Milestone {refs_required} refs → +₹{reward}")
            logger.info(f"✅ Milestone claimed: user={user_id} refs={refs_required} reward=₹{reward}")
            return {'success': True, 'reward': reward}

        except Exception as e:
            logger.error(f"Milestone claim error: {e}")
            return {'success': False, 'message': str(e)}

    def deduct_pass(self, user_id):
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

    # ========== BADGE CLAIM ==========

    BADGE_REWARDS = [
        {'passes': 2,    'balance': 0},       # 0 Starter
        {'passes': 5,    'balance': 1.0},     # 1 Rising
        {'passes': 10,   'balance': 3.0},     # 2 Pro
        {'passes': 20,   'balance': 10.0},    # 3 Elite
        {'passes': 50,   'balance': 50.0},    # 4 Champion
        {'passes': 100,  'balance': 100.0},   # 5 Legend
        {'passes': 150,  'balance': 200.0},   # 6 Master
        {'passes': 200,  'balance': 300.0},   # 7 GrandMaster
        {'passes': 500,  'balance': 1000.0},  # 8 Mythic
        {'passes': 1000, 'balance': 5000.0},  # 9 God Tier
    ]

    BADGE_REQ_REFS = [0, 10, 50, 100, 500, 1000, 1500, 2000, 5000, 10000]

    def claim_badge(self, user_id, badge_idx):
        try:
            user_id = int(user_id)
            badge_idx = int(badge_idx)

            if badge_idx < 0 or badge_idx >= len(self.BADGE_REWARDS):
                return {'success': False, 'message': 'Invalid badge'}

            user = self.get_user(user_id)
            if not user:
                return {'success': False, 'message': 'User not found'}

            # Check refs requirement
            required_refs = self.BADGE_REQ_REFS[badge_idx]
            if user.get('active_refs', 0) < required_refs:
                return {'success': False, 'message': f'{required_refs} active refs chahiye'}

            # Atomic claim — prevent double claim
            field = f'badge_claimed_{badge_idx}'
            result = self.users.find_one_and_update(
                {'user_id': user_id, field: {'$ne': True}},
                {'$set': {field: True}}
            )
            if not result:
                return {'success': False, 'message': 'Badge already claimed!'}

            reward = self.BADGE_REWARDS[badge_idx]
            passes = reward['passes']
            balance = reward['balance']

            # Give rewards
            if passes > 0:
                self.add_passes(user_id, passes, f"Badge {badge_idx} reward")
            if balance > 0:
                self.add_balance(user_id, balance, f"Badge {badge_idx} reward")

            badge_names = ['Starter','Rising','Pro','Elite','Champion','Legend','Master','GrandMaster','Mythic','God Tier']
            bname = badge_names[badge_idx] if badge_idx < len(badge_names) else f'Badge {badge_idx}'
            self.add_live_activity('badge', user_id, balance,
                f"Badge claimed: {bname} → +{passes} passes" + (f" +₹{balance}" if balance > 0 else ""))

            logger.info(f"✅ Badge claimed: user={user_id} badge={badge_idx} passes={passes} balance={balance}")
            return {'success': True, 'passes': passes, 'balance': balance}

        except Exception as e:
            logger.error(f"Badge claim error: {e}")
            return {'success': False, 'message': str(e)}

    # ========== PASS PURCHASE ==========

    def request_pass_purchase(self, user_id, pkg_id, passes, price, txn_id, screenshot=None):
        try:
            user_id = int(user_id)
            now = datetime.now().isoformat()

            # Check duplicate TXN ID
            existing = self.pass_requests.find_one({'txn_id': txn_id})
            if existing:
                return {'success': False, 'message': 'Ye Transaction ID pehle se use ho chuki hai!'}

            req = {
                'user_id': user_id,
                'pkg_id': pkg_id,
                'passes': passes,
                'price': price,
                'txn_id': txn_id,
                'screenshot': screenshot[:500] if screenshot else None,  # store thumbnail only
                'status': 'pending',
                'created_at': now,
                'processed_at': None,
                'processed_by': None
            }
            result = self.pass_requests.insert_one(req)
            req_id = str(result.inserted_id)

            # Notify in support messages too
            user = self.get_user(user_id)
            uname = user.get('first_name', 'User') if user else 'User'
            self.add_support_message(user_id, f"PASS REQUEST: {passes} passes for ₹{price} | TXN: {txn_id}")

            logger.info(f"✅ Pass request: user={user_id} pkg={pkg_id} passes={passes} txn={txn_id}")
            return {'success': True, 'request_id': req_id, 'message': 'Request bhej di!'}

        except Exception as e:
            logger.error(f"Pass request error: {e}")
            return {'success': False, 'message': str(e)}

    def process_pass_request(self, request_id, action, admin_id):
        try:
            from bson import ObjectId
            req = self.pass_requests.find_one({'_id': ObjectId(request_id)})
            if not req:
                return {'success': False, 'message': 'Request not found'}
            if req.get('status') != 'pending':
                return {'success': False, 'message': 'Already processed'}

            now = datetime.now().isoformat()
            user_id = req['user_id']
            passes = req['passes']

            if action == 'verify':
                self.pass_requests.update_one(
                    {'_id': ObjectId(request_id)},
                    {'$set': {'status': 'verified', 'processed_at': now, 'processed_by': admin_id}}
                )
                self.add_passes(user_id, passes, f"Purchased {passes} passes ₹{req['price']}")
                self.add_live_activity('bonus', user_id, 0, f"Purchased {passes} passes")
                logger.info(f"✅ Passes verified: user={user_id} passes={passes}")
                return {'success': True, 'user_id': user_id, 'passes': passes, 'action': 'verify'}
            else:
                self.pass_requests.update_one(
                    {'_id': ObjectId(request_id)},
                    {'$set': {'status': 'rejected', 'processed_at': now, 'processed_by': admin_id}}
                )
                logger.info(f"Pass request rejected: user={user_id}")
                return {'success': True, 'user_id': user_id, 'passes': 0, 'action': 'reject'}

        except Exception as e:
            logger.error(f"Process pass request error: {e}")
            return {'success': False, 'message': str(e)}

    def get_pending_pass_requests(self, limit=20):
        try:
            reqs = list(self.pass_requests.find({'status': 'pending'}).sort('created_at', -1).limit(limit))
            for r in reqs:
                r['_id'] = str(r['_id'])
            return reqs
        except Exception as e:
            logger.error(f"Get pass requests error: {e}")
            return []

    # ========== REF ACTIVITY ==========

    def get_ref_activity(self, referrer_id, limit=20):
        try:
            referrer_id = int(referrer_id)
            today = datetime.now().date().isoformat()
            refs = list(self.referrals.find({'referrer_id': referrer_id}).limit(limit))
            result = []
            for ref in refs:
                referred_user = self.get_user(ref['referred_id'])
                if not referred_user:
                    continue
                today_search = self.daily_searches.find_one({'user_id': ref['referred_id'], 'date': today})
                result.append({
                    'user_id': ref['referred_id'],
                    'first_name': referred_user.get('first_name', 'User'),
                    'username': referred_user.get('username', ''),
                    'is_active': ref.get('is_active', False),
                    'activation_date': ref.get('activation_date', ''),
                    'join_date': ref.get('join_date', ''),
                    'earnings': ref.get('earnings', 0),
                    'today_searched': bool(today_search),
                    'last_search_date': ref.get('last_search_date', '')
                })
            return result
        except Exception as e:
            logger.error(f"Error getting ref activity: {e}")
            return []

    # ========== DAILY REFERRAL EARNINGS ==========

    def process_daily_referral_earnings(self):
        if not self.ensure_connection():
            return 0
        try:
            today = datetime.now().date().isoformat()
            today_searches = list(self.daily_searches.find({'date': today}))
            earnings_count = 0

            for search in today_searches:
                try:
                    referrer_id = search.get('referrer_id')
                    if not referrer_id:
                        continue
                    referrer = self.get_user(referrer_id)
                    if referrer and not referrer.get('withdrawal_blocked') and not referrer.get('suspicious_activity'):
                        earnings_count += 1
                except Exception as e:
                    logger.error(f"Error processing search earning: {e}")
                    continue

            self.log_system_event('daily_earnings', f"Processed {earnings_count} search earnings")
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
            self.add_live_activity('bonus', user_id, self.config.CHANNEL_JOIN_BONUS, f"joined channel +₹{self.config.CHANNEL_JOIN_BONUS}")
            return True
        except Exception as e:
            logger.error(f"Error marking channel join: {e}")
            return False

    # ========== DAILY BONUS — UPDATED: 0.05/day max 0.30 ==========

    def claim_day_bonus(self, user_id, date_str):
        try:
            user_id = int(user_id)
            user = self.get_user(user_id)
            if not user:
                return None
            try:
                claim_date = datetime.fromisoformat(date_str).date()
            except:
                return None
            today = datetime.now().date()
            if claim_date != today:
                return None
            existing = self.daily_bonus.find_one({'user_id': user_id, 'date': date_str})
            if existing:
                return None

            streak = user.get('daily_streak', 0)
            last_daily = user.get('last_daily')

            # Streak breaks if yesterday not claimed
            if last_daily:
                try:
                    last_date = datetime.fromisoformat(last_daily).date()
                    yesterday = today - timedelta(days=1)
                    if last_date < yesterday:
                        streak = 0
                        self.users.update_one({'user_id': user_id}, {'$set': {'daily_streak': 0}})
                except:
                    streak = 0

            base_bonus = self.config.DAILY_BONUS  # 0.05
            # UPDATED: 0.05 per day of streak, max 0.30
            streak_bonus = min(streak * 0.05, 0.30)
            total_bonus = base_bonus + streak_bonus

            self.add_balance(user_id, total_bonus, f"Daily bonus for {date_str}")

            self.daily_bonus.insert_one({
                'user_id': user_id,
                'date': date_str,
                'bonus': total_bonus,
                'streak': streak + 1,
                'timestamp': datetime.now().isoformat()
            })
            new_streak = streak + 1
            self.users.update_one({'user_id': user_id}, {'$set': {'daily_streak': new_streak, 'last_daily': date_str}})

            self._update_single_mission_progress(user_id, 'm_daily', 1)
            self.add_live_activity('bonus', user_id, total_bonus, f"claimed daily bonus streak:{new_streak}🔥")
            self.user_cache.pop(f"user_{user_id}", None)
            return {'bonus': total_bonus, 'streak': new_streak, 'success': True, 'passes_added': 0}
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

    MISSIONS_DEF = [
        {'id': 'm_refer5',      'total': 5,  'reward': 2.0,  'track': 'active_refs'},
        {'id': 'm_search5',     'total': 5,  'reward': 1.0,  'track': 'daily_search'},
        {'id': 'm_self_search', 'total': 1,  'reward': 0.50, 'track': 'self_search'},
        {'id': 'm_shortlink',   'total': 1,  'reward': 1.0,  'track': 'shortlink'},
        {'id': 'm_game',        'total': 10, 'reward': 1.0,  'track': 'game_plays'},
        {'id': 'm_game5win',    'total': 5,  'reward': 1.5,  'track': 'game_wins'},
        {'id': 'm_passes',      'total': 1,  'reward': 1.0,  'track': 'pass_purchase'},
        {'id': 'm_daily',       'total': 1,  'reward': 0.10, 'track': 'daily_bonus'},
        {'id': 'm_streak3',     'total': 3,  'reward': 1.0,  'track': 'streak'},
        {'id': 'm_withdraw',    'total': 1,  'reward': 1.0,  'track': 'withdraw'},
    ]

    def get_user_missions(self, user_id):
        try:
            user_id = int(user_id)
            today = datetime.now().date().isoformat()
            result = {}
            user = self.get_user(user_id)

            for mdef in self.MISSIONS_DEF:
                mid = mdef['id']
                doc = self.missions.find_one({'user_id': user_id, 'date': today, 'mission_id': mid})
                if not doc:
                    progress = 0
                    if mid == 'm_refer5' and user:
                        progress = min(user.get('active_refs', 0), mdef['total'])
                    elif mid == 'm_daily':
                        bonus_today = self.daily_bonus.find_one({'user_id': user_id, 'date': today})
                        progress = 1 if bonus_today else 0

                    doc = {
                        'user_id': user_id,
                        'date': today,
                        'mission_id': mid,
                        'progress': progress,
                        'completed': progress >= mdef['total'],
                        'claimed': False
                    }
                    try:
                        self.missions.insert_one(doc)
                    except:
                        pass

                result[mid] = {
                    'progress': doc.get('progress', 0),
                    'completed': doc.get('completed', False),
                    'claimed': doc.get('claimed', False),
                    'claimed_date': doc.get('claimed_date', '')  # frontend uses this to verify TODAY
                }
            return result
        except Exception as e:
            logger.error(f"Error getting missions: {e}")
            return {}

    def _update_single_mission_progress(self, user_id, mission_id, count=1):
        try:
            user_id = int(user_id)
            today = datetime.now().date().isoformat()
            mdef = next((m for m in self.MISSIONS_DEF if m['id'] == mission_id), None)
            if not mdef:
                return

            doc = self.missions.find_one({'user_id': user_id, 'date': today, 'mission_id': mission_id})
            if not doc:
                doc = {'user_id': user_id, 'date': today, 'mission_id': mission_id, 'progress': 0, 'completed': False, 'claimed': False}

            if doc.get('claimed'):
                return

            new_progress = min(doc.get('progress', 0) + count, mdef['total'])
            completed = new_progress >= mdef['total']

            self.missions.update_one(
                {'user_id': user_id, 'date': today, 'mission_id': mission_id},
                {'$set': {'progress': new_progress, 'completed': completed}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error updating mission {mission_id}: {e}")

    def claim_single_mission(self, user_id, mission_id, reward, client_date=None):
        try:
            user_id = int(user_id)
            from datetime import timezone, timedelta as _td
            _ist = datetime.now(timezone.utc) + _td(hours=5, minutes=30)
            ist_today = _ist.date().isoformat()
            server_today = datetime.now().date().isoformat()
            today = client_date if client_date in [ist_today, server_today] else ist_today

            mdef = next((m for m in self.MISSIONS_DEF if m['id'] == mission_id), None)
            if not mdef:
                return {'success': False, 'message': 'Mission not found'}

            # ── STEP 1: Check already claimed (fast exit) ──────────────
            doc = self.missions.find_one({
                'user_id': user_id, 'date': today, 'mission_id': mission_id
            })
            if doc and doc.get('claimed'):
                return {'success': False, 'message': 'Already claimed'}

            # ── STEP 2: Verify mission is actually completed ────────────
            completed = doc.get('completed', False) if doc else False
            progress  = doc.get('progress', 0)      if doc else 0

            if not completed or progress < mdef['total']:
                user = self.get_user(user_id)
                if mission_id == 'm_refer5' and user:
                    completed = user.get('active_refs', 0) >= mdef['total']
                    progress  = min(user.get('active_refs', 0), mdef['total'])
                elif mission_id == 'm_daily':
                    bonus_today = self.daily_bonus.find_one({'user_id': user_id, 'date': today})
                    completed   = bool(bonus_today)
                    progress    = 1 if bonus_today else 0
                elif mission_id == 'm_game':
                    state     = self.game_states.find_one({'user_id': user_id, 'date': today})
                    plays     = (state.get('wins', 0) if state else 0) + (state.get('plays', 0) if state else 0)
                    progress  = min(plays, mdef['total'])
                    completed = progress >= mdef['total']
                elif mission_id == 'm_self_search':
                    completed = bool(user and user.get('last_self_search', '')[:10] == today)
                    progress  = 1 if completed else 0
                elif mission_id == 'm_streak3' and user:
                    streak    = user.get('daily_streak', 0)
                    progress  = min(streak, mdef['total'])
                    completed = streak >= mdef['total']
                elif mission_id == 'm_game5win' and user:
                    wins      = user.get('games_won', 0)
                    progress  = min(wins, mdef['total'])
                    completed = wins >= mdef['total']
                elif mission_id == 'm_withdraw':
                    wd        = self.withdrawals.find_one({'user_id': user_id, 'request_date': {'$gte': today}})
                    completed = bool(wd); progress = 1 if wd else 0
                elif mission_id == 'm_passes':
                    cl        = self.daily_claims.find_one({'user_id': user_id, 'claimed_at': {'$gte': today}})
                    completed = bool(cl); progress = 1 if cl else 0
                else:
                    completed = progress >= mdef['total']

            if not completed:
                return {'success': False, 'message': 'Mission abhi puri nahi hui — pehle complete karo!'}

            # ── STEP 3: Safe upsert using update_one (no unique conflict) ─
            update_result = self.missions.update_one(
                {
                    'user_id':    user_id,
                    'date':       today,
                    'mission_id': mission_id,
                    'claimed':    {'$ne': True}  # only update if NOT already claimed
                },
                {
                    '$set': {
                        'claimed':      True,
                        'completed':    True,
                        'progress':     progress,
                        'reward_given': float(reward),
                        'claimed_date': today,
                        'user_id':      user_id,
                        'date':         today,
                        'mission_id':   mission_id,
                    }
                },
                upsert=True
            )

            # If matched_count==0 and upserted_id==None → already claimed by race condition
            if update_result.matched_count == 0 and update_result.upserted_id is None:
                return {'success': False, 'message': 'Already claimed'}

            # ── STEP 4: Credit balance ────────────────────────────────
            self.add_balance(user_id, float(reward), f"Mission {mission_id} reward")
            self.add_live_activity('mission', user_id, reward, f"Mission complete! +{int(float(reward)*100)} pts")
            logger.info(f"✅ Mission claimed: user={user_id} {mission_id} +₹{reward}")
            return {'success': True, 'reward': float(reward)}

        except Exception as e:
            err = str(e)
            if 'duplicate' in err.lower() or 'E11000' in err:
                # Race condition — already claimed by another request, silently accept
                return {'success': False, 'message': 'Already claimed'}
            logger.error(f"Mission claim error {mission_id}: {e}")
            return {'success': False, 'message': 'Try again'}

    # ========== ADS — UPDATED: timer_seconds field ==========

    def get_all_ads(self):
        try:
            ads = list(self.ads.find().sort('order', 1))
            for ad in ads:
                ad['_id'] = str(ad['_id'])
            return ads
        except Exception as e:
            logger.error(f"Error getting ads: {e}")
            return []

    def update_ad(self, ad_id, title, reward, link, meta, icon=None, claim_code=None, timer_seconds=0, image_url=None, description=None):
        """
        UPDATED: saves timer_seconds, image_url, description.
        Resets all claims so users can claim again after edit.
        """
        try:
            update_data = {
                'title': title,
                'reward': float(reward),
                'link': link,
                'meta': meta,
                'edited_at': datetime.now().isoformat(),
                'claim_code': claim_code.upper() if claim_code else None,
                'timer_seconds': int(timer_seconds) if timer_seconds else 0,
                'image_url': image_url or '',
                'description': description or ''
            }
            if icon:
                update_data['icon'] = icon
            self.ads.update_one({'id': int(ad_id)}, {'$set': update_data}, upsert=True)
            self.reset_ad_claims(ad_id)
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

    def get_user_claimed_ads(self, user_id):
        try:
            user_id = int(user_id)
            claims = list(self.daily_claims.find({'user_id': user_id}, {'ad_id': 1, '_id': 0}))
            return [c['ad_id'] for c in claims]
        except Exception as e:
            logger.error(f"Error getting claimed ads: {e}")
            return []

    def claim_ad(self, user_id, ad_id, reward):
        try:
            user_id = int(user_id)
            existing = self.daily_claims.find_one({'user_id': user_id, 'ad_id': ad_id})
            if existing:
                return False
            ad = self.ads.find_one({'id': int(ad_id)})
            if not ad:
                return False
            self.add_balance(user_id, float(reward), f"Ad reward #{ad_id}")
            self.add_passes(user_id, 1, f"Ad #{ad_id} bonus pass")
            self.daily_claims.insert_one({
                'user_id': user_id,
                'ad_id': ad_id,
                'reward': float(reward),
                'claimed_at': datetime.now().isoformat()
            })
            self._update_single_mission_progress(user_id, 'm_passes', 1)
            self.add_live_activity('bonus', user_id, reward, f"claimed offer reward ₹{reward} +1Pass")
            return True
        except Exception as e:
            logger.error(f"Error claiming ad: {e}")
            return False

    def reset_ad_claims(self, ad_id):
        try:
            self.daily_claims.delete_many({'ad_id': ad_id})
            logger.info(f"Reset claims for ad {ad_id}")
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
            today = datetime.now().date().isoformat()
            # Reset today_earned if it's a new day
            user = self.users.find_one({'user_id': user_id}, {'today_date': 1, 'today_earned': 1})
            if user and user.get('today_date') != today:
                # New day — reset today_earned
                self.users.update_one(
                    {'user_id': user_id},
                    {'$set': {'today_earned': amount, 'today_date': today},
                     '$inc': {'balance': amount, 'total_earned': amount}}
                )
            else:
                self.users.update_one(
                    {'user_id': user_id},
                    {'$inc': {'balance': amount, 'total_earned': amount, 'today_earned': amount},
                     '$set': {'today_date': today}}
                )
            self.add_transaction(user_id, 'credit', amount, description)
            self.user_cache.pop(f"user_{user_id}", None)
            return True
        except Exception as e:
            logger.error(f"Error adding balance: {e}")
            return False

    # ========== WITHDRAWAL — UPDATED: min ₹20, check month refs ==========

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
            # UPDATED: minimum ₹20
            if amount < self.config.MIN_WITHDRAWAL:
                return {'success': False, 'message': f'Minimum withdrawal is ₹{self.config.MIN_WITHDRAWAL}'}
            # UPDATED: check 20 month active refs
            month_refs = self.get_month_active_refs(user_id)
            if month_refs < 20:
                return {'success': False, 'message': f'Is mahine sirf {month_refs}/20 active refs hain. 20 chahiye!'}
            pending = self.withdrawals.find_one({'user_id': user_id, 'status': 'pending'})
            if pending:
                return {'success': False, 'message': 'You already have a pending withdrawal'}
            self.users.update_one({'user_id': user_id}, {'$inc': {'balance': -amount}})
            now = datetime.now().isoformat()
            withdrawal = {
                'user_id': user_id, 'amount': amount, 'method': method, 'details': details,
                'status': 'pending', 'request_date': now, 'processed_date': None,
                'user_name': user.get('first_name', ''), 'username': user.get('username', ''),
                'active_refs': user.get('active_refs', 0), 'month_active_refs': month_refs
            }
            result = self.withdrawals.insert_one(withdrawal)
            self.add_transaction(user_id, 'withdrawal_request', -amount, f"Withdrawal #{str(result.inserted_id)[-6:]}")
            self.add_live_activity('withdraw_request', user_id, amount, f"requested withdrawal ₹{amount}")
            self._update_single_mission_progress(user_id, 'm_withdraw', 1)
            self.user_cache.pop(f"user_{user_id}", None)
            return {'success': True, 'message': 'Withdrawal request submitted!', 'id': str(result.inserted_id)}
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
            self.withdrawals.update_one(
                {'_id': ObjectId(withdrawal_id)},
                {'$set': {'status': 'completed', 'processed_date': datetime.now().isoformat(), 'admin_id': int(admin_id)}}
            )
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
            self.withdrawals.update_one(
                {'_id': ObjectId(withdrawal_id)},
                {'$set': {'status': 'rejected', 'processed_date': datetime.now().isoformat(), 'admin_id': int(admin_id)}}
            )
            self.add_balance(withdrawal['user_id'], withdrawal['amount'], "Refund for rejected withdrawal")
            return True
        except Exception as e:
            logger.error(f"Error rejecting withdrawal: {e}")
            return False

    # ========== TRANSACTIONS ==========

    def add_transaction(self, user_id, type_, amount, description=""):
        try:
            user_id = int(user_id)
            self.transactions.insert_one({
                'user_id': user_id, 'type': type_,
                'amount': float(amount), 'description': description,
                'timestamp': datetime.now().isoformat(), 'status': 'completed'
            })
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

    def get_leaderboard(self, limit=20, mode='weekly'):
        """
        Weekly = refs activated THIS week (Mon-Sun)
        Monthly = refs activated THIS month
        Both are fresh — no overlap with previous periods
        """
        try:
            now = datetime.now()

            if mode == 'weekly':
                # Monday of this week
                days_since_monday = now.weekday()
                week_start = (now - timedelta(days=days_since_monday)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                ).isoformat()
                date_filter = week_start
                label = 'weekly'
            else:
                # First day of this month
                month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
                date_filter = month_start
                label = 'monthly'

            # Count refs activated in this period per user
            pipeline = [
                {'$match': {
                    'is_active': True,
                    'activation_date': {'$gte': date_filter}
                }},
                {'$group': {
                    '_id': '$referrer_id',
                    'period_refs': {'$sum': 1}
                }},
                {'$sort': {'period_refs': -1}},
                {'$limit': limit}
            ]

            period_data = list(self.referrals.aggregate(pipeline))

            result = []
            for i, item in enumerate(period_data):
                uid = item['_id']
                user = self.get_user(uid)
                if not user:
                    continue
                result.append({
                    'rank': i + 1,
                    'name': user.get('first_name', 'User')[:15],
                    'active_refs': item['period_refs'],  # THIS period's refs
                    'total_active': user.get('active_refs', 0),  # all-time
                    'pending_refs': user.get('pending_refs', 0),
                    'total_earned': user.get('total_earned', 0),
                    'period': label
                })

            # If no period data yet, fall back to all-time active refs
            if not result:
                users = self.users.find(
                    {'suspicious_activity': False},
                    {'user_id': 1, 'first_name': 1, 'active_refs': 1, 'pending_refs': 1}
                ).sort('active_refs', -1).limit(limit)
                for i, user in enumerate(users):
                    result.append({
                        'rank': i + 1,
                        'name': user.get('first_name', 'User')[:15],
                        'active_refs': user.get('active_refs', 0),
                        'total_active': user.get('active_refs', 0),
                        'pending_refs': user.get('pending_refs', 0),
                        'total_earned': user.get('total_earned', 0),
                        'period': label
                    })

            return result

        except Exception as e:
            logger.error(f"Leaderboard error: {e}")
            return []

    # ========== GAME FUNCTIONS ==========

    # SPIN: segments must match frontend SEGS array exactly (same index)
    # Frontend SEGS: [0.10, 0.50, 0.10, 1.0, 0.50, 0.10, 2.0, 0.10]
    SPIN_SEGMENTS = [
        {'label': '₹0.10', 'value': 0.10},   # index 0
        {'label': '₹0.50', 'value': 0.50},   # index 1
        {'label': '₹0.10', 'value': 0.10},   # index 2
        {'label': '₹1',    'value': 1.0},    # index 3
        {'label': '₹0.50', 'value': 0.50},   # index 4
        {'label': '₹0.10', 'value': 0.10},   # index 5
        {'label': '₹2',    'value': 2.0},    # index 6
        {'label': '₹0.10', 'value': 0.10},   # index 7
    ]
    # FIXED Weights — realistic feel, not spammy 0.10
    # 0.10 = 40% (4 segs × 5), 0.50 = 30% (2 × 15), 1.0 = 20% (1 × 20), 2.0 = 10% (1 × 10)
    # Total = 20+15+20+15+10+20+10+20 = 130
    SPIN_WEIGHTS = [5, 15, 5, 20, 15, 5, 10, 5]
    # Actual probabilities:
    # ₹0.10 (indices 0,2,5,7) = (5+5+5+5)/80 = 20/80 = 25%
    # ₹0.50 (indices 1,4)     = (15+15)/80   = 30/80 = 37.5%
    # ₹1.0  (index 3)         = 20/80        = 25%
    # ₹2.0  (index 6)         = 10/80        = 12.5%
    # Expected value per spin = 0.10*0.25 + 0.50*0.375 + 1.0*0.25 + 2.0*0.125
    #                         = 0.025 + 0.1875 + 0.25 + 0.25 = 0.7125
    # Pass costs ~₹0.10 equivalent, house edge maintained through pass system

    def get_game_state(self, user_id, date=None):
        try:
            user_id = int(user_id)
            if not date:
                date = datetime.now().date().isoformat()
            state = self.game_states.find_one({'user_id': user_id, 'date': date})
            if not state:
                state = {
                    'user_id': user_id, 'date': date,
                    'today_game_earned': 0.0, 'wins': 0, 'win_streak': 0,
                    'guess_secret': random.randint(1, 10), 'guess_attempts_used': 0
                }
                self.game_states.insert_one(state)
            if '_id' in state:
                state['_id'] = str(state['_id'])
            return state
        except Exception as e:
            logger.error(f"Error getting game state: {e}")
            return {'today_game_earned': 0.0, 'wins': 0, 'win_streak': 0}

    def add_game_earning(self, user_id, amount, game_type='game', description='Game reward'):
        try:
            user_id = int(user_id)
            amount = float(amount)
            today = datetime.now().date().isoformat()
            # Daily cap — prevent abuse
            state = self.get_game_state(user_id, today)
            day_earned = state.get('today_game_earned', 0.0)
            cap = getattr(self, 'MAX_DAILY_GAME_EARN', 3.0)
            amount = round(min(amount, max(0.0, cap - day_earned)), 4)
            if amount <= 0:
                return {'success': True, 'earned': 0, 'capped': True}
            self.add_balance(user_id, amount, description)

            state = self.get_game_state(user_id, today)
            new_earned = state.get('today_game_earned', 0.0) + amount
            self.game_states.update_one(
                {'user_id': user_id, 'date': today},
                {'$set': {'today_game_earned': new_earned}, '$inc': {'wins': 1}},
                upsert=True
            )
            self.users.update_one(
                {'user_id': user_id},
                {'$inc': {'games_won': 1, 'total_game_earned': amount}}
            )
            self.user_cache.pop(f"user_{user_id}", None)
            self.add_live_activity('game', user_id, amount, f"won ₹{amount:.2f} in {game_type}")
            self._update_single_mission_progress(user_id, 'm_game', 1)

            return {'success': True, 'earned': amount, 'today_total': new_earned}
        except Exception as e:
            logger.error(f"Error adding game earning: {e}")
            return {'success': False, 'message': str(e), 'earned': 0}

    def deduct_game_balance(self, user_id, amount, game_type='game'):
        try:
            user_id = int(user_id)
            amount = float(amount)
            user = self.get_user(user_id)
            if not user:
                return {'success': False, 'message': 'User not found'}
            if user.get('balance', 0) < amount:
                return {'success': False, 'message': f'Balance kam hai! ₹{user.get("balance", 0):.2f} hai'}
            self.users.update_one({'user_id': user_id}, {'$inc': {'balance': -amount}})
            self.add_transaction(user_id, 'game_bet', -amount, f"Game bet in {game_type}")
            self.user_cache.pop(f"user_{user_id}", None)
            return {'success': True, 'deducted': amount}
        except Exception as e:
            logger.error(f"Error deducting game balance: {e}")
            return {'success': False, 'message': str(e)}

    def process_game_spin(self, user_id):
        """
        Spin — costs 1 pass.
        Returns segment_index so frontend wheel stops at exact correct segment.
        SEGS in frontend and SPIN_SEGMENTS here must be in same order.
        """
        try:
            user_id = int(user_id)
            user = self.get_user(user_id)
            if not user or user.get('passes', 0) <= 0:
                return {'success': False, 'message': 'Passes nahi hain! Refer karo ya daily bonus lo'}

            if not self.deduct_pass(user_id):
                return {'success': False, 'message': 'Pass deduct nahi hua'}

            weights = self.SPIN_WEIGHTS
            total_w = sum(weights)
            r = random.random() * total_w
            selected = len(weights) - 1
            for i, w in enumerate(weights):
                r -= w
                if r <= 0:
                    selected = i
                    break

            reward = self.SPIN_SEGMENTS[selected]['value']
            reward_label = self.SPIN_SEGMENTS[selected]['label']

            earn_result = self.add_game_earning(user_id, reward, 'spin', f"Spin reward {reward_label}")

            return {
                'success': True,
                'reward': earn_result.get('earned', reward),
                'reward_label': reward_label,
                'segment_index': selected,   # Frontend uses this to stop wheel
                'today_earned': earn_result.get('today_total', 0)
            }
        except Exception as e:
            logger.error(f"Error processing spin: {e}")
            return {'success': False, 'message': str(e)}

    def process_game_guess(self, user_id, guess, bet):
        """Number guess — costs 1 pass."""
        try:
            user_id = int(user_id)
            today = datetime.now().date().isoformat()
            state = self.get_game_state(user_id, today)

            user = self.get_user(user_id)
            if not user or user.get('passes', 0) <= 0:
                return {'success': False, 'message': 'Passes nahi hain!'}

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
                'attempts_used': attempts_used, 'guess': guess, 'reward': 0
            }

            if is_correct:
                reward = bet * 8
                earn_result = self.add_game_earning(user_id, reward, 'guess', "Guess correct! x8")
                result['reward'] = earn_result.get('earned', 0)
                result['today_earned'] = earn_result.get('today_total', 0)
                self.deduct_pass(user_id)
                self.game_states.update_one(
                    {'user_id': user_id, 'date': today},
                    {'$set': {'guess_secret': random.randint(1, 10), 'guess_attempts_used': 0}}
                )
            elif is_last_attempt:
                self.deduct_pass(user_id)
                self.game_states.update_one(
                    {'user_id': user_id, 'date': today},
                    {'$set': {'guess_secret': random.randint(1, 10), 'guess_attempts_used': 0}}
                )
            else:
                diff = abs(guess - secret)
                if diff <= 1: hint = '🔥 Bahut paas!'
                elif diff <= 3: hint = '♨️ Kaafi paas'
                elif diff <= 5: hint = '🌡️ Thoda door'
                else: hint = '❄️ Bahut door!'
                hint += ' (Kam karo)' if guess > secret else ' (Zyada karo)'
                result['hint'] = hint
                self.game_states.update_one({'user_id': user_id, 'date': today}, {'$set': {'guess_attempts_used': attempts_used}})

            return result
        except Exception as e:
            logger.error(f"Error processing guess: {e}")
            return {'success': False, 'message': str(e)}

    def process_game_coin(self, user_id, choice, bet):
        """Coin flip — costs 1 pass."""
        try:
            user_id = int(user_id)
            user = self.get_user(user_id)
            if not user or user.get('passes', 0) <= 0:
                return {'success': False, 'message': 'Passes nahi hain!'}

            deduct_result = self.deduct_game_balance(user_id, bet, 'coin')
            if not deduct_result.get('success'):
                return deduct_result

            self.deduct_pass(user_id)

            actual_result = 'heads' if random.random() < 0.5 else 'tails'
            won = (choice == actual_result)

            result = {'success': True, 'won': won, 'result': actual_result, 'choice': choice, 'bet': bet, 'reward': 0}

            if won:
                reward = bet * 2
                earn_result = self.add_game_earning(user_id, reward, 'coin', f"Coin flip win ₹{reward}")
                result['reward'] = earn_result.get('earned', 0)
                result['today_earned'] = earn_result.get('today_total', 0)

            return result
        except Exception as e:
            logger.error(f"Error processing coin flip: {e}")
            return {'success': False, 'message': str(e)}

    # ========== NEW: DICE GAME ==========

    def process_game_dice(self, user_id, choice):
        """
        Dice Roll game.
        - User picks number 1-6.
        - Costs 1 Pass.
        - Win: ₹0.50 if correct number comes.
        - House edge: 60% of matching rolls are forced to lose.
        - Effective win rate: ~6.7% per roll (1/6 * 40%).
        """
        try:
            user_id = int(user_id)

            if not 1 <= choice <= 6:
                return {'success': False, 'message': 'Choice must be 1-6'}

            user = self.get_user(user_id)
            if not user or user.get('passes', 0) <= 0:
                return {'success': False, 'message': 'Passes nahi hain! Refer karo ya daily bonus lo'}

            if not self.deduct_pass(user_id):
                return {'success': False, 'message': 'Pass deduct nahi hua'}

            # Roll dice
            actual_number = random.randint(1, 6)
            matched = (actual_number == choice)

            # House edge: even if matched, 60% chance of forced loss
            if matched:
                won = random.random() >= 0.60  # 40% of matches actually win
            else:
                won = False

            result = {
                'success': True,
                'won': won,
                'actual_number': actual_number,
                'choice': choice,
                'reward': 0
            }

            if won:
                reward = 0.50
                earn_result = self.add_game_earning(user_id, reward, 'dice', f"Dice roll win! {choice} aaya")
                result['reward'] = earn_result.get('earned', reward)
                result['today_earned'] = earn_result.get('today_total', 0)

            logger.info(f"Dice: user={user_id} choice={choice} actual={actual_number} matched={matched} won={won}")
            return result

        except Exception as e:
            logger.error(f"Error processing dice: {e}")
            return {'success': False, 'message': str(e)}

    def process_game_scratch(self, user_id):
        """
        Scratch card — costs 1 pass.
        Rewards: 0.10=60%, 0.50=25%, 1=10%, 2=4%, 5=1%
        """
        try:
            user_id = int(user_id)
            user = self.get_user(user_id)
            if not user or user.get('passes', 0) <= 0:
                return {'success': False, 'message': 'Passes nahi hain!'}

            if not self.deduct_pass(user_id):
                return {'success': False, 'message': 'Pass deduct nahi hua'}

            roll = random.random()
            if roll < 0.60:
                reward = 0.10
            elif roll < 0.85:
                reward = 0.50
            elif roll < 0.95:
                reward = 1.0
            elif roll < 0.99:
                reward = 2.0
            else:
                reward = 5.0

            earn_result = self.add_game_earning(user_id, reward, 'scratch', f"Scratch card ₹{reward}")

            return {
                'success': True,
                'reward': earn_result.get('earned', reward),
                'today_earned': earn_result.get('today_total', 0)
            }
        except Exception as e:
            logger.error(f"Error processing scratch: {e}")
            return {'success': False, 'message': str(e)}

    # ========== COLOR PREDICTION GAME ==========

    COLOR_CONFIG = {
        'red':    {'mult': 2,  'prob': 0.30},
        'green':  {'mult': 2,  'prob': 0.28},
        'blue':   {'mult': 2,  'prob': 0.25},
        'yellow': {'mult': 4,  'prob': 0.10},
        'purple': {'mult': 4,  'prob': 0.05},
        'orange': {'mult': 9,  'prob': 0.02},
    }

    def process_game_color(self, user_id, choice, bet):
        """
        Color Prediction. Red/Green/Blue=2x, Yellow/Purple=4x, Orange=9x
        House edge ~40%.
        """
        try:
            user_id = int(user_id)
            bet = float(bet)
            valid_colors = list(self.COLOR_CONFIG.keys())
            if choice not in valid_colors:
                return {'success': False, 'message': 'Invalid color'}
            user = self.get_user(user_id)
            if not user or user.get('passes', 0) <= 0:
                return {'success': False, 'message': 'Passes nahi hain!'}
            deduct_result = self.deduct_game_balance(user_id, bet, 'color')
            if not deduct_result.get('success'):
                return deduct_result
            if not self.deduct_pass(user_id):
                self.add_balance(user_id, bet, "Color refund")
                return {'success': False, 'message': 'Pass deduct nahi hua'}
            # Weighted color pick
            probs = [self.COLOR_CONFIG[c]['prob'] for c in valid_colors]
            total = sum(probs)
            r = random.random() * total
            result_color = valid_colors[-1]
            for i, p in enumerate(probs):
                r -= p
                if r <= 0:
                    result_color = valid_colors[i]
                    break
            won = (choice == result_color)
            result = {'success': True, 'won': won, 'result_color': result_color, 'choice': choice, 'reward': 0}
            if won:
                mult = self.COLOR_CONFIG[result_color]['mult']
                reward = round(bet * mult, 2)
                earn_result = self.add_game_earning(user_id, reward, 'color', f"Color {result_color} {mult}x")
                result['reward'] = earn_result.get('earned', reward)
                result['multiplier'] = mult
                result['today_earned'] = earn_result.get('today_total', 0)
            return result
        except Exception as e:
            logger.error(f"Color game error: {e}")
            return {'success': False, 'message': str(e)}

    def process_crash_start(self, user_id, bet):
        """Crash game — deduct pass AND bet amount from balance."""
        try:
            user_id = int(user_id)
            bet = float(bet)
            user = self.get_user(user_id)
            if not user or user.get('passes', 0) <= 0:
                return {'success': False, 'message': 'Passes nahi hain!'}
            if user.get('balance', 0) < bet:
                return {'success': False, 'message': f'Balance kam hai! ₹{user.get("balance",0):.2f} hai'}
            # Deduct pass
            if not self.deduct_pass(user_id):
                return {'success': False, 'message': 'Pass deduct nahi hua'}
            # Deduct bet from balance
            self.users.update_one({'user_id': user_id}, {'$inc': {'balance': -bet}})
            self.add_transaction(user_id, 'game_bet', -bet, f"Crash game bet ₹{bet}")
            self.user_cache.pop(f"user_{user_id}", None)
            return {'success': True}
        except Exception as e:
            logger.error(f"Crash start error: {e}")
            return {'success': False, 'message': str(e)}

    def process_crash_cashout(self, user_id, bet, multiplier, reward):
        """Crash cashout — credit winnings."""
        try:
            user_id = int(user_id)
            bet = float(bet)
            multiplier = float(multiplier)
            reward = float(reward)
            if multiplier < 1.0:
                return {'success': False, 'message': 'Invalid multiplier'}
            if reward > bet * 10.5:
                reward = round(bet * 10, 2)
            earn_result = self.add_game_earning(user_id, reward, 'crash', f"Crash cashout {multiplier}x")
            return {'success': True, 'reward': earn_result.get('earned', reward), 'multiplier': multiplier}
        except Exception as e:
            logger.error(f"Crash cashout error: {e}")
            return {'success': False, 'message': str(e)}

    # ========== RUNNER GAME ==========

    RUNNER_MODES = {
        '10s':  {'seconds': 10,  'reward_per_sec': 0.005, 'label': '10 Seconds'},
        '30s':  {'seconds': 30,  'reward_per_sec': 0.004, 'label': '30 Seconds'},
        '1m':   {'seconds': 60,  'reward_per_sec': 0.003, 'label': '1 Minute'},
        '5m':   {'seconds': 300, 'reward_per_sec': 0.002, 'label': '5 Minutes'},
        '10m':  {'seconds': 600, 'reward_per_sec': 0.0015,'label': '10 Minutes'},
        # Skill games
        'maze':       {'seconds': 120, 'reward_per_sec': 0.003, 'label': 'Sokoban',       'max_reward': 0.25},
        'snake':      {'seconds': 60,  'reward_per_sec': 0.003, 'label': 'Snake Game',    'max_reward': 0.20},
        'chess':      {'seconds': 60,  'reward_per_sec': 0.003, 'label': 'Chess',         'max_reward': 0.20},
        'blockblast': {'seconds': 120, 'reward_per_sec': 0.002, 'label': 'Block Blast',   'max_reward': 0.15},
        'gemmatch':   {'seconds': 120, 'reward_per_sec': 0.002, 'label': 'Gem Match',     'max_reward': 0.15},
    }
    MAX_DAILY_GAME_EARN = 3.0

    def runner_start(self, user_id, mode, bet):
        """Start runner game — deduct pass + bet."""
        try:
            user_id = int(user_id)
            bet = float(bet)
            if mode not in self.RUNNER_MODES:
                return {'success': False, 'message': 'Invalid mode'}
            user = self.get_user(user_id)
            if not user:
                return {'success': False, 'message': 'User not found'}
            if user.get('passes', 0) <= 0:
                return {'success': False, 'message': 'Passes nahi hain!'}
            if user.get('balance', 0) < bet:
                return {'success': False, 'message': f'Balance kam hai! ₹{user.get("balance",0):.2f}'}
            # Deduct pass + bet
            if not self.deduct_pass(user_id):
                return {'success': False, 'message': 'Pass deduct nahi hua'}
            self.users.update_one({'user_id': user_id}, {'$inc': {'balance': -bet}})
            self.add_transaction(user_id, 'game_bet', -bet, f"Runner game bet ₹{bet} ({mode})")
            self.user_cache.pop(f"user_{user_id}", None)
            mode_info = self.RUNNER_MODES[mode]
            max_reward = round(bet + (mode_info['seconds'] * mode_info['reward_per_sec']), 2)
            return {
                'success': True,
                'mode': mode,
                'seconds': mode_info['seconds'],
                'reward_per_sec': mode_info['reward_per_sec'],
                'bet': bet,
                'max_reward': max_reward
            }
        except Exception as e:
            logger.error(f"Runner start error: {e}")
            return {'success': False, 'message': str(e)}

    def runner_finish(self, user_id, mode, bet, survived_seconds):
        """Finish runner — credit reward based on survived time."""
        try:
            user_id = int(user_id)
            bet = float(bet)
            survived_seconds = int(survived_seconds)
            if mode not in self.RUNNER_MODES:
                return {'success': False, 'message': 'Invalid mode'}
            mode_info = self.RUNNER_MODES[mode]
            total_seconds = mode_info['seconds']
            reward_per_sec = mode_info['reward_per_sec']
            # Calculate reward: bet back + earnings per second survived
            if survived_seconds <= 0:
                return {'success': True, 'reward': 0, 'survived': 0, 'message': 'Game over! Kuch nahi mila.'}
            survived_pct = survived_seconds / total_seconds
            # Bet refund based on % survived
            bet_back = round(bet * survived_pct, 2)
            # Per second earning
            earned = round(survived_seconds * reward_per_sec, 4)
            total_reward = round(bet_back + earned, 2)
            # Cap at max possible (per-mode cap + anti-cheat)
            max_reward = round(bet + (total_seconds * reward_per_sec), 2)
            mode_cap = mode_info.get('max_reward', max_reward)
            total_reward = min(total_reward, max_reward, mode_cap)
            if total_reward > 0:
                self.add_game_earning(user_id, total_reward, 'runner',
                    f"Runner {mode} {survived_seconds}s → +₹{total_reward}")
                self.add_live_activity('runner', user_id, total_reward,
                    f"🏃 Runner {mode}: {survived_seconds}s → +₹{total_reward}")
            won = survived_seconds >= total_seconds
            return {
                'success': True,
                'reward': total_reward,
                'survived': survived_seconds,
                'won': won,
                'bet_back': bet_back,
                'earned': earned
            }
        except Exception as e:
            logger.error(f"Runner finish error: {e}")
            return {'success': False, 'message': str(e)}

    # ========== SYSTEM & CLEANUP ==========

    def remove_blocked_users(self, user_ids, progress_callback=None):
        try:
            deleted_count = 0
            failed_count = 0
            for user_id in user_ids:
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
            return deleted_count, failed_count
        except Exception as e:
            logger.error(f"Error removing blocked users: {e}")
            return 0, len(user_ids)

    def log_system_event(self, event_type, description):
        try:
            self.system_stats.insert_one({
                'event_type': event_type,
                'description': description,
                'timestamp': datetime.now().isoformat()
            })
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
