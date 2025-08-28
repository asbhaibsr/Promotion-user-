import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv

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
MOVIE_GROUP_LINK = "https://t.me/addlist/EOSX8n4AoC1jYWU1"

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client.get_database('bot_database')
users_collection = db.get_collection('users')
referrals_collection = db.get_collection('referrals')

# Dictionaries for multi-language support
MESSAGES = {
    "en": {
        "start_greeting": "Hey 👋! Welcome to the Movies Group Bot. Get your favorite movies by following these simple steps:",
        "start_step1": "Click the button below to join our movie group.",
        "start_step2": "Go to the group and type the name of the movie you want.",
        "start_step3": "The bot will give you a link to your movie.",
        "start_group_button": "Join Movies Group",
        "language_choice": "Choose your language:",
        "language_selected": "Language changed to English.",
        "earn_approved_message": "You are approved! Click the button below to get your referral link and rules:",
        "earn_button": "💰 Get Referral Link & Rules",
        "earn_rules_title": "💰 Rules for Earning",
        "earn_rule1": "1. Get people to join our group using your link.",
        "earn_rule2": "2. When your referred user searches for a movie in the group, they'll be taken to our bot via a shortlink.",
        "earn_rule3": "3. After they complete the shortlink process, you'll earn money. Note that you earn only <b>once per day</b> per referred user.",
        "earnings_breakdown": "Earnings Breakdown:",
        "owner_share": "Owner's Share:",
        "your_share": "Your Share:",
        "earnings_update": "Your earnings will automatically update in your account.",
        "not_approved_earn": "Your request is pending. Please wait for the admin's approval.",
        "not_approved_withdraw": "You must be approved to use this command.",
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
        "approve_request": "New user {full_name} (@{username}, ID: {user_id}) wants to start earning. Approve?",
        "request_sent": "Your request has been sent to the admin for approval. Please wait.",
        "earning_approved": "Congratulations! You have been approved to earn. Use /earn to get your link.",
        "earning_denied": "Your request was not approved.",
        "user_approved_admin": "User {user_id} has been approved.",
        "user_cancelled_admin": "User {user_id}'s request has been cancelled.",
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
        "check_stats_message": "Stats for user {user_id}:\n\nTotal Earnings: ${earnings:.4f}\nTotal Referrals: {referrals}\nApproved: {is_approved}",
        "check_stats_not_found": "❌ User with ID {user_id} not found.",
        "check_stats_usage": "❌ Usage: /checkstats <user_id>"
    },
    "hi": {
        "start_greeting": "नमस्ते 👋! मूवी ग्रुप बॉट में आपका स्वागत है। इन आसान स्टेप्स को फॉलो करके अपनी पसंदीदा मूवी पाएँ:",
        "start_step1": "हमारे मूवी ग्रुप में शामिल होने के लिए नीचे दिए गए बटन पर क्लिक करें।",
        "start_step2": "ग्रुप में जाकर अपनी मनपसंद मूवी का नाम लिखें।",
        "start_step3": "बॉट आपको आपकी मूवी की लिंक देगा।",
        "start_group_button": "मूवी ग्रुप जॉइन करें",
        "language_choice": "अपनी भाषा चुनें:",
        "language_selected": "भाषा हिंदी में बदल दी गई है।",
        "earn_approved_message": "आप स्वीकृत हैं! अपनी रेफरल लिंक और नियम पाने के लिए नीचे दिए गए बटन पर क्लिक करें:",
        "earn_button": "💰 रेफरल लिंक और नियम पाएँ",
        "earn_rules_title": "💰 कमाई के नियम",
        "earn_rule1": "1. अपनी लिंक का उपयोग करके लोगों को हमारे ग्रुप में शामिल करें।",
        "earn_rule2": "2. जब आपका रेफर किया गया यूजर ग्रुप में किसी मूवी को खोजता है, तो उसे शॉर्टलिंक के जरिए हमारे बॉट पर ले जाया जाएगा।",
        "earn_rule3": "3. जब वे शॉर्टलिंक प्रक्रिया पूरी कर लेंगे, तो आपको पैसे मिलेंगे। ध्यान दें कि आप प्रति रेफर किए गए यूजर से केवल <b>एक बार प्रति दिन</b> कमा सकते हैं।",
        "earnings_breakdown": "कमाई का विवरण:",
        "owner_share": "मालिक का हिस्सा:",
        "your_share": "आपका हिस्सा:",
        "earnings_update": "आपकी कमाई स्वचालित रूप से आपके खाते में अपडेट हो जाएगी।",
        "not_approved_earn": "आपका अनुरोध लंबित है। कृपया एडमिन की स्वीकृति का इंतजार करें।",
        "not_approved_withdraw": "इस कमांड का उपयोग करने के लिए आपको स्वीकृत होना चाहिए।",
        "withdrawal_message": "निकासी के विवरण देखने के लिए नीचे दिए गए बटन पर क्लिक करें:",
        "withdraw_button": "💸 निकासी का विवरण",
        "withdrawal_details_title": "💰 निकासी का विवरण 💰",
        "withdrawal_info": "निकासी केवल UPI ID, QR कोड, या बैंक खाते के माध्यम से ही संभव है।\nआप हर महीने अधिकतम $1 निकाल सकते हैं।",
        "total_earnings": "कुल कमाई:",
        "total_referrals": "कुल रेफरल:",
        "active_earners": "आज के सक्रिय कमाने वाले:",
        "contact_admin_text": "निकासी के लिए एडमिन से संपर्क करने हेतु नीचे दिए गए बटन पर क्लिक करें।",
        "contact_admin_button": "एडमिन से संपर्क करें",
        "new_referral_notification": "🥳 खुशखबरी! एक नया यूजर आपकी लिंक से जुड़ा है: {full_name} (@{username})।",
        "approve_request": "नया यूजर {full_name} (@{username}, ID: {user_id}) कमाई शुरू करना चाहता है। क्या आप स्वीकृत करते हैं?",
        "request_sent": "आपका अनुरोध एडमिन को भेज दिया गया है। कृपया प्रतीक्षा करें।",
        "earning_approved": "बधाई हो! आपको कमाई करने के लिए स्वीकृत किया गया है। अपनी लिंक पाने के लिए /earn का उपयोग करें।",
        "earning_denied": "आपका अनुरोध स्वीकृत नहीं हुआ।",
        "user_approved_admin": "यूजर {user_id} को स्वीकृत कर दिया गया है।",
        "user_cancelled_admin": "यूजर {user_id} का अनुरोध रद्द कर दिया गया है।",
        "daily_earning_update": "🎉 <b>आपकी कमाई अपडेट हो गई है!</b>\n"
                                "एक रेफर किए गए यूजर ({full_name}) ने आज शॉर्टलिंक प्रक्रिया पूरी की।\n"
                                "आपका नया बैलेंस: ${new_balance:.4f}",
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
        "check_stats_message": "यूजर {user_id} के आंकड़े:\n\nकुल कमाई: ${earnings:.4f}\nकुल रेफरल: {referrals}\nस्वीकृत: {is_approved}",
        "check_stats_not_found": "❌ यूजर ID {user_id} नहीं मिला।",
        "check_stats_usage": "❌ उपयोग: /checkstats <user_id>"
    }
}

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
    referral_id = context.args[0].replace("ref_", "") if context.args and context.args[0].startswith("ref_") else None

    # Update or insert user data.
    users_collection.update_one(
        {"user_id": user.id},
        {"$setOnInsert": {
            "username": user.username,
            "full_name": user.full_name,
            "lang": "en",
            "is_approved": False,
            "earnings": 0.0
        }},
        upsert=True
    )

    user_data = users_collection.find_one({"user_id": user.id})
    lang = user_data.get("lang", "en")

    # Create the keyboard with the movie group button and language button
    keyboard = [
        [InlineKeyboardButton(MESSAGES[lang]["start_group_button"], url=MOVIE_GROUP_LINK)],
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

    # Referral logic remains the same
    if referral_id:
        referral_data = referrals_collection.find_one({"referred_user_id": user.id})
        if not referral_data:
            referrals_collection.insert_one({
                "referrer_id": int(referral_id),
                "referred_user_id": user.id,
                "referred_username": user.username,
                "join_date": datetime.now(),
                "is_active_earner": False
            })
            try:
                # Use a fallback username if none is available
                referred_username_display = f"@{user.username}" if user.username else f"(No username)"
                
                referrer_lang = await get_user_lang(int(referral_id))
                await context.bot.send_message(
                    chat_id=int(referral_id),
                    text=MESSAGES[referrer_lang]["new_referral_notification"].format(
                        full_name=user.full_name, username=referred_username_display
                    )
                )
            except Exception as e:
                logging.error(f"Could not notify referrer {referral_id}: {e}")

async def earn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = await get_user_lang(user.id)
    user_data = users_collection.find_one({"user_id": user.id})

    # Check if user already exists in the database
    if not user_data:
        # If user is not in the database, add them and send approval request
        users_collection.update_one(
            {"user_id": user.id},
            {"$setOnInsert": {
                "username": user.username,
                "full_name": user.full_name,
                "lang": "en",
                "is_approved": False,
                "earnings": 0.0
            }},
            upsert=True
        )
        keyboard = [
            [
                InlineKeyboardButton("Approve", callback_data=f"approve_{user.id}"),
                InlineKeyboardButton("Cancel", callback_data=f"cancel_{user.id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=MESSAGES["en"]["approve_request"].format(
                full_name=user.full_name, username=user.username, user_id=user.id
            ),
            reply_markup=reply_markup,
        )
        await update.message.reply_text(MESSAGES[lang]["request_sent"])

    elif user_data.get("is_approved"):
        # If user is approved, show the earning button
        keyboard = [
            [InlineKeyboardButton(MESSAGES[lang]["earn_button"], callback_data="show_earn_details")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_html(MESSAGES[lang]["earn_approved_message"], reply_markup=reply_markup)
    else:
        # If user is pending approval, show the pending message
        await update.message.reply_text(MESSAGES[lang]["not_approved_earn"])

async def show_earn_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user = query.from_user
    lang = await get_user_lang(user.id)
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username

    referral_link = f"https://t.me/{bot_username}?start=ref_{user.id}"
    
    # Corrected message title
    message = (
        f"<b>{MESSAGES[lang]['earn_rules_title']}</b>\n\n"
        f"<b>Your Referral Link:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        f"<b>Rules:</b>\n"
        f"1. {MESSAGES[lang]['earn_rule1']}\n"
        f"2. {MESSAGES[lang]['earn_rule2']}\n"
        f"3. {MESSAGES[lang]['earn_rule3']}\n\n"
        f"<b>{MESSAGES[lang]['earnings_breakdown']}</b>\n"
        f"<b>{MESSAGES[lang]['owner_share']}</b> $0.006\n"
        f"<b>{MESSAGES[lang]['your_share']}</b> $0.0018\n\n"
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
    
    await query.edit_message_text(MESSAGES[lang]["earn_approved_message"], reply_markup=reply_markup, parse_mode='HTML')

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = await get_user_lang(user.id)
    user_data = users_collection.find_one({"user_id": user.id, "is_approved": True})

    if not user_data:
        await update.message.reply_text(MESSAGES[lang]["not_approved_withdraw"])
        return

    keyboard = [[InlineKeyboardButton(MESSAGES[lang]["withdraw_button"], callback_data="show_withdraw_details")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(MESSAGES[lang]["withdrawal_message"], reply_markup=reply_markup)

async def show_withdraw_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user = query.from_user
    lang = await get_user_lang(user.id)
    user_data = users_collection.find_one({"user_id": user.id, "is_approved": True})

    if not user_data:
        # This case is a fallback, should not happen if the command check is right
        await query.edit_message_text(MESSAGES[lang]["not_approved_withdraw"])
        return

    earnings = user_data.get("earnings", 0.0)
    referrals_count = referrals_collection.count_documents({"referrer_id": user.id})
    active_earners_count = referrals_collection.count_documents({"referrer_id": user.id, "is_active_earner": True})
    
    withdraw_link = f"https://t.me/{YOUR_TELEGRAM_HANDLE}"

    keyboard = [
        [InlineKeyboardButton(MESSAGES[lang]["contact_admin_button"], url=withdraw_link)],
        [InlineKeyboardButton("← Back", callback_data="back_to_withdraw_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = (
        f"<b>{MESSAGES[lang]['withdrawal_details_title']}</b>\n\n"
        f"<b>{MESSAGES[lang]['total_earnings']}</b> <b>${earnings:.4f}</b>\n"
        f"<b>{MESSAGES[lang]['total_referrals']}</b> <b>{referrals_count}</b>\n"
        f"<b>{MESSAGES[lang]['active_earners']}</b> <b>{active_earners_count}</b>\n\n"
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
            is_approved = "Yes" if user_data.get("is_approved") else "No"
            referrals = referrals_collection.count_documents({"referrer_id": target_user_id})

            message = MESSAGES[lang]["check_stats_message"].format(
                user_id=target_user_id,
                earnings=earnings,
                referrals=referrals,
                is_approved=is_approved
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

async def handle_admin_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    action, user_id_str = query.data.split("_")
    user_id = int(user_id_str)
    admin_lang = await get_user_lang(query.from_user.id)

    if action == "approve":
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"is_approved": True, "earnings": 0.0}},
            upsert=True
        )
        user_lang = await get_user_lang(user_id)
        await context.bot.send_message(chat_id=user_id, text=MESSAGES[user_lang]["earning_approved"])
        await query.edit_message_text(text=MESSAGES[admin_lang]["user_approved_admin"].format(user_id=user_id))
    elif action == "cancel":
        users_collection.delete_one({"user_id": user_id})
        user_lang = await get_user_lang(user_id)
        await context.bot.send_message(chat_id=user_id, text=MESSAGES[user_lang]["earning_denied"])
        await query.edit_message_text(text=MESSAGES[admin_lang]["user_cancelled_admin"].format(user_id=user_id))

async def handle_back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_data = users_collection.find_one({"user_id": user.id})
    lang = user_data.get("lang", "en")

    keyboard = [
        [InlineKeyboardButton(MESSAGES[lang]["start_group_button"], url=MOVIE_GROUP_LINK)],
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

async def process_shortlink_completion(user_id):
    referred_user = await Application.bot.get_chat(user_id)
    referral_data = referrals_collection.find_one({"referred_user_id": user_id})

    if referral_data:
        referrer_id = referral_data["referrer_id"]
        referrer_data = users_collection.find_one({"user_id": referrer_id, "is_approved": True})
        
        if referrer_data:
            today = datetime.now().date()
            last_earning_date = referrer_data.get("last_earning_date")
            referrer_lang = await get_user_lang(referrer_id)
            
            if not last_earning_date or last_earning_date.date() < today:
                earnings_to_add = 0.0018
                new_balance = referrer_data.get('earnings', 0) + earnings_to_add
                
                users_collection.update_one(
                    {"user_id": referrer_id},
                    {"$inc": {"earnings": earnings_to_add}, "$set": {"last_earning_date": datetime.now()}}
                )
                referrals_collection.update_one(
                    {"referred_user_id": user_id},
                    {"$set": {"is_active_earner": True}}
                )
                await Application.bot.send_message(
                    chat_id=referrer_id,
                    text=MESSAGES[referrer_lang]["daily_earning_update"].format(
                        full_name=referred_user.full_name, new_balance=new_balance
                    ),
                    parse_mode='HTML'
                )
                logging.info(f"Updated earnings for referrer {referrer_id}. New balance: {new_balance}")
            else:
                await Application.bot.send_message(
                    chat_id=referrer_id,
                    text=MESSAGES[referrer_lang]["daily_earning_limit"]
                )

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
    
    # Callback Handlers (More structured)
    application.add_handler(CallbackQueryHandler(language_menu, pattern="^select_lang$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_start, pattern="^back_to_start$"))
    application.add_handler(CallbackQueryHandler(handle_lang_choice, pattern="^lang_"))
    application.add_handler(CallbackQueryHandler(handle_admin_approval, pattern="^(approve|cancel)_"))
    application.add_handler(CallbackQueryHandler(show_earn_details, pattern="^show_earn_details$"))
    application.add_handler(CallbackQueryHandler(back_to_earn_menu, pattern="^back_to_earn_menu$"))
    application.add_handler(CallbackQueryHandler(show_withdraw_details, pattern="^show_withdraw_details$"))
    application.add_handler(CallbackQueryHandler(back_to_withdraw_menu, pattern="^back_to_withdraw_menu$"))
    
    # Start the Bot
    application.run_polling()

if __name__ == "__main__":
    main()
