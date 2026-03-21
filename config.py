# ===== config.py (FULLY UPDATED) =====

import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class Config:
    def __init__(self):
        # BOT
        self.BOT_TOKEN = os.getenv('BOT_TOKEN')
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required")

        self.BOT_USERNAME = os.getenv('BOT_USERNAME', 'LinkProviderRobot')

        # ADMINS
        admin_ids_str = os.getenv('ADMIN_IDS', '')
        try:
            self.ADMIN_IDS = [int(i.strip()) for i in admin_ids_str.split(',') if i.strip()]
        except ValueError:
            self.ADMIN_IDS = []

        # LOG CHANNEL
        log_ch = os.getenv('LOG_CHANNEL_ID')
        try:
            self.LOG_CHANNEL_ID = int(log_ch) if log_ch else None
        except:
            self.LOG_CHANNEL_ID = None

        # CHANNEL
        self.CHANNEL_ID        = os.getenv('CHANNEL_ID', '-1002283182645')
        self.CHANNEL_LINK      = os.getenv('CHANNEL_LINK', 'https://t.me/asbhai_bsr')
        self.CHANNEL_JOIN_BONUS = float(os.getenv('CHANNEL_JOIN_BONUS', '2.0'))

        # MOVIE GROUP
        self.MOVIE_GROUP_LINK  = os.getenv('MOVIE_GROUP_LINK', 'https://t.me/asfilter_group')
        self.MOVIE_GROUP_ID    = os.getenv('MOVIE_GROUP_ID', '-1003193018012')
        self.ALL_GROUPS_LINK   = os.getenv('ALL_GROUPS_LINK', 'https://t.me/addlist/6urdhhdLRqhiZmQ1')

        # SUPPORT
        self.SUPPORT_USERNAME  = os.getenv('SUPPORT_USERNAME', '@asbhaibsr')

        # WEBAPP
        self.WEBAPP_URL  = os.getenv('WEBAPP_URL')
        self.WEBHOOK_URL = os.getenv('WEBHOOK_URL')

        # MONGODB
        self.MONGODB_URI = os.getenv('MONGODB_URI')
        if not self.MONGODB_URI:
            raise ValueError("MONGODB_URI is required")
        self.MONGODB_DB = os.getenv('MONGODB_DB', 'filmyfund_bot')

        # EARNINGS — UPDATED
        self.REFERRAL_BONUS          = float(os.getenv('REFERRAL_BONUS', '0.60'))       # ₹0.60 per activation
        self.DAILY_REFERRAL_EARNING  = float(os.getenv('DAILY_REFERRAL_EARNING', '0.30')) # ₹0.30 per daily search
        self.DAILY_BONUS             = float(os.getenv('DAILY_BONUS', '0.05'))           # Base daily bonus
        self.MIN_WITHDRAWAL          = float(os.getenv('MIN_WITHDRAWAL', '20.0'))        # Min ₹20

        # ANTI-CHEAT
        self.MAX_SEARCHES_PER_DAY      = int(os.getenv('MAX_SEARCHES_PER_DAY', '1'))
        self.MIN_TIME_BETWEEN_SEARCHES = int(os.getenv('MIN_TIME_BETWEEN_SEARCHES', '300'))

        # TIERS
        self.TIERS = {
            1: {'name': '🥉 BASIC',   'rate': 0.30, 'required_refs': 0},
            2: {'name': '🥈 SILVER',  'rate': 0.40, 'required_refs': 50},
            3: {'name': '🥇 GOLD',    'rate': 0.50, 'required_refs': 100},
            4: {'name': '💎 DIAMOND', 'rate': 0.75, 'required_refs': 200},
        }

        # SERVER
        self.PORT             = int(os.getenv('PORT', '10000'))
        self.ENVIRONMENT      = os.getenv('ENVIRONMENT', 'production')
        self.FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'filmyfund-secret-2025')

        logger.info(f"✅ Config loaded | Bot: @{self.BOT_USERNAME} | Admins: {self.ADMIN_IDS}")

    def get_tier_name(self, tier):
        try:
            return self.TIERS.get(int(tier), self.TIERS[1])['name']
        except:
            return self.TIERS[1]['name']

    def get_tier_rate(self, tier):
        try:
            return self.TIERS.get(int(tier), self.TIERS[1])['rate']
        except:
            return self.TIERS[1]['rate']

    def calculate_tier(self, active_refs):
        try:
            active_refs = int(active_refs)
        except:
            active_refs = 0
        tier = 1
        for t_num, t_cfg in sorted(self.TIERS.items()):
            if active_refs >= t_cfg['required_refs']:
                tier = t_num
            else:
                break
        return tier

    def is_admin(self, user_id):
        try:
            return int(user_id) in self.ADMIN_IDS
        except:
            return False
