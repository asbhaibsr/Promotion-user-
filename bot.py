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

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
except (TypeError, ValueError, AttributeError):
    ADMIN_ID = None
    logger.warning("ADMIN_ID is not set or invalid. Some features may not work.")

YOUR_TELEGRAM_HANDLE = os.getenv("YOUR_TELEGRAM_HANDLE", "telegram") 
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID") # <-- आपका लॉग चैनल ID यहाँ से लोड होगा

# Group links
NEW_MOVIE_GROUP_LINK = "https://t.me/asfilter_bot"
MOVIE_GROUP_LINK = "https://t.me/asfilter_group" 
ALL_GROUPS_LINK = "https://t.me/addlist/6urdhhdLRqhiZmQ1"

# !! ज़रूरी !! - अपना स्क्रीनशॉट URL यहाँ बदलें
EXAMPLE_SCREENSHOT_URL = os.getenv("EXAMPLE_SCREENSHOT_URL", "https://envs.sh/ric.jpg")

# NEW: Channel Join Configuration
CHANNEL_USERNAME = "@asbhai_bsr"
CHANNEL_ID = -1002283182645 # Channel ID for checking membership
CHANNEL_BONUS = 15.00 # 15 Rs for joining once

# Load Render-specific variables
WEB_SERVER_URL = os.getenv("WEB_SERVER_URL")
PORT = int(os.getenv("PORT", 8000))

# Connect to MongoDB
try:
    client = MongoClient(MONGO_URI)
    db = client.get_database('bot_database')
    users_collection = db.get_collection('users')
    referrals_collection = db.get_collection('referrals')
    settings_collection = db.get_collection('settings')
    withdrawals_collection = db.get_collection('withdrawals')
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    # Exit or handle gracefully if DB connection is critical

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
    1: {"min_earnings": 0, "rate": 0.40, "name": "Beginner", "benefits_en": "Basic referral rate (₹0.40)", "benefits_hi": "सामान्य रेफरल दर (₹0.40)"},
    2: {"min_earnings": 50, "rate": 0.60, "name": "Pro", "benefits_en": "50% higher referral rate (₹0.60)", "benefits_hi": "50% ज़्यादा रेफरल दर (₹0.60)"},
    3: {"min_earnings": 200, "rate": 1.00, "name": "Expert", "benefits_en": "2.5x referral rate (₹1.00)", "benefits_hi": "2.5 गुना रेफरल दर (₹1.00)"},
    4: {"min_earnings": 500, "rate": 2.00, "name": "Master", "benefits_en": "5x referral rate (₹2.00)", "benefits_hi": "5 गुना रेफरल दर (₹2.00)"}
}

# Missions Configuration
DAILY_MISSIONS = {
    "search_3_movies": {"reward": 1.00, "target": 3, "name": "Search 3 Movies", "name_hi": "3 फिल्में खोजें"},
    "refer_2_friends": {"reward": 5.00, "target": 2, "name": "Refer 2 Friends", "name_hi": "2 दोस्तों को रेफ़र करें"},
    "claim_daily_bonus": {"reward": 0.50, "target": 1, "name": "Claim Daily Bonus", "name_hi": "दैनिक बोनस क्लेम करें"}
}

# --- ALL MESSAGES (INCL. MISSING ONES) ---
# FIX 1: Removed ** around bold text, made sure code blocks are only for links/IDs.
MESSAGES = {
    "en": {
        "start_greeting": "Hey 👋! Welcome to the Movies Group Bot. Get your favorite movies by following these simple steps:",
        "start_step1": "Click the button below to join our movie group.",
        "start_step2": "Go to the group and type the name of the movie you want.",
        "start_step3": "The bot will give you a link to your movie.",
        "language_choice": "Choose your language:",
        "language_selected": "Language changed to English.",
        "help_message_text": "<b>🤝 How to Earn Money</b>\n\n1️⃣ <b>Get Your Link:</b> Use the 'My Refer Link' button to get your unique referral link.\n\n2️⃣ <b>Share Your Link:</b> Share this link with your friends. Tell them to start the bot and join our movie group.\n\n3️⃣ <b>Earn:</b> When a referred friend searches for a movie in the group and completes the shortlink process, you earn money! You can earn from each friend up to 3 times per day.",
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
        # FIX 3: Added mission specific messages
        "mission_search_note": "⏳ Search 3 Movies ({current}/{target}) [In Progress]\n\n**Note:** This mission is completed when your *referred friend* searches 3 movies, not you.",
        "mission_search_progress": "⏳ Search 3 Movies ({current}/{target}) [In Progress]",
        "mission_complete": "✅ <b>Mission Completed!</b>\n\nYou earned ₹{reward:.2f} for {mission_name}!\nNew balance: ₹{new_balance:.2f}",
        "withdrawal_request_sent": "✅ <b>Withdrawal Request Sent!</b>\n\nYour request for ₹{amount:.2f} has been sent to admin. You will receive payment within 24 hours.",
        "withdrawal_insufficient": "❌ <b>Insufficient Balance!</b>\n\nMinimum withdrawal amount is ₹80.00",
        "withdrawal_approved_user": "✅ <b>Withdrawal Approved!</b>\n\nYour withdrawal of ₹{amount:.2f} has been approved. Payment will be processed within 24 hours.",
        "withdrawal_rejected_user": "❌ <b>Withdrawal Rejected!</b>\n\nYour withdrawal of ₹{amount:.2f} was rejected. Please contact admin for details.",
        "ref_link_message": "<b>Your Referral Link:</b>\n<code>{referral_link}</code>\n\n<b>Current Referral Rate:</b> ₹{tier_rate:.2f} per referral\n\n<i>Share this link with friends and earn money when they join and search for movies!</i>",
        "new_referral_notification": "🎉 <b>New Referral!</b>\n\n{full_name} ({username}) has joined using your link!\n\n💰 You received a joining bonus of ₹{bonus:.2f}!", # Added bonus info
        "daily_earning_update": "💰 <b>Referral Earning!</b> ({count}/3)\n\nYou earned ₹{amount:.2f} from your referral {full_name}. \nNew balance: ₹{new_balance:.2f}",
        "clear_earn_usage": "❌ Usage: /clearearn <user_id>",
        "clear_earn_success": "✅ Earnings for user {user_id} have been cleared.",
        "clear_earn_not_found": "❌ User {user_id} not found.",
        "check_stats_usage": "❌ Usage: /checkstats <user_id>",
        "check_stats_message": "📊 <b>User Stats</b>\n\nID: {user_id}\nEarnings: ₹{earnings:.2f}\nReferrals: {referrals}",
        "check_stats_not_found": "❌ User {user_id} not found.",
        "stats_message": "📊 <b>Bot Stats</b>\n\nTotal Users: {total_users}\nApproved Users: {approved_users}",
        "channel_bonus_claimed": "✅ <b>Channel Join Bonus!</b>\nYou have successfully claimed ₹{amount:.2f} for joining {channel}.\nNew balance: ₹{new_balance:.2f}",
        "channel_not_joined": "❌ <b>Channel Not Joined!</b>\nYou must join our channel {channel} to claim the bonus.",
        "channel_already_claimed": "⏳ <b>Bonus Already Claimed!</b>\nYou have already claimed the channel join bonus.",
        "top_users_title": "🏆 <b>Top 10 Earners</b> 🏆\n\n",
        "clear_junk_success": "✅ <b>Junk Data Cleared!</b>\n\nUsers: {deleted_users} deleted.\nReferrals: {deleted_referrals} deleted.",
        "clear_junk_admin_only": "❌ This command is for the bot admin only.",
        "tier_benefits_title": "👑 <b>Tier System Benefits</b> 👑\n\nYour earning rate increases as you earn more. Reach higher tiers for more money per referral!",
        "tier_info": "🔸 <b>{tier_name} (Level {tier}):</b> Min Earning: ₹{min_earnings:.2f}\n   - Benefit: {benefit}",
        "help_menu_title": "🆘 <b>Help & Support</b>",
        "help_menu_text": "If you have any questions, payment issues, or need to contact the admin, use the button below. Remember to read the 'How to Earn' (Referral Example) section first!",
    },
    "hi": {
        "start_greeting": "नमस्ते 👋! मूवी ग्रुप बॉट में आपका स्वागत है। इन आसान स्टेप्स को फॉलो करके अपनी पसंदीदा मूवी पाएँ:",
        "start_step1": "हमारे मूवी ग्रुप में शामिल होने के लिए नीचे दिए गए बटन पर क्लिक करें।",
        "start_step2": "ग्रुप में जाकर अपनी मनपसंद मूवी का नाम लिखें।",
        "start_step3": "बॉट आपको आपकी मूवी की लिंक देगा।",
        "language_choice": "अपनी भाषा चुनें:",
        "language_selected": "भाषा हिंदी में बदल दी गई है।",
        "help_message_text": "<b>🤝 पैसे कैसे कमाएं</b>\n\n1️⃣ <b>अपनी लिंक पाएं:</b> 'My Refer Link' बटन का उपयोग करके अपनी रेफरल लिंक पाएं।\n\n2️⃣ <b>शेयर करें:</b> इस लिंक को अपने दोस्तों के साथ शेयर करें। उन्हें बॉट शुरू करने और हमारे मूवी ग्रुप में शामिल होने के लिए कहें।\n\n3️⃣ <b>कमाई करें:</b> जब आपका रेफर किया गया दोस्त ग्रुप में कोई मूवी खोजता है और शॉर्टलिंक प्रक्रिया पूरी करता है, तो आप पैसे कमाते हैं! आप प्रत्येक दोस्त से एक दिन में 3 बार तक कमाई कर सकते हैं।",
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
        # FIX 3: Added mission specific messages
        "mission_search_note": "⏳ 3 फिल्में खोजें ({current}/{target}) [प्रगति में]\n\n**ध्यान दें:** यह मिशन तब पूरा होता है जब आपका *रेफर किया गया दोस्त* 3 फिल्में खोजता है, न कि आप।",
        "mission_search_progress": "⏳ 3 फिल्में खोजें ({current}/{target}) [प्रगति में]",
        "mission_complete": "✅ <b>मिशन पूरा हुआ!</b>\n\nआपने {mission_name} के लिए ₹{reward:.2f} कमाए!\nनया बैलेंस: ₹{new_balance:.2f}",
        "withdrawal_request_sent": "✅ <b>निकासी का अनुरोध भेज दिया गया!</b>\n\n₹{amount:.2f} के आपके अनुरोध को एडमिन को भेज दिया गया है। आपको 24 घंटे के भीतर भुगतान मिल जाएगा।",
        "withdrawal_insufficient": "❌ <b>पर्याप्त बैलेंस नहीं!</b>\n\nन्यूनतम निकासी राशि ₹80.00 है",
        "withdrawal_approved_user": "✅ <b>निकासी स्वीकृत!</b>\n\n₹{amount:.2f} की आपकी निकासी स्वीकृत कर दी गई है। भुगतान 24 घंटे के भीतर प्रोसेस किया जाएगा।",
        "withdrawal_rejected_user": "❌ <b>निकासी अस्वीकृत!</b>\n\n₹{amount:.2f} की आपकी निकासी अस्वीकृत कर दी गई है। विवरण के लिए एडमिन से संपर्क करें।",
        "ref_link_message": "<b>आपकी रेफरल लिंक:</b>\n<code>{referral_link}</code>\n\n<b>वर्तमान रेफरल दर:</b> ₹{tier_rate:.2f} प्रति रेफरल\n\n<i>इस लिंक को दोस्तों के साथ साझा करें और जब वे शामिल होकर फिल्में खोजते हैं, तो पैसे कमाएं!</i>",
        "new_referral_notification": "🎉 <b>नया रेफरल!</b>\n\n{full_name} ({username}) आपकी लिंक का उपयोग करके शामिल हुए हैं!\n\n💰 आपको जॉइनिंग बोनस ₹{bonus:.2f} मिला!", # Added bonus info
        "daily_earning_update": "💰 <b>रेफरल कमाई!</b> ({count}/3)\n\nआपने अपने रेफरल {full_name} से ₹{amount:.2f} कमाए। \nनया बैलेंस: ₹{new_balance:.2f}",
        "clear_earn_usage": "❌ उपयोग: /clearearn <user_id>",
        "clear_earn_success": "✅ उपयोगकर्ता {user_id} की कमाई साफ़ कर दी गई है।",
        "clear_earn_not_found": "❌ उपयोगकर्ता {user_id} नहीं मिला।",
        "check_stats_usage": "❌ उपयोग: /checkstats <user_id>",
        "check_stats_message": "📊 <b>यूज़र आँकड़े</b>\n\nID: {user_id}\nकमाई: ₹{earnings:.2f}\nरेफरल: {referrals}",
        "check_stats_not_found": "❌ उपयोगकर्ता {user_id} नहीं मिला।",
        "stats_message": "📊 <b>बॉट आँकड़े</b>\n\nकुल उपयोगकर्ता: {total_users}\nअनुमोदित उपयोगकर्ता: {approved_users}",
        "channel_bonus_claimed": "✅ <b>चैनल जॉइन बोनस!</b>\nआपने सफलतापूर्वक {channel} जॉइन करने के लिए ₹{amount:.2f} क्लेम कर लिए हैं।\nनया बैलेंस: ₹{new_balance:.2f}",
        "channel_not_joined": "❌ <b>चैनल जॉइन नहीं किया!</b>\nबोनस क्लेम करने के लिए आपको हमारा चैनल {channel} जॉइन करना होगा।",
        "channel_already_claimed": "⏳ <b>बोनस पहले ही क्लेम किया जा चुका है!</b>\nआप पहले ही चैनल जॉइन बोनस क्लेम कर चुके हैं।",
        "top_users_title": "🏆 <b>शीर्ष 10 कमाने वाले</b> 🏆\n\n",
        "clear_junk_success": "✅ <b>जंक डेटा साफ़!</b>\n\nयूज़र्स: {deleted_users} डिलीट किए गए।\nरेफरल: {deleted_referrals} डिलीट किए गए।",
        "clear_junk_admin_only": "❌ यह कमांड केवल बॉट एडमिन के लिए है।",
        "tier_benefits_title": "👑 <b>टियर सिस्टम के लाभ</b> 👑\n\nजैसे-जैसे आप अधिक कमाते हैं, आपकी कमाई दर बढ़ती जाती है। प्रति रेफरल अधिक पैसे के लिए उच्च टियर पर पहुँचें!",
        "tier_info": "🔸 <b>{tier_name} (लेवल {tier}):</b> न्यूनतम कमाई: ₹{min_earnings:.2f}\n   - लाभ: {benefit}",
        "help_menu_title": "🆘 <b>सहायता और समर्थन</b>",
        "help_menu_text": "यदि आपके कोई प्रश्न हैं, भुगतान संबंधी समस्याएँ हैं, या एडमिन से संपर्क करने की आवश्यकता है, तो नीचे दिए गए बटन का उपयोग करें। 'पैसे कैसे कमाएं' (रेफरल उदाहरण) अनुभाग को पहले पढ़ना याद रखें!",
    }
}

# --- COMMAND LISTS FOR /setcommands ---
USER_COMMANDS = [
    BotCommand("start", "Start the bot and see main menu."),
    BotCommand("earn", "See earning panel and referral link."),
]

ADMIN_COMMANDS = [
    BotCommand("admin", "Access Admin Panel and settings."),
    BotCommand("stats", "See bot total users and stats."),
    BotCommand("broadcast", "Send message to all users."),
    BotCommand("setrate", "Set referral rate (INR)."),
    BotCommand("setwelbonus", "Set welcome bonus (INR)."),
    BotCommand("topusers", "See top 10 earners."),
    BotCommand("clearjunk", "Delete inactive users and junk data."),
]

# --- UTILITY FUNCTIONS ---

async def send_log_message(context: ContextTypes.DEFAULT_TYPE, message: str):
    """Helper function to send a message to the log channel."""
    if LOG_CHANNEL_ID:
        try:
            await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=message, parse_mode='HTML', disable_web_page_preview=True)
        except Exception as e:
            logger.error(f"Failed to send log to channel {LOG_CHANNEL_ID}: {e}")

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
    # This is now the "base" rate, Tiers will override this
    # Use Tier 1 rate as the base display rate if settings don't exist
    return settings.get("rate_inr", TIERS[1]["rate"]) if settings else TIERS[1]["rate"]

async def get_welcome_bonus():
    settings = settings_collection.find_one({"_id": "welcome_bonus"})
    return settings.get("amount_inr", 5.00) if settings else 5.00

async def get_user_tier(user_id):
    user_data = users_collection.find_one({"user_id": user_id})
    if not user_data:
        return 1
    
    earnings_usd = user_data.get("earnings", 0.0) 
    earnings_inr = earnings_usd * DOLLAR_TO_INR
    
    # Iterate through tiers in reverse to find the highest matching tier
    for tier, info in sorted(TIERS.items(), reverse=True):
        if earnings_inr >= info["min_earnings"]:
            return tier
    return 1

async def get_tier_referral_rate(tier):
    return TIERS.get(tier, TIERS[1])["rate"] 

# --- MISSING FUNCTIONS ADDED ---

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the help/how to earn message."""
    query = update.callback_query
    await query.answer()
    lang = await get_user_lang(query.from_user.id)
    
    message = MESSAGES[lang]["help_menu_title"] + "\n\n" + MESSAGES[lang]["help_menu_text"]
    
    keyboard = [
        [InlineKeyboardButton("Contact Admin", url=f"https://t.me/{YOUR_TELEGRAM_HANDLE}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def show_tier_benefits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the tier system benefits."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    message = MESSAGES[lang]["tier_benefits_title"] + "\n\n"
    
    # Sort tiers by min_earnings ascending
    sorted_tiers = sorted(TIERS.items(), key=lambda item: item[1]['min_earnings'])
    
    for tier, info in sorted_tiers:
        benefit_key = "benefits_en" if lang == "en" else "benefits_hi"
        benefit_text = info.get(benefit_key, info['benefits_en']) # Fallback to English
        
        message += MESSAGES[lang]["tier_info"].format(
            tier_name=info['name'],
            tier=tier,
            min_earnings=info['min_earnings'],
            benefit=benefit_text
        ) + "\n"
        
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


# --- CORE BOT FUNCTIONS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    full_name = user.first_name + (f" {user.last_name}" if user.last_name else "")
    username_display = f"@{user.username}" if user.username else f"<code>{user.id}</code>"
    
    referral_id_str = context.args[0].replace("ref_", "") if context.args and context.args[0].startswith("ref_") else None
    referral_id = int(referral_id_str) if referral_id_str and referral_id_str.isdigit() else None

    user_data = users_collection.find_one({"user_id": user.id})
    is_new_user = not user_data

    # Ensure all new fields are set on first insertion
    update_data = {
        "$setOnInsert": {
            "user_id": user.id, # Ensure user_id is set
            "username": user.username,
            "full_name": full_name,
            "lang": "en",
            "is_approved": True,
            "earnings": 0.0,
            "last_checkin_date": None,
            "last_spin_date": None,
            "daily_bonus_streak": 0,
            "missions_completed": {},
            "welcome_bonus_received": False,
            "joined_date": datetime.now(),
            "daily_searches": 0, 
            "last_search_date": None,
            "channel_bonus_received": False, 
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
    
    if is_new_user:
        log_msg = f"👤 <b>New User</b>\nID: <code>{user.id}</code>\nName: {full_name}\nUsername: {username_display}"
        
        # Give welcome bonus
        if not user_data.get("welcome_bonus_received", False):
            welcome_bonus = await get_welcome_bonus()
            welcome_bonus_usd = welcome_bonus / DOLLAR_TO_INR
            
            users_collection.update_one(
                {"user_id": user.id},
                {"$inc": {"earnings": welcome_bonus_usd}, "$set": {"welcome_bonus_received": True}}
            )
            
            # Send message to new user about the bonus
            try:
                await update.message.reply_html(
                    MESSAGES[lang]["welcome_bonus_received"].format(amount=welcome_bonus)
                )
            except Exception:
                 # If message fails (e.g., bot started in a group), log it
                 pass
                 
            log_msg += f"\n🎁 Welcome Bonus: ₹{welcome_bonus:.2f}"

        # Handle referral logic (FIXED: Check if already referred and not referring self)
        if referral_id and referral_id != user.id:
            existing_referral = referrals_collection.find_one({"referred_user_id": user.id})
            
            if not existing_referral:
                referrals_collection.insert_one({
                    "referrer_id": referral_id,
                    "referred_user_id": user.id,
                    "referred_username": user.username,
                    "join_date": datetime.now(),
                    "last_earning_date": None,
                    "daily_earning_count": 0
                })
                
                # Initial join bonus (e.g., half the rate of referrer's current tier)
                referrer_tier = await get_user_tier(referral_id)
                tier_rate = await get_tier_referral_rate(referrer_tier)
                referral_rate_half = tier_rate / 2.0
                referral_rate_usd = referral_rate_half / DOLLAR_TO_INR
                
                users_collection.update_one(
                    {"user_id": referral_id},
                    {"$inc": {"earnings": referral_rate_usd}} 
                )
                
                log_msg += f"\n🔗 Referred by: <code>{referral_id}</code> (Join Bonus: ₹{referral_rate_half:.2f})"

                # Notify referrer (with bonus info)
                try:
                    referrer_lang = await get_user_lang(referral_id)
                    await context.bot.send_message(
                        chat_id=referral_id,
                        text=MESSAGES[referrer_lang]["new_referral_notification"].format(
                            full_name=full_name, username=username_display, bonus=referral_rate_half
                        ),
                        parse_mode='HTML'
                    )
                except (TelegramError, TimedOut) as e:
                    logger.error(f"Could not notify referrer {referral_id}: {e}")
            else:
                log_msg += f"\n❌ Referral ignored (already referred by {existing_referral['referrer_id']})"

        await send_log_message(context, log_msg) # Send log message for new user

    # Send the main menu
    keyboard = [
        [InlineKeyboardButton("🎬 Movie Groups", callback_data="show_movie_groups_menu")],
        [InlineKeyboardButton("💰 Earning Panel", callback_data="show_earning_panel")],
        [InlineKeyboardButton(f"🎁 Join {CHANNEL_USERNAME} & Claim ₹{CHANNEL_BONUS:.2f}", callback_data="claim_channel_bonus")], 
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
    # Don't answer immediately, wait until after checks
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    user_data = users_collection.find_one({"user_id": user.id})
    
    if not user_data:
        await query.answer("User data not found.", show_alert=True)
        await query.edit_message_text("User data not found.")
        return
    
    await query.answer()

    # Get user stats
    earnings_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR
    referrals_count = referrals_collection.count_documents({"referrer_id": user.id})
    user_tier = await get_user_tier(user.id)
    tier_info = TIERS.get(user_tier, TIERS[1]) 
    
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
        [InlineKeyboardButton("💡 Referral Example", callback_data="show_refer_example")],
        [InlineKeyboardButton(MESSAGES[lang]["spin_wheel_button"], callback_data="spin_wheel")],
        [InlineKeyboardButton("💸 Request Withdrawal", callback_data="show_withdraw_details_new")], # Changed to new details view
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
    
    message = (
        f"<b>🤑 ₹{tier_rate:.2f} Per Referral! Get Rich Fast!</b>\n\n"
        f"{MESSAGES[lang]['ref_link_message'].format(referral_link=referral_link, tier_rate=tier_rate)}\n\n"
        f"<b>💡 Secret Tip:</b> Your friends must <b>search 3 movies</b> in the group to get your full daily earning! Share this now!"
    )

    share_message_text = (
        f"🤯 Join the best Movie Bot and earn money! Get movies and ₹{await get_welcome_bonus():.2f} Bonus!\n\n"
        f"Use my special link to join: {referral_link}"
    )

    keyboard = [
        [InlineKeyboardButton("🔗 Share Your Link Now!", url=f"https://t.me/share/url?url={referral_link}&text={share_message_text}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


# --- NEW/FIXED FUNCTIONS ---

async def show_refer_example(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends the referral example text and screenshot."""
    query = update.callback_query
    await query.answer()
    
    # Hindi/English text for the image caption (Lalch)
    if await get_user_lang(query.from_user.id) == 'hi':
        message = """
<b>🔥 यह है कमाई का प्रूफ!</b>\n
देखिए, दोंस्तो! मैंने अपने एक दोस्त को रेफ़र किया, और उसने मेरी लिंक से बॉट जॉइन किया। 
वह रोज़ाना मूवी सर्च करके शॉर्टलिंक पूरी करता है, और उसकी कमाई का हिस्सा <b>सीधे मेरे वॉलेट में आता है!</b>

<b>याद रखें:</b> अगर वह यूज़र हर दिन 3 बार शॉर्टलिंक पूरी करता है, तो आपको उससे <b>हर दिन</b> पैसा मिलेगा (दिन में 3 बार तक)।
जितने ज़्यादा लोगों को आप रेफ़र करेंगे, उतनी ही ज़्यादा कमाई होगी! <b>अभी शेयर करें!</b>
"""
    else:
        message = """
<b>🔥 Earning Proof is Here!</b>\n
See, friends! I referred a friend, and they joined the bot using my link.
They search movies daily and complete shortlinks, and a share of their earning <b>comes directly to my wallet!</b>

<b>Remember:</b> If that user completes 3 shortlinks every day, you will earn money from them <b>daily</b> (up to 3 times per day).
The more people you refer, the higher your earnings will be! <b>Share Now!</b>
"""
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Delete the old panel message first
    try:
        await query.message.delete()
    except Exception:
        pass # Ignore if it fails
    
    try:
        # FIX 2: Check if URL is a placeholder/not set properly
        if not EXAMPLE_SCREENSHOT_URL or "ric.jpg" in EXAMPLE_SCREENSHOT_URL or "example.png" in EXAMPLE_SCREENSHOT_URL:
            # Fallback if URL is not set - now displays only a note to the user
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=message + "\n\n(<b>Note:</b> Referral screenshot link is not yet configured by the admin.)",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=EXAMPLE_SCREENSHOT_URL,
                caption=message,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Failed to send refer example photo: {e}")
        # Fallback to text only if photo sending fails
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=message + "\n\n(Screenshot could not be loaded. Check EXAMPLE_SCREENSHOT_URL)",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

async def claim_channel_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Checks channel membership and rewards the user once."""
    query = update.callback_query
    # Don't answer immediately, wait until after checks
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    user_data = users_collection.find_one({"user_id": user.id})

    if not user_data:
        await query.answer("User data not found.", show_alert=True)
        return

    if user_data.get("channel_bonus_received"):
        await query.answer(MESSAGES[lang]["channel_already_claimed"], show_alert=True)
        await query.edit_message_text(
            MESSAGES[lang]["channel_already_claimed"],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_main_menu")]])
        )
        return
        
    await query.answer("Checking membership...")

    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user.id)
        
        # Check if the user is a member (creator, administrator, or member)
        if member.status in ['creator', 'administrator', 'member']:
            
            bonus_amount_usd = CHANNEL_BONUS / DOLLAR_TO_INR
            new_balance = user_data.get("earnings", 0.0) + bonus_amount_usd
            
            users_collection.update_one(
                {"user_id": user.id},
                {"$inc": {"earnings": bonus_amount_usd}, "$set": {"channel_bonus_received": True}}
            )
            
            await query.edit_message_text(
                MESSAGES[lang]["channel_bonus_claimed"].format(
                    amount=CHANNEL_BONUS,
                    channel=CHANNEL_USERNAME,
                    new_balance=new_balance * DOLLAR_TO_INR
                ),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_main_menu")]]) if query.message else None,
                parse_mode='HTML'
            )
            
            # Log the bonus
            log_msg = f"🎁 <b>Channel Bonus</b>\nUser: @{user.username} (<code>{user.id}</code>)\nAmount: ₹{CHANNEL_BONUS:.2f}\nNew Balance: ₹{new_balance * DOLLAR_TO_INR:.2f}"
            await send_log_message(context, log_msg)
            
        else:
            await query.edit_message_text(
                MESSAGES[lang]["channel_not_joined"].format(channel=CHANNEL_USERNAME),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"Join {CHANNEL_USERNAME}", url=f"https://t.me/{CHANNEL_USERNAME.strip('@')}")],
                    [InlineKeyboardButton("⬅️ Back", callback_data="back_to_main_menu")]
                ]),
                parse_mode='HTML'
            )

    except Exception as e:
        logger.error(f"Error checking channel membership for {user.id}: {e}")
        await query.edit_message_text("❌ An error occurred while checking channel membership. Please try again later.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_main_menu")]])
        )

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
    # Don't answer immediately, wait until after checks
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    username_display = f"@{user.username}" if user.username else f"<code>{user.id}</code>"

    user_data = users_collection.find_one({"user_id": user.id})
    if not user_data:
        await query.answer("User data not found.", show_alert=True)
        return

    today = datetime.now().date()
    last_checkin = user_data.get("last_checkin_date")
    
    # Check if claimed today
    if last_checkin and isinstance(last_checkin, datetime) and last_checkin.date() == today:
        await query.answer(MESSAGES[lang]["daily_bonus_already_claimed"], show_alert=True)
        await query.edit_message_text(
            MESSAGES[lang]["daily_bonus_already_claimed"],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
        )
        return
        
    await query.answer("Claiming bonus...")

    streak = user_data.get("daily_bonus_streak", 0)
    
    # Check if streak continues (last checkin was yesterday)
    if last_checkin and isinstance(last_checkin, datetime) and (today - last_checkin.date()).days == 1:
        streak += 1
    else:
        streak = 1 # Streak broken or new streak

    bonus_amount = DAILY_BONUS_BASE + (streak * DAILY_BONUS_STREAK_MULTIPLIER)
    bonus_amount_usd = bonus_amount / DOLLAR_TO_INR
    
    new_balance = user_data.get("earnings", 0.0) + bonus_amount_usd
    
    # Update user data (atomic operations preferred)
    update_result = users_collection.update_one(
        {"user_id": user.id},
        {
            "$inc": {"earnings": bonus_amount_usd},
            "$set": {
                "last_checkin_date": datetime.now(),
                "daily_bonus_streak": streak,
                # Set mission as complete
                f"missions_completed.claim_daily_bonus": True 
            }
        }
    )
    
    if update_result.modified_count == 0:
        logger.error(f"Failed to update daily bonus for user {user.id}")
        await query.edit_message_text("❌ An error occurred while claiming bonus. Please try again.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
        )
        return

    streak_message = f"🔥 You are on a {streak}-day streak! Keep it up for bigger bonuses!"
    if lang == "hi":
        streak_message = f"🔥 आप {streak}-दिन की स्ट्रीक पर हैं! बड़े बोनस के लिए इसे जारी रखें!"
        
    await query.edit_message_text(
        MESSAGES[lang]["daily_bonus_success"].format(
            bonus_amount=bonus_amount,
            new_balance=new_balance * DOLLAR_TO_INR,
            streak_message=streak_message
        ),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
    )
    
    # Send log
    log_msg = f"🎁 <b>Daily Bonus</b>\nUser: {username_display}\nAmount: ₹{bonus_amount:.2f}\nStreak: {streak} days\nNew Balance: ₹{new_balance * DOLLAR_TO_INR:.2f}"
    await send_log_message(context, log_msg)

async def show_missions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the user's daily mission progress and processes immediate completions."""
    query = update.callback_query
    # Don't answer immediately, logic will take a moment
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    user_data = users_collection.find_one({"user_id": user.id})
    if not user_data:
        await query.answer("User data not found.", show_alert=True)
        return
        
    await query.answer()

    today = datetime.now().date()
    
    # --- Reset Daily-Dependent Missions/Counters if new day ---
    
    # 1. Check/Reset daily searches counter
    last_search_date = user_data.get("last_search_date")
    daily_searches = user_data.get("daily_searches", 0)
    
    # FIX: Ensure searches are reset correctly
    if not last_search_date or not isinstance(last_search_date, datetime) or last_search_date.date() != today:
        daily_searches = 0 # Reset search count
        # Also reset mission completion status for "search_3_movies"
        users_collection.update_one(
            {"user_id": user.id},
            {"$set": {"daily_searches": 0, "missions_completed.search_3_movies": False}}
        )
    # 2. Check/Reset daily bonus mission status if not claimed today
    last_checkin_date = user_data.get("last_checkin_date")
    is_bonus_claimed_today = last_checkin_date and isinstance(last_checkin_date, datetime) and last_checkin_date.date() == today
    if not is_bonus_claimed_today:
        users_collection.update_one(
            {"user_id": user.id},
            {"$set": {"missions_completed.claim_daily_bonus": False}}
        )
        
    # Recalculate referrals today (since start of the day)
    referrals_today_count = referrals_collection.count_documents({
        "referrer_id": user.id,
        "join_date": {"$gte": datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)}
    })
    
    # Also reset referral mission status if it's a new day
    if user_data.get("last_search_date") and user_data["last_search_date"].date() != today:
         users_collection.update_one(
            {"user_id": user.id},
            {"$set": {"missions_completed.refer_2_friends": False}}
        )

    # Re-fetch the updated user data for display/checks
    user_data = users_collection.find_one({"user_id": user.id})
    missions_completed = user_data.get("missions_completed", {})
    daily_searches = user_data.get("daily_searches", 0)
    
    message = f"{MESSAGES[lang]['missions_title']}\n\n"
    newly_completed_message = ""
    total_reward = 0.0

    # --- Mission: Search 3 Movies (FIXED DISPLAY LOGIC) ---
    mission_key = "search_3_movies"
    mission = DAILY_MISSIONS[mission_key]
    name = mission["name"] if lang == "en" else mission["name_hi"]
    
    # NOTE: The search_3_movies mission completion logic is handled in handle_group_messages.
    # Here we only check for completion and display the progress.
    
    if missions_completed.get(mission_key):
        message += f"✅ {name} ({mission['target']}/{mission['target']}) [<b>Completed</b>]\n"
    else:
        # FIX 3: Display a special note about the movie search mission logic
        message += MESSAGES[lang]["mission_search_note"].format(
            current=min(daily_searches, mission['target']),
            target=mission['target']
        ) + "\n"
        
    # --- Mission: Refer 2 Friends ---
    mission_key = "refer_2_friends"
    mission = DAILY_MISSIONS[mission_key]
    name = mission["name"] if lang == "en" else mission["name_hi"]
    if referrals_today_count >= mission['target'] and not missions_completed.get(mission_key):
        reward_usd = mission["reward"] / DOLLAR_TO_INR
        total_reward += mission["reward"]
        users_collection.update_one(
            {"user_id": user.id},
            {
                "$inc": {"earnings": reward_usd},
                "$set": {f"missions_completed.{mission_key}": True}
            }
        )
        newly_completed_message += f"✅ <b>{name}</b>: +₹{mission['reward']:.2f}\n"
        missions_completed[mission_key] = True # Update for display below
        message += f"✅ {name} ({mission['target']}/{mission['target']}) [<b>Completed</b>]\n"
    elif missions_completed.get(mission_key):
        message += f"✅ {name} ({mission['target']}/{mission['target']}) [<b>Completed</b>]\n"
    else:
        message += f"⏳ {name} ({min(referrals_today_count, mission['target'])}/{mission['target']}) [In Progress]\n"

    # --- Mission: Claim Daily Bonus (Status Only, Claim logic is in claim_daily_bonus) ---
    mission_key = "claim_daily_bonus"
    mission = DAILY_MISSIONS[mission_key]
    name = mission["name"] if lang == "en" else mission["name_hi"]
    
    if missions_completed.get(mission_key):
        message += f"✅ {name} [<b>Completed</b>]\n"
    else:
        message += f"⏳ {name} [In Progress]\n"

    # Final Message Construction
    if total_reward > 0:
        updated_data = users_collection.find_one({"user_id": user.id})
        updated_earnings_inr = updated_data.get("earnings", 0.0) * DOLLAR_TO_INR
        message += "\n"
        message += f"🎉 <b>Mission Rewards Claimed!</b>\n"
        message += newly_completed_message
        message += f"New Balance: ₹{updated_earnings_inr:.2f}"


    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


# --- SPIN WHEEL (with new animation) ---

async def spin_wheel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    # Don't answer immediately, wait until after checks
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    username_display = f"@{user.username}" if user.username else f"<code>{user.id}</code>"

    user_data = users_collection.find_one({"user_id": user.id})
    if not user_data:
        await query.answer("User data not found.", show_alert=True)
        return

    last_spin_date = user_data.get("last_spin_date")
    today = datetime.now().date()
    
    if last_spin_date and isinstance(last_spin_date, datetime) and last_spin_date.date() == today:
        await query.answer(MESSAGES[lang]["spin_wheel_already_spun"], show_alert=True)
        await query.edit_message_text(
            MESSAGES[lang]["spin_wheel_already_spun"],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
        )
        return
    
    spin_cost_inr = 2.00
    spin_cost_usd = spin_cost_inr / DOLLAR_TO_INR
    current_balance = user_data.get("earnings", 0.0)
    
    if current_balance < spin_cost_usd:
        await query.answer(MESSAGES[lang]["spin_wheel_insufficient_balance"], show_alert=True)
        await query.edit_message_text(
            MESSAGES[lang]["spin_wheel_insufficient_balance"],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
        )
        return
        
    await query.answer("Spinning the wheel...") # Answer with a light message before the heavy action

    # 1. Deduct cost (Atomically)
    result = users_collection.update_one(
        {"user_id": user.id, "earnings": {"$gte": spin_cost_usd}},
        {"$inc": {"earnings": -spin_cost_usd}}
    )
    
    if result.modified_count == 0:
         # Should not happen if balance check passed, but safety first
        await query.edit_message_text(
            "❌ Failed to deduct cost. Try again.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
        )
        return

    # 2. Start Animation Loop (More engaging spin)
    if lang == 'hi':
        base_text = "🎡 <b>स्पिन हो रहा है...</b>"
    else:
        base_text = "🎡 <b>Spinning...</b>"
        
    animation_frames = [
        f"{base_text} ⚪️",
        f"{base_text} 🔴",
        f"{base_text} 🟡",
        f"{base_text} 🟢"
    ]
    
    # Edit the message to show the spinning animation
    for frame in animation_frames:
        try:
            await context.bot.edit_message_text(
                chat_id=query.message.chat_id,
                message_id=query.message.message_id,
                text=frame,
                parse_mode='HTML'
            )
            await asyncio.sleep(0.5) # 0.5s * 4 frames = 2s spin
        except TelegramError: 
            pass # Ignore if message not modified

    # 3. Determine Prize
    prize_inr = random.choices(SPIN_PRIZES, weights=SPIN_WEIGHTS, k=1)[0]
    prize_usd = prize_inr / DOLLAR_TO_INR
    
    # 4. Final Balance Update (Atomically add prize and set last spin date)
    users_collection.update_one(
        {"user_id": user.id},
        {
            "$inc": {"earnings": prize_usd},
            "$set": {"last_spin_date": datetime.now()}
        }
    )
    
    # Re-fetch final balance
    updated_data = users_collection.find_one({"user_id": user.id})
    final_balance_usd = updated_data.get("earnings", 0.0) 

    # 5. Send Result
    log_msg = f"🎡 <b>Spin Wheel</b>\nUser: {username_display}\nCost: ₹{spin_cost_inr:.2f}\n"
    
    if prize_inr > 0:
        message = MESSAGES[lang]["spin_wheel_win"].format(
            amount=prize_inr, new_balance=final_balance_usd * DOLLAR_TO_INR
        )
        log_msg += f"Win: ₹{prize_inr:.2f}"
    else:
        message = MESSAGES[lang]["spin_wheel_lose"].format(
            new_balance=final_balance_usd * DOLLAR_TO_INR
        )
        log_msg += "Win: ₹0.00 (Lost)"
    
    log_msg += f"\nNew Balance: ₹{final_balance_usd * DOLLAR_TO_INR:.2f}"
    await send_log_message(context, log_msg) # Send log

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
    # Don't answer immediately, wait until after checks
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    user_data = users_collection.find_one({"user_id": user.id})
    username_display = f"@{user.username}" if user.username else f"<code>{user.id}</code>"

    if not user_data:
        await query.answer("User data not found.", show_alert=True)
        return
        
    await query.answer("Processing withdrawal request...")

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

    # Check if the user has enough balance *before* creating the request
    # NOTE: The current code does NOT deduct the amount instantly, it deducts on approval. 
    # This is a valid strategy to prevent double-spending, but users might see the money still in their account.
    
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

    # Notify admin and log channel
    admin_message = (
        f"🔄 <b>New Withdrawal Request</b>\n\n"
        f"👤 User: {user.full_name} ({username_display})\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"💰 Amount: ₹{earnings_inr:.2f}"
    )
    
    await send_log_message(context, admin_message) # Send to log channel

    if ADMIN_ID:
        try:
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
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
    )
    
async def show_withdraw_details_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = await get_user_lang(query.from_user.id)
    
    message = MESSAGES[lang]["withdrawal_message_updated"]
    
    keyboard = [
        [InlineKeyboardButton("Contact Admin", url=f"https://t.me/{YOUR_TELEGRAM_HANDLE}")],
        [InlineKeyboardButton("💸 Request Withdrawal (Final Step)", callback_data="request_withdrawal")],
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


# --- MESSAGE HANDLER (REFERRAL LOGIC UPDATED) ---

async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    
    # Check if user is the bot itself (to prevent self-triggering)
    bot_info = await context.bot.get_me()
    if user.id == bot_info.id:
        return
        
    user_data = users_collection.find_one({"user_id": user.id})
    if not user_data:
        # User not started the bot yet, ignore
        return 

    # --- Mission: Search movies (Updated check) ---
    today = datetime.now().date()
    
    # Atomically update daily searches and last search date
    result = users_collection.find_one_and_update(
        {"user_id": user.id},
        [
            {
                "$set": {
                    "daily_searches": {
                        "$cond": [
                            # If last_search_date is not today, reset to 1
                            {"$ne": [{"$dateToString": {"format": "%Y-%m-%d", "date": "$last_search_date"}}, {"$dateToString": {"format": "%Y-%m-%d", "date": datetime.now()}}]},
                            1, # Reset to 1 (first search of the day)
                            # Else, increment
                            {"$add": ["$daily_searches", 1]} 
                        ]
                    },
                    "last_search_date": datetime.now(),
                    # Only reset mission if it's a new day
                    "missions_completed.search_3_movies": {
                        "$cond": [
                            {"$ne": [{"$dateToString": {"format": "%Y-%m-%d", "date": "$last_search_date"}}, {"$dateToString": {"format": "%Y-%m-%d", "date": datetime.now()}}]},
                            False, # Reset mission to False on a new day
                            "$missions_completed.search_3_movies" # Keep current status
                        ]
                    }
                }
            }
        ],
        return_document=True # Get the updated document
    )
    
    if not result:
        logger.error(f"Failed to atomically update daily searches for user {user.id}")
        return

    daily_searches = result.get("daily_searches", 0)
    missions_completed = result.get("missions_completed", {})
    lang = result.get("lang", "en")
    
    # Check and complete mission after update
    mission_key = "search_3_movies"
    if daily_searches == DAILY_MISSIONS[mission_key]["target"] and not missions_completed.get(mission_key):
        mission = DAILY_MISSIONS[mission_key]
        reward_usd = mission["reward"] / DOLLAR_TO_INR
        
        # Atomically update mission completion and earnings
        updated_result = users_collection.find_one_and_update(
            {"user_id": user.id, f"missions_completed.{mission_key}": False},
            {
                "$inc": {"earnings": reward_usd},
                "$set": {f"missions_completed.{mission_key}": True}
            },
            return_document=True
        )
        
        if updated_result:
            try:
                updated_earnings_inr = updated_result.get("earnings", 0.0) * DOLLAR_TO_INR
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
                logger.error(f"Could not notify user about search mission completion: {e}")

    # --- Updated referral earning logic (3x per day with 5 min delay) ---
    referral_data = referrals_collection.find_one({"referred_user_id": user.id})
    if referral_data:
        referrer_id = referral_data["referrer_id"]
        
        # Check for self-referral safety just in case
        if referrer_id == user.id:
            logger.warning(f"Self-referral detected and ignored for user {user.id}")
            return
            
        # We schedule a job to check the limit and pay after 5 minutes (300 seconds)
        job_name = f"pay_{user.id}" # Simplified job name to be per-referred-user
        existing_jobs = context.job_queue.get_jobs_by_name(job_name)
        
        if not existing_jobs:
            context.job_queue.run_once(
                add_payment_after_delay, 
                300, # 5 minutes delay
                chat_id=user.id, # Pass chat_id for context
                user_id=user.id, 
                data={"referrer_id": referrer_id},
                name=job_name
            )
            logger.info(f"Payment task scheduled for user {user.id} (referrer {referrer_id}).")
        else:
             logger.info(f"Payment task for {user.id} already pending. Ignoring.")


async def pay_referrer(context: ContextTypes.DEFAULT_TYPE, user_id: int, referrer_id: int, count: int):
    """Helper function to process payment and send notifications."""
    
    referrer_tier = await get_user_tier(referrer_id)
    tier_rate = await get_tier_referral_rate(referrer_tier)
    earning_rate_usd = tier_rate / DOLLAR_TO_INR
    
    # Atomically increment referrer's earnings
    users_collection.update_one(
        {"user_id": referrer_id},
        {"$inc": {"earnings": earning_rate_usd}}
    )
    
    updated_referrer_data = users_collection.find_one({"user_id": referrer_id})
    new_balance_inr = updated_referrer_data.get("earnings", 0.0) * DOLLAR_TO_INR
    
    user_data = users_collection.find_one({"user_id": user_id})
    user_full_name = user_data.get("full_name", f"User {user_id}")
    
    # Notify referrer
    referrer_lang = await get_user_lang(referrer_id)
    try:
        await context.bot.send_message(
            chat_id=referrer_id,
            text=MESSAGES[referrer_lang]["daily_earning_update"].format(
                count=count,
                amount=tier_rate,
                full_name=user_full_name, 
                new_balance=new_balance_inr
            ),
            parse_mode='HTML'
        )
    except (TelegramError, TimedOut) as e:
        logger.error(f"Could not send daily earning update to referrer {referrer_id}: {e}")
    
    # Send log
    referrer_username = f"@{updated_referrer_data.get('username')}" if updated_referrer_data.get('username') else f"<code>{referrer_id}</code>"
    user_username = f"@{user_data.get('username')}" if user_data.get('username') else f"<code>{user_id}</code>"
    log_msg = (
        f"💸 <b>Referral Earning</b> ({count}/3)\n"
        f"Referrer: {referrer_username}\n"
        f"From User: {user_username}\n"
        f"Amount: ₹{tier_rate:.2f}\n"
        f"New Balance: ₹{new_balance_inr:.2f}"
    )
    await send_log_message(context, log_msg)
    
    logger.info(f"Payment {count}/3 processed for {referrer_id} from {user_id}")

async def add_payment_after_delay(context: ContextTypes.DEFAULT_TYPE):
    """
    Called by the job queue 5 minutes after a search.
    Atomically checks and updates the daily earning count.
    """
    job = context.job
    user_id = job.user_id
    referrer_id = job.data["referrer_id"]
    
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Check if the referred user is still in the bot (has not blocked it)
    try:
        await context.bot.get_chat_member(chat_id=user_id, user_id=user_id)
    except Exception as e:
        if "bot was blocked by the user" in str(e):
             logger.warning(f"Skipping payment for {referrer_id} as referred user {user_id} blocked the bot.")
             return
        
    # --- Atomic Check and Update ---
    
    # Find one document and update it based on conditions.
    # The $cond operator inside $set is complex but ensures atomicity.
    referral_doc_updated = referrals_collection.find_one_and_update(
        {"referred_user_id": user_id, "referrer_id": referrer_id},
        [
            {
                "$set": {
                    "daily_earning_count": {
                        "$cond": [
                            # Condition 1: If last_earning_date is BEFORE today, reset count to 1
                            {"$or": [
                                {"$lt": ["$last_earning_date", today_start]},
                                {"$eq": ["$last_earning_date", None]}
                            ]},
                            1,
                            # Condition 2: If count is < 3, increment
                            {"$cond": [
                                {"$lt": ["$daily_earning_count", 3]},
                                {"$add": ["$daily_earning_count", 1]},
                                "$daily_earning_count" # Keep as is (>= 3)
                            ]}
                        ]
                    },
                    # Always update last_earning_date if we are processing this logic
                    "last_earning_date": datetime.now()
                }
            }
        ],
        return_document=True # Returns the updated document
    )

    if referral_doc_updated:
        new_count = referral_doc_updated.get("daily_earning_count", 0)
        # Check if the count actually increased (if it was 3 and stayed 3, don't pay)
        
        # Check if the last_earning_date was reset (new day) or if it was an increment (same day < 3)
        # The logic is complex to check, simply check if the new_count is <= 3 and last_earning_date is today
        if new_count > 0 and new_count <= 3:
             # Payment should occur unless count was 3 and stayed 3 (which the $cond prevents)
             # To be safe, we only pay if it's 1, 2, or 3 *and* the last earning date is today (which it is)
             await pay_referrer(context, user_id, referrer_id, count=new_count)
        else:
            logger.info(f"Daily earning limit (3/3) reached or logic error for {referrer_id} from {user_id}. No payment.")
    else:
        logger.error(f"Referral document not found for user {user_id} and referrer {referrer_id}.")


# --- ADMIN AND MISC COMMANDS ---

async def topusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the top 10 earners in the bot."""
    lang = await get_user_lang(update.effective_user.id)
    
    # Fetch top 10 users based on earnings
    top_users_cursor = users_collection.find({}) \
        .sort("earnings", -1) \
        .limit(10)
        
    top_users = list(top_users_cursor)
    
    message = MESSAGES[lang]["top_users_title"]
    
    for i, user_data in enumerate(top_users):
        rank = i + 1
        earnings_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR
        full_name = user_data.get("full_name", f"User {user_data['user_id']}")
        
        # Use emojis for top 3
        if rank == 1: emoji = "🥇"
        elif rank == 2: emoji = "🥈"
        elif rank == 3: emoji = "🥉"
        else: emoji = "▪️"
        
        message += f"{emoji} <b>{rank}. {full_name}</b>: ₹{earnings_inr:.2f}\n"

    await update.message.reply_html(message)

async def clearjunk_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deletes inactive users, referred user entries without an active user, and clears old data."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_html(MESSAGES[await get_user_lang(update.effective_user.id)]["clear_junk_admin_only"])
        return

    await update.message.reply_html("⏳ <b>Starting junk data cleanup...</b>", parse_mode='HTML')
    
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    # Find junk users: joined > 30 days ago AND never claimed daily bonus OR (never searched AND has 0 earnings).
    # We prioritize deletion of users who started the bot but did nothing and have no earnings.
    junk_users_filter = {
        "joined_date": {"$lt": thirty_days_ago},
        "$or": [
            {"last_checkin_date": None}, # Never claimed daily bonus
            {"daily_searches": 0, "earnings": 0.0} # Never searched and zero earnings
        ]
    }
    
    # 2. Get IDs of users to be deleted
    users_to_delete_cursor = users_collection.find(junk_users_filter, {"user_id": 1})
    users_to_delete_ids = [user["user_id"] for user in users_to_delete_cursor]
    
    # 3. Delete users from users_collection
    if users_to_delete_ids:
        user_delete_result = users_collection.delete_many({"user_id": {"$in": users_to_delete_ids}})
        deleted_users_count = user_delete_result.deleted_count

        # 4. Delete corresponding entries from referrals_collection
        referral_delete_result = referrals_collection.delete_many({"referred_user_id": {"$in": users_to_delete_ids}})
        deleted_referrals_count = referral_delete_result.deleted_count
    else:
        deleted_users_count = 0
        deleted_referrals_count = 0

    lang = await get_user_lang(update.effective_user.id)
    await update.message.reply_html(
        MESSAGES[lang]["clear_junk_success"].format(
            deleted_users=deleted_users_count, 
            deleted_referrals=deleted_referrals_count
        ),
        parse_mode='HTML'
    )

# --- REST OF THE FUNCTIONS (Existing logic maintained) ---

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = await get_user_lang(user.id)
    
    if user.id != ADMIN_ID:
        await update.message.reply_html(MESSAGES[lang]["broadcast_admin_only"])
        return
    
    rate = await get_referral_bonus_inr() # Note: This shows base rate, not tier rate
    bonus = await get_welcome_bonus()
    
    message = (
        f"<b>⚙️ Admin Panel</b>\n\n"
        f"Current Settings:\n"
        f"🔗 <b>Tier 1 Base Rate:</b> ₹{rate:.2f}\n"
        f"🎁 <b>Welcome Bonus:</b> ₹{bonus:.2f}\n"
    )
    
    keyboard = [
        [InlineKeyboardButton("1️⃣ Set Tier 1 Rate", callback_data="admin_set_rate")],
        [InlineKeyboardButton("2️⃣ Set Welcome Bonus", callback_data="admin_set_welbonus")],
        [InlineKeyboardButton("3️⃣ Check Withdrawals", callback_data="admin_check_withdrawals")],
        [InlineKeyboardButton("4️⃣ Set Bot Commands", callback_data="admin_set_commands")],
        [InlineKeyboardButton("5️⃣ Check Bot Stats", callback_data="admin_stats")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # If it's a message, reply. If it's a callback, it's handled in handle_admin_callbacks
    if update.callback_query:
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await update.message.reply_html(message, reply_markup=reply_markup)

async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data
    user = query.from_user
    lang = await get_user_lang(user.id)

    if user.id != ADMIN_ID:
        await query.answer(MESSAGES[lang]["broadcast_admin_only"], show_alert=True)
        return
    
    await query.answer() 
    
    if data == "admin_set_rate":
        await query.edit_message_text("✍️ <b>Enter New Tier 1 (Base) Referral Rate (in INR):</b>\n\nExample: <code>/setrate 0.40</code>", parse_mode='HTML')
    elif data == "admin_set_welbonus":
        await query.edit_message_text("✍️ <b>Enter New Welcome Bonus (in INR):</b>\n\nExample: <code>/setwelbonus 5.00</code>", parse_mode='HTML')
    elif data == "admin_stats":
        total_users = users_collection.count_documents({})
        approved_users = users_collection.count_documents({"is_approved": True})
        message = MESSAGES[lang]["stats_message"].format(total_users=total_users, approved_users=approved_users)
        keyboard = [[InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_back")]]
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    elif data == "admin_check_withdrawals":
        pending_requests = list(withdrawals_collection.find({"status": "pending"}))
        
        message = "💸 <b>Pending Withdrawal Requests</b> 💸\n\n"
        keyboard = []
        
        if not pending_requests:
            message += "✅ No pending requests found."
        else:
            for req in pending_requests:
                username_display = f"@{req.get('username')}" if req.get('username') else f"ID: <code>{req['user_id']}</code>"
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
        # Call admin_panel directly and pass the callback query to update the message
        await admin_panel(update, context)


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
    message = ""
    try:
        # Set user commands (for all users)
        await bot.set_my_commands(USER_COMMANDS)
        
        # Set all commands (for admin scope)
        # Note: Telegram Bot API doesn't support setting commands *only* for one user ID easily, 
        # so we set it globally, and enforce admin check in command handlers.
        # This part ensures admin sees the full list if they reset commands.
        await bot.set_my_commands(USER_COMMANDS + ADMIN_COMMANDS)
        
        message = (
            "✅ <b>Commands Set Successfully!</b>\n\n"
            "All commands are set for admin.\n"
            "User commands (<code>/start</code>, <code>/earn</code>) are set for all users."
        )
        
    except Exception as e:
        logger.error(f"Failed to set bot commands: {e}")
        message = f"❌ <b>Failed to set commands:</b> {e}"
    
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
        
        # Update the Tier 1 rate in the global config (for runtime use)
        if 1 in TIERS:
            TIERS[1]["rate"] = new_rate 
        
        # We also update the "base" rate in settings for consistency/display
        settings_collection.update_one(
            {"_id": "referral_rate"},
            {"$set": {"rate_inr": new_rate}},
            upsert=True
        )
        await update.message.reply_html(f"✅ Tier 1 referral rate has been updated to ₹{new_rate:.2f}.")
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
    
    # Find and update the pending withdrawal request atomically
    withdrawal = withdrawals_collection.find_one_and_update(
        {"user_id": user_id, "status": "pending"},
        {"$set": {"status": action, "approved_date": datetime.now() if action == "approve" else None}},
        return_document=True # Returns the original document before update
    )
    
    if not withdrawal:
        await query.edit_message_text(f"❌ No <b>pending</b> withdrawal request found for user <code>{user_id}</code>. It might have been processed already.", parse_mode='HTML')
        return
        
    amount_inr = withdrawal['amount_inr']
    username_display = f"@{withdrawal.get('username')}" if withdrawal.get('username') else f"<code>{user_id}</code>"

    if action == "approve":
        # Subtract the withdrawn amount (this is the crucial step as we didn't deduct on request)
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
        
        msg = f"✅ Withdrawal of ₹{amount_inr:.2f} <b>approved</b> for user {username_display}."
        await query.edit_message_text(msg, parse_mode='HTML')
        await send_log_message(context, msg)
            
    elif action == "reject":
        # No balance deduction needed for rejection
        
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

        msg = f"❌ Withdrawal of ₹{amount_inr:.2f} <b>rejected</b> for user {username_display}."
        await query.edit_message_text(msg, parse_mode='HTML')
        await send_log_message(context, msg)

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
        [InlineKeyboardButton(f"🎁 Join {CHANNEL_USERNAME} & Claim ₹{CHANNEL_BONUS:.2f}", callback_data="claim_channel_bonus")], 
        [InlineKeyboardButton(MESSAGES[lang]["language_choice"], callback_data="select_lang")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = (
        f"{MESSAGES[lang]['start_greeting']}\n\n"
        f"<b>1.</b> {MESSAGES[lang]['start_step1']}\n"
        f"<b>2.</b> {MESSAGES[lang]['start_step2']}\n"
        f"<b>3.</b> {MESSAGES[lang]['start_step3']}"
    )
    
    # Handle the case where we are coming back from a photo message (referral example)
    if query.message.photo:
        try:
            await query.message.delete()
        except Exception:
            pass # Ignore if delete fails
            
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=message, 
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

async def earn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
            await update.message.reply_html(MESSAGES[lang]["check_stats_message"].format(user_id=user_id_to_check, earnings=earnings_inr, referrals=referrals), parse_mode='HTML')
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
    await update.message.reply_html(MESSAGES[lang]["stats_message"].format(total_users=total_users, approved_users=approved_users), parse_mode='HTML')

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
    
    await update.message.reply_html(f"📢 <b>Starting broadcast to all {total_users} users...</b>", parse_mode='HTML')

    for user in users_cursor:
        try:
            await context.bot.copy_message( # Use copy_message for better handling
                chat_id=user["user_id"],
                from_chat_id=update.effective_chat.id,
                message_id=forwarded_message.message_id
            )
            count += 1
            await asyncio.sleep(0.05) 
        except Exception:
            failed_count += 1
            pass 

    await update.message.reply_html(f"✅ <b>Broadcast Finished!</b>\n\nSent to: <b>{count}</b> users.\nFailed to send (blocked/error): <b>{failed_count}</b> users.", parse_mode='HTML')


# --- MAIN FUNCTION ---

def main() -> None:
    """Start the bot."""
    if not BOT_TOKEN or not MONGO_URI:
        logger.error("BOT_TOKEN or MONGO_URI is missing. Please set environment variables.")
        return

    application = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build() # Enable concurrent updates

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
    application.add_handler(CommandHandler("topusers", topusers_command))
    application.add_handler(CommandHandler("clearjunk", clearjunk_command))
    
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
    application.add_handler(CallbackQueryHandler(show_refer_example, pattern="^show_refer_example$")) 
    application.add_handler(CallbackQueryHandler(spin_wheel_command, pattern="^spin_wheel$"))
    application.add_handler(CallbackQueryHandler(show_missions, pattern="^show_missions$")) 
    application.add_handler(CallbackQueryHandler(request_withdrawal, pattern="^request_withdrawal$"))
    application.add_handler(CallbackQueryHandler(show_tier_benefits, pattern="^show_tier_benefits$")) 
    application.add_handler(CallbackQueryHandler(claim_channel_bonus, pattern="^claim_channel_bonus$")) 
    
    # Admin Panel Callbacks
    application.add_handler(CallbackQueryHandler(handle_admin_callbacks, pattern="^admin_")) 
    application.add_handler(CallbackQueryHandler(handle_withdrawal_approval, pattern="^(approve|reject)_withdraw_\\d+$"))
    
    # Group Message Handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_group_messages))

    # Get the job queue object from the application
    job_queue = application.job_queue
    # Pass the job_queue to the utility function if needed, but here it's in context.

    # Start the Bot
    if WEB_SERVER_URL and BOT_TOKEN:
        # Render/Heroku/etc. webhook mode
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN, # Use BOT_TOKEN as path to hide it from logs
            webhook_url=f"{WEB_SERVER_URL}/{BOT_TOKEN}",
            allowed_updates=Update.ALL_TYPES
        )
        logger.info(f"Bot started in Webhook Mode on port {PORT}.")
    else:
        # Local or simple polling mode
        logger.info("WEB_SERVER_URL not found, starting in Polling Mode.")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Bot started in Polling Mode.")

if __name__ == "__main__":
    main()
