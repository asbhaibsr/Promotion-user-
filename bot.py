
import os
import logging
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
# सुनिश्चित करें कि ADMIN_ID एक integer है
ADMIN_ID = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else None
YOUR_TELEGRAM_HANDLE = os.getenv("YOUR_TELEGRAM_HANDLE")
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")

# New movie group link and original links
NEW_MOVIE_GROUP_LINK = "https://t.me/asfilter_bot"
# 🔴 FIX: URL को 'https://t.me/asfilter_group' में बदला गया
MOVIE_GROUP_LINK = "https://t.me/asfilter_group" 
ALL_GROUPS_LINK = "https://t.me/addlist/6urdhhdLRqhiZmQ1"

# Load Render-specific variables
WEB_SERVER_URL = os.getenv("WEB_SERVER_URL")
PORT = int(os.getenv("PORT", 8000))

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client.get_database('bot_database')
users_collection = db.get_collection('users')
referrals_collection = db.get_collection('referrals')
settings_collection = db.get_collection('settings')

# --- MESSAGES Dictionary (आपका पूरा MESSAGES डिक्ट यहीं रहेगा) ---
# Dictionaries for multi-language support (यह डिक्शनरी वैसी ही रहेगी)
MESSAGES = {
    "en": {
        "start_greeting": "Hey 👋! Welcome to the Movies Group Bot. Get your favorite movies by following these simple steps:",
        "start_step1": "Click the button below to join our movie group.",
        "start_step2": "Go to the group and type the name of the movie you want.",
        "start_step3": "The bot will give you a link to your movie.",
        "start_group_button": "Join Movies Group",
        "new_group_button": "🆕 New Movie Group", # New button text
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
        "daily_earning_update": "🎉 <b>Your earnings have been updated!</b>\n"
                                "A referred user ({full_name}) completed the shortlink process today.\n"
                                "Your new balance: ${new_balance:.4f}",
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
        "help_message_text": "<b>🤝 How to Earn Money</b>\n\n"
                             "1️⃣ **Get Your Link:** Use the 'My Refer Link' button to get your unique referral link.\n\n"
                             "2️⃣ **Share Your Link:** Share this link with your friends. Tell them to start the bot and join our movie group.\n\n"
                             "3️⃣ **Earn:** When a referred friend searches for a movie in the group and completes the shortlink process, you earn money! You can earn from each friend once per day.",
        "withdrawal_message_updated": "💸 **Withdrawal Details**\n\n"
                                      "You can withdraw your earnings when your balance reaches ₹80 or more. Click the button below to contact the admin and get your payment.\n\n"
                                      "**Note:** Payments are sent via UPI ID, QR code, or Bank Account. Click the button and send your payment details to the admin.",
        "earning_panel_message": "<b>💰 Earning Panel</b>\n\n"
                                 "Manage all your earning activities here.",
        "daily_bonus_success": "🎉 <b>Daily Bonus Claimed!</b>\n"
                               "You have successfully claimed your daily bonus of ₹0.10. Your new balance is ₹{new_balance:.2f}.",
        "daily_bonus_already_claimed": "⏳ **Bonus Already Claimed!**\n"
                                       "You have already claimed your bonus for today. Try again tomorrow!",
        "admin_panel_title": "<b>⚙️ Admin Panel</b>\n\n"
                             "Manage bot settings and users from here.",
        "setrate_success": "✅ Referral earning rate has been updated to ₹{new_rate:.2f}.",
        "setrate_usage": "❌ Usage: /setrate <new_rate_in_inr>",
        "invalid_rate": "❌ Invalid rate. Please enter a number.",
        "referral_rate_updated": "The new referral rate is now ₹{new_rate:.2f}.",
    },
    "hi": {
        "start_greeting": "नमस्ते 👋! मूवी ग्रुप बॉट में आपका स्वागत है। इन आसान स्टेप्स को फॉलो करके अपनी पसंदीदा मूवी पाएँ:",
        "start_step1": "हमारे मूवी ग्रुप में शामिल होने के लिए नीचे दिए गए बटन पर क्लिक करें।",
        "start_step2": "ग्रुप में जाकर अपनी मनपसंद मूवी का नाम लिखें।",
        "start_step3": "बॉट आपको आपकी मूवी की लिंक देगा।",
        "start_group_button": "मूवी ग्रुप जॉइन करें",
        "new_group_button": "🆕 नया मूवी ग्रुप", # New button text
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
        "daily_earning_update": "🎉 <b>आपकी कमाई अपडेट हो गई है!</b>\n"
                                "एक रेफर किए गए यूजर ({full_name}) ने आज शॉर्टलिंक प्रक्रिया पूरी की।\n"
                                "आपका नया बैलेंस: ₹{new_balance:.2f}",
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
        "help_message_text": "<b>🤝 पैसे कैसे कमाएं</b>\n\n"
                             "1️⃣ **अपनी लिंक पाएं:** 'My Refer Link' बटन का उपयोग करके अपनी रेफरल लिंक पाएं।\n\n"
                             "2️⃣ **शेयर करें:** इस लिंक को अपने दोस्तों के साथ शेयर करें। उन्हें बॉट शुरू करने और हमारे मूवी ग्रुप में शामिल होने के लिए कहें।\n\n"
                             "3️⃣ **कमाई करें:** जब आपका रेफर किया गया दोस्त ग्रुप में कोई मूवी खोजता है और शॉर्टलिंक प्रक्रिया पूरी करता है, तो आप पैसे कमाते हैं! आप प्रत्येक दोस्त से एक दिन में एक बार कमाई कर सकते हैं।",
        "withdrawal_message_updated": "💸 **निकासी का विवरण**\n\n"
                                      "जब आपका बैलेंस ₹80 या उससे अधिक हो जाए, तो आप अपनी कमाई निकाल सकते हैं। एडमिन से संपर्क करने और अपना भुगतान पाने के लिए नीचे दिए गए बटन पर क्लिक करें।\n\n"
                                      "**ध्यान दें:** भुगतान UPI ID, QR कोड, या बैंक खाते के माध्यम से भेजे जाते हैं। बटन पर क्लिक करें और अपने भुगतान विवरण एडमिन को भेजें।",
        "earning_panel_message": "<b>💰 कमाई का पैनल</b>\n\n"
                                 "यहाँ आप अपनी कमाई से जुड़ी सभी गतिविधियाँ मैनेज कर सकते हैं।",
        "daily_bonus_success": "🎉 <b>दैनिक बोनस क्लेम किया गया!</b>\n"
                               "आपने सफलतापूर्वक अपना दैनिक बोनस ₹0.10 क्लेम कर लिया है। आपका नया बैलेंस ₹{new_balance:.2f} है।",
        "daily_bonus_already_claimed": "⏳ **बोनस पहले ही क्लेम किया जा चुका है!**\n"
                                       "आपने आज का बोनस पहले ही क्लेम कर लिया है। कल फिर कोशिश करें!",
        "admin_panel_title": "<b>⚙️ एडमिन पैनल</b>\n\n"
                             "यहाँ से बॉट की सेटिंग्स और यूज़र्स को मैनेज करें।",
        "setrate_success": "✅ रेफरल कमाई की दर ₹{new_rate:.2f} पर अपडेट हो गई है।",
        "setrate_usage": "❌ उपयोग: /setrate <नई_राशि_रुपये_में>",
        "invalid_rate": "❌ अमान्य राशि। कृपया एक संख्या दर्ज करें।",
        "referral_rate_updated": "नई रेफरल दर अब ₹{new_rate:.2f} है।",
    }
}
# --- MESSAGES Dictionary End ---


# Conversion rate (assuming a static rate for simplicity)
DOLLAR_TO_INR = 83.0
# Get referral bonus from settings or use a default
async def get_referral_bonus_inr():
    settings = settings_collection.find_one({"_id": "referral_rate"})
    return settings.get("rate_inr", 0.40) if settings else 0.40

async def get_referral_bonus_usd():
    rate_inr = await get_referral_bonus_inr()
    return rate_inr / DOLLAR_TO_INR

async def get_user_lang(user_id):
    """Fetches user's language preference from the database."""
    user_data = users_collection.find_one({"user_id": user_id})
    return user_data.get("lang", "en") if user_data else "en"

async def set_user_lang(user_id, lang):
    """Sets user's language preference in the database."""
    # Ensure 'user' object is passed correctly or get user object from database if necessary
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"lang": lang}},
        upsert=True
    )
    
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    referral_id_str = context.args[0].replace("ref_", "") if context.args and context.args[0].startswith("ref_") else None
    referral_id = int(referral_id_str) if referral_id_str else None

    # Check if user already exists
    user_data = users_collection.find_one({"user_id": user.id})
    
    # Check if a new user is being referred and they are not already in the DB
    is_new_user = not user_data

    # Update or insert user data.
    users_collection.update_one(
        {"user_id": user.id},
        {"$setOnInsert": {
            "username": user.username,
            "full_name": user.full_name,
            "lang": "en",
            "is_approved": True,
            "earnings": 0.0,
            "last_checkin_date": None
        }},
        upsert=True
    )

    user_data = users_collection.find_one({"user_id": user.id})
    lang = user_data.get("lang", "en")
    
    # NEW: LOG THE NEW USER
    if is_new_user and LOG_CHANNEL_ID:
        try:
            if referral_id:
                referrer_data = users_collection.find_one({"user_id": referral_id})
                referrer_username = referrer_data.get("username", "Unknown") if referrer_data else "Unknown"
                log_message = MESSAGES[lang]["new_user_log"].format(
                    user_id=user.id,
                    username=user.username or "N/A",
                    full_name=user.full_name or "N/A",
                    referrer_username=referrer_username,
                    referrer_id=referral_id
                )
            else:
                log_message = MESSAGES[lang]["new_user_log_no_ref"].format(
                    user_id=user.id,
                    username=user.username or "N/A",
                    full_name=user.full_name or "N/A"
                )
            await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=log_message, parse_mode='HTML')
        except Exception as e:
            logging.error(f"Could not log new user to channel: {e}")

    # Handle referral logic
    if referral_id:
        existing_referral = referrals_collection.find_one({"referred_user_id": user.id})
        
        if existing_referral:
            # If a referral already exists for this user, notify the current referrer
            referrer_lang = await get_user_lang(referral_id)
            try:
                await context.bot.send_message(
                    chat_id=referral_id,
                    text=MESSAGES[referrer_lang]["referral_already_exists"]
                )
            except (TelegramError, TimedOut) as e:
                logging.error(f"Could not send referral exists notification to {referral_id}: {e}")

        elif is_new_user:
            # This is a new user and a valid referral, so process it
            referrals_collection.insert_one({
                "referrer_id": referral_id,
                "referred_user_id": user.id,
                "referred_username": user.username,
                "join_date": datetime.now(),
            })
            
            # Add the referral bonus to the referrer's earnings
            referral_rate_usd = await get_referral_bonus_usd()
            users_collection.update_one(
                {"user_id": referral_id},
                {"$inc": {"earnings": referral_rate_usd}}
            )

            try:
                # Use a fallback username if none is available
                referred_username_display = f"@{user.username}" if user.username else f"(No username)"
                
                referrer_lang = await get_user_lang(referral_id)
                await context.bot.send_message(
                    chat_id=referral_id,
                    text=MESSAGES[referrer_lang]["new_referral_notification"].format(
                        full_name=user.full_name, username=referred_username_display
                    )
                )
            except (TelegramError, TimedOut) as e:
                logging.error(f"Could not notify referrer {referral_id}: {e}")


    # Send the main menu with earning panel and movie groups
    lang = await get_user_lang(user.id)
    keyboard = [
        # FIX: 'Movie Groups' बटन का callback_data जोड़ा गया
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
                
async def earn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (earn_command content is unchanged)
    user = update.effective_user
    lang = await get_user_lang(user.id)
    
    if not users_collection.find_one({"user_id": user.id}):
        users_collection.insert_one({
            "user_id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "lang": "en",
            "is_approved": True,
            "earnings": 0.0,
            "last_checkin_date": None
        })

    bot_info = await context.bot.get_me()
    bot_username = bot_info.username

    referral_link = f"https://t.me/{bot_username}?start=ref_{user.id}"

    message = (
        f"<b>{MESSAGES[lang]['earn_rules_title']}</b>\n\n"
        f"{MESSAGES[lang]['earn_rule1']}\n"
        f"{MESSAGES[lang]['earn_rule2']}\n"
        f"{MESSAGES[lang]['earn_rule3']}\n"
        f"{MESSAGES[lang]['earn_rule4']}\n\n"
        f"<b>Your Referral Link:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        f"<i>{MESSAGES[lang]['earnings_update']}</i>"
    )

    await update.message.reply_html(message)


async def show_earning_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (show_earning_panel content is unchanged)
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    keyboard = [
        [InlineKeyboardButton("My Refer Link", callback_data="show_refer_link")],
        [InlineKeyboardButton("💸 Withdraw", callback_data="show_withdraw_details_new")],
        [InlineKeyboardButton("🎁 Daily Bonus", callback_data="claim_daily_bonus")],
        [InlineKeyboardButton("Help", callback_data="show_help")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = MESSAGES[lang]["earning_panel_message"]
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (show_help content is unchanged)
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
    # ... (show_refer_link content is unchanged)
    query = update.callback_query
    await query.answer()
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    referral_link = f"https://t.me/{bot_username}?start=ref_{user.id}"
    
    message = (
        f"<b>Your Referral Link:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        f"<i>{MESSAGES[lang]['earnings_update']}</i>"
    )
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

    
async def show_withdraw_details_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (show_withdraw_details_new content is unchanged)
    query = update.callback_query
    await query.answer()

    user = query.from_user
    lang = await get_user_lang(user.id)
    user_data = users_collection.find_one({"user_id": user.id})

    if not user_data:
        await query.edit_message_text("User data not found.")
        return

    earnings = user_data.get("earnings", 0.0)
    earnings_inr = earnings * DOLLAR_TO_INR
    referrals_count = referrals_collection.count_documents({"referrer_id": user.id})
    
    withdraw_link = f"https://t.me/{YOUR_TELEGRAM_HANDLE}"
    
    keyboard = [
        [InlineKeyboardButton("💰 पैसे निकालने के लिए क्लिक करें", url=withdraw_link)],
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = (
        f"<b>{MESSAGES[lang]['withdrawal_message_updated']}</b>\n\n"
        f"<b>{MESSAGES[lang]['total_earnings']}</b> <b>₹{earnings_inr:.2f}</b>\n"
        f"<b>{MESSAGES[lang]['total_referrals']}</b> <b>{referrals_count}</b>\n\n"
    )

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def claim_daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (claim_daily_bonus content is unchanged)
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
    
    if last_checkin_date and last_checkin_date.date() == today:
        await query.edit_message_text(
            MESSAGES[lang]["daily_bonus_already_claimed"],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
        )
    else:
        bonus_inr = 0.10
        bonus_usd = bonus_inr / DOLLAR_TO_INR
        new_balance = user_data.get("earnings", 0.0) + bonus_usd
        
        users_collection.update_one(
            {"user_id": user.id},
            {"$set": {"last_checkin_date": datetime.now(), "earnings": new_balance}}
        )

        await query.edit_message_text(
            MESSAGES[lang]["daily_bonus_success"].format(new_balance=new_balance * DOLLAR_TO_INR),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
        )

# FIX: यह नया फ़ंक्शन 'Movie Groups' बटन के क्लिक को हैंडल करेगा
async def show_movie_groups_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    lang = await get_user_lang(query.from_user.id)

    # मूवी ग्रुप्स के लिंक वाले बटन
    # MOVIE_GROUP_LINK अब सही होना चाहिए
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
        # मुख्य मेन्यू में 'Movie Groups' बटन का callback_data सुनिश्चित किया गया
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
    
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (admin_panel content is unchanged)
    user = update.effective_user
    lang = await get_user_lang(user.id)

    if user.id != ADMIN_ID:
        await update.message.reply_text(MESSAGES[lang]["broadcast_admin_only"])
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Bot Stats", callback_data="admin_stats"),
         InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🗑️ Clear User Earnings", callback_data="admin_clearearn")],
        [InlineKeyboardButton("🔍 Check User Stats", callback_data="admin_checkstats")],
        [InlineKeyboardButton("⚙️ Set Refer Rate", callback_data="admin_setrate")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(MESSAGES[lang]["admin_panel_title"], reply_markup=reply_markup)


async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (handle_admin_callbacks content is unchanged)
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    command = query.data
    
    if command == "admin_stats":
        total_users = users_collection.count_documents({})
        approved_users = users_collection.count_documents({"is_approved": True})
        message = MESSAGES[lang]["stats_message"].format(total_users=total_users, approved_users=approved_users)
        await query.edit_message_text(message)
    elif command == "admin_broadcast":
        message = MESSAGES[lang]["broadcast_message"]
        await query.edit_message_text(message)
    elif command == "admin_clearearn":
        message = MESSAGES[lang]["clear_earn_usage"]
        await query.edit_message_text(message)
    elif command == "admin_checkstats":
        message = MESSAGES[lang]["check_stats_usage"]
        await query.edit_message_text(message)
    elif command == "admin_setrate":
        message = MESSAGES[lang]["setrate_usage"]
        await query.edit_message_text(message)


async def set_referral_rate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (set_referral_rate_command content is unchanged)
    user = update.effective_user
    lang = await get_user_lang(user.id)

    if user.id != ADMIN_ID:
        await update.message.reply_html(MESSAGES[lang]["broadcast_admin_only"])
        return

    if len(context.args) != 1:
        await update.message.reply_html(MESSAGES[lang]["setrate_usage"])
        return

    try:
        new_rate_inr = float(context.args[0])
        settings_collection.update_one(
            {"_id": "referral_rate"},
            {"$set": {"rate_inr": new_rate_inr}},
            upsert=True
        )
        await update.message.reply_html(
            MESSAGES[lang]["setrate_success"].format(new_rate=new_rate_inr)
        )
    except ValueError:
        await update.message.reply_html(MESSAGES[lang]["invalid_rate"])


async def clear_earn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (clear_earn_command content is unchanged)
    user = update.effective_user
    lang = await get_user_lang(user.id)

    if user.id != ADMIN_ID:
        await update.message.reply_html(MESSAGES[lang]["broadcast_admin_only"])
        return

    if len(context.args) != 1:
        await update.message.reply_html(MESSAGES[lang]["clear_earn_usage"])
        return

    try:
        target_user_id = int(context.args[0])
        result = users_collection.update_one(
            {"user_id": target_user_id},
            {"$set": {"earnings": 0.0}}
        )
        if result.modified_count > 0:
            await update.message.reply_html(MESSAGES[lang]["clear_earn_success"].format(user_id=target_user_id))
        else:
            await update.message.reply_html(MESSAGES[lang]["clear_earn_not_found"].format(user_id=target_user_id))
    except ValueError:
        await update.message.reply_html(MESSAGES[lang]["clear_earn_usage"])
        
async def check_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (check_stats_command content is unchanged)
    user = update.effective_user
    lang = await get_user_lang(user.id)

    if user.id != ADMIN_ID:
        await update.message.reply_html(MESSAGES[lang]["broadcast_admin_only"])
        return

    if len(context.args) != 1:
        await update.message.reply_html(MESSAGES[lang]["check_stats_usage"])
        return

    try:
        target_user_id = int(context.args[0])
        user_data = users_collection.find_one({"user_id": target_user_id})

        if user_data:
            earnings = user_data.get("earnings", 0.0)
            earnings_inr = earnings * DOLLAR_TO_INR
            referrals = referrals_collection.count_documents({"referrer_id": target_user_id})

            # The currency symbol and conversion have been fixed here
            message = MESSAGES[lang]["check_stats_message"].format(
                user_id=target_user_id,
                earnings=earnings_inr,
                referrals=referrals
            )
            await update.message.reply_html(message)
        else:
            await update.message.reply_html(MESSAGES[lang]["check_stats_not_found"].format(user_id=target_user_id))
    except ValueError:
        await update.message.reply_html(MESSAGES[lang]["check_stats_usage"])
        
async def checkbot_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (checkbot_command content is unchanged)
    user = update.effective_user
    lang = await get_user_lang(user.id)
    
    try:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Testing connection...", parse_mode='HTML')
        await update.message.reply_html(MESSAGES[lang]["checkbot_success"])
    except Exception as e:
        logging.error(f"Bot is not connected: {e}")
        await update.message.reply_html(MESSAGES[lang]["checkbot_failure"])
        
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (stats_command content is unchanged)
    user = update.effective_user
    lang = await get_user_lang(user.id)
    
    if user.id != ADMIN_ID:
        await update.message.reply_html(MESSAGES[lang]["broadcast_admin_only"])
        return

    total_users = users_collection.count_documents({})
    approved_users = users_collection.count_documents({"is_approved": True})
    
    await update.message.reply_html(
        MESSAGES[lang]["stats_message"].format(
            total_users=total_users, approved_users=approved_users
        )
    )
    
# --- ब्रॉडकास्ट कमांड में सुधार (Broadcast Command Improvement) ---
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = await get_user_lang(user.id)

    if user.id != ADMIN_ID:
        await update.message.reply_html(MESSAGES[lang]["broadcast_admin_only"])
        return

    if not update.message.reply_to_message:
        await update.message.reply_html(MESSAGES[lang]["broadcast_message"])
        return

    message_to_send = update.message.reply_to_message
    all_users = list(users_collection.find({}, {"user_id": 1}))
    
    await update.message.reply_html("ब्रॉडकास्ट संदेश भेजना शुरू हो रहा है...")

    sent_count = 0
    failed_count = 0
    
    # Send message sequentially with a small delay to avoid flood waits and high API load
    for user_doc in all_users:
        user_id = user_doc["user_id"]
        if user_id == ADMIN_ID:
            continue
        
        try:
            # Forward the message to the user
            await context.bot.forward_message(
                chat_id=user_id, 
                from_chat_id=update.effective_chat.id, 
                message_id=message_to_send.message_id
            )
            sent_count += 1
            # Wait for a small amount of time to reduce the load on the API
            await asyncio.sleep(0.05) # 50 milliseconds delay
            
        except TimedOut:
            # Handle timeout error if the request takes too long
            failed_count += 1
            logging.error(f"Timed out while broadcasting to user {user_id}. Retrying after a short delay.")
            await asyncio.sleep(1) # Wait longer after a timeout
        except TelegramError as e:
            # Handle other Telegram errors (e.g., bot was blocked by the user)
            failed_count += 1
            logging.error(f"Could not broadcast message to user {user_id}: {e}")
            # If the error is a FloodWait, the error object might have the retry_after field
            if 'retry_after' in str(e):
                logging.warning(f"Hit flood wait. Sleeping for {e.retry_after} seconds.")
                await asyncio.sleep(e.retry_after + 1) # Wait for the suggested time plus 1 second
            
        except Exception as e:
            # Handle other potential errors
            failed_count += 1
            logging.error(f"An unexpected error occurred while broadcasting to user {user_id}: {e}")
            await asyncio.sleep(0.5) # Small delay for unexpected errors

    await update.message.reply_html(
        MESSAGES[lang]["broadcast_success"].format(count=sent_count) + 
        f"\n❌ विफल संदेश (Failed): {failed_count} users"
    )
# --- ब्रॉडकास्ट कमांड सुधार समाप्त ---


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
    
# FIX: भाषा बदलने के बाद मेन्यू को अपडेट करने के लिए लॉजिक जोड़ा गया
async def handle_lang_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    lang = query.data.split("_")[1]
    await set_user_lang(query.from_user.id, lang)
    
    # Re-create the main start message with the new language
    # FIX: नए lang के साथ मेन्यू बटनों को अपडेट करें
    keyboard = [
        # मुख्य मेन्यू में 'Movie Groups' बटन का callback_data सुनिश्चित किया गया
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
        
async def add_payment_after_delay(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    # ... (add_payment_after_delay content is unchanged)
    await asyncio.sleep(300)
    
    user_data = users_collection.find_one({"user_id": user_id})
    if user_data:
        referral_data = referrals_collection.find_one({"referred_user_id": user.id})
        
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
                
                if not last_earning_date or last_earning_date.date() < today:
                    earning_rate_usd = await get_referral_bonus_usd()
                    new_balance = referrer_data.get('earnings', 0) + earning_rate_usd
                    
                    users_collection.update_one(
                        {"user_id": referrer_id},
                        {"$inc": {"earnings": earning_rate_usd}}
                    )

                    referrals_collection.update_one(
                        {"referred_user_id": user_id},
                        {"$set": {"last_earning_date": datetime.now()}}
                    )
                    
                    new_balance_inr = new_balance * DOLLAR_TO_INR

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
                        logging.error(f"Could not send daily earning update to referrer {referrer_id}: {e}")
                        
                    logging.info(f"Updated earnings for referrer {referrer_id}. New balance: {new_balance}")
                else:
                    logging.info(f"Daily earning limit reached for referrer {referrer_id} from user {user_id}. No new payment scheduled.")

async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (handle_group_messages content is unchanged)
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type in ["group", "supergroup"]:
        logging.info(f"Message received in group from user: {user.id}")

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

                if not last_earning_date or last_earning_date.date() < today:
                    asyncio.create_task(add_payment_after_delay(context, user.id))
                    logging.info(f"Payment task scheduled for user {user.id} after 5 minutes.")
                else:
                    logging.info(f"Daily earning limit reached for referrer {referrer_id} from user {user.id}. No new payment scheduled.")


def main() -> None:
    """Start the bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    # Command Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("earn", earn_command))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("clearearn", clear_earn_command))
    application.add_handler(CommandHandler("checkstats", check_stats_command))
    application.add_handler(CommandHandler("checkbot", checkbot_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("setrate", set_referral_rate_command))
    
    # Callback Handlers
    application.add_handler(CallbackQueryHandler(show_earning_panel, pattern="^show_earning_panel$"))
    # FIX: 'Movie Groups' बटन के लिए हैंडलर जोड़ा गया
    application.add_handler(CallbackQueryHandler(show_movie_groups_menu, pattern="^show_movie_groups_menu$"))
    application.add_handler(CallbackQueryHandler(back_to_main_menu, pattern="^back_to_main_menu$"))
    application.add_handler(CallbackQueryHandler(language_menu, pattern="^select_lang$"))
    application.add_handler(CallbackQueryHandler(handle_lang_choice, pattern="^lang_"))
    application.add_handler(CallbackQueryHandler(show_help, pattern="^show_help$"))
    application.add_handler(CallbackQueryHandler(show_refer_link, pattern="^show_refer_link$"))
    application.add_handler(CallbackQueryHandler(show_withdraw_details_new, pattern="^show_withdraw_details_new$"))
    application.add_handler(CallbackQueryHandler(claim_daily_bonus, pattern="^claim_daily_bonus$"))
    application.add_handler(CallbackQueryHandler(handle_admin_callbacks, pattern="^admin_"))
    
    # Group Message Handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_group_messages))

    # Start the Bot in webhook mode
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=f"/{BOT_TOKEN}",
        webhook_url=f"{WEB_SERVER_URL}/{BOT_TOKEN}",
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == "__main__":
    main()
