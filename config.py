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
    ALL_GROUPS_LINK = "https://t.me/addlist/6urdhhdLRqhiZmQ1"
    
    # === बोनस और रेट्स ===
    WELCOME_BONUS = 5.0
    DAILY_BONUS_BASE = 0.05
    DAILY_BONUS_INCREMENT = 0.02
    MIN_WITHDRAWAL = 50.0
    REFERRAL_RATE = 0.10
    REFERRAL_BONUS = 1  # spins
    
    # === स्पिन व्हील - प्राइजेज ===
    SPIN_PRIZES = [
        {"value": 0.00, "angle": 0, "name": "TRY AGAIN"},
        {"value": 0.05, "angle": 45, "name": "5 PAISE"},
        {"value": 0.10, "angle": 90, "name": "10 PAISE"},
        {"value": 0.20, "angle": 135, "name": "20 PAISE"},
        {"value": 0.50, "angle": 180, "name": "50 PAISE"},
        {"value": 1.00, "angle": 225, "name": "₹1"},
        {"value": 2.00, "angle": 270, "name": "₹2"},
        {"value": 5.00, "angle": 315, "name": "₹5 JACKPOT"}
    ]
    SPIN_WEIGHTS = [40, 25, 15, 10, 5, 3, 1, 1]
    INITIAL_SPINS = 3
    SPIN_COOLDOWN = timedelta(hours=1)
    
    # === टीयर सिस्टम ===
    TIERS = {
        1: {"min_refs": 0, "rate": 0.10, "name": "🥉 BASIC"},
        2: {"min_refs": 10, "rate": 0.12, "name": "🥈 SILVER"},
        3: {"min_refs": 30, "rate": 0.15, "name": "🥇 GOLD"},
        4: {"min_refs": 70, "rate": 0.18, "name": "👑 PLATINUM"},
        5: {"min_refs": 150, "rate": 0.22, "name": "💎 DIAMOND"},
        6: {"min_refs": 300, "rate": 0.27, "name": "⚡ VIP"},
    }
    
    # === मिशन सिस्टम ===
    MISSIONS = {
        "daily_search": {"target": 3, "reward": 0.15, "spins": 1, "name": "🔍 SEARCH"},
        "daily_refer": {"target": 2, "reward": 0.50, "spins": 1, "name": "👥 REFER"},
        "daily_bonus": {"target": 1, "reward": 0.10, "spins": 1, "name": "📅 DAILY"},
    }
    
    # === एडमिन कमांड्स ===
    ADMIN_COMMANDS = ["/admin", "/broadcast", "/stats", "/add", "/remove", "/check", "/clear"]
    
    # === लॉगिंग ===
    LOG_LEVEL = "INFO"
