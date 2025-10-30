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

YOUR_TELEGRAM_HANDLE = os.getenv("YOUR_TELEGRAM_HANDLE", "telegram") 
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")

NEW_MOVIE_GROUP_LINK = "https://t.me/asfilter_bot"
MOVIE_GROUP_LINK = "https://t.me/asfilter_group" 
ALL_GROUPS_LINK = "https://t.me/addlist/6urdhhdLRqhiZmQ1"

EXAMPLE_SCREENSHOT_URL = os.getenv("EXAMPLE_SCREENSHOT_URL", "https://envs.sh/ric.jpg")

CHANNEL_USERNAME = "@asbhai_bsr"
CHANNEL_ID = -1002283182645
CHANNEL_BONUS = 15.00
JOIN_CHANNEL_LINK = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}" # नया: चैनल लिंक

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
DOLLAR_TO_INR = 83.0

DAILY_BONUS_BASE = 0.50
DAILY_BONUS_STREAK_MULTIPLIER = 0.10

SPIN_PRIZES_WEIGHTS = {
    0.00: 4,
    0.20: 3,
    0.50: 3,
    0.80: 2,
    1.00: 2,
    3.00: 1,
    5.00: 1,
    10.00: 1
}
SPIN_PRIZES = list(SPIN_PRIZES_WEIGHTS.keys())
SPIN_WEIGHTS = list(SPIN_PRIZES_WEIGHTS.values())

SPIN_WHEEL_CONFIG = {
    "initial_free_spins": 3,
    "refer_to_get_spin": 1
}

TIERS = {
    1: {"min_earnings": 0, "rate": 0.40, "name": "Beginner", "benefits_en": "Basic referral rate (₹0.40)", "benefits_hi": "सामान्य रेफरल दर (₹0.40)"},
    2: {"min_earnings": 50, "rate": 0.60, "name": "Pro", "benefits_en": "50% higher referral rate (₹0.60)", "benefits_hi": "50% ज़्यादा रेफरल दर (₹0.60)"},
    3: {"min_earnings": 200, "rate": 1.00, "name": "Expert", "benefits_en": "2.5x referral rate (₹1.00)", "benefits_hi": "2.5 गुना रेफरल दर (₹1.00)"},
    4: {"min_earnings": 500, "rate": 2.00, "name": "Master", "benefits_en": "5x referral rate (₹2.00)", "benefits_hi": "5 गुना रेफरल दर (₹2.00)"}
}

DAILY_MISSIONS = {
    "search_3_movies": {"reward": 1.00, "target": 3, "name": "Search 3 Movies", "name_hi": "3 फिल्में खोजें"},
    "refer_2_friends": {"reward": 5.00, "target": 2, "name": "Refer 2 Friends", "name_hi": "2 दोस्तों को रेफ़र करें"},
    "claim_daily_bonus": {"reward": 0.50, "target": 1, "name": "Claim Daily Bonus", "name_hi": "दैनिक बोनस क्लेम करें"}
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
        "help_message_text": "<b>🤝 How to Earn Money</b>\n\n1️⃣ <b>Get Your Link:</b> Use the 'My Refer Link' button to get your unique referral link.\n\n2️⃣ <b>Share Your Link:</b> Share this link with your friends. Tell them to start the bot and join our movie group.\n\n3️⃣ <b>Earn:</b> When a referred friend searches for a movie in the group and completes the shortlink process, you earn money! You can earn from each friend up to 3 times per day.",
        "withdrawal_details_message": "💸 <b>Withdrawal Details</b>\n\nYour current balance is {balance}. You can withdraw when your balance reaches ₹80 or more.\n\nClick the button below to request withdrawal.", # Updated this for pending withdrawal button
        "earning_panel_message": "<b>💰 Earning Panel</b>\n\nManage all your earning activities here.",
        "daily_bonus_success": "🎉 <b>Daily Bonus Claimed!</b>\nYou have successfully claimed your daily bonus of ₹{bonus_amount:.2f}. Your new balance is ₹{new_balance:.2f}.\n\n{streak_message}",
        "daily_bonus_already_claimed": "⏳ <b>Bonus Already Claimed!</b>\nYou have already claimed your bonus for today. Try again tomorrow!",
        "admin_panel_title": "<b>⚙️ Admin Panel</b>\n\nManage bot settings and users from here.",
        "setrate_success": "✅ Tier 1 Referral earning rate has been updated to ₹{new_rate:.2f}.",
        "setrate_usage": "❌ Usage: /setrate <new_rate_in_inr>",
        "invalid_rate": "❌ Invalid rate. Please enter a number.",
        "referral_rate_updated": "The new Tier 1 referral rate is now ₹{new_rate:.2f}.",
        "broadcast_admin_only": "❌ This command is for the bot admin only.",
        "broadcast_message": "Please reply to a message with <code>/broadcast</code> to send it to all users.",
        "setwelbonus_usage": "❌ Usage: /setwelbonus <amount_in_inr>",
        "setwelbonus_success": "✅ Welcome bonus updated to ₹{new_bonus:.2f}",
        "welcome_bonus_received": "🎁 <b>Welcome Bonus!</b>\n\nYou have received ₹{amount:.2f} welcome bonus! Start earning more by referring friends.",
        "spin_wheel_title": "🎡 <b>Spin the Wheel - Free Earning!</b>\n\nRemaining Spins: {spins_left}\n\n<b>How to Get More Spins:</b>\nRefer 1 new user to get 1 free spin!",
        "spin_wheel_button": "✨ Spin Now ({spins_left} Left)",
        "spin_wheel_animating": "🎡 <b>Spinning...</b>\n\nWait for the result! 🍀",
        "spin_wheel_insufficient_spins": "❌ <b>No Spins Left!</b>\n\nYou need to refer 1 new user to get another free spin!",
        "spin_wheel_win": "🎉 <b>Congratulations!</b>\n\nYou won: ₹{amount:.2f}!\n\nNew balance: ₹{new_balance:.2f}\n\nRemaining Spins: {spins_left}",
        "spin_wheel_lose": "😢 <b>Better luck next time!</b>\n\nYou didn't win anything this time.\n\nRemaining balance: ₹{new_balance:.2f}\n\nRemaining Spins: {spins_left}",
        "missions_title": "🎯 <b>Daily Missions</b>\n\nComplete missions to earn extra rewards! Check your progress below:",
        "mission_search_note": "⏳ Search 3 Movies ({current}/{target}) [In Progress]\n\n<b>Note:</b> This mission is completed when your <b>referred friend</b> searches 3 movies, not you.",
        "mission_search_progress": "⏳ Search 3 Movies ({current}/{target}) [In Progress]",
        "mission_complete": "✅ <b>Mission Completed!</b>\n\nYou earned ₹{reward:.2f} for {mission_name}!\nNew balance: ₹{new_balance:.2f}",
        "withdrawal_request_sent": "✅ <b>Withdrawal Request Sent!</b>\n\nYour request for ₹{amount:.2f} has been sent to admin. You will receive payment within 24 hours.",
        "withdrawal_insufficient": "❌ <b>Insufficient Balance!</b>\n\nMinimum withdrawal amount is ₹80.00",
        "withdrawal_approved_user": "✅ <b>Withdrawal Approved!</b>\n\nYour withdrawal of ₹{amount:.2f} has been approved. Payment will be processed within 24 hours.",
        "withdrawal_rejected_user": "❌ <b>Withdrawal Rejected!</b>\n\nYour withdrawal of ₹{amount:.2f} was rejected. Please contact admin for details.",
        "ref_link_message": "<b>Your Referral Link:</b>\n<code>{referral_link}</code>\n\n<b>Current Referral Rate:</b> ₹{tier_rate:.2f} per referral\n\n<i>Share this link with friends and earn money when they join and search for movies!</i>",
        "new_referral_notification": "🎉 <b>New Referral!</b>\n\n{full_name} ({username}) has joined using your link!\n\n💰 You received a joining bonus of ₹{bonus:.2f}!\n\n🎰 You also earned 1 Free Spin for the Spin Wheel!",
        "daily_earning_update": "💰 <b>Referral Earning!</b> ({count}/3)\n\nYou earned ₹{amount:.2f} from your referral {full_name}. \nNew balance: ₹{new_balance:.2f}",
        "clear_earn_usage": "❌ Usage: /clearearn <user_id>",
        "clear_earn_success": "✅ Earnings for user {user_id} have been cleared.",
        "clear_earn_not_found": "❌ User {user_id} not found.",
        "check_stats_usage": "❌ Usage: /checkstats <user_id>",
        "check_stats_message": "📊 <b>User Stats</b>\n\nID: <code>{user_id}</code>\nEarnings: ₹{earnings:.2f}\nReferrals: {referrals}",
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
        "alert_daily_bonus": "🔔 <b>Reminder!</b>\n\nHey there, you haven't claimed your 🎁 <b>Daily Bonus</b> yet! Don't miss out on free money. Go to the Earning Panel now!",
        "alert_mission": "🎯 <b>Mission Alert!</b>\n\nYour <b>Daily Missions</b> are waiting! Complete them to earn extra cash today. Need help? Refer a friend and complete the 'Search 3 Movies' mission!",
        "alert_refer": "🔗 <b>Huge Earning Opportunity!</b>\n\nYour friends are missing out on the best movie bot! Share your referral link now and earn up to ₹{max_rate:.2f} per person daily!",
        "alert_spin": "🎰 <b>Free Spin Alert!</b>\n\nDo you have a free spin left? Spin the wheel now for a chance to win up to ₹10.00! Refer a friend to get more spins!",
        "join_channel_button_text": "Join Channel & Try Again" # नया: बटन टेक्स्ट बदला गया है
    },
    "hi": {
        "start_greeting": "नमस्ते 👋! मूवी ग्रुप बॉट में आपका स्वागत है। इन आसान स्टेप्स को फॉलो करके अपनी पसंदीदा मूवी पाएँ:",
        "start_step1": "हमारे मूवी ग्रुप में शामिल होने के लिए नीचे दिए गए बटन पर क्लिक करें।",
        "start_step2": "ग्रुप में जाकर अपनी मनपसंद मूवी का नाम लिखें।",
        "start_step3": "बॉट आपको आपकी मूवी की लिंक देगा।",
        "language_choice": "अपनी भाषा चुनें:",
        "language_selected": "भाषा हिंदी में बदल दी गई है।",
        "help_message_text": "<b>🤝 पैसे कैसे कमाएं</b>\n\n1️⃣ <b>अपनी लिंक पाएं:</b> 'My Refer Link' बटन का उपयोग करके अपनी रेफरल लिंक पाएं।\n\n2️⃣ <b>शेयर करें:</b> इस लिंक को अपने दोस्तों के साथ शेयर करें। उन्हें बॉट शुरू करने और हमारे मूवी ग्रुप में शामिल होने के लिए कहें।\n\n3️⃣ <b>कमाई करें:</b> जब आपका रेफर किया गया दोस्त ग्रुप में कोई मूवी खोजता है और शॉर्टलिंक प्रक्रिया पूरी करता है, तो आप पैसे कमाते हैं! आप प्रत्येक दोस्त से एक दिन में 3 बार तक कमाई कर सकते हैं।",
        "withdrawal_details_message": "💸 <b>निकासी का विवरण</b>\n\nआपका वर्तमान बैलेंस {balance} है। जब आपका बैलेंस ₹80 या उससे अधिक हो जाए, तो आप निकासी कर सकते हैं।\n\nनिकासी का अनुरोध करने के लिए नीचे दिए गए बटन पर क्लिक करें।", # Updated this for pending withdrawal button
        "earning_panel_message": "<b>💰 कमाई का पैनल</b>\n\nयहाँ आप अपनी कमाई से जुड़ी सभी गतिविधियाँ मैनेज कर सकते हैं।",
        "daily_bonus_success": "🎉 <b>दैनिक बोनस क्लेम किया गया!</b>\nआपने सफलतापूर्वक अपना दैनिक बोनस ₹{bonus_amount:.2f} क्लेम कर लिया है। आपका नया बैलेंस ₹{new_balance:.2f} है।\n\n{streak_message}",
        "daily_bonus_already_claimed": "⏳ <b>बोनस पहले ही क्लेम किया जा चुका है!</b>\nआपने आज का बोनस पहले ही क्लेम कर लिया है। कल फिर कोशिश करें!",
        "admin_panel_title": "<b>⚙️ एडमिन पैनल</b>\n\nयहाँ से बॉट की सेटिंग्स और यूज़र्स को मैनेज करें।",
        "setrate_success": "✅ Tier 1 रेफरल कमाई की दर ₹{new_rate:.2f} पर अपडेट हो गई है।",
        "setrate_usage": "❌ उपयोग: /setrate <नई_राशि_रुपये_में>",
        "invalid_rate": "❌ अमान्य राशि। कृपया एक संख्या दर्ज करें।",
        "referral_rate_updated": "नई Tier 1 रेफरल दर अब ₹{new_rate:.2f} है।",
        "broadcast_admin_only": "❌ यह कमांड केवल बॉट एडमिन के लिए है।",
        "broadcast_message": "सभी उपयोगकर्ताओं को संदेश भेजने के लिए कृपया किसी संदेश का <code>/broadcast</code> के साथ उत्तर दें।",
        "setwelbonus_usage": "❌ उपयोग: /setwelbonus <राशि_रुपये_में>",
        "setwelbonus_success": "✅ वेलकम बोनस ₹{new_bonus:.2f} पर अपडेट हो गया है।",
        "welcome_bonus_received": "🎁 <b>वेलकम बोनस!</b>\n\nआपको ₹{amount:.2f} वेलकम बोनस मिला है! दोस्तों को रेफर करके और कमाएँ।",
        "spin_wheel_title": "🎡 <b>व्हील स्पिन करें - मुफ्त कमाई!</b>\n\nबची हुई स्पिनें: {spins_left}\n\n<b>और स्पिन कैसे पाएं:</b>\n1 नए यूज़र को रेफ़र करें और 1 फ्री स्पिन पाएं!",
        "spin_wheel_button": "✨ अभी स्पिन करें ({spins_left} शेष)",
        "spin_wheel_animating": "🎡 <b>स्पिन हो रहा है...</b>\n\nपरिणाम का इंतजार करें! 🍀",
        "spin_wheel_insufficient_spins": "❌ <b>कोई स्पिन बाकी नहीं!</b>\n\nएक और फ्री स्पिन पाने के लिए 1 नए यूज़र को रेफ़र करें!",
        "spin_wheel_win": "🎉 <b>बधाई हो!</b>\n\nआपने जीता: ₹{amount:.2f}!\n\nनया बैलेंस: ₹{new_balance:.2f}\n\nबची हुई स्पिनें: {spins_left}",
        "spin_wheel_lose": "😢 <b>अगली बार बेहतर किस्मत!</b>\n\nइस बार आप कुछ नहीं जीत पाए।\n\nशेष बैलेंस: ₹{new_balance:.2f}\n\nबची हुई स्पिनें: {spins_left}",
        "missions_title": "🎯 <b>दैनिक मिशन</b>\n\nअतिरिक्त इनाम पाने के लिए मिशन पूरे करें! अपनी प्रगति नीचे देखें:",
        "mission_search_note": "⏳ 3 फिल्में खोजें ({current}/{target}) [प्रगति में]\n\n<b>ध्यान दें:</b> यह मिशन तब पूरा होता है जब आपका <b>रेफर किया गया दोस्त</b> 3 फिल्में खोजता है, न कि आप।",
        "mission_search_progress": "⏳ 3 फिल्में खोजें ({current}/{target}) [प्रगति में]",
        "mission_complete": "✅ <b>मिशन पूरा हुआ!</b>\n\nआपने {mission_name} के लिए ₹{reward:.2f} कमाए!\nनया बैलेंस: ₹{new_balance:.2f}",
        "withdrawal_request_sent": "✅ <b>निकासी का अनुरोध भेज दिया गया!</b>\n\n₹{amount:.2f} के आपके अनुरोध को एडमिन को भेज दिया गया है। आपको 24 घंटे के भीतर भुगतान मिल जाएगा।",
        "withdrawal_insufficient": "❌ <b>पर्याप्त बैलेंस नहीं!</b>\n\nन्यूनतम निकासी राशि ₹80.00 है",
        "withdrawal_approved_user": "✅ <b>निकासी स्वीकृत!</b>\n\n₹{amount:.2f} की आपकी निकासी स्वीकृत कर दी गई है। भुगतान 24 घंटे के भीतर प्रोसेस किया जाएगा।",
        "withdrawal_rejected_user": "❌ <b>निकासी अस्वीकृत!</b>\n\n₹{amount:.2f} की आपकी निकासी अस्वीकृत कर दी गई है। विवरण के लिए एडमिन से संपर्क करें।",
        "ref_link_message": "<b>आपकी रेफरल लिंक:</b>\n<code>{referral_link}</code>\n\n<b>वर्तमान रेफरल दर:</b> ₹{tier_rate:.2f} प्रति रेफरल\n\n<i>इस लिंक को दोस्तों के साथ साझा करें और जब वे शामिल होकर फिल्में खोजते हैं, तो पैसे कमाएं!</i>",
        "new_referral_notification": "🎉 <b>नया रेफरल!</b>\n\n{full_name} ({username}) आपकी लिंक का उपयोग करके शामिल हुए हैं!\n\n💰 आपको जॉइनिंग बोनस ₹{bonus:.2f} मिला!\n\n🎰 आपको स्पिन व्हील के लिए 1 फ्री स्पिन भी मिली है!",
        "daily_earning_update": "💰 <b>रेफरल कमाई!</b> ({count}/3)\n\nआपने अपने रेफरल {full_name} से ₹{amount:.2f} कमाए। \nनया बैलेंस: ₹{new_balance:.2f}",
        "clear_earn_usage": "❌ उपयोग: /clearearn <user_id>",
        "clear_earn_success": "✅ उपयोगकर्ता {user_id} की कमाई साफ़ कर दी गई है।",
        "clear_earn_not_found": "❌ उपयोगकर्ता {user_id} नहीं मिला।",
        "check_stats_usage": "❌ उपयोग: /checkstats <user_id>",
        "check_stats_message": "📊 <b>यूज़र आँकड़े</b>\n\nID: <code>{user_id}</code>\nकमाई: ₹{earnings:.2f}\nरेफरल: {referrals}",
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
        "alert_daily_bonus": "🔔 <b>याद दिलाना!</b>\n\nअरे, आपने अभी तक अपना 🎁 <b>दैनिक बोनस</b> क्लेम नहीं किया है! मुफ्त पैसे गँवाएं नहीं। अभी कमाई पैनल पर जाएँ!",
        "alert_mission": "🎯 <b>मिशन अलर्ट!</b>\n\nआपके <b>दैनिक मिशन</b> आपका इंतज़ार कर रहे हैं! आज ही अतिरिक्त नकद कमाने के लिए उन्हें पूरा करें। मदद चाहिए? एक दोस्त को रेफ़र करें और '3 फिल्में खोजें' मिशन पूरा करें!",
        "alert_refer": "🔗 <b>बड़ी कमाई का मौका!</b>\n\nआपके दोस्त सबसे अच्छे मूवी बॉट से चूक रहे हैं! अपनी रेफरल लिंक अभी साझा करें और प्रति व्यक्ति रोज़ाना ₹{max_rate:.2f} तक कमाएँ!",
        "alert_spin": "🎰 <b>फ्री स्पिन अलर्ट!</b>\n\nक्या आपके पास कोई फ्री स्पिन बची है? ₹10.00 तक जीतने के मौका पाने के लिए अभी व्हील स्पिन करें! अधिक स्पिन पाने के लिए एक दोस्त को रेफ़र करें!",
        "join_channel_button_text": "चैनल जॉइन करें और फिर कोशिश करें" # नया: बटन टेक्स्ट बदला गया है
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
