# utils.py
import re
from datetime import datetime
from telegram import Bot
from config import Config

def is_admin(user_id):
    """चेक करें कि यूजर एडमिन है या नहीं"""
    return user_id in Config.ADMIN_IDS

def get_referral_link(bot_username, user_id):
    """रेफरल लिंक जनरेट करें"""
    return f"https://t.me/{bot_username}?start=ref_{user_id}"

def format_balance(amount):
    """बैलेंस को फॉर्मेट करें"""
    return f"₹{amount:.2f}"

def get_tier_from_refs(refs):
    """रेफरल के हिसाब से टीयर निकालें"""
    for tier, config in sorted(Config.TIERS.items(), key=lambda x: x[1]["min_refs"], reverse=True):
        if refs >= config["min_refs"]:
            return tier
    return 1

def get_tier_name(tier):
    """टीयर का नाम प्राप्त करें"""
    return Config.TIERS.get(tier, {}).get("name", f"टीयर {tier}")

def escape_markdown(text):
    """मार्कडाउन टेक्स्ट को एस्केप करें"""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', str(text))

async def check_channel_membership(bot: Bot, user_id: int, channel: str):
    """चेक करें कि यूजर चैनल में है या नहीं"""
    try:
        # चैनल यूजरनेम से @ हटाएं
        if channel.startswith('@'):
            chat_id = channel
        else:
            chat_id = f"@{channel}"
        
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        # अगर चैनल प्राइवेट है या कोई एरर है
        return False

def generate_spin_result():
    """स्पिन रिजल्ट जनरेट करें (वेटेड रैंडम)"""
    import random
    return random.choices(Config.SPIN_PRIZES, weights=Config.SPIN_WEIGHTS)[0]

def get_daily_bonus(streak):
    """डेली बोनस कैलकुलेट करें"""
    return Config.DAILY_BONUS_BASE + (streak * Config.DAILY_BONUS_INCREMENT)

def time_ago(timestamp):
    """टाइमस्टैम्प से 'कितना समय पहले' बनाएं"""
    if not timestamp:
        return "कभी नहीं"
    
    diff = datetime.now() - timestamp
    
    if diff.days > 365:
        return f"{diff.days // 365} साल पहले"
    if diff.days > 30:
        return f"{diff.days // 30} महीने पहले"
    if diff.days > 0:
        return f"{diff.days} दिन पहले"
    if diff.seconds > 3600:
        return f"{diff.seconds // 3600} घंटे पहले"
    if diff.seconds > 60:
        return f"{diff.seconds // 60} मिनट पहले"
    return "अभी अभी"

def chunk_list(lst, size):
    """लिस्ट को छोटे-छोटे चंक्स में बांटें"""
    return [lst[i:i + size] for i in range(0, len(lst), size)]

def get_earning_rate(tier):
    """टीयर के हिसाब से कमाई रेट प्राप्त करें"""
    return Config.TIERS.get(tier, {}).get("rate", Config.REFERRAL_RATE)

def generate_user_stats_text(stats):
    """यूजर स्टैट्स को टेक्स्ट में बदलें"""
    return (
        f"👤 *आपका प्रोफाइल*\n\n"
        f"💰 *बैलेंस:* {format_balance(stats['balance'])}\n"
        f"🎰 *स्पिन:* {stats['spins']}\n"
        f"👑 *टीयर:* {stats['tier_name']} ({stats['tier_rate']}/सर्च)\n"
        f"👥 *कुल रेफरल:* {stats['total_refs']}\n"
        f"✅ *एक्टिव:* {stats['active_refs']}\n"
        f"⏳ *पेंडिंग:* {stats['pending_refs']}\n"
        f"📅 *मंथली:* {stats['monthly_refs']}\n"
        f"🔥 *डेली स्ट्रीक:* {stats['daily_streak']} दिन"
    )
