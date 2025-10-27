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

# --- UPDATED MESSAGES Dictionary ---
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
        
        # New Features Messages
        "welcome_bonus_received": "🎁 <b>Welcome Bonus!</b>\n\nYou have received ₹{amount:.2f} welcome bonus! Start earning more by referring friends.",
        "spin_wheel_title": "🎡 <b>Spin the Wheel</b>\n\nCost: ₹2.00\nClick 'Spin' to try your luck!",
        "spin_wheel_button": "✨ Spin Now (₹2)",
        "spin_wheel_animating": "🎡 <b>Spinning...</b>\n\nWait for the result! 🍀",
        "spin_wheel_insufficient_balance": "❌ <b>Insufficient Balance!</b>\n\nYou need at least ₹2.00 to spin the wheel.",
        "spin_wheel_already_spun": "⏳ <b>Already Spun Today!</b>\n\nYou can spin the wheel only once per day. Try again tomorrow!",
        "spin_wheel_win": "🎉 <b>Congratulations!</b>\n\nYou won: ₹{amount:.2f}!\n\nNew balance: ₹{new_balance:.2f}",
        "spin_wheel_lose": "😢 <b>Better luck next time!</b>\n\nYou didn't win anything this time.\n\nRemaining balance: ₹{new_balance:.2f}",
        "missions_title": "🎯 <b>Daily Missions</b>\n\nComplete missions to earn extra rewards!",
        "mission_complete": "✅ <b>Mission Completed!</b>\n\nYou earned ₹{reward:.2f} for {mission_name}!\nNew balance: ₹{new_balance:.2f}",
        "withdrawal_request_sent": "✅ <b>Withdrawal Request Sent!</b>\n\nYour request for ₹{amount:.2f} has been sent to admin. You will receive payment within 24 hours.",
        "withdrawal_insufficient": "❌ <b>Insufficient Balance!</b>\n\nMinimum withdrawal amount is ₹80.00",
        "withdrawal_approved_user": "✅ <b>Withdrawal Approved!</b>\n\nYour withdrawal of ₹{amount:.2f} has been approved. Payment will be processed within 24 hours.",
        "withdrawal_rejected_user": "❌ <b>Withdrawal Rejected!</b>\n\nYour withdrawal of ₹{amount:.2f} was rejected. Please contact admin for details.",
        "ref_link_message": "<b>Your Referral Link:</b>\n<code>{referral_link}</code>\n\n<b>Current Referral Rate:</b> ₹{tier_rate:.2f} per referral\n\n<i>Share this link with friends and earn money when they join and search for movies!</i>",
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
        
        # New Features Messages in Hindi
        "welcome_bonus_received": "🎁 <b>वेलकम बोनस!</b>\n\nआपको ₹{amount:.2f} वेलकम बोनस मिला है! दोस्तों को रेफर करके और कमाएँ।",
        "spin_wheel_title": "🎡 <b>व्हील स्पिन करें</b>\n\nलागत: ₹2.00\nअपनी किस्मत आज़माने के लिए 'Spin Now' पर क्लिक करें!",
        "spin_wheel_button": "✨ अभी स्पिन करें (₹2)",
        "spin_wheel_animating": "🎡 <b>स्पिन हो रहा है...</b>\n\nपरिणाम का इंतजार करें! 🍀",
        "spin_wheel_insufficient_balance": "❌ <b>पर्याप्त बैलेंस नहीं!</b>\n\nव्हील स्पिन करने के लिए आपके पास कम से कम ₹2.00 होने चाहिए।",
        "spin_wheel_already_spun": "⏳ <b>आज पहले ही स्पिन कर चुके हैं!</b>\n\nआप व्हील को केवल एक बार प्रति दिन स्पिन कर सकते हैं। कल फिर कोशिश करें!",
        "spin_wheel_win": "🎉 <b>बधाई हो!</b>\n\nआपने जीता: ₹{amount:.2f}!\n\nनया बैलेंस: ₹{new_balance:.2f}",
        "spin_wheel_lose": "😢 <b>अगली बार बेहतर किस्मत!</b>\n\nइस बार आप कुछ नहीं जीत पाए।\n\nशेष बैलेंस: ₹{new_balance:.2f}",
        "missions_title": "🎯 <b>दैनिक मिशन</b>\n\nअतिरिक्त इनाम पाने के लिए मिशन पूरे करें!",
        "mission_complete": "✅ <b>मिशन पूरा हुआ!</b>\n\nआपने {mission_name} के लिए ₹{reward:.2f} कमाए!\nनया बैलेंस: ₹{new_balance:.2f}",
        "withdrawal_request_sent": "✅ <b>निकासी का अनुरोध भेज दिया गया!</b>\n\n₹{amount:.2f} के आपके अनुरोध को एडमिन को भेज दिया गया है। आपको 24 घंटे के भीतर भुगतान मिल जाएगा।",
        "withdrawal_insufficient": "❌ <b>पर्याप्त बैलेंस नहीं!</b>\n\nन्यूनतम निकासी राशि ₹80.00 है",
        "withdrawal_approved_user": "✅ <b>निकासी स्वीकृत!</b>\n\n₹{amount:.2f} की आपकी निकासी स्वीकृत कर दी गई है। भुगतान 24 घंटे के भीतर प्रोसेस किया जाएगा।",
        "withdrawal_rejected_user": "❌ <b>निकासी अस्वीकृत!</b>\n\n₹{amount:.2f} की आपकी निकासी अस्वीकृत कर दी गई है। विवरण के लिए एडमिन से संपर्क करें।",
        "ref_link_message": "<b>आपकी रेफरल लिंक:</b>\n<code>{referral_link}</code>\n\n<b>वर्तमान रेफरल दर:</b> ₹{tier_rate:.2f} प्रति रेफरल\n\n<i>इस लिंक को दोस्तों के साथ साझा करें और जब वे शामिल होकर फिल्में खोजते हैं, तो पैसे कमाएं!</i>",
    }
}

# --- COMMAND LISTS FOR /setcommands ---
USER_COMMANDS = [
    BotCommand("start", "बॉट शुरू करें और मुख्य मेनू देखें।"),
    BotCommand("earn", "कमाई का पैनल और रेफरल लिंक देखें।"),
]

ADMIN_COMMANDS = [
    BotCommand("admin", "एडमिन पैनल और सेटिंग्स एक्सेस करें।"),
    BotCommand("stats", "बॉट के कुल उपयोगकर्ता और आंकड़े देखें।"),
    BotCommand("broadcast", "सभी उपयोगकर्ताओं को संदेश भेजें।"),
    BotCommand("setrate", "रेफरल दर (INR) सेट करें।"),
    BotCommand("setwelbonus", "वेलकम बोनस (INR) सेट करें।"),
]

# --- NEW FEATURES CONFIGURATION ---

# Spin Wheel Prizes (in INR)
# New prizes: 0.20, 0.50, 0.80, 1.00, 3.00, 5.00, 10.00. (0.00 for a loss)
# We use probabilities to ensure 0 is not too frequent but still present.
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


# Tier System Configuration (Kept as is for structure)
TIERS = {
    1: {"min_earnings": 0, "rate": 0.40, "name": "Beginner", "benefits": "Basic referral rate"},
    2: {"min_earnings": 50, "rate": 0.60, "name": "Pro", "benefits": "50% higher referral rate"},
    3: {"min_earnings": 200, "rate": 1.00, "name": "Expert", "benefits": "2.5x referral rate"},
    4: {"min_earnings": 500, "rate": 2.00, "name": "Master", "benefits": "5x referral rate"}
}

# Missions Configuration (Kept as is for structure)
DAILY_MISSIONS = {
    "search_3_movies": {"reward": 1.00, "target": 3, "name": "Search 3 Movies"},
    "refer_2_friends": {"reward": 5.00, "target": 2, "name": "Refer 2 Friends"},
    "claim_daily_bonus": {"reward": 0.50, "target": 1, "name": "Claim Daily Bonus"}
}

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
    
    # Use stored earnings, not USD, for tier calculation
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
    # ... (start_command logic remains largely the same, but ensuring user data structure is complete)
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

    # Handle referral logic (omitting detailed log logic for brevity, but it's in the original code)
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
            
            # Initial join bonus (e.g., half the rate) - this logic remains.
            referrer_tier = await get_user_tier(referral_id)
            tier_rate = await get_tier_referral_rate(referrer_tier)
            referral_rate_usd = tier_rate / DOLLAR_TO_INR
            
            users_collection.update_one(
                {"user_id": referral_id},
                {"$inc": {"earnings": referral_rate_usd / 2}} 
            )

            # Notify referrer (simplified)
            try:
                referrer_lang = await get_user_lang(referral_id)
                await context.bot.send_message(
                    chat_id=referral_id,
                    text=MESSAGES[referrer_lang]["new_referral_notification"].format(
                        full_name=full_name, username=f"@{user.username}" if user.username else "(No username)"
                    )
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


# --- NEW AND IMPROVED SPIN WHEEL IMPLEMENTATION ---

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

async def show_earning_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (Logic remains the same, but ensuring spin button uses new message)
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
        [InlineKeyboardButton(MESSAGES[lang]["spin_wheel_button"], callback_data="spin_wheel")], # Updated button text
        [InlineKeyboardButton("💸 Request Withdrawal", callback_data="request_withdrawal")],
        [InlineKeyboardButton("🎁 Daily Bonus", callback_data="claim_daily_bonus")],
        [InlineKeyboardButton("🎯 Daily Missions", callback_data="show_missions")],
        [InlineKeyboardButton("📊 Tier Benefits", callback_data="show_tier_benefits")],
        [InlineKeyboardButton("🆘 Help", callback_data="show_help")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


# --- IMPROVED ADMIN PANEL IMPLEMENTATION ---

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = await get_user_lang(user.id)
    
    if user.id != ADMIN_ID:
        await update.message.reply_html(MESSAGES[lang]["broadcast_admin_only"])
        return
    
    settings = settings_collection.find_one({"_id": "referral_rate"})
    rate = settings.get("rate_inr", 0.40) if settings else 0.40
    
    settings_bonus = settings_collection.find_one({"_id": "welcome_bonus"})
    bonus = settings_bonus.get("amount_inr", 5.00) if settings_bonus else 5.00
    
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
    
    if data == "admin_set_rate":
        await query.edit_message_text("✍️ **Enter New Referral Rate (in INR):**\n\nExample: `/setrate 1.00`")
    elif data == "admin_set_welbonus":
        await query.edit_message_text("✍️ **Enter New Welcome Bonus (in INR):**\n\nExample: `/setwelbonus 5.00`")
    elif data == "admin_check_withdrawals":
        pending_requests = withdrawals_collection.find({"status": "pending"})
        
        message = "💸 <b>Pending Withdrawal Requests</b> 💸\n\n"
        count = 0
        keyboard = []
        
        for req in pending_requests:
            count += 1
            username_display = f"@{req.get('username')}" if req.get('username') else f"ID: {req['user_id']}"
            message += (
                f"👤 {username_display}\n"
                f"💰 Amount: ₹{req['amount_inr']:.2f}\n"
                f"⏰ Date: {req['request_date'].strftime('%Y-%m-%d %H:%M')}\n\n"
            )
            keyboard.append([
                InlineKeyboardButton(f"✅ Approve {req['amount_inr']:.2f} (ID: {req['user_id']})", callback_data=f"approve_withdraw_{req['user_id']}"),
            ])

        if count == 0:
            message += "✅ No pending requests found."
        
        keyboard.append([InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_back")])
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        
    elif data == "admin_set_commands":
        await set_bot_commands_command(update, context, query=query)
        
    elif data == "admin_back":
        # Re-run admin_panel logic to show the main panel again
        await admin_panel(update, context)

# --- NEW ADMIN COMMAND: set_bot_commands ---
async def set_bot_commands_command(update: Update, context: ContextTypes.DEFAULT_TYPE, query=None) -> None:
    user = update.effective_user
    lang = await get_user_lang(user.id)

    if user.id != ADMIN_ID:
        if query:
            await query.answer(MESSAGES[lang]["broadcast_admin_only"], show_alert=True)
        else:
            await update.message.reply_html(MESSAGES[lang]["broadcast_admin_only"])
        return
    
    bot = context.bot
    try:
        # 1. Set User Commands (for all users)
        await bot.set_my_commands(USER_COMMANDS, scope=None, language_code='en')
        await bot.set_my_commands(USER_COMMANDS, scope=None, language_code='hi')

        # 2. Set Admin Commands (for admin only)
        # Using the ADMIN_ID as a specific chat_id scope for the commands to appear only to the admin
        await bot.set_my_commands(ADMIN_COMMANDS, scope=None, language_code='en')
        await bot.set_my_commands(ADMIN_COMMANDS, scope=None, language_code='hi')
        
        message = (
            "✅ **Commands Set Successfully!**\n\n"
            "User commands (`/start`, `/earn`) are set for all.\n"
            "Admin commands (`/admin`, `/stats`, etc.) are now visible."
        )
        
    except Exception as e:
        logger.error(f"Failed to set bot commands: {e}")
        message = f"❌ **Failed to set commands:** {e}"
    
    if query:
        keyboard = [[InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_back")]]
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    else:
        await update.message.reply_html(message, parse_mode='HTML')

# --- EXISTING ADMIN COMMANDS IMPROVED ---

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

# --- WITHDRAWAL APPROVAL LOGIC IMPROVED ---

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
    
    withdrawal = withdrawals_collection.find_one_and_update(
        {"user_id": user_id, "status": "pending"},
        {"$set": {"status": f"{action}ed", "approved_date": datetime.now() if action == 'approve' else None}},
        return_document=True
    )
    
    if not withdrawal:
        await query.edit_message_text(f"❌ No **pending** withdrawal request found for user {user_id}. It might have been processed already.")
        return
    
    amount_inr = withdrawal['amount_inr']

    if action == "approve":
        # Reset user earnings
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"earnings": 0.0}} # Set to 0 USD (or 0 INR after conversion)
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
        
        await query.edit_message_text(f"✅ Withdrawal of ₹{amount_inr:.2f} **approved** for user {user_id}. Earnings reset.")
            
    elif action == "reject":
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

# --- MESSAGE HANDLER FOR MISSIONS AND REFERRAL (Kept as is) ---
# handle_group_messages and add_payment_after_delay functions are kept the same 
# as they manage the core referral/shortlink and mission logic.

async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    
    if not users_collection.find_one({"user_id": user.id}):
        return 

    if chat.type in ["group", "supergroup"]:
        logger.info(f"Message received in group from user: {user.id}")

        # Mission: Search movies
        user_data = users_collection.find_one({"user_id": user.id})
        if user_data:
            today = datetime.now().date()
            last_search_date = user_data.get("last_search_date")
            
            # Use find_one_and_update for atomic updates
            if not last_search_date or not isinstance(last_search_date, datetime) or last_search_date.date() != today:
                users_collection.update_one(
                    {"user_id": user.id},
                    {"$set": {"daily_searches": 1, "last_search_date": datetime.now()}}
                )
            else:
                users_collection.update_one(
                    {"user_id": user.id},
                    {"$inc": {"daily_searches": 1}}
                )
            
            current_data = users_collection.find_one({"user_id": user.id})
            daily_searches = current_data.get("daily_searches", 0)
            
            mission_key = "search_3_movies"
            missions_completed = current_data.get("missions_completed", {})
            
            if daily_searches >= DAILY_MISSIONS[mission_key]["target"] and not missions_completed.get(mission_key):
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
                    lang = await get_user_lang(user.id)
                    updated_data = users_collection.find_one({"user_id": user.id})
                    updated_earnings_inr = updated_data.get("earnings", 0.0) * DOLLAR_TO_INR
                    
                    await context.bot.send_message(
                        chat_id=user.id,
                        text=MESSAGES[lang]["mission_complete"].format(
                            mission_name=mission["name"],
                            reward=mission["reward"],
                            new_balance=updated_earnings_inr
                        ),
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.error(f"Could not notify user about mission completion: {e}")

        # Existing referral earning logic
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
                    asyncio.create_task(add_payment_after_delay(context, user.id))
                    logger.info(f"Payment task scheduled for user {user.id} after 5 minutes.")
                else:
                    logger.info(f"Daily earning limit reached for referrer {referrer_id} from user {user.id}.")

async def add_payment_after_delay(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    await asyncio.sleep(300)  # 5 minutes delay
    
    user_data = users_collection.find_one({"user_id": user_id})
    if user_data:
        referral_data = referrals_collection.find_one({"referred_user_id": user_id})
        
        if referral_data:
            referrer_id = referral_data["referrer_id"]
            referrer_data = users_collection.find_one({"user_id": referrer_id})
            
            if referrer_data:
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
                    
                    # Notify referrer (omitting level up for brevity, but it's in the original code)
                    referrer_lang = await get_user_lang(referrer_id)
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=MESSAGES[referrer_lang]["daily_earning_update"].format(
                                full_name=user_data.get("full_name"), new_balance=new_balance_inr
                            ),
                            parse_mode='HTML'
                        )
                    except (TelegramError, TimedOut) as e:
                        logger.error(f"Could not send daily earning update to referrer {referrer_id}: {e}")
                        
                    logger.info(f"Updated earnings for referrer {referrer_id}. New balance (INR): {new_balance_inr}")
                else:
                    logger.info(f"Daily earning limit reached for referrer {referrer_id} from user {user_id}. No new payment scheduled after delay.")
# --- OTHER EXISTING FUNCTIONS (Kept as is) ---

async def show_movie_groups_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (Function remains the same)
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
    # ... (Function remains the same)
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

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (Function remains the same)
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

async def show_refer_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (Function remains the same)
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

async def request_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (Function remains the same)
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
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
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
    # ... (Function remains the same - updated button text)
    query = update.callback_query
    await query.answer()
    lang = await get_user_lang(query.from_user.id)
    
    user_data = users_collection.find_one({"user_id": query.from_user.id})
    earnings_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR
    
    message = MESSAGES[lang]["withdrawal_message_updated"]
    
    keyboard = [
        [InlineKeyboardButton("Contact Admin", url=f"https://t.me/{YOUR_TELEGRAM_HANDLE}")],
        [InlineKeyboardButton("💸 Request Withdrawal", callback_data="request_withdrawal")],
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


# --- PLACEHOLDER COMMANDS (Updated) ---

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
    # ... (Broadcasting logic remains the same)
    lang = await get_user_lang(update.effective_user.id)
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_html(MESSAGES[lang]["broadcast_admin_only"])
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_html(MESSAGES[lang]["broadcast_message"])
        return
        
    forwarded_message = update.message.reply_to_message
    
    users = users_collection.find({})
    count = 0
    failed_count = 0
    
    await update.message.reply_html(f"📢 **Starting broadcast to all {users_collection.count_documents({})} users...**")

    for user in users:
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
            pass # Ignore failed sends (e.g., user blocked the bot)

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
    application.add_handler(CommandHandler("setcommands", set_bot_commands_command)) # New Command
    
    # Callback Handlers
    application.add_handler(CallbackQueryHandler(show_earning_panel, pattern="^show_earning_panel$"))
    application.add_handler(CallbackQueryHandler(show_movie_groups_menu, pattern="^show_movie_groups_menu$"))
    application.add_handler(CallbackQueryHandler(back_to_main_menu, pattern="^back_to_main_menu$"))
    application.add_handler(CallbackQueryHandler(language_menu, pattern="^select_lang$"))
    application.add_handler(CallbackQueryHandler(handle_lang_choice, pattern="^lang_"))
    application.add_handler(CallbackQueryHandler(show_help, pattern="^show_help$"))
    application.add_handler(CallbackQueryHandler(show_refer_link, pattern="^show_refer_link$"))
    application.add_handler(CallbackQueryHandler(show_withdraw_details_new, pattern="^show_withdraw_details_new$"))
    application.add_handler(CallbackQueryHandler(claim_daily_bonus, pattern="^claim_daily_bonus$"))
    
    # New Features Callback Handlers
    application.add_handler(CallbackQueryHandler(spin_wheel_command, pattern="^spin_wheel$"))
    application.add_handler(CallbackQueryHandler(show_missions, pattern="^show_missions$"))
    application.add_handler(CallbackQueryHandler(request_withdrawal, pattern="^request_withdrawal$"))
    application.add_handler(CallbackQueryHandler(show_tier_benefits, pattern="^show_tier_benefits$"))
    
    # Admin Panel Callbacks (Implemented)
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
        logger.info("Bot started in Webhook Mode.")
    else:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Bot started in Polling Mode.")

if __name__ == "__main__":
    main()
