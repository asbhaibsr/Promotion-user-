# ===== config.py (FIXED WITH YOUR STRUCTURE) =====

import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class Config:
    def __init__(self):
        """Initialize all configuration variables with error handling"""
        
        # ===== BOT CONFIGURATION =====
        self.BOT_TOKEN = os.getenv('BOT_TOKEN')
        if not self.BOT_TOKEN:
            logger.error("❌ BOT_TOKEN not found in environment variables")
            raise ValueError("BOT_TOKEN is required")
        
        self.BOT_USERNAME = os.getenv('BOT_USERNAME', 'filmyfund_bot')
        
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
        
        # Log configuration summary
        self._log_config_summary()
    
    def _log_config_summary(self):
        """Log configuration summary for debugging"""
        logger.info("📝 Configuration loaded:")
        logger.info(f"  • Bot Username: @{self.BOT_USERNAME}")
        logger.info(f"  • Admin IDs: {self.ADMIN_IDS}")
        logger.info(f"  • Environment: {self.ENVIRONMENT}")
        logger.info(f"  • WebApp URL: {self.WEBAPP_URL}")
        logger.info(f"  • MongoDB DB: {self.MONGODB_DB}")
        logger.info(f"  • Channel ID: {self.CHANNEL_ID}")
        logger.info(f"  • Channel Link: {self.CHANNEL_LINK}")
        logger.info(f"  • Movie Group ID: {self.MOVIE_GROUP_ID}")
        logger.info(f"  • Movie Group Link: {self.MOVIE_GROUP_LINK}")
        logger.info(f"  • Referral Bonus: ₹{self.REFERRAL_BONUS}")
        logger.info(f"  • Daily Referral Earning: ₹{self.DAILY_REFERRAL_EARNING}")
        logger.info(f"  • Daily Bonus: ₹{self.DAILY_BONUS}")
        logger.info(f"  • Channel Join Bonus: ₹{self.CHANNEL_JOIN_BONUS}")
        logger.info(f"  • Min Withdrawal: ₹{self.MIN_WITHDRAWAL}")
        logger.info(f"  • Max Searches/Day: {self.MAX_SEARCHES_PER_DAY}")
    
    # ===== TIER HELPER METHODS =====
    
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
    
    def get_tier_requirements(self, tier):
        """Get tier requirements by tier number"""
        if not isinstance(tier, (int, float)):
            tier = 1
        tier = int(tier)
        return self.TIERS.get(tier, self.TIERS[1])['required_refs']
    
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
    
    def get_next_tier_info(self, current_tier, active_refs):
        """Get information about next tier"""
        current_tier = int(current_tier) if current_tier else 1
        active_refs = int(active_refs) if active_refs else 0
        
        next_tier_num = current_tier + 1
        if next_tier_num not in self.TIERS:
            return {
                'name': 'MAX TIER',
                'required': 0,
                'remaining': 0,
                'progress': 100,
                'rate_increase': 0
            }
        
        next_tier = self.TIERS[next_tier_num]
        current_rate = self.TIERS[current_tier]['rate']
        
        return {
            'name': next_tier['name'],
            'required': next_tier['required_refs'],
            'remaining': max(0, next_tier['required_refs'] - active_refs),
            'progress': min(100, (active_refs / next_tier['required_refs']) * 100),
            'rate_increase': next_tier['rate'] - current_rate
        }
    
    # ===== ADMIN HELPER =====
    
    def is_admin(self, user_id):
        """Check if user is admin"""
        try:
            return int(user_id) in self.ADMIN_IDS
        except (ValueError, TypeError):
            return False
    
    # ===== VALIDATION METHOD =====
    
    def validate_config(self):
        """Validate all configuration values"""
        errors = []
        warnings = []
        
        # Check required values
        if not self.BOT_TOKEN:
            errors.append("BOT_TOKEN is required")
        
        if not self.MONGODB_URI:
            errors.append("MONGODB_URI is required")
        
        # Check numeric values
        if self.REFERRAL_BONUS <= 0:
            warnings.append("REFERRAL_BONUS should be positive")
        
        if self.DAILY_REFERRAL_EARNING <= 0:
            warnings.append("DAILY_REFERRAL_EARNING should be positive")
        
        if self.MIN_WITHDRAWAL <= 0:
            warnings.append("MIN_WITHDRAWAL should be positive")
        
        if self.MAX_SEARCHES_PER_DAY <= 0:
            warnings.append("MAX_SEARCHES_PER_DAY should be positive")
        
        if self.MIN_TIME_BETWEEN_SEARCHES < 10:
            warnings.append("MIN_TIME_BETWEEN_SEARCHES is very low, may cause spam")
        
        # Check URLs
        if not self.WEBAPP_URL:
            warnings.append("WEBAPP_URL not configured, Mini App may not work")
        
        if self.WEBAPP_URL and not self.WEBAPP_URL.startswith(('http://', 'https://')):
            warnings.append("WEBAPP_URL should start with http:// or https://")
        
        # Check channel IDs
        if self.CHANNEL_ID and not str(self.CHANNEL_ID).startswith(('-100', '@')):
            warnings.append(f"CHANNEL_ID {self.CHANNEL_ID} may be invalid. Should start with -100 or @")
        
        if self.MOVIE_GROUP_ID and not str(self.MOVIE_GROUP_ID).startswith(('-100', '@')):
            warnings.append(f"MOVIE_GROUP_ID {self.MOVIE_GROUP_ID} may be invalid. Should start with -100 or @")
        
        # Return validation result
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }


# ===== CONFIGURATION VALIDATION FUNCTION =====

def validate_and_get_config():
    """Create config instance and validate"""
    try:
        config = Config()
        validation = config.validate_config()
        
        if validation['errors']:
            for error in validation['errors']:
                logger.error(f"❌ Config error: {error}")
            raise ValueError("Configuration validation failed")
        
        if validation['warnings']:
            for warning in validation['warnings']:
                logger.warning(f"⚠️ Config warning: {warning}")
        
        logger.info("✅ Configuration validation passed")
        return config
        
    except Exception as e:
        logger.error(f"❌ Failed to load configuration: {e}")
        raise


# ===== ENVIRONMENT VARIABLES TEMPLATE =====

ENV_TEMPLATE = """
# ===== FILMYFUND BOT ENVIRONMENT VARIABLES =====

# Bot Configuration (REQUIRED)
BOT_TOKEN=YOUR_BOT_TOKEN_HERE
BOT_USERNAME=your_bot_username

# Admin IDs (REQUIRED) - Comma separated
ADMIN_IDS=123456789,987654321

# MongoDB (REQUIRED)
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/
MONGODB_DB=filmyfund_bot

# Channel for Join Bonus
CHANNEL_ID=-1002283182645
CHANNEL_LINK=https://t.me/asbhai_bsr
CHANNEL_JOIN_BONUS=2.0

# Movie Group (where users search)
MOVIE_GROUP_ID=-1003193018012
MOVIE_GROUP_LINK=https://t.me/asfilter_group

# Other Groups
ALL_GROUPS_LINK=https://t.me/addlist/6urdhhdLRqhiZmQ1

# Support
SUPPORT_USERNAME=@asbhaibsr

# WebApp URLs (REQUIRED for Mini App)
WEBAPP_URL=https://your-app.onrender.com
WEBHOOK_URL=https://your-app.onrender.com

# Log Channel (optional)
LOG_CHANNEL_ID=-1001234567890

# Bonus Amounts
REFERRAL_BONUS=5.0
DAILY_REFERRAL_EARNING=0.30
DAILY_BONUS=0.05
MIN_WITHDRAWAL=50.0

# Anti-Cheat Settings
MAX_SEARCHES_PER_DAY=10
MIN_TIME_BETWEEN_SEARCHES=300

# Server
PORT=10000
ENVIRONMENT=production
FLASK_SECRET_KEY=your-secret-key-here
"""


if __name__ == '__main__':
    # If run directly, validate config
    logging.basicConfig(level=logging.INFO)
    print("🔍 Validating configuration...")
    try:
        config = validate_and_get_config()
        print("✅ Configuration is valid!")
        print(f"\n📊 Summary:")
        print(f"  • Bot: @{config.BOT_USERNAME}")
        print(f"  • Admins: {len(config.ADMIN_IDS)} configured")
        print(f"  • Environment: {config.ENVIRONMENT}")
        print(f"  • WebApp: {config.WEBAPP_URL}")
        print(f"  • MongoDB: {config.MONGODB_DB}")
        print(f"  • Channel ID: {config.CHANNEL_ID}")
        print(f"  • Movie Group: {config.MOVIE_GROUP_ID}")
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        print("\n📝 Environment variables template:")
        print(ENV_TEMPLATE)
