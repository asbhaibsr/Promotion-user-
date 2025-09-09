import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from pymongo import MongoClient
from datetime import datetime
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
ADMIN_ID = int(os.getenv("ADMIN_ID"))
YOUR_TELEGRAM_HANDLE = os.getenv("YOUR_TELEGRAM_HANDLE")
# Updated movie group links
MOVIE_GROUP_LINK = "https://t.me/movies_searchh_group"
ALL_GROUPS_LINK = "https://t.me/addlist/EOSX8n4AoC1jYWU1"

# Load Render-specific variables
WEB_SERVER_URL = os.getenv("WEB_SERVER_URL")
PORT = int(os.getenv("PORT", 8000))

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client.get_database('bot_database')
users_collection = db.get_collection('users')
referrals_collection = db.get_collection('referrals')

# Dictionaries for multi-language support (आपका पूरा MESSAGES डिक्ट यहीं रहेगा)
MESSAGES = {
    "en": {
        "start_greeting": "Hey 👋! Welcome to the Movies Group Bot. Get your favorite movies by following these simple steps:",
        "start_step1": "Click the button below to join our movie group.",
        "start_step2": "Go to the group and type the name of the movie you want.",
        "start_step3": "The bot will give you a link to your movie.",
        "start_group_button": "Join Movies Group",
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
        "check_stats_message": "Stats for user {user_id}:\n\nTotal Earnings: ${earnings:.4f}\nTotal Referrals: {referrals}",
        "check_stats_not_found": "❌ User with ID {user_id} not found.",
        "check_stats_usage": "❌ Usage: /checkstats <user_id>",
        "referral_already_exists": "This user has already been referred by someone else. You cannot get any benefits from this referral.",
    },
    "hi": {
        "start_greeting": "नमस्ते 👋! मूवी ग्रुप बॉट में आपका स्वागत है। इन आसान स्टेप्स को फॉलो करके अपनी पसंदीदा मूवी पाएँ:",
        "start_step1": "हमारे मूवी ग्रुप में शामिल होने के लिए नीचे दिए गए बटन पर क्लिक करें।",
        "start_step2": "ग्रुप में जाकर अपनी मनपसंद मूवी का नाम लिखें।",
        "start_step3": "बॉट आपको आपकी मूवी की लिंक देगा।",
        "start_group_button": "मूवी ग्रुप जॉइन करें",
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
        "referral_already_exists": "यह उपयोगकर्ता पहले ही किसी और के द्वारा रेफर किया जा चुका है। इसलिए, आप इस रेफरल से कोई लाभ नहीं उठा सकते हैं।"
    }
}

# Conversion rate (assuming a static rate for simplicity)
DOLLAR_TO_INR = 83.0
# NEW: Referral bonus in USD (₹0.40)
REFERRAL_BONUS_USD = 0.40 / DOLLAR_TO_INR

# ADD THIS VARIABLE FOR YOUR LOGGING CHANNEL
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")

async def get_user_lang(user_id):
    """Fetches user's language preference from the database."""
    user_data = users_collection.find_one({"user_id": user_id})
    return user_data.get("lang", "en") if user_data else "en"

async def set_user_lang(user_id, lang):
    """Sets user's language preference in the database."""
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
            "earnings": 0.0
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
            await context.bot.send_message(
                chat_id=referral_id,
                text=MESSAGES[referrer_lang]["referral_already_exists"]
            )
        elif is_new_user:
            # This is a new user and a valid referral, so process it
            referrals_collection.insert_one({
                "referrer_id": referral_id,
                "referred_user_id": user.id,
                "referred_username": user.username,
                "join_date": datetime.now(),
            })
            
            # Add the referral bonus to the referrer's earnings
            users_collection.update_one(
                {"user_id": referral_id},
                {"$inc": {"earnings": REFERRAL_BONUS_USD}}
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
            except Exception as e:
                logging.error(f"Could not notify referrer {referral_id}: {e}")

    # Send the first message (earning details)
    earn_keyboard = [
        [InlineKeyboardButton("Help", callback_data="show_help")],
        [InlineKeyboardButton("My Refer Link", callback_data="show_refer_link")],
        [InlineKeyboardButton("Withdraw", callback_data="show_withdraw_details_new")]
    ]
    earn_reply_markup = InlineKeyboardMarkup(earn_keyboard)
    
    earn_message = MESSAGES[lang]["earn_message"]
    
    await update.message.reply_text(earn_message, reply_markup=earn_reply_markup)

    # Send the second message (movie group details)
    keyboard = [
        [InlineKeyboardButton(MESSAGES[lang]["start_group_button"], url=MOVIE_GROUP_LINK)],
        [InlineKeyboardButton("Join All Movie Groups", url=ALL_GROUPS_LINK)],
        [InlineKeyboardButton(MESSAGES[lang]["earn_button"], callback_data="show_earn_details")],
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
    user = update.effective_user
    lang = await get_user_lang(user.id)
    
    if not users_collection.find_one({"user_id": user.id}):
        users_collection.insert_one({
            "user_id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "lang": "en",
            "is_approved": True,
            "earnings": 0.0
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

async def show_earn_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user = query.from_user
    lang = await get_user_lang(user.id)
    
    message = (
        f"<b>{MESSAGES[lang]['earn_rules_title']}</b>\n\n"
        f"{MESSAGES[lang]['earn_rule1']}\n"
        f"{MESSAGES[lang]['earn_rule2']}\n"
        f"{MESSAGES[lang]['earn_rule3']}\n"
        f"{MESSAGES[lang]['earn_rule4']}\n\n"
        f"{MESSAGES[lang]['earn_command_info']}"
    )
    
    earn_keyboard = [
        [InlineKeyboardButton("Help", callback_data="show_help")],
        [InlineKeyboardButton("My Refer Link", callback_data="show_refer_link")],
        [InlineKeyboardButton("Withdraw", callback_data="show_withdraw_details_new")]
    ]
    earn_reply_markup = InlineKeyboardMarkup(earn_keyboard)

    await query.edit_message_text(message, reply_markup=earn_reply_markup, parse_mode='HTML')

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = await get_user_lang(query.from_user.id)
    help_message = "Help message content goes here."
    await query.edit_message_text(help_message)

async def show_refer_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    await query.edit_message_text(message, parse_mode='HTML')
    
async def show_withdraw_details_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    
    if earnings_inr >= 80:
        keyboard = [
            [InlineKeyboardButton(MESSAGES[lang]["contact_admin_button"], url=withdraw_link)]
        ]
    else:
        keyboard = []
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = (
        f"<b>{MESSAGES[lang]['withdrawal_details_title']}</b>\n\n"
        f"<b>{MESSAGES[lang]['total_earnings']}</b> <b>₹{earnings_inr:.2f}</b>\n"
        f"<b>{MESSAGES[lang]['total_referrals']}</b> <b>{referrals_count}</b>\n\n"
        f"<b>{MESSAGES[lang]['withdrawal_info']}</b>"
    )

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def back_to_earn_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pass

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = await get_user_lang(user.id)
    user_data = users_collection.find_one({"user_id": user.id})

    if not user_data:
        users_collection.insert_one({
            "user_id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "lang": "en",
            "is_approved": True,
            "earnings": 0.0
        })

    keyboard = [[InlineKeyboardButton(MESSAGES[lang]["withdraw_button"], callback_data="show_withdraw_details")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(MESSAGES[lang]["withdrawal_message"], reply_markup=reply_markup)

async def show_withdraw_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    
    if earnings_inr >= 80:
        keyboard = [
            [InlineKeyboardButton(MESSAGES[lang]["contact_admin_button"], url=withdraw_link)],
            [InlineKeyboardButton("← Back", callback_data="back_to_withdraw_menu")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("← Back", callback_data="back_to_withdraw_menu")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = (
        f"<b>{MESSAGES[lang]['withdrawal_details_title']}</b>\n\n"
        f"<b>{MESSAGES[lang]['total_earnings']}</b> <b>₹{earnings_inr:.2f}</b>\n"
        f"<b>{MESSAGES[lang]['total_referrals']}</b> <b>{referrals_count}</b>\n\n"
        f"<b>{MESSAGES[lang]['withdrawal_info']}</b>"
    )

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

async def back_to_withdraw_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user = query.from_user
    lang = await get_user_lang(user.id)
    
    keyboard = [[InlineKeyboardButton(MESSAGES[lang]["withdraw_button"], callback_data="show_withdraw_details")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(MESSAGES[lang]["withdrawal_message"], reply_markup=reply_markup, parse_mode='HTML')

async def clear_earn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = await get_user_lang(user.id)

    if user.id != ADMIN_ID:
        await update.message.reply_text(MESSAGES[lang]["broadcast_admin_only"])
        return

    if len(context.args) != 1:
        await update.message.reply_text(MESSAGES[lang]["clear_earn_usage"])
        return

    try:
        target_user_id = int(context.args[0])
        result = users_collection.update_one(
            {"user_id": target_user_id},
            {"$set": {"earnings": 0.0}}
        )
        if result.modified_count > 0:
            await update.message.reply_text(MESSAGES[lang]["clear_earn_success"].format(user_id=target_user_id))
        else:
            await update.message.reply_text(MESSAGES[lang]["clear_earn_not_found"].format(user_id=target_user_id))
    except ValueError:
        await update.message.reply_text(MESSAGES[lang]["clear_earn_usage"])
        
async def check_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = await get_user_lang(user.id)

    if user.id != ADMIN_ID:
        await update.message.reply_text(MESSAGES[lang]["broadcast_admin_only"])
        return

    if len(context.args) != 1:
        await update.message.reply_text(MESSAGES[lang]["check_stats_usage"])
        return

    try:
        target_user_id = int(context.args[0])
        user_data = users_collection.find_one({"user_id": target_user_id})

        if user_data:
            earnings = user_data.get("earnings", 0.0)
            earnings_inr = earnings * DOLLAR_TO_INR
            referrals = referrals_collection.count_documents({"referrer_id": target_user_id})

            message = MESSAGES[lang]["check_stats_message"].format(
                user_id=target_user_id,
                earnings=earnings_inr,
                referrals=referrals
            )
            await update.message.reply_text(message)
        else:
            await update.message.reply_text(MESSAGES[lang]["check_stats_not_found"].format(user_id=target_user_id))
    except ValueError:
        await update.message.reply_text(MESSAGES[lang]["check_stats_usage"])
        
async def checkbot_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = await get_user_lang(user.id)
    
    try:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Testing connection...")
        await update.message.reply_text(MESSAGES[lang]["checkbot_success"])
    except Exception as e:
        logging.error(f"Bot is not connected: {e}")
        await update.message.reply_text(MESSAGES[lang]["checkbot_failure"])
        
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = await get_user_lang(user.id)
    
    if user.id != ADMIN_ID:
        await update.message.reply_text(MESSAGES[lang]["broadcast_admin_only"])
        return

    total_users = users_collection.count_documents({})
    approved_users = users_collection.count_documents({"is_approved": True})
    
    await update.message.reply_text(
        MESSAGES[lang]["stats_message"].format(
            total_users=total_users, approved_users=approved_users
        )
    )
    
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = await get_user_lang(user.id)

    if user.id != ADMIN_ID:
        await update.message.reply_text(MESSAGES[lang]["broadcast_admin_only"])
        return

    if not update.message.reply_to_message:
        await update.message.reply_text(MESSAGES[lang]["broadcast_message"])
        return

    message_to_send = update.message.reply_to_message
    all_users = list(users_collection.find({}, {"user_id": 1}))
    tasks = []
    
    await update.message.reply_text("Sending broadcast message...")

    for user_doc in all_users:
        user_id = user_doc["user_id"]
        if user_id == ADMIN_ID:
            continue
        # Create a task for each user to send the message concurrently
        tasks.append(
            context.bot.forward_message(
                chat_id=user_id, 
                from_chat_id=update.effective_chat.id, 
                message_id=message_to_send.message_id
            )
        )
    
    sent_count = 0
    failed_count = 0
    
    # Use asyncio.gather to run all tasks concurrently and handle exceptions
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, TelegramError):
            failed_count += 1
            logging.error(f"Could not broadcast message to a user: {result}")
        else:
            sent_count += 1
    
    await update.message.reply_text(f"✅ Broadcast finished!\n\nSent to: {sent_count} users\nFailed: {failed_count} users")


async def language_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("English 🇬🇧", callback_data="lang_en")],
        [InlineKeyboardButton("हिन्दी 🇮🇳", callback_data="lang_hi")],
        [InlineKeyboardButton("← Back", callback_data="back_to_start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    lang = await get_user_lang(query.from_user.id)
    await query.edit_message_text(text=MESSAGES[lang]["language_choice"], reply_markup=reply_markup)
    
async def handle_lang_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    lang = query.data.split("_")[1]
    await set_user_lang(query.from_user.id, lang)
    
    # Re-create the main start message with the new language
    keyboard = [
        [InlineKeyboardButton(MESSAGES[lang]["start_group_button"], url=MOVIE_GROUP_LINK)],
        [InlineKeyboardButton("Join All Movie Groups", url=ALL_GROUPS_LINK)],
        [InlineKeyboardButton(MESSAGES[lang]["earn_button"], callback_data="show_earn_details")],
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
        
async def handle_back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_data = users_collection.find_one({"user_id": user.id})
    lang = user_data.get("lang", "en")

    keyboard = [
        [InlineKeyboardButton(MESSAGES[lang]["start_group_button"], url=MOVIE_GROUP_LINK)],
        [InlineKeyboardButton("Join All Movie Groups", url=ALL_GROUPS_LINK)],
        [InlineKeyboardButton(MESSAGES[lang]["earn_button"], callback_data="show_earn_details")],
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
    await asyncio.sleep(300)
    
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
                
                if not last_earning_date or last_earning_date.date() < today:
                    earnings_to_add = 0.0018
                    new_balance = referrer_data.get('earnings', 0) + earnings_to_add
                    
                    users_collection.update_one(
                        {"user_id": referrer_id},
                        {"$inc": {"earnings": earnings_to_add}}
                    )

                    referrals_collection.update_one(
                        {"referred_user_id": user_id},
                        {"$set": {"last_earning_date": datetime.now()}}
                    )
                    
                    new_balance_inr = new_balance * DOLLAR_TO_INR

                    referrer_lang = await get_user_lang(referrer_id)
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=MESSAGES[referrer_lang]["daily_earning_update"].format(
                            full_name=user_data.get("full_name"), new_balance=new_balance_inr
                        ),
                        parse_mode='HTML'
                    )
                    logging.info(f"Updated earnings for referrer {referrer_id}. New balance: {new_balance}")
                else:
                    logging.info(f"Daily earning limit reached for referrer {referrer_id} from user {user_id}. No new payment scheduled.")

async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    application.add_handler(CommandHandler("withdraw", withdraw_command))
    application.add_handler(CommandHandler("clearearn", clear_earn_command))
    application.add_handler(CommandHandler("checkstats", check_stats_command))
    application.add_handler(CommandHandler("checkbot", checkbot_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    
    # Callback Handlers
    application.add_handler(CallbackQueryHandler(language_menu, pattern="^select_lang$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_start, pattern="^back_to_start$"))
    application.add_handler(CallbackQueryHandler(handle_lang_choice, pattern="^lang_"))
    application.add_handler(CallbackQueryHandler(show_earn_details, pattern="^show_earn_details$"))
    application.add_handler(CallbackQueryHandler(show_help, pattern="^show_help$"))
    application.add_handler(CallbackQueryHandler(show_refer_link, pattern="^show_refer_link$"))
    application.add_handler(CallbackQueryHandler(show_withdraw_details_new, pattern="^show_withdraw_details_new$"))
    application.add_handler(CallbackQueryHandler(back_to_earn_menu, pattern="^back_to_earn_menu$"))
    application.add_handler(CallbackQueryHandler(show_withdraw_details, pattern="^show_withdraw_details$"))
    application.add_handler(CallbackQueryHandler(back_to_withdraw_menu, pattern="^back_to_withdraw_menu$"))
    
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
