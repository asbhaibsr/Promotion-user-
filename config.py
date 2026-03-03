# ===== config.py =====
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot Configuration
    BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
    BOT_USERNAME = os.getenv('BOT_USERNAME', 'YOUR_BOT_USERNAME')
    
    # Admin IDs
    ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '123456789').split(',') if id.strip()]
    
    # Channel Configuration
    CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', '@asbhai_bsr')
    CHANNEL_LINK = os.getenv('CHANNEL_LINK', 'https://t.me/asbhai_bsr')
    CHANNEL_JOIN_BONUS = float(os.getenv('CHANNEL_JOIN_BONUS', 2.0))
    
    # Group Links
    MOVIE_GROUP_LINK = os.getenv('MOVIE_GROUP_LINK', 'https://t.me/asfilter_bot')
    NEW_GROUP_LINK = os.getenv('NEW_GROUP_LINK', 'https://t.me/asfilter_group')
    ALL_GROUPS_LINK = os.getenv('ALL_GROUPS_LINK', 'https://t.me/addlist/6urdhhdLRqhiZmQ1')
    
    # Support
    SUPPORT_USERNAME = os.getenv('SUPPORT_USERNAME', '@support')
    
    # WebApp URLs
    WEBAPP_URL = os.getenv('WEBAPP_URL', 'https://your-app.onrender.com')
    WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://your-app.onrender.com')
    
    # MongoDB Configuration
    MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
    MONGODB_DB = os.getenv('MONGODB_DB', 'filmyfund_bot')
    
    # Bonus Amounts
    REFERRAL_BONUS = float(os.getenv('REFERRAL_BONUS', 5.0))
    DAILY_BONUS = float(os.getenv('DAILY_BONUS', 0.05))
    MIN_WITHDRAWAL = float(os.getenv('MIN_WITHDRAWAL', 50.0))
    
    # Tier Configuration
    TIERS = {
        1: {'name': 'BASIC', 'rate': 0.10, 'required_refs': 0},
        2: {'name': 'SILVER', 'rate': 0.12, 'required_refs': 10},
        3: {'name': 'GOLD', 'rate': 0.15, 'required_refs': 30},
        4: {'name': 'DIAMOND', 'rate': 0.22, 'required_refs': 150},
        5: {'name': 'PLATINUM', 'rate': 0.30, 'required_refs': 500}
    }
    
    # Server
    PORT = int(os.getenv('PORT', 8080))
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'production')
    
    def get_tier_name(self, tier):
        return self.TIERS.get(tier, {}).get('name', 'BASIC')
    
    def get_tier_rate(self, tier):
        return self.TIERS.get(tier, {}).get('rate', 0.10)
    
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
