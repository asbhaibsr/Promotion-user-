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

# Load Render-specific variables
# **सुनिश्चित करें कि WEB_SERVER_URL आपके TWA HTML पेज का URL है**
WEB_SERVER_URL = os.getenv("WEB_SERVER_URL") 
PORT = int(os.getenv("PORT", 8000))

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client.get_database('bot_database')
users_collection = db.get_collection('users')
referrals_collection = db.get_collection('referrals')
settings_collection = db.get_collection('settings')

# --- MESSAGES Dictionary (वैसा ही रखा गया है) ---
MESSAGES = {
    "en": {
        "start_greeting": "Hey 👋! Welcome to the Movies Group Bot. All earning and movie links are now in our new Web App (TWA). Click the button below to start!",
        "start_step1": "Click the 'Earn & Watch Movies' button below.",
        "start_step2": "Use the Spin Wheel to earn daily and invite friends for more.",
        "start_step3": "Navigate to the 'Movies' tab inside the app to join groups.",
        "language_choice": "Choose your language:",
        "language_selected": "Language changed to English.",
        #... (other messages remain the same for admin commands/logs)
        "new_user_log": "🆕 <b>New User Connected:</b>\n\n<b>User ID:</b> <code>{user_id}</code>\n<b>Username:</b> @{username}\n<b>Full Name:</b> {full_name}\n<b>Referred By:</b> @{referrer_username} (ID: <code>{referrer_id}</code>)",
        "new_user_log_no_ref": "🆕 <b>New User Connected:</b>\n\n<b>User ID:</b> <code>{user_id}</code>\n<b>Username:</b> @{username}\n<b>Full Name:</b> {full_name}\n<b>Referred By:</b> None",
        "broadcast_admin_only": "❌ This command is for the bot admin only.",
        "broadcast_message": "Please reply to a message with `/broadcast` to send it to all users.",
        "broadcast_success": "✅ Message sent to all {count} users.",
        "clear_earn_success": "✅ User {user_id}'s earnings have been cleared.",
        "clear_earn_not_found": "❌ User with ID {user_id} not found or not an earner.",
        "clear_earn_usage": "❌ Usage: /clearearn <user_id>",
        "check_stats_message": "Stats for user {user_id}:\n\nTotal Earnings: ₹{earnings:.2f}\nTotal Referrals: {referrals}",
        "check_stats_not_found": "❌ User with ID {user_id} not found.",
        "check_stats_usage": "❌ Usage: /checkstats <user_id>",
        "stats_message": "Bot Stats:\n\n👥 Total Users: {total_users}\n🎯 Approved Earners: {approved_users}",
        "setrate_success": "✅ Referral earning rate has been updated to ₹{new_rate:.2f}.",
        "setrate_usage": "❌ Usage: /setrate <new_rate_in_inr>",
        "invalid_rate": "❌ Invalid rate. Please enter a number.",
        "admin_panel_title": "<b>⚙️ Admin Panel</b>\n\nManage bot settings and users from here.",
        "referral_already_exists": "This user has already been referred by someone else. You cannot get any benefits from this referral.",
    },
    "hi": {
        "start_greeting": "नमस्ते 👋! मूवी ग्रुप बॉट में आपका स्वागत है। सभी कमाई और मूवी लिंक अब हमारे नए वेब ऐप (TWA) में हैं। शुरू करने के लिए नीचे दिए गए बटन पर क्लिक करें!",
        "start_step1": "नीचे दिए गए 'Earn & Watch Movies' बटन पर क्लिक करें।",
        "start_step2": "दैनिक कमाई के लिए स्पिन व्हील का उपयोग करें और अधिक के लिए दोस्तों को आमंत्रित करें।",
        "start_step3": "ग्रुप्स में शामिल होने के लिए ऐप के अंदर 'Movies' टैब पर जाएँ।",
        "language_choice": "अपनी भाषा चुनें:",
        "language_selected": "भाषा हिंदी में बदल दी गई है।",
        #... (other messages remain the same for admin commands/logs)
        "new_user_log": "🆕 <b>नया उपयोगकर्ता जुड़ा है:</b>\n\n<b>उपयोगकर्ता आईडी:</b> <code>{user_id}</code>\n<b>यूजरनेम:</b> @{username}\n<b>पूरा नाम:</b> {full_name}\n<b>किसके द्वारा रेफर किया गया:</b> @{referrer_username} (आईडी: <code>{referrer_id}</code>)",
        "new_user_log_no_ref": "🆕 <b>नया उपयोगकर्ता जुड़ा है:</b>\n\n<b>उपयोगकर्ता आईडी:</b> <code>{user_id}</code>\n<b>यूजरनेम:</b> @{username}\n<b>पूरा नाम:</b> {full_name}\n<b>किसके द्वारा रेफर किया गया:</b> कोई नहीं",
        "broadcast_admin_only": "❌ यह कमांड केवल बॉट एडमिन के लिए है।",
        "broadcast_message": "सभी उपयोगकर्ताओं को संदेश भेजने के लिए कृपया किसी संदेश का `/broadcast` के साथ उत्तर दें।",
        "broadcast_success": "✅ संदेश सभी {count} उपयोगकर्ताओं को भेजा गया।",
        "clear_earn_success": "✅ यूजर {user_id} की कमाई साफ कर दी गई है।",
        "clear_earn_not_found": "❌ यूजर ID {user_id} नहीं मिला या वह कमाने वाला नहीं है।",
        "clear_earn_usage": "❌ उपयोग: /clearearn <user_id>",
        "check_stats_message": "यूजर {user_id} के आंकड़े:\n\nकुल कमाई: ₹{earnings:.2f}\nकुल रेफरल: {referrals}",
        "check_stats_not_found": "❌ यूजर ID {user_id} नहीं मिला।",
        "check_stats_usage": "❌ उपयोग: /checkstats <user_id>",
        "stats_message": "बॉट के आंकड़े:\n\n👥 कुल उपयोगकर्ता: {total_users}\n🎯 स्वीकृत कमाने वाले: {approved_users}",
        "setrate_success": "✅ रेफरल कमाई की दर ₹{new_rate:.2f} पर अपडेट हो गई है।",
        "setrate_usage": "❌ उपयोग: /setrate <नई_राशि_रुपये_में>",
        "invalid_rate": "❌ अमान्य राशि। कृपया एक संख्या दर्ज करें।",
        "admin_panel_title": "<b>⚙️ एडमिन पैनल</b>\n\nयहाँ से बॉट की सेटिंग्स और यूज़र्स को मैनेज करें।",
        "referral_already_exists": "यह उपयोगकर्ता पहले ही किसी और के द्वारा रेफर किया जा चुका है। इसलिए, आप इस रेफरल से कोई लाभ नहीं उठा सकते हैं।",
    }
}
# --- MESSAGES Dictionary End ---


# Conversion rate (assuming a static rate for simplicity)
DOLLAR_TO_INR = 83.0

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
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"lang": lang}},
        upsert=True
    )
    
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    # Referral ID logic remains to ensure referral tracking is correct
    referral_id_str = context.args[0].replace("ref_", "") if context.args and context.args[0].startswith("ref_") else None
    referral_id = int(referral_id_str) if referral_id_str else None

    user_data = users_collection.find_one({"user_id": user.id})
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
        # Logging logic remains the same
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

    # Handle referral logic (remains the same)
    if referral_id:
        existing_referral = referrals_collection.find_one({"referred_user_id": user.id})
        
        if existing_referral:
            referrer_lang = await get_user_lang(referral_id)
            try:
                await context.bot.send_message(
                    chat_id=referral_id,
                    text=MESSAGES[referrer_lang]["referral_already_exists"]
                )
            except (TelegramError, TimedOut) as e:
                logging.error(f"Could not send referral exists notification to {referral_id}: {e}")

        elif is_new_user:
            referrals_collection.insert_one({
                "referrer_id": referral_id,
                "referred_user_id": user.id,
                "referred_username": user.username,
                "join_date": datetime.now(),
            })
            
            # Note: Initial referral bonus is now handled *here* (on join)
            referral_rate_usd = await get_referral_bonus_usd()
            users_collection.update_one(
                {"user_id": referral_id},
                {"$inc": {"earnings": referral_rate_usd}}
            )

            try:
                referred_username_display = f"@{user.username}" if user.username else f"(No username)"
                referrer_lang = await get_user_lang(referral_id)
                await context.bot.send_message(
                    chat_id=referral_id,
                    # Note: You need to add 'new_referral_notification' to MESSAGES if it's missing
                    text=MESSAGES[referrer_lang].get("new_referral_notification", "🥳 New referral!").format(
                        full_name=user.full_name, username=referred_username_display
                    )
                )
            except (TelegramError, TimedOut) as e:
                logging.error(f"Could not notify referrer {referral_id}: {e}")

    # --- MAIN CHANGE: Web App Button ---
    lang = await get_user_lang(user.id)
    
    # URL for your Web App HTML page
    web_app_url = WEB_SERVER_URL 
    
    keyboard = [
        # यह बटन Telegram Web App को खोलेगा
        [InlineKeyboardButton("💰 Earn & Watch Movies 🎬", web_app={"url": web_app_url})], 
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
                
# /earn command is now mostly redundant but kept for backward compatibility/referral link
async def earn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (content remains the same, but the functionality is better handled by TWA)
    user = update.effective_user
    lang = await get_user_lang(user.id)
    
    # Ensure user exists
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
    
    # Fallback/Help message
    message = (
        f"<b>Referral Link:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        f"Use the main 'Earn & Watch Movies' button for the full panel."
    )

    await update.message.reply_html(message)


# --- OLD MENU CALLBACKS REMOVED/SIMPLIFIED ---

async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Redirects back to the main menu with the TWA button."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    lang = await get_user_lang(user.id)
    
    web_app_url = WEB_SERVER_URL
    
    keyboard = [
        [InlineKeyboardButton("💰 Earn & Watch Movies 🎬", web_app={"url": web_app_url})],
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
    

async def handle_lang_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    lang = query.data.split("_")[1]
    await set_user_lang(query.from_user.id, lang)
    
    # Re-create the main start message with the new language
    web_app_url = WEB_SERVER_URL
    
    keyboard = [
        [InlineKeyboardButton("💰 Earn & Watch Movies 🎬", web_app={"url": web_app_url})],
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

# --- ADMIN AND EARNING FUNCTIONS (Retained) ---

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    user = update.effective_user
    lang = await get_user_lang(user.id)
    
    try:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Testing connection...", parse_mode='HTML')
        await update.message.reply_html(MESSAGES[lang].get("checkbot_success", "✅ Bot is connected!"))
    except Exception as e:
        logging.error(f"Bot is not connected: {e}")
        await update.message.reply_html(MESSAGES[lang].get("checkbot_failure", "❌ Bot is not connected."))
        
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    
    for user_doc in all_users:
        user_id = user_doc["user_id"]
        if user_id == ADMIN_ID:
            continue
        
        try:
            await context.bot.forward_message(
                chat_id=user_id, 
                from_chat_id=update.effective_chat.id, 
                message_id=message_to_send.message_id
            )
            sent_count += 1
            await asyncio.sleep(0.05) # 50 milliseconds delay
            
        except TimedOut:
            failed_count += 1
            logging.error(f"Timed out while broadcasting to user {user_id}.")
            await asyncio.sleep(1) 
        except TelegramError as e:
            failed_count += 1
            logging.error(f"Could not broadcast message to user {user_id}: {e}")
            if 'retry_after' in str(e):
                logging.warning(f"Hit flood wait. Sleeping for {e.retry_after} seconds.")
                await asyncio.sleep(e.retry_after + 1)
            
        except Exception as e:
            failed_count += 1
            logging.error(f"An unexpected error occurred while broadcasting to user {user_id}: {e}")
            await asyncio.sleep(0.5)

    await update.message.reply_html(
        MESSAGES[lang]["broadcast_success"].format(count=sent_count) + 
        f"\n❌ विफल संदेश (Failed): {failed_count} users"
    )

# --- Group Message Handler (Retained for earning logic) ---

# Note: The existing logic of setting a payment task after a delay is highly unreliable
# and can lead to bugs and data loss. It is kept here as per your original code structure.
async def add_payment_after_delay(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    # This function is fundamentally flawed for production use due to reliance on
    # in-memory task scheduling. A robust system would use a dedicated queue/worker.
    await asyncio.sleep(300) # Wait 5 minutes
    
    user_data = users_collection.find_one({"user_id": user_id})
    if user_data:
        referral_data = referrals_collection.find_one({"referred_user_id": user_id}) # Corrected var name to user_id
        
        if referral_data:
            referrer_id = referral_data["referrer_id"]
            referrer_data = users_collection.find_one({"user_id": referrer_id})
            
            if referrer_data:
                # Earning logic remains the same (check for daily limit)
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
                            # Note: You need to add 'daily_earning_update' to MESSAGES if missing
                            text=MESSAGES[referrer_lang].get("daily_earning_update", "🎉 Earning updated!").format(
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
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type in ["group", "supergroup"]:
        # Existing logic to schedule payment task remains
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
    
    # Callback Handlers (Only essential ones remain)
    application.add_handler(CallbackQueryHandler(back_to_main_menu, pattern="^back_to_main_menu$"))
    application.add_handler(CallbackQueryHandler(language_menu, pattern="^select_lang$"))
    application.add_handler(CallbackQueryHandler(handle_lang_choice, pattern="^lang_"))
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
