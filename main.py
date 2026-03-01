# main.py - Main Application Entry Point

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
    format=Config.LOG_FORMAT,
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
                         min_withdrawal=Config.MIN_WITHDRAWAL,
                         bot_username=Config.BOT_USERNAME)

@flask_app.route('/api/user/<int:user_id>')
def api_user(user_id):
    """Get user data API"""
    stats = db.get_user_stats(user_id)
    if not stats:
        return jsonify({"error": "User not found"})
    return jsonify(stats)

@flask_app.route('/api/leaderboard')
def api_leaderboard():
    """Get leaderboard API"""
    lb = db.get_current_leaderboard()
    result = []
    for idx, user in enumerate(lb, 1):
        result.append({
            "rank": idx,
            "name": user.get("full_name", "User")[:20],
            "refs": user.get("monthly_referrals", 0),
            "balance": user.get("balance", 0),
            "tier": user.get("tier", 1)
        })
    return jsonify(result)

@flask_app.route('/api/top_earners')
def api_top_earners():
    """Get top earners API"""
    top = db.get_balance_leaderboard()
    result = []
    for idx, user in enumerate(top, 1):
        result.append({
            "rank": idx,
            "name": user.get("full_name", "User")[:20],
            "balance": user.get("balance", 0)
        })
    return jsonify(result)

@flask_app.route('/api/stats')
def api_stats():
    """Get global stats API"""
    stats = db.get_stats()
    return jsonify(stats)

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
        
        # Process update in new event loop
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
    
    # ===== COMMAND HANDLERS =====
    bot_app.add_handler(CommandHandler("start", BotHandlers.start))
    bot_app.add_handler(CommandHandler("check", BotHandlers.check_command))
    bot_app.add_handler(CommandHandler("admin", AdminHandlers.admin_panel))
    bot_app.add_handler(CommandHandler("stats", AdminHandlers.handle_admin_text))
    bot_app.add_handler(CommandHandler("add", AdminHandlers.handle_admin_text))
    bot_app.add_handler(CommandHandler("remove", AdminHandlers.handle_admin_text))
    bot_app.add_handler(CommandHandler("clear", AdminHandlers.handle_admin_text))
    
    # ===== MESSAGE HANDLERS =====
    # Group messages for tracking
    bot_app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, 
        BotHandlers.group_message
    ))
    
    # WebApp data handler
    bot_app.add_handler(MessageHandler(
        filters.StatusUpdate.WEB_APP_DATA, 
        BotHandlers.web_app_data
    ))
    
    # ===== CALLBACK HANDLERS =====
    bot_app.add_handler(CallbackQueryHandler(AdminHandlers.admin_callback, pattern="^admin_"))
    bot_app.add_handler(CallbackQueryHandler(BotHandlers.button_callback))
    
    # ===== BROADCAST HANDLER =====
    bot_app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        AdminHandlers.handle_broadcast_message
    ))
    
    # ===== CLEAR REPLY HANDLER =====
    bot_app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        AdminHandlers.handle_clear_reply
    ))
    
    # ===== ERROR HANDLER =====
    bot_app.add_error_handler(BotHandlers.error_handler)
    
    # Initialize bot
    await bot_app.initialize()
    
    # Set webhook
    webhook_url = f"{Config.WEB_APP_URL}/{Config.BOT_TOKEN}"
    await bot_app.bot.set_webhook(
        url=webhook_url,
        allowed_updates=["message", "callback_query", "chat_member", "web_app_data"],
        drop_pending_updates=True
    )
    
    logger.info(f"✅ Bot initialized! Webhook: {webhook_url}")
    
    # Get bot info
    bot_info = await bot_app.bot.get_me()
    logger.info(f"🤖 Bot: @{bot_info.username}")
    
    return bot_app

# ====== MAIN ======

def main():
    """Main entry point"""
    logger.info("🚀 Starting FILMYFUND application...")
    
    # Initialize bot
    asyncio.run(initialize_bot())
    logger.info("✅ Bot ready!")
    
    # Start Flask
    logger.info(f"🌐 Flask app starting on port {Config.PORT}")
    flask_app.run(host='0.0.0.0', port=Config.PORT, debug=False, threaded=True)

if __name__ == "__main__":
    main()
