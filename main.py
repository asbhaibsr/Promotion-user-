# ===== main.py =====
import logging
import os
import sys
import threading
import asyncio
import time
import json
from datetime import datetime

from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from flask import Flask, request, jsonify, render_template
import nest_asyncio

# Important: Apply nest_asyncio
nest_asyncio.apply()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Import modules
from config import Config
from database import Database
from handlers import Handlers
from admin import AdminHandlers

# Initialize components
config = Config()
db = Database(config)
handlers = Handlers(config, db)
admin = AdminHandlers(config, db, handlers)

# Flask app
app = Flask(__name__)

# Bot application reference
bot_app = None

# Global event loop for async tasks
bot_loop = None

# ===== FLASK ROUTES =====
@app.route('/')
def index():
    """Main WebApp page"""
    try:
        user_id = request.args.get('user_id', 0, type=int)
        user_data = db.get_user(user_id) if user_id else None
        
        # Default values if user not found
        if user_data:
            tier_name = config.get_tier_name(user_data.get('tier', 1))
            tier_rate = config.get_tier_rate(user_data.get('tier', 1))
            channel_joined = user_data.get('channel_joined', False)
        else:
            tier_name = config.get_tier_name(1)
            tier_rate = config.get_tier_rate(1)
            channel_joined = False
        
        return render_template(
            'index.html',
            user_id=user_id,
            user_name=user_data.get('first_name', 'User') if user_data else 'Guest',
            balance=user_data.get('balance', 0) if user_data else 0,
            total_earned=user_data.get('total_earned', 0) if user_data else 0,
            tier=user_data.get('tier', 1) if user_data else 1,
            tier_name=tier_name,
            tier_rate=tier_rate,
            total_refs=user_data.get('total_refs', 0) if user_data else 0,
            active_refs=user_data.get('active_refs', 0) if user_data else 0,
            pending_refs=user_data.get('pending_refs', 0) if user_data else 0,
            daily_streak=user_data.get('daily_streak', 0) if user_data else 0,
            channel_joined=channel_joined,
            min_withdrawal=config.MIN_WITHDRAWAL,
            channel=config.CHANNELS['main']['id'],
            channel_link=config.CHANNELS['main']['link'],
            channel_bonus=config.CHANNELS['main']['bonus'],
            movie_group=config.MOVIE_GROUP_LINK,
            new_group=config.NEW_GROUP_LINK,
            all_groups=config.ALL_GROUPS_LINK,
            bot_username=config.BOT_USERNAME,
            daily_referral_earning=config.DAILY_REFERRAL_EARNING
        )
    except Exception as e:
        logger.error(f"Index route error: {e}")
        return f"Error: {str(e)}", 500

@app.route('/api/user/<int:user_id>')
def get_user_api(user_id):
    """API to get user data"""
    try:
        user_data = db.get_user(user_id)
        if user_data:
            # Remove MongoDB _id for JSON serialization
            if '_id' in user_data:
                del user_data['_id']
            return jsonify(user_data)
        return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({'error': str(e)}), 500

# ===== NEW ROUTE: Get user withdrawal history =====
@app.route('/api/user/<int:user_id>/withdrawals')
def get_user_withdrawals_api(user_id):
    """API to get user withdrawal history"""
    try:
        withdrawals = db.get_user_withdrawals(user_id, 10)
        return jsonify(withdrawals)
    except Exception as e:
        logger.error(f"Withdrawal history error: {e}")
        return jsonify([])

@app.route('/api/leaderboard')
def leaderboard_api():
    """API to get leaderboard"""
    try:
        leaderboard = db.get_leaderboard(10)
        return jsonify(leaderboard)
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        return jsonify([])

# ⚡ FIXED: Webhook endpoint - removed bot_app.loop reference
@app.route(f'/webhook', methods=['POST'])
def webhook():
    """Telegram webhook endpoint"""
    global bot_app
    
    if bot_app is None:
        return 'Bot not initialized', 500
        
    try:
        # Get update data
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, bot_app.bot)
        
        # FIX: Use asyncio.create_task with global loop
        global bot_loop
        if bot_loop and bot_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                bot_app.process_update(update),
                bot_loop
            )
        else:
            logger.error("Bot loop not running")
            return 'Bot loop not running', 500
            
        return 'OK', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Error', 500

@app.route('/health')
def health():
    """Health check"""
    return jsonify({'status': 'ok', 'time': datetime.now().isoformat()}), 200

# ===== TELEGRAM BOT SETUP =====
async def post_init(application):
    """Setup after initialization"""
    # Set webhook to the Flask endpoint
    base_url = config.WEBHOOK_URL.rstrip('/')
    webhook_url = f"{base_url}/webhook"
    
    # Delete old webhook first
    await application.bot.delete_webhook(drop_pending_updates=True)
    
    # Set new webhook
    await application.bot.set_webhook(url=webhook_url)
    logger.info(f"✅ Webhook set to: {webhook_url}")
    
    # Set commands
    commands = [
        BotCommand("start", "🚀 Start the bot"),
        BotCommand("app", "📱 Open Mini App"),
        BotCommand("balance", "💰 Check balance"),
        BotCommand("referrals", "👥 My referrals"),
        BotCommand("withdraw", "💸 Withdraw earnings"),
        BotCommand("help", "❓ Help & support")
    ]
    await application.bot.set_my_commands(commands)
    
    # Send startup notification
    try:
        await application.bot.send_message(
            chat_id=config.LOG_CHANNEL_ID,
            text=f"🚀 **Bot Started!**\n\nTime: {datetime.now().isoformat()}\nMode: {config.ENVIRONMENT}",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Log channel error: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler"""
    logger.error(f"Update {update} caused error {context.error}")
    
    try:
        await context.bot.send_message(
            chat_id=config.LOG_CHANNEL_ID,
            text=f"❌ **Error Occurred**\n\nError: {str(context.error)[:500]}",
            parse_mode='Markdown'
        )
    except:
        pass
    
    try:
        if update and update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ An error occurred. Please try again later."
            )
    except:
        pass

async def scheduled_jobs():
    """Run scheduled jobs"""
    global bot_app
    
    while True:
        try:
            now = datetime.now()
            # Check every minute for midnight tasks
            if now.hour == 0 and now.minute == 0:
                # Process daily earnings
                count = db.process_daily_referral_earnings()
                
                if bot_app:
                    await bot_app.bot.send_message(
                        chat_id=config.LOG_CHANNEL_ID,
                        text=f"📊 **Daily Earnings Processed**\n\nProcessed: {count} referrals\nDate: {now.date().isoformat()}",
                        parse_mode='Markdown'
                    )
                
                # Check if it's Monday for weekly leaderboard
                if now.weekday() == 0:  # Monday
                    rewards = db.reset_weekly_leaderboard()
                    
                    reward_text = "🏆 **Weekly Leaderboard Results**\n\n"
                    if rewards:
                        for r in rewards:
                            reward_text += f"• User {r['user_id']}: Rank #{r['rank']} - ₹{r['reward']}\n"
                    else:
                        reward_text += "No rewards this week."
                    
                    if bot_app:
                        await bot_app.bot.send_message(
                            chat_id=config.LOG_CHANNEL_ID,
                            text=reward_text,
                            parse_mode='Markdown'
                        )
            
            await asyncio.sleep(60)  # Check every minute
            
        except Exception as e:
            logger.error(f"Scheduled job error: {e}")
            await asyncio.sleep(60)

def run_flask():
    """Run Flask in separate thread"""
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"🚀 Flask server starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def run_bot():
    """Run the bot in its own event loop"""
    global bot_app, bot_loop
    
    # Create new event loop for this thread
    bot_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(bot_loop)
    
    # Create application
    bot_app = Application.builder().token(config.BOT_TOKEN).build()
    
    # Add handlers
    bot_app.add_handler(CommandHandler("start", handlers.start))
    bot_app.add_handler(CommandHandler("app", handlers.open_app))
    bot_app.add_handler(CommandHandler("balance", handlers.check_balance))
    bot_app.add_handler(CommandHandler("referrals", handlers.show_referrals))
    bot_app.add_handler(CommandHandler("withdraw", handlers.withdraw_cmd))
    bot_app.add_handler(CommandHandler("help", handlers.help_cmd))
    
    # Admin commands
    bot_app.add_handler(CommandHandler("admin", admin.admin_panel))
    
    # Callback handler
    bot_app.add_handler(CallbackQueryHandler(admin.handle_admin_callback))
    
    # WebApp data handler
    bot_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handlers.handle_webapp_data))
    
    # Message handlers
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))
    bot_app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, admin.handle_admin_message))
    
    # Error handler
    bot_app.add_error_handler(error_handler)
    
    # Run post init
    bot_loop.run_until_complete(post_init(bot_app))
    
    # Start scheduled jobs
    bot_loop.create_task(scheduled_jobs())
    
    logger.info("🔄 Bot started in webhook mode")
    
    # Keep the bot running
    bot_loop.run_forever()

def main():
    """Main function"""
    logger.info("🤖 Starting FilmyFund Bot...")
    
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Run bot in main thread
    try:
        run_bot()
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    finally:
        # Cleanup
        if bot_loop:
            bot_loop.stop()

if __name__ == '__main__':
    main()
