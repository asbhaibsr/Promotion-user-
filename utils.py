# utils.py
import re
from datetime import datetime
from telegram import Bot
from config import Config

def is_admin(user_id):
    return user_id in Config.ADMIN_IDS

def get_referral_link(bot_username, user_id):
    return f"https://t.me/{bot_username}?start=ref_{user_id}"

def format_balance(amount):
    return f"₹{amount:.2f}"

def escape_markdown(text):
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', str(text))

async def check_channel_membership(bot: Bot, user_id: int, channel: str):
    try:
        if channel.startswith('@'):
            chat_id = channel
        else:
            chat_id = f"@{channel}"
        
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        return False

def generate_spin_result():
    import random
    prize_data = random.choices(Config.SPIN_PRIZES, weights=Config.SPIN_WEIGHTS)[0]
    return prize_data

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

def chunk_list(lst, size):
    return [lst[i:i + size] for i in range(0, len(lst), size)]

def get_earning_rate(tier):
    return Config.TIERS.get(tier, {}).get("rate", Config.REFERRAL_RATE)
