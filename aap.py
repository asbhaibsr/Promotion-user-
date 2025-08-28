import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime, timedelta

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
GROUP_ID = int(os.getenv("GROUP_ID"))
YOUR_TELEGRAM_HANDLE = os.getenv("YOUR_TELEGRAM_HANDLE")

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client.get_database('bot_database')
users_collection = db.get_collection('users')
referrals_collection = db.get_collection('referrals')

# Flask app for Render
app = Flask(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    referral_id = context.args[0].replace("ref_", "") if context.args and context.args[0].startswith("ref_") else None
    
    await update.message.reply_html(
        f"Hey {user.mention_html()}! Welcome to our bot. Join our group for a fun experience. Click the link below to get started and have fun!\n\n**GROUP LINK HERE**"
    )
    
    # Store referral data
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
            # Notify referrer
            try:
                await context.bot.send_message(
                    chat_id=int(referral_id),
                    text=f"🥳 Good news! A new user has joined through your link: {user.full_name} (@{user.username})."
                )
            except Exception as e:
                logging.error(f"Could not notify referrer {referral_id}: {e}")

async def earn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
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
            text=f"New user {user.full_name} (@{user.username}, ID: {user.id}) wants to start earning. Approve?",
            reply_markup=reply_markup,
        )
        await update.message.reply_text("Your request has been sent to the admin for approval. Please wait.")
    elif user_data.get("is_approved"):
        referral_link = f"https://t.me/your_bot_username?start=ref_{user.id}"
        
        await update.message.reply_text(
            f"You are approved! Here is your referral link:\n\n`{referral_link}`\n\n"
            f"💰 **Rules for Earning**\n"
            f"1. Get people to join our group using your link.\n"
            f"2. When your referred user searches for a movie in the group, they'll be taken to our bot via a shortlink.\n"
            f"3. After they complete the shortlink process, you'll earn money. Note that you earn only **once per day** per referred user.\n\n"
            f"**Earnings Breakdown:**\n"
            f"**Owner's Share:** $0.006\n"
            f"**Your Share:** $0.0018\n\n"
            f"Your earnings will automatically update in your account."
        )
    else:
        await update.message.reply_text("Your request is pending. Please wait for the admin's approval.")

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_data = users_collection.find_one({"user_id": user.id, "is_approved": True})

    if not user_data:
        await update.message.reply_text("You must be approved to use this command.")
        return

    earnings = user_data.get("earnings", 0.0)
    referrals_count = referrals_collection.count_documents({"referrer_id": user.id})
    active_earners_count = referrals_collection.count_documents({"referrer_id": user.id, "is_active_earner": True})
    
    withdraw_link = f"https://t.me/{YOUR_TELEGRAM_HANDLE}"

    await update.message.reply_text(
        f"💰 **Withdrawal Details** 💰\n\n"
        f"Total Earnings: **${earnings:.4f}**\n"
        f"Total Referrals: **{referrals_count}**\n"
        f"Active Earners Today: **{active_earners_count}**\n\n"
        f"Click the link below to contact the admin for withdrawal:\n{withdraw_link}"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    action, user_id_str = query.data.split("_")
    user_id = int(user_id_str)

    if action == "approve":
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"is_approved": True, "earnings": 0.0, "last_earning_date": None}},
            upsert=True
        )
        await context.bot.send_message(chat_id=user_id, text="Congratulations! You have been approved to earn. Use /earn to get your link.")
        await query.edit_message_text(text=f"User {user_id} has been approved.")
    elif action == "cancel":
        users_collection.delete_one({"user_id": user_id})
        await context.bot.send_message(chat_id=user_id, text="Your request was not approved.")
        await query.edit_message_text(text=f"User {user_id}'s request has been cancelled.")

# This function simulates the shortlink completion. You'll need to integrate this
# logic with your actual shortlink service.
async def process_shortlink_completion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # This is where your shortlink service would call back to your bot with a user ID
    # For this example, we assume the user ID is passed in the update or context
    referred_user = update.effective_user
    referral_data = referrals_collection.find_one({"referred_user_id": referred_user.id})

    if referral_data:
        referrer_id = referral_data["referrer_id"]
        referrer_data = users_collection.find_one({"user_id": referrer_id, "is_approved": True})
        
        if referrer_data:
            today = datetime.now().date()
            last_earning_date = referrer_data.get("last_earning_date")
            
            # Check if earnings have already been added today for this referral
            if not last_earning_date or last_earning_date.date() < today:
                earnings_to_add = 0.0018
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
                    text=f"🎉 **Your earnings have been updated!**\n"
                    f"A referred user ({referred_user.full_name}) completed the shortlink process today.\n"
                    f"Your new balance: ${referrer_data.get('earnings', 0) + earnings_to_add:.4f}"
                )
                logging.info(f"Updated earnings for referrer {referrer_id}. New balance: {referrer_data.get('earnings', 0) + earnings_to_add}")
            else:
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text=f"This user has already earned you money today. Your earnings will be updated again tomorrow."
                )

# Example endpoint for shortlink service callback (needs to be configured on Render)
@app.route('/shortlink_completed/<int:user_id>', methods=['GET'])
def shortlink_completed(user_id):
    # This is a mock. You'll need to implement the actual logic
    # and call the `process_shortlink_completion` async function
    # In a real-world scenario, you would handle this more robustly
    return jsonify({"status": "success", "message": "Earnings will be updated."})

# Main function to run the bot
def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("earn", earn_command))
    application.add_handler(CommandHandler("withdraw", withdraw_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # This is a placeholder for your shortlink completion event.
    # You would need to trigger `process_shortlink_completion` from your shortlink service
    # for a specific user ID.
    
    application.run_polling()

if __name__ == "__main__":
    main()
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))

