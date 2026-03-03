# ===== utils.py =====
import logging
import random
import string
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)

class Utils:
    def __init__(self, config, db):
        self.config = config
        self.db = db
    
    def generate_referral_code(self, user_id):
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"{user_id}{random_str}"
    
    def validate_upi_id(self, upi_id):
        pattern = r'^[a-zA-Z0-9._-]+@[a-zA-Z0-9]+$'
        return bool(re.match(pattern, upi_id))
    
    def validate_bank_details(self, details):
        return len(details.split()) >= 3
    
    def format_number(self, num):
        return "{:,}".format(num)
    
    def time_ago(self, timestamp):
        if not timestamp:
            return "Never"
        
        try:
            dt = datetime.fromisoformat(timestamp)
            now = datetime.now()
            diff = now - dt
            
            if diff.days > 365:
                return f"{diff.days // 365} years ago"
            elif diff.days > 30:
                return f"{diff.days // 30} months ago"
            elif diff.days > 0:
                return f"{diff.days} days ago"
            elif diff.seconds > 3600:
                return f"{diff.seconds // 3600} hours ago"
            elif diff.seconds > 60:
                return f"{diff.seconds // 60} minutes ago"
            else:
                return "Just now"
        except:
            return "Unknown"
    
    def calculate_tier_progress(self, user):
        current_tier = user.get('tier', 1)
        active_refs = user.get('active_refs', 0)
        
        next_tier = current_tier + 1
        required = self.config.get_tier_requirements(next_tier)
        
        if required == 0:
            return 100, "MAX"
        
        progress = min(100, (active_refs / required) * 100)
        return progress, f"{active_refs}/{required}"
    
    def get_daily_bonus_amount(self, streak):
        base = self.config.DAILY_BONUS
        bonus = min(streak * 0.02, 0.10)
        return base + bonus
    
    def is_valid_amount(self, amount):
        try:
            amount = float(amount)
            return amount > 0 and amount <= 1000000
        except:
            return False
    
    def sanitize_text(self, text):
        if not text:
            return ""
        chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    def get_prize_emoji(self, amount):
        if amount >= 5:
            return "🏆 JACKPOT!"
        elif amount >= 2:
            return "🎊 BIG WIN!"
        elif amount >= 1:
            return "🎉 GREAT!"
        elif amount >= 0.5:
            return "🎈 GOOD!"
        elif amount > 0:
            return "✨ NICE!"
        else:
            return "😢 TRY AGAIN"
    
    def get_tier_emoji(self, tier):
        emojis = {
            1: "🥉",
            2: "🥈",
            3: "🥇",
            4: "👑",
            5: "💎"
        }
        return emojis.get(tier, "🎯")
