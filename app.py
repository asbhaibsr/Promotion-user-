import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
YOUR_TELEGRAM_HANDLE = os.getenv("YOUR_TELEGRAM_HANDLE")
MOVIE_GROUP_LINK = "https://t.me/addlist/EOSX8n4AoC1jYWU1" # Your specific movie group link

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client.get_database('bot_database')
users_collection = db.get_collection('users')
referrals_collection = db.get_collection('referrals')

# Flask app for Render
app = Flask(__name__)

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
        "earn_approved": "You are approved! Here is your referral link:",
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
        "withdrawal_details_title": "💰 Withdrawal Details 💰",
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
    },
    "hi": {
        "start_greeting": "नमस्ते 👋! मूवी ग्रुप बॉट में आपका स्वागत है। इन आसान स्टेप्स को फॉलो करके अपनी पसंदीदा मूवी पाएँ:",
        "start_step1": "हमारे मूवी ग्रुप में शामिल होने के लिए नीचे दिए गए बटन पर क्लिक करें।",
        "start_step2": "ग्रुप में जाकर अपनी मनपसंद मूवी का नाम लिखें।",
        "start_step3": "बॉट आपको आपकी मूवी की लिंक देगा।",
        "start_group_button": "मूवी ग्रुप जॉइन करें",
        "language_choice": "अपनी भाषा चुनें:",
        "language_selected": "भाषा हिंदी में बदल दी गई है।",
        "earn_approved": "आप स्वीकृत हैं! आपकी रेफरल लिंक यहाँ है:",
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
        "withdrawal_details_title": "💰 निकासी का विवरण 💰",
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
                # --- START OF FIX ---
                # Use a fallback username if none is available
                referred_username_display = f"@{user.username}" if user.username else f"(कोई यूजरनेम नहीं)"
                # --- END OF FIX ---
                
                referrer_lang = await get_user_lang(int(referral_id))
                await context.bot.send_message(
                    chat_id=int(referral_id),
                    text=MESSAGES[referrer_lang]["new_referral_notification"].format(
                        full_name=user.full_name, username=referred_username_display
                    )
                )
            except Exception as e:
                logging.error(f"Could not notify referrer {referral_id}: {e}")

async def send_start_message_with_lang(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str) -> None:
    user = update.effective_user
    
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

    await update.message.edit_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def earn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = await get_user_lang(user.id)
    user_data = users_collection.find_one({"user_id": user.id})

    if not user_data:
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
        referral_link = f"https://t.me/MoviesGroupLinkp_bot?start=ref_{user.id}" 
        
        message = (
            f"<b>{MESSAGES[lang]['earn_approved']}</b>\n\n"
            f"<code>{referral_link}</code>\n\n"
            f"<b>{MESSAGES[lang]['earn_rules_title']}</b>\n"
            f"1. {MESSAGES[lang]['earn_rule1']}\n"
            f"2. {MESSAGES[lang]['earn_rule2']}\n"
            f"3. {MESSAGES[lang]['earn_rule3']}\n\n"
            f"<b>{MESSAGES[lang]['earnings_breakdown']}</b>\n"
            f"<b>{MESSAGES[lang]['owner_share']}</b> $0.006\n"
            f"<b>{MESSAGES[lang]['your_share']}</b> $0.0018\n\n"
            f"<i>{MESSAGES[lang]['earnings_update']}</i>"
        )
        await update.message.reply_html(message)
    else:
        await update.message.reply_text(MESSAGES[lang]["not_approved_earn"])

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = await get_user_lang(user.id)
    user_data = users_collection.find_one({"user_id": user.id, "is_approved": True})

    if not user_data:
        await update.message.reply_text(MESSAGES[lang]["not_approved_withdraw"])
        return

    earnings = user_data.get("earnings", 0.0)
    referrals_count = referrals_collection.count_documents({"referrer_id": user.id})
    active_earners_count = referrals_collection.count_documents({"referrer_id": user.id, "is_active_earner": True})
    
    withdraw_link = f"https://t.me/{YOUR_TELEGRAM_HANDLE}"

    keyboard = [[InlineKeyboardButton(MESSAGES[lang]["contact_admin_button"], url=withdraw_link)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = (
        f"<b>{MESSAGES[lang]['withdrawal_details_title']}</b>\n\n"
        f"<b>{MESSAGES[lang]['total_earnings']}</b> <b>${earnings:.4f}</b>\n"
        f"<b>{MESSAGES[lang]['total_referrals']}</b> <b>{referrals_count}</b>\n"
        f"<b>{MESSAGES[lang]['active_earners']}</b> <b>{active_earners_count}</b>"
    )

    await update.message.reply_html(message, reply_markup=reply_markup)

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


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "select_lang":
        await language_menu(update, context)
        return

    if query.data == "back_to_start":
        await start_command(update, context)
        return

    if query.data.startswith("lang_"):
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
        return

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

async def process_shortlink_completion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    referred_user = update.effective_user
    referral_data = referrals_collection.find_one({"referred_user_id": referred_user.id})

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
                    {"referred_user_id": referred_user.id},
                    {"$set": {"is_active_earner": True}}
                )
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text=MESSAGES[referrer_lang]["daily_earning_update"].format(
                        full_name=referred_user.full_name, new_balance=new_balance
                    ),
                    parse_mode='HTML'
                )
                logging.info(f"Updated earnings for referrer {referrer_id}. New balance: {new_balance}")
            else:
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text=MESSAGES[referrer_lang]["daily_earning_limit"]
                )

@app.route('/shortlink_completed/<int:user_id>', methods=['GET'])
def shortlink_completed(user_id):
    return jsonify({"status": "success", "message": "Earnings will be updated."})

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("earn", earn_command))
    application.add_handler(CommandHandler("withdraw", withdraw_command))
    application.add_handler(CommandHandler("checkbot", checkbot_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    application.run_polling()

if __name__ == "__main__":
    main()
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
