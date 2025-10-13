import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import pymongo
from datetime import datetime, timedelta
import asyncio
import random
import json
import time
from flask import Flask

# Logging Setup - YEH PEHLE AAYEGA
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Flask app for Render 24/7
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Promotion User Bot is Running! Status: ACTIVE"

@app.route('/health')
def health():
    return {"status": "active", "timestamp": datetime.now().isoformat()}

# Configuration
MONGODB_URI = os.getenv("MONGODB_URI", "your_mongodb_uri_here")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token_here")

# MongoDB Setup
try:
    client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=10000)
    db = client.promotion_bot
    users_collection = db.users
    referrals_collection = db.referrals
    settings_collection = db.settings
    leaderboard_collection = db.leaderboard
    movie_searches_collection = db.movie_searches
    withdrawals_collection = db.withdrawals
    
    # Create indexes
    users_collection.create_index("user_id", unique=True)
    referrals_collection.create_index([("referrer_id", 1), ("referred_id", 1)])
    movie_searches_collection.create_index([("user_id", 1), ("search_date", 1)])
    withdrawals_collection.create_index("user_id")
    
    logger.info("✅ MongoDB connected successfully")
except Exception as e:
    logger.error(f"❌ MongoDB connection error: {e}")
    # Continue without MongoDB for testing
    users_collection = None

# Constants
MOVIE_CHANNEL_ID = -1002283182645  # @asbhai_bsr
OWNER_ID = 7315805571  # @asbhaibsr
OWNER_USERNAME = "@asbhaibsr"
REFERRAL_BONUS = 2.0
DAILY_SEARCH_BONUS = 0.50
SPIN_PRIZES = [0.10, 0.20, 0.50, 1.00, 2.00, 5.00, 10.00, 0.00, 0.00, "premium"]

# Utility Functions
async def check_channel_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user has joined the movie channel"""
    try:
        member = await context.bot.get_chat_member(chat_id=MOVIE_CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking channel membership for {user_id}: {e}")
        return False

def has_searched_today(user_id: int) -> bool:
    """Check if user has already searched today"""
    if not users_collection:
        return False
        
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_searches = movie_searches_collection.count_documents({
        "user_id": user_id,
        "search_date": {"$gte": today_start}
    })
    return today_searches > 0

def get_user_data(user_id: int):
    """Get user data from database"""
    if not users_collection:
        return None
    return users_collection.find_one({"user_id": user_id})

def update_user_balance(user_id: int, amount: float):
    """Update user balance"""
    if users_collection:
        users_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"earnings": amount}},
            upsert=True
        )

def get_referral_stats(user_id: int):
    """Get user referral statistics"""
    if not referrals_collection:
        return {"total": 0, "earnings": 0, "pending": 0}
    
    total_refs = referrals_collection.count_documents({"referrer_id": user_id})
    earned_refs = referrals_collection.count_documents({"referrer_id": user_id, "bonus_paid": True})
    pending_refs = total_refs - earned_refs
    
    pipeline = [
        {"$match": {"referrer_id": user_id, "bonus_paid": True}},
        {"$group": {"_id": None, "total_earnings": {"$sum": "$earnings"}}}
    ]
    
    result = list(referrals_collection.aggregate(pipeline))
    total_earnings = result[0]["total_earnings"] if result else 0
    
    return {
        "total": total_refs,
        "earnings": total_earnings,
        "pending": pending_refs
    }

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command with referral system"""
    user = update.effective_user
    user_id = user.id
    
    logger.info(f"User {user_id} started the bot")
    
    # Get or create user data
    user_data = get_user_data(user_id)
    if not user_data:
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
            "last_search_date": None,
            "total_earnings": 0.0
        }
        if users_collection:
            users_collection.insert_one(user_data)
    
    # Check referral
    if context.args and context.args[0].startswith('ref_'):
        try:
            referrer_id = int(context.args[0].split('_')[1])
            if referrer_id != user_id:  # Prevent self-referral
                referrer_data = get_user_data(referrer_id)
                
                if referrer_data:
                    # Check if referral already exists
                    existing_ref = referrals_collection.find_one({
                        "referrer_id": referrer_id,
                        "referred_id": user_id
                    }) if referrals_collection else None
                    
                    if not existing_ref:
                        # Create referral record
                        referral_data = {
                            "referrer_id": referrer_id,
                            "referred_id": user_id,
                            "referral_date": datetime.now(),
                            "earnings": 0.0,
                            "spin_given": False,
                            "bonus_paid": False,
                            "reason": "Pending channel join"
                        }
                        if referrals_collection:
                            referrals_collection.insert_one(referral_data)
                            users_collection.update_one(
                                {"user_id": referrer_id},
                                {"$inc": {"total_referrals": 1}}
                            )
        except (ValueError, IndexError) as e:
            logger.error(f"Invalid referral code: {e}")
    
    # Check channel membership
    has_joined = await check_channel_membership(user_id, context)
    if users_collection:
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"has_joined_channel": has_joined}}
        )
    
    # TWA URL
    twa_url = f"https://ashhabsr.github.io/Promotion-user-panel/?user_id={user_id}"
    
    # Create keyboard
    keyboard = [
        [InlineKeyboardButton("🎮 Open Earning Panel", web_app=WebAppInfo(url=twa_url))]
    ]
    
    if not has_joined:
        keyboard.append([InlineKeyboardButton("📢 Join Our Channel", url="https://t.me/asbhai_bsr")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Welcome message
    welcome_text = f"""👋 Welcome {user.mention_html()}!

💰 <b>Promotion User Earning Bot</b> 🎉

{"✅ Channel Joined! Full Access Activated!" if has_joined else "❌ Join Channel to Unlock Earnings!"}

🎯 <b>Earning Methods:</b>
• 🤝 Refer Friends: ₹{REFERRAL_BONUS} + 1 Spin each
• 🎬 Daily Search: ₹{DAILY_SEARCH_BONUS} per day  
• 🎡 Spin Wheel: Win ₹0.10 to ₹10.00
• 🏆 Leaderboard: Daily prizes

💸 <b>Withdrawal:</b> Minimum ₹80

Click below to start earning! 🚀"""
    
    await update.message.reply_html(welcome_text, reply_markup=reply_markup)

async def movie_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle movie search command"""
    user = update.effective_user
    user_id = user.id
    
    # Check channel membership
    has_joined = await check_channel_membership(user_id, context)
    if not has_joined:
        await update.message.reply_text(
            "❌ <b>Channel Membership Required!</b>\n\n"
            "Join our channel to unlock daily earnings:\n"
            "👉 @asbhai_bsr\n\n"
            "After joining, use /join to activate bonuses!",
            parse_mode='HTML'
        )
        return
    
    # Check daily limit
    if has_searched_today(user_id):
        await update.message.reply_text(
            "⏰ <b>Daily Search Completed!</b>\n\n"
            "You've already earned your ₹0.50 for today!\n"
            "Come back tomorrow for another search.\n\n"
            "💡 <b>Other Ways to Earn:</b>\n"
            "• Invite friends: ₹2.00 each\n"
            "• Spin wheel: Win prizes\n"
            "• Complete offers",
            parse_mode='HTML'
        )
        return
    
    # Process search
    user_data = get_user_data(user_id)
    if not user_data:
        await start(update, context)
        return
    
    # Update earnings
    update_user_balance(user_id, DAILY_SEARCH_BONUS)
    
    # Log search
    if movie_searches_collection:
        search_data = {
            "user_id": user_id,
            "user_name": user.first_name,
            "search_date": datetime.now(),
            "earnings": DAILY_SEARCH_BONUS,
            "status": "completed"
        }
        movie_searches_collection.insert_one(search_data)
    
    # Update user stats
    if users_collection:
        users_collection.update_one(
            {"user_id": user_id},
            {
                "$inc": {"movie_searches": 1},
                "$set": {"last_search_date": datetime.now()}
            }
        )
    
    # Success message
    twa_url = f"https://ashhabsr.github.io/Promotion-user-panel/?user_id={user_id}"
    await update.message.reply_text(
        f"🎬 <b>Movie Search Completed!</b>\n\n"
        f"✅ <b>Earned:</b> ₹{DAILY_SEARCH_BONUS}\n"
        f"💰 <b>Total Balance:</b> ₹{user_data['earnings'] + DAILY_SEARCH_BONUS:.2f}\n\n"
        f"🔄 Next search available: <b>Tomorrow</b>\n\n"
        f"Keep inviting friends for more earnings! 💰",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📊 Open Dashboard", web_app=WebAppInfo(url=twa_url))
        ]])
    )

async def join_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle channel join verification"""
    user_id = update.effective_user.id
    
    has_joined = await check_channel_membership(user_id, context)
    
    if has_joined:
        # Update user status
        if users_collection:
            users_collection.update_one(
                {"user_id": user_id},
                {"$set": {"has_joined_channel": True}}
            )
        
        # Process pending referrals
        if referrals_collection:
            pending_refs = referrals_collection.find({
                "referrer_id": user_id,
                "bonus_paid": False
            })
            
            total_bonus = 0
            total_spins = 0
            
            for referral in pending_refs:
                # Pay bonus
                update_user_balance(user_id, REFERRAL_BONUS)
                users_collection.update_one(
                    {"user_id": user_id},
                    {
                        "$inc": {
                            "referral_earnings": REFERRAL_BONUS,
                            "spin_count": 1
                        }
                    }
                )
                
                referrals_collection.update_one(
                    {"_id": referral["_id"]},
                    {
                        "$set": {
                            "earnings": REFERRAL_BONUS,
                            "spin_given": True,
                            "bonus_paid": True,
                            "bonus_paid_date": datetime.now(),
                            "reason": "Bonus paid after channel join"
                        }
                    }
                )
                
                total_bonus += REFERRAL_BONUS
                total_spins += 1
            
            if total_bonus > 0:
                bonus_msg = f"\n\n🎉 <b>Pending Bonuses Activated!</b>\n" \
                          f"✅ Received: ₹{total_bonus:.2f} + {total_spins} Spins\n" \
                          f"For {total_spins} pending referrals!"
            else:
                bonus_msg = "\n\n✅ You're all set! Start earning now!"
        else:
            bonus_msg = "\n\n✅ Channel verified! Start earning!"
        
        twa_url = f"https://ashhabsr.github.io/Promotion-user-panel/?user_id={user_id}"
        await update.message.reply_text(
            f"✅ <b>Channel Verification Successful!</b>{bonus_msg}\n\n"
            f"🎯 <b>Now You Can:</b>\n"
            f"• Earn ₹0.50 daily from searches\n"
            f"• Get ₹2.00 + 1 Spin per referral\n"
            f"• Access all earning features!",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🚀 Start Earning", web_app=WebAppInfo(url=twa_url))
            ]])
        )
    else:
        await update.message.reply_text(
            "❌ <b>Channel Not Joined!</b>\n\n"
            "Please join our channel first:\n"
            "👉 @asbhai_bsr\n\n"
            "After joining, use this command again to verify!",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📢 Join Channel", url="https://t.me/asbhai_bsr")
            ]])
        )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check user balance"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    if not user_data:
        await start(update, context)
        return
    
    ref_stats = get_referral_stats(user_id)
    twa_url = f"https://ashhabsr.github.io/Promotion-user-panel/?user_id={user_id}"
    
    balance_text = f"""
💰 <b>Your Earnings Summary</b>

📊 <b>Main Balance:</b> ₹{user_data.get('earnings', 0):.2f}
🎯 <b>Target:</b> ₹80 (Withdrawal Minimum)

🤝 <b>Referral Stats:</b>
• Total Referrals: {ref_stats['total']}
• Active Referrals: {ref_stats['total'] - ref_stats['pending']}
• Pending Bonus: {ref_stats['pending']}
• Referral Earnings: ₹{ref_stats['earnings']:.2f}

🎡 <b>Spins Available:</b> {user_data.get('spin_count', 0)}
🎬 <b>Movie Searches:</b> {user_data.get('movie_searches', 0)}

💡 <b>Next Steps:</b>
• Invite more friends
• Do daily searches  
• Spin the wheel
    """
    
    await update.message.reply_text(
        balance_text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📊 Detailed Dashboard", web_app=WebAppInfo(url=twa_url))
        ]])
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Help command"""
    help_text = """
🆘 <b>Promotion User Bot - Help Guide</b>

🎯 <b>How to Earn:</b>
1. <b>Invite Friends</b> - Share your referral link
   • Earn ₹2.00 + 1 Spin per referral
   • Bonus paid after joining @asbhai_bsr

2. <b>Daily Movie Search</b> - Use /search command
   • Earn ₹0.50 once per day
   • Requires channel membership

3. <b>Spin Wheel</b> - Available in dashboard
   • Win ₹0.10 to ₹10.00
   • Premium prizes available

4. <b>Leaderboard</b> - Top earners daily
   • Win extra prizes

💰 <b>Withdrawal Rules:</b>
• Minimum: ₹80
• Processing: 24 hours
• Methods: UPI, Bank Transfer

📢 <b>Requirements:</b>
• Must join @asbhai_bsr channel
• Active Telegram account

🛠️ <b>Support:</b>
Contact @asbhaibsr for help
    """
    
    await update.message.reply_text(help_text, parse_mode='HTML')

# TWA Data Handler
async def handle_twa_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle data from Telegram Web App"""
    try:
        web_app_data = update.message.web_app_data
        data = json.loads(web_app_data.data)
        user_id = update.effective_user.id
        
        command = data.get('command')
        logger.info(f"TWA Data from {user_id}: {command}")
        
        if command == 'update_balance':
            amount = data.get('amount', 0.0)
            update_user_balance(user_id, amount)
            
            # Decrease spin count
            if users_collection:
                users_collection.update_one(
                    {"user_id": user_id},
                    {"$inc": {"spin_count": -1}}
                )
            
            await update.message.reply_text(f"✅ Spin completed! Added ₹{amount:.2f} to your balance.")
            
        elif command == 'withdrawal_request':
            amount = data.get('amount', 0.0)
            details = data.get('details', {})
            
            # Validate minimum amount
            if amount < 80:
                await update.message.reply_text("❌ Minimum withdrawal amount is ₹80!")
                return
            
            # Create withdrawal request
            if withdrawals_collection:
                withdrawal_data = {
                    "user_id": user_id,
                    "amount": amount,
                    "details": details,
                    "status": "pending",
                    "request_date": datetime.now(),
                    "user_name": update.effective_user.first_name,
                    "username": update.effective_user.username or "No username"
                }
                withdrawals_collection.insert_one(withdrawal_data)
            
            # Notify owner
            try:
                owner_text = f"""🔄 <b>NEW WITHDRAWAL REQUEST</b>

👤 <b>User:</b> {update.effective_user.first_name}
🆔 <b>ID:</b> {user_id}
📛 <b>Username:</b> @{update.effective_user.username or 'N/A'}
💰 <b>Amount:</b> ₹{amount}

📋 <b>Details:</b>
• Name: {details.get('fullName', 'N/A')}
• Account: {details.get('accountNumber', 'N/A')}  
• IFSC: {details.get('ifscCode', 'N/A')}
• UPI: {details.get('upiId', 'N/A')}
• Mobile: {details.get('mobileNo', 'N/A')}
• Email: {details.get('emailId', 'N/A')}

⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
                
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=owner_text,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("👤 Contact User", url=f"tg://user?id={user_id}"),
                        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}_{amount}")
                    ]])
                )
            except Exception as e:
                logger.error(f"Could not notify owner: {e}")
            
            # Reset user balance
            update_user_balance(user_id, -amount)
            
            await update.message.reply_text(
                f"✅ <b>Withdrawal Request Submitted!</b>\n\n"
                f"💰 <b>Amount:</b> ₹{amount}\n"
                f"⏰ <b>Processing Time:</b> 24 hours\n"
                f"📞 <b>Contact:</b> {OWNER_USERNAME} for queries",
                parse_mode='HTML'
            )
            
        elif command == 'premium_prize':
            # Handle premium prize
            try:
                owner_text = f"🎁 <b>PREMIUM PRIZE WINNER!</b>\n\n" \
                           f"👤 <b>User:</b> {update.effective_user.first_name}\n" \
                           f"🆔 <b>ID:</b> {user_id}\n" \
                           f"⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=owner_text,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🎁 Contact Winner", url=f"tg://user?id={user_id}")
                    ]])
                )
            except Exception as e:
                logger.error(f"Could not notify owner about premium prize: {e}")
            
            await update.message.reply_text(
                "🎉 <b>Congratulations! Premium Prize Won!</b>\n\n"
                f"Our admin {OWNER_USERNAME} will contact you shortly to deliver your premium reward!",
                parse_mode='HTML'
            )
            
        elif command == 'check_channel':
            # Channel verification from TWA
            has_joined = await check_channel_membership(user_id, context)
            if users_collection:
                users_collection.update_one(
                    {"user_id": user_id},
                    {"$set": {"has_joined_channel": has_joined}}
                )
            
            if has_joined:
                await update.message.reply_text("✅ Channel verified! Bonuses activated!")
            else:
                await update.message.reply_text("❌ Please join the channel first!")
                
    except Exception as e:
        logger.error(f"Error processing TWA data: {e}")
        await update.message.reply_text("❌ Error processing your request. Please try again.")

# Owner Approval Handler
async def handle_owner_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle withdrawal approval by owner"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != OWNER_ID:
        await query.edit_message_text("❌ Only owner can approve withdrawals!")
        return
    
    data = query.data
    if data.startswith('approve_'):
        try:
            parts = data.split('_')
            user_id = int(parts[1])
            amount = float(parts[2])
            
            # Update withdrawal status
            if withdrawals_collection:
                withdrawals_collection.update_one(
                    {"user_id": user_id, "status": "pending"},
                    {
                        "$set": {
                            "status": "approved",
                            "approved_date": datetime.now(),
                            "approved_by": query.from_user.id
                        }
                    }
                )
            
            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ <b>Withdrawal Approved!</b>\n\n"
                         f"💰 <b>Amount:</b> ₹{amount}\n"
                         f"🕒 <b>Status:</b> Approved\n"
                         f"💳 <b>Transfer:</b> Within 24 hours\n\n"
                         f"Thank you for using our service! 🎉",
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Could not notify user {user_id}: {e}")
            
            await query.edit_message_text(f"✅ Withdrawal approved for user {user_id}!")
            
        except (ValueError, IndexError) as e:
            logger.error(f"Error processing approval: {e}")
            await query.edit_message_text("❌ Error processing approval!")

# Scheduled Tasks
async def health_check(context: ContextTypes.DEFAULT_TYPE):
    """Health check for Render"""
    logger.info("🤖 Bot Health Check - Running...")

async def reset_daily_searches(context: ContextTypes.DEFAULT_TYPE):
    """Reset daily search limits"""
    logger.info("🔄 Daily searches reset for new day")

async def calculate_leaderboard(context: ContextTypes.DEFAULT_TYPE):
    """Calculate daily leaderboard"""
    logger.info("🏆 Calculating daily leaderboard...")

# Main Application
def main() -> None:
    """Main function to start the bot"""
    try:
        # Create application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        handlers = [
            CommandHandler("start", start),
            CommandHandler("search", movie_search),
            CommandHandler("movie", movie_search),
            CommandHandler("join", join_channel),
            CommandHandler("balance", balance),
            CommandHandler("help", help_command),
            MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_twa_message),
            CallbackQueryHandler(handle_owner_approval, pattern=r"^approve_")
        ]
        
        for handler in handlers:
            application.add_handler(handler)
        
        # Job queue for scheduled tasks
        job_queue = application.job_queue
        
        # Health check every 5 minutes
        job_queue.run_repeating(health_check, interval=300, first=10)
        
        # Daily tasks
        job_queue.run_daily(reset_daily_searches, time=datetime.time(hour=0, minute=0))
        job_queue.run_daily(calculate_leaderboard, time=datetime.time(hour=23, minute=30))
        
        # Start polling
        logger.info("🚀 Starting Promotion User Bot...")
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
    except Exception as e:
        logger.error(f"❌ Bot startup failed: {e}")
        time.sleep(30)
        main()

# Dual execution for Render
if __name__ == "__main__":
    import threading
    
    def run_flask():
        """Run Flask server for Render"""
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    
    def run_bot():
        """Run Telegram bot"""
        main()
    
    # Start both services
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    
    flask_thread.start()
    bot_thread.start()
    
    logger.info("🎯 Both services started: Flask + Telegram Bot")
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(60)
            logger.info("💚 System running...")
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
