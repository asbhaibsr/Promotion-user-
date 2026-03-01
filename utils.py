# utils.py - Helper Functions

import re
from datetime import datetime
from config import Config

def is_admin(user_id):
    """Check if user is admin"""
    return user_id in Config.ADMIN_IDS

def format_balance(amount):
    """Format balance with ₹ symbol"""
    return f"₹{amount:.2f}"

def escape_markdown(text):
    """Escape Markdown special characters"""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', str(text))

def format_number(num):
    """Format large numbers with K, M suffix"""
    if num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num/1_000:.1f}K"
    return str(num)

def get_time_ago(timestamp):
    """Get human readable time ago"""
    if not timestamp:
        return "Never"
    
    delta = datetime.now() - timestamp
    
    if delta.days > 365:
        years = delta.days // 365
        return f"{years} year{'s' if years>1 else ''} ago"
    elif delta.days > 30:
        months = delta.days // 30
        return f"{months} month{'s' if months>1 else ''} ago"
    elif delta.days > 0:
        return f"{delta.days} day{'s' if delta.days>1 else ''} ago"
    elif delta.seconds > 3600:
        hours = delta.seconds // 3600
        return f"{hours} hour{'s' if hours>1 else ''} ago"
    elif delta.seconds > 60:
        minutes = delta.seconds // 60
        return f"{minutes} minute{'s' if minutes>1 else ''} ago"
    else:
        return f"{delta.seconds} second{'s' if delta.seconds>1 else ''} ago"

def generate_transaction_id():
    """Generate unique transaction ID"""
    from datetime import datetime
    import random
    
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_part = random.randint(1000, 9999)
    return f"TXN{timestamp}{random_part}"

def validate_upi(upi_id):
    """Validate UPI ID format"""
    pattern = r'^[a-zA-Z0-9.\-_]{2,}@[a-zA-Z]{2,}$'
    return bool(re.match(pattern, upi_id))

def validate_bank_account(account):
    """Validate bank account number (basic)"""
    return account.isdigit() and 9 <= len(account) <= 18

def sanitize_input(text):
    """Sanitize user input"""
    if not text:
        return ""
    # Remove any potentially harmful characters
    return re.sub(r'[<>"\']', '', text)
