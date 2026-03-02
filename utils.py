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
        """Generate unique referral code"""
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"{user_id}{random_str}"
    
    def validate_upi_id(self, upi_id):
        """Validate UPI ID format"""
        pattern = r'^[a-zA-Z0-9._-]+@[a-zA-Z0-9]+$'
        return bool(re.match(pattern, upi_id))
    
    def validate_bank_details(self, details):
        """Basic bank details validation"""
        # Check if it has account number and IFSC
        return len(details.split()) >= 3
    
    def format_number(self, num):
        """Format number with commas"""
        return "{:,}".format(num)
    
    def time_ago(self, timestamp):
        """Convert timestamp to time ago string"""
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
        """Calculate progress to next tier"""
        current_tier = user.get('tier', 1)
        active_refs = user.get('active_refs', 0)
        
        next_tier = current_tier + 1
        required = self.config.get_tier_requirements(next_tier)
        
        if required == 0:
            return 100, "MAX"
        
        progress = min(100, (active_refs / required) * 100)
        return progress, f"{active_refs}/{required}"
    
    def get_daily_bonus_amount(self, streak):
        """Calculate daily bonus based on streak"""
        base = self.config.DAILY_BONUS
        bonus = min(streak * 0.02, 0.10)  # Max extra ₹0.10
        return base + bonus
    
    def is_valid_amount(self, amount):
        """Check if amount is valid"""
        try:
            amount = float(amount)
            return amount > 0 and amount <= 1000000  # Max ₹10L
        except:
            return False
    
    def sanitize_text(self, text):
        """Remove markdown special characters"""
        if not text:
            return ""
        chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    def create_pagination(self, items, page=1, per_page=10):
        """Create paginated response"""
        start = (page - 1) * per_page
        end = start + per_page
        
        return {
            'items': items[start:end],
            'page': page,
            'total': len(items),
            'pages': (len(items) + per_page - 1) // per_page,
            'has_next': end < len(items),
            'has_prev': start > 0
        }
    
    def get_prize_emoji(self, amount):
        """Get emoji for prize amount"""
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
        """Get emoji for tier"""
        emojis = {
            1: "🥉",
            2: "🥈",
            3: "🥇",
            4: "👑",
            5: "💎"
        }
        return emojis.get(tier, "🎯")
    
    def format_transaction(self, transaction):
        """Format transaction for display"""
        type_emoji = {
            'credit': '➕',
            'debit': '➖',
            'spin_win': '🎰',
            'daily_bonus': '🎁',
            'referral_bonus': '👥',
            'channel_bonus': '📢',
            'withdrawal': '💳'
        }
        
        emoji = type_emoji.get(transaction.get('type', 'credit'), '💰')
        amount = transaction.get('amount', 0)
        desc = transaction.get('description', '')
        time = self.time_ago(transaction.get('timestamp', ''))
        
        sign = '+' if amount > 0 else ''
        return f"{emoji} {sign}₹{abs(amount):.2f} - {desc} ({time})"
