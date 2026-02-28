import logging
import json
import asyncio
import threading
import os
from flask import Flask, render_template, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from datetime import datetime
import pymongo

from config import *
from database import *

logging.basicConfig(level=logging.INFO)

# ========== FLASK APP ==========
flask_app = Flask(__name__)
bot_app = None  # बाद में initialize करेंगे

# Flask Routes
@flask_app.route('/')
def index():
    user_id = request.args.get('user', '0')
    try:
        user_id = int(user_id)
    except:
        user_id = 0
    return render_template('index.html', user_id=user_id)

@flask_app.route('/api/user/<int:user_id>')
def api_user(user_id):
    stats = get_user_stats(user_id)
    if not stats:
        return jsonify({"error": "User not found"})
    return jsonify(stats)

@flask_app.route('/api/leaderboard')
def api_leaderboard():
    lb = get_leaderboard()
    result = []
    for u in lb:
        result.append({
            "name": u.get("full_name", "User")[:15],
            "refs": u.get("active_referrals", 0),
            "balance": u.get("balance", 0)
        })
    return jsonify(result)

# यह ENDPOINT Telegram webhook के लिए
@flask_app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    """Telegram का webhook यहाँ आएगा"""
    if not bot_app:
        return 'Bot not ready', 503
    
    update = Update.de_json(request.get_json(force=True), bot_app.bot)
    
    # IMPORTANT: asyncio में run करें
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(bot_app.process_update(update))
    
    return 'OK', 200

# ========== TELEGRAM BOT HANDLERS ==========
async def start(update: Update, context):
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
        create_user(user.id, user.username or "", user.first_name, referrer)
        
        # Welcome bonus
        if not db_user or not db_user.get("welcome_bonus"):
            update_balance(user.id, WELCOME_BONUS)
            users.update_one({"user_id": user.id}, {"$set": {"welcome_bonus": True}})
    
    # Mini App Button
    web_app_url = os.getenv("WEB_APP_URL", "https://your-app.onrender.com")
    keyboard = [[
        InlineKeyboardButton(
            "🎬 OPEN MINI APP", 
            web_app={"url": f"{web_app_url}/?user={user.id}"}
        )
    ]]
    
    user_data = get_user(user.id)
    balance = user_data.get("balance", 0) if user_data else 0
    spins = user_data.get("spins", 3) if user_data else 3
    
    await update.message.reply_text(
        f"👋 Welcome {user.first_name}!\n\n"
        f"💰 Balance: ₹{balance:.2f}\n"
        f"🎰 Spins: {spins}\n\n"
        f"Click below to open the Earning Mini App:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def group_message(update: Update, context):
    if not update.message or not update.message.text:
        return
    
    user = update.effective_user
    if not user:
        return
    
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

async def web_app_data(update: Update, context):
    """Mini App से डेटा receive करें"""
    if not update.effective_message or not update.effective_message.web_app_data:
        return
    
    data = update.effective_message.web_app_data.data
    
    try:
        payload = json.loads(data)
        action = payload.get("action")
        user_id = payload.get("user_id")
        
        if action == "get_data":
            stats = get_user_stats(user_id)
            await update.effective_message.reply_text(json.dumps(stats))
        
        elif action == "spin":
            user = get_user(user_id)
            if not user or user["spins"] <= 0:
                await update.effective_message.reply_text(json.dumps({"error": "No spins"}))
                return
            
            import random
            prize = random.choices(SPIN_PRIZES, weights=SPIN_WEIGHTS)[0]
            
            users.update_one(
                {"user_id": user_id},
                {"$inc": {"spins": -1, "balance": prize}}
            )
            
            updated_user = get_user(user_id)
            await update.effective_message.reply_text(
                json.dumps({"prize": prize, "balance": updated_user["balance"]})
            )
        
        elif action == "daily":
            result = claim_daily(user_id)
            if result:
                await update.effective_message.reply_text(json.dumps(result))
            else:
                await update.effective_message.reply_text(json.dumps({"error": "Already claimed"}))
        
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

# ========== BOT SETUP FUNCTION ==========
def setup_bot():
    """Telegram Bot initialize करें"""
    global bot_app
    
    bot_app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )
    
    # Add handlers
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT, group_message))
    bot_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data))
    
    return bot_app

# ========== MAIN FUNCTION ==========
def main():
    """मेन फंक्शन - सब कुछ यहीं से start होगा"""
    global bot_app
    
    print("🚀 Starting application...")
    
    # 1. Bot setup
    bot_app = setup_bot()
    
    # 2. Webhook setup
    webhook_url = f"{WEB_APP_URL}/{BOT_TOKEN}"
    
    # Async function को sync में run करें
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Webhook set करें
    loop.run_until_complete(
        bot_app.bot.set_webhook(url=webhook_url)
    )
    
    print(f"✅ Webhook set to: {webhook_url}")
    
    # 3. Flask app run करें (यह blocking call है)
    print(f"🌐 Flask app starting on port {PORT}")
    flask_app.run(host='0.0.0.0', port=PORT, debug=False)

if __name__ == "__main__":
    main()
