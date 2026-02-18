# config.py

import os
from pymongo import MongoClient
from dotenv import load_dotenv
import logging

# Configure basic logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# --- Environment Variables ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
except (TypeError, ValueError, AttributeError):
    ADMIN_ID = None
    logger.warning("ADMIN_ID is not set or invalid. Some features may not work.")

# अपना टेलीग्राम हैंडल (Username) यहां अपडेट करें
YOUR_TELEGRAM_HANDLE = os.getenv("YOUR_TELEGRAM_HANDLE", "telegram") 
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")

# --- ग्रुप और चैनल लिंक्स ---
NEW_MOVIE_GROUP_LINK = "https://t.me/asfilter_bot"
MOVIE_GROUP_LINK = "https://t.me/asfilter_group" 
ALL_GROUPS_LINK = "https://t.me/addlist/6urdhhdLRqhiZmQ1"

EXAMPLE_SCREENSHOT_URL = os.getenv("EXAMPLE_SCREENSHOT_URL", "https://image2url.com/r2/default/images/1771402664534-6f584f3f-b24f-4eac-9d77-bde9ce76cc09.jpg")

# --- चैनल बोनस सेटिंग्स ---
CHANNEL_USERNAME = "@asbhai_bsr"
CHANNEL_ID = -1002283182645
CHANNEL_BONUS = 2.00
# JOIN_CHANNEL_LINK हटा दिया गया - अब डायनामिक बनेगा

WEB_SERVER_URL = os.getenv("WEB_SERVER_URL")
PORT = int(os.getenv("PORT", 8000))

# --- Database Setup ---
try:
    client = MongoClient(MONGO_URI)
    DB = client.get_database('bot_database')
    USERS_COLLECTION = DB.get_collection('users')
    REFERRALS_COLLECTION = DB.get_collection('referrals')
    SETTINGS_COLLECTION = DB.get_collection('settings')
    WITHDRAWALS_COLLECTION = DB.get_collection('withdrawals')
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")

# --- Constants and Configuration ---
DOLLAR_TO_INR = 60.0

# --- डेली बोनस सेटिंग्स ---
DAILY_BONUS_BASE = 0.10
DAILY_BONUS_MULTIPLIER = 0.10 
DAILY_BONUS_STREAK_MULTIPLIER = DAILY_BONUS_MULTIPLIER 

# --- स्पिन व्हील सेटिंग्स ---
PRIZES_WEIGHTS = {
    0.00: 5,
    1.00: 9,
    3.00: 6,
    5.00: 3,
    10.00: 2,
    15.00: 1 
}
SPIN_PRIZES = list(PRIZES_WEIGHTS.keys())
SPIN_WEIGHTS = list(PRIZES_WEIGHTS.values())

SPIN_WHEEL_CONFIG = {
    "initial_free_spins": 3,
    "refer_to_get_spin": 1
}

# --- STICKER IDs ---
HEAD_STICKER_ID = "CAACAgUAAxkBAAEE6e5pC5SKmgOT8kAEa4FZOlQZq6zIEAACVh4AArnGWFQruyw1BLdYfx4E"
TAILS_STICKER_ID = "CAACAgUAAxkBAAEE6eppC5SBTnht6QYudJda5H4h--33rAACJxcAAixZWVSD-vwVuNoh9h4E"
PROCESSING_STICKER_ID = "CAACAgIAAxkBAAEE6fJpC5WmS0rLlh2J82_SsYLf6XA9rAAC9hIAAkvtaEkMpy9dDyb4fR4E"

# --- GAME CONFIGS ---
COIN_FLIP_CONFIG = {
    "win_multiplier": 1.8,
    "min_bet": 0.10,
    "max_bet": 5.00,
    "bet_increment": 0.10 
}

SLOT_MACHINE_CONFIG = {
    "min_bet": 0.10,
    "max_bet": 5.00,
    "bet_increment": 0.10
}

SLOT_SYMBOLS = ["🍒", "🍋", "⭐", "7️⃣", "🔔"]
SLOT_PAYOUTS = {
    "🍒🍒🍒": 0.50,
    "⭐⭐⭐": 1.00, 
    "7️⃣7️⃣7️⃣": 5.00
}

NUMBER_PREDICTION = {
    "entry_fee": [0.10, 0.50, 1.00, 2.00, 5.00],
    "duration": 6,
    "platform_commission": 0.20,
    "number_range": [1, 100]
}
NUMBER_PREDICTION["win_multiplier"] = 80.0

# --- टियर सिस्टम सेटिंग्स ---
TIERS = {
    1: {"min_earnings": 0, "rate": 0.20, "name": "Beginner", "benefits_en": "Basic referral rate (₹0.20)", "benefits_hi": "सामान्य रेफरल दर (₹0.20)"},
    2: {"min_earnings": 200, "rate": 0.35, "name": "Pro", "benefits_en": "Higher referral rate (₹0.35)", "benefits_hi": "उच्च रेफरल दर (₹0.35)"},
    3: {"min_earnings": 500, "rate": 0.45, "name": "Expert", "benefits_en": "Very high referral rate (₹0.45)", "benefits_hi": "बहुत उच्च रेफरल दर (₹0.45)"},
    4: {"min_earnings": 1000, "rate": 0.50, "name": "Master", "benefits_en": "Maximum referral rate (₹0.50)", "benefits_hi": "अधिकतम रेफरल दर (₹0.50)"}
}

# --- WITHDRAWAL METHODS CONFIG ---
WITHDRAWAL_METHODS = {
    "upi": "UPI (GPay/PhonePe/Paytm)",
    "bank": "Bank Account"
}

# --- WITHDRAWAL REQUIREMENTS (नया) ---
WITHDRAWAL_REQUIREMENTS = [
    {"min_balance": 1000.0, "required_refs": 150},
    {"min_balance": 500.0,  "required_refs": 100},
    {"min_balance": 200.0,  "required_refs": 50},
    {"min_balance": 80.0,   "required_refs": 20}
]

# --- LEADERBOARD CONFIG ---
LEADERBOARD_CONFIG = {
    1: {"reward": 300.0, "min_refs": 50},
    2: {"reward": 200.0, "min_refs": 30},
    3: {"reward": 100.0, "min_refs": 30},
    4: {"reward": 50.0,  "min_refs": 30},
    5: {"reward": 50.0,  "min_refs": 30},
    6: {"reward": 10.0,  "min_refs": 30},
    7: {"reward": 10.0,  "min_refs": 30},
    8: {"reward": 10.0,  "min_refs": 30},
    9: {"reward": 10.0,  "min_refs": 30},
    10:{"reward": 10.0,  "min_refs": 30},
}

# --- डेली मिशन सेटिंग्स ---
DAILY_MISSIONS = {
    "search_3_movies": {"reward": 0.60, "target": 3, "name": "Search 3 Movies (Ref. Paid Search)", "name_hi": "3 फिल्में खोजें (रेफ़रल का भुगतान)"}, 
    "refer_2_friends": {"reward": 1.40, "target": 2, "name": "Refer 2 Friends", "name_hi": "2 दोस्तों को रेफ़र करें"},
    "claim_daily_bonus": {"reward": 0.20, "target": 1, "name": "Claim Daily Bonus", "name_hi": "दैनिक बोनस क्लेम करें"}
}

# --- Messages and Text (शॉर्ट और एडवांस्ड) ---
MESSAGES = {
    "en": {
        "start_greeting": "🎬 <b>Movie Group Bot</b>\n\nHey {name}! Ready to earn? Follow these simple steps:",
        "start_step1": "Join our movie group below",
        "start_step2": "Search any movie in the group",
        "start_step3": "Earn money instantly!",
        "language_choice": "🌐 Language",
        "language_selected": "✅ Language: English",
        "language_prompt": "Select your language:",
        "earning_panel": "💰 <b>Earnings</b>\n\nBalance: ₹{balance}\nReferrals: {refs}\nTier: {tier}\nRate: ₹{rate}/ref",
        "daily_bonus": "🎁 Daily Bonus: +₹{amount}",
        "spin_wheel": "🎡 Spin Wheel: {spins} left",
        "withdraw": "💸 Withdraw (Min ₹80)",
        "refer_link": "🔗 Your Referral Link:\n{link}",
        "refer_example": "💡 <b>How to Earn</b>\n\n1. Share your link\n2. Friend joins\n3. Friend searches movie\n4. You get paid daily!",
        "withdrawal_insufficient": "❌ Minimum withdrawal: ₹80",
        "withdrawal_prompt_method": "🏦 Select payment method:",
        "withdrawal_prompt_details": "✍️ Send your {method} details:",
        "withdrawal_session_expired": "⏳ Session expired. Try again.",
        "withdrawal_details_received": "✅ Request sent!\nAmount: ₹{amount}\nDetails: {details}\n\nYou'll receive payment within 24h.",
        "withdrawal_approved": "✅ Withdrawal of ₹{amount} approved!",
        "withdrawal_rejected": "❌ Withdrawal of ₹{amount} rejected.",
        "channel_bonus": "🎁 Channel Bonus: +₹{amount}",
        "channel_already_claimed": "✅ Bonus already claimed!",
        "channel_bonus_error": "❌ Join {channel} first!",
        "channel_bonus_claimed": "✅ +₹{amount} added! New balance: ₹{balance}",
        "new_referral": "🎉 New referral!\n{name} joined via your link!",
        "daily_earning": "💰 +₹{amount} from referral!",
        "missions": "🎯 Missions\n\n🔹 Search 3 Movies: {s1}/3\n🔹 Refer 2 Friends: {s2}/2\n🔹 Claim Daily Bonus: {s3}/1",
        "leaderboard": "🏆 Top 10\n\n{ranks}\n\nYour Rank: #{rank}",
        "leaderboard_info": "🏆 <b>Leaderboard Prizes</b>\n\n1st: ₹300 (min 50 refs)\n2nd: ₹200 (min 30 refs)\n3rd: ₹100 (min 30 refs)\n4-5th: ₹50 (min 30 refs)\n6-10th: ₹10 (min 30 refs)",
        "help": "🆘 Contact: @{handle}",
        "verify_join": "✅ Verify Join",
        "join_channel": "🚀 Join Channel",
        "back": "⬅️ Back",
        "confirm": "✅ Confirm",
        "cancel": "❌ Cancel",
        "change": "✏️ Change"
    },
    "hi": {
        "start_greeting": "🎬 <b>मूवी ग्रुप बॉट</b>\n\nनमस्ते {name}! कमाई के लिए ये स्टेप्स फॉलो करें:",
        "start_step1": "नीचे मूवी ग्रुप जॉइन करें",
        "start_step2": "ग्रुप में कोई मूवी सर्च करें",
        "start_step3": "तुरंत पैसे कमाएं!",
        "language_choice": "🌐 भाषा",
        "language_selected": "✅ भाषा: हिंदी",
        "language_prompt": "अपनी भाषा चुनें:",
        "earning_panel": "💰 <b>कमाई</b>\n\nबैलेंस: ₹{balance}\nरेफरल: {refs}\nटियर: {tier}\nदर: ₹{rate}/रेफ",
        "daily_bonus": "🎁 दैनिक बोनस: +₹{amount}",
        "spin_wheel": "🎡 स्पिन व्हील: {spins} बाकी",
        "withdraw": "💸 निकासी (न्यूनतम ₹80)",
        "refer_link": "🔗 आपकी रेफरल लिंक:\n{link}",
        "refer_example": "💡 <b>कैसे कमाएं</b>\n\n1. लिंक शेयर करें\n2. दोस्त जॉइन करे\n3. दोस्त मूवी सर्च करे\n4. आपको रोज़ पैसे मिलें!",
        "withdrawal_insufficient": "❌ न्यूनतम निकासी: ₹80",
        "withdrawal_prompt_method": "🏦 भुगतान तरीका चुनें:",
        "withdrawal_prompt_details": "✍️ अपना {method} विवरण भेजें:",
        "withdrawal_session_expired": "⏳ सत्र समाप्त। फिर से कोशिश करें।",
        "withdrawal_details_received": "✅ अनुरोध भेजा गया!\nराशि: ₹{amount}\nविवरण: {details}\n\n24 घंटे में भुगतान मिलेगा।",
        "withdrawal_approved": "✅ ₹{amount} की निकासी स्वीकृत!",
        "withdrawal_rejected": "❌ ₹{amount} की निकासी अस्वीकृत।",
        "channel_bonus": "🎁 चैनल बोनस: +₹{amount}",
        "channel_already_claimed": "✅ बोनस पहले ही मिल चुका!",
        "channel_bonus_error": "❌ पहले {channel} जॉइन करें!",
        "channel_bonus_claimed": "✅ +₹{amount} जुड़े! नया बैलेंस: ₹{balance}",
        "new_referral": "🎉 नया रेफरल!\n{name} आपकी लिंक से जुड़े!",
        "daily_earning": "💰 रेफरल से +₹{amount}!",
        "missions": "🎯 मिशन\n\n🔹 3 मूवी सर्च: {s1}/3\n🔹 2 दोस्त रेफर: {s2}/2\n🔹 डेली बोनस: {s3}/1",
        "leaderboard": "🏆 टॉप 10\n\n{ranks}\n\nआपकी रैंक: #{rank}",
        "leaderboard_info": "🏆 <b>लीडरबोर्ड इनाम</b>\n\n🥇 ₹300 (न्यूनतम 50 रेफ)\n🥈 ₹200 (न्यूनतम 30 रेफ)\n🥉 ₹100 (न्यूनतम 30 रेफ)\n4-5वां ₹50 (न्यूनतम 30 रेफ)\n6-10वां ₹10 (न्यूनतम 30 रेफ)",
        "help": "🆘 संपर्क: @{handle}",
        "verify_join": "✅ ज्वाइन वेरिफाई करें",
        "join_channel": "🚀 चैनल जॉइन करें",
        "back": "⬅️ वापस",
        "confirm": "✅ पक्का करें",
        "cancel": "❌ रद्द करें",
        "change": "✏️ बदलें"
    }
}

# --- Telegram Bot Commands ---
from telegram import BotCommand
USER_COMMANDS = [
    BotCommand("start", "Start the bot and see main menu."),
    BotCommand("earn", "See earning panel and referral link."),
]

ADMIN_COMMANDS = [
    BotCommand("admin", "Access Admin Panel and settings."),
]
