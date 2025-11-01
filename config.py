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

# Your Telegram handle
YOUR_TELEGRAM_HANDLE = os.getenv("YOUR_TELEGRAM_HANDLE", "telegram") 
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")

# --- Group and Channel Links ---
NEW_MOVIE_GROUP_LINK = "https://t.me/asfilter_bot"
MOVIE_GROUP_LINK = "https://t.me/asfilter_group" 
ALL_GROUPS_LINK = "https://t.me/addlist/6urdhhdLRqhiZmQ1"

EXAMPLE_SCREENSHOT_URL = os.getenv("EXAMPLE_SCREENSHOT_URL", "https://envs.sh/v3A.jpg")

# --- Channel Bonus Settings ---
CHANNEL_USERNAME = "@asbhai_bsr"
CHANNEL_ID = -1002283182645
CHANNEL_BONUS = 2.00
JOIN_CHANNEL_LINK = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"

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
DOLLAR_TO_INR = 75.0

# --- Daily Bonus Settings ---
DAILY_BONUS_BASE = 0.10
DAILY_BONUS_MULTIPLIER = 0.10 
DAILY_BONUS_STREAK_MULTIPLIER = DAILY_BONUS_MULTIPLIER 

# --- Spin Wheel Settings ---
PRIZES_WEIGHTS = {
    0.00: 4,
    0.10: 3,
    0.20: 3,
    0.50: 2,
    1.00: 1,
    2.00: 1 
}
SPIN_PRIZES = list(PRIZES_WEIGHTS.keys())
SPIN_WEIGHTS = list(PRIZES_WEIGHTS.values())

SPIN_WHEEL_CONFIG = {
    "initial_free_spins": 3,
    "refer_to_get_spin": 1
}

# --- Tier System Settings ---
TIERS = {
    1: {"min_earnings": 0, "rate": 0.20, "name": "Beginner", "benefits_en": "Basic referral rate (₹0.20)", "benefits_hi": "सामान्य रेफरल दर (₹0.20)"},
    2: {"min_earnings": 200, "rate": 0.35, "name": "Pro", "benefits_en": "Higher referral rate (₹0.35)", "benefits_hi": "उच्च रेफरल दर (₹0.35)"},
    3: {"min_earnings": 500, "rate": 0.45, "name": "Expert", "benefits_en": "Very high referral rate (₹0.45)", "benefits_hi": "बहुत उच्च रेफरल दर (₹0.45)"},
    4: {"min_earnings": 1000, "rate": 0.50, "name": "Master", "benefits_en": "Maximum referral rate (₹0.50)", "benefits_hi": "अधिकतम रेफरल दर (₹0.50)"}
}

# --- Daily Mission Settings ---
DAILY_MISSIONS = {
    "search_3_movies": {"reward": 0.50, "target": 3, "name": "Search 3 Movies (Ref. Paid Search)", "name_hi": "3 फिल्में खोजें (रेफ़रल का भुगतान)"}, 
    "refer_2_friends": {"reward": 1.40, "target": 2, "name": "Refer 2 Friends", "name_hi": "2 दोस्तों को रेफ़र करें"},
    "claim_daily_bonus": {"reward": 0.10, "target": 1, "name": "Claim Daily Bonus", "name_hi": "दैनिक बोनस क्लेम करें"}
}

# --- Premium Messages and Text ---
MESSAGES = {
    "en": {
        "start_greeting": "🌟✨ *Welcome to Movies Group Bot!* ✨🌟\n\n🎬 *Your Ultimate Movie Destination* 🎬\n\nGet your favorite movies instantly with our premium service! 🚀",
        "start_step1": "📥 *Step 1:* Join our exclusive movie group",
        "start_step2": "🔍 *Step 2:* Search any movie in the group",
        "start_step3": "🎯 *Step 3:* Get direct download link instantly",
        "language_choice": "🌐 *Choose Your Preferred Language:*",
        "language_selected": "✅ *Language Updated!*\n\nEnglish selected successfully! 🎯",
        "language_prompt": "🗣️ *Please select your language:*",
        "help_message_text": "💼 *HOW TO EARN MONEY* 💼\n\n💰 **3-Step Earning System:**\n\n1️⃣ **GET YOUR LINK**\n   └─ Use 'My Refer Link' for unique referral code\n\n2️⃣ **SHARE & INVITE**\n   └─ Share link with friends & family\n   └─ Ask them to join movie group\n\n3️⃣ **EARN PASSIVELY**\n   └─ Earn when friends search movies\n   └─ ₹0.20-0.50 per referral daily\n   └─ Up to 3 searches per friend daily\n\n⚡ *Passive Income Made Easy!* ⚡",
        "refer_example_message": "🎯 *REFERRAL MASTERY GUIDE* 🎯\n\n📊 **Earning Breakdown:**\n\n• Share your unique referral link\n• Friends join & search 3+ movies\n• You earn ₹{rate} per friend daily\n• Maximum 3 searches counted daily\n\n💡 *Pro Tip:* More referrals = More daily income!",
        "withdrawal_details_message": "💳 *WITHDRAWAL PORTAL* 💳\n\n💰 **Current Balance:** {balance}\n🎯 **Minimum Withdrawal:** ₹80.00\n⏰ **Processing Time:** 24 hours\n\n📥 *Ready to cash out?*",
        "earning_panel_message": "🚀 *PREMIUM EARNING DASHBOARD* 🚀\n\nManage all your income streams in one place!",
        "daily_bonus_success": "🎊 *DAILY BONUS CLAIMED!* 🎊\n\n💎 **Bonus Amount:** ₹{bonus_amount:.2f}\n💰 **New Balance:** ₹{new_balance:.2f}\n\n{streak_message}",
        "daily_bonus_already_claimed": "⏰ *BONUS ALREADY COLLECTED!*\n\n✨ Come back tomorrow for more rewards!",
        "admin_panel_title": "⚡ *ADMIN CONTROL PANEL* ⚡\n\nFull system management access",
        "setrate_success": "✅ *RATE UPDATED!*\n\nNew Tier 1 rate: ₹{new_rate:.2f}",
        "setrate_usage": "❌ *USAGE:* /setrate <amount_in_inr>",
        "invalid_rate": "⚠️ *INVALID AMOUNT*\nPlease enter valid number",
        "referral_rate_updated": "🔄 *Rate Updated Successfully!*\nNew Tier 1: ₹{new_rate:.2f}",
        "broadcast_admin_only": "🔒 *ADMIN ACCESS REQUIRED*",
        "broadcast_message": "📢 *BROADCAST MESSAGE*\n\nReply with /broadcast to send message",
        "setwelbonus_usage": "❌ *USAGE:* /setwelbonus <amount_in_inr>",
        "setwelbonus_success": "✅ *WELCOME BONUS UPDATED!*\nNew amount: ₹{new_bonus:.2f}",
        "welcome_bonus_received": "🎁 *WELCOME BONUS UNLOCKED!* 🎁\n\n💎 **Bonus:** ₹{amount:.2f}\n🚀 Start your earning journey now!",
        "spin_wheel_title": "🎡 *PREMIUM SPIN WHEEL* 🎡\n\n🎯 **Spins Remaining:** {spins_left}\n💡 **Get More Spins:** Refer 1 user = 1 free spin!",
        "spin_wheel_button": "✨ SPIN NOW ({spins_left} LEFT)",
        "spin_wheel_animating": "🌀 *SPINNING WHEEL...*\n\nGood luck! 🍀",
        "spin_wheel_insufficient_spins": "❌ *NO SPINS AVAILABLE!*\n\n💡 Refer 1 user to get free spin!",
        "spin_wheel_win": "🎉 *CONGRATULATIONS!* 🎉\n\n🏆 **You Won:** ₹{amount:.2f}\n💰 **New Balance:** ₹{new_balance:.2f}\n🎡 **Spins Left:** {spins_left}",
        "spin_wheel_lose": "😔 *Better Luck Next Time!*\n\n💎 Balance remains: ₹{new_balance:.2f}\n🎡 Spins remaining: {spins_left}",
        "missions_title": "🎯 *DAILY MISSIONS* 🎯\n\nComplete missions for extra rewards!",
        "mission_search_note": "⏳ *Search 3 Movies* ({current}/{target})\n💡 Paid searches from referrals count",
        "mission_search_progress": "⏳ *Search Progress* ({current}/{target})",
        "mission_complete": "✅ *MISSION ACCOMPLISHED!*\n\n🎁 **Reward:** ₹{reward:.2f}\n💎 **New Balance:** ₹{new_balance:.2f}",
        "withdrawal_request_sent": "📨 *REQUEST SUBMITTED!*\n\n💰 **Amount:** ₹{amount:.2f}\n⏰ **Processing:** 24 hours\n\nWe'll notify you once processed!",
        "withdrawal_insufficient": "❌ *INSUFFICIENT BALANCE*\n\n🎯 **Minimum:** ₹80.00 required",
        "withdrawal_approved_user": "✅ *WITHDRAWAL APPROVED!*\n\n💳 **Amount:** ₹{amount:.2f}\n⏰ **Processing:** 24 hours\n\nPayment on its way! 🚀",
        "withdrawal_rejected_user": "❌ *WITHDRAWAL REJECTED*\n\n📞 Contact admin for details",
        "ref_link_message": "🔗 *YOUR REFERRAL LINK*\n\n{referral_link}\n\n💎 **Current Rate:** ₹{tier_rate:.2f} per referral\n\nShare & start earning today! 💰",
        "new_referral_notification": "🎊 *NEW REFERRAL ALERT!* 🎊\n\n👤 **User:** {full_name} ({username})\n💎 **Bonus:** ₹{bonus:.2f}\n🎡 **Free Spin:** +1 Spin added!",
        "daily_earning_update_new": "💰 *DAILY EARNING UPDATE!*\n\n👤 **From:** {full_name}\n💎 **Amount:** ₹{amount:.2f}\n💰 **New Balance:** ₹{new_balance:.2f}",
        "search_success_message": "✅ *SEARCH COMPLETE!*\n\n🎬 Movie link ready!\n💰 Referrer paid successfully",
        "clear_earn_usage": "❌ *USAGE:* /clearearn <user_id>",
        "clear_earn_success": "✅ *EARNINGS CLEARED!*\nUser: {user_id}",
        "clear_earn_not_found": "❌ *USER NOT FOUND*\nID: {user_id}",
        "check_stats_usage": "❌ *USAGE:* /checkstats <user_id>",
        "check_stats_message": "📊 *USER STATISTICS*\n\n🆔 ID: {user_id}\n💰 Earnings: ₹{earnings:.2f}\n👥 Referrals: {referrals}",
        "check_stats_not_found": "❌ *USER NOT FOUND*\nID: {user_id}",
        "stats_message": "📈 *BOT ANALYTICS*\n\n👥 Total Users: {total_users}\n✅ Active Users: {approved_users}",
        "channel_bonus_claimed": "✅ *CHANNEL BONUS CLAIMED!*\n\n💎 **Amount:** ₹{amount:.2f}\n💰 **New Balance:** ₹{new_balance:.2f}",
        "channel_not_joined": "❌ *CHANNEL MEMBERSHIP REQUIRED*\n\nJoin {channel} to claim bonus",
        "channel_already_claimed": "⏰ *BONUS ALREADY CLAIMED*",
        "channel_bonus_failure": "❌ *VERIFICATION FAILED*\nPlease join {channel}",
        "top_users_title": "🏆 *TOP 10 EARNERS* 🏆\n\n(Total Earnings Leaderboard)\n\n",
        "clear_junk_success": "🧹 *SYSTEM CLEANED!*\n\n🗑️ Users Removed: {users}\n📊 Referrals Cleared: {referrals}\n💳 Withdrawals Processed: {withdrawals}",
        "clear_junk_admin_only": "🔒 *ADMIN ACCESS REQUIRED*",
        "tier_benefits_title": "👑 *VIP TIER SYSTEM* 👑\n\nEarn more as you grow!",
        "tier_info": "💎 *{tier_name}* (Level {tier})\n   └─ Min Earnings: ₹{min_earnings:.2f}\n   └─ Benefit: {benefit}",
        "tier_benefits_message": "👑 *VIP TIER BENEFITS* 👑\n\nUpgrade your earning potential!\n\n• 🥉 Tier 1: Beginner (₹0.20/referral)\n• 🥈 Tier 2: Pro (₹0.35/referral)\n• 🥇 Tier 3: Expert (₹0.45/referral)\n• 💎 Tier 4: Master (₹0.50/referral)",
        "help_menu_title": "🆘 *PREMIUM SUPPORT*",
        "help_menu_text": "Need assistance? We're here to help!",
        "help_message": "🆘 *CUSTOMER SUPPORT*\n\n📞 **Admin Contact:** @{telegram_handle}\n💡 **Tip:** Check referral guide first!",
        "alert_daily_bonus": "🔔 *DAILY BONUS REMINDER!*\n\n🎁 Claim your free bonus now!",
        "alert_mission": "🎯 *MISSION ALERT!*\n\nComplete daily missions for extra cash!",
        "alert_refer": "🚀 *EARNING OPPORTUNITY!*\n\nShare your link & earn up to ₹{max_rate:.2f} daily!",
        "alert_spin": "🎰 *FREE SPIN AVAILABLE!*\n\nSpin to win up to ₹2.00!",
        "join_channel_button_text": "🌟 JOIN CHANNEL & RETRY",
        "admin_user_stats_prompt": "📊 *USER STATS REQUEST*\n\nReply with User ID:",
        "admin_add_money_prompt": "💰 *ADD FUNDS*\n\nAmount for user {user_id} (INR):",
        "admin_clear_data_prompt": "⚠️ *DATA MANAGEMENT*\n\nReply:\n• `earning` - Clear earnings only\n• `all` - Delete all user data",
        "admin_user_not_found": "❌ *USER NOT FOUND*\nID: {user_id}",
        "admin_add_money_success": "✅ *FUNDS ADDED!*\n\nUser: {user_id}\nAmount: ₹{amount:.2f}\nNew Balance: ₹{new_balance:.2f}",
        "admin_clear_earnings_success": "✅ *EARNINGS CLEARED!*\nUser: {user_id}\nNew Balance: ₹0.00",
        "admin_delete_user_success": "✅ *USER DELETED!*\nID: {user_id}",
        "admin_invalid_input": "❌ *INVALID INPUT*",
        "leaderboard_title": "🏆 *MONTHLY LEADERBOARD* 🏆\n\nTop 10 Referrers of the Month!",
        "leaderboard_rank_entry": "   📈 Monthly Referrals: {monthly_refs}\n   💰 Total Balance: ₹{balance:.2f}\n",
        "monthly_reward_notification": "🎉 *LEADERBOARD REWARD!* 🎉\n\n🏅 **Rank:** #{rank}\n💰 **Reward:** ₹{reward:.2f}\n💎 **New Balance:** ₹{new_balance:.2f}",
        "channel_bonus_error": "❌ *VERIFICATION ERROR*\n\nPlease ensure you've joined {channel}\n\nAdmin notified if issue persists",
    },
    "hi": {
        "start_greeting": "🌟✨ *मूवी ग्रुप बॉट में स्वागत है!* ✨🌟\n\n🎬 *आपकी अंतिम मूवी डेस्टिनेशन* 🎬\n\nप्रीमियम सर्विस के साथ तुरंत पाएं अपनी पसंदीदा फिल्में! 🚀",
        "start_step1": "📥 *स्टेप 1:* हमारे एक्सक्लूसिव मूवी ग्रुप में जुड़ें",
        "start_step2": "🔍 *स्टेप 2:* ग्रुप में कोई भी मूवी सर्च करें",
        "start_step3": "🎯 *स्टेप 3:* तुरंत डायरेक्ट डाउनलोड लिंक पाएं",
        "language_choice": "🌐 *अपनी पसंदीदा भाषा चुनें:*",
        "language_selected": "✅ *भाषा अपडेट!*\n\nहिंदी सफलतापूर्वक चुनी गई! 🎯",
        "language_prompt": "🗣️ *कृपया अपनी भाषा चुनें:*",
        "help_message_text": "💼 *पैसे कैसे कमाएं* 💼\n\n💰 **3-स्टेप कमाई सिस्टम:**\n\n1️⃣ **अपनी लिंक पाएं**\n   └─ 'My Refer Link' से यूनिक कोड पाएं\n\n2️⃣ **शेयर करें और इनवाइट करें**\n   └─ दोस्तों और परिवार के साथ शेयर करें\n   └─ उन्हें मूवी ग्रुप में जुड़ने को कहें\n\n3️⃣ **पैसिव इनकम कमाएं**\n   └─ दोस्तों के सर्च करने पर कमाएं\n   └─ ₹0.20-0.50 प्रति रेफरल डेली\n   └─ प्रति दोस्त 3 सर्च तक\n\n⚡ *आसान पैसिव इनकम!* ⚡",
        "refer_example_message": "🎯 *रेफरल मास्टरी गाइड* 🎯\n\n📊 **कमाई ब्रेकडाउन:**\n\n• अपनी यूनिक लिंक शेयर करें\n• दोस्त जुड़ें और 3+ मूवी सर्च करें\n• आप कमाएं ₹{rate} प्रति दोस्त डेली\n• मैक्सिमम 3 सर्च काउंटेड डेली\n\n💡 *प्रो टिप:* ज्यादा रेफरल = ज्यादा डेली इनकम!",
        "withdrawal_details_message": "💳 *विथड्रॉल पोर्टल* 💳\n\n💰 **करंट बैलेंस:** {balance}\n🎯 **मिनिमम विथड्रॉल:** ₹80.00\n⏰ **प्रोसेसिंग टाइम:** 24 घंटे\n\n📥 *कैश आउट के लिए तैयार?*",
        "earning_panel_message": "🚀 *प्रीमियम कमाई डैशबोर्ड* 🚀\n\nसभी इनकम स्ट्रीम्स एक जगह मैनेज करें!",
        "daily_bonus_success": "🎊 *डेली बोनस क्लेम!* 🎊\n\n💎 **बोनस अमाउंट:** ₹{bonus_amount:.2f}\n💰 **नया बैलेंस:** ₹{new_balance:.2f}\n\n{streak_message}",
        "daily_bonus_already_claimed": "⏰ *बोनस पहले ही क्लेम!*\n\n✨ कल और रिवॉर्ड्स के लिए वापस आएं!",
        "admin_panel_title": "⚡ *एडमिन कंट्रोल पैनल* ⚡\n\nफुल सिस्टम मैनेजमेंट एक्सेस",
        "setrate_success": "✅ *रेट अपडेट!*\n\nनया टियर 1 रेट: ₹{new_rate:.2f}",
        "setrate_usage": "❌ *यूसेज:* /setrate <amount_in_inr>",
        "invalid_rate": "⚠️ *इनवैलिड अमाउंट*\nवैलिड नंबर डालें",
        "referral_rate_updated": "🔄 *रेट सक्सेसफुली अपडेट!*\nनया टियर 1: ₹{new_rate:.2f}",
        "broadcast_admin_only": "🔒 *एडमिन एक्सेस रिक्वायर्ड*",
        "broadcast_message": "📢 *ब्रॉडकास्ट मैसेज*\n\nमैसेज भेजने के लिए /broadcast के साथ रिप्लाई करें",
        "setwelbonus_usage": "❌ *यूसेज:* /setwelbonus <amount_in_inr>",
        "setwelbonus_success": "✅ *वेलकम बोनस अपडेट!*\nनई अमाउंट: ₹{new_bonus:.2f}",
        "welcome_bonus_received": "🎁 *वेलकम बोनस अनलॉक!* 🎁\n\n💎 **बोनस:** ₹{amount:.2f}\n🚀 अब शुरू करें अपनी कमाई जर्नी!",
        "spin_wheel_title": "🎡 *प्रीमियम स्पिन व्हील* 🎡\n\n🎯 **बची स्पिन:** {spins_left}\n💡 **ज्यादा स्पिन पाएं:** 1 यूजर रेफर = 1 फ्री स्पिन!",
        "spin_wheel_button": "✨ अभी स्पिन करें ({spins_left} शेष)",
        "spin_wheel_animating": "🌀 *स्पिनिंग व्हील...*\n\nगुड लक! 🍀",
        "spin_wheel_insufficient_spins": "❌ *कोई स्पिन नहीं!*\n\n💡 फ्री स्पिन के लिए 1 यूजर रेफर करें!",
        "spin_wheel_win": "🎉 *कॉन्ग्रैचुलेशन!* 🎉\n\n🏆 **आप जीते:** ₹{amount:.2f}\n💰 **नया बैलेंस:** ₹{new_balance:.2f}\n🎡 **बची स्पिन:** {spins_left}",
        "spin_wheel_lose": "😔 *अगली बार बेहतर किस्मत!*\n\n💎 बैलेंस: ₹{new_balance:.2f}\n🎡 स्पिन बची: {spins_left}",
        "missions_title": "🎯 *डेली मिशन* 🎯\n\nएक्स्ट्रा रिवॉर्ड्स के लिए मिशन पूरे करें!",
        "mission_search_note": "⏳ *3 मूवी सर्च* ({current}/{target})\n💡 रेफरल के पेड सर्च काउंट होते हैं",
        "mission_search_progress": "⏳ *सर्च प्रोग्रेस* ({current}/{target})",
        "mission_complete": "✅ *मिशन कंप्लीट!*\n\n🎁 **रिवॉर्ड:** ₹{reward:.2f}\n💎 **नया बैलेंस:** ₹{new_balance:.2f}",
        "withdrawal_request_sent": "📨 *रिक्वेस्ट सबमिट!*\n\n💰 **अमाउंट:** ₹{amount:.2f}\n⏰ **प्रोसेसिंग:** 24 घंटे\n\nप्रोसेस होने पर नोटिफाई करेंगे!",
        "withdrawal_insufficient": "❌ *इनसफिशिएंट बैलेंस*\n\n🎯 **मिनिमम:** ₹80.00 रिक्वायर्ड",
        "withdrawal_approved_user": "✅ *विथड्रॉल अप्रूव्ड!*\n\n💳 **अमाउंट:** ₹{amount:.2f}\n⏰ **प्रोसेसिंग:** 24 घंटे\n\nपेमेंट ऑन द वे! 🚀",
        "withdrawal_rejected_user": "❌ *विथड्रॉल रिजेक्टेड*\n\n📞 डिटेल्स के लिए एडमिन से संपर्क करें",
        "ref_link_message": "🔗 *आपकी रेफरल लिंक*\n\n{referral_link}\n\n💎 **करंट रेट:** ₹{tier_rate:.2f} प्रति रेफरल\n\nशेयर करें और आज ही कमाना शुरू करें! 💰",
        "new_referral_notification": "🎊 *नया रेफरल अलर्ट!* 🎊\n\n👤 **यूजर:** {full_name} ({username})\n💎 **बोनस:** ₹{bonus:.2f}\n🎡 **फ्री स्पिन:** +1 स्पिन ऐडेड!",
        "daily_earning_update_new": "💰 *डेली कमाई अपडेट!*\n\n👤 **से:** {full_name}\n💎 **अमाउंट:** ₹{amount:.2f}\n💰 **नया बैलेंस:** ₹{new_balance:.2f}",
        "search_success_message": "✅ *सर्च कंप्लीट!*\n\n🎬 मूवी लिंक रेडी!\n💰 रेफरर को पेमेंट सक्सेसफुल",
        "clear_earn_usage": "❌ *यूसेज:* /clearearn <user_id>",
        "clear_earn_success": "✅ *कमाई क्लियर!*\nयूजर: {user_id}",
        "clear_earn_not_found": "❌ *यूजर नहीं मिला*\nID: {user_id}",
        "check_stats_usage": "❌ *यूसेज:* /checkstats <user_id>",
        "check_stats_message": "📊 *यूजर स्टैटिस्टिक्स*\n\n🆔 ID: {user_id}\n💰 कमाई: ₹{earnings:.2f}\n👥 रेफरल: {referrals}",
        "check_stats_not_found": "❌ *यूजर नहीं मिला*\nID: {user_id}",
        "stats_message": "📈 *बॉट एनालिटिक्स*\n\n👥 टोटल यूजर: {total_users}\n✅ एक्टिव यूजर: {approved_users}",
        "channel_bonus_claimed": "✅ *चैनल बोनस क्लेम!*\n\n💎 **अमाउंट:** ₹{amount:.2f}\n💰 **नया बैलेंस:** ₹{new_balance:.2f}",
        "channel_not_joined": "❌ *चैनल मेंबरशिप रिक्वायर्ड*\n\nबोनस के लिए {channel} जॉइन करें",
        "channel_already_claimed": "⏰ *बोनस पहले ही क्लेम*",
        "channel_bonus_failure": "❌ *वेरिफिकेशन फेल्ड*\nकृपया {channel} जॉइन करें",
        "top_users_title": "🏆 *टॉप 10 अर्नर* 🏆\n\n(टोटल अर्निंग लीडरबोर्ड)\n\n",
        "clear_junk_success": "🧹 *सिस्टम क्लीन!*\n\n🗑️ रिमूव्ड यूजर: {users}\n📊 क्लियर रेफरल: {referrals}\n💳 प्रोसेस्ड विथड्रॉल: {withdrawals}",
        "clear_junk_admin_only": "🔒 *एडमिन एक्सेस रिक्वायर्ड*",
        "tier_benefits_title": "👑 *वीआईपी टियर सिस्टम* 👑\n\nग्रो करते हुए ज्यादा कमाएं!",
        "tier_info": "💎 *{tier_name}* (लेवल {tier})\n   └─ मिनिमम कमाई: ₹{min_earnings:.2f}\n   └─ बेनिफिट: {benefit}",
        "tier_benefits_message": "👑 *वीआईपी टियर बेनिफिट्स* 👑\n\nअपनी कमाई पोटेंशियल अपग्रेड करें!\n\n• 🥉 टियर 1: बिगिनर (₹0.20/रेफरल)\n• 🥈 टियर 2: प्रो (₹0.35/रेफरल)\n• 🥇 टियर 3: एक्सपर्ट (₹0.45/रेफरल)\n• 💎 टियर 4: मास्टर (₹0.50/रेफरल)",
        "help_menu_title": "🆘 *प्रीमियम सपोर्ट*",
        "help_menu_text": "असिस्टेंस चाहिए? हम यहां हैं मदद के लिए!",
        "help_message": "🆘 *कस्टमर सपोर्ट*\n\n📞 **एडमिन कॉन्टैक्ट:** @{telegram_handle}\n💡 **टिप:** पहले रेफरल गाइड चेक करें!",
        "alert_daily_bonus": "🔔 *डेली बोनस रिमाइंडर!*\n\n🎁 अब क्लेम करें अपना फ्री बोनस!",
        "alert_mission": "🎯 *मिशन अलर्ट!*\n\nएक्स्ट्रा कैश के लिए डेली मिशन पूरे करें!",
        "alert_refer": "🚀 *कमाई का मौका!*\n\nअपनी लिंक शेयर करें और ₹{max_rate:.2f} डेली तक कमाएं!",
        "alert_spin": "🎰 *फ्री स्पिन अवेलेबल!*\n\n₹2.00 तक जीतने के लिए स्पिन करें!",
        "join_channel_button_text": "🌟 चैनल जॉइन करें और रिट्राई",
        "admin_user_stats_prompt": "📊 *यूजर स्टैट्स रिक्वेस्ट*\n\nयूजर ID के साथ रिप्लाई करें:",
        "admin_add_money_prompt": "💰 *फंड्स ऐड करें*\n\nयूजर {user_id} के लिए अमाउंट (INR):",
        "admin_clear_data_prompt": "⚠️ *डेटा मैनेजमेंट*\n\nरिप्लाई करें:\n• `earning` - सिर्फ कमाई क्लियर\n• `all` - सारा यूजर डेटा डिलीट",
        "admin_user_not_found": "❌ *यूजर नहीं मिला*\nID: {user_id}",
        "admin_add_money_success": "✅ *फंड्स ऐडेड!*\n\nयूजर: {user_id}\nअमाउंट: ₹{amount:.2f}\nनया बैलेंस: ₹{new_balance:.2f}",
        "admin_clear_earnings_success": "✅ *कमाई क्लियर!*\nयूजर: {user_id}\nनया बैलेंस: ₹0.00",
        "admin_delete_user_success": "✅ *यूजर डिलीटेड!*\nID: {user_id}",
        "admin_invalid_input": "❌ *इनवैलिड इनपुट*",
        "leaderboard_title": "🏆 *मंथली लीडरबोर्ड* 🏆\n\nमहीने के टॉप 10 रेफरर!",
        "leaderboard_rank_entry": "   📈 मंथली रेफरल: {monthly_refs}\n   💰 टोटल बैलेंस: ₹{balance:.2f}\n",
        "monthly_reward_notification": "🎉 *लीडरबोर्ड रिवॉर्ड!* 🎉\n\n🏅 **रैंक:** #{rank}\n💰 **रिवॉर्ड:** ₹{reward:.2f}\n💎 **नया बैलेंस:** ₹{new_balance:.2f}",
        "channel_bonus_error": "❌ *वेरिफिकेशन एरर*\n\nकृपया सुनिश्चित करें आपने {channel} जॉइन किया है\n\nइशू बना रहा तो एडमिन को नोटिफाई किया गया",
    }
}

# --- Telegram Bot Commands ---
from telegram import BotCommand
USER_COMMANDS = [
    BotCommand("start", "🚀 Start bot & main menu"),
    BotCommand("earn", "💰 Earning panel & referral link"),
]

ADMIN_COMMANDS = [
    BotCommand("admin", "⚡ Admin Panel & settings"),
]
