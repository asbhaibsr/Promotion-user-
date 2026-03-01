# utils.py - हेल्पर फंक्शन्स

import re
from datetime import datetime
from config import Config

def is_admin(user_id):
    return user_id in Config.ADMIN_IDS

def get_referral_link(user_id):
    return f"https://t.me/LinkProviderRobot?start=ref_{user_id}"

def format_balance(amount):
    return f"₹{amount:.2f}"

def escape_markdown(text):
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', str(text))

def time_ago(timestamp):
    if not timestamp:
        return "Never"
    
    diff = datetime.now() - timestamp
    
    if diff.days > 365:
        return f"{diff.days // 365} years ago"
    if diff.days > 30:
        return f"{diff.days // 30} months ago"
    if diff.days > 0:
        return f"{diff.days} days ago"
    if diff.seconds > 3600:
        return f"{diff.seconds // 3600} hours ago"
    if diff.seconds > 60:
        return f"{diff.seconds // 60} minutes ago"
    return "Just now"

def get_earning_rate(tier):
    return Config.TIERS.get(tier, {}).get("rate", Config.REFERRAL_RATE)
