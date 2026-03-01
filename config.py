# config.py - Advanced Configuration 2026

import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # === CORE SETTINGS ===
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "7315805581").split(",")]
    MONGO_URI = os.getenv("MONGO_URI")
    WEB_APP_URL = os.getenv("WEB_APP_URL", "https://promotion-user.onrender.com")
    PORT = int(os.getenv("PORT", 10000))
    
    # === CHANNEL & GROUP ===
    CHANNEL_USERNAME = "@asbhai_bsr"
    CHANNEL_LINK = "https://t.me/asbhai_bsr"
    CHANNEL_ID = -1002283182645
    CHANNEL_BONUS = 2.0
    
    MOVIE_GROUP_LINK = "https://t.me/asfilter_group"
    NEW_MOVIE_GROUP_LINK = "https://t.me/asfilter_bot"
    MOVIE_GROUP_ID = -1003193018012
    
    # === BONUS & RATES ===
    WELCOME_BONUS = 5.0
    DAILY_BONUS_BASE = 0.05
    DAILY_BONUS_INCREMENT = 0.02
    MIN_WITHDRAWAL = 50.0
    REFERRAL_RATE = 0.10
    REFERRAL_BONUS = 1  # spins
    
    # === SPIN WHEEL - PROBABILITY BASED ===
    SPIN_PRIZES = [
        {"value": 0.00, "color": "#ff6b6b", "name": "TRY AGAIN", "weight": 4000},
        {"value": 0.05, "color": "#4ecdc4", "name": "5 PAISE", "weight": 2500},
        {"value": 0.10, "color": "#ffe66d", "name": "10 PAISE", "weight": 1500},
        {"value": 0.20, "color": "#ff9f1c", "name": "20 PAISE", "weight": 1000},
        {"value": 0.50, "color": "#c77dff", "name": "50 PAISE", "weight": 500},
        {"value": 1.00, "color": "#ff99c8", "name": "₹1", "weight": 300},
        {"value": 2.00, "color": "#6c5ce7", "name": "₹2", "weight": 150},
        {"value": 5.00, "color": "#00cec9", "name": "₹5 JACKPOT", "weight": 50}
    ]
    INITIAL_SPINS = 3
    SPIN_COOLDOWN = timedelta(hours=1)
    
    # === TIER SYSTEM ===
    TIERS = {
        1: {"min_refs": 0, "rate": 0.10, "name": "🥉 BASIC", "bonus": 0, "color": "#8B4513"},
        2: {"min_refs": 5, "rate": 0.12, "name": "🥈 SILVER", "bonus": 5, "color": "#C0C0C0"},
        3: {"min_refs": 15, "rate": 0.15, "name": "🥇 GOLD", "bonus": 15, "color": "#FFD700"},
        4: {"min_refs": 30, "rate": 0.18, "name": "👑 PLATINUM", "bonus": 30, "color": "#E5E4E2"},
        5: {"min_refs": 50, "rate": 0.22, "name": "💎 DIAMOND", "bonus": 60, "color": "#B9F2FF"},
        6: {"min_refs": 100, "rate": 0.27, "name": "⚡ VIP", "bonus": 120, "color": "#9400D3"},
    }
    
    # === MISSIONS ===
    MISSIONS = {
        "daily_search": {
            "target": 3, 
            "reward": 0.15, 
            "spins": 1, 
            "name": "MOVIE SEARCH", 
            "icon": "🔍",
            "desc": "Search 3 movies in group"
        },
        "daily_refer": {
            "target": 2, 
            "reward": 0.50, 
            "spins": 1, 
            "name": "REFER FRIENDS", 
            "icon": "👥",
            "desc": "Get 2 active referrals"
        },
        "daily_bonus": {
            "target": 1, 
            "reward": 0.10, 
            "spins": 1, 
            "name": "DAILY CHECK-IN", 
            "icon": "📅",
            "desc": "Claim daily bonus"
        },
        "spin_master": {
            "target": 5, 
            "reward": 0.25, 
            "spins": 2, 
            "name": "SPIN MASTER", 
            "icon": "🎡",
            "desc": "Spin wheel 5 times"
        }
    }
    
    # === LEADERBOARD REWARDS ===
    LEADERBOARD_REWARDS = {
        1: {"reward": 300, "min_refs": 20},
        2: {"reward": 200, "min_refs": 15},
        3: {"reward": 100, "min_refs": 10},
        4: {"reward": 75, "min_refs": 7},
        5: {"reward": 75, "min_refs": 7},
        6: {"reward": 50, "min_refs": 5},
        7: {"reward": 50, "min_refs": 5},
        8: {"reward": 50, "min_refs": 5},
        9: {"reward": 50, "min_refs": 5},
        10: {"reward": 50, "min_refs": 5},
    }
    
    # === LOGGING ===
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # === BOT USERNAME ===
    BOT_USERNAME = "LinkProviderRobot"  # Your bot username without @
