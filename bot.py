import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import pymongo
from datetime import datetime, time as dt_time # time को dt_time alias किया
import json
import time
from flask import Flask

# Logging Setup
# FIX: Logging को थोड़ा साफ किया
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
# YEH PEHLE AAYEGA

# Flask app for Render 24/7
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Promotion User Bot is Running! Status: ACTIVE"

@app.route('/health')
def health():
    return {"status": "active", "timestamp": datetime.now().isoformat()}

# Configuration
# Note: Render variables will be automatically pulled from environment variables
MONGODB_URI = os.getenv("MONGODB_URI") 
BOT_TOKEN = os.getenv("BOT_TOKEN") 

# MongoDB Setup
users_collection = None
referrals_collection = None
settings_collection = None
leaderboard_collection = None
movie_searches_collection = None
withdrawals_collection = None

if MONGODB_URI:
    try:
        # Increased timeout for better cloud connection
        client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=20000) 
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
        logger.error(f"❌ MongoDB connection error: {e}. Bot will run without database functions.")
else:
    logger.warning("⚠️ MONGODB_URI is not set. Database functionality will be disabled.")


# Constants (Same as original)
MOVIE_CHANNEL_ID = -1002283182645  # @asbhai_bsr
OWNER_ID = 7315805571  # @asbhaibsr
OWNER_USERNAME = "@asbhaibsr"
REFERRAL_BONUS = 2.0
DAILY_SEARCH_BONUS = 0.50
SPIN_PRIZES = [0.10, 0.20, 0.50, 1.00, 2.00, 5.00, 10.00, 0.00, 0.00, "premium"]

# Utility Functions (Same as original)
async def check_channel_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user has joined the movie channel"""
    try:
        member = await context.bot.get_chat_member(chat_id=MOVIE_CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        # User not found in chat, bot not admin, or channel ID is wrong
        logger.error(f"Error checking channel membership for {user_id}: {e}")
        return False

def has_searched_today(user_id: int) -> bool:
    """Check if user has already searched today"""
    if not movie_searches_collection:
        return False
        
    # Get today's start in local time (important for daily reset)
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
    
    # Calculate total referral earnings (Requires aggregation pipeline)
    pipeline = [
        {"$match": {"referrer_id": user_id, "bonus_paid": True}},
        {"$group": {"_id": None, "total_earnings": {"$sum": "$earnings"}}}
    ]
    
    result = list(referrals_collection.aggregate(pipeline))
    total_earnings = result[0]["total_earnings"] if result and result[0] and "total_earnings" in result[0] else 0
    
    return {
        "total": total_refs,
        "earnings": total_earnings,
        "pending": pending_refs
    }
    
async def _process_pending_referrals(user_id: int, context: ContextTypes.DEFAULT_TYPE, message=None):
    """Internal function to process pending referral bonuses"""
    if not referrals_collection or not users_collection:
        return "", 0, 0
    
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

    return bonus_msg, total_bonus, total_spins

# Command Handlers (Same as original, modified slightly for flow)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command with referral system"""
    user = update.effective_user
    user_id = user.id
    
    if not update.message:
        return # Ignore non-message updates if possible, though /start is usually a message

    logger.info(f"User {user_id} started the bot")
    
    if not users_collection:
        await update.message.reply_text("❌ Database not connected. Please contact admin.", parse_mode='HTML')
        return

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
        users_collection.insert_one(user_data)
    
    # Check referral
    if context.args and context.args[0].startswith('ref_'):
        try:
            referrer_id = int(context.args[0].split('_')[1])
            if referrer_id != user_id: 
                referrer_data = get_user_data(referrer_id)
                
                if referrer_data and referrals_collection:
                    existing_ref = referrals_collection.find_one({
                        "referrer_id": referrer_id,
                        "referred_id": user_id
                    })
                    
                    if not existing_ref:
                        referral_data = {
                            "referrer_id": referrer_id,
                            "referred_id": user_id,
                            "referral_date": datetime.now(),
                            "earnings": 0.0,
                            "spin_given": False,
                            "bonus_paid": False,
                            "reason": "Pending channel join"
                        }
                        referrals_collection.insert_one(referral_data)
                        users_collection.update_one(
                            {"user_id": referrer_id},
                            {"$inc": {"total_referrals": 1}}
                        )
        except (ValueError, IndexError) as e:
            logger.error(f"Invalid referral code or database issue: {e}")
    
    # Check channel membership
    has_joined = await check_channel_membership(user_id, context)
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"has_joined_channel": has_joined}}
    )
    if has_joined:
        await _process_pending_referrals(user_id, context, update.message)

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
    
    if not update.message or not users_collection or not movie_searches_collection:
        await update.message.reply_text("❌ Error: Database service is unavailable. Please try again later.")
        return

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
        # Try to run start to ensure user data exists
        await start(update, context) 
        user_data = get_user_data(user_id)
        if not user_data:
             await update.message.reply_text("❌ Error: Could not retrieve or create user data. Please try /start again.")
             return
    
    # Update earnings
    update_user_balance(user_id, DAILY_SEARCH_BONUS)
    
    # Log search
    search_data = {
        "user_id": user_id,
        "user_name": user.first_name,
        "search_date": datetime.now(),
        "earnings": DAILY_SEARCH_BONUS,
        "status": "completed"
    }
    movie_searches_collection.insert_one(search_data)
    
    # Update user stats
    users_collection.update_one(
        {"user_id": user_id},
        {
            "$inc": {"movie_searches": 1},
            "$set": {"last_search_date": datetime.now()}
        }
    )
    
    # Success message
    updated_user_data = get_user_data(user_id) 
    
    twa_url = f"https://ashhabsr.github.io/Promotion-user-panel/?user_id={user_id}"
    await update.message.reply_text(
        f"🎬 <b>Movie Search Completed!</b>\n\n"
        f"✅ <b>Earned:</b> ₹{DAILY_SEARCH_BONUS}\n"
        f"💰 <b>Total Balance:</b> ₹{updated_user_data.get('earnings', 0.0):.2f}\n" 
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
    
    if not update.message or not users_collection:
        await update.message.reply_text("❌ Error: Database service is unavailable. Please try again later.")
        return
        
    has_joined = await check_channel_membership(user_id, context)
    
    if has_joined:
        # Update user status
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"has_joined_channel": True}}
        )
        
        bonus_msg, _, _ = await _process_pending_referrals(user_id, context)

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
    
    if not update.message or not users_collection:
        await update.message.reply_text("❌ Error: Database service is unavailable. Please try again later.")
        return
        
    user_data = get_user_data(user_id)
    
    if not user_data:
        await start(update, context)
        # Attempt to re-fetch after start
        user_data = get_user_data(user_id)
        if not user_data:
            return
    
    ref_stats = get_referral_stats(user_id)
    twa_url = f"https://ashhabsr.github.io/Promotion-user-panel/?user_id={user_id}"
    
    balance_text = f"""
💰 <b>Your Earnings Summary</b>

📊 <b>Main Balance:</b> ₹{user_data.get('earnings', 0.0):.2f}
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
    if not update.message: return

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

# TWA Data Handler (Same as original, with balance check improvement)
async def handle_twa_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle data from Telegram Web App"""
    if not update.message or not users_collection or not withdrawals_collection:
        await update.message.reply_text("❌ Error: Database service is unavailable. Please try again later.")
        return
        
    try:
        web_app_data = update.message.web_app_data
        data = json.loads(web_app_data.data)
        user_id = update.effective_user.id
        
        command = data.get('command')
        logger.info(f"TWA Data from {user_id}: {command}")
        
        if command == 'update_balance':
            amount = float(data.get('amount', 0.0))
            if amount > 0:
                update_user_balance(user_id, amount)
            
            # Decrease spin count
            users_collection.update_one(
                {"user_id": user_id},
                {"$inc": {"spin_count": -1}}
            )
            
            await update.message.reply_text(f"✅ Spin completed! Added ₹{amount:.2f} to your balance.")
            
        elif command == 'withdrawal_request':
            amount = float(data.get('amount', 0.0))
            details = data.get('details', {})
            
            user_data = get_user_data(user_id)
            current_balance = user_data.get('earnings', 0.0) if user_data else 0.0

            if amount < 80:
                await update.message.reply_text("❌ Minimum withdrawal amount is ₹80!")
                return
            
            if amount > current_balance:
                await update.message.reply_text(f"❌ Insufficient balance! Your current balance is ₹{current_balance:.2f}.")
                return

            # Create withdrawal request
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
🆔 <b>ID:</b> <code>{user_id}</code>
📛 <b>Username:</b> @{update.effective_user.username or 'N/A'}
💰 <b>Amount:</b> ₹{amount:.2f}

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
            
            # Deduct user balance
            update_user_balance(user_id, -amount)
            
            await update.message.reply_text(
                f"✅ <b>Withdrawal Request Submitted!</b>\n\n"
                f"💰 <b>Amount:</b> ₹{amount:.2f}\n"
                f"⏰ <b>Processing Time:</b> 24 hours\n"
                f"📞 <b>Contact:</b> {OWNER_USERNAME} for queries",
                parse_mode='HTML'
            )
            
        elif command == 'premium_prize':
            users_collection.update_one(
                {"user_id": user_id},
                {"$inc": {"spin_count": -1}}
            )

            try:
                owner_text = f"🎁 <b>PREMIUM PRIZE WINNER!</b>\n\n" \
                           f"👤 <b>User:</b> {update.effective_user.first_name}\n" \
                           f"🆔 <b>ID:</b> <code>{user_id}</code>\n" \
                           f"📛 <b>Username:</b> @{update.effective_user.username or 'N/A'}\n" \
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
            users_collection.update_one(
                {"user_id": user_id},
                {"$set": {"has_joined_channel": has_joined}}
            )
            
            if has_joined:
                bonus_msg, _, _ = await _process_pending_referrals(user_id, context)
                await update.message.reply_text(f"✅ Channel verified! Bonuses activated!{bonus_msg}")
            else:
                await update.message.reply_text("❌ Please join the channel first!")
                
    except Exception as e:
        logger.error(f"Error processing TWA data: {e}")
        await update.message.reply_text("❌ Error processing your request. Please try again.")

# Owner Approval Handler (Same as original)
async def handle_owner_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle withdrawal approval by owner"""
    query = update.callback_query
    
    if not query or not withdrawals_collection:
        logger.error("Callback query or DB is missing in handle_owner_approval.")
        return

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
            result = withdrawals_collection.update_one(
                {"user_id": user_id, "amount": amount, "status": "pending"},
                {
                    "$set": {
                        "status": "approved",
                        "approved_date": datetime.now(),
                        "approved_by": query.from_user.id
                    }
                }
            )
            
            if result.matched_count == 0:
                 await query.edit_message_text(f"❌ Withdrawal for user {user_id} (₹{amount}) not found or already processed!")
                 return

            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ <b>Withdrawal Approved!</b>\n\n"
                         f"💰 <b>Amount:</b> ₹{amount:.2f}\n"
                         f"🕒 <b>Status:</b> Approved\n"
                         f"💳 <b>Transfer:</b> Within 24 hours\n\n"
                         f"Thank you for using our service! 🎉",
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Could not notify user {user_id}: {e}")
            
            await query.edit_message_text(f"✅ Withdrawal approved for user {user_id} (₹{amount:.2f})!")
            
        except (ValueError, IndexError) as e:
            logger.error(f"Error processing approval: {e}")
            await query.edit_message_text("❌ Error processing approval!")

# Scheduled Tasks (Same as original)
async def health_check(context: ContextTypes.DEFAULT_TYPE):
    """Health check for Render"""
    logger.info("🤖 Bot Health Check - Running...")

async def reset_daily_searches(context: ContextTypes.DEFAULT_TYPE):
    """Reset daily search limits"""
    logger.info("🔄 Daily searches reset/stats calculated for new day")

async def calculate_leaderboard(context: ContextTypes.DEFAULT_TYPE):
    """Calculate daily leaderboard"""
    logger.info("🏆 Calculating daily leaderboard...")

# Main Application
def main() -> None:
    """Main function to start the bot"""
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN is not set. Cannot start the bot.")
        return

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
        
        # Daily tasks: FIX 1 - datetime.time() constructor called correctly
        # Note: Jobs run based on the bot's server time (likely UTC on Render)
        job_queue.run_daily(reset_daily_searches, time=dt_time(hour=0, minute=0))
        job_queue.run_daily(calculate_leaderboard, time=dt_time(hour=23, minute=30))
        
        # Start polling
        logger.info("🚀 Starting Promotion User Bot...")
        
        # FIX 2: Added 'close_loop=False' for better threading compatibility with Flask
        # Also ensured that no unsupported arguments are passed
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
            close_loop=False
        )
        
    except Exception as e:
        logger.error(f"❌ Bot startup failed: {e}")
        # Added sleep for stability before application attempts to exit
        time.sleep(5)
        logger.error("❌ Exiting bot process after failure.")

# Dual execution for Render (Same as original)
if __name__ == "__main__":
    import threading
    
    def run_flask():
        """Run Flask server for Render"""
        port = int(os.environ.get('PORT', 5000))
        # use_reloader=False is crucial for multi-threading environments
        try:
            logger.info(f"Starting Flask server on port {port}")
            app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
        except Exception as e:
            logger.error(f"❌ Flask startup failed: {e}")
    
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
            # Log every minute to keep the system awake on some free tiers (like Render free tier)
            logger.info("💚 System running...")
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user (KeyboardInterrupt)")
    except Exception as e:
        logger.error(f"❌ Main thread loop error: {e}")

