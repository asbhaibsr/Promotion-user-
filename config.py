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
# ✅ ERROR FIX: Inline Keyboard URL के लिए Markdown फॉर्मेट को सादे URL से बदल दिया गया।
# यह टेलीग्राम बॉट की Inline Keyboard Bad Request एरर को ठीक करता है।
NEW_MOVIE_GROUP_LINK = "https://t.me/asfilter_bot"
MOVIE_GROUP_LINK = "https://t.me/asfilter_group" 
ALL_GROUPS_LINK = "https://t.me/addlist/6urdhhdLRqhiZmQ1"

EXAMPLE_SCREENSHOT_URL = os.getenv("EXAMPLE_SCREENSHOT_URL", "https://envs.sh/v3A.jpg")

# --- चैनल बोनस सेटिंग्स ---
CHANNEL_USERNAME = "@asbhai_bsr"
CHANNEL_ID = -1002283182645
CHANNEL_BONUS = 2.00  # नया: चैनल जॉइन बोनस को ₹5.00 से घटाकर ₹2.00 किया गया
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
# 'STREAK_MULTIPLIER' से 'STREAK' हटाकर 'DAILY_BONUS_MULTIPLIER' किया गया
DAILY_BONUS_MULTIPLIER = 0.10 

# ✅ ERROR FIX: पुरानी इम्पोर्ट त्रुटि को ठीक करने के लिए
# यह वेरिएबल अब आपके कोड के पुराने हिस्से (जैसे db_utils) द्वारा
# अपेक्षित है, इसलिए इसे DAILY_BONUS_MULTIPLIER के बराबर सेट किया गया है।
DAILY_BONUS_STREAK_MULTIPLIER = DAILY_BONUS_MULTIPLIER 

# --- स्पिन व्हील सेटिंग्स ---
# 'SPIN_PRIZES_WEIGHTS' नाम सही किया गया, 'SPIN_PRIZES_WEIGHTS' में से 'SPIN' हटाया गया
PRIZES_WEIGHTS = {
    0.00: 4,  # जीतने की संभावना सबसे ज़्यादा
    0.10: 3,
    0.20: 3,
    0.50: 2,
    1.00: 1,  # बड़ा इनाम, कम संभावना
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
    # दरें कम रखी गईं ताकि आपको ₹0.54 प्रति क्लिक पर फायदा हो
    1: {"min_earnings": 0, "rate": 0.20, "name": "Beginner", "benefits_en": "Basic referral rate (₹0.20)", "benefits_hi": "सामान्य रेफरल दर (₹0.20)"},
    2: {"min_earnings": 200, "rate": 0.35, "name": "Pro", "benefits_en": "Higher referral rate (₹0.35)", "benefits_hi": "उच्च रेफरल दर (₹0.35)"},
    3: {"min_earnings": 500, "rate": 0.45, "name": "Expert", "benefits_en": "Very high referral rate (₹0.45)", "benefits_hi": "बहुत उच्च रेफरल दर (₹0.45)"},
    4: {"min_earnings": 1000, "rate": 0.50, "name": "Master", "benefits_en": "Maximum referral rate (₹0.50)", "benefits_hi": "अधिकतम रेफरल दर (₹0.50)"}
}

# --- डेली मिशन सेटिंग्स ---
DAILY_MISSIONS = {
    # 0.60 को घटाकर 0.50 किया गया ताकि यह ₹0.54 प्रति क्लिक से कम रहे।
    "search_3_movies": {"reward": 0.50, "target": 3, "name": "Search 3 Movies (Ref. Paid Search)", "name_hi": "3 फिल्में खोजें (रेफ़रल का भुगतान)"}, 
    "refer_2_friends": {"reward": 1.40, "target": 2, "name": "Refer 2 Friends", "name_hi": "2 दोस्तों को रेफ़र करें"},
    "claim_daily_bonus": {"reward": 0.10, "target": 1, "name": "Claim Daily Bonus", "name_hi": "दैनिक बोनस क्लेम करें"}
}

# --- Messages and Text ---
MESSAGES = {
    "en": {
        "start_greeting": "Hey 👋! Welcome to the Movies Group Bot. Get your favorite movies by following these simple steps:",
        "start_step1": "Click the button below to join our movie group.",
        "start_step2": "Go to the group and type the name of the movie you want.",
        "start_step3": "The bot will give you a link to your movie.",
        "language_choice": "Choose your language:",
        "language_selected": "Language changed to English.",
        "language_prompt": "Please select your language:",
        "help_message_text": "🤝 How to Earn Money\n\n1️⃣ Get Your Link: Use the 'My Refer Link' button to get your unique referral link.\n\n2️⃣ Share Your Link: Share this link with your friends. Tell them to start the bot and join our movie group.\n\n3️⃣ Earn: When a referred friend searches for a movie in the group and completes the shortlink process, you earn money! You can earn from each friend up to 3 times per day.",
        "refer_example_message": "💡 Referral Example / How to Earn\n\n1. Share your link with friends.\n2. They start the bot and join the movie group.\n3. They search for 3 movies in the group (or more).\n4. You get paid for 3 searches/day from that friend! ₹{rate} per referral/day.",
        "withdrawal_details_message": "💸 Withdrawal Details\n\nYour current balance is {balance}. You can withdraw when your balance reaches ₹80 or more.\n\nClick the button below to request withdrawal.",
        "earning_panel_message": "💰 Earning Panel\n\nManage all your earning activities here.",
        "daily_bonus_success": "🎉 Daily Bonus Claimed!\nYou have successfully claimed your daily bonus of ₹{bonus_amount:.2f}. Your new balance is ₹{new_balance:.2f}.\n\n{streak_message}",
        "daily_bonus_already_claimed": "⏳ Bonus Already Claimed!\nYou have already claimed your bonus for today. Try again tomorrow!",
        "admin_panel_title": "⚙️ Admin Panel\n\nManage bot settings and users from here.",
        "setrate_success": "✅ Tier 1 Referral earning rate has been updated to ₹{new_rate:.2f}.",
        "setrate_usage": "❌ Usage: /setrate <new_rate_in_inr>",
        "invalid_rate": "❌ Invalid rate. Please enter a number.",
        "referral_rate_updated": "The new Tier 1 referral rate is now ₹{new_rate:.2f}.",
        "broadcast_admin_only": "❌ This command is for the bot admin only.",
        "broadcast_message": "Please reply to a message with /broadcast to send it to all users.", # Formatting tags removed
        "setwelbonus_usage": "❌ Usage: /setwelbonus <amount_in_inr>",
        "setwelbonus_success": "✅ Welcome bonus updated to ₹{new_bonus:.2f}",
        "welcome_bonus_received": "🎁 Welcome Bonus!\n\nYou have received ₹{amount:.2f} welcome bonus! Start earning more by referring friends.",
        "spin_wheel_title": "🎡 Spin the Wheel - Free Earning!\n\nRemaining Spins: {spins_left}\n\nHow to Get More Spins:\nRefer 1 new user to get 1 free spin!",
        "spin_wheel_button": "✨ Spin Now ({spins_left} Left)",
        "spin_wheel_animating": "🎡 Spinning...\n\nWait for the result! 🍀",
        "spin_wheel_insufficient_spins": "❌ No Spins Left!\n\nYou need to refer 1 new user to get another free spin!",
        "spin_wheel_win": "🎉 Congratulations!\n\nYou won: ₹{amount:.2f}!\n\nNew balance: ₹{new_balance:.2f}\n\nRemaining Spins: {spins_left}",
        "spin_wheel_lose": "😢 Better luck next time!\n\nYou didn't win anything this time.\n\nRemaining balance: ₹{new_balance:.2f}\n\nRemaining Spins: {spins_left}",
        "missions_title": "🎯 Daily Missions\n\nComplete missions to earn extra rewards! Check your progress below:",
        "mission_search_note": "⏳ Search 3 Movies (Paid Search) ({current}/{target}) [In Progress]\n\nNote: This mission is completed when you receive payment from your referred users 3 times today.",
        "mission_search_progress": "⏳ Search 3 Movies ({current}/{target}) [In Progress]",
        "mission_complete": "✅ Mission Completed!\n\nYou earned ₹{reward:.2f} for {mission_name}!\nNew balance: ₹{new_balance:.2f}",
        "withdrawal_request_sent": "✅ Withdrawal Request Sent!\n\nYour request for ₹{amount:.2f} has been sent to admin. You will receive payment within 24 hours.",
        "withdrawal_insufficient": "❌ Insufficient Balance!\n\nMinimum withdrawal amount is ₹80.00",
        "withdrawal_approved_user": "✅ Withdrawal Approved!\n\nYour withdrawal of ₹{amount:.2f} has been approved. Payment will be processed within 24 hours.",
        "withdrawal_rejected_user": "❌ Withdrawal Rejected!\n\nYour withdrawal of ₹{amount:.2f} was rejected. Please contact admin for details.",
        "ref_link_message": "Your Referral Link:\n{referral_link}\n\nCurrent Referral Rate: ₹{tier_rate:.2f} per referral\n\nShare this link with friends and earn money when they join and search for movies!", # Formatting tags removed
        "new_referral_notification": "🎉 New Referral!\n\n{full_name} ({username}) has joined using your link!\n\n💰 You received a joining bonus of ₹{bonus:.2f}!\n\n🎰 You also earned 1 Free Spin for the Spin Wheel!",
        "daily_earning_update_new": "💰 Daily Referral Earning!\n\nYou earned ₹{amount:.2f} from your referral {full_name} for a paid search today. \nNew balance: ₹{new_balance:.2f}",
        "search_success_message": "✅ Movie Search Complete!\n\nYour shortlink process is complete. Your referrer has received their payment for today from your search! Find your movie link now.",
        "clear_earn_usage": "❌ Usage: /clearearn <user_id>",
        "clear_earn_success": "✅ Earnings for user {user_id} have been cleared.",
        "clear_earn_not_found": "❌ User {user_id} not found.",
        "check_stats_usage": "❌ Usage: /checkstats <user_id>",
        "check_stats_message": "📊 User Stats\n\nID: {user_id}\nEarnings: ₹{earnings:.2f}\nReferrals: {referrals}", # Formatting tags removed
        "check_stats_not_found": "❌ User {user_id} not found.",
        "stats_message": "📊 Bot Stats\n\nTotal Users: {total_users}\nApproved Users: {approved_users}",
        "channel_bonus_claimed": "✅ Channel Join Bonus!\nYou have successfully claimed ₹{amount:.2f} for joining {channel}.\nNew balance: ₹{new_balance:.2f}",
        "channel_not_joined": "❌ Channel Not Joined!\nYou must join our channel {channel} to claim the bonus.",
        "channel_already_claimed": "⏳ Bonus Already Claimed!\nYou have already claimed the channel join bonus.",
        "channel_bonus_failure": "❌ Channel Not Joined!\nYou must join our channel {channel} to claim the bonus.",
        
        # --- MESSAGES Dictionay में बदलाव ---
        # 1. "top_users_title" को बदला गया
        "top_users_title": "🏆 Top 10 Total Earners 🏆\n\n(This is different from the Monthly Leaderboard)\n\n",
        # 2. "clear_junk_success" को बदला गया
        "clear_junk_success": "✅ Junk Data Cleared!\n\nUsers deleted: {users}\nReferral records cleared: {referrals}\nWithdrawals cleared: {withdrawals}",
        
        "clear_junk_admin_only": "❌ This command is for the bot admin only.",
        "tier_benefits_title": "👑 Tier System Benefits 👑\n\nYour earning rate increases as you earn more. Reach higher tiers for more money per referral!",
        "tier_info": "🔸 {tier_name} (Level {tier}): Min Earning: ₹{min_earnings:.2f}\n   - Benefit: {benefit}",
        
        # TIERS Dictionay से मेल खाने के लिए हार्डकोडेड मैसेज को अपडेट किया गया
        "tier_benefits_message": "👑 Tier System Benefits 👑\n\nYour earning rate increases as you earn more. Reach higher tiers for more money per referral!\n\nTier 1: Beginner (Min Earning: ₹0.00, Rate: ₹0.20)\nTier 2: Pro (Min Earning: ₹200.00, Rate: ₹0.35)\nTier 3: Expert (Min Earning: ₹500.00, Rate: ₹0.45)\nTier 4: Master (Min Earning: ₹1000.00, Rate: ₹0.50)",
        
        "help_menu_title": "🆘 Help & Support",
        "help_menu_text": "If you have any questions, payment issues, or need to contact the admin, use the button below. Remember to read the 'How to Earn' (Referral Example) section first!",
        "help_message": "🆘 Help & Support\n\nIf you have any questions or payment issues, please contact the admin directly: @{telegram_handle}\n\nTip: Read the 'Referral Example' in the Earning Panel first!",
        "alert_daily_bonus": "🔔 Reminder!\n\nHey there, you haven't claimed your 🎁 Daily Bonus yet! Don't miss out on free money. Go to the Earning Panel now!",
        "alert_mission": "🎯 Mission Alert!\n\nYour Daily Missions are waiting! Complete them to earn extra cash today. Need help? Refer a friend and complete the 'Search 3 Movies' mission!",
        "alert_refer": "🔗 Huge Earning Opportunity!\n\nYour friends are missing out on the best movie bot! Share your referral link now and earn up to ₹{max_rate:.2f} per person daily!",
        "alert_spin": "🎰 Free Spin Alert!\n\nDo you have a free spin left? Spin the wheel now for a chance to win up to ₹2.00! Refer a friend to get more spins!", # स्पिन प्राइस के अनुसार अपडेट किया गया
        "join_channel_button_text": "Join Channel & Try Again",
        
        # --- ENGLISH (en) MESSAGES (NEW) ---

        # -- ADMIN USER STATS (NEW) --
        "admin_user_stats_prompt": "✍️ Please reply to this message with the User ID you want to check:",
        "admin_add_money_prompt": "💰 Please reply with the amount (in INR, e.g., 10.50) you want to add to user {user_id}:",
        "admin_clear_data_prompt": "⚠️ Are you sure?\nTo clear only earnings, reply with: `earning`\nTo delete all user data, reply with: `all`",
        "admin_user_not_found": "❌ User {user_id} not found in the database.",
        "admin_add_money_success": "✅ Successfully added ₹{amount:.2f} to user {user_id}. New balance: ₹{new_balance:.2f}",
        "admin_clear_earnings_success": "✅ Successfully cleared earnings for user {user_id}. New balance: ₹0.00",
        "admin_delete_user_success": "✅ Successfully deleted all data for user {user_id}.",
        "admin_invalid_input": "❌ Invalid input. Please try again.",

        # -- LEADERBOARD (NEW) --
        "leaderboard_title": "🏆 Monthly Leaderboard 🏆\n\nTop 10 referrers of the month!",
        "leaderboard_rank_entry": "   - Monthly Referrals: {monthly_refs}\n   - Total Balance: ₹{balance:.2f}\n",
        
        # --- YAHAN NAYE MESSAGES ADD KIYE GAYE HAIN ---
        "leaderboard_info_title": "💡 Leaderboard Benefits",
        "leaderboard_info_text": "This leaderboard shows the Top 10 users with the most 'Monthly Referrals'.\n\n🏆 <b>What's the Benefit?</b>\nThe Top 10 users at the end of the month win a cash prize!\n\n💰 <b>How to Get Money?</b>\nOn the 1st of every month, rewards are automatically added to the winners' bot balance.\n\n🎯 <b>What is it For?</b>\nYour rank is based <i>only</i> on the number of new users you refer each month. The user with the most referrals wins!",
        # --- BADLAAV KHATM ---

        "monthly_reward_notification": "🎉 Leaderboard Reward! 🎉\n\nCongratulations! You finished at Rank #{rank} on the monthly leaderboard.\n\nYou have been awarded: ₹{reward:.2f}\n\nYour new balance is: ₹{new_balance:.2f}",

        # -- CHANNEL BONUS FIX (NEW) --
        "channel_bonus_error": "❌ Verification Failed!\n\nWe could not verify your membership. Please ensure you have joined the channel ({channel}) and try again in a moment.\n\nIf this problem continues, the admin has been notified.",
    },
    "hi": {
        "start_greeting": "नमस्ते 👋! मूवी ग्रुप बॉट में आपका स्वागत है। इन आसान स्टेप्स को फॉलो करके अपनी पसंदीदा मूवी पाएँ:",
        "start_step1": "हमारे मूवी ग्रुप में शामिल होने के लिए नीचे दिए गए बटन पर क्लिक करें।",
        "start_step2": "ग्रुप में जाकर अपनी मनपसंद मूवी का नाम लिखें।",
        "start_step3": "बॉट आपको आपकी मूवी की लिंक देगा।",
        "language_choice": "अपनी भाषा चुनें:",
        "language_selected": "भाषा हिंदी में बदल दी गई है।",
        "language_prompt": "कृपया अपनी भाषा चुनें:",
        "help_message_text": "🤝 पैसे कैसे कमाएं\n\n1️⃣ अपनी लिंक पाएं: 'My Refer Link' बटन का उपयोग करके अपनी रेफरल लिंक पाएं।\n\n2️⃣ शेयर करें: इस लिंक को अपने दोस्तों के साथ शेयर करें। उन्हें बॉट शुरू करने और हमारे मूवी ग्रुप में शामिल होने के लिए कहें।\n\n3️⃣ कमाई करें: जब आपका रेफर किया गया दोस्त ग्रुप में कोई मूवी खोजता है और शॉर्टलिंक प्रक्रिया पूरी करता है, तो आप पैसे कमाते हैं! आप प्रत्येक दोस्त से एक दिन में 3 बार तक कमाई कर सकते हैं।",
        "refer_example_message": "💡 रेफरल उदाहरण / पैसे कैसे कमाएं\n\n1. अपनी लिंक दोस्तों के साथ साझा करें।\n2. वे बॉट शुरू करते हैं और मूवी ग्रुप में शामिल होते हैं।\n3. वे ग्रुप में 3 फिल्में खोजते हैं (या अधिक)।\n4. आपको उस दोस्त से 3 खोज/दिन के लिए भुगतान मिलता है! ₹{rate} प्रति रेफरल/दिन।",
        "withdrawal_details_message": "💸 निकासी का विवरण\n\nआपका वर्तमान बैलेंस {balance} है। जब आपका बैलेंस ₹80 या उससे अधिक हो जाए, तो आप निकासी कर सकते हैं।\n\nनिकासी का अनुरोध करने के लिए नीचे दिए गए बटन पर क्लिक करें।",
        "earning_panel_message": "💰 कमाई का पैनल\n\nयहाँ आप अपनी कमाई से जुड़ी सभी गतिविधियाँ मैनेज कर सकते हैं।",
        "daily_bonus_success": "🎉 दैनिक बोनस क्लेम किया गया!\nआपने सफलतापूर्वक अपना दैनिक बोनस ₹{bonus_amount:.2f} क्लेम कर लिया है। आपका नया बैलेंस ₹{new_balance:.2f} है।\n\n{streak_message}",
        "daily_bonus_already_claimed": "⏳ बोनस पहले ही क्लेम किया जा चुका है!\nआपने आज का बोनस पहले ही क्लेम कर लिया है। कल फिर कोशिश करें!",
        "admin_panel_title": "⚙️ एडमिन पैनल\n\nयहाँ से बॉट की सेटिंग्स और यूज़र्स को मैनेज करें।",
        "setrate_success": "✅ Tier 1 रेफरल कमाई की दर ₹{new_rate:.2f} पर अपडेट हो गई है।",
        "setrate_usage": "❌ उपयोग: /setrate <नई_राशि_रुपये_में>",
        "invalid_rate": "❌ अमान्य राशि। कृपया एक संख्या दर्ज करें।",
        "referral_rate_updated": "नई Tier 1 रेफरल दर अब ₹{new_rate:.2f} है।",
        "broadcast_admin_only": "❌ यह कमांड केवल बॉट एडमिन के लिए है।",
        "broadcast_message": "सभी उपयोगकर्ताओं को संदेश भेजने के लिए कृपया किसी संदेश का /broadcast के साथ उत्तर दें।", # Formatting tags removed
        "setwelbonus_usage": "❌ उपयोग: /setwelbonus <राशि_रुपये_में>",
        "setwelbonus_success": "✅ वेलकम बोनस ₹{new_bonus:.2f} पर अपडेट हो गया है।",
        "welcome_bonus_received": "🎁 वेलकम बोनस!\n\nआपको ₹{amount:.2f} वेलकम बोनस मिला है! दोस्तों को रेफर करके और कमाएँ।",
        "spin_wheel_title": "🎡 व्हील स्पिन करें - मुफ्त कमाई!\n\nबची हुई स्पिनें: {spins_left}\n\nऔर स्पिन कैसे पाएं:\n1 नए यूज़र को रेफ़र करें और 1 फ्री स्पिन पाएं!",
        "spin_wheel_button": "✨ अभी स्पिन करें ({spins_left} शेष)",
        "spin_wheel_animating": "🎡 स्पिन हो रहा है...\n\nपरिणाम का इंतजार करें! 🍀",
        "spin_wheel_insufficient_spins": "❌ कोई स्पिन बाकी नहीं!\n\nएक और फ्री स्पिन पाने के लिए 1 नए यूज़र को रेफ़र करें!",
        "spin_wheel_win": "🎉 बधाई हो!\n\nआपने जीता: ₹{amount:.2f}!\n\nनया बैलेंस: ₹{new_balance:.2f}\n\nबची हुई स्पिनें: {spins_left}",
        "spin_wheel_lose": "😢 अगली बार बेहतर किस्मत!\n\nइस बार आप कुछ नहीं जीत पाए।\n\nशेष बैलेंस: ₹{new_balance:.2f}\n\nबची हुई स्पिनें: {spins_left}",
        "missions_title": "🎯 दैनिक मिशन\n\nअतिरिक्त इनाम पाने के लिए मिशन पूरे करें! अपनी प्रगति नीचे देखें:",
        "mission_search_note": "⏳ 3 फिल्में खोजें (भुगतान प्राप्त) ({current}/{target}) [प्रगति में]\n\nध्यान दें: यह मिशन तब पूरा होता है जब आपको आज आपके रेफर किए गए यूज़र्स से 3 बार भुगतान मिलता है।",
        "mission_search_progress": "⏳ 3 फिल्में खोजें ({current}/{target}) [प्रगति में]",
        "mission_complete": "✅ मिशन पूरा हुआ!\n\nआपने {mission_name} के लिए ₹{reward:.2f} कमाए!\nनया बैलेंस: ₹{new_balance:.2f}",
        "withdrawal_request_sent": "✅ निकासी का अनुरोध भेज दिया गया!\n\n₹{amount:.2f} के आपके अनुरोध को एडमिन को भेज दिया गया है। आपको 24 घंटे के भीतर भुगतान मिल जाएगा।",
        "withdrawal_insufficient": "❌ पर्याप्त बैलेंस नहीं!\n\nन्यूनतम निकासी राशि ₹80.00 है",
        "withdrawal_approved_user": "✅ निकासी स्वीकृत!\n\n₹{amount:.2f} की आपकी निकासी स्वीकृत कर दी गई है। भुगतान 24 घंटे के भीतर प्रोसेस किया जाएगा।",
        "withdrawal_rejected_user": "❌ निकासी अस्वीकृत!\n\n₹{amount:.2f} की आपकी निकासी अस्वीकृत कर दी गई है। विवरण के लिए एडमिन से संपर्क करें।",
        "ref_link_message": "आपकी रेफरल लिंक:\n{referral_link}\n\nवर्तमान रेफरल दर: ₹{tier_rate:.2f} प्रति रेफरल\n\nइस लिंक को दोस्तों के साथ साझा करें और जब वे शामिल होकर फिल्में खोजते हैं, तो पैसे कमाएं!", # Formatting tags removed
        "new_referral_notification": "🎉 नया रेफरल!\n\n{full_name} ({username}) आपकी लिंक का उपयोग करके शामिल हुए हैं!\n\n💰 आपको जॉइनिंग बोनस ₹{bonus:.2f} मिला!\n\n🎰 आपको स्पिन व्हील के लिए 1 फ्री स्पिन भी मिली है!",
        "daily_earning_update_new": "💰 रोजाना रेफरल कमाई!\n\nआज एक पेड सर्च के लिए आपने अपने रेफरल {full_name} से ₹{amount:.2f} कमाए। \nनया बैलेंस: ₹{new_balance:.2f}",
        "search_success_message": "✅ मूवी सर्च पूरी!\n\nआपकी शॉर्टलिंक प्रक्रिया पूरी हो गई है। आपके रेफ़र करने वाले को आपकी खोज के लिए आज का भुगतान मिल गया है! अब अपनी मूवी लिंक ढूंढें।",
        "clear_earn_usage": "❌ उपयोग: /clearearn <user_id>",
        "clear_earn_success": "✅ उपयोगकर्ता {user_id} की कमाई साफ़ कर दी गई है।",
        "clear_earn_not_found": "❌ उपयोगकर्ता {user_id} नहीं मिला।",
        "check_stats_usage": "❌ उपयोग: /checkstats <user_id>",
        "check_stats_message": "📊 यूज़र आँकड़े\n\nID: {user_id}\nकमाई: ₹{earnings:.2f}\nरेफरल: {referrals}", # Formatting tags removed
        "check_stats_not_found": "❌ उपयोगकर्ता {user_id} नहीं मिला।",
        "stats_message": "📊 बॉट आँकड़े\n\nकुल उपयोगकर्ता: {total_users}\nअनुमोदित उपयोगकर्ता: {approved_users}",
        "channel_bonus_claimed": "✅ चैनल जॉइन बोनस!\nआपने सफलतापूर्वक {channel} जॉइन करने के लिए ₹{amount:.2f} क्लेम कर लिए हैं।\nनया बैलेंस: ₹{new_balance:.2f}",
        "channel_not_joined": "❌ चैनल जॉइन नहीं किया!\nबोनस क्लेम करने के लिए आपको हमारा चैनल {channel} जॉइन करना होगा।",
        "channel_already_claimed": "⏳ बोनस पहले ही क्लेम किया जा चुका है!\nआप पहले ही चैनल जॉइन बोनस क्लेम कर चुके हैं।",
        "channel_bonus_failure": "❌ चैनल जॉइन नहीं किया!\nबोनस क्लेम करने के लिए आपको हमारा चैनल {channel} जॉइन करना होगा।",
        
        # --- MESSAGES Dictionay में बदलाव ---
        # 1. "top_users_title" को बदला गया
        "top_users_title": "🏆 शीर्ष 10 कुल कमाने वाले 🏆\n\n(यह मासिक लीडरबोर्ड से अलग है)\n\n",
        # 2. "clear_junk_success" को बदला गया
        "clear_junk_success": "✅ जंक डेटा साफ़!\n\nडिलीट किए गए यूज़र्स: {users}\nसाफ़ किए गए रेफरल रिकॉर्ड: {referrals}\nसाफ़ की गई निकासी: {withdrawals}",
        
        "clear_junk_admin_only": "❌ यह कमांड केवल बॉट एडमिन के लिए है।",
        "tier_benefits_title": "👑 टियर सिस्टम के लाभ 👑\n\nजैसे-जैसे आप अधिक कमाते हैं, आपकी कमाई दर बढ़ती जाती है। प्रति रेफरल अधिक पैसे के लिए उच्च टियर पर पहुँचें!",
        "tier_info": "🔸 {tier_name} (लेवल {tier}): न्यूनतम कमाई: ₹{min_earnings:.2f}\n   - लाभ: {benefit}",
        
        # TIERS Dictionay से मेल खाने के लिए हार्डकोडेड मैसेज को अपडेट किया गया
        "tier_benefits_message": "👑 टियर सिस्टम के लाभ 👑\n\nजैसे-जैसे आप अधिक कमाते हैं, आपकी कमाई दर बढ़ती जाती है। प्रति रेफरल अधिक पैसे के लिए उच्च टियर पर पहुँचें!\n\nटियर 1: शुरुआती (न्यूनतम कमाई: ₹0.00, दर: ₹0.20)\nटियर 2: प्रो (न्यूनतम कमाई: ₹200.00, दर: ₹0.35)\nटियर 3: एक्सपर्ट (न्यूनतम कमाई: ₹500.00, दर: ₹0.45)\nटियर 4: मास्टर (न्यूनतम कमाई: ₹1000.00, दर: ₹0.50)",
        
        "help_menu_title": "🆘 सहायता और समर्थन",
        "help_menu_text": "यदि आपके कोई प्रश्न हैं, भुगतान संबंधी समस्याएँ हैं, या एडमिन से संपर्क करने की आवश्यकता है, तो नीचे दिए गए बटन का उपयोग करें। 'पैसे कैसे कमाएं' (रेफरल उदाहरण) अनुभाग को पहले पढ़ना याद रखें!",
        "help_message": "🆘 सहायता और समर्थन\n\nयदि आपके कोई प्रश्न या भुगतान संबंधी समस्याएँ हैं, तो कृपया सीधे एडमिन से संपर्क करें: @{telegram_handle}\n\nटिप: पहले कमाई पैनल में 'रेफरल उदाहरण' पढ़ें!",
        "alert_daily_bonus": "🔔 याद दिलाना!\n\nअरे, आपने अभी तक अपना 🎁 दैनिक बोनस क्लेम नहीं किया है! मुफ्त पैसे गँवाएं नहीं। अभी कमाई पैनल पर जाएँ!",
        "alert_mission": "🎯 मिशन अलर्ट!\n\nआपके दैनिक मिशन आपका इंतज़ार कर रहे हैं! आज ही अतिरिक्त नकद कमाने के लिए उन्हें पूरा करें। मदद चाहिए? एक दोस्त को रेफ़र करें और '3 फिल्में खोजें' मिशन पूरा करें!",
        "alert_refer": "🔗 बड़ी कमाई का मौका!\n\nआपके दोस्त सबसे अच्छे मूवी बॉट से चूक रहे हैं! अपनी रेफरल लिंक अभी साझा करें और प्रति व्यक्ति रोज़ाना ₹{max_rate:.2f} तक कमाएँ!",
        "alert_spin": "🎰 फ्री स्पिन अलर्ट!\n\nक्या आपके पास कोई फ्री स्पिन बची है? ₹2.00 तक जीतने के मौका पाने के लिए अभी व्हील स्पिन करें! अधिक स्पिन पाने के लिए एक दोस्त को रेफ़र करें!", # स्पिन प्राइस के अनुसार अपडेट किया गया
        "join_channel_button_text": "चैनल जॉइन करें और फिर कोशिश करें",
        
        # --- HINDI (hi) MESSAGES (NEW) ---

        # -- ADMIN USER STATS (NEW) --
        "admin_user_stats_prompt": "✍️ कृपया जिस यूज़र की जांच करनी है, उसकी User ID इस मैसेज के रिप्लाई में भेजें:",
        "admin_add_money_prompt": "💰 कृपया वह राशि (INR में, जैसे: 10.50) रिप्लाई में भेजें जो आप यूज़र {user_id} को देना चाहते हैं:",
        "admin_clear_data_prompt": "⚠️ क्या आप निश्चित हैं?\nकेवल कमाई (earnings) साफ़ करने के लिए, रिप्लाई करें: `earning`\nयूज़र का सारा डेटा डिलीट करने के लिए, रिप्लाई करें: `all`",
        "admin_user_not_found": "❌ यूज़र {user_id} डेटाबेस में नहीं मिला।",
        "admin_add_money_success": "✅ यूज़र {user_id} को ₹{amount:.2f} सफलतापूर्वक जोड़ दिए गए। नया बैलेंस: ₹{new_balance:.2f}",
        "admin_clear_earnings_success": "✅ यूज़र {user_id} की कमाई सफलतापूर्वक साफ़ कर दी गई। नया बैलेंस: ₹0.00",
        "admin_delete_user_success": "✅ यूज़र {user_id} का सारा डेटा सफलतापूर्वक डिलीट कर दिया गया।",
        "admin_invalid_input": "❌ अमान्य इनपुट। कृपया पुनः प्रयास करें।",

        # -- LEADERBOARD (NEW) --
        "leaderboard_title": "🏆 मासिक लीडरबोर्ड 🏆\n\nइस महीने के टॉप 10 रेफरर!",
        "leaderboard_rank_entry": "   - मासिक रेफरल: {monthly_refs}\n   - कुल बैलेंस: ₹{balance:.2f}\n",
        
        # --- YAHAN NAYE MESSAGES ADD KIYE GAYE HAIN ---
        "leaderboard_info_title": "💡 लीडरबोर्ड के फायदे",
        "leaderboard_info_text": "इस महीने के 'मासिक रेफ़रल' के आधार पर टॉप 10 यूज़र्स इस लीडरबोर्ड में दिखाए जाते हैं।\n\n🏆 <b>क्या फायदा है?</b>\nमहीने के अंत में टॉप 10 यूज़र्स को नकद इनाम मिलता है!\n\n💰 <b>पैसे कैसे मिलेंगे?</b>\nहर महीने की 1 तारीख को, इनाम की राशि विजेताओं के बॉट बैलेंस में अपने आप जोड़ दी जाती है।\n\n🎯 <b>यह किस लिए है?</b>\nआपकी रैंक <i>केवल</i> इस बात पर आधारित है कि आप हर महीने कितने नए यूज़र्स को रेफ़र करते हैं। सबसे ज्यादा रेफ़रल करने वाला यूज़र जीतता है!",
        # --- BADLAAV KHATM ---
        
        "monthly_reward_notification": "🎉 लीडरबोर्ड इनाम! 🎉\n\nबधाई हो! आपने मासिक लीडरबोर्ड पर रैंक #{rank} हासिल किया है।\n\nआपको ₹{reward:.2f} का इनाम दिया गया है।\n\nआपका नया बैलेंस है: ₹{new_balance:.2f}",

        # -- CHANNEL BONUS FIX (NEW) --
        "channel_bonus_error": "❌ सत्यापन विफल!\n\nहम आपकी सदस्यता को सत्यापित नहीं कर सके। कृपया सुनिश्चित करें कि आप चैनल ({channel}) से जुड़ गए हैं और कुछ देर बाद पुनः प्रयास करें।\n\nयदि यह समस्या बनी रहती है, तो एडमिन को सूचित कर दिया गया है।",
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
