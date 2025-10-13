import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
# TWA डेटा को हैंडल करने के लिए filters.StatusUpdate.WEB_APP_DATA का उपयोग करें
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import pymongo
from datetime import datetime
import asyncio
import json # JSON data को parse करने के लिए जोड़ा गया

# --- CONFIGURATION (कृपया इन मानों को अपडेट करें) ---
# NOTE: Production में इन मानों को os.getenv() के माध्यम से Environment Variables (.env) में होना चाहिए
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/") 
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE") # यहां अपना असली टोकन डालें

# अपने चैनल और मालिक के विवरण
# सुनिश्चित करें कि MOVIE_CHANNEL_ID सही है और बॉट इसमें एडमिन है।
MOVIE_CHANNEL_ID = -1002283182645  # @asbhai_bsr channel ID
OWNER_ID = 7315805571  # Owner ID (@asbhaibsr)
OWNER_USERNAME = "@asbhaibsr"  # Owner username

# --- MONGODB SETUP ---
client = pymongo.MongoClient(MONGODB_URI)
db = client.promotion_bot
users_collection = db.users
referrals_collection = db.referrals
# settings_collection = db.settings # उपयोग नहीं किया गया, हटा सकते हैं
# leaderboard_collection = db.leaderboard # उपयोग नहीं किया गया, हटा सकते हैं
movie_searches_collection = db.movie_searches
# withdrawals collection का उपयोग handle_twa_message में किया गया है

# --- LOGGING SETUP ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- UTILITY FUNCTIONS ---

# Check if user joined movie channel
async def check_channel_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """चैनल सदस्यता की जाँच करता है। त्रुटि (Chat not found) से बचने के लिए बॉट को एडमिन होना चाहिए।"""
    try:
        # यहाँ MOVIE_CHANNEL_ID का उपयोग किया गया है
        member = await context.bot.get_chat_member(chat_id=MOVIE_CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        # यह त्रुटि तब आती है जब बॉट चैनल में एडमिन नहीं होता या ID गलत होती है।
        logger.error(f"Error checking channel membership: {e}")
        return False

# Check if user already searched today
def has_searched_today(user_id: int) -> bool:
    """जाँच करता है कि उपयोगकर्ता ने आज मूवी सर्च से कमाया है या नहीं।"""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_searches = movie_searches_collection.count_documents({
        "user_id": user_id,
        "search_date": {"$gte": today_start}
    })
    return today_searches > 0

# --- COMMAND HANDLERS ---

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id
    
    # Check if user exists in database
    user_data = users_collection.find_one({"user_id": user_id})
    
    # 1. New User & Referral Logic
    if not user_data:
        # Create new user (आपका मौजूदा logic)
        # ... (new user creation logic) ...
        user_data = {
            "user_id": user_id,
            "first_name": user.first_name,
            "last_name": user.last_name or "",
            "username": user.username or "",
            "earnings": 0.0,
            "spin_count": 3,
            "last_spin_date": None,
            "joined_date": datetime.now(),
            "referral_code": f"ref_{user_id}",
            "total_referrals": 0,
            "referral_earnings": 0.0,
            "has_joined_channel": False,
            "movie_searches": 0,
            "last_search_date": None
        }
        users_collection.insert_one(user_data)
        
        # Check if this is a referral
        if context.args and context.args[0].startswith('ref_'):
            try:
                referrer_id = int(context.args[0].split('_')[1])
                referrer_data = users_collection.find_one({"user_id": referrer_id})
                
                if referrer_data:
                    # Check if referrer has joined channel
                    referrer_joined = await check_channel_membership(referrer_id, context)
                    
                    # Referral bonus logic (आपका मौजूदा logic)
                    if referrer_joined:
                        referral_bonus = 2.0
                        users_collection.update_one(
                            {"user_id": referrer_id},
                            {"$inc": {"earnings": referral_bonus, "referral_earnings": referral_bonus, "total_referrals": 1, "spin_count": 1}}
                        )
                        referrals_collection.insert_one({"referrer_id": referrer_id, "referred_id": user_id, "referral_date": datetime.now(), "earnings": referral_bonus, "spin_given": True, "bonus_paid": True})
                        
                        try:
                            await context.bot.send_message(chat_id=referrer_id, text=f"🎉 Congratulations! {user.first_name} joined using your referral link.\n\nYou earned: ₹{referral_bonus} + 1 Spin!\n\n💰 Total earnings: ₹{referrer_data['earnings'] + referral_bonus:.2f}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Open Earning Panel", web_app=WebAppInfo(url=f"https://ashhabsr.github.io/Promotion-user-panel/?user_id={referrer_id}"))]]))
                        except Exception as e:
                            logger.error(f"Could not notify referrer: {e}")
                    else:
                        # Referrer hasn't joined channel - no bonus yet, but log referral
                        referrals_collection.insert_one({"referrer_id": referrer_id, "referred_id": user_id, "referral_date": datetime.now(), "earnings": 0.0, "spin_given": False, "bonus_paid": False, "reason": "Referrer not joined channel"})
                        try:
                            await context.bot.send_message(chat_id=referrer_id, text=f"❌ {user.first_name} joined using your link BUT you didn't get bonus!\n\nJoin our channel to get ₹2 + 1 Spin per referral:\nhttps://t.me/asbhai_bsr", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel", url="https://t.me/asbhai_bsr")]]))
                        except Exception as e:
                            logger.error(f"Could not notify referrer: {e}")
            except ValueError:
                logger.error("Invalid referrer ID in start command args.")
    
    # 2. General Start Message Logic
    
    # Check channel membership & update in DB
    has_joined = await check_channel_membership(user_id, context)
    users_collection.update_one({"user_id": user_id}, {"$set": {"has_joined_channel": has_joined}})
    
    # Create TWA button (आपका URL उपयोग किया गया है)
    keyboard = [
        [InlineKeyboardButton(
            "Open Earning Panel", 
            web_app=WebAppInfo(url=f"https://ashhabsr.github.io/Promotion-user-panel/?user_id={user_id}")
        )]
    ]
    
    if not has_joined:
        keyboard.append([InlineKeyboardButton("Join Our Channel 🎬", url="https://t.me/asbhai_bsr")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"👋 Hello {user.mention_html()}!\n\nWelcome to Promotion User Bot! 🎉\n\n"
    
    if not has_joined:
        welcome_text += "❌ Join our channel to earn from referrals & searches!\n\n"
    else:
        welcome_text += "✅ Channel joined! You can earn now!\n\n"
    
    searched_today = has_searched_today(user_id)
    if searched_today:
        welcome_text += "⏰ Today's movie search: ✅ COMPLETED\n"
    else:
        welcome_text += "⏰ Today's movie search: ❌ PENDING\n"
    
    welcome_text += "\n💰 Earn money by:\n• Inviting friends (₹2 + 1 Spin after joining channel)\n• Daily movie search (₹0.50 once per day)\n• Spinning the wheel\n• Completing offers\n\nClick below to open your earning panel:"
    
    await update.message.reply_html(welcome_text, reply_markup=reply_markup)

# Movie search command
async def movie_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    has_joined = await check_channel_membership(user_id, context)
    
    if not has_joined:
        await update.message.reply_text(
            "❌ You need to join our channel first to earn from searches!\n\n"
            "Join here: https://t.me/asbhai_bsr\n\n",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel 🎬", url="https://t.me/asbhai_bsr")]])
        )
        return
    
    if has_searched_today(user_id):
        await update.message.reply_text(
            "⏰ You have already completed today's movie search!\n\n"
            "Come back tomorrow for another ₹0.50 earning! 💰\n\n",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Open Earning Panel", web_app=WebAppInfo(url=f"https://ashhabsr.github.io/Promotion-user-panel/?user_id={user_id}"))
            ]])
        )
        return
    
    search_earning = 0.50
    user_data = users_collection.find_one({"user_id": user_id})
    
    # Update DB
    users_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"earnings": search_earning, "movie_searches": 1}, "$set": {"last_search_date": datetime.now()}}
    )
    
    movie_searches_collection.insert_one({"user_id": user_id, "user_name": user_name, "search_date": datetime.now(), "earnings": search_earning, "status": "completed"})
    
    await update.message.reply_text(
        f"🎬 Today's movie search completed!\n\n"
        f"✅ You earned: ₹{search_earning}\n"
        f"💰 Total earnings: ₹{user_data['earnings'] + search_earning:.2f}\n\n"
        f"🔄 Next search available: Tomorrow",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Open Earning Panel", web_app=WebAppInfo(url=f"https://ashhabsr.github.io/Promotion-user-panel/?user_id={user_id}"))
        ]])
    )

# Check referral bonuses for users who joined channel later
async def check_referral_bonuses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    has_joined = await check_channel_membership(user_id, context)
    
    if has_joined:
        pending_referrals = referrals_collection.find({"referrer_id": user_id, "bonus_paid": False})
        
        total_bonus = 0
        total_spins = 0
        
        for referral in pending_referrals:
            referral_bonus = 2.0
            users_collection.update_one({"user_id": user_id}, {"$inc": {"earnings": referral_bonus, "referral_earnings": referral_bonus, "spin_count": 1}})
            
            referrals_collection.update_one({"_id": referral["_id"]}, {"$set": {"earnings": referral_bonus, "spin_given": True, "bonus_paid": True, "bonus_paid_date": datetime.now()}})
            
            total_bonus += referral_bonus
            total_spins += 1
        
        if total_bonus > 0:
            await update.message.reply_text(
                f"🎉 Channel joined! Pending bonuses activated!\n\n"
                f"✅ You received: ₹{total_bonus:.2f} + {total_spins} Spins\n"
                f"for {total_spins} pending referrals! 💰",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Open Earning Panel", web_app=WebAppInfo(url=f"https://ashhabsr.github.io/Promotion-user-panel/?user_id={user_id}"))
                ]])
            )
        else:
            await update.message.reply_text(
                "✅ Channel joined successfully!\n\n"
                "अब आप कमा सकते हैं: \n"
                "• Daily movie search (₹0.50)\n"
                "• Per referral (₹2 + 1 Spin)!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Open Earning Panel", web_app=WebAppInfo(url=f"https://ashhabsr.github.io/Promotion-user-panel/?user_id={user_id}"))
                ]])
            )
    else:
        await update.message.reply_text(
            "❌ You haven't joined our channel yet!\n\n"
            "Join here: https://t.me/asbhai_bsr\n\n",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel 🎬", url="https://t.me/asbhai_bsr")]])
        )

# --- WEB APP DATA HANDLER (CORRECTED) ---

# TWA से JSON data को हैंडल करने के लिए नया फंक्शन
async def handle_twa_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """TWA से आए JSON डेटा को संभालता है।"""
    # web_app_data message के अंदर होता है
    web_app_data_json = update.message.web_app_data.data
    user_id = update.effective_user.id
    
    try:
        data = json.loads(web_app_data_json)
        
        command = data.get('command')
        
        if command == 'update_balance':
            amount = data.get('amount')
            users_collection.update_one(
                {"user_id": user_id},
                {"$inc": {"earnings": amount, "spin_count": -1}} # Spin & Win से आया है, इसलिए स्पिन घटाएं
            )
            await update.message.reply_text(f"✅ Balance updated! Added ₹{amount} (from Spin & Win).")
            
        elif command == 'withdrawal_request':
            amount = data.get('amount')
            details = data.get('details')
            
            # (आपका मौजूदा withdrawal logic)
            withdrawal_data = {"user_id": user_id, "amount": amount, "details": details, "status": "pending", "request_date": datetime.now()}
            db.withdrawals.insert_one(withdrawal_data)
            
            try:
                user_info = users_collection.find_one({"user_id": user_id})
                user_name = user_info.get('first_name', 'Unknown')
                username = user_info.get('username', 'No username')
                
                # Owner Notification (आपका मौजूदा logic)
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=f"🔄 NEW WITHDRAWAL REQUEST\n\n👤 User: {user_name} (@{username})\n💰 Amount: ₹{amount}\n\n📋 Details:\n• UPI: {details.get('upiId')}\n• Account: {details.get('accountNumber')}\n", # Shortened details for brevity
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("Contact User", url=f"tg://user?id={user_id}"),
                        InlineKeyboardButton("Approve", callback_data=f"approve_{user_id}_{amount}")
                    ]])
                )
            except Exception as e:
                logger.error(f"Could not notify owner: {e}")
                
            await update.message.reply_text(
                "✅ Withdrawal request submitted!\n\n"
                "💰 Amount: ₹" + str(amount) + "\n"
                "⏰ Processing time: 24 hours\n\n"
                "For any query, contact " + OWNER_USERNAME
            )
            
        elif command == 'premium_prize':
            # (आपका मौजूदा premium prize logic)
            try:
                user_info = users_collection.find_one({"user_id": user_id})
                user_name = user_info.get('first_name', 'Unknown')
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=f"🎁 PREMIUM PRIZE WINNER!\n\n👤 User: {user_name}\n🆔 ID: {user_id}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Contact Winner", url=f"tg://user?id={user_id}")]])
                )
            except Exception as e:
                logger.error(f"Could not notify owner about premium prize: {e}")
                
            await update.message.reply_text(
                "🎉 Congratulations! You won a premium prize!\n\n"
                "Our admin " + OWNER_USERNAME + " will contact you soon."
            )
            
        elif command == 'check_channel':
            # TWA से Channel check request
            has_joined = await check_channel_membership(user_id, context)
            users_collection.update_one({"user_id": user_id}, {"$set": {"has_joined_channel": has_joined}})
            
            if has_joined:
                # Pending bonuses के लिए check_referral_bonuses को call करें
                # Note: यह फ़ंक्शन CallbackQueryHandler के लिए बना है, इसलिए इसे MessageHandler के लिए बदलना होगा।
                # सुविधा के लिए, हम यहाँ logic दोहरा रहे हैं:
                
                pending_referrals = referrals_collection.find({"referrer_id": user_id, "bonus_paid": False})
                total_bonus = 0
                total_spins = 0
                
                for referral in pending_referrals:
                    referral_bonus = 2.0
                    users_collection.update_one({"user_id": user_id}, {"$inc": {"earnings": referral_bonus, "referral_earnings": referral_bonus, "spin_count": 1}})
                    referrals_collection.update_one({"_id": referral["_id"]}, {"$set": {"earnings": referral_bonus, "spin_given": True, "bonus_paid": True, "bonus_paid_date": datetime.now()}})
                    total_bonus += referral_bonus
                    total_spins += 1
                
                if total_bonus > 0:
                    await update.message.reply_text(f"🎉 Channel joined & verified! Pending bonuses activated!\n\n✅ You received: ₹{total_bonus:.2f} + {total_spins} Spins! 💰")
                else:
                    await update.message.reply_text("✅ Channel joined & verified! Now start earning! 💰")
            else:
                await update.message.reply_text("❌ You haven't joined the channel yet!")
            
    except Exception as e:
        logger.error(f"Error processing TWA message: {e}")
        await update.message.reply_text("❌ Error processing your request. Please try again.")

# Handle owner approval (CallbackQuery)
async def handle_owner_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (आपका मौजूदा owner approval logic) ...
    query = update.callback_query
    await query.answer()
    
    if str(query.from_user.id) != str(OWNER_ID):
        await query.edit_message_text("❌ Only owner can approve withdrawals!")
        return
    
    data = query.data
    if data.startswith('approve_'):
        parts = data.split('_')
        user_id = int(parts[1])
        amount = float(parts[2])
        
        # Update withdrawal status & reset user balance
        db.withdrawals.update_one({"user_id": user_id, "status": "pending"}, {"$set": {"status": "approved", "approved_date": datetime.now()}})
        users_collection.update_one({"user_id": user_id}, {"$set": {"earnings": 0.0}})
        
        # Notify user
        try:
            await context.bot.send_message(chat_id=user_id, text=f"✅ Your withdrawal request for ₹{amount} has been approved!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Open Earning Panel", web_app=WebAppInfo(url=f"https://ashhabsr.github.io/Promotion-user-panel/?user_id={user_id}"))]]))
        except Exception as e:
            logger.error(f"Could not notify user: {e}")
        
        await query.edit_message_text(f"✅ Withdrawal approved for user {user_id}!")

# Reset daily searches (Job Queue - Midnight)
async def reset_daily_searches(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Daily searches reset - Ready for new day!")

# --- MAIN FUNCTION ---
def main() -> None:
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", movie_search))
    application.add_handler(CommandHandler("movie", movie_search))
    application.add_handler(CommandHandler("join", check_referral_bonuses))
    
    # 💥 सबसे महत्वपूर्ण सुधार: TWA data को handle करने के लिए MessageHandler का उपयोग करें
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_twa_message))
    
    # Owner approval CallbackQuery को handle करें
    application.add_handler(CallbackQueryHandler(handle_owner_approval, pattern=r'^approve_'))
    
    # Add job queue for daily reset
    job_queue = application.job_queue
    # Note: Job Queue केवल long polling में काम करता है, webhook में नहीं।
    # job_queue.run_daily(reset_daily_searches, time=datetime.time(hour=0, minute=0))
    
    # Start the Bot
    application.run_polling()

if __name__ == "__main__":
    main()
