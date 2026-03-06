# ===== main.py =====

import logging
import os
import sys
import asyncio
import threading
import time
import json
import signal
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Suppress noisy logs
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)

# Import with error handling
try:
    from flask import Flask, request, jsonify, render_template
    from telegram import Update, BotCommand
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
    from telegram.constants import ParseMode
    import nest_asyncio
    from dotenv import load_dotenv
    import pytz
except ImportError as e:
    logger.critical(f"Import Error: {e}")
    sys.exit(1)

# Apply nest_asyncio
nest_asyncio.apply()

# Load environment variables
load_dotenv()

# Import our modules
from config import Config
from database import Database
from handlers import Handlers
from admin import AdminHandlers  # Add this import

# ========== FLASK APP ==========
app = Flask(__name__)

# Global references
config = None
db = None
handlers = None
admin_handlers = None  # Add this
bot_app = None
bot_loop = None

# Health status
start_time = datetime.now()
request_count = 0


@app.route('/')
def index():
    """Main WebApp page"""
    global config, db, request_count
    request_count += 1
    
    try:
        user_id = request.args.get('user_id', 0, type=int)
        
        # Get user data
        user_data = None
        if user_id and user_id > 0 and db:
            user_data = db.get_user(user_id)
        
        # Default values
        template_vars = {
            'user_id': user_id,
            'user_name': 'Guest',
            'balance': 0,
            'total_earned': 0,
            'tier': 1,
            'tier_name': '🥉 BASIC',
            'tier_rate': 0.30,
            'total_refs': 0,
            'active_refs': 0,
            'pending_refs': 0,
            'daily_streak': 0,
            'channel_joined': False,
            'min_withdrawal': config.MIN_WITHDRAWAL if config else 50,
            'channel_id': config.CHANNEL_ID if config else '',
            'channel_link': config.CHANNEL_LINK if config else '',
            'channel_bonus': config.CHANNEL_JOIN_BONUS if config else 2.0,
            'movie_group_link': config.MOVIE_GROUP_LINK if config else '',
            'movie_group_id': config.MOVIE_GROUP_ID if config else '',
            'all_groups_link': config.ALL_GROUPS_LINK if config else '',
            'bot_username': config.BOT_USERNAME if config else '',
            'daily_referral_earning': config.DAILY_REFERRAL_EARNING if config else 0.30
        }
        
        # Override with user data
        if user_data:
            template_vars.update({
                'user_name': user_data.get('first_name', 'User'),
                'balance': user_data.get('balance', 0),
                'total_earned': user_data.get('total_earned', 0),
                'tier': user_data.get('tier', 1),
                'tier_name': config.get_tier_name(user_data.get('tier', 1)) if config else '🥉 BASIC',
                'tier_rate': config.get_tier_rate(user_data.get('tier', 1)) if config else 0.30,
                'total_refs': user_data.get('total_refs', 0),
                'active_refs': user_data.get('active_refs', 0),
                'pending_refs': user_data.get('pending_refs', 0),
                'daily_streak': user_data.get('daily_streak', 0),
                'channel_joined': user_data.get('channel_joined', False)
            })
        
        return render_template('index.html', **template_vars)
        
    except Exception as e:
        logger.error(f"Index route error: {e}")
        return f"Error: {str(e)}", 500


@app.route('/api/user/<int:user_id>')
def get_user_api(user_id):
    """API to get user data"""
    global db, request_count
    request_count += 1
    
    try:
        if user_id == 0:
            return jsonify({
                'user_id': 0,
                'first_name': 'Guest',
                'balance': 0,
                'total_earned': 0,
                'tier': 1,
                'tier_name': '🥉 BASIC',
                'total_refs': 0,
                'active_refs': 0,
                'pending_refs': 0,
                'daily_streak': 0,
                'channel_joined': False
            })
        
        user_data = db.get_user(user_id) if db else None
        if user_data:
            return jsonify(user_data)
        
        return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/<int:user_id>/withdrawals')
def get_user_withdrawals_api(user_id):
    """API to get user withdrawal history"""
    global db, request_count
    request_count += 1
    
    try:
        withdrawals = db.get_user_withdrawals(user_id, 10) if db else []
        return jsonify(withdrawals)
    except Exception as e:
        logger.error(f"Withdrawal history error: {e}")
        return jsonify([])


@app.route('/api/leaderboard')
def leaderboard_api():
    """API to get leaderboard"""
    global db, request_count
    request_count += 1
    
    try:
        leaderboard = db.get_leaderboard(10) if db else []
        return jsonify(leaderboard)
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        return jsonify([])


@app.route('/api/stats')
def stats_api():
    """API to get system stats"""
    global request_count, start_time, db
    
    uptime = str(datetime.now() - start_time).split('.')[0]
    
    stats = {
        'uptime': uptime,
        'requests': request_count,
        'status': 'healthy',
        'db_connected': db.connected if db else False,
        'timestamp': datetime.now().isoformat()
    }
    
    return jsonify(stats)


@app.route('/health')
def health():
    """Health check endpoint"""
    global db
    
    status = {
        'status': 'ok',
        'time': datetime.now().isoformat(),
        'db_connected': db.connected if db else False
    }
    
    if not db or not db.connected:
        status['status'] = 'degraded'
        return jsonify(status), 503
    
    return jsonify(status)


@app.route('/favicon.ico')
def favicon():
    """Favicon fix"""
    return "", 204


# ========== BOT SETUP ==========
async def post_init(application):
    """Setup after initialization"""
    global config
    
    logger.info("🚀 Running post-initialization setup...")
    
    try:
        # Set commands
        commands = [
            BotCommand("start", "🚀 Start the bot"),
            BotCommand("app", "📱 Open Mini App"),
            BotCommand("balance", "💰 Check balance"),
            BotCommand("referrals", "👥 My referrals"),
            BotCommand("withdraw", "💸 Withdraw earnings"),
            BotCommand("admin", "👑 Admin Panel"),
            BotCommand("help", "❓ Help")
        ]
        await application.bot.set_my_commands(commands)
        
        # Send startup notification
        if config.LOG_CHANNEL_ID:
            try:
                await application.bot.send_message(
                    chat_id=config.LOG_CHANNEL_ID,
                    text=(
                        f"🚀 **Bot Started!**\n\n"
                        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Log channel error: {e}")
        
        logger.info("✅ Bot initialization complete")
        
    except Exception as e:
        logger.error(f"Post-init error: {e}")


async def scheduled_jobs():
    """Run scheduled background jobs"""
    global db, config
    
    logger.info("🔄 Scheduled jobs started")
    
    while True:
        try:
            now = datetime.now()
            
            # Daily earnings at midnight
            if now.hour == 0 and now.minute == 0:
                logger.info("🔄 Processing daily earnings...")
                count = db.process_daily_referral_earnings()
                logger.info(f"✅ Processed {count} daily earnings")
            
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Scheduled job error: {e}")
            await asyncio.sleep(60)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler"""
    logger.error(f"Update {update} caused error {context.error}")
    
    # Try to notify user
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ An error occurred. Please try again later."
            )
        except:
            pass


def run_bot():
    """Run the bot in polling mode (simpler for Render)"""
    global bot_app, bot_loop, config, db, handlers, admin_handlers
    
    logger.info("🤖 Starting bot in polling mode...")
    
    # Create new event loop
    bot_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(bot_loop)
    
    try:
        # Create application
        bot_app = Application.builder().token(config.BOT_TOKEN).build()
        
        # Add regular handlers
        bot_app.add_handler(CommandHandler("start", handlers.start))
        bot_app.add_handler(CommandHandler("app", handlers.open_app))
        bot_app.add_handler(CommandHandler("balance", handlers.check_balance))
        bot_app.add_handler(CommandHandler("referrals", handlers.show_referrals))
        bot_app.add_handler(CommandHandler("withdraw", handlers.withdraw_cmd))
        bot_app.add_handler(CommandHandler("help", handlers.help_cmd))
        
        # Add admin handlers
        bot_app.add_handler(CommandHandler("admin", admin_handlers.admin_panel))
        bot_app.add_handler(CallbackQueryHandler(admin_handlers.handle_admin_callback, pattern="^admin_"))
        bot_app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, admin_handlers.handle_admin_message))
        
        # Message handlers
        bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))
        bot_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handlers.handle_webapp_data))
        
        # Error handler
        bot_app.add_error_handler(error_handler)
        
        # Run post init
        bot_loop.run_until_complete(post_init(bot_app))
        
        # Start scheduled jobs
        bot_loop.create_task(scheduled_jobs())
        
        logger.info("✅ Bot started successfully")
        
        # Start polling
        bot_app.run_polling()
        
    except Exception as e:
        logger.error(f"Bot error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if bot_loop:
            bot_loop.close()


def run_flask():
    """Run Flask in separate thread"""
    global config
    
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 Flask server starting on port {port}")
    
    # Run Flask
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        use_reloader=False,
        threaded=True
    )


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("🛑 Shutting down...")
    
    global db, bot_loop
    
    # Cleanup
    if db:
        db.cleanup()
    
    if bot_loop:
        bot_loop.stop()
    
    sys.exit(0)


def main():
    """Main function"""
    global config, db, handlers, admin_handlers
    
    print("""
    ╔══════════════════════════════════════╗
    ║     FILMYFUND BOT - FIXED VERSION    ║
    ║        100% WORKING SOLUTION          ║
    ╚══════════════════════════════════════╝
    """)
    
    logger.info("🚀 Starting FilmyFund Bot...")
    
    try:
        # Initialize config
        logger.info("📝 Loading configuration...")
        config = Config()
        
        # Initialize database
        logger.info("🗄️ Connecting to database...")
        db = Database(config)
        
        # Initialize handlers
        logger.info("🔄 Initializing handlers...")
        handlers = Handlers(config, db)
        
        # Initialize admin handlers
        logger.info("👑 Initializing admin handlers...")
        admin_handlers = AdminHandlers(config, db)
        
        # Set signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start Flask in a separate thread
        logger.info("🌐 Starting Flask web server...")
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        # Small delay for Flask to start
        time.sleep(2)
        
        # Run bot in main thread (using polling instead of webhook)
        logger.info("🤖 Starting Telegram bot...")
        run_bot()
        
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if db:
            db.cleanup()
        logger.info("👋 Shutdown complete")


if __name__ == '__main__':
    main()
