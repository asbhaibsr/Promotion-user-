import os
from pymongo import MongoClient
from dotenv import load_dotenv
import logging

# Configure basic logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# --- Utility Function for VIP Font ---
# This function converts text to the requested small caps font.
def to_vip_font(text):
    # Mapping for the specific small caps font style
    mapping = {
        'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'ᴇ', 'F': 'ꜰ', 'G': 'ɢ', 'H': 'ʜ', 
        'I': 'ɪ', 'J': 'ᴊ', 'K': 'ᴋ', 'L': 'ʟ', 'M': 'ᴍ', 'N': 'ɴ', 'O': 'ᴏ', 'P': 'ᴘ', 
        'Q': 'Q', 'R': 'ʀ', 'S': 's', 'T': 'ᴛ', 'U': 'ᴜ', 'V': 'ᴠ', 'W': 'ᴡ', 'X': 'x', 
        'Y': 'ʏ', 'Z': 'ᴢ', 
        # Lowercase mapping for consistency (using the same small caps style)
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 'g': 'ɢ', 'h': 'ʜ', 
        'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ', 
        'q': 'Q', 'r': 'ʀ', 's': 's', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 
        'y': 'ʏ', 'z': 'ᴢ',
    }
    result = ''
    for char in text:
        # Prioritize title case conversion for the first letter of words
        if char.isalpha():
             # Convert to uppercase for mapping if it is a title case
            if char.isupper() or (len(result) > 0 and result[-1].isspace() and char.islower()):
                result += mapping.get(char.upper(), char)
            else:
                result += mapping.get(char, char)
        else:
            result += char
    return result.title().replace(' ', ' ') # Final title case adjustment for better look


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

EXAMPLE_SCREENSHOT_URL = os.getenv("EXAMPLE_SCREENSHOT_URL", "https://envs.sh/v3A.jpg")

# --- चैनल बोनस सेटिंग्स ---
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

# --- डेली बोनस सेटिंग्स ---
DAILY_BONUS_BASE = 0.10
DAILY_BONUS_MULTIPLIER = 0.10 
DAILY_BONUS_STREAK_MULTIPLIER = DAILY_BONUS_MULTIPLIER 

# --- स्पिन व्हील सेटिंग्स ---
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

# --- टियर सिस्टम सेटिंग्स (₹0.54 की कमाई को ध्यान में रखते हुए) ---
TIERS = {
    1: {"min_earnings": 0, "rate": 0.20, "name": "Beginner", "benefits_en": "Basic referral rate (₹0.20)", "benefits_hi": "सामान्य रेफरल दर (₹0.20)"},
    2: {"min_earnings": 200, "rate": 0.35, "name": "Pro", "benefits_en": "Higher referral rate (₹0.35)", "benefits_hi": "उच्च रेफरल दर (₹0.35)"},
    3: {"min_earnings": 500, "rate": 0.45, "name": "Expert", "benefits_en": "Very high referral rate (₹0.45)", "benefits_hi": "बहुत उच्च रेफरल दर (₹0.45)"},
    4: {"min_earnings": 1000, "rate": 0.50, "name": "Master", "benefits_en": "Maximum referral rate (₹0.50)", "benefits_hi": "अधिकतम रेफरल दर (₹0.50)"}
}

# --- डेली मिशन सेटिंग्स ---
DAILY_MISSIONS = {
    "search_3_movies": {"reward": 0.50, "target": 3, "name": "Search 3 Movies (Ref. Paid Search)", "name_hi": "3 फिल्में खोजें (रेफ़रल का भुगतान)"}, 
    "refer_2_friends": {"reward": 1.40, "target": 2, "name": "Refer 2 Friends", "name_hi": "2 दोस्तों को रेफ़र करें"},
    "claim_daily_bonus": {"reward": 0.10, "target": 1, "name": "Claim Daily Bonus", "name_hi": "दैनिक बोनस क्लेम करें"}
}

# --- Messages and Text ---
MESSAGES = {
    "en": {
        "start_greeting": f"👋 {to_vip_font('Hey')}! {to_vip_font('Welcome to the Movies Group Bot')}. {to_vip_font('Get your favorite movies by following these simple steps')}:",
        "start_step1": "✨ {to_vip_font('Click the button below to join our movie group')}.",
        "start_step2": "🎬 {to_vip_font('Go to the group and type the name of the movie you want')}.",
        "start_step3": "🔗 {to_vip_font('The bot will give you a link to your movie')}.",
        "language_choice": "🌐 {to_vip_font('Choose your language')}:",
        "language_selected": "✅ {to_vip_font('Language changed to English')}.",
        "language_prompt": "✍️ {to_vip_font('Please select your language')}:",
        "help_message_text": f"<b>🤝 {to_vip_font('How to Earn Money')}</b>\n\n1️⃣ <b>{to_vip_font('Get Your Link')}:</b> {to_vip_font("Use the 'My Refer Link' button to get your unique referral link")}.\n\n2️⃣ <b>{to_vip_font('Share Your Link')}:</b> {to_vip_font('Share this link with your friends. Tell them to start the bot and join our movie group')}.\n\n3️⃣ <b>{to_vip_font('Earn')}:</b> {to_vip_font('When a referred friend searches for a movie in the group and completes the shortlink process, you earn money! You can earn from each friend up to 3 times per day')}.",
        "refer_example_message": f"<b>💡 {to_vip_font('Referral Example / How to Earn')}</b>\n\n1. {to_vip_font('Share your link with friends')}.\n2. {to_vip_font('They start the bot and join the movie group')}.\n3. {to_vip_font('They search for <b>3 movies</b> in the group (or more)')}.\n4. {to_vip_font('You get paid for <b>3 searches/day</b> from that friend! ₹{rate} per referral/day')}.",
        "withdrawal_details_message": f"💸 <b>{to_vip_font('Withdrawal Details')}</b>\n\n{to_vip_font('Your current balance is')} <b>₹{{balance}}</b>. {to_vip_font('You can withdraw when your balance reaches <b>₹80</b> or more')}.\n\n{to_vip_font('Click the button below to request withdrawal')}.",
        "earning_panel_message": f"💰 <b>{to_vip_font('Earning Panel')}</b>\n\n{to_vip_font('Manage all your earning activities here')}.",
        "daily_bonus_success": f"🎉 <b>{to_vip_font('Daily Bonus Claimed!')}</b>\n{to_vip_font('You have successfully claimed your daily bonus of')} <b>₹{{bonus_amount:.2f}}</b>. {to_vip_font('Your new balance is')} <b>₹{{new_balance:.2f}}</b>.\n\n{{streak_message}}",
        "daily_bonus_already_claimed": f"⏳ <b>{to_vip_font('Bonus Already Claimed!')}</b>\n{to_vip_font('You have already claimed your bonus for today. Try again tomorrow!')}",
        "admin_panel_title": f"⚙️ <b>{to_vip_font('Admin Panel')}</b>\n\n{to_vip_font('Manage bot settings and users from here')}.",
        "setrate_success": f"✅ {to_vip_font('Tier 1 Referral earning rate has been updated to')} <b>₹{{new_rate:.2f}}</b>.",
        "setrate_usage": "❌ {to_vip_font('Usage: /setrate <new_rate_in_inr>')}",
        "invalid_rate": "❌ {to_vip_font('Invalid rate. Please enter a number')}.",
        "referral_rate_updated": f"⭐ {to_vip_font('The new Tier 1 referral rate is now')} <b>₹{{new_rate:.2f}}</b>.",
        "broadcast_admin_only": "❌ {to_vip_font('This command is for the bot admin only')}.",
        "broadcast_message": "📢 {to_vip_font('Please reply to a message with /broadcast to send it to all users')}.",
        "setwelbonus_usage": "❌ {to_vip_font('Usage: /setwelbonus <amount_in_inr>')}",
        "setwelbonus_success": f"✅ {to_vip_font('Welcome bonus updated to')} <b>₹{{new_bonus:.2f}}</b>",
        "welcome_bonus_received": f"🎁 <b>{to_vip_font('Welcome Bonus!')}</b>\n\n{to_vip_font('You have received')} <b>₹{{amount:.2f}}</b> {to_vip_font('welcome bonus! Start earning more by referring friends')}.",
        "spin_wheel_title": f"🎡 <b>{to_vip_font('Spin the Wheel - Free Earning!')}</b>\n\n{to_vip_font('Remaining Spins:')} <b>{{spins_left}}</b>\n\n<b>{to_vip_font('How to Get More Spins:')}</b>\n🔗 {to_vip_font('Refer 1 new user to get 1 free spin!')}",
        "spin_wheel_button": "✨ {to_vip_font('Spin Now')} ({{spins_left}} {to_vip_font('Left')})",
        "spin_wheel_animating": "🍀 <b>{to_vip_font('Spinning...')}</b>\n\n{to_vip_font('Wait for the result!')} ⏳",
        "spin_wheel_insufficient_spins": "❌ <b>{to_vip_font('No Spins Left!')}</b>\n\n{to_vip_font('You need to refer 1 new user to get another free spin!')}",
        "spin_wheel_win": f"🎉 <b>{to_vip_font('Congratulations!')}</b>\n\n{to_vip_font('You won:')} <b>₹{{amount:.2f}}!</b>\n\n{to_vip_font('New balance:')} <b>₹{{new_balance:.2f}}</b>\n\n{to_vip_font('Remaining Spins:')} <b>{{spins_left}}</b>",
        "spin_wheel_lose": f"😢 <b>{to_vip_font('Better luck next time!')}</b>\n\n{to_vip_font('You didn\'t win anything this time')}.\n\n{to_vip_font('Remaining balance:')} <b>₹{{new_balance:.2f}}</b>\n\n{to_vip_font('Remaining Spins:')} <b>{{spins_left}}</b>",
        "missions_title": f"🎯 <b>{to_vip_font('Daily Missions')}</b>\n\n{to_vip_font('Complete missions to earn extra rewards! Check your progress below')}:",
        "mission_search_note": "⏳ {to_vip_font('Search 3 Movies (Paid Search)')} ({{current}}/{{target}}) [<b>{to_vip_font('In Progress')}</b>]\n\n<b>{to_vip_font('Note:')}</b> {to_vip_font('This mission is completed when you receive payment from your referred users 3 times today')}.",
        "mission_search_progress": "⏳ {to_vip_font('Search 3 Movies')} ({{current}}/{{target}}) [<b>{to_vip_font('In Progress')}</b>]",
        "mission_complete": f"✅ <b>{to_vip_font('Mission Completed!')}</b>\n\n{to_vip_font('You earned')} <b>₹{{reward:.2f}}</b> {to_vip_font('for')} {{mission_name}}!\n{to_vip_font('New balance:')} <b>₹{{new_balance:.2f}}</b>",
        "withdrawal_request_sent": f"✅ <b>{to_vip_font('Withdrawal Request Sent!')}</b>\n\n{to_vip_font('Your request for')} <b>₹{{amount:.2f}}</b> {to_vip_font('has been sent to admin. You will receive payment within 24 hours')}.",
        "withdrawal_insufficient": "❌ <b>{to_vip_font('Insufficient Balance!')}</b>\n\n{to_vip_font('Minimum withdrawal amount is')} <b>₹80.00</b>",
        "withdrawal_approved_user": f"✅ <b>{to_vip_font('Withdrawal Approved!')}</b>\n\n{to_vip_font('Your withdrawal of')} <b>₹{{amount:.2f}}</b> {to_vip_font('has been approved. Payment will be processed within 24 hours')}.",
        "withdrawal_rejected_user": f"❌ <b>{to_vip_font('Withdrawal Rejected!')}</b>\n\n{to_vip_font('Your withdrawal of')} <b>₹{{amount:.2f}}</b> {to_vip_font('was rejected. Please contact admin for details')}.",
        "ref_link_message": f"🔗 <b>{to_vip_font('Your Referral Link:')}</b>\n<b>{{referral_link}}</b>\n\n💰 <b>{to_vip_font('Current Referral Rate:')}</b> <b>₹{{tier_rate:.2f}}</b> {to_vip_font('per referral')}\n\n<i>{to_vip_font('Share this link with friends and earn money when they join and search for movies!')}</i>",
        "new_referral_notification": f"🎉 <b>{to_vip_font('New Referral!')}</b>\n\n<b>{{full_name}}</b> ({{username}}) {to_vip_font('has joined using your link!')}\n\n💰 {to_vip_font('You received a joining bonus of')} <b>₹{{bonus:.2f}}!</b>\n\n🎰 {to_vip_font('You also earned 1 Free Spin for the Spin Wheel!')}",
        "daily_earning_update_new": f"💸 <b>{to_vip_font('Daily Referral Earning!')}</b>\n\n{to_vip_font('You earned')} <b>₹{{amount:.2f}}</b> {to_vip_font('from your referral')} <b>{{full_name}}</b> {to_vip_font('for a paid search today')}. \n{to_vip_font('New balance:')} <b>₹{{new_balance:.2f}}</b>",
        "search_success_message": f"✅ <b>{to_vip_font('Movie Search Complete!')}</b>\n\n{to_vip_font('Your shortlink process is complete. Your referrer has received their payment for today from your search! Find your movie link now')}.",
        "clear_earn_usage": "❌ {to_vip_font('Usage: /clearearn <user_id>')}",
        "clear_earn_success": f"✅ {to_vip_font('Earnings for user')} <b>{{user_id}}</b> {to_vip_font('have been cleared')}.",
        "clear_earn_not_found": f"❌ {to_vip_font('User')} <b>{{user_id}}</b> {to_vip_font('not found')}.",
        "check_stats_usage": "❌ {to_vip_font('Usage: /checkstats <user_id>')}",
        "check_stats_message": f"📊 <b>{to_vip_font('User Stats')}</b>\n\n{to_vip_font('ID:')} <b>{{user_id}}</b>\n{to_vip_font('Earnings:')} <b>₹{{earnings:.2f}}</b>\n{to_vip_font('Referrals:')} <b>{{referrals}}</b>",
        "check_stats_not_found": f"❌ {to_vip_font('User')} <b>{{user_id}}</b> {to_vip_font('not found')}.",
        "stats_message": f"📈 <b>{to_vip_font('Bot Stats')}</b>\n\n{to_vip_font('Total Users:')} <b>{{total_users}}</b>\n{to_vip_font('Approved Users:')} <b>{{approved_users}}</b>",
        "channel_bonus_claimed": f"✅ <b>{to_vip_font('Channel Join Bonus!')}</b>\n{to_vip_font('You have successfully claimed')} <b>₹{{amount:.2f}}</b> {to_vip_font('for joining')} {{channel}}.\n{to_vip_font('New balance:')} <b>₹{{new_balance:.2f}}</b>",
        "channel_not_joined": "❌ <b>{to_vip_font('Channel Not Joined!')}</b>\n{to_vip_font('You must join our channel')} {{channel}} {to_vip_font('to claim the bonus')}.",
        "channel_already_claimed": "⏳ <b>{to_vip_font('Bonus Already Claimed!')}</b>\n{to_vip_font('You have already claimed the channel join bonus')}.",
        "channel_bonus_failure": "❌ <b>{to_vip_font('Channel Not Joined!')}</b>\n{to_vip_font('You must join our channel')} {{channel}} {to_vip_font('to claim the bonus')}.",
        "top_users_title": f"🏆 <b>{to_vip_font('Top 10 Total Earners')}</b> 🏆\n\n({to_vip_font('This is different from the Monthly Leaderboard')})\n\n",
        "clear_junk_success": f"✅ <b>{to_vip_font('Junk Data Cleared!')}</b>\n\n{to_vip_font('Users deleted:')} <b>{{users}}</b>\n{to_vip_font('Referral records cleared:')} <b>{{referrals}}</b>\n{to_vip_font('Withdrawals cleared:')} <b>{{withdrawals}}</b>",
        "clear_junk_admin_only": "❌ {to_vip_font('This command is for the bot admin only')}.",
        "tier_benefits_title": f"👑 <b>{to_vip_font('Tier System Benefits')}</b> 👑\n\n{to_vip_font('Your earning rate increases as you earn more. Reach higher tiers for more money per referral!')}",
        "tier_info": "🔸 <b>{to_vip_font('{tier_name}')} (Level {tier}):</b> {to_vip_font('Min Earning: <b>₹{min_earnings:.2f}</b>')}\n   - {to_vip_font('Benefit:')} {benefit}",
        "tier_benefits_message": f"👑 <b>{to_vip_font('Tier System Benefits')}</b> 👑\n\n{to_vip_font('Your earning rate increases as you earn more. Reach higher tiers for more money per referral!')}\n\n<b>{to_vip_font('Tier 1: Beginner')}</b> ({to_vip_font('Min Earning: <b>₹0.00</b>, Rate: <b>₹0.20</b>')})\n<b>{to_vip_font('Tier 2: Pro')}</b> ({to_vip_font('Min Earning: <b>₹200.00</b>, Rate: <b>₹0.35</b>')})\n<b>{to_vip_font('Tier 3: Expert')}</b> ({to_vip_font('Min Earning: <b>₹500.00</b>, Rate: <b>₹0.45</b>')})\n<b>{to_vip_font('Tier 4: Master')}</b> ({to_vip_font('Min Earning: <b>₹1000.00</b>, Rate: <b>₹0.50</b>')})",
        "help_menu_title": "🆘 <b>{to_vip_font('Help & Support')}</b>",
        "help_menu_text": "{to_vip_font('If you have any questions, payment issues, or need to contact the admin, use the button below. Remember to read the \\'How to Earn\\' (Referral Example) section first!')}",
        "help_message": f"🆘 <b>{to_vip_font('Help & Support')}</b>\n\n{to_vip_font('If you have any questions or payment issues, please contact the admin directly:')} <b>@{YOUR_TELEGRAM_HANDLE}</b>\n\n{to_vip_font('Tip: Read the \\'Referral Example\\' in the Earning Panel first!')}!",
        "alert_daily_bonus": f"🔔 <b>{to_vip_font('Reminder!')}</b>\n\n{to_vip_font('Hey there, you haven\\'t claimed your')} 🎁 <b>{to_vip_font('Daily Bonus')}</b> {to_vip_font('yet! Don\\'t miss out on free money. Go to the Earning Panel now!')}",
        "alert_mission": f"🎯 <b>{to_vip_font('Mission Alert!')}</b>\n\n{to_vip_font('Your')} <b>{to_vip_font('Daily Missions')}</b> {to_vip_font('are waiting! Complete them to earn extra cash today. Need help? Refer a friend and complete the \\'Search 3 Movies\\' mission!')}",
        "alert_refer": f"🔗 <b>{to_vip_font('Huge Earning Opportunity!')}</b>\n\n{to_vip_font('Your friends are missing out on the best movie bot! Share your referral link now and earn up to')} <b>₹{{max_rate:.2f}}</b> {to_vip_font('per person daily!')}",
        "alert_spin": f"🎰 <b>{to_vip_font('Free Spin Alert!')}</b>\n\n{to_vip_font('Do you have a free spin left? Spin the wheel now for a chance to win up to <b>₹2.00</b>! Refer a friend to get more spins!')}",
        "join_channel_button_text": "Join Channel & Try Again",
        "admin_user_stats_prompt": "✍️ {to_vip_font('Please reply to this message with the User ID you want to check:')}",
        "admin_add_money_prompt": f"💰 {to_vip_font('Please reply with the amount (in INR, e.g., 10.50) you want to add to user')} <b>{{user_id}}</b>:",
        "admin_clear_data_prompt": f"⚠️ {to_vip_font('Are you sure?')}\n{to_vip_font('To clear <b>only earnings</b>, reply with:')} <b>`earning`</b>\n{to_vip_font('To delete <b>all user data</b>, reply with:')} <b>`all`</b>",
        "admin_user_not_found": f"❌ {to_vip_font('User')} <b>{{user_id}}</b> {to_vip_font('not found in the database')}.",
        "admin_add_money_success": f"✅ {to_vip_font('Successfully added')} <b>₹{{amount:.2f}}</b> {to_vip_font('to user')} <b>{{user_id}}</b>. {to_vip_font('New balance:')} <b>₹{{new_balance:.2f}}</b>",
        "admin_clear_earnings_success": f"✅ {to_vip_font('Successfully cleared earnings for user')} <b>{{user_id}}</b>. {to_vip_font('New balance: <b>₹0.00</b>')}",
        "admin_delete_user_success": f"✅ {to_vip_font('Successfully deleted all data for user')} <b>{{user_id}}</b>.",
        "admin_invalid_input": "❌ {to_vip_font('Invalid input. Please try again')}.",
        "leaderboard_title": f"🏆 <b>{to_vip_font('Monthly Leaderboard')}</b> 🏆\n\n{to_vip_font('Top 10 referrers of the month!')}",
        "leaderboard_rank_entry": "   - <b>{to_vip_font('Monthly Referrals:')}</b> {{monthly_refs}}\n   - <b>{to_vip_font('Total Balance:')}</b> ₹{{balance:.2f}}\n",
        "monthly_reward_notification": f"🎉 <b>{to_vip_font('Leaderboard Reward!')}</b> 🎉\n\n{to_vip_font('Congratulations! You finished at')} <b>{to_vip_font('Rank')} #{{rank}}</b> {to_vip_font('on the monthly leaderboard')}.\n\n{to_vip_font('You have been awarded:')} <b>₹{{reward:.2f}}</b>\n\n{to_vip_font('Your new balance is:')} <b>₹{{new_balance:.2f}}</b>",
        "channel_bonus_error": f"❌ <b>{to_vip_font('Verification Failed!')}</b>\n\n{to_vip_font('We could not verify your membership. Please ensure you have joined the channel')} ({{channel}}) {to_vip_font('and try again in a moment')}.\n\n{to_vip_font('If this problem continues, the admin has been notified')}.",
    },
    "hi": {
        "start_greeting": f"नमस्ते 👋! {to_vip_font('मूवी ग्रुप बॉट में आपका स्वागत है')}। {to_vip_font('इन आसान स्टेप्स को फॉलो करके अपनी पसंदीदा मूवी पाएँ')}:",
        "start_step1": "✨ {to_vip_font('हमारे मूवी ग्रुप में शामिल होने के लिए नीचे दिए गए बटन पर क्लिक करें')}।",
        "start_step2": "🎬 {to_vip_font('ग्रुप में जाकर अपनी मनपसंद मूवी का नाम लिखें')}।",
        "start_step3": "🔗 {to_vip_font('बॉट आपको आपकी मूवी की लिंक देगा')}।",
        "language_choice": "🌐 {to_vip_font('अपनी भाषा चुनें')}:",
        "language_selected": "✅ {to_vip_font('भाषा हिंदी में बदल दी गई है')}।",
        "language_prompt": "✍️ {to_vip_font('कृपया अपनी भाषा चुनें')}:",
        "help_message_text": f"<b>🤝 {to_vip_font('पैसे कैसे कमाएं')}</b>\n\n1️⃣ <b>{to_vip_font('अपनी लिंक पाएं')}:</b> {to_vip_font("My Refer Link' बटन का उपयोग करके अपनी रेफरल लिंक पाएं")}।\n\n2️⃣ <b>{to_vip_font('शेयर करें')}:</b> {to_vip_font('इस लिंक को अपने दोस्तों के साथ शेयर करें। उन्हें बॉट शुरू करने और हमारे मूवी ग्रुप में शामिल होने के लिए कहें')}।\n\n3️⃣ <b>{to_vip_font('कमाई करें')}:</b> {to_vip_font('जब आपका रेफर किया गया दोस्त ग्रुप में कोई मूवी खोजता है और शॉर्टलिंक प्रक्रिया पूरी करता है, तो आप पैसे कमाते हैं! आप प्रत्येक दोस्त से एक दिन में 3 बार तक कमाई कर सकते हैं')}।",
        "refer_example_message": f"<b>💡 {to_vip_font('रेफरल उदाहरण / पैसे कैसे कमाएं')}</b>\n\n1. {to_vip_font('अपनी लिंक दोस्तों के साथ साझा करें')}।\n2. {to_vip_font('वे बॉट शुरू करते हैं और मूवी ग्रुप में शामिल होते हैं')}।\n3. {to_vip_font('वे ग्रुप में <b>3 फिल्में</b> खोजते हैं (या अधिक)')}।\n4. {to_vip_font('आपको उस दोस्त से <b>3 खोज/दिन</b> के लिए भुगतान मिलता है! ₹{rate} प्रति रेफरल/दिन')}।",
        "withdrawal_details_message": f"💸 <b>{to_vip_font('निकासी का विवरण')}</b>\n\n{to_vip_font('आपका वर्तमान बैलेंस')} <b>₹{{balance}}</b> {to_vip_font('है। जब आपका बैलेंस <b>₹80</b> या उससे अधिक हो जाए, तो आप निकासी कर सकते हैं')}।\n\n{to_vip_font('निकासी का अनुरोध करने के लिए नीचे दिए गए बटन पर क्लिक करें')}।",
        "earning_panel_message": f"💰 <b>{to_vip_font('कमाई का पैनल')}</b>\n\n{to_vip_font('यहाँ आप अपनी कमाई से जुड़ी सभी गतिविधियाँ मैनेज कर सकते हैं')}।",
        "daily_bonus_success": f"🎉 <b>{to_vip_font('दैनिक बोनस क्लेम किया गया!')}</b>\n{to_vip_font('आपने सफलतापूर्वक अपना दैनिक बोनस')} <b>₹{{bonus_amount:.2f}}</b> {to_vip_font('क्लेम कर लिया है। आपका नया बैलेंस')} <b>₹{{new_balance:.2f}}</b> {to_vip_font('है')}।\n\n{{streak_message}}",
        "daily_bonus_already_claimed": f"⏳ <b>{to_vip_font('बोनस पहले ही क्लेम किया जा चुका है!')}</b>\n{to_vip_font('आपने आज का बोनस पहले ही क्लेम कर लिया है। कल फिर कोशिश करें!')}",
        "admin_panel_title": f"⚙️ <b>{to_vip_font('एडमिन पैनल')}</b>\n\n{to_vip_font('यहाँ से बॉट की सेटिंग्स और यूज़र्स को मैनेज करें')}।",
        "setrate_success": f"✅ {to_vip_font('Tier 1 रेफरल कमाई की दर')} <b>₹{{new_rate:.2f}}</b> {to_vip_font('पर अपडेट हो गई है')}।",
        "setrate_usage": "❌ {to_vip_font('उपयोग: /setrate <नई_राशि_रुपये_में>')}",
        "invalid_rate": "❌ {to_vip_font('अमान्य राशि। कृपया एक संख्या दर्ज करें')}।",
        "referral_rate_updated": f"⭐ {to_vip_font('नई Tier 1 रेफरल दर अब')} <b>₹{{new_rate:.2f}}</b> {to_vip_font('है')}।",
        "broadcast_admin_only": "❌ {to_vip_font('यह कमांड केवल बॉट एडमिन के लिए है')}।",
        "broadcast_message": "📢 {to_vip_font('सभी उपयोगकर्ताओं को संदेश भेजने के लिए कृपया किसी संदेश का /broadcast के साथ उत्तर दें')}।",
        "setwelbonus_usage": "❌ {to_vip_font('उपयोग: /setwelbonus <राशि_रुपये_में>')}",
        "setwelbonus_success": f"✅ {to_vip_font('वेलकम बोनस')} <b>₹{{new_bonus:.2f}}</b> {to_vip_font('पर अपडेट हो गया है')}।",
        "welcome_bonus_received": f"🎁 <b>{to_vip_font('वेलकम बोनस!')}</b>\n\n{to_vip_font('आपको')} <b>₹{{amount:.2f}}</b> {to_vip_font('वेलकम बोनस मिला है! दोस्तों को रेफर करके और कमाएँ')}।",
        "spin_wheel_title": f"🎡 <b>{to_vip_font('व्हील स्पिन करें - मुफ्त कमाई!')}</b>\n\n{to_vip_font('बची हुई स्पिनें:')} <b>{{spins_left}}</b>\n\n<b>{to_vip_font('और स्पिन कैसे पाएं:')}</b>\n🔗 {to_vip_font('1 नए यूज़र को रेफ़र करें और 1 फ्री स्पिन पाएं!')}",
        "spin_wheel_button": "✨ {to_vip_font('अभी स्पिन करें')} ({{spins_left}} {to_vip_font('शेष')})",
        "spin_wheel_animating": "🍀 <b>{to_vip_font('स्पिन हो रहा है...')}</b>\n\n{to_vip_font('परिणाम का इंतजार करें!')} ⏳",
        "spin_wheel_insufficient_spins": "❌ <b>{to_vip_font('कोई स्पिन बाकी नहीं!')}</b>\n\n{to_vip_font('एक और फ्री स्पिन पाने के लिए 1 नए यूज़र को रेफ़र करें!')}",
        "spin_wheel_win": f"🎉 <b>{to_vip_font('बधाई हो!')}</b>\n\n{to_vip_font('आपने जीता:')} <b>₹{{amount:.2f}}!</b>\n\n{to_vip_font('नया बैलेंस:')} <b>₹{{new_balance:.2f}}</b>\n\n{to_vip_font('बची हुई स्पिनें:')} <b>{{spins_left}}</b>",
        "spin_wheel_lose": f"😢 <b>{to_vip_font('अगली बार बेहतर किस्मत!')}</b>\n\n{to_vip_font('इस बार आप कुछ नहीं जीत पाए')}।\n\n{to_vip_font('शेष बैलेंस:')} <b>₹{{new_balance:.2f}}</b>\n\n{to_vip_font('बची हुई स्पिनें:')} <b>{{spins_left}}</b>",
        "missions_title": f"🎯 <b>{to_vip_font('दैनिक मिशन')}</b>\n\n{to_vip_font('अतिरिक्त इनाम पाने के लिए मिशन पूरे करें! अपनी प्रगति नीचे देखें')}ः",
        "mission_search_note": "⏳ {to_vip_font('3 फिल्में खोजें (भुगतान प्राप्त)')} ({{current}}/{{target}}) [<b>{to_vip_font('प्रगति में')}</b>]\n\n<b>{to_vip_font('ध्यान दें')}ः</b> {to_vip_font('यह मिशन तब पूरा होता है जब आपको आज आपके रेफर किए गए यूज़र्स से 3 बार भुगतान मिलता है')}।",
        "mission_search_progress": "⏳ {to_vip_font('3 फिल्में खोजें')} ({{current}}/{{target}}) [<b>{to_vip_font('प्रगति में')}</b>]",
        "mission_complete": f"✅ <b>{to_vip_font('मिशन पूरा हुआ!')}</b>\n\n{to_vip_font('आपने')} {{mission_name}} {to_vip_font('के लिए')} <b>₹{{reward:.2f}}</b> {to_vip_font('कमाए')}!\n{to_vip_font('नया बैलेंस:')} <b>₹{{new_balance:.2f}}</b>",
        "withdrawal_request_sent": f"✅ <b>{to_vip_font('निकासी का अनुरोध भेज दिया गया!')}</b>\n\n{to_vip_font('₹{{amount:.2f}} के आपके अनुरोध को एडमिन को भेज दिया गया है। आपको 24 घंटे के भीतर भुगतान मिल जाएगा')}।",
        "withdrawal_insufficient": "❌ <b>{to_vip_font('पर्याप्त बैलेंस नहीं!')}</b>\n\n{to_vip_font('न्यूनतम निकासी राशि')} <b>₹80.00</b> {to_vip_font('है')}",
        "withdrawal_approved_user": f"✅ <b>{to_vip_font('निकासी स्वीकृत!')}</b>\n\n{to_vip_font('₹{{amount:.2f}} की आपकी निकासी स्वीकृत कर दी गई है। भुगतान 24 घंटे के भीतर प्रोसेस किया जाएगा')}।",
        "withdrawal_rejected_user": f"❌ <b>{to_vip_font('निकासी अस्वीकृत!')}</b>\n\n{to_vip_font('₹{{amount:.2f}} की आपकी निकासी अस्वीकृत कर दी गई है। विवरण के लिए एडमिन से संपर्क करें')}।",
        "ref_link_message": f"🔗 <b>{to_vip_font('आपकी रेफरल लिंक:')}</b>\n<b>{{referral_link}}</b>\n\n💰 <b>{to_vip_font('वर्तमान रेफरल दर:')}</b> <b>₹{{tier_rate:.2f}}</b> {to_vip_font('प्रति रेफरल')}\n\n<i>{to_vip_font('इस लिंक को दोस्तों के साथ साझा करें और जब वे शामिल होकर फिल्में खोजते हैं, तो पैसे कमाएं!')}</i>",
        "new_referral_notification": f"🎉 <b>{to_vip_font('नया रेफरल!')}</b>\n\n<b>{{full_name}}</b> ({{username}}) {to_vip_font('आपकी लिंक का उपयोग करके शामिल हुए हैं')}!\n\n💰 {to_vip_font('आपको जॉइनिंग बोनस')} <b>₹{{bonus:.2f}}</b> {to_vip_font('मिला')}!\n\n🎰 {to_vip_font('आपको स्पिन व्हील के लिए 1 फ्री स्पिन भी मिली है')}!",
        "daily_earning_update_new": f"💸 <b>{to_vip_font('रोजाना रेफरल कमाई!')}</b>\n\n{to_vip_font('आज एक पेड सर्च के लिए आपने अपने रेफरल')} <b>{{full_name}}</b> {to_vip_font('से')} <b>₹{{amount:.2f}}</b> {to_vip_font('कमाए')}। \n{to_vip_font('नया बैलेंस:')} <b>₹{{new_balance:.2f}}</b>",
        "search_success_message": f"✅ <b>{to_vip_font('मूवी सर्च पूरी!')}</b>\n\n{to_vip_font('आपकी शॉर्टलिंक प्रक्रिया पूरी हो गई है। आपके रेफ़र करने वाले को आपकी खोज के लिए आज का भुगतान मिल गया है! अब अपनी मूवी लिंक ढूंढें')}।",
        "clear_earn_usage": "❌ {to_vip_font('उपयोग: /clearearn <user_id>')}",
        "clear_earn_success": f"✅ {to_vip_font('उपयोगकर्ता')} <b>{{user_id}}</b> {to_vip_font('की कमाई साफ़ कर दी गई है')}।",
        "clear_earn_not_found": f"❌ {to_vip_font('उपयोगकर्ता')} <b>{{user_id}}</b> {to_vip_font('नहीं मिला')}।",
        "check_stats_usage": "❌ {to_vip_font('उपयोग: /checkstats <user_id>')}",
        "check_stats_message": f"📊 <b>{to_vip_font('यूज़र आँकड़े')}</b>\n\n{to_vip_font('ID:')} <b>{{user_id}}</b>\n{to_vip_font('कमाई:')} <b>₹{{earnings:.2f}}</b>\n{to_vip_font('रेफरल:')} <b>{{referrals}}</b>",
        "check_stats_not_found": f"❌ {to_vip_font('उपयोगकर्ता')} <b>{{user_id}}</b> {to_vip_font('नहीं मिला')}।",
        "stats_message": f"📈 <b>{to_vip_font('बॉट आँकड़े')}</b>\n\n{to_vip_font('कुल उपयोगकर्ता:')} <b>{{total_users}}</b>\n{to_vip_font('अनुमोदित उपयोगकर्ता:')} <b>{{approved_users}}</b>",
        "channel_bonus_claimed": f"✅ <b>{to_vip_font('चैनल जॉइन बोनस!')}</b>\n{to_vip_font('आपने सफलतापूर्वक')} {{channel}} {to_vip_font('जॉइन करने के लिए')} <b>₹{{amount:.2f}}</b> {to_vip_font('क्लेम कर लिए हैं')}।\n{to_vip_font('नया बैलेंस:')} <b>₹{{new_balance:.2f}}</b>",
        "channel_not_joined": "❌ <b>{to_vip_font('चैनल जॉइन नहीं किया!')}</b>\n{to_vip_font('बोनस क्लेम करने के लिए आपको हमारा चैनल')} {{channel}} {to_vip_font('जॉइन करना होगा')}।",
        "channel_already_claimed": "⏳ <b>{to_vip_font('बोनस पहले ही क्लेम किया जा चुका है!')}</b>\n{to_vip_font('आप पहले ही चैनल जॉइन बोनस क्लेम कर चुके हैं')}।",
        "channel_bonus_failure": "❌ <b>{to_vip_font('चैनल जॉइन नहीं किया!')}</b>\n{to_vip_font('बोनस क्लेम करने के लिए आपको हमारा चैनल')} {{channel}} {to_vip_font('जॉइन करना होगा')}।",
        "top_users_title": f"🏆 <b>{to_vip_font('शीर्ष 10 कुल कमाने वाले')}</b> 🏆\n\n({to_vip_font('यह मासिक लीडरबोर्ड से अलग है')})\n\n",
        "clear_junk_success": f"✅ <b>{to_vip_font('जंक डेटा साफ़!')}</b>\n\n{to_vip_font('डिलीट किए गए यूज़र्स:')} <b>{{users}}</b>\n{to_vip_font('साफ़ किए गए रेफरल रिकॉर्ड:')} <b>{{referrals}}</b>\n{to_vip_font('साफ़ की गई निकासी:')} <b>{{withdrawals}}</b>",
        "clear_junk_admin_only": "❌ {to_vip_font('यह कमांड केवल बॉट एडमिन के लिए है')}।",
        "tier_benefits_title": f"👑 <b>{to_vip_font('टियर सिस्टम के लाभ')}</b> 👑\n\n{to_vip_font('जैसे-जैसे आप अधिक कमाते हैं, आपकी कमाई दर बढ़ती जाती है। प्रति रेफरल अधिक पैसे के लिए उच्च टियर पर पहुँचें!')}",
        "tier_info": "🔸 <b>{to_vip_font('{tier_name}')} (लेवल {tier}):</b> {to_vip_font('न्यूनतम कमाई: <b>₹{min_earnings:.2f}</b>')}\n   - {to_vip_font('लाभ:')} {benefit}",
        "tier_benefits_message": f"👑 <b>{to_vip_font('टियर सिस्टम के लाभ')}</b> 👑\n\n{to_vip_font('जैसे-जैसे आप अधिक कमाते हैं, आपकी कमाई दर बढ़ती जाती है। प्रति रेफरल अधिक पैसे के लिए उच्च टियर पर पहुँचें!')}\n\n<b>{to_vip_font('टियर 1: शुरुआती')}</b> ({to_vip_font('न्यूनतम कमाई: <b>₹0.00</b>, दर: <b>₹0.20</b>')})\n<b>{to_vip_font('टियर 2: प्रो')}</b> ({to_vip_font('न्यूनतम कमाई: <b>₹200.00</b>, दर: <b>₹0.35</b>')})\n<b>{to_vip_font('टियर 3: एक्सपर्ट')}</b> ({to_vip_font('न्यूनतम कमाई: <b>₹500.00</b>, दर: <b>₹0.45</b>')})\n<b>{to_vip_font('टियर 4: मास्टर')}</b> ({to_vip_font('न्यूनतम कमाई: <b>₹1000.00</b>, दर: <b>₹0.50</b>')})",
        "help_menu_title": "🆘 <b>{to_vip_font('सहायता और समर्थन')}</b>",
        "help_menu_text": "{to_vip_font('यदि आपके कोई प्रश्न हैं, भुगतान संबंधी समस्याएँ हैं, या एडमिन से संपर्क करने की आवश्यकता है, तो नीचे दिए गए बटन का उपयोग करें। \\'पैसे कैसे कमाएं\\' (रेफरल उदाहरण) अनुभाग को पहले पढ़ना याद रखें!')}",
        "help_message": f"🆘 <b>{to_vip_font('सहायता और समर्थन')}</b>\n\n{to_vip_font('यदि आपके कोई प्रश्न या भुगतान संबंधी समस्याएँ हैं, तो कृपया सीधे एडमिन से संपर्क करें:')} <b>@{YOUR_TELEGRAM_HANDLE}</b>\n\n{to_vip_font('टिप: पहले कमाई पैनल में \\'रेफरल उदाहरण\\' पढ़ें!')}!",
        "alert_daily_bonus": f"🔔 <b>{to_vip_font('याद दिलाना!')}</b>\n\n{to_vip_font('अरे, आपने अभी तक अपना')} 🎁 <b>{to_vip_font('दैनिक बोनस')}</b> {to_vip_font('क्लेम नहीं किया है! मुफ्त पैसे गँवाएं नहीं। अभी कमाई पैनल पर जाएँ!')}",
        "alert_mission": f"🎯 <b>{to_vip_font('मिशन अलर्ट!')}</b>\n\n{to_vip_font('आपके')} <b>{to_vip_font('दैनिक मिशन')}</b> {to_vip_font('आपका इंतज़ार कर रहे हैं! आज ही अतिरिक्त नकद कमाने के लिए उन्हें पूरा करें। मदद चाहिए? एक दोस्त को रेफ़र करें और \\'3 फिल्में खोजें\\' मिशन पूरा करें!')}",
        "alert_refer": f"🔗 <b>{to_vip_font('बड़ी कमाई का मौका!')}</b>\n\n{to_vip_font('आपके दोस्त सबसे अच्छे मूवी बॉट से चूक रहे हैं! अपनी रेफरल लिंक अभी साझा करें और प्रति व्यक्ति रोज़ाना')} <b>₹{{max_rate:.2f}}</b> {to_vip_font('तक कमाएँ!')}",
        "alert_spin": f"🎰 <b>{to_vip_font('फ्री स्पिन अलर्ट!')}</b>\n\n{to_vip_font('क्या आपके पास कोई फ्री स्पिन बची है? <b>₹2.00</b> तक जीतने के मौका पाने के लिए अभी व्हील स्पिन करें! अधिक स्पिन पाने के लिए एक दोस्त को रेफ़र करें!')}",
        "join_channel_button_text": "चैनल जॉइन करें और फिर कोशिश करें",
        "admin_user_stats_prompt": "✍️ {to_vip_font('कृपया जिस यूज़र की जांच करनी है, उसकी User ID इस मैसेज के रिप्लाई में भेजें:')}",
        "admin_add_money_prompt": f"💰 {to_vip_font('कृपया वह राशि (INR में, जैसे: 10.50) रिप्लाई में भेजें जो आप यूज़र')} <b>{{user_id}}</b> {to_vip_font('को देना चाहते हैं:')}",
        "admin_clear_data_prompt": f"⚠️ {to_vip_font('क्या आप निश्चित हैं?')}\n{to_vip_font('केवल <b>कमाई (earnings)</b> साफ़ करने के लिए, रिप्लाई करें:')} <b>`earning`</b>\n{to_vip_font('यूज़र का <b>सारा डेटा</b> डिलीट करने के लिए, रिप्लाई करें:')} <b>`all`</b>",
        "admin_user_not_found": f"❌ {to_vip_font('यूज़र')} <b>{{user_id}}</b> {to_vip_font('डेटाबेस में नहीं मिला')}।",
        "admin_add_money_success": f"✅ {to_vip_font('यूज़र')} <b>{{user_id}}</b> {to_vip_font('को')} <b>₹{{amount:.2f}}</b> {to_vip_font('सफलतापूर्वक जोड़ दिए गए। नया बैलेंस:')} <b>₹{{new_balance:.2f}}</b>",
        "admin_clear_earnings_success": f"✅ {to_vip_font('यूज़र')} <b>{{user_id}}</b> {to_vip_font('की कमाई सफलतापूर्वक साफ़ कर दी गई। नया बैलेंस: <b>₹0.00</b>')}",
        "admin_delete_user_success": f"✅ {to_vip_font('यूज़र')} <b>{{user_id}}</b> {to_vip_font('का सारा डेटा सफलतापूर्वक डिलीट कर दिया गया')}।",
        "admin_invalid_input": "❌ {to_vip_font('अमान्य इनपुट। कृपया पुनः प्रयास करें')}।",
        "leaderboard_title": f"🏆 <b>{to_vip_font('मासिक लीडरबोर्ड')}</b> 🏆\n\n{to_vip_font('इस महीने के टॉप 10 रेफरर!')}",
        "leaderboard_rank_entry": "   - <b>{to_vip_font('मासिक रेफरल:')}</b> {{monthly_refs}}\n   - <b>{to_vip_font('कुल बैलेंस:')}</b> ₹{{balance:.2f}}\n",
        "monthly_reward_notification": f"🎉 <b>{to_vip_font('लीडरबोर्ड इनाम!')}</b> 🎉\n\n{to_vip_font('बधाई हो! आपने मासिक लीडरबोर्ड पर')} <b>{to_vip_font('रैंक')} #{{rank}}</b> {to_vip_font('हासिल किया है')}।\n\n{to_vip_font('आपको')} <b>₹{{reward:.2f}}</b> {to_vip_font('का इनाम दिया गया है')}।\n\n{to_vip_font('आपका नया बैलेंस है:')} <b>₹{{new_balance:.2f}}</b>",
        "channel_bonus_error": f"❌ <b>{to_vip_font('सत्यापन विफल!')}</b>\n\n{to_vip_font('हम आपकी सदस्यता को सत्यापित नहीं कर सके। कृपया सुनिश्चित करें कि आप चैनल')} ({{channel}}) {to_vip_font('से जुड़ गए हैं और कुछ देर बाद पुनः प्रयास करें')}।\n\n{to_vip_font('यदि यह समस्या बनी रहती है, तो एडमिन को सूचित कर दिया गया है')}।",
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
