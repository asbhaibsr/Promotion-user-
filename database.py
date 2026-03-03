# ===== database.py =====
import logging
from datetime import datetime, timedelta
import random
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, config):
        self.config = config
        
        try:
            self.client = MongoClient(config.MONGODB_URI)
            self.db = self.client[config.MONGODB_DB]
            
            self.client.admin.command('ping')
            logger.info("✅ MongoDB Connected Successfully!")
            
            # Initialize collections
            self.users = self.db['users']
            self.transactions = self.db['transactions']
            self.withdrawals = self.db['withdrawals']
            self.referrals = self.db['referrals']
            self.issues = self.db['issues']
            self.missions = self.db['missions']
            self.leaderboard_history = self.db['leaderboard_history']
            self.channel_joins = self.db['channel_joins']  # Track channel joins
            self.daily_searches = self.db['daily_searches']  # Track daily searches
            
            # Create indexes
            self.users.create_index('user_id', unique=True)
            self.users.create_index('referrer_id')
            self.referrals.create_index('referred_id', unique=True)
            self.referrals.create_index([('referrer_id', ASCENDING), ('is_active', ASCENDING)])
            self.transactions.create_index('user_id')
            self.withdrawals.create_index('user_id')
            self.withdrawals.create_index('status')
            self.daily_searches.create_index([('user_id', ASCENDING), ('date', ASCENDING)], unique=True)
            self.channel_joins.create_index([('user_id', ASCENDING), ('channel_id', ASCENDING)], unique=True)
            
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
        """Add new user with referral tracking"""
        try:
            existing = self.users.find_one({'user_id': user_data['user_id']})
            if existing:
                self.users.update_one(
                    {'user_id': user_data['user_id']},
                    {'$set': {'last_active': datetime.now().isoformat()}}
                )
                return False
            
            now = datetime.now().isoformat()
            
            new_user = {
                'user_id': user_data['user_id'],
                'first_name': user_data.get('first_name', ''),
                'username': user_data.get('username', ''),
                'referrer_id': user_data.get('referrer_id'),
                'balance': 0.0,
                'total_earned': 0.0,
                'spins': 3,
                'tier': 1,
                'total_refs': 0,
                'active_refs': 0,
                'pending_refs': 1 if user_data.get('referrer_id') else 0,
                'monthly_refs': 0,
                'daily_streak': 0,
                'last_daily': None,
                'channel_joined': False,
                'payment_method': None,
                'payment_details': None,
                'total_searches': 0,
                'weekly_searches': 0,
                'join_date': now,
                'last_active': now,
                'is_admin': user_data['user_id'] in self.config.ADMIN_IDS,
                'mission_progress': {
                    'referrals': 0,
                    'searches': 0,
                    'daily_streak': 0,
                    'current_mission': 1
                }
            }
            
            self.users.insert_one(new_user)
            
            if user_data.get('referrer_id'):
                self.referrals.insert_one({
                    'referrer_id': user_data['referrer_id'],
                    'referred_id': user_data['user_id'],
                    'join_date': now,
                    'last_search': None,
                    'is_active': False,  # Pending until first search
                    'earnings': 0
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
    
    def process_daily_referral_earnings(self):
        """Process daily earnings for active referrals"""
        try:
            today = datetime.now().date().isoformat()
            
            # Get all active referrals
            active_refs = self.referrals.find({'is_active': True})
            
            earnings_count = 0
            for ref in active_refs:
                referrer_id = ref['referrer_id']
                referred_id = ref['referred_id']
                
                # Check if referred user searched today
                today_search = self.daily_searches.find_one({
                    'user_id': referred_id,
                    'date': today
                })
                
                if today_search:
                    # Get referrer's tier and calculate earnings
                    referrer = self.get_user(referrer_id)
                    if referrer:
                        tier_rate = self.config.get_tier_rate(referrer.get('tier', 1))
                        
                        # Add earnings to referrer
                        self.add_balance(
                            referrer_id, 
                            tier_rate, 
                            f"Daily referral earning from user {referred_id}"
                        )
                        
                        # Update referral record
                        self.referrals.update_one(
                            {'_id': ref['_id']},
                            {
                                '$inc': {'earnings': tier_rate},
                                '$set': {'last_earning_date': today}
                            }
                        )
                        
                        earnings_count += 1
            
            logger.info(f"✅ Processed daily earnings for {earnings_count} active referrals")
            return earnings_count
            
        except Exception as e:
            logger.error(f"Error processing daily earnings: {e}")
            return 0
    
    def activate_referral(self, referred_id):
        """Activate referral when user searches first time"""
        try:
            referral = self.referrals.find_one({'referred_id': referred_id})
            
            if referral and not referral.get('is_active'):
                # Mark as active
                self.referrals.update_one(
                    {'referred_id': referred_id},
                    {
                        '$set': {
                            'is_active': True,
                            'first_search_date': datetime.now().isoformat()
                        }
                    }
                )
                
                referrer_id = referral['referrer_id']
                
                # Update referrer counts
                self.users.update_one(
                    {'user_id': referrer_id},
                    {
                        '$inc': {
                            'pending_refs': -1,
                            'active_refs': 1
                        }
                    }
                )
                
                # Give one-time referral bonus to referrer
                self.add_balance(
                    referrer_id,
                    self.config.REFERRAL_BONUS,
                    f"One-time referral bonus for user {referred_id}"
                )
                
                # Also give bonus to the new user
                self.add_balance(
                    referred_id,
                    0.30,  # New user gets ₹0.30 for first search
                    "First search bonus"
                )
                
                # Update tier based on new active count
                self.update_user_tier(referrer_id)
                
                return True
                
        except Exception as e:
            logger.error(f"Error activating referral: {e}")
            return False
    
    def record_search(self, user_id):
        """Record user search in movie group"""
        try:
            today = datetime.now().date().isoformat()
            
            # Record daily search
            self.daily_searches.update_one(
                {'user_id': user_id, 'date': today},
                {'$set': {
                    'user_id': user_id,
                    'date': today,
                    'timestamp': datetime.now().isoformat()
                }},
                upsert=True
            )
            
            # Increment user search count
            self.users.update_one(
                {'user_id': user_id},
                {
                    '$inc': {
                        'total_searches': 1,
                        'weekly_searches': 1
                    },
                    '$set': {'last_active': datetime.now().isoformat()}
                }
            )
            
            # Check if this is first search (activate referral)
            user = self.get_user(user_id)
            if user and user.get('total_searches', 0) == 1:
                self.activate_referral(user_id)
            
            # Update mission progress
            self.update_mission_progress(user_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error recording search: {e}")
            return False
    
    def check_channel_join(self, user_id, channel_id):
        """Check if user joined channel (to be called from bot)"""
        try:
            # This will be verified by Telegram bot API
            join_record = self.channel_joins.find_one({
                'user_id': user_id,
                'channel_id': channel_id
            })
            
            return join_record is not None
            
        except Exception as e:
            logger.error(f"Error checking channel join: {e}")
            return False
    
    def mark_channel_join(self, user_id, channel_id):
        """Mark user as joined channel"""
        try:
            self.channel_joins.insert_one({
                'user_id': user_id,
                'channel_id': channel_id,
                'joined_at': datetime.now().isoformat()
            })
            
            # Add bonus
            channel_bonus = self.config.CHANNELS.get('main', {}).get('bonus', 2.0)
            self.add_balance(user_id, channel_bonus, "Channel join bonus")
            
            self.users.update_one(
                {'user_id': user_id},
                {'$set': {'channel_joined': True}}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error marking channel join: {e}")
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
    
    def update_user_tier(self, user_id):
        """Update user tier based on active referrals"""
        try:
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
                
                self.add_transaction(
                    user_id,
                    'tier_upgrade',
                    0,
                    f"Upgraded to {self.config.get_tier_name(new_tier)}"
                )
                
                return new_tier
            
            return user.get('tier')
            
        except Exception as e:
            logger.error(f"Error updating tier: {e}")
            return None
    
    def claim_daily_bonus(self, user_id):
        """Claim daily bonus with streak"""
        try:
            user = self.get_user(user_id)
            if not user:
                return None
            
            now = datetime.now()
            today = now.date().isoformat()
            
            last_daily = user.get('last_daily')
            if last_daily and last_daily.startswith(today):
                return None
            
            # Calculate streak
            streak = 1
            if last_daily:
                try:
                    last_date = datetime.fromisoformat(last_daily).date()
                    if (now.date() - last_date).days == 1:
                        streak = user.get('daily_streak', 0) + 1
                    elif (now.date() - last_date).days > 1:
                        streak = 1  # Reset streak
                except:
                    streak = 1
            
            # Bonus amount increases with streak
            base_bonus = self.config.DAILY_BONUS
            streak_bonus = min(streak * 0.02, 0.15)
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
            
            # Update mission progress
            self.update_mission_progress(user_id)
            
            return {
                'bonus': total_bonus,
                'streak': streak,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Error claiming daily: {e}")
            return None
    
    def update_mission_progress(self, user_id):
        """Update user mission progress"""
        try:
            user = self.get_user(user_id)
            if not user:
                return
            
            # Get current mission
            current_mission = user.get('mission_progress', {}).get('current_mission', 1)
            mission_config = self.config.MISSIONS.get(current_mission)
            
            if not mission_config:
                return
            
            # Calculate progress
            progress = {
                'referrals': user.get('active_refs', 0),
                'searches': user.get('total_searches', 0),
                'daily_streak': user.get('daily_streak', 0)
            }
            
            # Check if mission completed
            completed = True
            for req_type, required in mission_config['requirements'].items():
                if progress.get(req_type, 0) < required:
                    completed = False
                    break
            
            if completed:
                # Give reward
                reward = mission_config['reward']
                self.add_balance(user_id, reward, f"Mission {current_mission} completed")
                
                # Move to next mission
                self.users.update_one(
                    {'user_id': user_id},
                    {
                        '$set': {
                            f'mission_progress.current_mission': current_mission + 1
                        }
                    }
                )
                
                return True
            
            # Update progress
            self.users.update_one(
                {'user_id': user_id},
                {'$set': {
                    'mission_progress.referrals': progress['referrals'],
                    'mission_progress.searches': progress['searches'],
                    'mission_progress.daily_streak': progress['daily_streak']
                }}
            )
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating mission: {e}")
            return False
    
    def get_leaderboard(self, limit=10):
        """Get weekly leaderboard"""
        try:
            # Get top users by weekly searches
            users = self.users.find(
                {'weekly_searches': {'$gt': 0}},
                {'user_id': 1, 'first_name': 1, 'weekly_searches': 1, 'active_refs': 1}
            ).sort('weekly_searches', -1).limit(limit)
            
            result = []
            for i, user in enumerate(users):
                result.append({
                    'rank': i + 1,
                    'name': user.get('first_name', 'User')[:15],
                    'searches': user.get('weekly_searches', 0),
                    'refs': user.get('active_refs', 0)
                })
            
            return result
        except Exception as e:
            logger.error(f"Leaderboard error: {e}")
            return []
    
    def reset_weekly_leaderboard(self):
        """Reset weekly leaderboard and distribute rewards"""
        try:
            # Get top users
            top_users = list(self.users.find(
                {'weekly_searches': {'$gt': 0}},
                {'user_id': 1, 'first_name': 1, 'weekly_searches': 1, 'active_refs': 1}
            ).sort('weekly_searches', -1).limit(10))
            
            rewards_given = []
            
            # Give rewards based on rank
            for i, user in enumerate(top_users):
                rank = i + 1
                reward_config = None
                
                if rank <= 3:
                    # Check if they have 50+ active refs
                    if user.get('active_refs', 0) >= 50:
                        reward_config = self.config.LEADERBOARD_REWARDS.get(rank)
                elif 4 <= rank <= 10:
                    if user.get('active_refs', 0) >= 25:
                        reward_config = self.config.LEADERBOARD_REWARDS.get('4-10')
                
                if reward_config:
                    self.add_balance(
                        user['user_id'],
                        reward_config['reward'],
                        f"Weekly leaderboard rank #{rank}"
                    )
                    rewards_given.append({
                        'user_id': user['user_id'],
                        'rank': rank,
                        'reward': reward_config['reward']
                    })
            
            # Reset weekly searches
            self.users.update_many(
                {},
                {'$set': {'weekly_searches': 0}}
            )
            
            # Store history
            self.leaderboard_history.insert_one({
                'week_start': (datetime.now() - timedelta(days=7)).isoformat(),
                'week_end': datetime.now().isoformat(),
                'rewards': rewards_given
            })
            
            logger.info(f"✅ Weekly leaderboard reset with {len(rewards_given)} rewards")
            return rewards_given
            
        except Exception as e:
            logger.error(f"Error resetting leaderboard: {e}")
            return []
    
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
                'admin_note': None
            }
            
            result = self.withdrawals.insert_one(withdrawal)
            
            self.add_transaction(
                user_id,
                'withdrawal_request',
                -amount,
                f"Withdrawal request #{str(result.inserted_id)[-6:]} via {method}"
            )
            
            return {
                'success': True, 
                'message': 'Withdrawal request submitted',
                'id': str(result.inserted_id)
            }
            
        except Exception as e:
            logger.error(f"Error processing withdrawal: {e}")
            return {'success': False, 'message': 'Internal error'}
    
    def add_transaction(self, user_id, type_, amount, description=""):
        """Add transaction record"""
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
    
    def add_issue_report(self, user_id, issue):
        """Add user issue report"""
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
    
    def get_user_missions(self, user_id):
        """Get user mission progress"""
        user = self.get_user(user_id)
        if not user:
            return {}
        
        current_mission = user.get('mission_progress', {}).get('current_mission', 1)
        missions = {}
        
        for mission_num, mission_config in self.config.MISSIONS.items():
            if mission_num < current_mission:
                # Completed
                missions[f'mission_{mission_num}'] = {
                    'name': mission_config['name'],
                    'icon': mission_config['name'].split()[0],
                    'completed': True,
                    'reward': mission_config['reward']
                }
            elif mission_num == current_mission:
                # Current
                progress = user.get('mission_progress', {})
                missions[f'mission_{mission_num}'] = {
                    'name': mission_config['name'],
                    'icon': mission_config['name'].split()[0],
                    'progress': {
                        'referrals': f"{progress.get('referrals', 0)}/{mission_config['requirements']['referrals']}",
                        'searches': f"{progress.get('searches', 0)}/{mission_config['requirements']['searches']}",
                        'streak': f"{progress.get('daily_streak', 0)}/{mission_config['requirements']['daily_streak']}"
                    },
                    'reward': mission_config['reward'],
                    'completed': False
                }
            else:
                # Locked
                missions[f'mission_{mission_num}'] = {
                    'name': mission_config['name'],
                    'icon': '🔒',
                    'locked': True,
                    'reward': mission_config['reward']
                }
        
        return missions
    
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
    
    def update_withdrawal_status(self, withdrawal_id, status, note=None):
        """Update withdrawal status"""
        try:
            from bson.objectid import ObjectId
            self.withdrawals.update_one(
                {'_id': ObjectId(withdrawal_id)},
                {
                    '$set': {
                        'status': status,
                        'processed_date': datetime.now().isoformat(),
                        'admin_note': note
                    }
                }
            )
            return True
        except Exception as e:
            logger.error(f"Error updating withdrawal: {e}")
            return False
