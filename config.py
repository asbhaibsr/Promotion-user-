# ===== config.py =====
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot Configuration
    BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
    BOT_USERNAME = os.getenv('BOT_USERNAME', 'YOUR_BOT_USERNAME')
    
    # Admin IDs (comma separated)
    ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '123456789').split(',') if id.strip()]
    
    # LOG CHANNEL - Bot will send all logs here
    LOG_CHANNEL_ID = os.getenv('LOG_CHANNEL_ID', '-1001234567890')  # Channel ID for logs
    
    # Channel Configuration for Join Bonus
    CHANNELS = {
        'main': {
            'id': os.getenv('CHANNEL_ID', '@your_channel'),
            'link': os.getenv('CHANNEL_LINK', 'https://t.me/your_channel'),
            'bonus': float(os.getenv('CHANNEL_JOIN_BONUS', 2.0))
        }
    }
    
    # Group Links
    MOVIE_GROUP_LINK = os.getenv('MOVIE_GROUP_LINK', 'https://t.me/your_group')
    NEW_GROUP_LINK = os.getenv('NEW_GROUP_LINK', 'https://t.me/your_group2')
    ALL_GROUPS_LINK = os.getenv('ALL_GROUPS_LINK', 'https://t.me/addlist/xxxx')
    
    # Support
    SUPPORT_USERNAME = os.getenv('SUPPORT_USERNAME', '@support')
    
    # WebApp URLs
    WEBAPP_URL = os.getenv('WEBAPP_URL', 'https://your-app.onrender.com')
    WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://your-app.onrender.com')
    
    # MongoDB Configuration
    MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb+srv://username:password@cluster.mongodb.net/')
    MONGODB_DB = os.getenv('MONGODB_DB', 'filmyfund_bot')
    
    # Bonus Amounts
    REFERRAL_BONUS = float(os.getenv('REFERRAL_BONUS', 5.0))  # One-time welcome bonus
    DAILY_REFERRAL_EARNING = float(os.getenv('DAILY_REFERRAL_EARNING', 0.30))  # Daily per active referral
    DAILY_BONUS = float(os.getenv('DAILY_BONUS', 0.05))
    MIN_WITHDRAWAL = float(os.getenv('MIN_WITHDRAWAL', 50.0))
    
    # Tier Configuration (Per Search/Referral Earnings)
    TIERS = {
        1: {'name': '🥉 BASIC', 'rate': 0.30, 'required_refs': 0},
        2: {'name': '🥈 SILVER', 'rate': 0.35, 'required_refs': 10},
        3: {'name': '🥇 GOLD', 'rate': 0.40, 'required_refs': 30},
        4: {'name': '💎 DIAMOND', 'rate': 0.50, 'required_refs': 100},
        5: {'name': '👑 PLATINUM', 'rate': 0.75, 'required_refs': 500}
    }
    
    # Missions Configuration
    MISSIONS = {
        1: {'name': '🚀 Beginner', 'requirements': {'referrals': 3, 'searches': 5, 'daily_streak': 3}, 'reward': 2.0},
        2: {'name': '🌟 Active', 'requirements': {'referrals': 10, 'searches': 20, 'daily_streak': 7}, 'reward': 5.0},
        3: {'name': '💪 Pro', 'requirements': {'referrals': 25, 'searches': 50, 'daily_streak': 15}, 'reward': 12.0},
        4: {'name': '🏆 Legend', 'requirements': {'referrals': 50, 'searches': 100, 'daily_streak': 30}, 'reward': 25.0}
    }
    
    # Leaderboard Rewards (Weekly)
    LEADERBOARD_REWARDS = {
        1: {'rank': 1, 'reward': 200.0, 'required_active': 50},
        2: {'rank': 2, 'reward': 200.0, 'required_active': 50},
        3: {'rank': 3, 'reward': 200.0, 'required_active': 50},
        4: {'rank': '4-10', 'reward': 50.0, 'required_active': 25}
    }
    
    # Server
    PORT = int(os.getenv('PORT', 8080))
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'production')
    
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
