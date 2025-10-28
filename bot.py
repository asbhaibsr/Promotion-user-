import os
import logging
import random
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.error import TelegramError, TimedOut
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from pymongo import MongoClient
from datetime import datetime, timedelta
from dotenv import load_dotenv
import asyncio

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
# Ensure ADMIN_ID is an integer or None
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
except (TypeError, ValueError, AttributeError):
    ADMIN_ID = None
    logger.warning("ADMIN_ID is not set or invalid. Some features may not work.")

YOUR_TELEGRAM_HANDLE = os.getenv("YOUR_TELEGRAM_HANDLE", "telegram") # Default placeholder
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")

# Group links
NEW_MOVIE_GROUP_LINK = "https://t.me/asfilter_bot"
MOVIE_GROUP_LINK = "https://t.me/asfilter_group" 
ALL_GROUPS_LINK = "https://t.me/addlist/6urdhhdLRqhiZmQ1"

# Load Render-specific variables (Kept for completeness but using polling in main)
WEB_SERVER_URL = os.getenv("WEB_SERVER_URL")
PORT = int(os.getenv("PORT", 8000))

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client.get_database('bot_database')
users_collection = db.get_collection('users')
referrals_collection = db.get_collection('referrals')
settings_collection = db.get_collection('settings')
withdrawals_collection = db.get_collection('withdrawals')

# Conversion rate
DOLLAR_TO_INR = 83.0

# --- NEW FEATURES CONFIGURATION ---

# Daily Bonus Config
DAILY_BONUS_BASE = 0.50 # Base bonus in INR
DAILY_BONUS_STREAK_MULTIPLIER = 0.10 # Extra 0.10 INR per day of streak

# Spin Wheel Prizes (in INR)
SPIN_PRIZES_WEIGHTS = {
    0.00: 4,  # 0Rs - 4 parts
    0.20: 3,  # 0.20Rs - 3 parts
    0.50: 3,  # 0.50Rs - 3 parts
    0.80: 2,  # 0.80Rs - 2 parts
    1.00: 2,  # 1Rs - 2 parts
    3.00: 1,  # 3Rs - 1 part
    5.00: 1,  # 5Rs - 1 part
    10.00: 1   # 10Rs - 1 part
}
SPIN_PRIZES = list(SPIN_PRIZES_WEIGHTS.keys())
SPIN_WEIGHTS = list(SPIN_PRIZES_WEIGHTS.values())


# Tier System Configuration
TIERS = {
    1: {"min_earnings": 0, "rate": 0.40, "name": "Beginner", "benefits": "Basic referral rate"},
    2: {"min_earnings": 50, "rate": 0.60, "name": "Pro", "benefits": "50% higher referral rate"},
    3: {"min_earnings": 200, "rate": 1.00, "name": "Expert", "benefits": "2.5x referral rate"},
    4: {"min_earnings": 500, "rate": 2.00, "name": "Master", "benefits": "5x referral rate"}
}

# Missions Configuration
DAILY_MISSIONS = {
    "search_3_movies": {"reward": 1.00, "target": 3, "name": "Search 3 Movies", "name_hi": "3 फिल्में खोजें"},
    "refer_2_friends": {"reward": 5.00, "target": 2, "name": "Refer 2 Friends", "name_hi": "2 दोस्तों को रेफ़र करें"},
    "claim_daily_bonus": {"reward": 0.50, "target": 1, "name": "Claim Daily Bonus", "name_hi": "दैनिक बोनस क्लेम करें"}
}

# --- ALL MESSAGES (INCL. MISSING ONES) ---
MESSAGES = {
    "en": {
        "start_greeting": "Hey 👋! Welcome to the Movies Group Bot. Get your favorite movies by following these simple steps:",
        "start_step1": "Click the button below to join our movie group.",
        "start_step2": "Go to the group and type the name of the movie you want.",
        "start_step3": "The bot will give you a link to your movie.",
        "language_choice": "Choose your language:",
        "language_selected": "Language changed to English.",
        "help_message_text": "<b>🤝 How to Earn Money</b>\n\n1️⃣ <b>Get Your Link:</b> Use the 'My Refer Link' button to get your unique referral link.\n\n2️⃣ <b>Share Your Link:</b> Share this link with your friends. Tell them to start the bot and join our movie group.\n\n3️⃣ <b>Earn:</b> When a referred friend searches for a movie in the group and completes the shortlink process, you earn money! You can earn from each friend once per day.",
        "withdrawal_message_updated": "💸 <b>Withdrawal Details</b>\n\nYou can withdraw your earnings when your balance reaches ₹80 or more. Click the button below to contact the admin and get your payment.\n\n<b>Note:</b> Payments are sent via UPI ID, QR code, or Bank Account. Click the button and send your payment details to the admin.",
        "earning_panel_message": "<b>💰 Earning Panel</b>\n\nManage all your earning activities here.",
        "daily_bonus_success": "🎉 <b>Daily Bonus Claimed!</b>\nYou have successfully claimed your daily bonus of ₹{bonus_amount:.2f}. Your new balance is ₹{new_balance:.2f}.\n\n{streak_message}",
        "daily_bonus_already_claimed": "⏳ <b>Bonus Already Claimed!</b>\nYou have already claimed your bonus for today. Try again tomorrow!",
        "admin_panel_title": "<b>⚙️ Admin Panel</b>\n\nManage bot settings and users from here.",
        "setrate_success": "✅ Referral earning rate has been updated to ₹{new_rate:.2f}.",
        "setrate_usage": "❌ Usage: /setrate <new_rate_in_inr>",
        "invalid_rate": "❌ Invalid rate. Please enter a number.",
        "referral_rate_updated": "The new referral rate is now ₹{new_rate:.2f}.",
        "broadcast_admin_only": "❌ This command is for the bot admin only.",
        "broadcast_message": "Please reply to a message with `/broadcast` to send it to all users.",
        "setwelbonus_usage": "❌ Usage: /setwelbonus <amount_in_inr>",
        "setwelbonus_success": "✅ Welcome bonus updated to ₹{new_bonus:.2f}",
        "welcome_bonus_received": "🎁 <b>Welcome Bonus!</b>\n\nYou have received ₹{amount:.2f} welcome bonus! Start earning more by referring friends.",
        "spin_wheel_title": "🎡 <b>Spin the Wheel</b>\n\nCost: ₹2.00\nClick 'Spin' to try your luck!",
        "spin_wheel_button": "✨ Spin Now (₹2)",
        "spin_wheel_animating": "🎡 <b>Spinning...</b>\n\nWait for the result! 🍀",
        "spin_wheel_insufficient_balance": "❌ <b>Insufficient Balance!</b>\n\nYou need at least ₹2.00 to spin the wheel.",
        "spin_wheel_already_spun": "⏳ <b>Already Spun Today!</b>\n\nYou can spin the wheel only once per day. Try again tomorrow!",
        "spin_wheel_win": "🎉 <b>Congratulations!</b>\n\nYou won: ₹{amount:.2f}!\n\nNew balance: ₹{new_balance:.2f}",
        "spin_wheel_lose": "😢 <b>Better luck next time!</b>\n\nYou didn't win anything this time.\n\nRemaining balance: ₹{new_balance:.2f}",
        "missions_title": "🎯 <b>Daily Missions</b>\n\nComplete missions to earn extra rewards! Check your progress below:",
        "mission_complete": "✅ <b>Mission Completed!</b>\n\nYou earned ₹{reward:.2f} for {mission_name}!\nNew balance: ₹{new_balance:.2f}",
        "withdrawal_request_sent": "✅ <b>Withdrawal Request Sent!</b>\n\nYour request for ₹{amount:.2f} has been sent to admin. You will receive payment within 24 hours.",
        "withdrawal_insufficient": "❌ <b>Insufficient Balance!</b>\n\nMinimum withdrawal amount is ₹80.00",
        "withdrawal_approved_user": "✅ <b>Withdrawal Approved!</b>\n\nYour withdrawal of ₹{amount:.2f} has been approved. Payment will be processed within 24 hours.",
        "withdrawal_rejected_user": "❌ <b>Withdrawal Rejected!</b>\n\nYour withdrawal of ₹{amount:.2f} was rejected. Please contact admin for details.",
        "ref_link_message": "<b>Your Referral Link:</b>\n<code>{referral_link}</code>\n\n<b>Current Referral Rate:</b> ₹{tier_rate:.2f} per referral\n\n<i>Share this link with friends and earn money when they join and search for movies!</i>",
        "new_referral_notification": "🎉 <b>New Referral!</b>\n\n{full_name} ({username}) has joined using your link!",
        "daily_earning_update": "💰 <b>Referral Earning!</b>\n\nYou earned money from your referral {full_name}. \nNew balance: ₹{new_balance:.2f}",
        "clear_earn_usage": "❌ Usage: /clearearn <user_id>",
        "clear_earn_success": "✅ Earnings for user {user_id} have been cleared.",
        "clear_earn_not_found": "❌ User {user_id} not found.",
        "check_stats_usage": "❌ Usage: /checkstats <user_id>",
        "check_stats_message": "📊 <b>User Stats</b>\n\nID: {user_id}\nEarnings: ₹{earnings:.2f}\nReferrals: {referrals}",
        "check_stats_not_found": "❌ User {user_id} not found.",
        "stats_message": "📊 <b>Bot Stats</b>\n\nTotal Users: {total_users}\nApproved Users: {approved_users}",
    },
    "hi": {
        "start_greeting": "नमस्ते 👋! मूवी ग्रुप बॉट में आपका स्वागत है। इन आसान स्टेप्स को फॉलो करके अपनी पसंदीदा मूवी पाएँ:",
        "start_step1": "हमारे मूवी ग्रुप में शामिल होने के लिए नीचे दिए गए बटन पर क्लिक करें।",
        "start_step2": "ग्रुप में जाकर अपनी मनपसंद मूवी का नाम लिखें।",
        "start_step3": "बॉट आपको आपकी मूवी की लिंक देगा।",
        "language_choice": "अपनी भाषा चुनें:",
        "language_selected": "भाषा हिंदी में बदल दी गई है।",
        "help_message_text": "<b>🤝 पैसे कैसे कमाएं</b>\n\n1️⃣ <b>अपनी लिंक पाएं:</b> 'My Refer Link' बटन का उपयोग करके अपनी रेफरल लिंक पाएं।\n\n2️⃣ <b>शेयर करें:</b> इस लिंक को अपने दोस्तों के साथ शेयर करें। उन्हें बॉट शुरू करने और हमारे मूवी ग्रुप में शामिल होने के लिए कहें।\n\n3️⃣ <b>कमाई करें:</b> जब आपका रेफर किया गया दोस्त ग्रुप में कोई मूवी खोजता है और शॉर्टलिंक प्रक्रिया पूरी करता है, तो आप पैसे कमाते हैं! आप प्रत्येक दोस्त से एक दिन में एक बार कमाई कर सकते हैं।",
        "withdrawal_message_updated": "💸 <b>निकासी का विवरण</b>\n\nजब आपका बैलेंस ₹80 या उससे अधिक हो जाए, तो आप अपनी कमाई निकाल सकते हैं। एडमिन से संपर्क करने और अपना भुगतान पाने के लिए नीचे दिए गए बटन पर क्लिक करें।\n\n<b>ध्यान दें:</b> भुगतान UPI ID, QR कोड, या बैंक खाते के माध्यम से भेजे जाते हैं। बटन पर क्लिक करें और अपने भुगतान विवरण एडमिन को भेजें।",
        "earning_panel_message": "<b>💰 कमाई का पैनल</b>\n\nयहाँ आप अपनी कमाई से जुड़ी सभी गतिविधियाँ मैनेज कर सकते हैं।",
        "daily_bonus_success": "🎉 <b>दैनिक बोनस क्लेम किया गया!</b>\nआपने सफलतापूर्वक अपना दैनिक बोनस ₹{bonus_amount:.2f} क्लेम कर लिया है। आपका नया बैलेंस ₹{new_balance:.2f} है।\n\n{streak_message}",
        "daily_bonus_already_claimed": "⏳ <b>बोनस पहले ही क्लेम किया जा चुका है!</b>\nआपने आज का बोनस पहले ही क्लेम कर लिया है। कल फिर कोशिश करें!",
        "admin_panel_title": "<b>⚙️ एडमिन पैनल</b>\n\nयहाँ से बॉट की सेटिंग्स और यूज़र्स को मैनेज करें।",
        "setrate_success": "✅ रेफरल कमाई की दर ₹{new_rate:.2f} पर अपडेट हो गई है।",
        "setrate_usage": "❌ उपयोग: /setrate <नई_राशि_रुपये_में>",
        "invalid_rate": "❌ अमान्य राशि। कृपया एक संख्या दर्ज करें।",
        "referral_rate_updated": "नई रेफरल दर अब ₹{new_rate:.2f} है।",
        "broadcast_admin_only": "❌ यह कमांड केवल बॉट एडमिन के लिए है।",
        "broadcast_message": "सभी उपयोगकर्ताओं को संदेश भेजने के लिए कृपया किसी संदेश का `/broadcast` के साथ उत्तर दें।",
        "setwelbonus_usage": "❌ उपयोग: /setwelbonus <राशि_रुपये_में>",
        "setwelbonus_success": "✅ वेलकम बोनस ₹{new_bonus:.2f} पर अपडेट हो गया है।",
        "welcome_bonus_received": "🎁 <b>वेलकम बोनस!</b>\n\nआपको ₹{amount:.2f} वेलकम बोनस मिला है! दोस्तों को रेफर करके और कमाएँ।",
        "spin_wheel_title": "🎡 <b>व्हील स्पिन करें</b>\n\nलागत: ₹2.00\nअपनी किस्मत आज़माने के लिए 'Spin Now' पर क्लिक करें!",
        "spin_wheel_button": "✨ अभी स्पिन करें (₹2)",
        "spin_wheel_animating": "🎡 <b>स्पिन हो रहा है...</b>\n\nपरिणाम का इंतजार करें! 🍀",
        "spin_wheel_insufficient_balance": "❌ <b>पर्याप्त बैलेंस नहीं!</b>\n\nव्हील स्पिन करने के लिए आपके पास कम से कम ₹2.00 होने चाहिए।",
        "spin_wheel_already_spun": "⏳ <b>आज पहले ही स्पिन कर चुके हैं!</b>\n\nआप व्हील को केवल एक बार प्रति दिन स्पिन कर सकते हैं। कल फिर कोशिश करें!",
        "spin_wheel_win": "🎉 <b>बधाई हो!</b>\n\nआपने जीता: ₹{amount:.2f}!\n\nनया बैलेंस: ₹{new_balance:.2f}",
        "spin_wheel_lose": "😢 <b>अगली बार बेहतर किस्मत!</b>\n\nइस बार आप कुछ नहीं जीत पाए।\n\nशेष बैलेंस: ₹{new_balance:.2f}",
        "missions_title": "🎯 <b>दैनिक मिशन</b>\n\nअतिरिक्त इनाम पाने के लिए मिशन पूरे करें! अपनी प्रगति नीचे देखें:",
        "mission_complete": "✅ <b>मिशन पूरा हुआ!</b>\n\nआपने {mission_name} के लिए ₹{reward:.2f} कमाए!\nनया बैलेंस: ₹{new_balance:.2f}",
        "withdrawal_request_sent": "✅ <b>निकासी का अनुरोध भेज दिया गया!</b>\n\n₹{amount:.2f} के आपके अनुरोध को एडमिन को भेज दिया गया है। आपको 24 घंटे के भीतर भुगतान मिल जाएगा।",
        "withdrawal_insufficient": "❌ <b>पर्याप्त बैलेंस नहीं!</b>\n\nन्यूनतम निकासी राशि ₹80.00 है",
        "withdrawal_approved_user": "✅ <b>निकासी स्वीकृत!</b>\n\n₹{amount:.2f} की आपकी निकासी स्वीकृत कर दी गई है। भुगतान 24 घंटे के भीतर प्रोसेस किया जाएगा।",
        "withdrawal_rejected_user": "❌ <b>निकासी अस्वीकृत!</b>\n\n₹{amount:.2f} की आपकी निकासी अस्वीकृत कर दी गई है। विवरण के लिए एडमिन से संपर्क करें।",
        "ref_link_message": "<b>आपकी रेफरल लिंक:</b>\n<code>{referral_link}</code>\n\n<b>वर्तमान रेफरल दर:</b> ₹{tier_rate:.2f} प्रति रेफरल\n\n<i>इस लिंक को दोस्तों के साथ साझा करें और जब वे शामिल होकर फिल्में खोजते हैं, तो पैसे कमाएं!</i>",
        "new_referral_notification": "🎉 <b>नया रेफरल!</b>\n\n{full_name} ({username}) आपकी लिंक का उपयोग करके शामिल हुए हैं!",
        "daily_earning_update": "💰 <b>रेफरल कमाई!</b>\n\nआपने अपने रेफरल {full_name} से पैसे कमाए। \nनया बैलेंस: ₹{new_balance:.2f}",
        "clear_earn_usage": "❌ उपयोग: /clearearn <user_id>",
        "clear_earn_success": "✅ उपयोगकर्ता {user_id} की कमाई साफ़ कर दी गई है।",
        "clear_earn_not_found": "❌ उपयोगकर्ता {user_id} नहीं मिला।",
        "check_stats_usage": "❌ उपयोग: /checkstats <user_id>",
        "check_stats_message": "📊 <b>यूज़र आँकड़े</b>\n\nID: {user_id}\nकमाई: ₹{earnings:.2f}\nरेफरल: {referrals}",
        "check_stats_not_found": "❌ उपयोगकर्ता {user_id} नहीं मिला।",
        "stats_message": "📊 <b>बॉट आँकड़े</b>\n\nकुल उपयोगकर्ता: {total_users}\nअनुमोदित उपयोगकर्ता: {approved_users}",
    }
}

# --- COMMAND LISTS FOR /setcommands ---
USER_COMMANDS = [
    BotCommand("start", "Start the bot and see main menu."),
    BotCommand("earn", "See earning panel and referral link."),
]

ADMIN_COMMANDS = [
    BotCommand("start", "Start the bot"),
    BotCommand("earn", "See earning panel"),
    BotCommand("admin", "Access Admin Panel and settings."),
    BotCommand("stats", "See bot total users and stats."),
    BotCommand("broadcast", "Send message to all users."),
    BotCommand("setrate", "Set referral rate (INR)."),
    BotCommand("setwelbonus", "Set welcome bonus (INR)."),
]

# --- UTILITY FUNCTIONS ---

async def get_user_lang(user_id):
    user_data = users_collection.find_one({"user_id": user_id})
    return user_data.get("lang", "en") if user_data else "en"

async def set_user_lang(user_id, lang):
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"lang": lang}},
        upsert=True
    )

async def get_referral_bonus_inr():
    settings = settings_collection.find_one({"_id": "referral_rate"})
    return settings.get("rate_inr", 0.40) if settings else 0.40

async def get_welcome_bonus():
    settings = settings_collection.find_one({"_id": "welcome_bonus"})
    return settings.get("amount_inr", 5.00) if settings else 5.00

async def get_user_tier(user_id):
    user_data = users_collection.find_one({"user_id": user_id})
    if not user_data:
        return 1
    
    earnings_usd = user_data.get("earnings", 0.0) 
    earnings_inr = earnings_usd * DOLLAR_TO_INR
    
    for tier, info in sorted(TIERS.items(), reverse=True):
        if earnings_inr >= info["min_earnings"]:
            return tier
    return 1

async def get_tier_referral_rate(tier):
    return TIERS.get(tier, TIERS[1])["rate"] 

# --- CORE BOT FUNCTIONS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    full_name = user.first_name + (f" {user.last_name}" if user.last_name else "")
    
    referral_id_str = context.args[0].replace("ref_", "") if context.args and context.args[0].startswith("ref_") else None
    referral_id = int(referral_id_str) if referral_id_str and referral_id_str.isdigit() else None

    user_data = users_collection.find_one({"user_id": user.id})
    is_new_user = not user_data

    # Ensure all new fields are set on first insertion
    update_data = {
        "$setOnInsert": {
            "username": user.username,
            "full_name": full_name,
            "lang": "en",
            "is_approved": True,
            "earnings": 0.0, # Stored in USD, converted to INR for display
            "last_checkin_date": None,
            "last_spin_date": None,
            "daily_bonus_streak": 0,
            "missions_completed": {},
            "welcome_bonus_received": False,
            "joined_date": datetime.now(),
            "daily_searches": 0, 
            "last_search_date": None 
        }
    }
    
    users_collection.update_one(
        {"user_id": user.id},
        update_data,
        upsert=True
    )

    # Re-fetch data to get defaults if it was a new user
    user_data = users_collection.find_one({"user_id": user.id})
    lang = user_data.get("lang", "en")
    
    # Give welcome bonus to new users
    if is_new_user and not user_data.get("welcome_bonus_received", False):
        welcome_bonus = await get_welcome_bonus()
        welcome_bonus_usd = welcome_bonus / DOLLAR_TO_INR
        
        users_collection.update_one(
            {"user_id": user.id},
            {"$inc": {"earnings": welcome_bonus_usd}, "$set": {"welcome_bonus_received": True}}
        )
        
        await update.message.reply_html(
            MESSAGES[lang]["welcome_bonus_received"].format(amount=welcome_bonus)
        )

    # Handle referral logic
    if referral_id and referral_id != user.id and is_new_user:
        existing_referral = referrals_collection.find_one({"referred_user_id": user.id})
        
        if not existing_referral:
            referrals_collection.insert_one({
                "referrer_id": referral_id,
                "referred_user_id": user.id,
                "referred_username": user.username,
                "join_date": datetime.now(),
                "last_earning_date": None 
            })
            
            # Initial join bonus (e.g., half the rate)
            referrer_tier = await get_user_tier(referral_id)
            tier_rate = await get_tier_referral_rate(referrer_tier)
            referral_rate_usd = (tier_rate / DOLLAR_TO_INR) / 2 # Half bonus on join
            
            users_collection.update_one(
                {"user_id": referral_id},
                {"$inc": {"earnings": referral_rate_usd}} 
            )

            # Notify referrer
            try:
                referrer_lang = await get_user_lang(referral_id)
                await context.bot.send_message(
                    chat_id=referral_id,
                    text=MESSAGES[referrer_lang]["new_referral_notification"].format(
                        full_name=full_name, username=f"@{user.username}" if user.username else "(No username)"
                    ),
                    parse_mode='HTML'
                )
            except (TelegramError, TimedOut) as e:
                logger.error(f"Could not notify referrer {referral_id}: {e}")

    # Send the main menu
    keyboard = [
        [InlineKeyboardButton("🎬 Movie Groups", callback_data="show_movie_groups_menu")],
        [InlineKeyboardButton("💰 Earning Panel", callback_data="show_earning_panel")],
        [InlineKeyboardButton(MESSAGES[lang]["language_choice"], callback_data="select_lang")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        f"{MESSAGES[lang]['start_greeting']}\n\n"
        f"<b>1.</b> {MESSAGES[lang]['start_step1']}\n"
        f"<b>2.</b> {MESSAGES[lang]['start_step2']}\n"
        f"<b>3.</b> {MESSAGES[lang]['start_step3']}"
    )
    
    await update.message.reply_html(message, reply_markup=reply_markup)

# --- EARNING PANEL FUNCTIONS ---

async def show_earning_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    user_data = users_collection.find_one({"user_id": user.id})
    
    if not user_data:
        await query.edit_message_text("User data not found.")
        return

    # Get user stats
    earnings_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR
    referrals_count = referrals_collection.count_documents({"referrer_id": user.id})
    user_tier = await get_user_tier(user.id)
    tier_info = TIERS.get(user_tier, TIERS[1]) 
    
    # Enhanced earning panel message
    message = (
        f"<b>💰 Earning Panel</b>\n\n"
        f"🏅 <b>Current Tier:</b> {tier_info['name']} (Level {user_tier})\n"
        f"💵 <b>Balance:</b> ₹{earnings_inr:.2f}\n"
        f"👥 <b>Total Referrals:</b> {referrals_count}\n"
        f"🎯 <b>Referral Rate:</b> ₹{tier_info['rate']:.2f}/referral\n\n"
        f"<i>Earn more to unlock higher tiers with better rates!</i>"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔗 My Refer Link", callback_data="show_refer_link")],
        [InlineKeyboardButton(MESSAGES[lang]["spin_wheel_button"], callback_data="spin_wheel")],
        [InlineKeyboardButton("💸 Request Withdrawal", callback_data="request_withdrawal")],
        [InlineKeyboardButton("🎁 Daily Bonus", callback_data="claim_daily_bonus")],
        [InlineKeyboardButton("🎯 Daily Missions", callback_data="show_missions")],
        [InlineKeyboardButton("📊 Tier Benefits", callback_data="show_tier_benefits")],
        [InlineKeyboardButton("🆘 Help", callback_data="show_help")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

async def show_refer_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    referral_link = f"https://t.me/{bot_username}?start=ref_{user.id}"
    
    user_tier = await get_user_tier(user.id)
    tier_rate = await get_tier_referral_rate(user_tier)
    
    message = MESSAGES[lang]["ref_link_message"].format(
        referral_link=referral_link,
        tier_rate=tier_rate
    )
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    help_message = MESSAGES[lang]["help_message_text"]
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(help_message, reply_markup=reply_markup, parse_mode='HTML')

# --- NEWLY ADDED/FIXED FUNCTIONS ---

async def language_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the language selection menu."""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇮🇳 हिंदी", callback_data="lang_hi")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Please choose your language: / अपनी भाषा चुनें:", 
        reply_markup=reply_markup
    )

async def handle_lang_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the user's language selection."""
    query = update.callback_query
    await query.answer()
    
    lang = query.data.split("_")[1] # e.g., "lang_en" -> "en"
    user_id = query.from_user.id
    
    await set_user_lang(user_id, lang)
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="back_to_main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        MESSAGES[lang]["language_selected"],
        reply_markup=reply_markup
    )

async def claim_daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the daily bonus claim."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    user_data = users_collection.find_one({"user_id": user.id})
    if not user_data:
        await query.edit_message_text("User data not found.")
        return

    today = datetime.now().date()
    last_checkin = user_data.get("last_checkin_date")
    
    if last_checkin and isinstance(last_checkin, datetime) and last_checkin.date() == today:
        await query.edit_message_text(
            MESSAGES[lang]["daily_bonus_already_claimed"],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
        )
        return

    streak = user_data.get("daily_bonus_streak", 0)
    
    # Check for streak
    if last_checkin and isinstance(last_checkin, datetime) and (today - last_checkin.date()).days == 1:
        streak += 1
    else:
        streak = 1 # Reset or start streak

    bonus_amount = DAILY_BONUS_BASE + (streak * DAILY_BONUS_STREAK_MULTIPLIER)
    bonus_amount_usd = bonus_amount / DOLLAR_TO_INR
    
    new_balance = user_data.get("earnings", 0.0) + bonus_amount_usd
    
    users_collection.update_one(
        {"user_id": user.id},
        {
            "$set": {
                "earnings": new_balance,
                "last_checkin_date": datetime.now(),
                "daily_bonus_streak": streak,
                f"missions_completed.claim_daily_bonus": True # Mark mission as complete
            }
        }
    )
    
    streak_message = f"🔥 You are on a {streak}-day streak! Keep it up for bigger bonuses!"
    if lang == "hi":
        streak_message = f"🔥 आप {streak}-दिन की स्ट्रीक पर हैं! बड़े बोनस के लिए इसे जारी रखें!"
        
    await query.edit_message_text(
        MESSAGES[lang]["daily_bonus_success"].format(
            bonus_amount=bonus_amount,
            new_balance=new_balance * DOLLAR_TO_INR,
            streak_message=streak_message
        ),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]),
        parse_mode='HTML'
    )

async def show_missions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the user's daily mission progress."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    user_data = users_collection.find_one({"user_id": user.id})
    if not user_data:
        await query.edit_message_text("User data not found.")
        return
        
    missions_completed = user_data.get("missions_completed", {})
    daily_searches = user_data.get("daily_searches", 0)
    
    # Check if last_search_date is today, if not, reset daily_searches
    last_search_date = user_data.get("last_search_date")
    today = datetime.now().date()
    if not last_search_date or not isinstance(last_search_date, datetime) or last_search_date.date() != today:
        daily_searches = 0 # Reset for the new day

    # Check referral mission
    referrals_today_count = referrals_collection.count_documents({
        "referrer_id": user.id,
        "join_date": {"$gte": datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)}
    })

    message = f"{MESSAGES[lang]['missions_title']}\n\n"

    # Mission 1: Search 3 Movies
    mission_key = "search_3_movies"
    mission = DAILY_MISSIONS[mission_key]
    name = mission["name"] if lang == "en" else mission["name_hi"]
    if missions_completed.get(mission_key):
        message += f"✅ {name} ({mission['target']}/{mission['target']}) [<b>Completed</b>]\n"
    else:
        message += f"⏳ {name} ({daily_searches}/{mission['target']}) [In Progress]\n"
        
    # Mission 2: Refer 2 Friends
    mission_key = "refer_2_friends"
    mission = DAILY_MISSIONS[mission_key]
    name = mission["name"] if lang == "en" else mission["name_hi"]
    if missions_completed.get(mission_key):
        message += f"✅ {name} ({mission['target']}/{mission['target']}) [<b>Completed</b>]\n"
    else:
        message += f"⏳ {name} ({referrals_today_count}/{mission['target']}) [In Progress]\n"

    # Mission 3: Claim Daily Bonus
    mission_key = "claim_daily_bonus"
    mission = DAILY_MISSIONS[mission_key]
    name = mission["name"] if lang == "en" else mission["name_hi"]
    if missions_completed.get(mission_key):
        message += f"✅ {name} [<b>Completed</b>]\n"
    else:
        message += f"⏳ {name} [In Progress]\n"

    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

async def show_tier_benefits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the benefits for all tiers."""
    query = update.callback_query
    await query.answer()
    
    lang = await get_user_lang(query.from_user.id)
    user_tier = await get_user_tier(query.from_user.id)

    message = "<b>🏆 Tier Benefits 🏆</b>\n\n"
    if lang == 'hi':
        message = "<b>🏆 टियर के लाभ 🏆</b>\n\n"
        
    for tier, info in sorted(TIERS.items()):
        if tier == user_tier:
            message += "<b>" # Bold the current tier
            
        name = info['name']
        benefits = info['benefits']
        
        if lang == 'hi':
            # Simple translation for tier names
            if name == 'Beginner': name = 'शुरुआती'
            elif name == 'Pro': name = 'प्रो'
            elif name == 'Expert': name = 'विशेषज्ञ'
            elif name == 'Master': name = 'मास्टर'
            
            if benefits == 'Basic referral rate': benefits = 'बेसिक रेफरल दर'
            elif benefits == '50% higher referral rate': benefits = '50% अधिक रेफरल दर'
            elif benefits == '2.5x referral rate': benefits = '2.5x रेफरल दर'
            elif benefits == '5x referral rate': benefits = '5x रेफरल दर'
        
        message += f"🏅 <b>Level {tier}: {name}</b>\n"
        message += f"💰 Rate: ₹{info['rate']:.2f}\n"
        message += f"📋 Unlocks at: ₹{info['min_earnings']} total earnings\n"
        message += f"✨ Benefit: {benefits}\n"
        
        if tier == user_tier:
            message += "</b><i>(Your Current Tier)</i>\n" if lang == 'en' else "</b><i>(आपका वर्तमान टियर)</i>\n"
            
        message += "\n"

    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

# --- SPIN WHEEL ---

async def spin_wheel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    # 1. Check constraints (balance, daily limit)
    user_data = users_collection.find_one({"user_id": user.id})
    if not user_data:
        await query.edit_message_text("User data not found.")
        return

    last_spin_date = user_data.get("last_spin_date")
    today = datetime.now().date()
    
    if last_spin_date and isinstance(last_spin_date, datetime) and last_spin_date.date() == today:
        await query.edit_message_text(
            MESSAGES[lang]["spin_wheel_already_spun"],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
        )
        return

    spin_cost_inr = 2.00
    spin_cost_usd = spin_cost_inr / DOLLAR_TO_INR
    current_balance = user_data.get("earnings", 0.0)
    
    if current_balance < spin_cost_usd:
        await query.edit_message_text(
            MESSAGES[lang]["spin_wheel_insufficient_balance"],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
        )
        return

    # 2. Start Spinning Animation/Delay
    # Deduct cost first
    final_balance_usd_after_cost = current_balance - spin_cost_usd
    
    users_collection.update_one(
        {"user_id": user.id},
        {"$set": {"earnings": final_balance_usd_after_cost}}
    )
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send animating message
    await query.edit_message_text(
        MESSAGES[lang]["spin_wheel_animating"],
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    await asyncio.sleep(2) # 2-second delay for the "spin" effect

    # 3. Determine Prize (Weighted Random Choice)
    prize_inr = random.choices(SPIN_PRIZES, weights=SPIN_WEIGHTS, k=1)[0]
    prize_usd = prize_inr / DOLLAR_TO_INR
    
    # 4. Final Balance Update
    final_balance_usd = final_balance_usd_after_cost + prize_usd
    
    users_collection.update_one(
        {"user_id": user.id},
        {
            "$set": {
                "earnings": final_balance_usd,
                "last_spin_date": datetime.now()
            }
        }
    )

    # 5. Send Result
    if prize_inr > 0:
        message = MESSAGES[lang]["spin_wheel_win"].format(
            amount=prize_inr, new_balance=final_balance_usd * DOLLAR_TO_INR
        )
    else:
        message = MESSAGES[lang]["spin_wheel_lose"].format(
            new_balance=final_balance_usd * DOLLAR_TO_INR
        )

    keyboard = [
        [InlineKeyboardButton(MESSAGES[lang]["spin_wheel_button"], callback_data="spin_wheel")],
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.edit_message_text(
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        text=message, 
        reply_markup=reply_markup, 
        parse_mode='HTML'
    )

# --- WITHDRAWAL FUNCTIONS ---

async def request_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    user_data = users_collection.find_one({"user_id": user.id})
    
    if not user_data:
        await query.edit_message_text("User data not found.")
        return

    earnings_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR
    
    if earnings_inr < 80:
        await query.edit_message_text(
            MESSAGES[lang]["withdrawal_insufficient"],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
        )
        return

    existing_request = withdrawals_collection.find_one({"user_id": user.id, "status": "pending"})
    if existing_request:
        await query.edit_message_text(
            "❌ <b>Request Already Pending!</b>\n\nYour previous withdrawal request is still being processed.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]),
            parse_mode='HTML'
        )
        return

    # Create withdrawal request
    withdrawal_data = {
        "user_id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "amount_inr": earnings_inr,
        "status": "pending",
        "request_date": datetime.now(),
        "approved_date": None
    }
    
    withdrawals_collection.insert_one(withdrawal_data)

    # Notify admin
    if ADMIN_ID:
        try:
            admin_message = (
                f"🔄 <b>New Withdrawal Request</b>\n\n"
                f"👤 User: {user.full_name} (@{user.username})\n"
                f"🆔 ID: <code>{user.id}</code>\n"
                f"💰 Amount: ₹{earnings_inr:.2f}\n"
                f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_message,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve_withdraw_{user.id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_withdraw_{user.id}")
                ]])
            )
        except Exception as e:
            logger.error(f"Could not notify admin about withdrawal: {e}")

    await query.edit_message_text(
        MESSAGES[lang]["withdrawal_request_sent"].format(amount=earnings_inr),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]),
        parse_mode='HTML'
    )
    
async def show_withdraw_details_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # This function is kept for legacy button, but new button is "request_withdrawal"
    query = update.callback_query
    await query.answer()
    lang = await get_user_lang(query.from_user.id)
    
    message = MESSAGES[lang]["withdrawal_message_updated"]
    
    keyboard = [
        [InlineKeyboardButton("Contact Admin", url=f"https://t.me/{YOUR_TELEGRAM_HANDLE}")],
        [InlineKeyboardButton("💸 Request Withdrawal", callback_data="request_withdrawal")],
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


# --- ADMIN PANEL AND COMMANDS ---

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = await get_user_lang(user.id)
    
    if user.id != ADMIN_ID:
        await update.message.reply_html(MESSAGES[lang]["broadcast_admin_only"])
        return
    
    rate = await get_referral_bonus_inr()
    bonus = await get_welcome_bonus()
    
    message = (
        f"<b>⚙️ Admin Panel</b>\n\n"
        f"Current Settings:\n"
        f"🔗 **Referral Rate:** ₹{rate:.2f}\n"
        f"🎁 **Welcome Bonus:** ₹{bonus:.2f}\n"
    )
    
    keyboard = [
        [InlineKeyboardButton("1️⃣ Set Referral Rate", callback_data="admin_set_rate")],
        [InlineKeyboardButton("2️⃣ Set Welcome Bonus", callback_data="admin_set_welbonus")],
        [InlineKeyboardButton("3️⃣ Check Withdrawals", callback_data="admin_check_withdrawals")],
        [InlineKeyboardButton("4️⃣ Set Bot Commands", callback_data="admin_set_commands")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(message, reply_markup=reply_markup, parse_mode='HTML')

async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data
    user = query.from_user
    lang = await get_user_lang(user.id)

    if user.id != ADMIN_ID:
        await query.answer(MESSAGES[lang]["broadcast_admin_only"], show_alert=True)
        return
    
    await query.answer() # Answer callback first
    
    if data == "admin_set_rate":
        await query.edit_message_text("✍️ **Enter New Referral Rate (in INR):**\n\nExample: `/setrate 1.00`")
    elif data == "admin_set_welbonus":
        await query.edit_message_text("✍️ **Enter New Welcome Bonus (in INR):**\n\nExample: `/setwelbonus 5.00`")
    elif data == "admin_check_withdrawals":
        pending_requests = list(withdrawals_collection.find({"status": "pending"}))
        
        message = "💸 <b>Pending Withdrawal Requests</b> 💸\n\n"
        keyboard = []
        
        if not pending_requests:
            message += "✅ No pending requests found."
        else:
            for req in pending_requests:
                username_display = f"@{req.get('username')}" if req.get('username') else f"ID: {req['user_id']}"
                message += (
                    f"👤 {username_display}\n"
                    f"💰 Amount: ₹{req['amount_inr']:.2f}\n"
                    f"⏰ Date: {req['request_date'].strftime('%Y-%m-%d %H:%M')}\n\n"
                )
                keyboard.append([
                    InlineKeyboardButton(f"✅ Approve (ID: {req['user_id']})", callback_data=f"approve_withdraw_{req['user_id']}"),
                    InlineKeyboardButton(f"❌ Reject (ID: {req['user_id']})", callback_data=f"reject_withdraw_{req['user_id']}")
                ])
        
        keyboard.append([InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_back")])
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        
    elif data == "admin_set_commands":
        await set_bot_commands_command(update, context, query=query)
        
    elif data == "admin_back":
        # Re-run admin_panel logic to show the main panel again
        # We need to send it as a new message or edit the existing one
        try:
            await admin_panel(update, context)
            if query.message: # if called from a button
                await query.delete_message()
        except Exception as e:
            logger.error(f"Error returning to admin panel: {e}")
            # Fallback if update is not a message
            if query.message:
                await query.edit_message_text("Returning to admin panel...")
                await admin_panel(query, context) # Pass query

async def set_bot_commands_command(update: Update, context: ContextTypes.DEFAULT_TYPE, query=None) -> None:
    """Sets the bot commands for users and admin."""
    effective_update = query if query else update
    user = effective_update.from_user
    lang = await get_user_lang(user.id)

    if user.id != ADMIN_ID:
        if query:
            await query.answer(MESSAGES[lang]["broadcast_admin_only"], show_alert=True)
        else:
            await update.message.reply_html(MESSAGES[lang]["broadcast_admin_only"])
        return
    
    bot = context.bot
    try:
        # Set User Commands (for all users)
        await bot.set_my_commands(USER_COMMANDS)
        
        # Set Admin Commands (for admin only)
        await bot.set_my_commands(USER_COMMANDS + ADMIN_COMMANDS, scope=None)
        
        message = (
            "✅ **Commands Set Successfully!**\n\n"
            "All commands are set for admin.\n"
            "User commands (`/start`, `/earn`) are set for all users."
        )
        
    except Exception as e:
        logger.error(f"Failed to set bot commands: {e}")
        message = f"❌ **Failed to set commands:** {e}"
    
    if query:
        keyboard = [[InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_back")]]
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    else:
        await update.message.reply_html(message, parse_mode='HTML')

async def set_welcome_bonus_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = await get_user_lang(user.id)

    if user.id != ADMIN_ID:
        await update.message.reply_html(MESSAGES[lang]["broadcast_admin_only"])
        return

    if len(context.args) != 1:
        await update.message.reply_html(MESSAGES[lang]["setwelbonus_usage"])
        return

    try:
        new_bonus = float(context.args[0])
        if new_bonus < 0:
            raise ValueError
        settings_collection.update_one(
            {"_id": "welcome_bonus"},
            {"$set": {"amount_inr": new_bonus}},
            upsert=True
        )
        await update.message.reply_html(MESSAGES[lang]["setwelbonus_success"].format(new_bonus=new_bonus))
    except ValueError:
        await update.message.reply_html(MESSAGES[lang]["invalid_rate"])
        
async def set_referral_rate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = await get_user_lang(user.id)
    if user.id != ADMIN_ID:
        await update.message.reply_html(MESSAGES[lang]["broadcast_admin_only"])
        return
    if len(context.args) != 1:
        await update.message.reply_html(MESSAGES[lang]["setrate_usage"])
        return
    
    try:
        new_rate = float(context.args[0])
        if new_rate < 0:
            raise ValueError
        settings_collection.update_one(
            {"_id": "referral_rate"},
            {"$set": {"rate_inr": new_rate}},
            upsert=True
        )
        await update.message.reply_html(MESSAGES[lang]["setrate_success"].format(new_rate=new_rate))
    except ValueError:
        await update.message.reply_html(MESSAGES[lang]["invalid_rate"])

async def handle_withdrawal_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if user.id != ADMIN_ID:
        return

    data_parts = query.data.split("_")
    action = data_parts[0]
    user_id_str = data_parts[-1] 
    
    try:
        user_id = int(user_id_str)
    except ValueError:
        await query.edit_message_text("❌ Invalid User ID in callback data.")
        return
    
    withdrawal = withdrawals_collection.find_one(
        {"user_id": user_id, "status": "pending"}
    )
    
    if not withdrawal:
        await query.edit_message_text(f"❌ No **pending** withdrawal request found for user {user_id}. It might have been processed already.")
        return
        
    amount_inr = withdrawal['amount_inr']

    if action == "approve":
        # Update withdrawal status
        withdrawals_collection.update_one(
            {"_id": withdrawal["_id"]},
            {"$set": {"status": "approved", "approved_date": datetime.now()}}
        )
        
        # Reset user earnings (subtract the withdrawn amount)
        users_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"earnings": -(amount_inr / DOLLAR_TO_INR)}}
        )
        
        # Notify user
        try:
            user_lang = await get_user_lang(user_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=MESSAGES[user_lang]["withdrawal_approved_user"].format(amount=amount_inr),
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Could not notify user {user_id} about withdrawal approval: {e}")
        
        await query.edit_message_text(f"✅ Withdrawal of ₹{amount_inr:.2f} **approved** for user {user_id}. Earnings updated.")
            
    elif action == "reject":
        # Update withdrawal status
        withdrawals_collection.update_one(
            {"_id": withdrawal["_id"]},
            {"$set": {"status": "rejected"}}
        )
        
        # Note: We do NOT reset/subtract earnings if rejected. The money stays in their balance.
        
        # Notify user
        try:
            user_lang = await get_user_lang(user_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=MESSAGES[user_lang]["withdrawal_rejected_user"].format(amount=amount_inr),
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Could not notify user {user_id} about withdrawal rejection: {e}")

        await query.edit_message_text(f"❌ Withdrawal of ₹{amount_inr:.2f} **rejected** for user {user_id}.")

# --- MESSAGE HANDLER (MISSIONS AND REFERRAL) ---

async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    
    user_data = users_collection.find_one({"user_id": user.id})
    if not user_data:
        return 

    if chat.type in ["group", "supergroup"]:
        logger.info(f"Message received in group from user: {user.id}")
        lang = user_data.get("lang", "en")

        # --- Mission: Search movies ---
        today = datetime.now().date()
        last_search_date = user_data.get("last_search_date")
        
        daily_searches = user_data.get("daily_searches", 0)
        
        if not last_search_date or not isinstance(last_search_date, datetime) or last_search_date.date() != today:
            # First search of the day
            daily_searches = 1
            users_collection.update_one(
                {"user_id": user.id},
                {"$set": {"daily_searches": 1, "last_search_date": datetime.now()}}
            )
        else:
            # Increment search count
            daily_searches += 1
            users_collection.update_one(
                {"user_id": user.id},
                {"$inc": {"daily_searches": 1}}
            )
        
        mission_key = "search_3_movies"
        missions_completed = user_data.get("missions_completed", {})
        
        if daily_searches == DAILY_MISSIONS[mission_key]["target"] and not missions_completed.get(mission_key):
            mission = DAILY_MISSIONS[mission_key]
            reward_usd = mission["reward"] / DOLLAR_TO_INR
            
            users_collection.update_one(
                {"user_id": user.id},
                {
                    "$inc": {"earnings": reward_usd},
                    "$set": {f"missions_completed.{mission_key}": True}
                }
            )
            
            try:
                updated_data = users_collection.find_one({"user_id": user.id})
                updated_earnings_inr = updated_data.get("earnings", 0.0) * DOLLAR_TO_INR
                mission_name = mission["name"] if lang == "en" else mission["name_hi"]
                
                await context.bot.send_message(
                    chat_id=user.id,
                    text=MESSAGES[lang]["mission_complete"].format(
                        mission_name=mission_name,
                        reward=mission["reward"],
                        new_balance=updated_earnings_inr
                    ),
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Could not notify user about mission completion: {e}")

        # --- Existing referral earning logic ---
        referral_data = referrals_collection.find_one({"referred_user_id": user.id})
        if referral_data:
            referrer_id = referral_data["referrer_id"]
            referrer_data = users_collection.find_one({"user_id": referrer_id})
            
            if referrer_data:
                last_earning_date_doc = referrals_collection.find_one({
                    "referred_user_id": user.id, 
                    "referrer_id": referrer_id
                })
                last_earning_date = last_earning_date_doc.get("last_earning_date") if last_earning_date_doc else None
                today = datetime.now().date()

                if not last_earning_date or not isinstance(last_earning_date, datetime) or last_earning_date.date() < today:
                    # Schedule payment only if it hasn't been paid today
                    asyncio.create_task(add_payment_after_delay(context, user.id, referrer_id))
                    logger.info(f"Payment task scheduled for user {user.id} after 5 minutes.")
                else:
                    logger.info(f"Daily earning limit reached for referrer {referrer_id} from user {user.id}.")

async def add_payment_after_delay(context: ContextTypes.DEFAULT_TYPE, user_id: int, referrer_id: int):
    await asyncio.sleep(300)  # 5 minutes delay
    
    # Re-check to ensure payment wasn't already made today (e.g., by another quick search)
    last_earning_date_doc = referrals_collection.find_one({
        "referred_user_id": user_id, 
        "referrer_id": referrer_id
    })
    last_earning_date = last_earning_date_doc.get("last_earning_date") if last_earning_date_doc else None
    today = datetime.now().date()

    if not last_earning_date or not isinstance(last_earning_date, datetime) or last_earning_date.date() < today:
        
        referrer_tier = await get_user_tier(referrer_id)
        tier_rate = await get_tier_referral_rate(referrer_tier)
        earning_rate_usd = tier_rate / DOLLAR_TO_INR
        
        users_collection.update_one(
            {"user_id": referrer_id},
            {"$inc": {"earnings": earning_rate_usd}}
        )

        referrals_collection.update_one(
            {"referred_user_id": user_id},
            {"$set": {"last_earning_date": datetime.now()}}
        )
        
        updated_referrer_data = users_collection.find_one({"user_id": referrer_id})
        new_balance_inr = updated_referrer_data.get("earnings", 0.0) * DOLLAR_TO_INR
        
        user_data = users_collection.find_one({"user_id": user_id})
        
        # Notify referrer
        referrer_lang = await get_user_lang(referrer_id)
        try:
            await context.bot.send_message(
                chat_id=referrer_id,
                text=MESSAGES[referrer_lang]["daily_earning_update"].format(
                    full_name=user_data.get("full_name", "your referral"), 
                    new_balance=new_balance_inr
                ),
                parse_mode='HTML'
            )
        except (TelegramError, TimedOut) as e:
            logger.error(f"Could not send daily earning update to referrer {referrer_id}: {e}")
            
        logger.info(f"Updated earnings for referrer {referrer_id}. New balance (INR): {new_balance_inr}")
    else:
        logger.info(f"Payment for {user_id} to {referrer_id} already processed today. Skipping delayed payment.")

# --- OTHER COMMANDS (STATS, BROADCAST, ETC.) ---

async def show_movie_groups_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    lang = await get_user_lang(query.from_user.id)

    keyboard = [
        [InlineKeyboardButton("🆕 New Movie Group", url=NEW_MOVIE_GROUP_LINK)],
        [InlineKeyboardButton("Join Movies Group", url=MOVIE_GROUP_LINK)],
        [InlineKeyboardButton("Join All Movie Groups", url=ALL_GROUPS_LINK)],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = (
        f"<b>🎬 Movie Groups</b>\n\n"
        f"{MESSAGES[lang]['start_step1']}"
    )

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    lang = await get_user_lang(query.from_user.id)
    keyboard = [
        [InlineKeyboardButton("🎬 Movie Groups", callback_data="show_movie_groups_menu")],
        [InlineKeyboardButton("💰 Earning Panel", callback_data="show_earning_panel")],
        [InlineKeyboardButton(MESSAGES[lang]["language_choice"], callback_data="select_lang")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = (
        f"{MESSAGES[lang]['start_greeting']}\n\n"
        f"<b>1.</b> {MESSAGES[lang]['start_step1']}\n"
        f"<b>2.</b> {MESSAGES[lang]['start_step2']}\n"
        f"<b>3.</b> {MESSAGES[lang]['start_step3']}"
    )
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

async def earn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Use inline button to access panel from /earn
    lang = await get_user_lang(update.effective_user.id)
    keyboard = [[InlineKeyboardButton("💰 Earning Panel", callback_data="show_earning_panel")]]
    await update.message.reply_html(MESSAGES[lang]["earning_panel_message"], reply_markup=InlineKeyboardMarkup(keyboard))


async def clear_earn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await get_user_lang(update.effective_user.id)
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_html(MESSAGES[lang]["broadcast_admin_only"])
        return
    if len(context.args) != 1:
        await update.message.reply_html(MESSAGES[lang]["clear_earn_usage"])
        return
    try:
        user_id_to_clear = int(context.args[0])
        result = users_collection.update_one({"user_id": user_id_to_clear}, {"$set": {"earnings": 0.0}})
        if result.modified_count > 0:
            await update.message.reply_html(MESSAGES[lang]["clear_earn_success"].format(user_id=user_id_to_clear))
        else:
            await update.message.reply_html(MESSAGES[lang]["clear_earn_not_found"].format(user_id=user_id_to_clear))
    except ValueError:
        await update.message.reply_html(MESSAGES[lang]["clear_earn_usage"])

async def check_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await get_user_lang(update.effective_user.id)
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_html(MESSAGES[lang]["broadcast_admin_only"])
        return
    if len(context.args) != 1:
        await update.message.reply_html(MESSAGES[lang]["check_stats_usage"])
        return
    try:
        user_id_to_check = int(context.args[0])
        user_data = users_collection.find_one({"user_id": user_id_to_check})
        if user_data:
            earnings_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR
            referrals = referrals_collection.count_documents({"referrer_id": user_id_to_check})
            await update.message.reply_html(MESSAGES[lang]["check_stats_message"].format(user_id=user_id_to_check, earnings=earnings_inr, referrals=referrals))
        else:
            await update.message.reply_html(MESSAGES[lang]["check_stats_not_found"].format(user_id=user_id_to_check))
    except ValueError:
        await update.message.reply_html(MESSAGES[lang]["check_stats_usage"])
        
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await get_user_lang(update.effective_user.id)
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_html(MESSAGES[lang]["broadcast_admin_only"])
        return
    total_users = users_collection.count_documents({})
    approved_users = users_collection.count_documents({"is_approved": True})
    await update.message.reply_html(MESSAGES[lang]["stats_message"].format(total_users=total_users, approved_users=approved_users))

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await get_user_lang(update.effective_user.id)
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_html(MESSAGES[lang]["broadcast_admin_only"])
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_html(MESSAGES[lang]["broadcast_message"])
        return
        
    forwarded_message = update.message.reply_to_message
    
    users_cursor = users_collection.find({})
    total_users = users_collection.count_documents({})
    count = 0
    failed_count = 0
    
    await update.message.reply_html(f"📢 **Starting broadcast to all {total_users} users...**")

    for user in users_cursor:
        try:
            await context.bot.forward_message(
                chat_id=user["user_id"],
                from_chat_id=update.effective_chat.id,
                message_id=forwarded_message.message_id
            )
            count += 1
            await asyncio.sleep(0.05) # Delay to avoid flood limits
        except Exception:
            failed_count += 1
            pass 

    await update.message.reply_html(f"✅ **Broadcast Finished!**\n\nSent to: **{count}** users.\nFailed to send (blocked/error): **{failed_count}** users.")


# --- MAIN FUNCTION ---

def main() -> None:
    """Start the bot."""
    if not BOT_TOKEN or not MONGO_URI:
        logger.error("BOT_TOKEN or MONGO_URI is missing.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # Command Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("earn", earn_command)) 
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("clearearn", clear_earn_command))
    application.add_handler(CommandHandler("checkstats", check_stats_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("setrate", set_referral_rate_command))
    application.add_handler(CommandHandler("setwelbonus", set_welcome_bonus_command))
    application.add_handler(CommandHandler("setcommands", set_bot_commands_command))
    
    # Callback Handlers
    application.add_handler(CallbackQueryHandler(show_earning_panel, pattern="^show_earning_panel$"))
    application.add_handler(CallbackQueryHandler(show_movie_groups_menu, pattern="^show_movie_groups_menu$"))
    application.add_handler(CallbackQueryHandler(back_to_main_menu, pattern="^back_to_main_menu$"))
    application.add_handler(CallbackQueryHandler(language_menu, pattern="^select_lang$")) # <-- FIXED
    application.add_handler(CallbackQueryHandler(handle_lang_choice, pattern="^lang_")) # <-- ADDED
    application.add_handler(CallbackQueryHandler(show_help, pattern="^show_help$"))
    application.add_handler(CallbackQueryHandler(show_refer_link, pattern="^show_refer_link$"))
    application.add_handler(CallbackQueryHandler(show_withdraw_details_new, pattern="^show_withdraw_details_new$"))
    application.add_handler(CallbackQueryHandler(claim_daily_bonus, pattern="^claim_daily_bonus$")) # <-- ADDED
    
    # New Features Callback Handlers
    application.add_handler(CallbackQueryHandler(spin_wheel_command, pattern="^spin_wheel$"))
    application.add_handler(CallbackQueryHandler(show_missions, pattern="^show_missions$")) # <-- ADDED
    application.add_handler(CallbackQueryHandler(request_withdrawal, pattern="^request_withdrawal$"))
    application.add_handler(CallbackQueryHandler(show_tier_benefits, pattern="^show_tier_benefits$")) # <-- ADDED
    
    # Admin Panel Callbacks
    application.add_handler(CallbackQueryHandler(handle_admin_callbacks, pattern="^admin_")) 
    application.add_handler(CallbackQueryHandler(handle_withdrawal_approval, pattern="^(approve|reject)_withdraw_\\d+$"))
    
    # Group Message Handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_group_messages))

    # Start the Bot
    if WEB_SERVER_URL and BOT_TOKEN:
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=f"/{BOT_TOKEN}",
            webhook_url=f"{WEB_SERVER_URL}/{BOT_TOKEN}",
            allowed_updates=Update.ALL_TYPES
        )
        logger.info(f"Bot started in Webhook Mode on port {PORT}.")
    else:
        logger.info("WEB_SERVER_URL not found, starting in Polling Mode.")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Bot started in Polling Mode.")

if __name__ == "__main__":
    main()
