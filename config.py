# config.py
import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

# === बॉट कॉन्फिग ===
class Config:
    # टोकन और आईडी
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "6357654427").split(",")]
    MONGO_URI = os.getenv("MONGO_URI")
    WEB_APP_URL = os.getenv("WEB_APP_URL", "https://promotion-user.onrender.com")
    PORT = int(os.getenv("PORT", 10000))
    
    # चैनल और ग्रुप
    CHANNEL_USERNAME = "@asbhai_bsr"  # सही यूजरनेम
    CHANNEL_BONUS = 2.0  # चैनल जॉइन बोनस
    MOVIE_GROUP_LINK = "https://t.me/asfilter_group"
    NEW_MOVIE_GROUP_LINK = "https://t.me/asfilter_bot"
    ALL_GROUPS_LINK = "https://t.me/addlist/6urdhhdLRqhiZmQ1"
    
    # बोनस और रेट्स
    WELCOME_BONUS = 5.0
    DAILY_BONUS_BASE = 0.05
    DAILY_BONUS_INCREMENT = 0.02
    MIN_WITHDRAWAL = 50.0
    REFERRAL_RATE = 0.10
    REFERRAL_BONUS = 1  # स्पिन बोनस
    
    # स्पिन व्हील
    SPIN_PRIZES = [0.00, 0.05, 0.10, 0.20, 0.50, 1.00, 2.00, 5.00]
    SPIN_WEIGHTS = [40, 25, 15, 10, 5, 3, 1, 1]
    INITIAL_SPINS = 3
    SPIN_COOLDOWN = timedelta(hours=1)  # 1 घंटे का कूलडाउन
    
    # टीयर सिस्टम (प्रॉफिट के हिसाब से)
    TIERS = {
        1: {"min_refs": 0, "rate": 0.10, "name": "🥉 बेसिक", "bonus": 0},
        2: {"min_refs": 10, "rate": 0.12, "name": "🥈 सिल्वर", "bonus": 5},
        3: {"min_refs": 30, "rate": 0.15, "name": "🥇 गोल्ड", "bonus": 15},
        4: {"min_refs": 70, "rate": 0.18, "name": "👑 प्लेटिनम", "bonus": 30},
        5: {"min_refs": 150, "rate": 0.22, "name": "💎 डायमंड", "bonus": 60},
        6: {"min_refs": 300, "rate": 0.27, "name": "⚡ वीआईपी", "bonus": 120},
    }
    
    # मिशन सिस्टम
    MISSIONS = {
        "daily_search": {"target": 3, "reward": 0.15, "spins": 1},
        "daily_refer": {"target": 2, "reward": 0.50, "spins": 1},
        "daily_bonus": {"target": 1, "reward": 0.10, "spins": 1},
        "weekly_refer": {"target": 10, "reward": 5.0, "spins": 5},
    }
    
    # लीडरबोर्ड रिवॉर्ड्स
    LEADERBOARD_REWARDS = {
        1: {"reward": 150, "min_refs": 50},
        2: {"reward": 100, "min_refs": 40},
        3: {"reward": 75, "min_refs": 30},
        4: {"reward": 50, "min_refs": 25},
        5: {"reward": 40, "min_refs": 20},
        6: {"reward": 30, "min_refs": 15},
        7: {"reward": 25, "min_refs": 12},
        8: {"reward": 20, "min_refs": 10},
        9: {"reward": 15, "min_refs": 8},
        10: {"reward": 10, "min_refs": 5},
    }
    
    # एडमिन सेटिंग्स
    ADMIN_COMMANDS = ["/admin", "/broadcast", "/stats", "/add", "/remove", "/block", "/unblock"]
    
    # एडवांस फीचर्स
    ENABLE_ADS = True
    AD_PRICE_PER_VIEW = 0.001  # प्रति व्यू कमाई
    REFERRAL_COOLDOWN = timedelta(hours=24)  # रेफरल पेमेंट कूलडाउन
    
    # लॉगिंग
    LOG_LEVEL = "INFO"
    ENABLE_ANALYTICS = True
