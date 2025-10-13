import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import pymongo
from datetime import datetime, timedelta
import asyncio
import random

# MongoDB setup
client = pymongo.MongoClient(os.getenv("MONGODB_URI"))
db = client.promotion_bot
users_collection = db.users
referrals_collection = db.referrals
settings_collection = db.settings
leaderboard_collection = db.leaderboard
movie_searches_collection = db.movie_searches

# Bot token
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Your channel and owner details
MOVIE_CHANNEL_ID = -1002283182645  # @asbhai_bsr channel ID
OWNER_ID = 7315805571  # Owner ID (@asbhaibsr)
OWNER_USERNAME = "@asbhaibsr"  # Owner username

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Check if user joined movie channel
async def check_channel_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=MOVIE_CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking channel membership: {e}")
        return False

# Check if user already searched today
def has_searched_today(user_id: int) -> bool:
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_searches = movie_searches_collection.count_documents({
        "user_id": user_id,
        "search_date": {"$gte": today_start}
    })
    return today_searches > 0

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id
    
    # Check if user exists in database
    user_data = users_collection.find_one({"user_id": user_id})
    
    if not user_data:
        # Create new user
        user_data = {
            "user_id": user_id,
            "first_name": user.first_name,
            "last_name": user.last_name or "",
            "username": user.username or "",
            "earnings": 0.0,
            "spin_count": 3,  # New users get 3 spins
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
            referrer_id = int(context.args[0].split('_')[1])
            referrer_data = users_collection.find_one({"user_id": referrer_id})
            
            if referrer_data:
                # Check if referrer has joined channel
                referrer_joined = await check_channel_membership(referrer_id, context)
                
                if referrer_joined:
                    # Update referrer's stats - Give 1 SPIN + ₹2 ONLY if joined channel
                    referral_bonus = 2.0  # ₹2 per referral
                    users_collection.update_one(
                        {"user_id": referrer_id},
                        {
                            "$inc": {
                                "earnings": referral_bonus,
                                "referral_earnings": referral_bonus,
                                "total_referrals": 1,
                                "spin_count": 1  # +1 Spin for referral
                            }
                        }
                    )
                    
                    # Add to referrals collection
                    referral_data = {
                        "referrer_id": referrer_id,
                        "referred_id": user_id,
                        "referral_date": datetime.now(),
                        "earnings": referral_bonus,
                        "spin_given": True,
                        "bonus_paid": True
                    }
                    referrals_collection.insert_one(referral_data)
                    
                    # Notify referrer
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=f"🎉 Congratulations! {user.first_name} joined using your referral link.\n\nYou earned: ₹{referral_bonus} + 1 Spin!\n\n💰 Total earnings: ₹{referrer_data['earnings'] + referral_bonus:.2f}",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("Open Earning Panel", web_app=WebAppInfo(url=f"https://ashhabsr.github.io/Promotion-user-panel/?user_id={referrer_id}"))
                            ]])
                        )
                    except Exception as e:
                        logger.error(f"Could not notify referrer: {e}")
                else:
                    # Referrer hasn't joined channel - no bonus
                    referral_data = {
                        "referrer_id": referrer_id,
                        "referred_id": user_id,
                        "referral_date": datetime.now(),
                        "earnings": 0.0,
                        "spin_given": False,
                        "bonus_paid": False,
                        "reason": "Referrer not joined channel"
                    }
                    referrals_collection.insert_one(referral_data)
                    
                    # Notify referrer to join channel
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=f"❌ {user.first_name} joined using your link BUT you didn't get bonus!\n\nJoin our channel to get ₹2 + 1 Spin per referral:\nhttps://t.me/asbhai_bsr",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("Join Channel", url="https://t.me/asbhai_bsr")
                            ]])
                        )
                    except Exception as e:
                        logger.error(f"Could not notify referrer: {e}")
    
    # Check channel membership
    has_joined = await check_channel_membership(user_id, context)
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"has_joined_channel": has_joined}}
    )
    
    # Create TWA button
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
    
    # Check if user searched today
    searched_today = has_searched_today(user_id)
    if searched_today:
        welcome_text += "⏰ Today's movie search: ✅ COMPLETED\n"
    else:
        welcome_text += "⏰ Today's movie search: ❌ PENDING\n"
    
    welcome_text += "\n💰 Earn money by:\n• Inviting friends (₹2 + 1 Spin after joining channel)\n• Daily movie search (₹0.50 once per day)\n• Spinning the wheel\n• Completing offers\n\nClick below to open your earning panel:"
    
    await update.message.reply_html(welcome_text, reply_markup=reply_markup)

# Movie search command - User searches for movies
async def movie_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    # Check if user has joined channel
    has_joined = await check_channel_membership(user_id, context)
    
    if not has_joined:
        await update.message.reply_text(
            "❌ You need to join our channel first to earn from searches!\n\n"
            "Join here: https://t.me/asbhai_bsr\n\n"
            "After joining, try again!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel 🎬", url="https://t.me/asbhai_bsr")]])
        )
        return
    
    # Check if user already searched today
    if has_searched_today(user_id):
        await update.message.reply_text(
            "⏰ You have already completed today's movie search!\n\n"
            "Come back tomorrow for another ₹0.50 earning! 💰\n\n"
            "You can still earn by:\n"
            "• Inviting friends (₹2 + 1 Spin each)\n"
            "• Spinning the wheel\n"
            "• Completing offers",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Open Earning Panel", web_app=WebAppInfo(url=f"https://ashhabsr.github.io/Promotion-user-panel/?user_id={user_id}"))
            ]])
        )
        return
    
    # Process movie search (ONCE PER DAY)
    search_earning = 0.50  # ₹0.50 per day
    
    # Get current user data
    user_data = users_collection.find_one({"user_id": user_id})
    
    # Update user data
    users_collection.update_one(
        {"user_id": user_id},
        {
            "$inc": {
                "earnings": search_earning,
                "movie_searches": 1
            },
            "$set": {
                "last_search_date": datetime.now()
            }
        }
    )
    
    # Log movie search
    search_data = {
        "user_id": user_id,
        "user_name": user_name,
        "search_date": datetime.now(),
        "earnings": search_earning,
        "status": "completed"
    }
    movie_searches_collection.insert_one(search_data)
    
    # Send confirmation
    await update.message.reply_text(
        f"🎬 Today's movie search completed!\n\n"
        f"✅ You earned: ₹{search_earning}\n"
        f"💰 Total earnings: ₹{user_data['earnings'] + search_earning:.2f}\n\n"
        f"🔄 Next search available: Tomorrow\n\n"
        f"Keep inviting friends to earn more! 💰",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Open Earning Panel", web_app=WebAppInfo(url=f"https://ashhabsr.github.io/Promotion-user-panel/?user_id={user_id}"))
        ]])
    )

# Check referral bonuses for users who joined channel later
async def check_referral_bonuses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    # Check if user has joined channel now
    has_joined = await check_channel_membership(user_id, context)
    
    if has_joined:
        # Check for pending referrals without bonus
        pending_referrals = referrals_collection.find({
            "referrer_id": user_id,
            "bonus_paid": False
        })
        
        total_bonus = 0
        total_spins = 0
        
        for referral in pending_referrals:
            # Pay pending bonus
            referral_bonus = 2.0
            users_collection.update_one(
                {"user_id": user_id},
                {
                    "$inc": {
                        "earnings": referral_bonus,
                        "referral_earnings": referral_bonus,
                        "spin_count": 1
                    }
                }
            )
            
            referrals_collection.update_one(
                {"_id": referral["_id"]},
                {
                    "$set": {
                        "earnings": referral_bonus,
                        "spin_given": True,
                        "bonus_paid": True,
                        "bonus_paid_date": datetime.now()
                    }
                }
            )
            
            total_bonus += referral_bonus
            total_spins += 1
        
        if total_bonus > 0:
            await update.message.reply_text(
                f"🎉 Channel joined! Pending bonuses activated!\n\n"
                f"✅ You received: ₹{total_bonus:.2f} + {total_spins} Spins\n"
                f"for {total_spins} pending referrals!\n\n"
                f"Keep inviting more friends! 💰",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Open Earning Panel", web_app=WebAppInfo(url=f"https://ashhabsr.github.io/Promotion-user-panel/?user_id={user_id}"))
                ]])
            )
        else:
            await update.message.reply_text(
                "✅ Channel joined successfully!\n\n"
                "Now you can:\n"
                "• Earn ₹0.50 daily from movie search\n"
                "• Get ₹2 + 1 Spin for each referral\n"
                "• Access all earning features!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Open Earning Panel", web_app=WebAppInfo(url=f"https://ashhabsr.github.io/Promotion-user-panel/?user_id={user_id}"))
                ]])
            )
    else:
        await update.message.reply_text(
            "❌ You haven't joined our channel yet!\n\n"
            "Join here: https://t.me/asbhai_bsr\n\n"
            "After joining, use this command again to activate earnings!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel 🎬", url="https://t.me/asbhai_bsr")]])
        )

# Handle TWA data
async def handle_twa_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    try:
        import json
        data = json.loads(query.data)
        user_id = query.from_user.id
        
        if data.get('command') == 'update_balance':
            amount = data.get('amount')
            users_collection.update_one(
                {"user_id": user_id},
                {"$inc": {"earnings": amount}}
            )
            await query.edit_message_text(f"✅ Balance updated! Added ₹{amount}")
            
        elif data.get('command') == 'withdrawal_request':
            amount = data.get('amount')
            details = data.get('details')
            
            # Process withdrawal and notify owner
            withdrawal_data = {
                "user_id": user_id,
                "amount": amount,
                "details": details,
                "status": "pending",
                "request_date": datetime.now()
            }
            db.withdrawals.insert_one(withdrawal_data)
            
            # Notify owner directly
            try:
                user_info = users_collection.find_one({"user_id": user_id})
                user_name = user_info.get('first_name', 'Unknown')
                username = user_info.get('username', 'No username')
                
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=f"🔄 NEW WITHDRAWAL REQUEST\n\n"
                         f"👤 User: {user_name} (@{username})\n"
                         f"🆔 ID: {user_id}\n"
                         f"💰 Amount: ₹{amount}\n\n"
                         f"📋 Details:\n"
                         f"• Name: {details.get('fullName')}\n"
                         f"• Account: {details.get('accountNumber')}\n"
                         f"• IFSC: {details.get('ifscCode')}\n"
                         f"• UPI: {details.get('upiId')}\n"
                         f"• Mobile: {details.get('mobileNo')}\n"
                         f"• Email: {details.get('emailId')}\n\n"
                         f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("Contact User", url=f"tg://user?id={user_id}"),
                        InlineKeyboardButton("Approve", callback_data=f"approve_{user_id}_{amount}")
                    ]])
                )
            except Exception as e:
                logger.error(f"Could not notify owner: {e}")
                
            await query.edit_message_text(
                "✅ Withdrawal request submitted!\n\n"
                "💰 Amount: ₹" + str(amount) + "\n"
                "⏰ Processing time: 24 hours\n\n"
                "For any query, contact " + OWNER_USERNAME
            )
            
        elif data.get('command') == 'premium_prize':
            # Notify owner about premium prize
            try:
                user_info = users_collection.find_one({"user_id": user_id})
                user_name = user_info.get('first_name', 'Unknown')
                
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=f"🎁 PREMIUM PRIZE WINNER!\n\n"
                         f"👤 User: {user_name}\n"
                         f"🆔 ID: {user_id}\n"
                         f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                         f"Please contact them to deliver the premium prize.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("Contact Winner", url=f"tg://user?id={user_id}")
                    ]])
                )
            except Exception as e:
                logger.error(f"Could not notify owner about premium prize: {e}")
                
            await query.edit_message_text(
                "🎉 Congratulations! You won a premium prize!\n\n"
                "Our admin " + OWNER_USERNAME + " will contact you soon."
            )
            
        elif data.get('command') == 'check_channel':
            # Check channel membership from TWA
            has_joined = await check_channel_membership(user_id, context)
            users_collection.update_one(
                {"user_id": user_id},
                {"$set": {"has_joined_channel": has_joined}}
            )
            
            if has_joined:
                # Check for pending bonuses
                await check_referral_bonuses(update, context)
            else:
                await query.edit_message_text("❌ You haven't joined the channel yet!")
            
    except Exception as e:
        logger.error(f"Error processing TWA data: {e}")
        await query.edit_message_text("❌ Error processing your request. Please try again.")

# Handle owner approval
async def handle_owner_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        
        # Update withdrawal status
        db.withdrawals.update_one(
            {"user_id": user_id, "status": "pending"},
            {"$set": {"status": "approved", "approved_date": datetime.now()}}
        )
        
        # Reset user balance after withdrawal
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"earnings": 0.0}}
        )
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ Your withdrawal request for ₹{amount} has been approved!\n\n"
                     f"The amount will be transferred within 24 hours.\n\n"
                     f"Thank you for using our service! 💰",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Open Earning Panel", web_app=WebAppInfo(url=f"https://ashhabsr.github.io/Promotion-user-panel/?user_id={user_id}"))
                ]])
            )
        except Exception as e:
            logger.error(f"Could not notify user: {e}")
        
        await query.edit_message_text(f"✅ Withdrawal approved for user {user_id}!")

# Reset daily searches (run at midnight)
async def reset_daily_searches(context: ContextTypes.DEFAULT_TYPE):
    # This would reset daily search limits
    # In production, you'd implement this with a scheduler
    logger.info("Daily searches reset - Ready for new day!")

# Main function
def main() -> None:
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", movie_search))
    application.add_handler(CommandHandler("movie", movie_search))
    application.add_handler(CommandHandler("join", check_referral_bonuses))
    application.add_handler(CallbackQueryHandler(handle_twa_data, pattern=r'^{.*}$'))
    application.add_handler(CallbackQueryHandler(handle_owner_approval, pattern=r'^approve_'))
    
    # Add job queue for daily reset
    job_queue = application.job_queue
    # job_queue.run_daily(reset_daily_searches, time=datetime.time(hour=0, minute=0))
    
    # Start the Bot
    application.run_polling()

if __name__ == "__main__":
    main()
