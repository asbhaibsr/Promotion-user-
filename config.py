# ===== config.py (FIXED WITH BOT USERNAME) =====

import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class Config:
    def __init__(self):
        """Initialize all configuration variables"""
        
        # ===== BOT CONFIGURATION =====
        self.BOT_TOKEN = os.getenv('BOT_TOKEN')
        if not self.BOT_TOKEN:
            logger.error("❌ BOT_TOKEN not found in environment variables")
            raise ValueError("BOT_TOKEN is required")
        
        # FIXED: Use your actual bot username
        self.BOT_USERNAME = os.getenv('BOT_USERNAME', 'LinkProviderRobot')
        
        # ===== ADMIN CONFIGURATION =====
        admin_ids_str = os.getenv('ADMIN_IDS', '')
        try:
            self.ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip()]
            if not self.ADMIN_IDS:
                logger.warning("⚠️ No ADMIN_IDS configured. Admin commands will not work.")
        except ValueError:
            logger.error(f"❌ Invalid ADMIN_IDS format: {admin_ids_str}")
            self.ADMIN_IDS = []
        
        # ===== LOG CHANNEL =====
        log_channel = os.getenv('LOG_CHANNEL_ID')
        try:
            self.LOG_CHANNEL_ID = int(log_channel) if log_channel else None
        except ValueError:
            logger.warning(f"⚠️ Invalid LOG_CHANNEL_ID: {log_channel}")
            self.LOG_CHANNEL_ID = None
        
        # ===== CHANNEL CONFIGURATION =====
        self.CHANNEL_ID = os.getenv('CHANNEL_ID', '-1002283182645')
        self.CHANNEL_LINK = os.getenv('CHANNEL_LINK', 'https://t.me/asbhai_bsr')
        
        try:
            self.CHANNEL_JOIN_BONUS = float(os.getenv('CHANNEL_JOIN_BONUS', '2.0'))
        except ValueError:
            logger.warning("⚠️ Invalid CHANNEL_JOIN_BONUS, using default 2.0")
            self.CHANNEL_JOIN_BONUS = 2.0
        
        # ===== MOVIE GROUP =====
        self.MOVIE_GROUP_LINK = os.getenv('MOVIE_GROUP_LINK', 'https://t.me/asfilter_group')
        self.MOVIE_GROUP_ID = os.getenv('MOVIE_GROUP_ID', '-1003193018012')
        
        # ===== OTHER GROUPS =====
        self.ALL_GROUPS_LINK = os.getenv('ALL_GROUPS_LINK', 'https://t.me/addlist/6urdhhdLRqhiZmQ1')
        
        # ===== SUPPORT =====
        self.SUPPORT_USERNAME = os.getenv('SUPPORT_USERNAME', '@asbhaibsr')
        
        # ===== WEBAPP URLS =====
        self.WEBAPP_URL = os.getenv('WEBAPP_URL')
        if not self.WEBAPP_URL:
            logger.warning("⚠️ WEBAPP_URL not configured. Mini App will not work properly.")
        
        self.WEBHOOK_URL = os.getenv('WEBHOOK_URL')
        
        # ===== MONGODB CONFIGURATION =====
        self.MONGODB_URI = os.getenv('MONGODB_URI')
        if not self.MONGODB_URI:
            logger.error("❌ MONGODB_URI not found in environment variables")
            raise ValueError("MONGODB_URI is required")
        
        self.MONGODB_DB = os.getenv('MONGODB_DB', 'filmyfund_bot')
        
        # ===== BONUS AMOUNTS =====
        try:
            self.REFERRAL_BONUS = float(os.getenv('REFERRAL_BONUS', '0.40'))
        except ValueError:
            logger.warning("⚠️ Invalid REFERRAL_BONUS, using default 0.40")
            self.REFERRAL_BONUS = 0.40
        
        try:
            self.DAILY_REFERRAL_EARNING = float(os.getenv('DAILY_REFERRAL_EARNING', '0.30'))
        except ValueError:
            logger.warning("⚠️ Invalid DAILY_REFERRAL_EARNING, using default 0.30")
            self.DAILY_REFERRAL_EARNING = 0.30
        
        try:
            self.DAILY_BONUS = float(os.getenv('DAILY_BONUS', '0.05'))
        except ValueError:
            logger.warning("⚠️ Invalid DAILY_BONUS, using default 0.05")
            self.DAILY_BONUS = 0.05
        
        try:
            self.MIN_WITHDRAWAL = float(os.getenv('MIN_WITHDRAWAL', '20.0'))
        except ValueError:
            logger.warning("⚠️ Invalid MIN_WITHDRAWAL, using default 20.0")
            self.MIN_WITHDRAWAL = 20.0
        
        # ===== ANTI-CHEAT SETTINGS =====
        try:
            self.MAX_SEARCHES_PER_DAY = int(os.getenv('MAX_SEARCHES_PER_DAY', '1'))
        except ValueError:
            logger.warning("⚠️ Invalid MAX_SEARCHES_PER_DAY, using default 1")
            self.MAX_SEARCHES_PER_DAY = 1
        
        try:
            self.MIN_TIME_BETWEEN_SEARCHES = int(os.getenv('MIN_TIME_BETWEEN_SEARCHES', '300'))
        except ValueError:
            logger.warning("⚠️ Invalid MIN_TIME_BETWEEN_SEARCHES, using default 300")
            self.MIN_TIME_BETWEEN_SEARCHES = 300
        
        # ===== TIER CONFIGURATION =====
        self.TIERS = {
            1: {'name': '🥉 BASIC', 'rate': 0.20, 'required_refs': 0},
            2: {'name': '🥈 SILVER', 'rate': 0.30, 'required_refs': 50},
            3: {'name': '🥇 GOLD', 'rate': 0.40, 'required_refs': 100},
            4: {'name': '💎 DIAMOND', 'rate': 0.50, 'required_refs': 200},
            5: {'name': '👑 PLATINUM', 'rate': 0.75, 'required_refs': 500}
        }
        
        # ===== SERVER CONFIGURATION =====
        try:
            self.PORT = int(os.getenv('PORT', '10000'))
        except ValueError:
            logger.warning("⚠️ Invalid PORT, using default 10000")
            self.PORT = 10000
        
        self.ENVIRONMENT = os.getenv('ENVIRONMENT', 'production')
        
        # ===== FLASK SECRET =====
        self.FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'filmyfund-secret-key-2024')
        
        self._log_config_summary()
    
    def _log_config_summary(self):
        """Log configuration summary"""
        logger.info("📝 Configuration loaded:")
        logger.info(f"  • Bot Username: @{self.BOT_USERNAME}")
        logger.info(f"  • Admin IDs: {self.ADMIN_IDS}")
        logger.info(f"  • Environment: {self.ENVIRONMENT}")
        logger.info(f"  • WebApp URL: {self.WEBAPP_URL}")
        logger.info(f"  • MongoDB DB: {self.MONGODB_DB}")
        logger.info(f"  • Daily Bonus: ₹{self.DAILY_BONUS}")
        logger.info(f"  • Min Withdrawal: ₹{self.MIN_WITHDRAWAL}")
    
    def get_tier_name(self, tier):
        """Get tier name by tier number"""
        if not isinstance(tier, (int, float)):
            tier = 1
        tier = int(tier)
        return self.TIERS.get(tier, self.TIERS[1])['name']
    
    def get_tier_rate(self, tier):
        """Get tier rate by tier number"""
        if not isinstance(tier, (int, float)):
            tier = 1
        tier = int(tier)
        return self.TIERS.get(tier, self.TIERS[1])['rate']
    
    def calculate_tier(self, active_refs):
        """Calculate user tier based on active referrals"""
        if not isinstance(active_refs, (int, float)):
            active_refs = 0
        active_refs = int(active_refs)
        
        tier = 1
        for t_num, t_config in sorted(self.TIERS.items()):
            if active_refs >= t_config['required_refs']:
                tier = t_num
            else:
                break
        return tier
    
    def is_admin(self, user_id):
        """Check if user is admin"""
        try:
            return int(user_id) in self.ADMIN_IDS
        except (ValueError, TypeError):
            return False
