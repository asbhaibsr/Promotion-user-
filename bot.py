import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import pymongo
from datetime import datetime, timedelta
import asyncio

# MongoDB setup
client = pymongo.MongoClient(os.getenv("MONGODB_URI"))
db = client.promotion_bot
users_collection = db.users
referrals_collection = db.referrals
settings_collection = db.settings
leaderboard_collection = db.leaderboard

# Bot token
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

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
            "spin_count": 3,
            "last_spin_date": None,
            "joined_date": datetime.now(),
            "referral_code": f"ref_{user_id}",
            "total_referrals": 0,
            "referral_earnings": 0.0
        }
        users_collection.insert_one(user_data)
        
        # Check if this is a referral
        if context.args and context.args[0].startswith('ref_'):
            referrer_id = int(context.args[0].split('_')[1])
            referrer_data = users_collection.find_one({"user_id": referrer_id})
            
            if referrer_data:
                # Update referrer's stats
                referral_bonus = 2.0  # ₹2 per referral
                users_collection.update_one(
                    {"user_id": referrer_id},
                    {
                        "$inc": {
                            "earnings": referral_bonus,
                            "referral_earnings": referral_bonus,
                            "total_referrals": 1,
                            "spin_count": 1
                        }
                    }
                )
                
                # Add to referrals collection
                referral_data = {
                    "referrer_id": referrer_id,
                    "referred_id": user_id,
                    "referral_date": datetime.now(),
                    "earnings": referral_bonus
                }
                referrals_collection.insert_one(referral_data)
                
                # Notify referrer
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 Congratulations! {user.first_name} joined using your referral link. You earned ₹{referral_bonus} and got 1 extra spin!"
                    )
                except Exception as e:
                    logger.error(f"Could not notify referrer: {e}")
    
    # Create TWA button
    keyboard = [
        [InlineKeyboardButton(
            "Open Earning Panel", 
            web_app=WebAppInfo(url=f"https://yourdomain.com/index.html?user_id={user_id}")
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        f"👋 Hello {user.mention_html()}!\n\n"
        "Welcome to Promotion User Bot! 🎉\n\n"
        "Earn money by:\n"
        "• Inviting friends\n"
        "• Joining movie groups\n"
        "• Spinning the wheel daily\n"
        "• Completing offers\n\n"
        "Click the button below to open your earning panel:",
        reply_markup=reply_markup
    )

# Handle TWA data
async def handle_twa_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    try:
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
            
            # Process withdrawal (in a real app, this would integrate with payment gateway)
            # For now, just log and notify admin
            withdrawal_data = {
                "user_id": user_id,
                "amount": amount,
                "details": details,
                "status": "pending",
                "request_date": datetime.now()
            }
            db.withdrawals.insert_one(withdrawal_data)
            
            # Notify admin
            admin_id = 123456789  # Replace with actual admin ID
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"🔄 New withdrawal request:\n"
                         f"User: {user_id}\n"
                         f"Amount: ₹{amount}\n"
                         f"Name: {details.get('fullName')}\n"
                         f"Account: {details.get('accountNumber')}\n"
                         f"UPI: {details.get('upiId')}"
                )
            except Exception as e:
                logger.error(f"Could not notify admin: {e}")
                
            await query.edit_message_text("✅ Withdrawal request submitted! We'll process it within 24 hours.")
            
        elif data.get('command') == 'premium_prize':
            # Notify admin about premium prize
            admin_id = 123456789  # Replace with actual admin ID
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"🎁 Premium Prize Winner!\n"
                         f"User ID: {user_id}\n"
                         f"Please contact them to deliver the premium prize."
                )
            except Exception as e:
                logger.error(f"Could not notify admin about premium prize: {e}")
                
            await query.edit_message_text("🎉 Congratulations! You won a premium prize! Our admin will contact you soon.")
            
    except Exception as e:
        logger.error(f"Error processing TWA data: {e}")
        await query.edit_message_text("❌ Error processing your request. Please try again.")

# Leaderboard calculation (run daily)
async def calculate_leaderboard():
    # Get yesterday's date
    yesterday = datetime.now() - timedelta(days=1)
    start_of_day = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Calculate scores based on earnings and referrals
    pipeline = [
        {
            "$match": {
                "joined_date": {"$gte": start_of_day, "$lte": end_of_day}
            }
        },
        {
            "$lookup": {
                "from": "referrals",
                "localField": "user_id",
                "foreignField": "referrer_id",
                "as": "referrals"
            }
        },
        {
            "$project": {
                "user_id": 1,
                "first_name": 1,
                "earnings": 1,
                "referral_count": {"$size": "$referrals"},
                "score": {
                    "$add": [
                        "$earnings",
                        {"$multiply": [{"$size": "$referrals"}, 5]}  # 5 points per referral
                    ]
                }
            }
        },
        {
            "$sort": {"score": -1}
        },
        {
            "$limit": 5
        }
    ]
    
    top_users = list(users_collection.aggregate(pipeline))
    
    # Prizes
    prizes = [200, 150, 100, 50, 0]  # 5th prize is premium (handled manually)
    
    # Distribute prizes and update leaderboard
    for i, user in enumerate(top_users):
        prize_amount = prizes[i] if i < len(prizes) else 0
        
        if prize_amount > 0:
            # Add prize to user's balance
            users_collection.update_one(
                {"user_id": user["user_id"]},
                {"$inc": {"earnings": prize_amount}}
            )
            
            # Notify user
            try:
                await application.bot.send_message(
                    chat_id=user["user_id"],
                    text=f"🏆 Congratulations! You ranked #{i+1} on yesterday's leaderboard and won ₹{prize_amount}!"
                )
            except Exception as e:
                logger.error(f"Could not notify leaderboard winner: {e}")
        
        # Record in leaderboard collection
        leaderboard_data = {
            "user_id": user["user_id"],
            "rank": i + 1,
            "score": user["score"],
            "prize": prize_amount,
            "date": yesterday.date()
        }
        leaderboard_collection.insert_one(leaderboard_data)
    
    logger.info(f"Leaderboard calculated for {yesterday.date()}")

# Scheduled task for leaderboard
async def scheduled_leaderboard(context: ContextTypes.DEFAULT_TYPE):
    await calculate_leaderboard()

# Main function
def main() -> None:
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_twa_data, pattern=r'^{.*}$'))
    
    # Add job queue for scheduled tasks
    job_queue = application.job_queue
    job_queue.run_daily(scheduled_leaderboard, time=datetime.time(hour=0, minute=0))  # Run at midnight
    
    # Start the Bot
    application.run_polling()

if __name__ == "__main__":
    main()
