import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
        "earn_message": "Click the button below to get your referral link and rules:",
        "earn_button": "💰 Get Referral Link & Rules",
        "earn_rules_title": "💰 Rules for Earning",
        "earn_rule1": "➡️ Get people to join our group using your link.",
        "earn_rule2": "➡️ When your referred user searches for a movie in the group, they'll be taken to our bot via a shortlink.",
        "earn_rule3": "➡️ After they complete the shortlink process, you'll earn money. Note that you earn only <b>once per day</b> per referred user.",
        "earnings_breakdown": "Earnings Breakdown:",
        "owner_share": "Owner's Share:",
        "your_share": "Your Share:",
        "earnings_update": "Your earnings will automatically update in your account.",
        "withdrawal_message": "Click the button below to see your withdrawal details:",
        "withdraw_button": "💸 Withdrawal Details",
        "withdrawal_details_title": "💰 Withdrawal Details 💰",
        "withdrawal_info": "Withdrawals are only possible via UPI ID, QR code, or bank account.\nYou can withdraw a maximum of $1 per month.",
        "total_earnings": "Total Earnings:",
        "total_referrals": "Total Referrals:",
        "active_earners": "Active Earners Today:",
        "contact_admin_text": "Click the button below to contact the admin for withdrawal.",
        "contact_admin_button": "Contact Admin",
        "new_referral_notification": "🥳 Good news! A new user has joined through your link: {full_name} (@{username}).",
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
        "earn_message": "अपनी रेफरल लिंक और नियम पाने के लिए नीचे दिए गए बटन पर क्लिक करें:",
        "earn_button": "💰 रेफरल लिंक और नियम पाएँ",
        "earn_rules_title": "💰 कमाई के नियम",
        "earn_rule1": "➡️ अपनी लिंक का उपयोग करके लोगों को हमारे ग्रुप में शामिल करें।",
        "earn_rule2": "➡️ जब आपका रेफर किया गया यूजर ग्रुप में किसी मूवी को खोजता है, तो उसे शॉर्टलिंक के जरिए हमारे बॉट पर ले जाया जाएगा।",
        "earn_rule3": "➡️ जब वे शॉर्टलिंक प्रक्रिया पूरी कर लेंगे, तो आपको पैसे मिलेंगे। ध्यान दें कि आप प्रति रेफर किए गए यूजर से केवल <b>एक बार प्रति दिन</b> कमा सकते हैं।",
        "earnings_breakdown": "कमाई का विवरण:",
        "owner_share": "मालिक का हिस्सा:",
        "your_share": "आपका हिस्सा:",
        "earnings_update": "आपकी कमाई स्वचालित रूप से आपके खाते में अपडेट हो जाएगी।",
        "withdrawal_message": "निकासी के विवरण देखने के लिए नीचे दिए गए बटन पर क्लिक करें:",
        "withdraw_button": "💸 निकासी का विवरण",
        "withdrawal_details_title": "💰 निकासी का विवरण 💰",
        "withdrawal_info": "निकासी केवल UPI ID, QR कोड, या बैंक खाते के माध्यम से ही संभव है।\nआप हर महीने अधिकतम ₹80 या उससे अधिक होने पर ही निकाल सकते हैं।",
        "total_earnings": "कुल कमाई:",
        "total_referrals": "कुल रेफरल:",
        "active_earners": "आज के सक्रिय कमाने वाले:",
        "contact_admin_text": "निकासी के लिए एडमिन से संपर्क करने हेतु नीचे दिए गए बटन पर क्लिक करें।",
        "contact_admin_button": "एडमिन से संपर्क करें",
        "new_referral_notification": "🥳 खुशखबरी! एक नया यूजर आपकी लिंक से जुड़ा है: {full_name} (@{username})।",
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

    # Create the keyboard with the movie group button, all groups button, and earn money button
    keyboard = [
        [InlineKeyboardButton(MESSAGES[lang]["start_group_button"], url=MOVIE_GROUP_LINK)],
        [InlineKeyboardButton("Join All Movie Groups", url=ALL_GROUPS_LINK)],
        [InlineKeyboardButton("💰 Earn Money", callback_data="show_earn_details")],
        [InlineKeyboardButton(MESSAGES[lang]["language_choice"], callback_data="select_lang")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Construct the message with proper HTML tags for bold text
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
    
    # Check if user already exists in the database
    if not users_collection.find_one({"user_id": user.id}):
        # If user is not in the database, add them and set is_approved to True
        users_collection.insert_one({
            "user_id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "lang": "en",
            "is_approved": True,
            "earnings": 0.0
        })

    # Show the earning button for all users now
    keyboard = [
        [InlineKeyboardButton(MESSAGES[lang]["earn_button"], callback_data="show_earn_details")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(MESSAGES[lang]["earn_message"], reply_markup=reply_markup)

async def show_earn_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user = query.from_user
    lang = await get_user_lang(user.id)
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username

    referral_link = f"https://t.me/{bot_username}?start=ref_{user.id}"
    
    owner_share_usd = 0.006
    user_share_usd = 0.0018
    user_share_inr = user_share_usd * DOLLAR_TO_INR

    message = (
        f"<b>{MESSAGES[lang]['earn_rules_title']}</b>\n\n"
        f"<b>Your Referral Link:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        f"<b>Rules:</b>\n"
        f"1. {MESSAGES[lang]['earn_rule1']}\n"
        f"2. {MESSAGES[lang]['earn_rule2']}\n"
        f"3. {MESSAGES[lang]['earn_rule3']}\n\n"
        f"<b>{MESSAGES[lang]['earnings_breakdown']}</b>\n"
        f"<b>{MESSAGES[lang]['owner_share']}</b> ${owner_share_usd:.4f}\n"
        f"<b>{MESSAGES[lang]['your_share']}</b> ₹{user_share_inr:.2f}\n\n"
        f"<i>{MESSAGES[lang]['earnings_update']}</i>"
    )

    keyboard = [[InlineKeyboardButton("← Back", callback_data="back_to_earn_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

async def back_to_earn_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user = query.from_user
    lang = await get_user_lang(user.id)
    
    keyboard = [[InlineKeyboardButton(MESSAGES[lang]["earn_button"], callback_data="show_earn_details")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(MESSAGES[lang]["earn_message"], reply_markup=reply_markup, parse_mode='HTML')

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = await get_user_lang(user.id)
    user_data = users_collection.find_one({"user_id": user.id})

    if not user_data:
        # A new user who tries /withdraw first, create them
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
    
    # Check if earnings are >= 80 INR
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
    sent_count = 0
    failed_count = 0
    
    await update.message.reply_text("Sending broadcast message...")

    for user_doc in all_users:
        user_id = user_doc["user_id"]
        if user_id == ADMIN_ID:
            continue
        try:
            await context.bot.forward_message(chat_id=user_id, from_chat_id=update.effective_chat.id, message_id=message_to_send.message_id)
            sent_count += 1
        except Exception as e:
            logging.error(f"Could not broadcast message to user {user_id}: {e}")
            failed_count += 1
    
    if failed_count > 0:
        await update.message.reply_text(MESSAGES[lang]["broadcast_failed"].format(count=sent_count))
    else:
        await update.message.reply_text(MESSAGES[lang]["broadcast_success"].format(count=sent_count))

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
        [InlineKeyboardButton("💰 Earn Money", callback_data="show_earn_details")],
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
        [InlineKeyboardButton("💰 Earn Money", callback_data="show_earn_details")],
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
    
# Corrected NEW FUNCTION - This will run after the 5-minute delay
async def add_payment_after_delay(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    # Wait for 5 minutes (300 seconds) as per the user's request
    await asyncio.sleep(300)
    
    # After the delay, perform the payment logic
    user_data = users_collection.find_one({"user_id": user_id})
    if user_data:
        referral_data = referrals_collection.find_one({"referred_user_id": user_id})
        
        if referral_data:
            referrer_id = referral_data["referrer_id"]
            referrer_data = users_collection.find_one({"user_id": referrer_id}) # No is_approved check needed now
            
            if referrer_data:
                # Get the date of the last earning from this specific referred user
                last_earning_date_doc = referrals_collection.find_one({
                    "referred_user_id": user_id, 
                    "referrer_id": referrer_id
                })
                last_earning_date = last_earning_date_doc.get("last_earning_date") if last_earning_date_doc else None
                
                today = datetime.now().date()
                
                # Check if this referrer has already earned from this user today
                if not last_earning_date or last_earning_date.date() < today:
                    earnings_to_add = 0.0018
                    new_balance = referrer_data.get('earnings', 0) + earnings_to_add
                    
                    # Update earnings for the referrer and store the date of the payment
                    users_collection.update_one(
                        {"user_id": referrer_id},
                        {"$inc": {"earnings": earnings_to_add}}
                    )

                    # Update the referrals collection with the date of the successful payment
                    referrals_collection.update_one(
                        {"referred_user_id": user_id},
                        {"$set": {"last_earning_date": datetime.now()}}
                    )
                    
                    # Convert new balance to INR for the message
                    new_balance_inr = new_balance * DOLLAR_TO_INR

                    # Notify the referrer
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

# MODIFIED HANDLER - This will trigger the delayed task
async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    
    # Check if the message is in a group
    if chat.type in ["group", "supergroup"]:
        logging.info(f"Message received in group from user: {user.id}")

        # Find if this user was referred by someone
        referral_data = referrals_collection.find_one({"referred_user_id": user.id})
        
        if referral_data:
            referrer_id = referral_data["referrer_id"]
            referrer_data = users_collection.find_one({"user_id": referrer_id})
            
            if referrer_data:
                # Check if the referrer has already earned from this specific user today
                last_earning_date_doc = referrals_collection.find_one({
                    "referred_user_id": user.id, 
                    "referrer_id": referrer_id
                })
                last_earning_date = last_earning_date_doc.get("last_earning_date") if last_earning_date_doc else None
                today = datetime.now().date()

                if not last_earning_date or last_earning_date.date() < today:
                    # Create a new asyncio task to handle the delay and payment
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
    application.add_handler(CallbackQueryHandler(back_to_earn_menu, pattern="^back_to_earn_menu$"))
    application.add_handler(CallbackQueryHandler(show_withdraw_details, pattern="^show_withdraw_details$"))
    application.add_handler(CallbackQueryHandler(back_to_withdraw_menu, pattern="^back_to_withdraw_menu$"))
    
    # Group Message Handler (यह नया है)
    # This will trigger the payment after a delay
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
