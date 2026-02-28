import logging
import json
import asyncio
import os
import random
import traceback
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import pymongo

# ====== LOAD ENVIRONMENT VARIABLES ======
from dotenv import load_dotenv
load_dotenv()

# ====== CONFIG FROM ENVIRONMENT ======
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
MONGO_URI = os.getenv("MONGO_URI")
PORT = int(os.getenv("PORT", 10000))
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://promotion-user.onrender.com")

# Movie Groups
MOVIE_GROUP_LINK = os.getenv("MOVIE_GROUP_LINK", "https://t.me/asfilter_group")
NEW_MOVIE_GROUP_LINK = os.getenv("NEW_MOVIE_GROUP_LINK", "https://t.me/asfilter_bot")
ALL_GROUPS_LINK = os.getenv("ALL_GROUPS_LINK", "https://t.me/addlist/6urdhhdLRqhiZmQ1")

# Bonus & Rates
WELCOME_BONUS = float(os.getenv("WELCOME_BONUS", "5.0"))
DAILY_BONUS_BASE = float(os.getenv("DAILY_BONUS_BASE", "0.05"))
MIN_WITHDRAWAL = float(os.getenv("MIN_WITHDRAWAL", "50.0"))

# Spin Wheel
SPIN_PRIZES = [0.00, 0.05, 0.10, 0.20, 0.50, 1.00]
SPIN_WEIGHTS = [50, 20, 15, 10, 4, 1]

# Tiers
TIERS = {
    1: {"rate": 0.10, "name": "🥉 Beginner"},
    2: {"rate": 0.12, "name": "🥈 Pro"},
    3: {"rate": 0.15, "name": "🥇 Expert"},
    4: {"rate": 0.18, "name": "👑 Master"},
    5: {"rate": 0.20, "name": "💎 Legend"}
}

# ====== LOGGING SETUP ======
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Check if all required variables are set
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not set in environment variables!")
    exit(1)

if not MONGO_URI:
    logger.error("❌ MONGO_URI not set in environment variables!")
    exit(1)

if ADMIN_ID == 0:
    logger.warning("⚠️ ADMIN_ID not set! Admin features will not work.")

# ====== DATABASE SETUP ======
try:
    client = pymongo.MongoClient(MONGO_URI)
    db = client.movie_bot
    users = db.users
    referrals = db.referrals
    withdrawals = db.withdrawals
    logger.info("✅ MongoDB connected successfully")
except Exception as e:
    logger.error(f"❌ MongoDB connection error: {e}")
    exit(1)

# ====== DATABASE FUNCTIONS ======
def get_user(user_id):
    return users.find_one({"user_id": user_id})

def create_user(user_id, username, full_name, referrer=None):
    user = {
        "user_id": user_id,
        "username": username,
        "full_name": full_name,
        "balance": 0.0,
        "spins": 3,
        "tier": 1,
        "total_referrals": 0,
        "active_referrals": 0,
        "monthly_referrals": 0,
        "joined": datetime.now(),
        "last_daily": None,
        "daily_streak": 0,
        "payment_method": None,
        "payment_details": None,
        "welcome_bonus": False
    }
    users.insert_one(user)
    
    if referrer and referrer != user_id:
        referrals.insert_one({
            "referrer": referrer,
            "user": user_id,
            "joined": datetime.now(),
            "active": False,
            "first_search": None,
            "last_paid": None
        })
    return user

def update_balance(user_id, amount):
    users.update_one(
        {"user_id": user_id},
        {"$inc": {"balance": amount}}
    )
    user = get_user(user_id)
    return user["balance"] if user else 0

def activate_referral(user_id):
    ref = referrals.find_one({"user": user_id})
    if ref and not ref["active"]:
        referrals.update_one(
            {"user": user_id},
            {"$set": {"active": True, "first_search": datetime.now()}}
        )
        users.update_one(
            {"user_id": ref["referrer"]},
            {"$inc": {"active_referrals": 1, "monthly_referrals": 1, "spins": 1}}
        )
        return ref["referrer"]
    return None

def pay_referrer(user_id):
    ref = referrals.find_one({"user": user_id, "active": True})
    if not ref:
        return None
    
    today = datetime.now().date()
    if ref.get("last_paid") and ref["last_paid"].date() == today:
        return None
    
    referrer = users.find_one({"user_id": ref["referrer"]})
    if not referrer:
        return None
    
    tier = referrer.get("tier", 1)
    rate = TIERS[tier]["rate"]
    
    users.update_one(
        {"user_id": ref["referrer"]},
        {"$inc": {"balance": rate}}
    )
    
    referrals.update_one(
        {"user": user_id},
        {"$set": {"last_paid": datetime.now()}}
    )
    
    return rate

def claim_daily(user_id):
    user = users.find_one({"user_id": user_id})
    if not user:
        return None
    
    today = datetime.now().date()
    last = user.get("last_daily")
    
    if last and last.date() == today:
        return None
    
    streak = 1
    if last and last.date() == today - timedelta(days=1):
        streak = user.get("daily_streak", 0) + 1
    else:
        streak = 1
    
    bonus = DAILY_BONUS_BASE + (streak * 0.02)
    
    users.update_one(
        {"user_id": user_id},
        {
            "$set": {"last_daily": datetime.now(), "daily_streak": streak},
            "$inc": {"balance": bonus}
        }
    )
    
    updated_user = get_user(user_id)
    return {
        "bonus": bonus, 
        "streak": streak, 
        "balance": updated_user["balance"] if updated_user else user["balance"] + bonus
    }

def get_user_stats(user_id):
    user = users.find_one({"user_id": user_id})
    if not user:
        return None
    
    ref_count = referrals.count_documents({"referrer": user_id})
    active_refs = referrals.count_documents({"referrer": user_id, "active": True})
    
    return {
        "balance": user.get("balance", 0),
        "spins": user.get("spins", 0),
        "tier": user.get("tier", 1),
        "total_refs": ref_count,
        "active_refs": active_refs,
        "monthly_refs": user.get("monthly_referrals", 0)
    }

def get_leaderboard():
    return list(users.find(
        {"active_referrals": {"$gt": 0}}
    ).sort("active_referrals", -1).limit(10))

def save_payment_details(user_id, method, details):
    users.update_one(
        {"user_id": user_id},
        {"$set": {
            "payment_method": method,
            "payment_details": details
        }}
    )

def create_withdrawal(user_id, amount, method, details):
    user = users.find_one({"user_id": user_id})
    if not user or user["balance"] < amount or amount < MIN_WITHDRAWAL:
        return False
    
    withdrawal = {
        "user_id": user_id,
        "amount": amount,
        "method": method,
        "details": details,
        "status": "pending",
        "requested": datetime.now()
    }
    withdrawals.insert_one(withdrawal)
    
    users.update_one(
        {"user_id": user_id},
        {"$set": {"balance": 0}}
    )
    return True

def check_missions(user_id, mission_type):
    # Mission function - can be expanded later
    pass

# ====== FLASK APP ======
flask_app = Flask(__name__)
bot_app = None

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

# ====== CORRECTED WEBHOOK HANDLER ======
@flask_app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    """Telegram webhook handler - FIXED"""
    global bot_app
    
    if not bot_app:
        logger.error("❌ Bot app not initialized")
        return 'Bot not ready', 503
    
    try:
        # Get data from Telegram
        update_data = request.get_json(force=True)
        logger.info(f"📩 Received update: {update_data.get('update_id', 'unknown')}")
        
        # Create Update object
        update = Update.de_json(update_data, bot_app.bot)
        
        # ✅ CRITICAL FIX: Create new event loop and run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # This properly awaits the coroutine
        loop.run_until_complete(bot_app.process_update(update))
        
        # Clean up
        loop.close()
        
        logger.info("✅ Update processed successfully")
        return 'OK', 200
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        traceback.print_exc()
        return 'Error', 500

# ====== TELEGRAM BOT HANDLERS ======
async def start(update: Update, context):
    """Start command handler"""
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
        
        # Send welcome message
        await update.message.reply_text(
            f"🎁 Welcome! You received ₹{WELCOME_BONUS} welcome bonus!"
        )
    
    # Get updated user data
    user_data = get_user(user.id)
    balance = user_data.get("balance", 0) if user_data else 0
    spins = user_data.get("spins", 3) if user_data else 3
    
    # Mini App Button
    keyboard = [[
        InlineKeyboardButton(
            "🎬 OPEN MINI APP", 
            web_app={"url": f"{WEB_APP_URL}/?user={user.id}"}
        )
    ]]
    
    await update.message.reply_text(
        f"👋 Welcome {user.first_name}!\n\n"
        f"💰 Balance: ₹{balance:.2f}\n"
        f"🎰 Spins: {spins}\n\n"
        f"Click below to open the Earning Mini App:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    logger.info(f"✅ User {user.id} started the bot")

async def group_message(update: Update, context):
    """Group message handler - for movie searches"""
    if not update.message or not update.message.text:
        return
    
    user = update.effective_user
    if not user:
        return
    
    # Log the message
    logger.info(f"📝 Group message from {user.id}: {update.message.text[:30]}...")
    
    # Activate referral on first search
    referrer = activate_referral(user.id)
    if referrer:
        try:
            await context.bot.send_message(
                referrer,
                f"🎉 Your referral {user.first_name} just searched their first movie!\n"
                f"✅ Referral activated! +1 Spin added!"
            )
            logger.info(f"✅ Referral activated: {referrer} -> {user.id}")
        except Exception as e:
            logger.error(f"Failed to notify referrer: {e}")
    
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
                logger.info(f"💰 Paid ₹{amount} to referrer {ref_doc['referrer']}")
            except Exception as e:
                logger.error(f"Failed to notify referrer about payment: {e}")
    
    # Update user missions
    check_missions(user.id, "search")

async def web_app_data(update: Update, context):
    """Handle data from Mini App"""
    if not update.effective_message or not update.effective_message.web_app_data:
        return
    
    data = update.effective_message.web_app_data.data
    logger.info(f"📱 WebApp data received: {data[:50]}...")
    
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
            if not user or user["spins"] <= 0:
                await update.effective_message.reply_text(json.dumps({"error": "No spins"}))
                return
            
            prize = random.choices(SPIN_PRIZES, weights=SPIN_WEIGHTS)[0]
            
            users.update_one(
                {"user_id": user_id},
                {"$inc": {"spins": -1, "balance": prize}}
            )
            
            updated_user = get_user(user_id)
            await update.effective_message.reply_text(
                json.dumps({"prize": prize, "balance": updated_user["balance"]})
            )
            logger.info(f"🎡 User {user_id} spun and won ₹{prize}")
        
        elif action == "daily":
            result = claim_daily(user_id)
            if result:
                await update.effective_message.reply_text(json.dumps(result))
                logger.info(f"📅 User {user_id} claimed daily bonus: ₹{result['bonus']}")
            else:
                await update.effective_message.reply_text(json.dumps({"error": "Already claimed"}))
        
        elif action == "save_payment":
            method = payload.get("method")
            details = payload.get("details")
            save_payment_details(user_id, method, details)
            await update.effective_message.reply_text(json.dumps({"success": True}))
            logger.info(f"💳 User {user_id} saved payment details")
        
        elif action == "withdraw":
            amount = payload.get("amount")
            method = payload.get("method")
            details = payload.get("details")
            
            success = create_withdrawal(user_id, amount, method, details)
            await update.effective_message.reply_text(json.dumps({"success": success}))
            
            if success:
                logger.info(f"💰 Withdrawal request from {user_id}: ₹{amount}")
                
                # Notify admin
                if success and ADMIN_ID:
                    try:
                        await context.bot.send_message(
                            ADMIN_ID,
                            f"💰 New Withdrawal Request\n"
                            f"User: {user_id}\n"
                            f"Amount: ₹{amount}\n"
                            f"Method: {method}\n"
                            f"Details: {details}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify admin: {e}")
        
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
        logger.error(f"❌ WebApp data error: {e}")
        traceback.print_exc()

async def admin(update: Update, context):
    """Admin commands"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /add <user_id> <amount> or /clear <user_id>")
        return
    
    cmd = context.args[0]
    try:
        target = int(context.args[1])
        amount = float(context.args[2]) if len(context.args) > 2 else 0
    except:
        await update.message.reply_text("Invalid arguments")
        return
    
    if cmd == "add":
        new_balance = update_balance(target, amount)
        await update.message.reply_text(f"✅ Added ₹{amount}. New balance: ₹{new_balance}")
        try:
            await context.bot.send_message(target, f"🎁 You received ₹{amount} bonus!")
        except:
            pass
        logger.info(f"👑 Admin added ₹{amount} to user {target}")
    
    elif cmd == "clear":
        users.update_one({"user_id": target}, {"$set": {"balance": 0}})
        await update.message.reply_text(f"✅ Balance cleared for {target}")
        logger.info(f"👑 Admin cleared balance for user {target}")

async def error_handler(update: Update, context):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")

# ====== MAIN FUNCTION ======
def main():
    global bot_app
    
    logger.info("🚀 Starting application...")
    
    # Create bot application
    bot_app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )
    
    # Add handlers
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT, group_message))
    bot_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data))
    if ADMIN_ID != 0:
        bot_app.add_handler(CommandHandler("add", admin, filters.User(ADMIN_ID)))
        bot_app.add_handler(CommandHandler("clear", admin, filters.User(ADMIN_ID)))
    bot_app.add_error_handler(error_handler)
    
    # Set webhook
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        webhook_url = f"{WEB_APP_URL}/{BOT_TOKEN}"
        loop.run_until_complete(
            bot_app.bot.set_webhook(url=webhook_url)
        )
        loop.close()
        
        logger.info(f"✅ Webhook set to: {webhook_url}")
    except Exception as e:
        logger.error(f"❌ Failed to set webhook: {e}")
    
    # Start Flask app
    logger.info(f"🌐 Flask app starting on port {PORT}")
    flask_app.run(host='0.0.0.0', port=PORT, debug=False)

if __name__ == "__main__":
    main()
