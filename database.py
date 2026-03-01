# database.py - MongoDB डेटाबेस

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
from datetime import datetime, timedelta
import logging
from config import Config
import random

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        try:
            self.client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=5000)
            self.db = self.client.movie_bot_advanced
            
            # Test connection
            self.client.admin.command('ping')
            logger.info("✅ MongoDB Connected Successfully")
        except Exception as e:
            logger.error(f"❌ MongoDB Connection Failed: {e}")
            raise e
        
        # कलेक्शन
        self.users = self.db.users
        self.referrals = self.db.referrals
        self.withdrawals = self.db.withdrawals
        self.transactions = self.db.transactions
        self.channel_joins = self.db.channel_joins
        self.spins = self.db.spins
        self.missions = self.db.missions
        self.group_activity = self.db.group_activity
        self.monthly_leaderboard = self.db.monthly_leaderboard
        self.reports = self.db.reports
        
        self._create_indexes()
        logger.info("✅ Database Ready")
    
    def _create_indexes(self):
        self.users.create_index("user_id", unique=True)
        self.users.create_index([("balance", DESCENDING)])
        self.referrals.create_index([("referrer", ASCENDING), ("user", ASCENDING)], unique=True)
        self.referrals.create_index("user", unique=True)
        self.group_activity.create_index([("user_id", ASCENDING), ("date", ASCENDING)], unique=True)
    
    # ========== USER FUNCTIONS ==========
    
    def get_user(self, user_id):
        try:
            return self.users.find_one({"user_id": user_id})
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None
    
    def create_user(self, user_id, username, full_name, referrer=None):
        try:
            user = {
                "user_id": user_id,
                "username": username,
                "full_name": full_name,
                "balance": 0.0,
                "total_earned": 0.0,
                "spins": Config.INITIAL_SPINS,
                "tier": 1,
                "total_referrals": 0,
                "active_referrals": 0,
                "monthly_referrals": 0,
                "joined": datetime.now(),
                "last_active": datetime.now(),
                "last_daily": None,
                "daily_streak": 0,
                "last_spin": None,
                "payment_method": None,
                "payment_details": None,
                "welcome_bonus": False,
                "channel_joined": False,
                "is_blocked": False,
                "total_searches": 0,
                "last_search_date": None,
                "search_streak": 0
            }
            
            self.users.insert_one(user)
            
            if referrer and referrer != user_id:
                ref_user = self.get_user(referrer)
                if ref_user and not ref_user.get("is_blocked", False):
                    self.referrals.insert_one({
                        "referrer": referrer,
                        "user": user_id,
                        "joined": datetime.now(),
                        "active": False,
                        "first_search": None,
                        "last_active": None
                    })
            
            return user
            
        except DuplicateKeyError:
            return self.get_user(user_id)
        except Exception as e:
            logger.error(f"Error creating user {user_id}: {e}")
            return None
    
    def update_user(self, user_id, updates):
        try:
            updates["last_active"] = datetime.now()
            return self.users.update_one(
                {"user_id": user_id},
                {"$set": updates}
            )
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            return None
    
    def update_balance(self, user_id, amount, transaction_type=None, details=None):
        try:
            result = self.users.update_one(
                {"user_id": user_id},
                {"$inc": {"balance": amount, "total_earned": max(0, amount)}}
            )
            
            if result.modified_count > 0 and transaction_type:
                self.transactions.insert_one({
                    "user_id": user_id,
                    "amount": amount,
                    "type": transaction_type,
                    "details": details,
                    "timestamp": datetime.now()
                })
            
            user = self.get_user(user_id)
            return user["balance"] if user else 0
        except Exception as e:
            logger.error(f"Error updating balance for {user_id}: {e}")
            return 0
    
    def get_user_stats(self, user_id):
        user = self.get_user(user_id)
        if not user:
            return None
        
        ref_count = self.referrals.count_documents({"referrer": user_id})
        active_refs = self.referrals.count_documents({"referrer": user_id, "active": True})
        pending_refs = ref_count - active_refs
        
        tier = self._get_tier_from_refs(active_refs)
        
        return {
            "balance": round(user.get("balance", 0), 2),
            "total_earned": round(user.get("total_earned", 0), 2),
            "spins": user.get("spins", 0),
            "tier": tier,
            "tier_name": Config.TIERS[tier]["name"],
            "tier_rate": Config.TIERS[tier]["rate"],
            "total_refs": ref_count,
            "active_refs": active_refs,
            "pending_refs": pending_refs,
            "monthly_refs": user.get("monthly_referrals", 0),
            "daily_streak": user.get("daily_streak", 0),
            "channel_joined": user.get("channel_joined", False),
            "total_searches": user.get("total_searches", 0),
            "referral_link": f"https://t.me/LinkProviderRobot?start=ref_{user_id}"
        }
    
    def _get_tier_from_refs(self, refs):
        for tier, config in sorted(Config.TIERS.items(), key=lambda x: x[1]["min_refs"], reverse=True):
            if refs >= config["min_refs"]:
                return tier
        return 1
    
    # ========== DAILY BONUS ==========
    
    def claim_daily(self, user_id):
        user = self.get_user(user_id)
        if not user:
            return None
        
        today = datetime.now().date()
        last = user.get("last_daily")
        
        if last and last.date() == today:
            return None
        
        if last and last.date() == today - timedelta(days=1):
            streak = user.get("daily_streak", 0) + 1
        else:
            streak = 1
        
        bonus = Config.DAILY_BONUS_BASE + (streak * Config.DAILY_BONUS_INCREMENT)
        
        self.users.update_one(
            {"user_id": user_id},
            {
                "$set": {"last_daily": datetime.now(), "daily_streak": streak},
                "$inc": {"balance": bonus, "total_earned": bonus}
            }
        )
        
        # Update mission
        self.update_mission(user_id, "daily_bonus")
        
        return {
            "bonus": round(bonus, 2),
            "streak": streak,
            "balance": round(user["balance"] + bonus, 2)
        }
    
    # ========== SPIN WHEEL ==========
    
    def spin_wheel(self, user_id):
        user = self.get_user(user_id)
        if not user:
            return {"error": "User not found"}
        
        if user["spins"] <= 0:
            return {"error": "No spins left"}
        
        prize_data = random.choices(Config.SPIN_PRIZES, weights=Config.SPIN_WEIGHTS)[0]
        prize = prize_data["value"]
        
        self.users.update_one(
            {"user_id": user_id},
            {
                "$inc": {"spins": -1, "balance": prize, "total_earned": prize},
                "$set": {"last_spin": datetime.now()}
            }
        )
        
        return {
            "prize": prize,
            "prize_name": prize_data["name"],
            "remaining_spins": user["spins"] - 1
        }
    
    # ========== CHANNEL JOIN ==========
    
    def mark_channel_joined(self, user_id, channel):
        if self.channel_joins.find_one({"user_id": user_id, "channel": channel}):
            return False
        
        self.channel_joins.insert_one({
            "user_id": user_id,
            "channel": channel,
            "joined_at": datetime.now()
        })
        
        self.update_balance(user_id, Config.CHANNEL_BONUS, "channel_bonus", f"Channel {channel} join bonus")
        
        self.users.update_one(
            {"user_id": user_id},
            {"$set": {"channel_joined": True}}
        )
        
        return True
    
    # ========== WITHDRAWAL ==========
    
    def create_withdrawal(self, user_id, amount, method, details):
        user = self.get_user(user_id)
        if not user:
            return False, "User not found"
        
        if user["balance"] < amount:
            return False, "Insufficient balance"
        
        if amount < Config.MIN_WITHDRAWAL:
            return False, f"Minimum withdrawal ₹{Config.MIN_WITHDRAWAL}"
        
        withdrawal = {
            "user_id": user_id,
            "amount": amount,
            "method": method,
            "details": details,
            "status": "pending",
            "requested": datetime.now(),
            "processed": None
        }
        
        self.withdrawals.insert_one(withdrawal)
        
        self.users.update_one(
            {"user_id": user_id},
            {"$inc": {"balance": -amount}}
        )
        
        return True, "Withdrawal request submitted"
    
    # ========== MISSIONS ==========
    
    def update_mission(self, user_id, mission_type):
        today = datetime.now().date().isoformat()
        
        mission = self.missions.find_one({
            "user_id": user_id,
            "type": mission_type,
            "date": today
        })
        
        if not mission:
            mission = {
                "user_id": user_id,
                "type": mission_type,
                "date": today,
                "count": 1,
                "completed": False
            }
            self.missions.insert_one(mission)
        else:
            self.missions.update_one(
                {"_id": mission["_id"]},
                {"$inc": {"count": 1}}
            )
            mission["count"] += 1
        
        config = Config.MISSIONS.get(mission_type)
        if config and mission["count"] >= config["target"] and not mission.get("completed"):
            self.missions.update_one(
                {"_id": mission["_id"]},
                {"$set": {"completed": True}}
            )
            
            self.update_balance(user_id, config["reward"], "mission", f"Mission {mission_type} completed")
            self.users.update_one(
                {"user_id": user_id},
                {"$inc": {"spins": config["spins"]}}
            )
            
            return {
                "completed": True,
                "reward": config["reward"],
                "spins": config["spins"]
            }
        
        return {"count": mission["count"], "completed": mission.get("completed", False)}
    
    def get_missions(self, user_id):
        today = datetime.now().date().isoformat()
        missions = {}
        
        for mission_type, config in Config.MISSIONS.items():
            mission = self.missions.find_one({
                "user_id": user_id,
                "type": mission_type,
                "date": today
            })
            
            missions[mission_type] = {
                "count": mission["count"] if mission else 0,
                "completed": mission["completed"] if mission else False,
                "target": config["target"],
                "reward": config["reward"],
                "spins": config["spins"],
                "name": config["name"],
                "icon": config["icon"]
            }
        
        return missions
    
    # ========== LEADERBOARD ==========
    
    def get_current_leaderboard(self, limit=10):
        pipeline = [
            {"$match": {"is_blocked": False, "monthly_referrals": {"$gt": 0}}},
            {"$sort": {"monthly_referrals": -1}},
            {"$limit": limit},
            {"$project": {
                "user_id": 1,
                "full_name": 1,
                "monthly_referrals": 1,
                "balance": 1,
                "active_referrals": 1
            }}
        ]
        return list(self.users.aggregate(pipeline))
    
    # ========== ADMIN FUNCTIONS ==========
    
    def get_stats(self):
        total_users = self.users.count_documents({})
        active_today = self.group_activity.count_documents({
            "date": datetime.now().date().isoformat()
        })
        
        return {
            "total_users": total_users,
            "active_users": self.users.count_documents({"is_blocked": False}),
            "blocked_users": self.users.count_documents({"is_blocked": True}),
            "active_today": active_today,
            "pending_withdrawals": self.withdrawals.count_documents({"status": "pending"}),
            "total_earned": sum(u.get("total_earned", 0) for u in self.users.find({}, {"total_earned": 1})),
            "total_paid": sum(w.get("amount", 0) for w in self.withdrawals.find({"status": "completed"})),
            "today_users": self.users.count_documents({"joined": {"$gte": datetime.now().replace(hour=0, minute=0, second=0)}})
        }
    
    def get_all_users(self, filter_blocked=False):
        query = {"is_blocked": False} if filter_blocked else {}
        return list(self.users.find(query))
    
    def clear_user_earnings(self, user_id):
        self.users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "balance": 0,
                    "total_earned": 0,
                    "spins": Config.INITIAL_SPINS,
                    "total_referrals": 0,
                    "active_referrals": 0,
                    "monthly_referrals": 0,
                    "daily_streak": 0,
                    "total_searches": 0,
                    "search_streak": 0,
                    "last_daily": None,
                    "last_spin": None
                }
            }
        )
        return True
    
    def clear_all_user_data(self, user_id):
        self.users.delete_one({"user_id": user_id})
        self.referrals.delete_many({"referrer": user_id})
        self.referrals.delete_many({"user": user_id})
        self.transactions.delete_many({"user_id": user_id})
        self.withdrawals.delete_many({"user_id": user_id})
        self.spins.delete_many({"user_id": user_id})
        self.missions.delete_many({"user_id": user_id})
        self.channel_joins.delete_many({"user_id": user_id})
        self.group_activity.delete_many({"user_id": user_id})
        return True
    
    def save_report(self, user_id, issue):
        report = {
            "user_id": user_id,
            "issue": issue,
            "timestamp": datetime.now(),
            "status": "pending"
        }
        self.reports.insert_one(report)
        return report


# Global database instance
db = Database()# main.py - मुख्य बॉट + Flask App

import logging
import asyncio
import os
import traceback
from flask import Flask, render_template, request, jsonify
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, CallbackQueryHandler
)
from config import Config
from database import db
from handlers import BotHandlers
from admin import AdminHandlers
import nest_asyncio

# Fix for event loop
nest_asyncio.apply()

# ====== LOGGING ======
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, Config.LOG_LEVEL)
)
logger = logging.getLogger(__name__)

# ====== FLASK APP ======
flask_app = Flask(__name__)
bot_app = None

# ====== FLASK ROUTES ======
@flask_app.route('/')
def index():
    """Mini App Home Page"""
    user_id = request.args.get('user', '0')
    
    try:
        user_id = int(user_id)
    except:
        user_id = 0
    
    return render_template('index.html', 
                         user_id=user_id,
                         channel=Config.CHANNEL_USERNAME,
                         channel_link=Config.CHANNEL_LINK,
                         channel_bonus=Config.CHANNEL_BONUS,
                         min_withdrawal=Config.MIN_WITHDRAWAL)

@flask_app.route('/api/user/<int:user_id>')
def api_user(user_id):
    stats = db.get_user_stats(user_id)
    if not stats:
        return jsonify({"error": "User not found"})
    return jsonify(stats)

@flask_app.route('/api/leaderboard')
def api_leaderboard():
    lb = db.get_current_leaderboard()
    result = []
    for idx, user in enumerate(lb, 1):
        result.append({
            "rank": idx,
            "name": user.get("full_name", "User")[:20],
            "refs": user.get("monthly_referrals", 0),
            "balance": user.get("balance", 0)
        })
    return jsonify(result)

@flask_app.route(f'/{Config.BOT_TOKEN}', methods=['POST'])
def webhook():
    """Telegram Webhook Handler"""
    global bot_app
    
    if not bot_app:
        logger.error("❌ Bot not initialized")
        return 'Bot not ready', 503
    
    try:
        update_data = request.get_json(force=True)
        logger.info(f"📩 Update received: {update_data.get('update_id', 'unknown')}")
        
        update = Update.de_json(update_data, bot_app.bot)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(bot_app.process_update(update))
        finally:
            loop.close()
        
        logger.info("✅ Update processed successfully")
        return 'OK', 200
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        traceback.print_exc()
        return 'Error', 500

# ====== BOT INITIALIZATION ======
async def initialize_bot():
    """Initialize bot application"""
    global bot_app
    
    bot_app = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Register handlers
    bot_app.add_handler(CommandHandler("start", BotHandlers.start))
    bot_app.add_handler(CommandHandler("admin", AdminHandlers.admin_panel))
    bot_app.add_handler(CommandHandler("check", BotHandlers.check_command))
    bot_app.add_handler(CommandHandler("stats", AdminHandlers.handle_admin_text))
    bot_app.add_handler(CommandHandler("add", AdminHandlers.handle_admin_text))
    bot_app.add_handler(CommandHandler("remove", AdminHandlers.handle_admin_text))
    bot_app.add_handler(CommandHandler("clear", AdminHandlers.handle_admin_text))
    
    # Message handlers
    bot_app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, 
        BotHandlers.group_message
    ))
    bot_app.add_handler(MessageHandler(
        filters.StatusUpdate.WEB_APP_DATA, 
        BotHandlers.web_app_data
    ))
    
    # Callback handlers
    bot_app.add_handler(CallbackQueryHandler(AdminHandlers.admin_callback, pattern="^admin_"))
    
    # Broadcast handler
    bot_app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        AdminHandlers.handle_broadcast_message
    ))
    
    # Clear reply handler
    bot_app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        AdminHandlers.handle_clear_reply
    ))
    
    # Error handler
    bot_app.add_error_handler(BotHandlers.error_handler)
    
    # Initialize bot
    await bot_app.initialize()
    
    # Set webhook
    webhook_url = f"{Config.WEB_APP_URL}/{Config.BOT_TOKEN}"
    await bot_app.bot.set_webhook(
        url=webhook_url,
        allowed_updates=["message", "callback_query", "chat_member"]
    )
    
    logger.info(f"✅ Bot initialized! Webhook: {webhook_url}")
    return bot_app

# ====== MAIN ======
def main():
    """Main entry point"""
    logger.info("🚀 Starting application...")
    
    # Initialize bot
    asyncio.run(initialize_bot())
    logger.info("✅ Bot ready!")
    
    # Start Flask
    logger.info(f"🌐 Flask app starting on port {Config.PORT}")
    flask_app.run(host='0.0.0.0', port=Config.PORT, debug=False)

if __name__ == "__main__":
    main()
