import os
from pymongo import MongoClient
from dotenv import load_dotenv
import logging
import re
from telegram import BotCommand

# Configure basic logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# --- Utility Function for VIP Font (FIXED) ---
def apply_vip_font(text):
    """
    Converts a string to a stylized 'VIP Font' using Unicode characters, 
    while safely ignoring HTML tags (like <b>).
    """
    
    # Custom mapping based on the requested style [Usᴇ Tʜɪs Fᴏɴᴛ] (Small Caps/Script-like)
    mapping = {
        'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'ᴇ', 'F': 'ꜰ', 'G': 'ɢ', 'H': 'ʜ', 'I': 'ɪ', 
        'J': 'ᴊ', 'K': 'ᴋ', 'L': 'ʟ', 'M': 'ᴍ', 'N': 'ɴ', 'O': 'ᴏ', 'P': 'ᴘ', 'Q': 'Q', 'R': 'ʀ', 
        'S': 's', 'T': 'ᴛ', 'U': 'ᴜ', 'V': 'ᴠ', 'W': 'ᴡ', 'X': 'x', 'Y': 'ʏ', 'Z': 'ᴢ',
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 'g': 'ɢ', 'h': 'ʜ', 'i': 'ɪ', 
        'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ', 'q': 'Q', 'r': 'ʀ', 
        's': 's', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ',
        # Placeholders for f-string formatting (e.g., {balance:.2f}) are handled below
    }
    
    final_text = ""
    inside_tag = False
    inside_placeholder = False
    
    # Iterate through the text, character by character
    i = 0
    while i < len(text):
        char = text[i]
        
        # 1. Handle HTML tags (e.g., <b>)
        if char == '<':
            inside_tag = True
            final_text += char
            i += 1
            continue
        elif char == '>':
            inside_tag = False
            final_text += char
            i += 1
            continue
        elif inside_tag:
            final_text += char
            i += 1
            continue
            
        # 2. Handle f-string placeholders (e.g., {balance:.2f})
        elif char == '{':
            inside_placeholder = True
            final_text += char
            i += 1
            continue
        elif char == '}':
            inside_placeholder = False
            final_text += char
            i += 1
            continue
        elif inside_placeholder:
            final_text += char
            i += 1
            continue
            
        # 3. Apply VIP font to regular letters
        elif char.isalpha():
            # Get the replacement character, default to the original character if not found
            final_text += mapping.get(char.upper(), char)
            i += 1
            continue
        
        # 4. Keep all other characters (spaces, numbers, punctuation, emojis) as is
        else:
            final_text += char
            i += 1
            continue
            
    return final_text

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

# --- Premium Messages and Text (Updated for <b> tag and VIP Font Look) ---
MESSAGES = {
    "en": {
        "start_greeting": apply_vip_font("🌟✨ <b>Welcome to Movies Group Bot!</b> ✨🌟\n\n🎬 <b>Your Ultimate Movie Destination</b> 🎬\n\nGet your favorite movies instantly with our premium service! 🚀"),
        "start_step1": apply_vip_font("📥 <b>Step 1:</b> Join our exclusive movie group"),
        "start_step2": apply_vip_font("🔍 <b>Step 2:</b> Search any movie in the group"),
        "start_step3": apply_vip_font("🎯 <b>Step 3:</b> Get direct download link instantly"),
        "language_choice": apply_vip_font("🌐 <b>Choose Your Preferred Language:</b>"),
        "language_selected": apply_vip_font("✅ <b>Language Updated!</b>\n\nEnglish selected successfully! 🎯"),
        "language_prompt": apply_vip_font("🗣️ <b>Please select your language:</b>"),
        "help_message_text": apply_vip_font("💼 <b>HOW TO EARN MONEY</b> 💼\n\n💰 <b>3-Step Earning System:</b>\n\n1️⃣ <b>GET YOUR LINK</b>\n   └─ Use 'My Refer Link' for unique referral code\n\n2️⃣ <b>SHARE & INVITE</b>\n   └─ Share link with friends & family\n   └─ Ask them to join movie group\n\n3️⃣ <b>EARN PASSIVELY</b>\n   └─ Earn when friends search movies\n   └─ ₹0.20-0.50 per referral daily\n   └─ Up to 3 searches per friend daily\n\n⚡ <b>Passive Income Made Easy!</b> ⚡"),
        "refer_example_message": apply_vip_font("🎯 <b>REFERRAL MASTERY GUIDE</b> 🎯\n\n📊 <b>Earning Breakdown:</b>\n\n• Share your unique referral link\n• Friends join & search 3+ movies\n• You earn ₹{rate} per friend daily\n• Maximum 3 searches counted daily\n\n💡 <b>Pro Tip:</b> More referrals = More daily income!"),
        "withdrawal_details_message": apply_vip_font("💳 <b>WITHDRAWAL PORTAL</b> 💳\n\n💰 <b>Current Balance:</b> {balance}\n🎯 <b>Minimum Withdrawal:</b> ₹80.00\n⏰ <b>Processing Time:</b> 24 hours\n\n📥 <b>Ready to cash out?</b>"),
        "earning_panel_message": apply_vip_font("🚀 <b>PREMIUM EARNING DASHBOARD</b> 🚀\n\nManage all your income streams in one place!"),
        "daily_bonus_success": apply_vip_font("🎊 <b>DAILY BONUS CLAIMED!</b> 🎊\n\n💎 <b>Bonus Amount:</b> ₹{bonus_amount:.2f}\n💰 <b>New Balance:</b> ₹{new_balance:.2f}\n\n{streak_message}"),
        "daily_bonus_already_claimed": apply_vip_font("⏰ <b>BONUS ALREADY COLLECTED!</b>\n\n✨ Come back tomorrow for more rewards!"),
        "admin_panel_title": apply_vip_font("⚡ <b>ADMIN CONTROL PANEL</b> ⚡\n\nFull system management access"),
        "setrate_success": apply_vip_font("✅ <b>RATE UPDATED!</b>\n\nNew Tier 1 rate: ₹{new_rate:.2f}"),
        "setrate_usage": apply_vip_font("❌ <b>USAGE:</b> /setrate <amount_in_inr>"),
        "invalid_rate": apply_vip_font("⚠️ <b>INVALID AMOUNT</b>\nPlease enter valid number"),
        "referral_rate_updated": apply_vip_font("🔄 <b>Rate Updated Successfully!</b>\nNew Tier 1: ₹{new_rate:.2f}"),
        "broadcast_admin_only": apply_vip_font("🔒 <b>ADMIN ACCESS REQUIRED</b>"),
        "broadcast_message": apply_vip_font("📢 <b>BROADCAST MESSAGE</b>\n\nReply with /broadcast to send message"),
        "setwelbonus_usage": apply_vip_font("❌ <b>USAGE:</b> /setwelbonus <amount_in_inr>"),
        "setwelbonus_success": apply_vip_font("✅ <b>WELCOME BONUS UPDATED!</b>\nNew amount: ₹{new_bonus:.2f}"),
        "welcome_bonus_received": apply_vip_font("🎁 <b>WELCOME BONUS UNLOCKED!</b> 🎁\n\n💎 <b>Bonus:</b> ₹{amount:.2f}\n🚀 Start your earning journey now!"),
        "spin_wheel_title": apply_vip_font("🎡 <b>PREMIUM SPIN WHEEL</b> 🎡\n\n🎯 <b>Spins Remaining:</b> {spins_left}\n💡 <b>Get More Spins:</b> Refer 1 user = 1 free spin!"),
        "spin_wheel_button": apply_vip_font("✨ SPIN NOW ({spins_left} LEFT)"),
        "spin_wheel_animating": apply_vip_font("🌀 <b>SPINNING WHEEL...</b>\n\nGood luck! 🍀"),
        "spin_wheel_insufficient_spins": apply_vip_font("❌ <b>NO SPINS AVAILABLE!</b>\n\n💡 Refer 1 user to get free spin!"),
        "spin_wheel_win": apply_vip_font("🎉 <b>CONGRATULATIONS!</b> 🎉\n\n🏆 <b>You Won:</b> ₹{amount:.2f}\n💰 <b>New Balance:</b> ₹{new_balance:.2f}\n🎡 <b>Spins Left:</b> {spins_left}"),
        "spin_wheel_lose": apply_vip_font("😔 <b>Better Luck Next Time!</b>\n\n💎 Balance remains: ₹{new_balance:.2f}\n🎡 Spins remaining: {spins_left}"),
        "missions_title": apply_vip_font("🎯 <b>DAILY MISSIONS</b> 🎯\n\nComplete missions for extra rewards!"),
        "mission_search_note": apply_vip_font("⏳ <b>Search 3 Movies</b> ({current}/{target})\n💡 Paid searches from referrals count"),
        "mission_search_progress": apply_vip_font("⏳ <b>Search Progress</b> ({current}/{target})"),
        "mission_complete": apply_vip_font("✅ <b>MISSION ACCOMPLISHED!</b>\n\n🎁 <b>Reward:</b> ₹{reward:.2f}\n💎 <b>New Balance:</b> ₹{new_balance:.2f}"),
        "withdrawal_request_sent": apply_vip_font("📨 <b>REQUEST SUBMITTED!</b>\n\n💰 <b>Amount:</b> ₹{amount:.2f}\n⏰ <b>Processing:</b> 24 hours\n\nWe'll notify you once processed!"),
        "withdrawal_insufficient": apply_vip_font("❌ <b>INSUFFICIENT BALANCE</b>\n\n🎯 <b>Minimum:</b> ₹80.00 required"),
        "withdrawal_approved_user": apply_vip_font("✅ <b>WITHDRAWAL APPROVED!</b>\n\n💳 <b>Amount:</b> ₹{amount:.2f}\n⏰ <b>Processing:</b> 24 hours\n\nPayment on its way! 🚀"),
        "withdrawal_rejected_user": apply_vip_font("❌ <b>WITHDRAWAL REJECTED</b>\n\n📞 Contact admin for details"),
        "ref_link_message": apply_vip_font("🔗 <b>YOUR REFERRAL LINK</b>\n\n{referral_link}\n\n💎 <b>Current Rate:</b> ₹{tier_rate:.2f} per referral\n\nShare & start earning today! 💰"),
        "new_referral_notification": apply_vip_font("🎊 <b>NEW REFERRAL ALERT!</b> 🎊\n\n👤 <b>User:</b> {full_name} ({username})\n💎 <b>Bonus:</b> ₹{bonus:.2f}\n🎡 <b>Free Spin:</b> +1 Spin added!"),
        "daily_earning_update_new": apply_vip_font("💰 <b>DAILY EARNING UPDATE!</b>\n\n👤 <b>From:</b> {full_name}\n💎 <b>Amount:</b> ₹{amount:.2f}\n💰 <b>New Balance:</b> ₹{new_balance:.2f}"),
        "search_success_message": apply_vip_font("✅ <b>SEARCH COMPLETE!</b>\n\n🎬 Movie link ready!\n💰 Referrer paid successfully"),
        "clear_earn_usage": apply_vip_font("❌ <b>USAGE:</b> /clearearn <user_id>"),
        "clear_earn_success": apply_vip_font("✅ <b>EARNINGS CLEARED!</b>\nUser: {user_id}"),
        "clear_earn_not_found": apply_vip_font("❌ <b>USER NOT FOUND</b>\nID: {user_id}"),
        "check_stats_usage": apply_vip_font("❌ <b>USAGE:</b> /checkstats <user_id>"),
        "check_stats_message": apply_vip_font("📊 <b>USER STATISTICS</b>\n\n🆔 ID: {user_id}\n💰 Earnings: ₹{earnings:.2f}\n👥 Referrals: {referrals}"),
        "check_stats_not_found": apply_vip_font("❌ <b>USER NOT FOUND</b>\nID: {user_id}"),
        "stats_message": apply_vip_font("📈 <b>BOT ANALYTICS</b>\n\n👥 Total Users: {total_users}\n✅ Active Users: {approved_users}"),
        "channel_bonus_claimed": apply_vip_font("✅ <b>CHANNEL BONUS CLAIMED!</b>\n\n💎 <b>Amount:</b> ₹{amount:.2f}\n💰 <b>New Balance:</b> ₹{new_balance:.2f}"),
        "channel_not_joined": apply_vip_font("❌ <b>CHANNEL MEMBERSHIP REQUIRED</b>\n\nJoin {channel} to claim bonus"),
        "channel_already_claimed": apply_vip_font("⏰ <b>BONUS ALREADY CLAIMED</b>"),
        "channel_bonus_failure": apply_vip_font("❌ <b>VERIFICATION FAILED</b>\nPlease join {channel}"),
        "top_users_title": apply_vip_font("🏆 <b>TOP 10 EARNERS</b> 🏆\n\n(Total Earnings Leaderboard)\n\n"),
        "clear_junk_success": apply_vip_font("🧹 <b>SYSTEM CLEANED!</b>\n\n🗑️ Users Removed: {users}\n📊 Referrals Cleared: {referrals}\n💳 Withdrawals Processed: {withdrawals}"),
        "clear_junk_admin_only": apply_vip_font("🔒 <b>ADMIN ACCESS REQUIRED</b>"),
        "tier_benefits_title": apply_vip_font("👑 <b>VIP TIER SYSTEM</b> 👑\n\nEarn more as you grow!"),
        "tier_info": apply_vip_font("💎 <b>{tier_name}</b> (Level {tier})\n   └─ Min Earnings: ₹{min_earnings:.2f}\n   └─ Benefit: {benefit}"),
        "tier_benefits_message": apply_vip_font("👑 <b>VIP TIER BENEFITS</b> 👑\n\nUpgrade your earning potential!\n\n• 🥉 Tier 1: Beginner (₹0.20/referral)\n• 🥈 Tier 2: Pro (₹0.35/referral)\n• 🥇 Tier 3: Expert (₹0.45/referral)\n• 💎 Tier 4: Master (₹0.50/referral)"),
        "help_menu_title": apply_vip_font("🆘 <b>PREMIUM SUPPORT</b>"),
        "help_menu_text": apply_vip_font("Need assistance? We're here to help!"),
        "help_message": apply_vip_font("🆘 <b>CUSTOMER SUPPORT</b>\n\n📞 <b>Admin Contact:</b> @{telegram_handle}\n💡 <b>Tip:</b> Check referral guide first!"),
        "alert_daily_bonus": apply_vip_font("🔔 <b>DAILY BONUS REMINDER!</b>\n\n🎁 Claim your free bonus now!"),
        "alert_mission": apply_vip_font("🎯 <b>MISSION ALERT!</b>\n\nComplete daily missions for extra cash!"),
        "alert_refer": apply_vip_font("🚀 <b>EARNING OPPORTUNITY!</b>\n\nShare your link & earn up to ₹{max_rate:.2f} daily!"),
        "alert_spin": apply_vip_font("🎰 <b>FREE SPIN AVAILABLE!</b>\n\nSpin to win up to ₹2.00!"),
        "join_channel_button_text": apply_vip_font("🌟 JOIN CHANNEL & RETRY"),
        "admin_user_stats_prompt": apply_vip_font("📊 <b>USER STATS REQUEST</b>\n\nReply with User ID:"),
        "admin_add_money_prompt": apply_vip_font("💰 <b>ADD FUNDS</b>\n\nAmount for user {user_id} (INR):"),
        "admin_clear_data_prompt": apply_vip_font("⚠️ <b>DATA MANAGEMENT</b>\n\nReply:\n• `earning` - Clear earnings only\n• `all` - Delete all user data"),
        "admin_user_not_found": apply_vip_font("❌ <b>USER NOT FOUND</b>\nID: {user_id}"),
        "admin_add_money_success": apply_vip_font("✅ <b>FUNDS ADDED!</b>\n\nUser: {user_id}\nAmount: ₹{amount:.2f}\nNew Balance: ₹{new_balance:.2f}"),
        "admin_clear_earnings_success": apply_vip_font("✅ <b>EARNINGS CLEARED!</b>\nUser: {user_id}\nNew Balance: ₹0.00"),
        "admin_delete_user_success": apply_vip_font("✅ <b>USER DELETED!</b>\nID: {user_id}"),
        "admin_invalid_input": apply_vip_font("❌ <b>INVALID INPUT</b>"),
        "leaderboard_title": apply_vip_font("🏆 <b>MONTHLY LEADERBOARD</b> 🏆\n\nTop 10 Referrers of the Month!"),
        "leaderboard_rank_entry": apply_vip_font("   📈 Monthly Referrals: {monthly_refs}\n   💰 Total Balance: ₹{balance:.2f}\n"),
        "monthly_reward_notification": apply_vip_font("🎉 <b>LEADERBOARD REWARD!</b> 🎉\n\n🏅 <b>Rank:</b> #{rank}\n💰 <b>Reward:</b> ₹{reward:.2f}\n💎 <b>New Balance:</b> ₹{new_balance:.2f}"),
        "channel_bonus_error": apply_vip_font("❌ <b>VERIFICATION ERROR</b>\n\nPlease ensure you've joined {channel}\n\nAdmin notified if issue persists"),
    },
    "hi": {
        "start_greeting": apply_vip_font("🌟✨ <b>मूवी ग्रुप बॉट में स्वागत है!</b> ✨🌟\n\n🎬 <b>आपकी अंतिम मूवी डेस्टिनेशन</b> 🎬\n\nप्रीमियम सर्विस के साथ तुरंत पाएं अपनी पसंदीदा फिल्में! 🚀"),
        "start_step1": apply_vip_font("📥 <b>स्टेप 1:</b> हमारे एक्सक्लूसिव मूवी ग्रुप में जुड़ें"),
        "start_step2": apply_vip_font("🔍 <b>स्टेप 2:</b> ग्रुप में कोई भी मूवी सर्च करें"),
        "start_step3": apply_vip_font("🎯 <b>स्टेप 3:</b> तुरंत डायरेक्ट डाउनलोड लिंक पाएं"),
        "language_choice": apply_vip_font("🌐 <b>अपनी पसंदीदा भाषा चुनें:</b>"),
        "language_selected": apply_vip_font("✅ <b>भाषा अपडेट!</b>\n\nहिंदी सफलतापूर्वक चुनी गई! 🎯"),
        "language_prompt": apply_vip_font("🗣️ <b>कृपया अपनी भाषा चुनें:</b>"),
        "help_message_text": apply_vip_font("💼 <b>पैसे कैसे कमाएं</b> 💼\n\n💰 <b>3-स्टेप कमाई सिस्टम:</b>\n\n1️⃣ <b>अपनी लिंक पाएं</b>\n   └─ 'My Refer Link' से यूनिक कोड पाएं\n\n2️⃣ <b>शेयर करें और इनवाइट करें</b>\n   └─ दोस्तों और परिवार के साथ शेयर करें\n   └─ उन्हें मूवी ग्रुप में जुड़ने को कहें\n\n3️⃣ <b>पैसिव इनकम कमाएं</b>\n   └─ दोस्तों के सर्च करने पर कमाएं\n   └─ ₹0.20-0.50 प्रति रेफरल डेली\n   └─ प्रति दोस्त 3 सर्च तक\n\n⚡ <b>आसान पैसिव इनकम!</b> ⚡"),
        "refer_example_message": apply_vip_font("🎯 <b>रेफरल मास्टरी गाइड</b> 🎯\n\n📊 <b>कमाई ब्रेकडाउन:</b>\n\n• अपनी यूनिक लिंक शेयर करें\n• दोस्त जुड़ें और 3+ मूवी सर्च करें\n• आप कमाएं ₹{rate} प्रति दोस्त डेली\n• मैक्सिमम 3 सर्च काउंटेड डेली\n\n💡 <b>प्रो टिप:</b> ज्यादा रेफरल = ज्यादा डेली इनकम!"),
        "withdrawal_details_message": apply_vip_font("💳 <b>विथड्रॉल पोर्टल</b> 💳\n\n💰 <b>करंट बैलेंस:</b> {balance}\n🎯 <b>मिनिमम विथड्रॉल:</b> ₹80.00\n⏰ <b>प्रोसेसिंग टाइम:</b> 24 घंटे\n\n📥 <b>कैश आउट के लिए तैयार?</b>"),
        "earning_panel_message": apply_vip_font("🚀 <b>प्रीमियम कमाई डैशबोर्ड</b> 🚀\n\nसभी इनकम स्ट्रीम्स एक जगह मैनेज करें!"),
        "daily_bonus_success": apply_vip_font("🎊 <b>डेली बोनस क्लेम!</b> 🎊\n\n💎 <b>बोनस अमाउंट:</b> ₹{bonus_amount:.2f}\n💰 <b>नया बैलेंस:</b> ₹{new_balance:.2f}\n\n{streak_message}"),
        "daily_bonus_already_claimed": apply_vip_font("⏰ <b>बोनस पहले ही क्लेम!</b>\n\n✨ कल और रिवॉर्ड्स के लिए वापस आएं!"),
        "admin_panel_title": apply_vip_font("⚡ <b>एडमिन कंट्रोल पैनल</b> ⚡\n\nफुल सिस्टम मैनेजमेंट एक्सेस"),
        "setrate_success": apply_vip_font("✅ <b>रेट अपडेट!</b>\n\nनया टियर 1 रेट: ₹{new_rate:.2f}"),
        "setrate_usage": apply_vip_font("❌ <b>यूसेज:</b> /setrate <amount_in_inr>"),
        "invalid_rate": apply_vip_font("⚠️ <b>इनवैलिड अमाउंट</b>\nवैलिड नंबर डालें"),
        "referral_rate_updated": apply_vip_font("🔄 <b>रेट सक्सेसफुली अपडेट!</b>\nनया टियर 1: ₹{new_rate:.2f}"),
        "broadcast_admin_only": apply_vip_font("🔒 <b>एडमिन एक्सेस रिक्वायर्ड</b>"),
        "broadcast_message": apply_vip_font("📢 <b>ब्रॉडकास्ट मैसेज</b>\n\nमैसेज भेजने के लिए /broadcast के साथ रिप्लाई करें"),
        "setwelbonus_usage": apply_vip_font("❌ <b>यूसेज:</b> /setwelbonus <amount_in_inr>"),
        "setwelbonus_success": apply_vip_font("✅ <b>वेलकम बोनस अपडेट!</b>\nनई अमाउंट: ₹{new_bonus:.2f}"),
        "welcome_bonus_received": apply_vip_font("🎁 <b>वेलकम बोनस अनलॉक!</b> 🎁\n\n💎 <b>बोनस:</b> ₹{amount:.2f}\n🚀 अब शुरू करें अपनी कमाई जर्नी!"),
        "spin_wheel_title": apply_vip_font("🎡 <b>प्रीमियम स्पिन व्हील</b> 🎡\n\n🎯 <b>बची स्पिन:</b> {spins_left}\n💡 <b>ज्यादा स्पिन पाएं:</b> 1 यूजर रेफर = 1 फ्री स्पिन!"),
        "spin_wheel_button": apply_vip_font("✨ अभी स्पिन करें ({spins_left} शेष)"),
        "spin_wheel_animating": apply_vip_font("🌀 <b>स्पिनिंग व्हील...</b>\n\nगुड लक! 🍀"),
        "spin_wheel_insufficient_spins": apply_vip_font("❌ <b>कोई स्पिन नहीं!</b>\n\n💡 फ्री स्पिन के लिए 1 यूजर रेफर करें!"),
        "spin_wheel_win": apply_vip_font("🎉 <b>कॉन्ग्रैचुलेशन!</b> 🎉\n\n🏆 <b>आप जीते:</b> ₹{amount:.2f}\n💰 <b>नया बैलेंस:</b> ₹{new_balance:.2f}\n🎡 <b>बची स्पिन:</b> {spins_left}"),
        "spin_wheel_lose": apply_vip_font("😔 <b>अगली बार बेहतर किस्मत!</b>\n\n💎 बैलेंस: ₹{new_balance:.2f}\n🎡 स्पिन बची: {spins_left}"),
        "missions_title": apply_vip_font("🎯 <b>डेली मिशन</b> 🎯\n\nएक्स्ट्रा रिवॉर्ड्स के लिए मिशन पूरे करें!"),
        "mission_search_note": apply_vip_font("⏳ <b>3 मूवी सर्च</b> ({current}/{target})\n💡 रेफरल के पेड सर्च काउंट होते हैं"),
        "mission_search_progress": apply_vip_font("⏳ <b>सर्च प्रोग्रेस</b> ({current}/{target})"),
        "mission_complete": apply_vip_font("✅ <b>मिशन कंप्लीट!</b>\n\n🎁 <b>रिवॉर्ड:</b> ₹{reward:.2f}\n💎 <b>नया बैलेंस:</b> ₹{new_balance:.2f}"),
        "withdrawal_request_sent": apply_vip_font("📨 <b>रिक्वेस्ट सबमिट!</b>\n\n💰 <b>अमाउंट:</b> ₹{amount:.2f}\n⏰ <b>प्रोसेसिंग:</b> 24 घंटे\n\nप्रोसेस होने पर नोटिफाई करेंगे!"),
        "withdrawal_insufficient": apply_vip_font("❌ <b>इनसफिशिएंट बैलेंस</b>\n\n🎯 <b>मिनिमम:</b> ₹80.00 रिक्वायर्ड"),
        "withdrawal_approved_user": apply_vip_font("✅ <b>विथड्रॉल अप्रूव्ड!</b>\n\n💳 <b>अमाउंट:</b> ₹{amount:.2f}\n⏰ <b>प्रोसेसिंग:</b> 24 घंटे\n\nपेमेंट ऑन द वे! 🚀"),
        "withdrawal_rejected_user": apply_vip_font("❌ <b>विथड्रॉल रिजेक्टेड</b>\n\n📞 डिटेल्स के लिए एडमिन से संपर्क करें"),
        "ref_link_message": apply_vip_font("🔗 <b>आपकी रेफरल लिंक</b>\n\n{referral_link}\n\n💎 <b>करंट रेट:</b> ₹{tier_rate:.2f} प्रति रेफरल\n\nशेयर करें और आज ही कमाना शुरू करें! 💰"),
        "new_referral_notification": apply_vip_font("🎊 <b>नया रेफरल अलर्ट!</b> 🎊\n\n👤 <b>यूजर:</b> {full_name} ({username})\n💎 <b>बोनस:</b> ₹{bonus:.2f}\n🎡 <b>फ्री स्पिन:</b> +1 स्पिन ऐडेड!"),
        "daily_earning_update_new": apply_vip_font("💰 <b>डेली कमाई अपडेट!</b>\n\n👤 <b>से:</b> {full_name}\n💎 <b>अमाउंट:</b> ₹{amount:.2f}\n💰 <b>नया बैलेंस:</b> ₹{new_balance:.2f}"),
        "search_success_message": apply_vip_font("✅ <b>सर्च कंप्लीट!</b>\n\n🎬 मूवी लिंक रेडी!\n💰 रेफरर को पेमेंट सक्सेसफुल"),
        "clear_earn_usage": apply_vip_font("❌ <b>यूसेज:</b> /clearearn <user_id>"),
        "clear_earn_success": apply_vip_font("✅ <b>कमाई क्लियर!</b>\nयूजर: {user_id}"),
        "clear_earn_not_found": apply_vip_font("❌ <b>यूजर नहीं मिला</b>\nID: {user_id}"),
        "check_stats_usage": apply_vip_font("❌ <b>यूसेज:</b> /checkstats <user_id>"),
        "check_stats_message": apply_vip_font("📊 <b>यूजर स्टैटिस्टिक्स</b>\n\n🆔 ID: {user_id}\n💰 कमाई: ₹{earnings:.2f}\n👥 रेफरल: {referrals}"),
        "check_stats_not_found": apply_vip_font("❌ <b>यूजर नहीं मिला</b>\nID: {user_id}"),
        "stats_message": apply_vip_font("📈 <b>बॉट एनालिटिक्स</b>\n\n👥 टोटल यूजर: {total_users}\n✅ एक्टिव यूजर: {approved_users}"),
        "channel_bonus_claimed": apply_vip_font("✅ <b>चैनल बोनस क्लेम!</b>\n\n💎 <b>अमाउंट:</b> ₹{amount:.2f}\n💰 <b>नया बैलेंस:</b> ₹{new_balance:.2f}"),
        "channel_not_joined": apply_vip_font("❌ <b>चैनल मेंबरशिप रिक्वायर्ड</b>\n\nबोनस के लिए {channel} जॉइन करें"),
        "channel_already_claimed": apply_vip_font("⏰ <b>बोनस पहले ही क्लेम</b>"),
        "channel_bonus_failure": apply_vip_font("❌ <b>वेरिफिकेशन फेल्ड</b>\nकृपया {channel} जॉइन करें"),
        "top_users_title": apply_vip_font("🏆 <b>टॉप 10 अर्नर</b> 🏆\n\n(टोटल अर्निंग लीडरबोर्ड)\n\n"),
        "clear_junk_success": apply_vip_font("🧹 <b>सिस्टम क्लीन!</b>\n\n🗑️ रिमूव्ड यूजर: {users}\n📊 क्लियर रेफरल: {referrals}\n💳 प्रोसेस्ड विथड्रॉल: {withdrawals}"),
        "clear_junk_admin_only": apply_vip_font("🔒 <b>एडमिन एक्सेस रिक्वायर्ड</b>"),
        "tier_benefits_title": apply_vip_font("👑 <b>वीआईपी टियर सिस्टम</b> 👑\n\nग्रो करते हुए ज्यादा कमाएं!"),
        "tier_info": apply_vip_font("💎 <b>{tier_name}</b> (लेवल {tier})\n   └─ मिनिमम कमाई: ₹{min_earnings:.2f}\n   └─ बेनिफिट: {benefit}"),
        "tier_benefits_message": apply_vip_font("👑 <b>वीआईपी टियर बेनिफिट्स</b> 👑\n\nअपनी कमाई पोटेंशियल अपग्रेड करें!\n\n• 🥉 टियर 1: बिगिनर (₹0.20/रेफरल)\n• 🥈 टियर 2: प्रो (₹0.35/रेफरल)\n• 🥇 टियर 3: एक्सपर्ट (₹0.45/रेफरल)\n• 💎 टियर 4: मास्टर (₹0.50/रेफरल)"),
        "help_menu_title": apply_vip_font("🆘 <b>प्रीमियम सपोर्ट</b>"),
        "help_menu_text": apply_vip_font("असिस्टेंस चाहिए? हम यहां हैं मदद के लिए!"),
        "help_message": apply_vip_font("🆘 <b>कस्टमर सपोर्ट</b>\n\n📞 <b>एडमिन कॉन्टैक्ट:</b> @{telegram_handle}\n💡 <b>टिप:</b> पहले रेफरल गाइड चेक करें!"),
        "alert_daily_bonus": apply_vip_font("🔔 <b>डेली बोनस रिमाइंडर!</b>\n\n🎁 अब क्लेम करें अपना फ्री बोनस!"),
        "alert_mission": apply_vip_font("🎯 <b>मिशन अलर्ट!</b>\n\nएक्स्ट्रा कैश के लिए डेली मिशन पूरे करें!"),
        "alert_refer": apply_vip_font("🚀 <b>कमाई का मौका!</b>\n\nअपनी लिंक शेयर करें और ₹{max_rate:.2f} डेली तक कमाएं!"),
        "alert_spin": apply_vip_font("🎰 <b>फ्री स्पिन अवेलेबल!</b>\n\n₹2.00 तक जीतने के लिए स्पिन करें!"),
        "join_channel_button_text": apply_vip_font("🌟 चैनल जॉइन करें और रिट्राई"),
        "admin_user_stats_prompt": apply_vip_font("📊 <b>यूजर स्टैट्स रिक्वेस्ट</b>\n\nयूजर ID के साथ रिप्लाई करें:"),
        "admin_add_money_prompt": apply_vip_font("💰 <b>फंड्स ऐड करें</b>\n\nयूजर {user_id} के लिए अमाउंट (INR):"),
        "admin_clear_data_prompt": apply_vip_font("⚠️ <b>डेटा मैनेजमेंट</b>\n\nरिप्लाई करें:\n• `earning` - सिर्फ कमाई क्लियर\n• `all` - सारा यूजर डेटा डिलीट"),
        "admin_user_not_found": apply_vip_font("❌ <b>यूजर नहीं मिला</b>\nID: {user_id}"),
        "admin_add_money_success": apply_vip_font("✅ <b>फंड्स ऐडेड!</b>\n\nयूजर: {user_id}\nअमाउंट: ₹{amount:.2f}\nनया बैलेंस: ₹{new_balance:.2f}"),
        "admin_clear_earnings_success": apply_vip_font("✅ <b>कमाई क्लियर!</b>\nयूजर: {user_id}\nनया बैलेंस: ₹0.00"),
        "admin_delete_user_success": apply_vip_font("✅ <b>यूजर डिलीटेड!</b>\nID: {user_id}"),
        "admin_invalid_input": apply_vip_font("❌ <b>इनवैलिड इनपुट</b>"),
        "leaderboard_title": apply_vip_font("🏆 <b>मंथली लीडरबोर्ड</b> 🏆\n\nमहीने के टॉप 10 रेफरर!"),
        "leaderboard_rank_entry": apply_vip_font("   📈 मंथली रेफरल: {monthly_refs}\n   💰 टोटल बैलेंस: ₹{balance:.2f}\n"),
        "monthly_reward_notification": apply_vip_font("🎉 <b>लीडरबोर्ड रिवॉर्ड!</b> 🎉\n\n🏅 <b>रैंक:</b> #{rank}\n💰 <b>रिवॉर्ड:</b> ₹{reward:.2f}\n💎 <b>नया बैलेंस:</b> ₹{new_balance:.2f}"),
        "channel_bonus_error": apply_vip_font("❌ <b>वेरिफिकेशन एरर</b>\n\nकृपया सुनिश्चित करें आपने {channel} जॉइन किया है\n\nइशू बना रहा तो एडमिन को नोटिफाई किया गया"),
    }
}


# --- Telegram Bot Commands ---
USER_COMMANDS = [
    BotCommand("start", apply_vip_font("🚀 Start bot & main menu")),
    BotCommand("earn", apply_vip_font("💰 Earning panel & referral link")),
]

ADMIN_COMMANDS = [
    BotCommand("admin", apply_vip_font("⚡ Admin Panel & settings")),
]

