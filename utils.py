# utils.py - हेल्पर फंक्शन्स

import re
from datetime import datetime
from config import Config

def is_admin(user_id):
    return user_id in Config.ADMIN_IDS

def format_balance(amount):
    return f"₹{amount:.2f}"

def escape_markdown(text):
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', str(text))
