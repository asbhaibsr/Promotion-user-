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
YOUR_TELEGRAM_HANDLE = os.getenv("YOUR_TELEGRAM_HANDLE", "your_username") 
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")

# --- ग्रुप और चैनल लिंक्स ---
NEW_MOVIE_GROUP_LINK = "https://t.me/asfilter_bot"
MOVIE_GROUP_LINK = "https://t.me/asfilter_group" 
ALL_GROUPS_LINK = "https://t.me/addlist/6urdhhdLRqhiZmQ1"

EXAMPLE_SCREENSHOT_URL = os.getenv("EXAMPLE_SCREENSHOT_URL", "https://example.com/screenshot.jpg")

# --- चैनल बोनस सेटिंग्स ---
CHANNEL_USERNAME = "@asbhai_bsr"
CHANNEL_ID = -1002283182645
CHANNEL_BONUS = 2.00
# JOIN_CHANNEL_LINK को हटा दिया गया है - अब Dynamic Generate होगा

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

# --- WITHDRAWAL & LEADERBOARD SETTINGS ---
WITHDRAWAL_REQUIREMENTS = [
    {"min_balance": 1000.0, "required_refs": 150},
    {"min_balance": 500.0,  "required_refs": 100},
    {"min_balance": 200.0,  "required_refs": 50},
    {"min_balance": 80.0,   "required_refs": 20}
]

WITHDRAWAL_METHODS = {
    "upi": "UPI (GPay/PhonePe/Paytm)",
    "bank": "Bank Account"
}

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
        "help_message": "🆘 Help & Support\n\nIf you have any questions or payment issues, please contact the admin directly: @{telegram_handle}\n\nTip: Read the 'Referral Example' in the Earning Panel first!",
        "refer_example_message": "💡 Referral Example / How to Earn\n\n1. Share your link with friends.\n2. They start the bot and join the movie group.\n3. They search for 3 movies in the group (or more).\n4. You get paid for 3 searches/day from that friend! ₹{rate} per referral/day.",
        "withdrawal_details_message": "💸 Withdrawal Details\n\nYour current balance is {balance}. You can withdraw when your balance reaches ₹80 or more.\n\nClick the button below to request withdrawal.",
        "earning_panel_message": "💰 Earning Panel\n\nManage all your earning activities here.",
        "daily_bonus_success": "🎉 Daily Bonus Claimed!\nYou have successfully claimed your daily bonus of ₹{bonus_amount:.2f}. Your new balance is ₹{new_balance:.2f}.\n\n{streak_message}",
        "daily_bonus_already_claimed": "⏳ Bonus Already Claimed!\nYou have already claimed your bonus for today. Try again tomorrow!",
        "welcome_bonus_received": "🎁 Welcome Bonus!\n\nYou have received ₹{amount:.2f} welcome bonus! Start earning more by referring friends.",
        "spin_wheel_title": "🎡 Spin the Wheel - Free Earning!\n\nRemaining Spins: {spins_left}\n\nHow to Get More Spins:\nRefer 1 new user to get 1 free spin!",
        "spin_wheel_button": "✨ Spin Now ({spins_left} Left)",
        "spin_wheel_animating": "🎡 Spinning...\n\nWait for the result! 🍀",
        "spin_wheel_insufficient_spins": "❌ No Spins Left!\n\nYou need to refer 1 new user to get another free spin!",
        "spin_wheel_win": "🎉 Congratulations!\n\nYou won: ₹{amount:.2f}!\n\nNew balance: ₹{new_balance:.2f}\n\nRemaining Spins: {spins_left}",
        "spin_wheel_lose": "😢 Better luck next time!\n\nYou didn't win anything this time.\n\nRemaining balance: ₹{new_balance:.2f}\n\nRemaining Spins: {spins_left}",
        "missions_title": "🎯 Daily Missions\n\nComplete missions to earn extra rewards! Check your progress below:",
        "withdrawal_insufficient": "❌ Insufficient Balance!\n\nMinimum withdrawal amount is ₹80.00",
        "withdrawal_prompt_details": "✅ **Ready to Withdraw!**\n\nPlease send your payment details in a single message (e.g., UPI ID, Bank A/C + IFSC, or upload a QR Code screenshot).\n\n⚠️ **This request will expire in 30 seconds.**",
        "withdrawal_session_expired": "⏳ **Withdrawal Session Expired!**\n\nYour 30-second window to send payment details has closed. Please start the withdrawal request again from the Earning Panel.",
        "withdrawal_details_received": "✅ **Details Received!**\n\nYour withdrawal request for ₹{amount:.2f} with your payment details has been sent to the admin for approval.",
        "withdrawal_approved_user": "✅ Withdrawal Approved!\n\nYour withdrawal of ₹{amount:.2f} has been approved. Payment will be processed within 24 hours.",
        "withdrawal_rejected_user": "❌ Withdrawal Rejected!\n\nYour withdrawal of ₹{amount:.2f} was rejected. Please contact admin for details.",
        "ref_link_message": "Your Referral Link:\n{referral_link}\n\nCurrent Referral Rate: ₹{tier_rate:.2f} per referral\n\nShare this link with friends and earn money when they join and search for movies!",
        "new_referral_notification": "🎉 New Referral!\n\n{full_name} ({username}) has joined using your link!\n\n🎰 You earned <b>1 Free Spin</b>!\n\n💰 <b>IMPORTANT:</b> To earn money from this user, tell them to <b>search for a movie in the group</b> and complete the shortlink process. You will get paid!",
        "daily_earning_update_new": "💰 Daily Referral Earning!\n\nYou earned ₹{amount:.2f} from your referral {full_name} for a paid search today. \nNew balance: ₹{new_balance:.2f}",
        "channel_bonus_claimed": "✅ Channel Join Bonus!\nYou have successfully claimed ₹{amount:.2f} for joining {channel}.\nNew balance: ₹{new_balance:.2f}",
        "channel_not_joined": "❌ Channel Not Joined!\nYou must join our channel {channel} to claim the bonus.",
        "channel_already_claimed": "⏳ Bonus Already Claimed!\nYou have already claimed the channel join bonus.",
        "channel_bonus_failure": "❌ Channel Not Joined!\nYou must join our channel {channel} to claim the bonus.",
        "channel_bonus_error": "❌ Verification Failed!\n\nWe could not verify your membership. Please ensure you have joined the channel ({channel}) and try again in a moment.\n\nIf this problem continues, the admin has been notified.",
        "tier_benefits_message": "👑 Tier System Benefits 👑\n\nYour earning rate increases as you earn more. Reach higher tiers for more money per referral!\n\nTier 1: Beginner (Min Earning: ₹0.00, Rate: ₹0.20)\nTier 2: Pro (Min Earning: ₹200.00, Rate: ₹0.35)\nTier 3: Expert (Min Earning: ₹500.00, Rate: ₹0.45)\nTier 4: Master (Min Earning: ₹1000.00, Rate: ₹0.50)",
        "leaderboard_title": "🏆 Monthly Leaderboard 🏆\n\nTop 10 referrers of the month!",
        "leaderboard_info_text": "This leaderboard shows the Top 10 users with the most 'Monthly Referrals'.\n\n🏆 <b>What's the Benefit?</b>\nThe Top 10 users at the end of the month win a cash prize!\n\n💰 <b>Prize Money (Paid on 1st of Month):</b>\n🥇 Rank 1: <b>₹300.00</b> (Min 50 Refs)\n🥈 Rank 2: <b>₹200.00</b> (Min 30 Refs)\n🥉 Rank 3: <b>₹100.00</b> (Min 30 Refs)\n🏅 Rank 4-5: <b>₹50.00</b> (Min 30 Refs)\n🏅 Rank 6-10: <b>₹10.00</b> (Min 30 Refs)\n\n🎯 <b>How to Win?</b>\nYour rank is based <i>only</i> on the number of new users you refer each month. More referrals = Higher rank!",
    },
    "hi": {
        "start_greeting": "नमस्ते 👋! मूवी ग्रुप बॉट में आपका स्वागत है। इन आसान स्टेप्स को फॉलो करके अपनी पसंदीदा मूवी पाएँ:",
        "start_step1": "हमारे मूवी ग्रुप में शामिल होने के लिए नीचे दिए गए बटन पर क्लिक करें।",
        "start_step2": "ग्रुप में जाकर अपनी मनपसंद मूवी का नाम लिखें।",
        "start_step3": "बॉट आपको आपकी मूवी की लिंक देगा।",
        "language_choice": "अपनी भाषा चुनें:",
        "language_selected": "भाषा हिंदी में बदल दी गई है।",
        "language_prompt": "कृपया अपनी भाषा चुनें:",
        "help_message": "🆘 सहायता और समर्थन\n\nयदि आपके कोई प्रश्न या भुगतान संबंधी समस्याएँ हैं, तो कृपया सीधे एडमिन से संपर्क करें: @{telegram_handle}\n\nटिप: पहले कमाई पैनल में 'रेफरल उदाहरण' पढ़ें!",
        "refer_example_message": "💡 रेफरल उदाहरण / पैसे कैसे कमाएं\n\n1. अपनी लिंक दोस्तों के साथ साझा करें।\n2. वे बॉट शुरू करते हैं और मूवी ग्रुप में शामिल होते हैं।\n3. वे ग्रुप में 3 फिल्में खोजते हैं (या अधिक)।\n4. आपको उस दोस्त से 3 खोज/दिन के लिए भुगतान मिलता है! ₹{rate} प्रति रेफरल/दिन।",
        "withdrawal_details_message": "💸 निकासी का विवरण\n\nआपका वर्तमान बैलेंस {balance} है। जब आपका बैलेंस ₹80 या उससे अधिक हो जाए, तो आप निकासी कर सकते हैं।\n\nनिकासी का अनुरोध करने के लिए नीचे दिए गए बटन पर क्लिक करें।",
        "earning_panel_message": "💰 कमाई का पैनल\n\nयहाँ आप अपनी कमाई से जुड़ी सभी गतिविधियाँ मैनेज कर सकते हैं।",
        "daily_bonus_success": "🎉 दैनिक बोनस क्लेम किया गया!\nआपने सफलतापूर्वक अपना दैनिक बोनस ₹{bonus_amount:.2f} क्लेम कर लिया है। आपका नया बैलेंस ₹{new_balance:.2f} है।\n\n{streak_message}",
        "daily_bonus_already_claimed": "⏳ बोनस पहले ही क्लेम किया जा चुका है!\nआपने आज का बोनस पहले ही क्लेम कर लिया है। कल फिर कोशिश करें!",
        "welcome_bonus_received": "🎁 वेलकम बोनस!\n\nआपको ₹{amount:.2f} वेलकम बोनस मिला है! दोस्तों को रेफर करके और कमाएँ।",
        "spin_wheel_title": "🎡 व्हील स्पिन करें - मुफ्त कमाई!\n\nबची हुई स्पिनें: {spins_left}\n\nऔर स्पिन कैसे पाएं:\n1 नए यूज़र को रेफ़र करें और 1 फ्री स्पिन पाएं!",
        "spin_wheel_button": "✨ अभी स्पिन करें ({spins_left} शेष)",
        "spin_wheel_animating": "🎡 स्पिन हो रहा है...\n\nपरिणाम का इंतजार करें! 🍀",
        "spin_wheel_insufficient_spins": "❌ कोई स्पिन बाकी नहीं!\n\nएक और फ्री स्पिन पाने के लिए 1 नए यूज़र को रेफ़र करें!",
        "spin_wheel_win": "🎉 बधाई हो!\n\nआपने जीता: ₹{amount:.2f}!\n\nनया बैलेंस: ₹{new_balance:.2f}\n\nबची हुई स्पिनें: {spins_left}",
        "spin_wheel_lose": "😢 अगली बार बेहतर किस्मत!\n\nइस बार आप कुछ नहीं जीत पाए।\n\nशेष बैलेंस: ₹{new_balance:.2f}\n\nबची हुई स्पिनें: {spins_left}",
        "missions_title": "🎯 दैनिक मिशन\n\nअतिरिक्त इनाम पाने के लिए मिशन पूरे करें! अपनी प्रगति नीचे देखें:",
        "withdrawal_insufficient": "❌ पर्याप्त बैलेंस नहीं!\n\nन्यूनतम निकासी राशि ₹80.00 है",
        "withdrawal_prompt_details": "✅ **निकासी के लिए तैयार!**\n\nकृपया अपना भुगतान विवरण एक ही संदेश में भेजें (जैसे, UPI ID, बैंक A/C + IFSC, या QR कोड स्क्रीनशॉट अपलोड करें)।\n\n⚠️ **यह अनुरोध 30 सेकंड में समाप्त हो जाएगा।**",
        "withdrawal_session_expired": "⏳ **निकासी सत्र समाप्त!**\n\nभुगतान विवरण भेजने के लिए आपकी 30-सेकंड की विंडो बंद हो गई है। कृपया Earning Panel से फिर से निकासी का अनुरोध शुरू करें।",
        "withdrawal_details_received": "✅ **विवरण प्राप्त हुआ!**\n\nआपके भुगतान विवरण के साथ ₹{amount:.2f} के लिए आपका निकासी अनुरोध एडमिन को अनुमोदन के लिए भेज दिया गया है।",
        "withdrawal_approved_user": "✅ निकासी स्वीकृत!\n\n₹{amount:.2f} की आपकी निकासी स्वीकृत कर दी गई है। भुगतान 24 घंटे के भीतर प्रोसेस किया जाएगा।",
        "withdrawal_rejected_user": "❌ निकासी अस्वीकृत!\n\n₹{amount:.2f} की आपकी निकासी अस्वीकृत कर दी गई है। विवरण के लिए एडमिन से संपर्क करें।",
        "ref_link_message": "आपकी रेफरल लिंक:\n{referral_link}\n\nवर्तमान रेफरल दर: ₹{tier_rate:.2f} प्रति रेफरल\n\nइस लिंक को दोस्तों के साथ साझा करें और जब वे शामिल होकर फिल्में खोजते हैं, तो पैसे कमाएं!",
        "new_referral_notification": "🎉 नया रेफरल!\n\n{full_name} ({username}) आपकी लिंक का उपयोग करके शामिल हुए हैं!\n\n🎰 आपको <b>1 फ्री स्पिन</b> मिली है!\n\n💰 <b>ज़रूरी सूचना:</b> इस यूज़र से पैसे कमाने के लिए, उन्हें <b>ग्रुप में मूवी सर्च करने</b> और शॉर्टलिंक पूरा करने के लिए कहें। आपको पैसे मिलेंगे!",
        "daily_earning_update_new": "💰 रोजाना रेफरल कमाई!\n\nआज एक पेड सर्च के लिए आपने अपने रेफरल {full_name} से ₹{amount:.2f} कमाए। \nनया बैलेंस: ₹{new_balance:.2f}",
        "channel_bonus_claimed": "✅ चैनल जॉइन बोनस!\nआपने सफलतापूर्वक {channel} जॉइन करने के लिए ₹{amount:.2f} क्लेम कर लिए हैं।\nनया बैलेंस: ₹{new_balance:.2f}",
        "channel_not_joined": "❌ चैनल जॉइन नहीं किया!\nबोनस क्लेम करने के लिए आपको हमारा चैनल {channel} जॉइन करना होगा।",
        "channel_already_claimed": "⏳ बोनस पहले ही क्लेम किया जा चुका है!\nआप पहले ही चैनल जॉइन बोनस क्लेम कर चुके हैं।",
        "channel_bonus_failure": "❌ चैनल जॉइन नहीं किया!\nबोनस क्लेम करने के लिए आपको हमारा चैनल {channel} जॉइन करना होगा।",
        "channel_bonus_error": "❌ सत्यापन विफल!\n\nहम आपकी सदस्यता को सत्यापित नहीं कर सके। कृपया सुनिश्चित करें कि आप चैनल ({channel}) से जुड़ गए हैं और कुछ देर बाद पुनः प्रयास करें।\n\nयदि यह समस्या बनी रहती है, तो एडमिन को सूचित कर दिया गया है।",
        "tier_benefits_message": "👑 टियर सिस्टम के लाभ 👑\n\nजैसे-जैसे आप अधिक कमाते हैं, आपकी कमाई दर बढ़ती जाती है। प्रति रेफरल अधिक पैसे के लिए उच्च टियर पर पहुँचें!\n\nटियर 1: शुरुआती (न्यूनतम कमाई: ₹0.00, दर: ₹0.20)\nटियर 2: प्रो (न्यूनतम कमाई: ₹200.00, दर: ₹0.35)\nटियर 3: एक्सपर्ट (न्यूनतम कमाई: ₹500.00, दर: ₹0.45)\nटियर 4: मास्टर (न्यूनतम कमाई: ₹1000.00, दर: ₹0.50)",
        "leaderboard_title": "🏆 मासिक लीडरबोर्ड 🏆\n\nइस महीने के टॉप 10 रेफरर!",
        "leaderboard_info_text": "यह लीडरबोर्ड 'मासिक रेफ़रल' के आधार पर टॉप 10 यूज़र्स को दिखाता है।\n\n🏆 <b>क्या फायदा है?</b>\nमहीने के अंत में टॉप 10 यूज़र्स को नकद इनाम मिलता है!\n\n💰 <b>इनाम राशि (महीने की 1 तारीख को):</b>\n🥇 रैंक 1: <b>₹300.00</b> (न्यूनतम 50 रेफ़रल)\n🥈 रैंक 2: <b>₹200.00</b> (न्यूनतम 30 रेफ़रल)\n🥉 रैंक 3: <b>₹100.00</b> (न्यूनतम 30 रेफ़रल)\n🏅 रैंक 4-5: <b>₹50.00</b> (न्यूनतम 30 रेफ़रल)\n🏅 रैंक 6-10: <b>₹10.00</b> (न्यूनतम 30 रेफ़रल)\n\n🎯 <b>कैसे जीतें?</b>\nआपकी रैंक <i>केवल</i> इस बात पर आधारित है कि आप हर महीने कितने नए यूज़र्स को रेफ़र करते हैं। ज़्यादा रेफ़रल = ऊँची रैंक!",
    }
}
