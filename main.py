# main.py - ULTIMATE FIXED VERSION with Thread Pool Executor

import logging
import asyncio
import os
import sys
import traceback
import time
import concurrent.futures
from flask import Flask, render_template, request, jsonify
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, CallbackQueryHandler, ContextTypes
)
from config import Config
from database import db
from handlers import BotHandlers
from admin import AdminHandlers
import nest_asyncio

# CRITICAL FIX: Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# ====== LOGGING ======
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, Config.LOG_LEVEL),
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ====== FLASK APP ======
flask_app = Flask(__name__)
bot_app = None
bot_initialized = False

# Create a thread pool executor for async operations
executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)

# ====== FLASK ROUTES ======
@flask_app.route('/')
def index():
    """Mini App Home Page"""
    try:
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
                             movie_group=Config.MOVIE_GROUP_LINK,
                             new_group=Config.NEW_MOVIE_GROUP_LINK,
                             all_groups=Config.ALL_GROUPS_LINK,
                             min_withdrawal=Config.MIN_WITHDRAWAL)
    except Exception as e:
        logger.error(f"Index route error: {e}")
        return "Error loading page", 500

@flask_app.route('/api/user/<int:user_id>')
def api_user(user_id):
    try:
        stats = db.get_user_stats(user_id)
        if not stats:
            return jsonify({"error": "User not found"})
        return jsonify(stats)
    except Exception as e:
        logger.error(f"API user error: {e}")
        return jsonify({"error": str(e)}), 500

@flask_app.route('/api/leaderboard')
def api_leaderboard():
    try:
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
    except Exception as e:
        logger.error(f"API leaderboard error: {e}")
        return jsonify([])

@flask_app.route(f'/{Config.BOT_TOKEN}', methods=['POST'])
def webhook():
    """Telegram Webhook Handler - ULTIMATE FIX"""
    global bot_app, bot_initialized
    
    if not bot_initialized or not bot_app:
        logger.error("❌ Bot not initialized")
        return jsonify({"error": "Bot not ready"}), 503
    
    try:
        update_data = request.get_json(force=True)
        logger.info(f"📩 Update received: {update_data.get('update_id', 'unknown')}")
        
        update = Update.de_json(update_data, bot_app.bot)
        
        # CRITICAL FIX: Use executor to run async function in separate thread
        future = executor.submit(run_async_task, bot_app.process_update, update)
        
        # Wait for result with timeout
        try:
            future.result(timeout=30)
            logger.info("✅ Update processed successfully")
        except concurrent.futures.TimeoutError:
            logger.error("❌ Update processing timeout")
        except Exception as e:
            logger.error(f"❌ Update processing error: {e}")
            traceback.print_exc()
        
        return 'OK', 200
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def run_async_task(coro_func, *args):
    """Run async task in separate event loop"""
    try:
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run the coroutine
        result = loop.run_until_complete(coro_func(*args))
        
        # Cleanup
        loop.run_until_complete(asyncio.sleep(0))
        loop.close()
        
        return result
    except Exception as e:
        logger.error(f"Async task error: {e}")
        raise

@flask_app.route('/health')
def health():
    """Health check endpoint"""
    global bot_initialized
    return jsonify({
        "status": "ok",
        "bot": "initialized" if bot_initialized else "not_initialized",
        "timestamp": time.time()
    })

# ====== BOT INITIALIZATION ======
async def initialize_bot():
    """Initialize bot application - ULTIMATE FIX"""
    global bot_app, bot_initialized
    
    try:
        logger.info("🚀 Initializing bot...")
        
        # Build application with proper settings
        bot_app = Application.builder().token(Config.BOT_TOKEN).build()
        
        # Register all handlers
        register_handlers(bot_app)
        
        # Initialize bot
        await bot_app.initialize()
        
        # Set webhook with retry logic
        webhook_url = f"{Config.WEB_APP_URL}/{Config.BOT_TOKEN}"
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Delete old webhook first
                await bot_app.bot.delete_webhook(drop_pending_updates=True)
                
                # Set new webhook
                success = await bot_app.bot.set_webhook(
                    url=webhook_url,
                    allowed_updates=["message", "callback_query", "chat_member"],
                    max_connections=40
                )
                
                if success:
                    logger.info(f"✅ Webhook set successfully: {webhook_url}")
                    break
                else:
                    logger.error(f"❌ Failed to set webhook (attempt {attempt + 1})")
                    
            except Exception as e:
                logger.error(f"Webhook attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                else:
                    raise
        
        bot_initialized = True
        logger.info("✅ Bot initialized successfully!")
        
        # Get webhook info
        webhook_info = await bot_app.bot.get_webhook_info()
        logger.info(f"📊 Webhook Info: {webhook_info}")
        
        return bot_app
        
    except Exception as e:
        logger.error(f"❌ Bot initialization failed: {e}")
        traceback.print_exc()
        bot_initialized = False
        raise e

def register_handlers(app):
    """Register all bot handlers"""
    # Command handlers
    app.add_handler(CommandHandler("start", BotHandlers.start))
    app.add_handler(CommandHandler("check", BotHandlers.check_command))
    app.add_handler(CommandHandler("admin", AdminHandlers.admin_panel))
    
    # Admin commands
    app.add_handler(CommandHandler("stats", AdminHandlers.handle_admin_text))
    app.add_handler(CommandHandler("add", AdminHandlers.handle_admin_text))
    app.add_handler(CommandHandler("remove", AdminHandlers.handle_admin_text))
    app.add_handler(CommandHandler("block", AdminHandlers.handle_admin_text))
    app.add_handler(CommandHandler("unblock", AdminHandlers.handle_admin_text))
    app.add_handler(CommandHandler("clear", AdminHandlers.handle_admin_text))
    
    # Message handlers
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, 
        BotHandlers.group_message
    ))
    app.add_handler(MessageHandler(
        filters.StatusUpdate.WEB_APP_DATA, 
        BotHandlers.web_app_data
    ))
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(AdminHandlers.admin_callback, pattern="^admin_"))
    
    # Broadcast handler (private chat)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        AdminHandlers.handle_broadcast_message
    ))
    
    # Clear reply handler
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        AdminHandlers.handle_clear_reply
    ))
    
    # Error handler
    app.add_error_handler(BotHandlers.error_handler)

def run_bot():
    """Run bot in separate thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(initialize_bot())
    except Exception as e:
        logger.error(f"Bot thread error: {e}")
    finally:
        loop.close()

# ====== MAIN ======
def main():
    """Main entry point - ULTIMATE FIX"""
    logger.info("🚀 Starting application...")
    
    # Initialize bot in background thread
    import threading
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Wait for bot to initialize
    time.sleep(5)
    
    # Start Flask
    logger.info(f"🌐 Flask app starting on port {Config.PORT}")
    
    # Run Flask with production server
    flask_app.run(
        host='0.0.0.0', 
        port=Config.PORT, 
        debug=False,
        threaded=True
    )

if __name__ == "__main__":
    main()
