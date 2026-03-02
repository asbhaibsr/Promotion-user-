# ===== main.py =====
import logging
import os
import sys
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from flask import Flask, request, jsonify, render_template
import threading
import asyncio
import nest_asyncio
from datetime import datetime
import json

# Apply nest_asyncio to fix event loop issues
nest_asyncio.apply()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import Config
from database import Database
from handlers import Handlers
from admin import AdminHandlers
from utils import Utils

# Initialize components
config = Config()
db = Database(config)
handlers = Handlers(config, db)
admin = AdminHandlers(config, db, handlers)
utils = Utils(config, db)

# Create Flask app for WebApp
app = Flask(__name__)

# Store bot application reference
bot_app = None

# ===== FLASK ROUTES =====
@app.route('/')
def index():
    """Main WebApp page"""
    try:
        # Get user_id from query params
        user_id = request.args.get('user_id', 0, type=int)
        ref_code = request.args.get('start', '')
        
        # Get user data if exists
        user_data = db.get_user(user_id) if user_id else None
        
        if user_data:
            return render_template(
                'index.html',
                user_id=user_id,
                user_name=user_data.get('first_name', 'User'),
                balance=user_data.get('balance', 0),
                total_earned=user_data.get('total_earned', 0),
                spins=user_data.get('spins', 3),
                tier=user_data.get('tier', 1),
                tier_name=config.get_tier_name(user_data.get('tier', 1)),
                tier_rate=config.get_tier_rate(user_data.get('tier', 1)),
                total_refs=user_data.get('total_refs', 0),
                active_refs=user_data.get('active_refs', 0),
                pending_refs=user_data.get('pending_refs', 0),
                monthly_refs=user_data.get('monthly_refs', 0),
                daily_streak=user_data.get('daily_streak', 0),
                channel_joined=user_data.get('channel_joined', False),
                min_withdrawal=config.MIN_WITHDRAWAL,
                channel=config.CHANNEL_USERNAME,
                channel_link=f"https://t.me/{config.CHANNEL_USERNAME.replace('@', '')}",
                channel_bonus=config.CHANNEL_JOIN_BONUS,
                movie_group=config.MOVIE_GROUP_LINK,
                new_group=config.NEW_GROUP_LINK,
                all_groups=config.ALL_GROUPS_LINK,
                bot_username=config.BOT_USERNAME
            )
        else:
            # New user - create basic context
            return render_template(
                'index.html',
                user_id=user_id or 0,
                user_name='Guest',
                balance=0,
                total_earned=0,
                spins=3,
                tier=1,
                tier_name='BASIC',
                tier_rate=0.10,
                total_refs=0,
                active_refs=0,
                pending_refs=0,
                monthly_refs=0,
                daily_streak=0,
                channel_joined=False,
                min_withdrawal=config.MIN_WITHDRAWAL,
                channel=config.CHANNEL_USERNAME,
                channel_link=f"https://t.me/{config.CHANNEL_USERNAME.replace('@', '')}",
                channel_bonus=config.CHANNEL_JOIN_BONUS,
                movie_group=config.MOVIE_GROUP_LINK,
                new_group=config.NEW_GROUP_LINK,
                all_groups=config.ALL_GROUPS_LINK,
                bot_username=config.BOT_USERNAME
            )
    except Exception as e:
        logger.error(f"Index route error: {e}")
        return f"Error loading page: {str(e)}", 500

@app.route('/api/user/<int:user_id>')
def get_user_api(user_id):
    """API to get user data"""
    try:
        user_data = db.get_user(user_id)
        if user_data:
            return jsonify(user_data)
        return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        logger.error(f"API user error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/leaderboard')
def leaderboard_api():
    """API to get leaderboard"""
    try:
        leaderboard = db.get_leaderboard(10)
        return jsonify(leaderboard)
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        return jsonify([])

@app.route('/webhook', methods=['POST'])
def webhook():
    """Telegram webhook endpoint"""
    try:
        update = Update.de_json(request.get_json(force=True), bot_app.bot)
        asyncio.run_coroutine_threadsafe(
            bot_app.process_update(update),
            bot_app.loop
        )
        return 'OK', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Error', 500

# ===== TELEGRAM BOT SETUP =====
async def post_init(application):
    """Setup bot commands after initialization"""
    await application.bot.set_webhook(url=f"{config.WEBHOOK_URL}/webhook")
    logger.info(f"✅ Webhook set to: {config.WEBHOOK_URL}/webhook")
    
    # Set commands
    commands = [
        BotCommand("start", "🚀 Start the bot"),
        BotCommand("app", "📱 Open Mini App"),
        BotCommand("balance", "💰 Check balance"),
        BotCommand("referrals", "👥 My referrals"),
        BotCommand("daily", "🎁 Daily bonus"),
        BotCommand("withdraw", "💳 Withdraw earnings"),
        BotCommand("help", "❓ Help & support")
    ]
    await application.bot.set_my_commands(commands)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler"""
    logger.error(f"Update {update} caused error {context.error}")
    try:
        if update and update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ An error occurred. Please try again later."
            )
    except:
        pass

def run_flask():
    """Run Flask in a separate thread"""
    app.run(host='0.0.0.0', port=config.PORT, debug=False, use_reloader=False)

def main():
    """Main function to run both bot and Flask"""
    global bot_app
    
    # Create bot application
    bot_app = Application.builder().token(config.BOT_TOKEN).build()
    
    # Add handlers
    # Start command
    bot_app.add_handler(CommandHandler("start", handlers.start))
    bot_app.add_handler(CommandHandler("app", handlers.open_app))
    bot_app.add_handler(CommandHandler("balance", handlers.check_balance))
    bot_app.add_handler(CommandHandler("referrals", handlers.show_referrals))
    bot_app.add_handler(CommandHandler("daily", handlers.daily_bonus_cmd))
    bot_app.add_handler(CommandHandler("withdraw", handlers.withdraw_cmd))
    bot_app.add_handler(CommandHandler("help", handlers.help_cmd))
    
    # Callback queries
    bot_app.add_handler(CallbackQueryHandler(handlers.handle_callback))
    
    # WebApp data handler - CRITICAL for actions to work!
    bot_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handlers.handle_webapp_data))
    
    # Message handlers
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))
    
    # Admin commands
    bot_app.add_handler(CommandHandler("admin", admin.admin_panel))
    bot_app.add_handler(CommandHandler("stats", admin.stats))
    bot_app.add_handler(CommandHandler("broadcast", admin.broadcast))
    bot_app.add_handler(CommandHandler("addbalance", admin.add_balance))
    bot_app.add_handler(CommandHandler("setbonus", admin.set_daily_bonus))
    
    # Error handler
    bot_app.add_error_handler(error_handler)
    
    # Set post init
    bot_app.post_init = post_init
    
    # Start Flask in a thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    logger.info("🚀 Bot and Flask server started!")
    
    # Run bot with polling (for development) or webhook (for production)
    if config.ENVIRONMENT == "development":
        bot_app.run_polling()
    else:
        # Run bot in webhook mode
        bot_app.run_webhook(
            listen="0.0.0.0",
            port=config.PORT,
            url_path=config.BOT_TOKEN,
            webhook_url=f"{config.WEBHOOK_URL}/{config.BOT_TOKEN}"
        )

if __name__ == '__main__':
    main()
