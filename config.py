# config.py - सारी सेटिंग्स

import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # === टोकन और आईडी ===
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "7315805581").split(",")]
    MONGO_URI = os.getenv("MONGO_URI")
    WEB_APP_URL = os.getenv("WEB_APP_URL", "https://promotion-user.onrender.com")
    PORT = int(os.getenv("PORT", 10000))
    
    # === चैनल और ग्रुप ===
    CHANNEL_USERNAME = "@asbhai_bsr"
    CHANNEL_LINK = "https://t.me/asbhai_bsr"
    CHANNEL_ID = -1002283182645
    CHANNEL_BONUS = 2.0
    
    MOVIE_GROUP_LINK = "https://t.me/asfilter_group"
    NEW_MOVIE_GROUP_LINK = "https://t.me/asfilter_bot"
    MOVIE_GROUP_ID = -1003193018012
    
    # === बोनस और रेट्स ===
    WELCOME_BONUS = 5.0
    DAILY_BONUS_BASE = 0.05
    DAILY_BONUS_INCREMENT = 0.02
    MIN_WITHDRAWAL = 50.0
    REFERRAL_RATE = 0.10
    REFERRAL_BONUS = 1  # spins
    
    # === स्पिन व्हील - सिंपल प्राइज ===
    SPIN_PRIZES = [
        {"value": 0.00, "color": "#ff6b6b", "name": "TRY AGAIN"},
        {"value": 0.05, "color": "#4ecdc4", "name": "5 PAISE"},
        {"value": 0.10, "color": "#ffe66d", "name": "10 PAISE"},
        {"value": 0.20, "color": "#ff9f1c", "name": "20 PAISE"},
        {"value": 0.50, "color": "#c77dff", "name": "50 PAISE"},
        {"value": 1.00, "color": "#ff99c8", "name": "₹1"},
        {"value": 2.00, "color": "#6c5ce7", "name": "₹2"},
        {"value": 5.00, "color": "#00cec9", "name": "₹5 JACKPOT"}
    ]
    SPIN_WEIGHTS = [40, 25, 15, 10, 5, 3, 1, 1]
    INITIAL_SPINS = 3
    SPIN_COOLDOWN = timedelta(hours=1)
    
    # === टीयर सिस्टम ===
    TIERS = {
        1: {"min_refs": 0, "rate": 0.10, "name": "🥉 BASIC", "bonus": 0},
        2: {"min_refs": 10, "rate": 0.12, "name": "🥈 SILVER", "bonus": 5},
        3: {"min_refs": 30, "rate": 0.15, "name": "🥇 GOLD", "bonus": 15},
        4: {"min_refs": 70, "rate": 0.18, "name": "👑 PLATINUM", "bonus": 30},
        5: {"min_refs": 150, "rate": 0.22, "name": "💎 DIAMOND", "bonus": 60},
        6: {"min_refs": 300, "rate": 0.27, "name": "⚡ VIP", "bonus": 120},
    }
    
    # === मिशन सिस्टम ===
    MISSIONS = {
        "daily_search": {"target": 3, "reward": 0.15, "spins": 1, "name": "🔍 SEARCH", "icon": "🔍"},
        "daily_refer": {"target": 2, "reward": 0.50, "spins": 1, "name": "👥 REFER", "icon": "👥"},
        "daily_bonus": {"target": 1, "reward": 0.10, "spins": 1, "name": "📅 DAILY", "icon": "📅"},
    }
    
    # === लीडरबोर्ड रिवॉर्ड्स ===
    LEADERBOARD_REWARDS = {
        1: {"reward": 300, "min_refs": 50},
        2: {"reward": 200, "min_refs": 35},
        3: {"reward": 100, "min_refs": 15},
        4: {"reward": 50, "min_refs": 5},
        5: {"reward": 50, "min_refs": 5},
        6: {"reward": 50, "min_refs": 5},
        7: {"reward": 50, "min_refs": 5},
        8: {"reward": 50, "min_refs": 5},
        9: {"reward": 50, "min_refs": 5},
        10: {"reward": 50, "min_refs": 5},
    }
    
    # === एडमिन कमांड्स ===
    ADMIN_COMMANDS = ["/admin", "/broadcast", "/stats", "/add", "/remove", "/check", "/clear"]
    
    # === लॉगिंग ===
    LOG_LEVEL = "INFO"
