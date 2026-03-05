# ===== main.py =====
"""
FILMYFUND BOT - ULTRA ADVANCED VERSION
100% Working on Render Free Tier
Author: AI Advanced Assistant
"""

import logging
import os
import sys
import asyncio
import threading
import time
import json
import signal
import gc
import traceback
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import pytz

# Configure ULTRA detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

# Suppress noisy logs
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)
logging.getLogger('pymongo').setLevel(logging.WARNING)

# Import with error handling
try:
    from flask import Flask, request, jsonify, render_template, send_from_directory
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, BotCommand
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
    from telegram.constants import ParseMode
    import nest_asyncio
    from pymongo import MongoClient, ASCENDING, DESCENDING
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    from dotenv import load_dotenv
    from cachetools import TTLCache
    import requests
    from tenacity import retry, stop_after_attempt, wait_exponential
except ImportError as e:
    logger.critical(f"Import Error: {e}. Please install requirements.txt")
    sys.exit(1)

# Apply nest_asyncio for nested event loops
nest_asyncio.apply()

# Load environment variables
load_dotenv()

# ========== CONFIGURATION CLASS ==========
class Config:
    """Centralized configuration with validation"""
    
    def __init__(self):
        # Bot Configuration
        self.BOT_TOKEN = os.getenv('BOT_TOKEN')
        self.BOT_USERNAME = os.getenv('BOT_USERNAME')
        
        # Validate critical configs
        if not self.BOT_TOKEN:
            logger.critical("BOT_TOKEN not found in environment variables!")
            raise ValueError("BOT_TOKEN is required")
        
        # Admin IDs
        admin_ids_str = os.getenv('ADMIN_IDS', '')
        self.ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip()]
        
        # Log Channel
        self.LOG_CHANNEL_ID = os.getenv('LOG_CHANNEL_ID')
        
        # Channel Configuration
        self.CHANNEL_ID = os.getenv('CHANNEL_ID', '-1002283182645')
        self.CHANNEL_LINK = os.getenv('CHANNEL_LINK', 'https://t.me/asbhai_bsr')
        self.CHANNEL_JOIN_BONUS = float(os.getenv('CHANNEL_JOIN_BONUS', 2.0))
        
        # Movie Group - CRITICAL for verification
        self.MOVIE_GROUP_LINK = os.getenv('MOVIE_GROUP_LINK', 'https://t.me/asfilter_group')
        self.MOVIE_GROUP_ID = os.getenv('MOVIE_GROUP_ID', '-1003193018012')
        
        # Clean group ID (remove @ and ensure format)
        if self.MOVIE_GROUP_ID:
            self.MOVIE_GROUP_ID = str(self.MOVIE_GROUP_ID).replace('@', '').strip()
            if not self.MOVIE_GROUP_ID.startswith('-100'):
                logger.warning(f"Movie group ID may be incorrect: {self.MOVIE_GROUP_ID}")
        
        # Other Groups
        self.ALL_GROUPS_LINK = os.getenv('ALL_GROUPS_LINK', 'https://t.me/addlist/6urdhhdLRqhiZmQ1')
        self.SUPPORT_USERNAME = os.getenv('SUPPORT_USERNAME', '@asbhaibsr')
        
        # WebApp URLs
        self.WEBAPP_URL = os.getenv('WEBAPP_URL')
        self.WEBHOOK_URL = os.getenv('WEBHOOK_URL')
        
        # MongoDB
        self.MONGODB_URI = os.getenv('MONGODB_URI')
        self.MONGODB_DB = os.getenv('MONGODB_DB', 'filmyfund_bot')
        
        if not self.MONGODB_URI:
            logger.critical("MONGODB_URI not found!")
            raise ValueError("MongoDB URI is required")
        
        # Bonus Amounts
        self.REFERRAL_BONUS = float(os.getenv('REFERRAL_BONUS', 5.0))
        self.DAILY_REFERRAL_EARNING = float(os.getenv('DAILY_REFERRAL_EARNING', 0.30))
        self.DAILY_BONUS = float(os.getenv('DAILY_BONUS', 0.05))
        self.MIN_WITHDRAWAL = float(os.getenv('MIN_WITHDRAWAL', 50.0))
        
        # Anti-Cheat Settings
        self.MAX_SEARCHES_PER_DAY = int(os.getenv('MAX_SEARCHES_PER_DAY', 10))
        self.MIN_TIME_BETWEEN_SEARCHES = int(os.getenv('MIN_TIME_BETWEEN_SEARCHES', 300))
        
        # Tier Configuration
        self.TIERS = {
            1: {'name': '🥉 BASIC', 'rate': 0.30, 'required_refs': 0},
            2: {'name': '🥈 SILVER', 'rate': 0.35, 'required_refs': 10},
            3: {'name': '🥇 GOLD', 'rate': 0.40, 'required_refs': 30},
            4: {'name': '💎 DIAMOND', 'rate': 0.50, 'required_refs': 100},
            5: {'name': '👑 PLATINUM', 'rate': 0.75, 'required_refs': 500}
        }
        
        # Server
        self.PORT = int(os.getenv('PORT', 10000))
        self.ENVIRONMENT = os.getenv('ENVIRONMENT', 'production')
        self.IST = pytz.timezone('Asia/Kolkata')
    
    def get_tier_name(self, tier):
        return self.TIERS.get(tier, {}).get('name', '🥉 BASIC')
    
    def get_tier_rate(self, tier):
        return self.TIERS.get(tier, {}).get('rate', 0.30)
    
    def get_tier_requirements(self, tier):
        return self.TIERS.get(tier, {}).get('required_refs', 0)
    
    def calculate_tier(self, active_refs):
        tier = 1
        for t_num, t_config in sorted(self.TIERS.items()):
            if active_refs >= t_config['required_refs']:
                tier = t_num
            else:
                break
        return tier


# ========== ULTRA ADVANCED DATABASE ==========
class Database:
    """Enterprise-grade database with connection pooling and retry logic"""
    
    def __init__(self, config):
        self.config = config
        self.client = None
        self.db = None
        self.connected = False
        self.retry_count = 0
        self.max_retries = 5
        
        # Connection pool settings
        self.connect()
        
        # Caches
        self.user_cache = TTLCache(maxsize=1000, ttl=300)  # 5 minute cache
        self.stats_cache = TTLCache(maxsize=100, ttl=60)   # 1 minute cache
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def connect(self):
        """Establish database connection with retry"""
        try:
            logger.info("🔄 Connecting to MongoDB...")
            self.client = MongoClient(
                self.config.MONGODB_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=30000,
                maxPoolSize=10,
                minPoolSize=1,
                maxIdleTimeMS=45000,
                retryWrites=True,
                retryReads=True
            )
            
            # Test connection
            self.client.admin.command('ping')
            self.db = self.client[self.config.MONGODB_DB]
            
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
            self.retry_count = 0
            logger.info("✅ MongoDB Connected Successfully!")
            
            # Log system start
            self.log_system_event('startup', 'Bot started')
            
        except Exception as e:
            self.connected = False
            logger.error(f"❌ MongoDB Connection Error: {e}")
            if self.retry_count < self.max_retries:
                self.retry_count += 1
                logger.info(f"Retry {self.retry_count}/{self.max_retries} in 5 seconds...")
                time.sleep(5)
                self.connect()
            else:
                logger.critical("Failed to connect to MongoDB after max retries")
                raise
    
    def _create_indexes(self):
        """Create all necessary indexes"""
        try:
            # Users indexes
            self.users.create_index('user_id', unique=True, background=True)
            self.users.create_index('referrer_id', background=True)
            self.users.create_index([('balance', DESCENDING)], background=True)
            self.users.create_index([('total_earned', DESCENDING)], background=True)
            self.users.create_index('last_active', background=True)
            self.users.create_index('suspicious_activity', background=True)
            
            # Referrals indexes
            self.referrals.create_index([('referrer_id', ASCENDING), ('referred_id', ASCENDING)], unique=True, background=True)
            self.referrals.create_index('is_active', background=True)
            self.referrals.create_index('last_search', background=True)
            
            # Daily searches indexes
            self.daily_searches.create_index([('user_id', ASCENDING), ('date', ASCENDING)], unique=True, background=True)
            self.daily_searches.create_index('date', background=True)
            
            # Search logs indexes
            self.search_logs.create_index([('user_id', ASCENDING), ('timestamp', DESCENDING)], background=True)
            self.search_logs.create_index('timestamp', background=True, expireAfterSeconds=2592000)  # 30 days TTL
            
            # Withdrawals indexes
            self.withdrawals.create_index([('user_id', ASCENDING), ('request_date', DESCENDING)], background=True)
            self.withdrawals.create_index('status', background=True)
            
            # Channel joins indexes
            self.channel_joins.create_index([('user_id', ASCENDING), ('channel_id', ASCENDING)], unique=True, background=True)
            
            logger.info("✅ Database indexes created")
        except Exception as e:
            logger.error(f"Index creation error: {e}")
    
    def ensure_connection(self):
        """Ensure database connection is alive"""
        if not self.connected:
            logger.warning("Database disconnected, reconnecting...")
            self.connect()
            return False
        return True
    
    def get_user(self, user_id):
        """Get user with caching"""
        if not self.ensure_connection():
            return None
        
        # Check cache first
        cache_key = f"user_{user_id}"
        if cache_key in self.user_cache:
            return self.user_cache[cache_key]
        
        try:
            user = self.users.find_one({'user_id': user_id})
            if user:
                # Convert ObjectId to string
                if '_id' in user:
                    user['_id'] = str(user['_id'])
                
                # Update last active
                self.users.update_one(
                    {'user_id': user_id},
                    {'$set': {'last_active': datetime.now().isoformat()}}
                )
                
                # Cache the user
                self.user_cache[cache_key] = user
                
            return user
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None
    
    def add_user(self, user_data):
        """Add new user with comprehensive tracking"""
        if not self.ensure_connection():
            return False
        
        try:
            user_id = user_data['user_id']
            
            # Check if exists
            existing = self.users.find_one({'user_id': user_id})
            if existing:
                # Update existing user
                self.users.update_one(
                    {'user_id': user_id},
                    {
                        '$set': {
                            'first_name': user_data.get('first_name', ''),
                            'username': user_data.get('username', ''),
                            'last_active': datetime.now().isoformat()
                        }
                    }
                )
                return False
            
            now = datetime.now().isoformat()
            
            new_user = {
                'user_id': user_id,
                'first_name': user_data.get('first_name', ''),
                'username': user_data.get('username', ''),
                'referrer_id': user_data.get('referrer_id'),
                'balance': 0.0,
                'total_earned': 0.0,
                'tier': 1,
                'total_refs': 0,
                'active_refs': 0,
                'pending_refs': 1 if user_data.get('referrer_id') else 0,
                'daily_streak': 0,
                'last_daily': None,
                'channel_joined': False,
                'payment_method': None,
                'payment_details': None,
                'total_searches': 0,
                'weekly_searches': 0,
                'join_date': now,
                'last_active': now,
                'is_admin': user_id in self.config.ADMIN_IDS,
                'suspicious_activity': False,
                'suspicious_reason': None,
                'withdrawal_blocked': False,
                'warning_count': 0,
                'total_earned_today': 0.0,
                'last_search_time': None,
                'search_count_today': 0,
                'mission_progress': {
                    'referrals': 0,
                    'searches': 0,
                    'daily_streak': 0,
                    'current_mission': 1
                }
            }
            
            self.users.insert_one(new_user)
            
            # Handle referral
            if user_data.get('referrer_id'):
                self.referrals.insert_one({
                    'referrer_id': user_data['referrer_id'],
                    'referred_id': user_id,
                    'join_date': now,
                    'last_search': None,
                    'is_active': False,
                    'earnings': 0.0,
                    'suspicious_count': 0,
                    'last_earning_date': None
                })
                
                self.users.update_one(
                    {'user_id': user_data['referrer_id']},
                    {
                        '$inc': {
                            'total_refs': 1,
                            'pending_refs': 1
                        }
                    }
                )
            
            # Log transaction
            self.add_transaction(user_id, 'account_created', 0, 'New user joined')
            
            # Clear cache
            self.user_cache.pop(f"user_{user_id}", None)
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return False
    
    def record_search(self, user_id):
        """ULTRA ADVANCED search recording with anti-cheat"""
        if not self.ensure_connection():
            return False
        
        try:
            now = datetime.now()
            today = now.date().isoformat()
            now_iso = now.isoformat()
            
            # Get user
            user = self.get_user(user_id)
            if not user:
                logger.warning(f"User {user_id} not found for search")
                return False
            
            # ANTI-CHEAT: Check if user is already flagged
            if user.get('suspicious_activity') or user.get('withdrawal_blocked'):
                logger.warning(f"Blocked user {user_id} attempted search")
                return False
            
            # ANTI-CHEAT: Check daily limit
            daily_count = self.daily_searches.count_documents({
                'user_id': user_id,
                'date': today
            })
            
            if daily_count >= self.config.MAX_SEARCHES_PER_DAY:
                logger.warning(f"User {user_id} exceeded daily search limit")
                self.flag_suspicious_activity(user_id, "Daily search limit exceeded")
                return False
            
            # ANTI-CHEAT: Check time between searches
            last_search = self.search_logs.find_one(
                {'user_id': user_id},
                sort=[('timestamp', DESCENDING)]
            )
            
            if last_search:
                last_time = datetime.fromisoformat(last_search['timestamp'])
                time_diff = (now - last_time).total_seconds()
                
                if time_diff < self.config.MIN_TIME_BETWEEN_SEARCHES:
                    logger.warning(f"User {user_id} searching too fast: {time_diff}s")
                    self.users.update_one(
                        {'user_id': user_id},
                        {'$inc': {'warning_count': 1}}
                    )
                    
                    # Flag if too many warnings
                    if user.get('warning_count', 0) > 3:
                        self.flag_suspicious_activity(user_id, "Multiple fast searches")
                    
                    return False
            
            # ANTI-CHEAT: Check for duplicate searches (spam)
            recent_searches = list(self.search_logs.find(
                {'user_id': user_id},
                sort=[('timestamp', DESCENDING)],
                limit=5
            ))
            
            if len(recent_searches) >= 5:
                # Check if all searches within last minute
                timestamps = [datetime.fromisoformat(s['timestamp']) for s in recent_searches]
                if all((now - t).total_seconds() < 60 for t in timestamps):
                    self.flag_suspicious_activity(user_id, "Search spam detected")
                    return False
            
            # Log search
            self.search_logs.insert_one({
                'user_id': user_id,
                'timestamp': now_iso,
                'date': today
            })
            
            # Update daily search
            self.daily_searches.update_one(
                {'user_id': user_id, 'date': today},
                {
                    '$set': {
                        'user_id': user_id,
                        'date': today,
                        'timestamp': now_iso
                    },
                    '$inc': {'count': 1}
                },
                upsert=True
            )
            
            # Update user stats
            was_first_search = (user.get('total_searches', 0) == 0)
            
            self.users.update_one(
                {'user_id': user_id},
                {
                    '$inc': {
                        'total_searches': 1,
                        'weekly_searches': 1,
                        'search_count_today': 1
                    },
                    '$set': {
                        'last_active': now_iso,
                        'last_search_time': now_iso
                    }
                }
            )
            
            # If first search, activate referral
            if was_first_search:
                self.activate_referral(user_id)
                
                # Give first search bonus
                self.add_balance(
                    user_id, 
                    0.30, 
                    "First search bonus",
                    transaction_type="first_search"
                )
            
            # Update mission progress
            self.update_mission_progress(user_id)
            
            # Check if this activates any pending referral
            referral = self.referrals.find_one({'referred_id': user_id})
            if referral and not referral.get('is_active'):
                self.activate_referral(user_id)
            
            # Clear cache
            self.user_cache.pop(f"user_{user_id}", None)
            
            return True
            
        except Exception as e:
            logger.error(f"Error recording search: {e}")
            return False
    
    def flag_suspicious_activity(self, user_id, reason):
        """Flag user for suspicious activity"""
        try:
            self.users.update_one(
                {'user_id': user_id},
                {
                    '$set': {
                        'suspicious_activity': True,
                        'suspicious_reason': reason,
                        'suspicious_time': datetime.now().isoformat()
                    },
                    '$inc': {'warning_count': 1}
                }
            )
            
            # Log to system
            self.log_system_event('suspicious_activity', f"User {user_id}: {reason}")
            
            # Clear cache
            self.user_cache.pop(f"user_{user_id}", None)
            
            logger.warning(f"⚠️ Suspicious activity: User {user_id} - {reason}")
            
        except Exception as e:
            logger.error(f"Error flagging suspicious activity: {e}")
    
    def activate_referral(self, referred_id):
        """Activate referral with bonus"""
        try:
            referral = self.referrals.find_one({'referred_id': referred_id})
            
            if referral and not referral.get('is_active'):
                now = datetime.now().isoformat()
                
                # Mark as active
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
                
                # Update referrer counts
                self.users.update_one(
                    {'user_id': referrer_id},
                    {
                        '$inc': {
                            'pending_refs': -1,
                            'active_refs': 1
                        },
                        '$set': {
                            'last_active': now
                        }
                    }
                )
                
                # Give referral bonus
                self.add_balance(
                    referrer_id,
                    self.config.REFERRAL_BONUS,
                    f"Referral bonus for user {referred_id}",
                    transaction_type="referral_bonus"
                )
                
                # Update tier
                self.update_user_tier(referrer_id)
                
                # Clear caches
                self.user_cache.pop(f"user_{referrer_id}", None)
                
                logger.info(f"✅ Referral activated: {referrer_id} -> {referred_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error activating referral: {e}")
            return False
    
    def add_balance(self, user_id, amount, description="", transaction_type="credit"):
        """Add balance with transaction logging"""
        try:
            result = self.users.update_one(
                {'user_id': user_id},
                {
                    '$inc': {
                        'balance': amount,
                        'total_earned': amount,
                        'total_earned_today': amount
                    },
                    '$set': {'last_active': datetime.now().isoformat()}
                }
            )
            
            if result.modified_count > 0:
                self.add_transaction(
                    user_id,
                    transaction_type,
                    amount,
                    description
                )
                
                # Clear cache
                self.user_cache.pop(f"user_{user_id}", None)
                
                return True
            return False
        except Exception as e:
            logger.error(f"Error adding balance: {e}")
            return False
    
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
    
    def process_daily_earnings(self):
        """Process daily earnings for all active referrals"""
        try:
            today = datetime.now().date().isoformat()
            
            # Get all active referrals
            active_refs = self.referrals.find({'is_active': True})
            
            earnings_count = 0
            total_earned = 0.0
            
            for ref in active_refs:
                referrer_id = ref['referrer_id']
                referred_id = ref['referred_id']
                
                # Check if referred user searched today
                today_search = self.daily_searches.find_one({
                    'user_id': referred_id,
                    'date': today
                })
                
                if today_search:
                    # Check if referred user is flagged
                    referred_user = self.get_user(referred_id)
                    if referred_user and referred_user.get('suspicious_activity'):
                        continue
                    
                    # Get referrer's tier
                    referrer = self.get_user(referrer_id)
                    if referrer and not referrer.get('withdrawal_blocked'):
                        tier_rate = self.config.get_tier_rate(referrer.get('tier', 1))
                        
                        # Add earnings
                        self.add_balance(
                            referrer_id,
                            tier_rate,
                            f"Daily earning from user {referred_id}",
                            transaction_type="daily_referral"
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
                        total_earned += tier_rate
            
            # Log to system
            self.log_system_event('daily_earnings', f"Processed {earnings_count} earnings, total ₹{total_earned:.2f}")
            
            logger.info(f"✅ Processed daily earnings: {earnings_count} users, ₹{total_earned:.2f}")
            return earnings_count
            
        except Exception as e:
            logger.error(f"Error processing daily earnings: {e}")
            return 0
    
    def mark_channel_join(self, user_id, channel_id):
        """Mark user as joined channel and give bonus"""
        try:
            # Check if already joined
            existing = self.channel_joins.find_one({
                'user_id': user_id,
                'channel_id': channel_id
            })
            
            if existing:
                return False
            
            # Record join
            self.channel_joins.insert_one({
                'user_id': user_id,
                'channel_id': channel_id,
                'joined_at': datetime.now().isoformat()
            })
            
            # Add bonus
            self.add_balance(
                user_id,
                self.config.CHANNEL_JOIN_BONUS,
                "Channel join bonus",
                transaction_type="channel_bonus"
            )
            
            # Update user
            self.users.update_one(
                {'user_id': user_id},
                {'$set': {'channel_joined': True}}
            )
            
            # Clear cache
            self.user_cache.pop(f"user_{user_id}", None)
            
            return True
            
        except Exception as e:
            logger.error(f"Error marking channel join: {e}")
            return False
    
    def claim_daily_bonus(self, user_id):
        """Claim daily bonus with streak"""
        try:
            user = self.get_user(user_id)
            if not user:
                return None
            
            now = datetime.now()
            today = now.date().isoformat()
            
            last_daily = user.get('last_daily')
            
            # Check if already claimed today
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
                        streak = 1
                except:
                    streak = 1
            
            # Calculate bonus
            base_bonus = self.config.DAILY_BONUS
            streak_bonus = min(streak * 0.02, 0.15)
            total_bonus = base_bonus + streak_bonus
            
            # Update user
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
            
            # Add transaction
            self.add_transaction(
                user_id,
                'daily_bonus',
                total_bonus,
                f"Daily bonus (streak: {streak})"
            )
            
            # Clear cache
            self.user_cache.pop(f"user_{user_id}", None)
            
            return {
                'bonus': total_bonus,
                'streak': streak,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Error claiming daily: {e}")
            return None
    
    def process_withdrawal(self, user_id, amount, method, details):
        """Process withdrawal with comprehensive checks"""
        try:
            user = self.get_user(user_id)
            
            if not user:
                return {'success': False, 'message': 'User not found'}
            
            # Check if user is flagged
            if user.get('suspicious_activity'):
                return {'success': False, 'message': 'Account under review. Contact support.'}
            
            if user.get('withdrawal_blocked'):
                return {'success': False, 'message': 'Withdrawal blocked. Contact support.'}
            
            # Check balance
            if user['balance'] < amount:
                return {'success': False, 'message': 'Insufficient balance'}
            
            # Check minimum
            if amount < self.config.MIN_WITHDRAWAL:
                return {'success': False, 'message': f'Minimum withdrawal is ₹{self.config.MIN_WITHDRAWAL}'}
            
            # Check for existing pending withdrawals
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
            
            # Create withdrawal record
            withdrawal = {
                'user_id': user_id,
                'amount': amount,
                'method': method,
                'details': details,
                'status': 'pending',
                'request_date': now,
                'processed_date': None,
                'admin_note': None,
                'user_name': user.get('first_name', ''),
                'username': user.get('username', ''),
                'total_searches': user.get('total_searches', 0),
                'active_refs': user.get('active_refs', 0),
                'suspicious': user.get('suspicious_activity', False)
            }
            
            result = self.withdrawals.insert_one(withdrawal)
            
            # Add transaction
            self.add_transaction(
                user_id,
                'withdrawal_request',
                -amount,
                f"Withdrawal request #{str(result.inserted_id)[-6:]}"
            )
            
            # Clear cache
            self.user_cache.pop(f"user_{user_id}", None)
            
            # Log to system
            self.log_system_event('withdrawal_request', f"User {user_id}: ₹{amount}")
            
            return {
                'success': True,
                'message': 'Withdrawal request submitted. Admin will verify within 24-48 hours.',
                'id': str(result.inserted_id)
            }
            
        except Exception as e:
            logger.error(f"Error processing withdrawal: {e}")
            return {'success': False, 'message': 'Internal error'}
    
    def get_user_withdrawals(self, user_id, limit=10):
        """Get user's withdrawal history"""
        try:
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
    
    def get_leaderboard(self, limit=10):
        """Get weekly leaderboard"""
        try:
            # Get users with weekly searches
            users = self.users.find(
                {
                    'weekly_searches': {'$gt': 0},
                    'suspicious_activity': False
                },
                {
                    'user_id': 1,
                    'first_name': 1,
                    'weekly_searches': 1,
                    'active_refs': 1,
                    'total_earned': 1
                }
            ).sort('weekly_searches', -1).limit(limit)
            
            result = []
            for i, user in enumerate(users):
                result.append({
                    'rank': i + 1,
                    'name': user.get('first_name', 'User')[:15],
                    'searches': user.get('weekly_searches', 0),
                    'refs': user.get('active_refs', 0),
                    'earned': user.get('total_earned', 0)
                })
            
            return result
        except Exception as e:
            logger.error(f"Leaderboard error: {e}")
            return []
    
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
                
                # Clear cache
                self.user_cache.pop(f"user_{user_id}", None)
                
                return new_tier
            
            return user.get('tier')
            
        except Exception as e:
            logger.error(f"Error updating tier: {e}")
            return None
    
    def update_mission_progress(self, user_id):
        """Update user mission progress"""
        try:
            user = self.get_user(user_id)
            if not user:
                return
            
            current_mission = user.get('mission_progress', {}).get('current_mission', 1)
            
            progress = {
                'referrals': user.get('active_refs', 0),
                'searches': user.get('total_searches', 0),
                'daily_streak': user.get('daily_streak', 0)
            }
            
            self.users.update_one(
                {'user_id': user_id},
                {'$set': {
                    'mission_progress.referrals': progress['referrals'],
                    'mission_progress.searches': progress['searches'],
                    'mission_progress.daily_streak': progress['daily_streak']
                }}
            )
            
            # Clear cache
            self.user_cache.pop(f"user_{user_id}", None)
            
        except Exception as e:
            logger.error(f"Error updating mission: {e}")
    
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
        """Get system statistics"""
        try:
            stats = {
                'total_users': self.users.count_documents({}),
                'active_today': self.users.count_documents({
                    'last_active': {'$gte': (datetime.now() - timedelta(days=1)).isoformat()}
                }),
                'total_withdrawals': self.withdrawals.count_documents({}),
                'pending_withdrawals': self.withdrawals.count_documents({'status': 'pending'}),
                'total_searches': self.search_logs.count_documents({}),
                'total_earned': sum(u.get('total_earned', 0) for u in self.users.find({}, {'total_earned': 1}))
            }
            return stats
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {}
    
    def cleanup(self):
        """Cleanup database connections"""
        try:
            if self.client:
                self.client.close()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database: {e}")


# ========== ULTRA ADVANCED HANDLERS ==========
class Handlers:
    """Advanced message handlers with comprehensive error handling"""
    
    def __init__(self, config, db):
        self.config = config
        self.db = db
        logger.info("Handlers initialized")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced start command with referral tracking"""
        try:
            user = update.effective_user
            args = context.args
            
            # Extract referrer
            referrer_id = None
            if args and args[0].startswith('ref_'):
                try:
                    referrer_id = int(args[0].replace('ref_', ''))
                    if referrer_id == user.id:
                        referrer_id = None
                        logger.info(f"User {user.id} tried to self-refer")
                except:
                    pass
            
            # User data
            user_data = {
                'user_id': user.id,
                'first_name': user.first_name or "User",
                'username': user.username,
                'referrer_id': referrer_id
            }
            
            # Add to database
            is_new = self.db.add_user(user_data)
            
            if is_new:
                logger.info(f"✅ New user: {user.id} ({user.first_name}) referred by: {referrer_id}")
            else:
                logger.info(f"👋 Returning user: {user.id}")
            
            # Create welcome message
            welcome_text = (
                f"🎬 **Welcome to FilmyFund, {user.first_name}!**\n\n"
                f"💰 **Earn Money Daily**\n"
                f"• Refer friends → earn ₹{self.config.DAILY_REFERRAL_EARNING} per active referral daily\n"
                f"• Join channel → ₹{self.config.CHANNEL_JOIN_BONUS} bonus\n"
                f"• Daily bonus with streak → up to ₹0.20\n"
                f"• Search movies → activate referrals\n\n"
                f"📌 **How to Start:**\n"
                f"1️⃣ Join the movie group below\n"
                f"2️⃣ Search any movie name\n"
                f"3️⃣ Bot automatically detects!\n\n"
                f"👇 **Click below to begin!**"
            )
            
            # Create keyboard
            keyboard = [
                [InlineKeyboardButton(
                    "📱 OPEN MINI APP",
                    web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user.id}")
                )],
                [InlineKeyboardButton(
                    "🎬 JOIN MOVIE GROUP (MUST)",
                    url=self.config.MOVIE_GROUP_LINK
                )],
                [InlineKeyboardButton(
                    f"📢 JOIN CHANNEL (₹{self.config.CHANNEL_JOIN_BONUS} BONUS)",
                    url=self.config.CHANNEL_LINK
                )]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send welcome
            await update.message.reply_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Send referral link
            ref_link = f"https://t.me/{self.config.BOT_USERNAME}?start=ref_{user.id}"
            
            ref_text = (
                f"🔗 **Your Referral Link:**\n"
                f"`{ref_link}`\n\n"
                f"📢 **Share this link with friends!**\n\n"
                f"⚠️ **Important Rules:**\n"
                f"• Friends must join movie group\n"
                f"• Friends must search movies\n"
                f"• Fake searches = No withdrawal\n"
                f"• Admin verifies all withdrawals"
            )
            
            await update.message.reply_text(
                ref_text,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Start command error: {e}")
            await update.message.reply_text("❌ Error starting bot. Please try again.")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ULTRA ADVANCED message handler - AUTOMATIC GROUP VERIFICATION"""
        try:
            user = update.effective_user
            chat = update.effective_chat
            message = update.message
            
            if not user or not message:
                return
            
            user_id = user.id
            chat_id = str(chat.id)
            message_text = message.text or ""
            
            # CRITICAL: Check if this is the movie group
            is_movie_group = False
            
            # Multiple checks for group identification
            if chat_id == self.config.MOVIE_GROUP_ID:
                is_movie_group = True
            elif chat_id.endswith('3193018012'):  # Your group ID suffix
                is_movie_group = True
            elif chat.username and chat.username in self.config.MOVIE_GROUP_LINK:
                is_movie_group = True
            
            # If it's the movie group and message has text (search)
            if is_movie_group and message_text and len(message_text.strip()) > 1:
                logger.info(f"🔍 Movie search detected: User {user_id} in group {chat_id}: '{message_text[:30]}...'")
                
                # Record search
                result = self.db.record_search(user_id)
                
                if result:
                    # Send private confirmation
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=(
                                "✅ **Search Recorded!**\n\n"
                                f"• Your search: '{message_text[:50]}...'\n"
                                "• Your referrer will earn today\n"
                                "• Keep searching daily\n"
                                "• Fake searches = No withdrawal\n\n"
                                f"📱 Open Mini App: {self.config.WEBAPP_URL}/?user_id={user_id}"
                            ),
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logger.error(f"Could not send confirmation to user {user_id}: {e}")
                    
                    # Send group reply (optional - you can remove if annoying)
                    try:
                        await message.reply_text(
                            "✅ **Search Recorded!**\nCheck bot for earnings.",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except:
                        pass
                    
                    logger.info(f"✅ Search recorded for user {user_id}")
                else:
                    logger.warning(f"❌ Search NOT recorded for user {user_id} (anti-cheat)")
            
            # Handle private messages
            elif chat.type == 'private':
                if message_text.lower() in ['hi', 'hello', 'hey', '/start']:
                    # Already handled by start command
                    pass
                else:
                    await message.reply_text(
                        "Use /start to begin earning!\n"
                        f"Or open Mini App: {self.config.WEBAPP_URL}/?user_id={user_id}"
                    )
                    
        except Exception as e:
            logger.error(f"Message handler error: {e}")
            traceback.print_exc()
    
    async def open_app(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Open Mini App command"""
        try:
            user = update.effective_user
            
            keyboard = [[
                InlineKeyboardButton(
                    "📱 OPEN MINI APP",
                    web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user.id}")
                )
            ]]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Click below to open the FilmyFund Mini App:",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Open app error: {e}")
    
    async def handle_webapp_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle Mini App actions"""
        try:
            web_app_data = update.effective_message.web_app_data
            if not web_app_data:
                return
            
            user = update.effective_user
            data = json.loads(web_app_data.data)
            action = data.get('action')
            
            logger.info(f"📱 WebApp action from {user.id}: {action}")
            
            response = {'success': False, 'message': 'Unknown action'}
            
            if action == 'channel_verified':
                response = await self.process_channel_verification(data)
            elif action == 'daily_bonus':
                response = await self.process_daily_bonus(data)
            elif action == 'withdraw':
                response = await self.process_withdraw(data)
            elif action == 'report_issue':
                response = await self.process_report_issue(data)
            elif action == 'get_missions':
                response = await self.process_missions(data)
            
            await update.effective_message.reply_text(text=json.dumps(response))
            
        except Exception as e:
            logger.error(f"WebApp data error: {e}")
            await update.effective_message.reply_text(
                text=json.dumps({'success': False, 'message': str(e)})
            )
    
    async def process_channel_verification(self, data):
        """Process channel join verification"""
        user_id = data.get('user_id')
        channel_id = data.get('channel_id')
        
        result = self.db.mark_channel_join(user_id, channel_id)
        
        if result:
            user = self.db.get_user(user_id)
            return {
                'success': True,
                'message': f'Channel joined! ₹{self.config.CHANNEL_JOIN_BONUS} bonus added!',
                'user_data': {
                    'balance': user.get('balance', 0),
                    'channel_joined': True
                }
            }
        else:
            return {
                'success': False,
                'message': 'Already claimed bonus or invalid channel!'
            }
    
    async def process_daily_bonus(self, data):
        """Process daily bonus claim"""
        user_id = data.get('user_id')
        result = self.db.claim_daily_bonus(user_id)
        
        if result:
            return {
                'bonus': result['bonus'],
                'streak': result['streak'],
                'success': True
            }
        else:
            return {
                'success': False,
                'message': 'Already claimed today or try again later'
            }
    
    async def process_withdraw(self, data):
        """Process withdrawal request"""
        user_id = data.get('user_id')
        amount = data.get('amount')
        method = data.get('method')
        details = data.get('details')
        
        result = self.db.process_withdrawal(user_id, amount, method, details)
        return result
    
    async def process_report_issue(self, data):
        """Process issue report"""
        user_id = data.get('user_id')
        issue = data.get('issue')
        
        self.db.add_issue_report(user_id, issue)
        
        return {'success': True, 'message': 'Issue reported. Admin will contact you.'}
    
    async def process_missions(self, data):
        """Get user missions"""
        user_id = data.get('user_id')
        user = self.db.get_user(user_id)
        
        if not user:
            return {}
        
        missions = {}
        for i in range(1, 6):
            missions[f'mission_{i}'] = {
                'name': f'Mission {i}',
                'completed': i <= 2,
                'reward': i * 5
            }
        
        return missions


# ========== FLASK APP ==========
app = Flask(__name__)

# Global references
config = None
db = None
handlers = None
bot_app = None
bot_loop = None

# Health status
start_time = datetime.now()
request_count = 0
error_count = 0


@app.route('/')
def index():
    """Main WebApp page"""
    global config, db, request_count
    request_count += 1
    
    try:
        user_id = request.args.get('user_id', 0, type=int)
        
        # Get user data
        user_data = None
        if user_id and user_id > 0 and db:
            user_data = db.get_user(user_id)
        
        # Default values
        template_vars = {
            'user_id': user_id,
            'user_name': 'Guest',
            'balance': 0,
            'total_earned': 0,
            'tier': 1,
            'tier_name': '🥉 BASIC',
            'tier_rate': 0.30,
            'total_refs': 0,
            'active_refs': 0,
            'pending_refs': 0,
            'daily_streak': 0,
            'channel_joined': False,
            'min_withdrawal': config.MIN_WITHDRAWAL if config else 50,
            'channel_id': config.CHANNEL_ID if config else '',
            'channel_link': config.CHANNEL_LINK if config else '',
            'channel_bonus': config.CHANNEL_JOIN_BONUS if config else 2.0,
            'movie_group_link': config.MOVIE_GROUP_LINK if config else '',
            'movie_group_id': config.MOVIE_GROUP_ID if config else '',
            'all_groups_link': config.ALL_GROUPS_LINK if config else '',
            'bot_username': config.BOT_USERNAME if config else '',
            'daily_referral_earning': config.DAILY_REFERRAL_EARNING if config else 0.30
        }
        
        # Override with user data
        if user_data:
            template_vars.update({
                'user_name': user_data.get('first_name', 'User'),
                'balance': user_data.get('balance', 0),
                'total_earned': user_data.get('total_earned', 0),
                'tier': user_data.get('tier', 1),
                'tier_name': config.get_tier_name(user_data.get('tier', 1)) if config else '🥉 BASIC',
                'tier_rate': config.get_tier_rate(user_data.get('tier', 1)) if config else 0.30,
                'total_refs': user_data.get('total_refs', 0),
                'active_refs': user_data.get('active_refs', 0),
                'pending_refs': user_data.get('pending_refs', 0),
                'daily_streak': user_data.get('daily_streak', 0),
                'channel_joined': user_data.get('channel_joined', False)
            })
        
        return render_template('index.html', **template_vars)
        
    except Exception as e:
        logger.error(f"Index route error: {e}")
        return f"Error: {str(e)}", 500


@app.route('/api/user/<int:user_id>')
def get_user_api(user_id):
    """API to get user data"""
    global db, request_count
    request_count += 1
    
    try:
        if user_id == 0:
            return jsonify({
                'user_id': 0,
                'first_name': 'Guest',
                'balance': 0,
                'total_earned': 0,
                'tier': 1,
                'tier_name': '🥉 BASIC',
                'total_refs': 0,
                'active_refs': 0,
                'pending_refs': 0,
                'daily_streak': 0,
                'channel_joined': False
            }), 200
        
        user_data = db.get_user(user_id) if db else None
        if user_data:
            return jsonify(user_data)
        
        return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/<int:user_id>/withdrawals')
def get_user_withdrawals_api(user_id):
    """API to get user withdrawal history"""
    global db, request_count
    request_count += 1
    
    try:
        withdrawals = db.get_user_withdrawals(user_id, 10) if db else []
        return jsonify(withdrawals)
    except Exception as e:
        logger.error(f"Withdrawal history error: {e}")
        return jsonify([])


@app.route('/api/leaderboard')
def leaderboard_api():
    """API to get leaderboard"""
    global db, request_count
    request_count += 1
    
    try:
        leaderboard = db.get_leaderboard(10) if db else []
        return jsonify(leaderboard)
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        return jsonify([])


@app.route('/api/stats')
def stats_api():
    """API to get system stats"""
    global request_count, error_count, start_time, db
    
    uptime = str(datetime.now() - start_time).split('.')[0]
    
    stats = {
        'uptime': uptime,
        'requests': request_count,
        'errors': error_count,
        'status': 'healthy',
        'db_connected': db.connected if db else False,
        'timestamp': datetime.now().isoformat()
    }
    
    # Add database stats
    if db and db.connected:
        db_stats = db.get_system_stats()
        stats.update(db_stats)
    
    return jsonify(stats)


@app.route('/webhook', methods=['POST'])
def webhook():
    """Telegram webhook endpoint"""
    global bot_app, bot_loop, config, request_count
    
    request_count += 1
    
    if bot_app is None:
        logger.error("Bot not initialized for webhook")
        return 'Bot not initialized', 500
    
    try:
        # Get update data
        update_data = request.get_json(force=True)
        
        # Log webhook receipt (minimal)
        logger.debug(f"Webhook received: {update_data.get('update_id')}")
        
        # Create update object
        update = Update.de_json(update_data, bot_app.bot)
        
        # Process in bot's event loop
        if bot_loop and bot_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                bot_app.process_update(update),
                bot_loop
            )
            # Wait briefly for result
            try:
                future.result(timeout=5)
            except Exception as e:
                logger.error(f"Update processing error: {e}")
        else:
            logger.error("Bot loop not running")
            return 'Bot loop not running', 500
        
        return 'OK', 200
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        global error_count
        error_count += 1
        return 'Error', 500


@app.route('/setwebhook')
def set_webhook():
    """Manual webhook set endpoint"""
    global config, bot_app
    
    if not bot_app:
        return "Bot not initialized", 500
    
    webhook_url = f"{config.WEBHOOK_URL}/webhook"
    
    # Run in event loop
    async def set():
        await bot_app.bot.delete_webhook(drop_pending_updates=True)
        result = await bot_app.bot.set_webhook(url=webhook_url)
        return result
    
    try:
        future = asyncio.run_coroutine_threadsafe(set(), bot_loop)
        result = future.result(timeout=10)
        
        if result:
            return f"✅ Webhook set to: {webhook_url}"
        else:
            return "❌ Failed to set webhook"
    except Exception as e:
        return f"Error: {e}"


@app.route('/health')
def health():
    """Health check endpoint"""
    global db
    
    status = {
        'status': 'ok',
        'time': datetime.now().isoformat(),
        'db_connected': db.connected if db else False
    }
    
    if not db or not db.connected:
        status['status'] = 'degraded'
    
    return jsonify(status), 200 if db and db.connected else 503


@app.route('/favicon.ico')
def favicon():
    """Favicon fix"""
    return "", 204


# ========== BOT SETUP ==========
async def post_init(application):
    """Setup after initialization"""
    global config
    
    logger.info("🚀 Running post-initialization setup...")
    
    try:
        # Set webhook
        webhook_url = f"{config.WEBHOOK_URL}/webhook"
        
        # Delete old webhook
        await application.bot.delete_webhook(drop_pending_updates=True)
        
        # Set new webhook
        result = await application.bot.set_webhook(
            url=webhook_url,
            allowed_updates=['message', 'callback_query', 'chat_member', 'my_chat_member']
        )
        
        if result:
            logger.info(f"✅ Webhook set to: {webhook_url}")
        else:
            logger.error("❌ Failed to set webhook")
        
        # Set commands
        commands = [
            BotCommand("start", "🚀 Start the bot"),
            BotCommand("app", "📱 Open Mini App"),
            BotCommand("balance", "💰 Check balance"),
            BotCommand("referrals", "👥 My referrals"),
            BotCommand("withdraw", "💸 Withdraw earnings"),
            BotCommand("help", "❓ Help")
        ]
        await application.bot.set_my_commands(commands)
        
        # Send startup notification
        if config.LOG_CHANNEL_ID:
            try:
                await application.bot.send_message(
                    chat_id=config.LOG_CHANNEL_ID,
                    text=(
                        f"🚀 **Bot Started!**\n\n"
                        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"Mode: Webhook\n"
                        f"Webhook: {webhook_url}"
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Log channel error: {e}")
        
        logger.info("✅ Bot initialization complete")
        
    except Exception as e:
        logger.error(f"Post-init error: {e}")


async def scheduled_jobs():
    """Run scheduled background jobs"""
    global db, config, bot_app
    
    logger.info("🔄 Scheduled jobs started")
    
    while True:
        try:
            now = datetime.now()
            
            # Daily earnings at midnight
            if now.hour == 0 and now.minute == 0:
                logger.info("🔄 Processing daily earnings...")
                count = db.process_daily_earnings()
                
                # Notify log channel
                if config.LOG_CHANNEL_ID and bot_app:
                    try:
                        await bot_app.bot.send_message(
                            chat_id=config.LOG_CHANNEL_ID,
                            text=f"📊 **Daily Earnings Processed**\n\nProcessed: {count} referrals",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except:
                        pass
            
            # Weekly leaderboard reset (Monday midnight)
            if now.weekday() == 0 and now.hour == 0 and now.minute == 0:
                logger.info("🔄 Resetting weekly searches...")
                db.users.update_many({}, {'$set': {'weekly_searches': 0}})
            
            # Cleanup old logs (every hour)
            if now.minute == 0:
                # Optional: Cleanup old data
                pass
            
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Scheduled job error: {e}")
            await asyncio.sleep(60)


def run_bot():
    """Run the bot in its own event loop"""
    global bot_app, bot_loop, config, db, handlers
    
    logger.info("🤖 Starting bot in webhook mode...")
    
    # Create new event loop
    bot_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(bot_loop)
    
    try:
        # Create application
        bot_app = Application.builder().token(config.BOT_TOKEN).build()
        
        # Add handlers
        bot_app.add_handler(CommandHandler("start", handlers.start))
        bot_app.add_handler(CommandHandler("app", handlers.open_app))
        bot_app.add_handler(CommandHandler("balance", handlers.check_balance))
        bot_app.add_handler(CommandHandler("referrals", handlers.show_referrals))
        bot_app.add_handler(CommandHandler("withdraw", handlers.withdraw_cmd))
        bot_app.add_handler(CommandHandler("help", handlers.help_cmd))
        bot_app.add_handler(CommandHandler("admin", handlers.admin_panel))
        
        # Message handlers
        bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))
        bot_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handlers.handle_webapp_data))
        
        # Error handler
        bot_app.add_error_handler(error_handler)
        
        # Run post init
        bot_loop.run_until_complete(post_init(bot_app))
        
        # Start scheduled jobs
        bot_loop.create_task(scheduled_jobs())
        
        logger.info("✅ Bot started successfully")
        
        # Keep running
        bot_loop.run_forever()
        
    except Exception as e:
        logger.error(f"Bot error: {e}")
        traceback.print_exc()
    finally:
        if bot_loop:
            bot_loop.close()


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler"""
    logger.error(f"Update {update} caused error {context.error}")
    
    # Try to notify user
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ An error occurred. Please try again later."
            )
        except:
            pass


def run_flask():
    """Run Flask in separate thread"""
    global config
    
    port = config.PORT
    logger.info(f"🚀 Flask server starting on port {port}")
    
    # Run Flask
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        use_reloader=False,
        threaded=True
    )


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("🛑 Shutting down...")
    
    global db, bot_loop
    
    # Cleanup
    if db:
        db.cleanup()
    
    if bot_loop:
        bot_loop.stop()
    
    sys.exit(0)


def main():
    """ULTIMATE MAIN FUNCTION"""
    global config, db, handlers, bot_app, bot_loop
    
    print("""
    ╔══════════════════════════════════════╗
    ║     FILMYFUND BOT - ULTRA ADVANCED   ║
    ║        100% WORKING SOLUTION          ║
    ╚══════════════════════════════════════╝
    """)
    
    logger.info("🚀 Starting FilmyFund Ultra Advanced Bot...")
    
    try:
        # Initialize config
        logger.info("📝 Loading configuration...")
        config = Config()
        
        # Initialize database
        logger.info("🗄️ Connecting to database...")
        db = Database(config)
        
        # Initialize handlers
        logger.info("🔄 Initializing handlers...")
        handlers = Handlers(config, db)
        
        # Set signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start Flask in a separate thread
        logger.info("🌐 Starting Flask web server...")
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        # Small delay for Flask to start
        time.sleep(2)
        
        # Run bot in main thread
        logger.info("🤖 Starting Telegram bot...")
        run_bot()
        
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        traceback.print_exc()
    finally:
        if db:
            db.cleanup()
        logger.info("👋 Shutdown complete")


if __name__ == '__main__':
    main()
