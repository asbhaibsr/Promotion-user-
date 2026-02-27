import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from datetime import datetime

from config import *
from database import *

logging.basicConfig(level=logging.INFO)

# === START COMMAND ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Referral check
    referrer = None
    if context.args and context.args[0].startswith("ref_"):
        try:
            referrer = int(context.args[0].replace("ref_", ""))
        except:
            pass
    
    # Get or create user
    db_user = get_user(user.id)
    if not db_user:
        create_user(user.id, user.username, user.first_name, referrer)
        
        # Welcome bonus
        if not db_user or not db_user.get("welcome_bonus"):
            update_balance(user.id, WELCOME_BONUS)
            users.update_one({"user_id": user.id}, {"$set": {"welcome_bonus": True}})
    
    # Mini App Button
    keyboard = [[
        InlineKeyboardButton("🎬 OPEN MINI APP", web_app={"url": f"{WEB_APP_URL}?user={user.id}"})
    ]]
    
    await update.message.reply_text(
        f"👋 Welcome {user.first_name}!\n\n"
        f"💰 Balance: ₹{get_user(user.id)['balance']:.2f}\n"
        f"🎰 Spins: {get_user(user.id)['spins']}\n\n"
        f"Click below to open the Earning Mini App:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# === GROUP MESSAGE HANDLER ===
async def group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    user = update.effective_user
    
    # Activate referral on first search
    referrer = activate_referral(user.id)
    if referrer:
        try:
            await context.bot.send_message(
                referrer,
                f"🎉 Your referral {user.first_name} just searched their first movie!\n"
                f"✅ Referral activated! +1 Spin added!"
            )
        except:
            pass
    
    # Pay referrer (daily)
    amount = pay_referrer(user.id)
    if amount:
        ref_doc = referrals.find_one({"user": user.id})
        if ref_doc:
            try:
                await context.bot.send_message(
                    ref_doc["referrer"],
                    f"💰 Daily Earning!\n"
                    f"From: {user.first_name}\n"
                    f"Amount: ₹{amount:.2f}"
                )
            except:
                pass
    
    # Update user missions
    check_missions(user.id, "search")

# === MINI APP DATA HANDLER ===
async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.effective_message.web_app_data.data
    import json
    
    try:
        payload = json.loads(data)
        action = payload.get("action")
        user_id = payload.get("user_id")
        
        if action == "get_data":
            user = get_user(user_id)
            stats = get_user_stats(user_id)
            
            await update.effective_message.reply_text(
                json.dumps({
                    "balance": stats["balance"],
                    "spins": stats["spins"],
                    "tier": stats["tier"],
                    "total_refs": stats["total_refs"],
                    "active_refs": stats["active_refs"],
                    "monthly_refs": stats["monthly_refs"],
                    "movie_group": MOVIE_GROUP_LINK,
                    "new_group": NEW_MOVIE_GROUP_LINK,
                    "all_groups": ALL_GROUPS_LINK
                })
            )
        
        elif action == "spin":
            user = get_user(user_id)
            if user["spins"] <= 0:
                await update.effective_message.reply_text(json.dumps({"error": "No spins"}))
                return
            
            import random
            prize = random.choices(SPIN_PRIZES, weights=SPIN_WEIGHTS)[0]
            
            users.update_one(
                {"user_id": user_id},
                {"$inc": {"spins": -1, "balance": prize}}
            )
            
            await update.effective_message.reply_text(
                json.dumps({"prize": prize, "balance": user["balance"] + prize})
            )
        
        elif action == "daily":
            result = claim_daily(user_id)
            if result:
                await update.effective_message.reply_text(json.dumps(result))
            else:
                await update.effective_message.reply_text(json.dumps({"error": "Already claimed"}))
        
        elif action == "withdraw":
            amount = payload.get("amount")
            method = payload.get("method")
            details = payload.get("details")
            
            success = create_withdrawal(user_id, amount, method, details)
            await update.effective_message.reply_text(json.dumps({"success": success}))
            
            # Notify admin
            if success:
                await context.bot.send_message(
                    ADMIN_ID,
                    f"💰 New Withdrawal Request\n"
                    f"User: {user_id}\n"
                    f"Amount: ₹{amount}\n"
                    f"Method: {method}\n"
                    f"Details: {details}"
                )
        
        elif action == "leaderboard":
            lb = get_leaderboard()
            result = []
            for u in lb:
                result.append({
                    "name": u.get("full_name", "User"),
                    "refs": u.get("active_referrals", 0)
                })
            await update.effective_message.reply_text(json.dumps(result))
            
    except Exception as e:
        logging.error(f"WebApp Error: {e}")

# === ADMIN COMMANDS ===
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    text = update.message.text.split()
    if len(text) < 3:
        await update.message.reply_text("Usage: /add user_id amount")
        return
    
    cmd = text[0]
    target = int(text[1])
    amount = float(text[2])
    
    if cmd == "/add":
        new_balance = update_balance(target, amount)
        await update.message.reply_text(f"✅ Added ₹{amount}. New balance: ₹{new_balance}")
        try:
            await context.bot.send_message(target, f"🎁 You received ₹{amount} bonus!")
        except:
            pass
    
    elif cmd == "/clear":
        users.update_one({"user_id": target}, {"$set": {"balance": 0}})
        await update.message.reply_text(f"✅ Balance cleared for {target}")

# === MAIN ===
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT, group_message))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data))
    app.add_handler(CommandHandler("add", admin, filters.User(ADMIN_ID)))
    app.add_handler(CommandHandler("clear", admin, filters.User(ADMIN_ID)))
    
    print("🤖 Bot is running...")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=f"{WEB_APP_URL}/{BOT_TOKEN}"
    )

if __name__ == "__main__":
    main()
