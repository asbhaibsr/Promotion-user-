import os
from dotenv import load_dotenv

load_dotenv()

# === BOT CONFIG ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
MONGO_URI = os.getenv("MONGO_URI")
PORT = int(os.getenv("PORT", 8000))
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://promotion-user.onrender.com")

# === GROUP LINKS ===
MOVIE_GROUP_LINK = "https://t.me/asfilter_group"
NEW_MOVIE_GROUP_LINK = "https://t.me/asfilter_bot"
ALL_GROUPS_LINK = "https://t.me/addlist/6urdhhdLRqhiZmQ1"

# === CHANNELS ===
FORCE_JOIN_CHANNELS = [-1002283182645]  # अपनी चैनल ID डालें
PRIVATE_CHANNELS = [-1002892671107]     # प्राइवेट चैनल ID
REQUEST_MODE = True

# === BONUS & RATES ===
WELCOME_BONUS = 5.0
DAILY_BONUS_BASE = 0.05
REFERRAL_RATE = 0.10
MIN_WITHDRAWAL = 50.0

# === SPIN WHEEL ===
SPIN_PRIZES = [0.00, 0.05, 0.10, 0.20, 0.50, 1.00]
SPIN_WEIGHTS = [50, 20, 15, 10, 4, 1]
INITIAL_SPINS = 3

# === TIERS ===
TIERS = {
    1: {"min": 0, "rate": 0.10, "name": "🥉 Beginner"},
    2: {"min": 100, "rate": 0.12, "name": "🥈 Pro"},
    3: {"min": 300, "rate": 0.15, "name": "🥇 Expert"},
    4: {"min": 800, "rate": 0.18, "name": "👑 Master"},
    5: {"min": 2000, "rate": 0.20, "name": "💎 Legend"}
}

# === LEADERBOARD REWARDS ===
LEADERBOARD = {
    1: {"reward": 150, "min_refs": 50},
    2: {"reward": 100, "min_refs": 30},
    3: {"reward": 50, "min_refs": 30},
    4: {"reward": 25, "min_refs": 20},
    5: {"reward": 25, "min_refs": 20},
    (6, 10): {"reward": 5, "min_refs": 10}
}
