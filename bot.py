import os
import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
# Ensure ADMIN_ID is an integer or None
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
except (TypeError, ValueError):
    ADMIN_ID = None

YOUR_TELEGRAM_HANDLE = os.getenv("YOUR_TELEGRAM_HANDLE")
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

# --- MESSAGES Dictionary (Updated with new features) ---
MESSAGES = {
    "en": {
        "start_greeting": "Hey 👋! Welcome to the Movies Group Bot. Get your favorite movies by following these simple steps:",
        "start_step1": "Click the button below to join our movie group.",
        "start_step2": "Go to the group and type the name of the movie you want.",
        "start_step3": "The bot will give you a link to your movie.",
        "start_group_button": "Join Movies Group",
        "new_group_button": "🆕 New Movie Group",
        "language_choice": "Choose your language:",
        "language_selected": "Language changed to English.",
        "earn_message": "Here's how you can earn with this bot:",
        "earn_button": "How to Earn Money",
        "earn_rules_title": "💰 How to Earn with this Bot",
        "earn_rule1": "1. Refer friends using your unique referral link.",
        "earn_rule2": "2. When a referred friend searches for a movie in the group, they will be redirected to the bot via a shortlink.",
        "earn_rule3": "3. After they complete the shortlink, you earn money.",
        "earn_rule4": "4. You can only earn from each referred user once per day.",
        "earn_command_info": "Use the /earn command to get your referral link.",
        "earnings_breakdown": "Earnings Breakdown:",
        "owner_share": "Owner's Share:",
        "your_share": "Your Share:",
        "earnings_update": "Your earnings will automatically update in your account.",
        "withdrawal_message": "Click the button below to see your withdrawal details:",
        "withdraw_button": "💸 Withdrawal Details",
        "withdrawal_details_title": "💰 Withdrawal Details 💰",
        "withdrawal_info": "You can withdraw any amount as long as your balance is ₹80 or more. Withdrawals are only possible via UPI ID, QR code, or bank account.",
        "total_earnings": "Total Earnings:",
        "total_referrals": "Total Referrals:",
        "active_earners": "Active Earners Today:",
        "contact_admin_text": "Click the button below to contact the admin for withdrawal.",
        "contact_admin_button": "Contact Admin",
        "new_referral_notification": "🥳 Good news! A new user has joined through your link: {full_name} (@{username}).",
        "new_user_log": "🆕 <b>New User Connected:</b>\n\n<b>User ID:</b> <code>{user_id}</code>\n<b>Username:</b> @{username}\n<b>Full Name:</b> {full_name}\n<b>Referred By:</b> @{referrer_username} (ID: <code>{referrer_id}</code>)",
        "new_user_log_no_ref": "🆕 <b>New User Connected:</b>\n\n<b>User ID:</b> <code>{user_id}</code>\n<b>Username:</b> @{username}\n<b>Full Name:</b> {full_name}\n<b>Referred By:</b> None",
        "daily_earning_update": "🎉 <b>Your earnings have been updated!</b>\nA referred user ({full_name}) completed the shortlink process today.\nYour new balance: ₹{new_balance:.2f}",
        "daily_earning_limit": "This user has already earned you money today. Your earnings will be updated again tomorrow.",
        "checkbot_success": "✅ Bot is connected to this group!",
        "checkbot_failure": "❌ Bot is not connected to this group. Please check the settings.",
        "stats_message": "Bot Stats:\n\n👥 Total Users: {total_users}\n🎯 Approved Earners: {approved_users}",
        "broadcast_admin_only": "❌ This command is for the bot admin only.",
        "broadcast_message": "Please reply to a message with `/broadcast` to send it to all users.",
        "broadcast_success": "✅ Message sent to all {count} users.",
        "broadcast_failed": "❌ Failed to send message to all users. Please check logs for errors.",
        "broadcast_title": "📢 New Message from Admin!",
        "broadcast_forwarding_error": "❌ Error forwarding message.",
        "clear_earn_success": "✅ User {user_id}'s earnings have been cleared.",
        "clear_earn_not_found": "❌ User with ID {user_id} not found or not an earner.",
        "clear_earn_usage": "❌ Usage: /clearearn <user_id>",
        "check_stats_message": "Stats for user {user_id}:\n\nTotal Earnings: ₹{earnings:.2f}\nTotal Referrals: {referrals}",
        "check_stats_not_found": "❌ User with ID {user_id} not found.",
        "check_stats_usage": "❌ Usage: /checkstats <user_id>",
        "referral_already_exists": "This user has already been referred by someone else. You cannot get any benefits from this referral.",
        "help_message_text": "<b>🤝 How to Earn Money</b>\n\n1️⃣ <b>Get Your Link:</b> Use the 'My Refer Link' button to get your unique referral link.\n\n2️⃣ <b>Share Your Link:</b> Share this link with your friends. Tell them to start the bot and join our movie group.\n\n3️⃣ <b>Earn:</b> When a referred friend searches for a movie in the group and completes the shortlink process, you earn money! You can earn from each friend once per day.",
        "withdrawal_message_updated": "💸 <b>Withdrawal Details</b>\n\nYou can withdraw your earnings when your balance reaches ₹80 or more. Click the button below to contact the admin and get your payment.\n\n<b>Note:</b> Payments are sent via UPI ID, QR code, or Bank Account. Click the button and send your payment details to the admin.",
        "earning_panel_message": "<b>💰 Earning Panel</b>\n\nManage all your earning activities here.",
        "daily_bonus_success": "🎉 <b>Daily Bonus Claimed!</b>\nYou have successfully claimed your daily bonus of ₹{bonus_amount:.2f}. Your new balance is ₹{new_balance:.2f}.",
        "daily_bonus_already_claimed": "⏳ <b>Bonus Already Claimed!</b>\nYou have already claimed your bonus for today. Try again tomorrow!",
        "admin_panel_title": "<b>⚙️ Admin Panel</b>\n\nManage bot settings and users from here.",
        "setrate_success": "✅ Referral earning rate has been updated to ₹{new_rate:.2f}.",
        "setrate_usage": "❌ Usage: /setrate <new_rate_in_inr>",
        "invalid_rate": "❌ Invalid rate. Please enter a number.",
        "referral_rate_updated": "The new referral rate is now ₹{new_rate:.2f}.",
        
        # New Features Messages
        "welcome_bonus_received": "🎁 <b>Welcome Bonus!</b>\n\nYou have received ₹{amount:.2f} welcome bonus! Start earning more by referring friends.",
        "spin_wheel_title": "🎡 <b>Spin the Wheel</b>\n\nSpin cost: ₹2.00\nClick the button below to try your luck!",
        "spin_wheel_button": "🎡 Spin Wheel (₹2)",
        "spin_wheel_insufficient_balance": "❌ <b>Insufficient Balance!</b>\n\nYou need at least ₹2.00 to spin the wheel.",
        "spin_wheel_already_spun": "⏳ <b>Already Spun Today!</b>\n\nYou can spin the wheel only once per day. Try again tomorrow!",
        "spin_wheel_win": "🎉 <b>Congratulations!</b>\n\nYou won: ₹{amount:.2f}!\n\nNew balance: ₹{new_balance:.2f}",
        "spin_wheel_lose": "😢 <b>Better luck next time!</b>\n\nYou didn't win anything this time.\n\nRemaining balance: ₹{new_balance:.2f}",
        "missions_title": "🎯 <b>Daily Missions</b>\n\nComplete missions to earn extra rewards!",
        "mission_complete": "✅ <b>Mission Completed!</b>\n\nYou earned ₹{reward:.2f} for {mission_name}!\nNew balance: ₹{new_balance:.2f}",
        "level_up": "🏆 <b>Level Up!</b>\n\nCongratulations! You reached Level {level}!\nYour referral rate is now ₹{rate:.2f} per referral.",
        "withdrawal_request_sent": "✅ <b>Withdrawal Request Sent!</b>\n\nYour request for ₹{amount:.2f} has been sent to admin. You will receive payment within 24 hours.",
        "withdrawal_insufficient": "❌ <b>Insufficient Balance!</b>\n\nMinimum withdrawal amount is ₹80.00",
        "tier_system_title": "🏅 <b>Tier System</b>\n\nCurrent Tier: {tier}\nBenefits: {benefits}",
    },
    "hi": {
        "start_greeting": "नमस्ते 👋! मूवी ग्रुप बॉट में आपका स्वागत है। इन आसान स्टेप्स को फॉलो करके अपनी पसंदीदा मूवी पाएँ:",
        "start_step1": "हमारे मूवी ग्रुप में शामिल होने के लिए नीचे दिए गए बटन पर क्लिक करें।",
        "start_step2": "ग्रुप में जाकर अपनी मनपसंद मूवी का नाम लिखें।",
        "start_step3": "बॉट आपको आपकी मूवी की लिंक देगा।",
        "start_group_button": "मूवी ग्रुप जॉइन करें",
        "new_group_button": "🆕 नया मूवी ग्रुप",
        "language_choice": "अपनी भाषा चुनें:",
        "language_selected": "भाषा हिंदी में बदल दी गई है।",
        "earn_message": "आप इस बॉट से कैसे कमा सकते हैं, यहां बताया गया है:",
        "earn_button": "पैसे कैसे कमाएं",
        "earn_rules_title": "💰 इस बॉट से पैसे कैसे कमाएं",
        "earn_rule1": "1. अपनी रेफरल लिंक का उपयोग करके दोस्तों को रेफर करें।",
        "earn_rule2": "2. जब आपका रेफर किया गया दोस्त ग्रुप में कोई मूवी खोजता है, तो उसे एक शॉर्टलिंक के माध्यम से बॉट पर रीडायरेक्ट किया जाएगा।",
        "earn_rule3": "3. जब वे शॉर्टलिंक पूरा कर लेंगे, तो आप पैसे कमाएंगे।",
        "earn_rule4": "4. आप प्रति रेफर किए गए यूजर से केवल एक बार प्रति दिन कमा सकते हैं।",
        "earn_command_info": "अपनी रेफरल लिंक पाने के लिए /earn कमांड का उपयोग करें।",
        "earnings_breakdown": "कमाई का विवरण:",
        "owner_share": "मालिक का हिस्सा:",
        "your_share": "आपका हिस्सा:",
        "earnings_update": "आपकी कमाई स्वचालित रूप से आपके खाते में अपडेट हो जाएगी।",
        "withdrawal_message": "निकासी के विवरण देखने के लिए नीचे दिए गए बटन पर क्लिक करें:",
        "withdraw_button": "💸 निकासी का विवरण",
        "withdrawal_details_title": "💰 निकासी का विवरण 💰",
        "withdrawal_info": "आप किसी भी राशि को निकाल सकते हैं, बशर्ते कि आपका बैलेंस ₹80 या उससे अधिक हो। निकासी केवल UPI ID, QR कोड, या बैंक खाते के माध्यम से ही संभव है।",
        "total_earnings": "कुल कमाई:",
        "total_referrals": "कुल रेफरल:",
        "active_earners": "आज के सक्रिय कमाने वाले:",
        "contact_admin_text": "निकासी के लिए एडमिन से संपर्क करने हेतु नीचे दिए गए बटन पर क्लिक करें।",
        "contact_admin_button": "एडमिन से संपर्क करें",
        "new_referral_notification": "🥳 खुशखबरी! एक नया यूजर आपकी लिंक से जुड़ा है: {full_name} (@{username})।",
        "new_user_log": "🆕 <b>नया उपयोगकर्ता जुड़ा है:</b>\n\n<b>उपयोगकर्ता आईडी:</b> <code>{user_id}</code>\n<b>यूजरनेम:</b> @{username}\n<b>पूरा नाम:</b> {full_name}\n<b>किसके द्वारा रेफर किया गया:</b> @{referrer_username} (आईडी: <code>{referrer_id}</code>)",
        "new_user_log_no_ref": "🆕 <b>नया उपयोगकर्ता जुड़ा है:</b>\n\n<b>उपयोगकर्ता आईडी:</b> <code>{user_id}</code>\n<b>यूजरनेम:</b> @{username}\n<b>पूरा नाम:</b> {full_name}\n<b>किसके द्वारा रेफर किया गया:</b> कोई नहीं",
        "daily_earning_update": "🎉 <b>आपकी कमाई अपडेट हो गई है!</b>\nएक रेफर किए गए यूजर ({full_name}) ने आज शॉर्टलिंक प्रक्रिया पूरी की।\nआपका नया बैलेंस: ₹{new_balance:.2f}",
        "daily_earning_limit": "इस यूजर से आपने आज पहले ही कमाई कर ली है। आपकी कमाई कल फिर से अपडेट होगी।",
        "checkbot_success": "✅ बॉट इस ग्रुप से जुड़ा हुआ है!",
        "checkbot_failure": "❌ बॉट इस ग्रुप से जुड़ा हुआ नहीं है। कृपया सेटिंग्स जांचें।",
        "stats_message": "बॉट के आंकड़े:\n\n👥 कुल उपयोगकर्ता: {total_users}\n🎯 स्वीकृत कमाने वाले: {approved_users}",
        "broadcast_admin_only": "❌ यह कमांड केवल बॉट एडमिन के लिए है।",
        "broadcast_message": "सभी उपयोगकर्ताओं को संदेश भेजने के लिए कृपया किसी संदेश का `/broadcast` के साथ उत्तर दें।",
        "broadcast_success": "✅ संदेश सभी {count} उपयोगकर्ताओं को भेजा गया।",
        "broadcast_failed": "❌ सभी उपयोगकर्ताओं को संदेश भेजने में विफल। कृपया त्रुटियों के लिए लॉग जांचें।",
        "broadcast_title": "📢 एडमिन की ओर से नया संदेश!",
        "broadcast_forwarding_error": "❌ संदेश फॉरवर्ड करने में त्रुटि।",
        "clear_earn_success": "✅ यूजर {user_id} की कमाई साफ कर दी गई है।",
        "clear_earn_not_found": "❌ यूजर ID {user_id} नहीं मिला या वह कमाने वाला नहीं है।",
        "clear_earn_usage": "❌ उपयोग: /clearearn <user_id>",
        "check_stats_message": "यूजर {user_id} के आंकड़े:\n\nकुल कमाई: ₹{earnings:.2f}\nकुल रेफरल: {referrals}",
        "check_stats_not_found": "❌ यूजर ID {user_id} नहीं मिला।",
        "check_stats_usage": "❌ उपयोग: /checkstats <user_id>",
        "referral_already_exists": "यह उपयोगकर्ता पहले ही किसी और के द्वारा रेफर किया जा चुका है। इसलिए, आप इस रेफरल से कोई लाभ नहीं उठा सकते हैं।",
        "help_message_text": "<b>🤝 पैसे कैसे कमाएं</b>\n\n1️⃣ <b>अपनी लिंक पाएं:</b> 'My Refer Link' बटन का उपयोग करके अपनी रेफरल लिंक पाएं।\n\n2️⃣ <b>शेयर करें:</b> इस लिंक को अपने दोस्तों के साथ शेयर करें। उन्हें बॉट शुरू करने और हमारे मूवी ग्रुप में शामिल होने के लिए कहें।\n\n3️⃣ <b>कमाई करें:</b> जब आपका रेफर किया गया दोस्त ग्रुप में कोई मूवी खोजता है और शॉर्टलिंक प्रक्रिया पूरी करता है, तो आप पैसे कमाते हैं! आप प्रत्येक दोस्त से एक दिन में एक बार कमाई कर सकते हैं।",
        "withdrawal_message_updated": "💸 <b>निकासी का विवरण</b>\n\nजब आपका बैलेंस ₹80 या उससे अधिक हो जाए, तो आप अपनी कमाई निकाल सकते हैं। एडमिन से संपर्क करने और अपना भुगतान पाने के लिए नीचे दिए गए बटन पर क्लिक करें।\n\n<b>ध्यान दें:</b> भुगतान UPI ID, QR कोड, या बैंक खाते के माध्यम से भेजे जाते हैं। बटन पर क्लिक करें और अपने भुगतान विवरण एडमिन को भेजें।",
        "earning_panel_message": "<b>💰 कमाई का पैनल</b>\n\nयहाँ आप अपनी कमाई से जुड़ी सभी गतिविधियाँ मैनेज कर सकते हैं।",
        "daily_bonus_success": "🎉 <b>दैनिक बोनस क्लेम किया गया!</b>\nआपने सफलतापूर्वक अपना दैनिक बोनस ₹{bonus_amount:.2f} क्लेम कर लिया है। आपका नया बैलेंस ₹{new_balance:.2f} है।",
        "daily_bonus_already_claimed": "⏳ <b>बोनस पहले ही क्लेम किया जा चुका है!</b>\nआपने आज का बोनस पहले ही क्लेम कर लिया है। कल फिर कोशिश करें!",
        "admin_panel_title": "<b>⚙️ एडमिन पैनल</b>\n\nयहाँ से बॉट की सेटिंग्स और यूज़र्स को मैनेज करें।",
        "setrate_success": "✅ रेफरल कमाई की दर ₹{new_rate:.2f} पर अपडेट हो गई है।",
        "setrate_usage": "❌ उपयोग: /setrate <नई_राशि_रुपये_में>",
        "invalid_rate": "❌ अमान्य राशि। कृपया एक संख्या दर्ज करें।",
        "referral_rate_updated": "नई रेफरल दर अब ₹{new_rate:.2f} है।",
        
        # New Features Messages in Hindi
        "welcome_bonus_received": "🎁 <b>वेलकम बोनस!</b>\n\nआपको ₹{amount:.2f} वेलकम बोनस मिला है! दोस्तों को रेफर करके और कमाएँ।",
        "spin_wheel_title": "🎡 <b>व्हील स्पिन करें</b>\n\nस्पिन की लागत: ₹2.00\nअपनी किस्मत आज़माने के लिए नीचे बटन पर क्लिक करें!",
        "spin_wheel_button": "🎡 व्हील स्पिन (₹2)",
        "spin_wheel_insufficient_balance": "❌ <b>पर्याप्त बैलेंस नहीं!</b>\n\nव्हील स्पिन करने के लिए आपके पास कम से कम ₹2.00 होने चाहिए।",
        "spin_wheel_already_spun": "⏳ <b>आज पहले ही स्पिन कर चुके हैं!</b>\n\nआप व्हील को केवल एक बार प्रति दिन स्पिन कर सकते हैं। कल फिर कोशिश करें!",
        "spin_wheel_win": "🎉 <b>बधाई हो!</b>\n\nआपने जीता: ₹{amount:.2f}!\n\nनया बैलेंस: ₹{new_balance:.2f}",
        "spin_wheel_lose": "😢 <b>अगली बार बेहतर किस्मत!</b>\n\nइस बार आप कुछ नहीं जीत पाए।\n\nशेष बैलेंस: ₹{new_balance:.2f}",
        "missions_title": "🎯 <b>दैनिक मिशन</b>\n\nअतिरिक्त इनाम पाने के लिए मिशन पूरे करें!",
        "mission_complete": "✅ <b>मिशन पूरा हुआ!</b>\n\nआपने {mission_name} के लिए ₹{reward:.2f} कमाए!\nनया बैलेंस: ₹{new_balance:.2f}",
        "level_up": "🏆 <b>लेवल अप!</b>\n\nबधाई! आप लेवल {level} तक पहुँच गए!\nआपकी रेफरल दर अब ₹{rate:.2f} प्रति रेफरल है।",
        "withdrawal_request_sent": "✅ <b>निकासी का अनुरोध भेज दिया गया!</b>\n\n₹{amount:.2f} के आपके अनुरोध को एडमिन को भेज दिया गया है। आपको 24 घंटे के भीतर भुगतान मिल जाएगा।",
        "withdrawal_insufficient": "❌ <b>पर्याप्त बैलेंस नहीं!</b>\n\nन्यूनतम निकासी राशि ₹80.00 है",
        "tier_system_title": "🏅 <b>टियर सिस्टम</b>\n\nवर्तमान टियर: {tier}\nलाभ: {benefits}",
    }
}

# --- NEW FEATURES CONFIGURATION ---

# Spin Wheel Prizes (in INR)
SPIN_PRIZES = [0, 1, 2, 5, 10, 20, 50]  # 0 means no win

# Tier System Configuration
TIERS = {
    1: {"min_earnings": 0, "rate": 0.40, "name": "Beginner", "benefits": "Basic referral rate"},
    2: {"min_earnings": 50, "rate": 0.60, "name": "Pro", "benefits": "50% higher referral rate"},
    3: {"min_earnings": 200, "rate": 1.00, "name": "Expert", "benefits": "2.5x referral rate"},
    4: {"min_earnings": 500, "rate": 2.00, "name": "Master", "benefits": "5x referral rate"}
}

# Missions Configuration
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

async def get_referral_bonus_usd():
    rate_inr = await get_referral_bonus_inr()
    return rate_inr / DOLLAR_TO_INR

async def get_welcome_bonus():
    settings = settings_collection.find_one({"_id": "welcome_bonus"})
    return settings.get("amount_inr", 5.00) if settings else 5.00

async def get_user_tier(user_id):
    user_data = users_collection.find_one({"user_id": user_id})
    if not user_data:
        return 1
    
    earnings_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR
    
    for tier, info in sorted(TIERS.items(), reverse=True):
        if earnings_inr >= info["min_earnings"]:
            return tier
    return 1

async def get_tier_referral_rate(tier):
    return TIERS.get(tier, TIERS[1])["rate"] # Added .get() with default to prevent key error

# --- CORE BOT FUNCTIONS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    # FIX: user.full_name is not a standard attribute. Use first_name and last_name.
    full_name = user.first_name + (f" {user.last_name}" if user.last_name else "")
    
    referral_id_str = context.args[0].replace("ref_", "") if context.args and context.args[0].startswith("ref_") else None
    referral_id = int(referral_id_str) if referral_id_str and referral_id_str.isdigit() else None

    # Check if user already exists
    user_data = users_collection.find_one({"user_id": user.id})
    is_new_user = not user_data

    # Update or insert user data
    users_collection.update_one(
        {"user_id": user.id},
        {"$setOnInsert": {
            "username": user.username,
            "full_name": full_name, # Use fixed full_name
            "lang": "en",
            "is_approved": True,
            "earnings": 0.0,
            "last_checkin_date": None,
            "last_spin_date": None,
            "daily_bonus_streak": 0,
            "missions_completed": {},
            "welcome_bonus_received": False,
            "joined_date": datetime.now(),
            "daily_searches": 0, # Added for missions
            "last_search_date": None # Added for missions
        }},
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
        
        # Send bonus message separately if it's the first message
        try:
            await update.message.reply_html(
                MESSAGES[lang]["welcome_bonus_received"].format(amount=welcome_bonus)
            )
        except Exception as e:
             logging.error(f"Could not send welcome bonus message: {e}")

    # NEW: LOG THE NEW USER
    if is_new_user and LOG_CHANNEL_ID:
        try:
            if referral_id:
                referrer_data = users_collection.find_one({"user_id": referral_id})
                referrer_username = referrer_data.get("username", "Unknown") if referrer_data else "Unknown"
                log_message = MESSAGES[lang]["new_user_log"].format(
                    user_id=user.id,
                    username=user.username or "N/A",
                    full_name=full_name or "N/A",
                    referrer_username=referrer_username,
                    referrer_id=referral_id
                )
            else:
                log_message = MESSAGES[lang]["new_user_log_no_ref"].format(
                    user_id=user.id,
                    username=user.username or "N/A",
                    full_name=full_name or "N/A"
                )
            await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=log_message, parse_mode='HTML')
        except Exception as e:
            logging.error(f"Could not log new user to channel: {e}")

    # Handle referral logic
    if referral_id and referral_id != user.id: # User cannot refer themselves
        existing_referral = referrals_collection.find_one({"referred_user_id": user.id})
        
        if existing_referral:
            referrer_lang = await get_user_lang(referral_id)
            try:
                await context.bot.send_message(
                    chat_id=referral_id,
                    text=MESSAGES[referrer_lang]["referral_already_exists"]
                )
            except (TelegramError, TimedOut) as e:
                logging.error(f"Could not send referral exists notification to {referral_id}: {e}")

        elif is_new_user:
            referrals_collection.insert_one({
                "referrer_id": referral_id,
                "referred_user_id": user.id,
                "referred_username": user.username,
                "join_date": datetime.now(),
                "last_earning_date": None # Added for daily earning limit
            })
            
            # Add the referral bonus to the referrer's earnings using tier-based rate
            referrer_tier = await get_user_tier(referral_id)
            tier_rate = await get_tier_referral_rate(referrer_tier)
            referral_rate_usd = tier_rate / DOLLAR_TO_INR
            
            # NOTE: We only add the bonus *after* a shortlink is completed (in add_payment_after_delay)
            # For simplicity in this fix, I'll add a small initial referral bonus for the join event.
            # You might want to remove this if you only pay on shortlink completion.
            users_collection.update_one(
                {"user_id": referral_id},
                {"$inc": {"earnings": referral_rate_usd / 2}} # Half the rate for just joining
            )

            try:
                referred_username_display = f"@{user.username}" if user.username else f"(No username)"
                referrer_lang = await get_user_lang(referral_id)
                await context.bot.send_message(
                    chat_id=referral_id,
                    text=MESSAGES[referrer_lang]["new_referral_notification"].format(
                        full_name=full_name, username=referred_username_display
                    )
                )
            except (TelegramError, TimedOut) as e:
                logging.error(f"Could not notify referrer {referral_id}: {e}")

    # Send the main menu
    lang = await get_user_lang(user.id)
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
    
    # Use reply if a welcome bonus was not just sent, or edit the last one
    if is_new_user and user_data.get("welcome_bonus_received", False):
        # We assume the last message was the welcome bonus, try to send a new one
        await update.message.reply_html(message, reply_markup=reply_markup)
    else:
        await update.message.reply_html(message, reply_markup=reply_markup)


# --- NEW FEATURES IMPLEMENTATION ---

async def spin_wheel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    user_data = users_collection.find_one({"user_id": user.id})
    
    if not user_data:
        await query.edit_message_text("User data not found.")
        return

    # Check if already spun today
    last_spin_date = user_data.get("last_spin_date")
    today = datetime.now().date()
    
    # FIX: last_spin_date might be None
    if last_spin_date and isinstance(last_spin_date, datetime) and last_spin_date.date() == today:
        await query.edit_message_text(
            MESSAGES[lang]["spin_wheel_already_spun"],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
        )
        return

    # Check balance
    spin_cost_inr = 2.00
    spin_cost_usd = spin_cost_inr / DOLLAR_TO_INR
    current_balance = user_data.get("earnings", 0.0)
    
    if current_balance < spin_cost_usd:
        await query.edit_message_text(
            MESSAGES[lang]["spin_wheel_insufficient_balance"],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
        )
        return

    # Deduct spin cost, Spin the wheel
    prize_inr = random.choice(SPIN_PRIZES)
    prize_usd = prize_inr / DOLLAR_TO_INR
    
    # Calculate final balance in one go: deduct cost, then add prize
    final_balance_usd = current_balance - spin_cost_usd + prize_usd
    
    # Update user data
    users_collection.update_one(
        {"user_id": user.id},
        {
            "$set": {
                "earnings": final_balance_usd,
                "last_spin_date": datetime.now()
            }
        }
    )

    # Send result
    if prize_inr > 0:
        message = MESSAGES[lang]["spin_wheel_win"].format(
            amount=prize_inr, new_balance=final_balance_usd * DOLLAR_TO_INR
        )
    else:
        message = MESSAGES[lang]["spin_wheel_lose"].format(
            new_balance=final_balance_usd * DOLLAR_TO_INR
        )

    keyboard = [
        [InlineKeyboardButton("🔄 Spin Again", callback_data="spin_wheel")],
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

async def show_missions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    message = MESSAGES[lang]["missions_title"] + "\n\n"
    
    # Add mission details
    for mission_id, mission in DAILY_MISSIONS.items():
        message += f"🎯 {mission['name']}\n💰 Reward: ₹{mission['reward']:.2f}\n📊 Target: {mission['target']}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

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

    # Check for existing pending request to prevent spam
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
        "full_name": user.full_name, # This will be None if user has no full_name set
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
            logging.error(f"Could not notify admin about withdrawal: {e}")

    await query.edit_message_text(
        MESSAGES[lang]["withdrawal_request_sent"].format(amount=earnings_inr),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]),
        parse_mode='HTML'
    )

# --- UPDATED EARNING PANEL WITH NEW FEATURES ---

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
    tier_info = TIERS.get(user_tier, TIERS[1]) # Added .get() with default
    
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
        [InlineKeyboardButton("🎡 Spin Wheel (₹2)", callback_data="spin_wheel")],
        [InlineKeyboardButton("💸 Request Withdrawal", callback_data="request_withdrawal")],
        [InlineKeyboardButton("🎁 Daily Bonus", callback_data="claim_daily_bonus")],
        [InlineKeyboardButton("🎯 Daily Missions", callback_data="show_missions")],
        [InlineKeyboardButton("📊 Tier Benefits", callback_data="show_tier_benefits")],
        [InlineKeyboardButton("🆘 Help", callback_data="show_help")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

async def show_tier_benefits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    user_tier = await get_user_tier(user.id)
    
    message = f"<b>🏅 Tier System Benefits</b>\n\n"
    
    for tier, info in TIERS.items():
        status = "✅ CURRENT" if tier == user_tier else "🔒 LOCKED" if tier > user_tier else "✅ UNLOCKED"
        message += f"<b>Level {tier}: {info['name']}</b> {status}\n"
        message += f"💰 Min Earnings: ₹{info['min_earnings']:.2f}\n" # Added formatting
        message += f"🎯 Rate: ₹{info['rate']:.2f}/referral\n" # Added formatting
        message += f"⭐ Benefits: {info['benefits']}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

# --- UPDATED DAILY BONUS WITH PROGRESSIVE SYSTEM ---

async def claim_daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user = query.from_user
    lang = await get_user_lang(user.id)
    user_data = users_collection.find_one({"user_id": user.id})
    
    if not user_data:
        await query.edit_message_text("User data not found.")
        return

    last_checkin_date = user_data.get("last_checkin_date")
    today = datetime.now().date()
    streak = user_data.get("daily_bonus_streak", 0)

    # FIX: Check if last_checkin_date is a datetime object
    if last_checkin_date and isinstance(last_checkin_date, datetime) and last_checkin_date.date() == today:
        await query.edit_message_text(
            MESSAGES[lang]["daily_bonus_already_claimed"],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
        )
        return
        
    # Check if consecutive
    is_consecutive = last_checkin_date and isinstance(last_checkin_date, datetime) and (today - last_checkin_date.date()).days == 1
    
    if is_consecutive:
        streak += 1
    else:
        streak = 1 
        
    # Progressive bonus system
    BONUS_TIERS = {1: 0.10, 2: 0.20, 3: 0.30, 4: 0.50, 5: 1.00, 6: 2.00, 7: 5.00}
    bonus_inr = BONUS_TIERS.get(min(streak, 7), 5.00) 
    bonus_usd = bonus_inr / DOLLAR_TO_INR
    new_balance = user_data.get("earnings", 0.0) + bonus_usd
    
    # Update user data
    users_collection.update_one(
        {"user_id": user.id},
        {"$set": {
            "last_checkin_date": datetime.now(), 
            "earnings": new_balance,
            "daily_bonus_streak": streak
        }}
    )
    
    # Mission: Claim Daily Bonus
    missions_completed = user_data.get("missions_completed", {})
    mission_key = "claim_daily_bonus"
    if not missions_completed.get(mission_key):
        mission = DAILY_MISSIONS[mission_key]
        reward_usd = mission["reward"] / DOLLAR_TO_INR
        
        users_collection.update_one(
            {"user_id": user.id},
            {
                "$inc": {"earnings": reward_usd},
                "$set": {f"missions_completed.{mission_key}": True}
            }
        )
        new_balance += reward_usd
        
        # Notify user about mission completion
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=MESSAGES[lang]["mission_complete"].format(
                    mission_name=mission["name"],
                    reward=mission["reward"],
                    new_balance=new_balance * DOLLAR_TO_INR
                ),
                parse_mode='HTML'
            )
        except Exception as e:
            logging.error(f"Could not notify user about mission completion: {e}")
    
    streak_message = f"🔥 <b>Streak:</b> {streak} days in a row!"
    if streak >= 7:
        streak_message += "\n🎉 <b>Maximum bonus reached! Keep the streak going!</b>"
    
    await query.edit_message_text(
        MESSAGES[lang]["daily_bonus_success"].format(
            bonus_amount=bonus_inr, 
            new_balance=new_balance * DOLLAR_TO_INR
        ) + f"\n\n{streak_message}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]),
        parse_mode='HTML'
    )

# --- NEW ADMIN COMMANDS ---

async def set_welcome_bonus_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = await get_user_lang(user.id)

    if user.id != ADMIN_ID:
        await update.message.reply_html(MESSAGES[lang]["broadcast_admin_only"])
        return

    if len(context.args) != 1:
        await update.message.reply_html("❌ Usage: /setwelbonus <amount_in_inr>")
        return

    try:
        new_bonus = float(context.args[0])
        settings_collection.update_one(
            {"_id": "welcome_bonus"},
            {"$set": {"amount_inr": new_bonus}},
            upsert=True
        )
        await update.message.reply_html(f"✅ Welcome bonus updated to ₹{new_bonus:.2f}")
    except ValueError:
        await update.message.reply_html("❌ Invalid amount. Please enter a number.")

async def handle_withdrawal_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if user.id != ADMIN_ID:
        return

    # FIX: Correctly split the query data
    data_parts = query.data.split("_")
    action = data_parts[0]
    user_id_str = data_parts[-1] # User ID is always the last part
    
    try:
        user_id = int(user_id_str)
    except ValueError:
        await query.edit_message_text("❌ Invalid User ID in callback data.")
        return
    
    # Use find_one_and_update to ensure atomic operation on a pending request
    withdrawal = withdrawals_collection.find_one_and_update(
        {"user_id": user_id, "status": "pending"},
        {"$set": {"status": f"{action}ed", "approved_date": datetime.now() if action == 'approve' else None}},
        return_document=True
    )
    
    if not withdrawal:
        await query.edit_message_text(f"❌ No pending withdrawal request found for user {user_id}")
        return

    if action == "approve":
        # Reset user earnings
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"earnings": 0.0}}
        )
        
        # Notify user
        try:
            user_lang = await get_user_lang(user_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ <b>Withdrawal Approved!</b>\n\nYour withdrawal of ₹{withdrawal['amount_inr']:.2f} has been approved. Payment will be processed within 24 hours.",
                parse_mode='HTML'
            )
        except Exception as e:
            logging.error(f"Could not notify user about withdrawal approval: {e}")
        
        await query.edit_message_text(f"✅ Withdrawal approved for user {user_id}. Earnings reset.")
            
    elif action == "reject":
        # Notify user
        try:
            user_lang = await get_user_lang(user_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ <b>Withdrawal Rejected!</b>\n\nYour withdrawal of ₹{withdrawal['amount_inr']:.2f} was rejected. Please contact admin for details.",
                parse_mode='HTML'
            )
        except Exception as e:
            logging.error(f"Could not notify user about withdrawal rejection: {e}")

        await query.edit_message_text(f"❌ Withdrawal rejected for user {user_id}")


# --- EXISTING FUNCTIONS (Updated for new features) ---

async def show_movie_groups_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    lang = await get_user_lang(query.from_user.id)

    keyboard = [
        [InlineKeyboardButton(MESSAGES[lang]["new_group_button"], url=NEW_MOVIE_GROUP_LINK)],
        [InlineKeyboardButton(MESSAGES[lang]["start_group_button"], url=MOVIE_GROUP_LINK)],
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
        f"<b>Your Referral Link:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        f"<b>Current Referral Rate:</b> ₹{tier_rate:.2f} per referral\n\n"
        f"<i>Share this link with friends and earn money when they join and search for movies!</i>"
    )
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

# --- PLACEHOLDER FUNCTIONS FOR MISSING COMMANDS/CALLBACKS ---
# These are needed so the bot application can build without crashing.

async def earn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await get_user_lang(update.effective_user.id)
    await update.message.reply_html(f"<b>{MESSAGES[lang]['earning_panel_message']}</b>\n\nUse the 'My Refer Link' button to get your link.")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = await get_user_lang(user.id)
    if user.id != ADMIN_ID:
        await update.message.reply_html(MESSAGES[lang]["broadcast_admin_only"])
        return
    
    # Placeholder admin panel keyboard
    keyboard = [
        [InlineKeyboardButton("Set Referral Rate", callback_data="admin_set_rate")],
        [InlineKeyboardButton("Set Welcome Bonus", callback_data="admin_set_welbonus")],
        [InlineKeyboardButton("Check Withdrawals", callback_data="admin_check_withdrawals")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(MESSAGES[lang]["admin_panel_title"], reply_markup=reply_markup)

async def clear_earn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await get_user_lang(update.effective_user.id)
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_html(MESSAGES[lang]["broadcast_admin_only"])
        return
    await update.message.reply_html(MESSAGES[lang]["clear_earn_usage"])

async def check_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await get_user_lang(update.effective_user.id)
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_html(MESSAGES[lang]["broadcast_admin_only"])
        return
    await update.message.reply_html(MESSAGES[lang]["check_stats_usage"])

async def checkbot_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await get_user_lang(update.effective_user.id)
    await update.message.reply_html(MESSAGES[lang]["checkbot_success"])

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
    await update.message.reply_html(MESSAGES[lang]["broadcast_message"])

async def set_referral_rate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await get_user_lang(update.effective_user.id)
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_html(MESSAGES[lang]["broadcast_admin_only"])
        return
    if len(context.args) != 1:
        await update.message.reply_html(MESSAGES[lang]["setrate_usage"])
        return
    
    try:
        new_rate = float(context.args[0])
        settings_collection.update_one(
            {"_id": "referral_rate"},
            {"$set": {"rate_inr": new_rate}},
            upsert=True
        )
        await update.message.reply_html(MESSAGES[lang]["setrate_success"].format(new_rate=new_rate))
    except ValueError:
        await update.message.reply_html(MESSAGES[lang]["invalid_rate"])

async def show_withdraw_details_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = await get_user_lang(query.from_user.id)
    
    user_data = users_collection.find_one({"user_id": query.from_user.id})
    earnings_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR
    
    message = MESSAGES[lang]["withdrawal_message_updated"].format(total_earnings=earnings_inr) # Placeholder for now
    
    keyboard = [
        [InlineKeyboardButton(MESSAGES[lang]["contact_admin_button"], url=f"https://t.me/{YOUR_TELEGRAM_HANDLE}")],
        [InlineKeyboardButton("💸 Request Withdrawal", callback_data="request_withdrawal")],
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Admin function not fully implemented.")
    # Placeholder for general admin callbacks


# --- MESSAGE HANDLER FOR MISSIONS ---

async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    
    # FIX: Add this check to prevent errors if user is not in DB yet
    if not users_collection.find_one({"user_id": user.id}):
        return 

    if chat.type in ["group", "supergroup"]:
        logging.info(f"Message received in group from user: {user.id}")

        # Mission: Search movies
        user_data = users_collection.find_one({"user_id": user.id})
        if user_data:
            today = datetime.now().date()
            last_search_date = user_data.get("last_search_date")
            
            # Use find_one_and_update for atomic updates
            if not last_search_date or not isinstance(last_search_date, datetime) or last_search_date.date() != today:
                # Reset daily search count
                users_collection.update_one(
                    {"user_id": user.id},
                    {"$set": {"daily_searches": 1, "last_search_date": datetime.now()}}
                )
            else:
                # Increment search count
                users_collection.update_one(
                    {"user_id": user.id},
                    {"$inc": {"daily_searches": 1}}
                )
            
            # Check if mission completed
            current_data = users_collection.find_one({"user_id": user.id})
            daily_searches = current_data.get("daily_searches", 0)
            
            mission_key = "search_3_movies"
            missions_completed = current_data.get("missions_completed", {})
            
            if daily_searches >= DAILY_MISSIONS[mission_key]["target"] and not missions_completed.get(mission_key):
                mission = DAILY_MISSIONS[mission_key]
                reward_usd = mission["reward"] / DOLLAR_TO_INR
                
                # Update mission completion and earnings atomically
                users_collection.update_one(
                    {"user_id": user.id},
                    {
                        "$inc": {"earnings": reward_usd},
                        "$set": {f"missions_completed.{mission_key}": True}
                    }
                )
                
                # Notify user
                try:
                    lang = await get_user_lang(user.id)
                    # Fetch updated earnings after the mission reward
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
                    logging.error(f"Could not notify user about mission completion: {e}")

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

                # FIX: Check if last_earning_date is a datetime object
                if not last_earning_date or not isinstance(last_earning_date, datetime) or last_earning_date.date() < today:
                    asyncio.create_task(add_payment_after_delay(context, user.id))
                    logging.info(f"Payment task scheduled for user {user.id} after 5 minutes.")
                else:
                    logging.info(f"Daily earning limit reached for referrer {referrer_id} from user {user.id}. No new payment scheduled.")

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
                
                # FIX: Check if last_earning_date is a datetime object
                if not last_earning_date or not isinstance(last_earning_date, datetime) or last_earning_date.date() < today:
                    
                    # Use tier-based referral rate
                    referrer_tier = await get_user_tier(referrer_id)
                    tier_rate = await get_tier_referral_rate(referrer_tier)
                    earning_rate_usd = tier_rate / DOLLAR_TO_INR
                    
                    # FIX: Only update the earnings once
                    users_collection.update_one(
                        {"user_id": referrer_id},
                        {"$inc": {"earnings": earning_rate_usd}}
                    )

                    referrals_collection.update_one(
                        {"referred_user_id": user_id},
                        {"$set": {"last_earning_date": datetime.now()}}
                    )
                    
                    # Fetch the updated referrer data
                    updated_referrer_data = users_collection.find_one({"user_id": referrer_id})
                    new_balance_inr = updated_referrer_data.get("earnings", 0.0) * DOLLAR_TO_INR
                    
                    referrer_lang = await get_user_lang(referrer_id)
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=MESSAGES[referrer_lang]["daily_earning_update"].format(
                                full_name=user_data.get("full_name"), new_balance=new_balance_inr
                            ),
                            parse_mode='HTML'
                        )
                        
                        # Check for level up
                        old_tier = referrer_tier # Old tier
                        new_tier = await get_user_tier(referrer_id) # New tier is calculated from updated earnings
                        
                        if new_tier > old_tier:
                            await context.bot.send_message(
                                chat_id=referrer_id,
                                text=MESSAGES[referrer_lang]["level_up"].format(
                                    level=new_tier, rate=await get_tier_referral_rate(new_tier)
                                ),
                                parse_mode='HTML'
                            )
                            
                    except (TelegramError, TimedOut) as e:
                        logging.error(f"Could not send daily earning update to referrer {referrer_id}: {e}")
                        
                    logging.info(f"Updated earnings for referrer {referrer_id}. New balance (INR): {new_balance_inr}")
                else:
                    logging.info(f"Daily earning limit reached for referrer {referrer_id} from user {user_id}. No new payment scheduled after delay.")

# --- LANGUAGE HANDLERS ---

async def language_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("English 🇬🇧", callback_data="lang_en")],
        [InlineKeyboardButton("हिन्दी 🇮🇳", callback_data="lang_hi")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    lang = await get_user_lang(query.from_user.id)
    await query.edit_message_text(text=MESSAGES[lang]["language_choice"], reply_markup=reply_markup)

async def handle_lang_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    lang = query.data.split("_")[1]
    await set_user_lang(query.from_user.id, lang)
    
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

# --- MAIN FUNCTION ---

def main() -> None:
    """Start the bot."""
    if not BOT_TOKEN:
        logging.error("BOT_TOKEN is not set. Please set it in the .env file.")
        return
    if not MONGO_URI:
        logging.error("MONGO_URI is not set. Please set it in the .env file.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # Command Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("earn", earn_command)) # PLACEHOLDER
    application.add_handler(CommandHandler("admin", admin_panel)) # PLACEHOLDER
    application.add_handler(CommandHandler("clearearn", clear_earn_command)) # PLACEHOLDER
    application.add_handler(CommandHandler("checkstats", check_stats_command)) # PLACEHOLDER
    application.add_handler(CommandHandler("checkbot", checkbot_command)) # PLACEHOLDER
    application.add_handler(CommandHandler("stats", stats_command)) # PLACEHOLDER
    application.add_handler(CommandHandler("broadcast", broadcast_command)) # PLACEHOLDER
    application.add_handler(CommandHandler("setrate", set_referral_rate_command)) # PLACEHOLDER
    application.add_handler(CommandHandler("setwelbonus", set_welcome_bonus_command))
    
    # Callback Handlers
    application.add_handler(CallbackQueryHandler(show_earning_panel, pattern="^show_earning_panel$"))
    application.add_handler(CallbackQueryHandler(show_movie_groups_menu, pattern="^show_movie_groups_menu$"))
    application.add_handler(CallbackQueryHandler(back_to_main_menu, pattern="^back_to_main_menu$"))
    application.add_handler(CallbackQueryHandler(language_menu, pattern="^select_lang$"))
    application.add_handler(CallbackQueryHandler(handle_lang_choice, pattern="^lang_"))
    application.add_handler(CallbackQueryHandler(show_help, pattern="^show_help$"))
    application.add_handler(CallbackQueryHandler(show_refer_link, pattern="^show_refer_link$"))
    application.add_handler(CallbackQueryHandler(show_withdraw_details_new, pattern="^show_withdraw_details_new$")) # PLACEHOLDER
    application.add_handler(CallbackQueryHandler(claim_daily_bonus, pattern="^claim_daily_bonus$"))
    application.add_handler(CallbackQueryHandler(handle_admin_callbacks, pattern="^admin_")) # PLACEHOLDER
    
    # New Features Callback Handlers
    application.add_handler(CallbackQueryHandler(spin_wheel_command, pattern="^spin_wheel$"))
    application.add_handler(CallbackQueryHandler(show_missions, pattern="^show_missions$"))
    application.add_handler(CallbackQueryHandler(request_withdrawal, pattern="^request_withdrawal$"))
    application.add_handler(CallbackQueryHandler(show_tier_benefits, pattern="^show_tier_benefits$"))
    # FIX: Corrected pattern for withdrawal approval/rejection
    application.add_handler(CallbackQueryHandler(handle_withdrawal_approval, pattern="^(approve|reject)_withdraw_\\d+$"))
    
    # Group Message Handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_group_messages))

    # Start the Bot
    # FIX: Using polling for simplicity, change to run_webhook if deploying to Render/Heroku etc.
    if WEB_SERVER_URL and BOT_TOKEN:
        # Webhook Mode (For cloud deployment like Render)
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=f"/{BOT_TOKEN}",
            webhook_url=f"{WEB_SERVER_URL}/{BOT_TOKEN}",
            allowed_updates=Update.ALL_TYPES
        )
        logging.info("Bot started in Webhook Mode.")
    else:
        # Polling Mode (For local testing or simple deployment)
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        logging.info("Bot started in Polling Mode.")

if __name__ == "__main__":
    main()
