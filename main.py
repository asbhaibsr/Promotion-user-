# ===== main.py =====
import logging
import os
import sys
from telegram import Update, BotCommand
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

# Apply nest_asyncio
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

# ===== FLASK ROUTES =====
@app.route('/')
def index():
    """Main WebApp page"""
    try:
        user_id = request.args.get('user_id', 0, type=int)
        user_data = db.get_user(user_id) if user_id else None
        
        return render_template(
            'index.html',
            user_id=user_id,
            user_name=user_data.get('first_name', 'User') if user_data else 'Guest',
            balance=user_data.get('balance', 0) if user_data else 0,
            total_earned=user_data.get('total_earned', 0) if user_data else 0,
            spins=user_data.get('spins', 3) if user_data else 3,
            tier=user_data.get('tier', 1) if user_data else 1,
            tier_name=config.get_tier_name(user_data.get('tier', 1) if user_data else 1),
            tier_rate=config.get_tier_rate(user_data.get('tier', 1) if user_data else 1),
            total_refs=user_data.get('total_refs', 0) if user_data else 0,
            active_refs=user_data.get('active_refs', 0) if user_data else 0,
            pending_refs=user_data.get('pending_refs', 0) if user_data else 0,
            daily_streak=user_data.get('daily_streak', 0) if user_data else 0,
            channel_joined=user_data.get('channel_joined', False) if user_data else False,
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
            # Remove sensitive fields
            if '_id' in user_data:
                del user_data['_id']
            return jsonify(user_data)
        return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        logger.error(f"API error: {e}")
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

@app.route('/health')
def health():
    """Health check"""
    return jsonify({'status': 'ok', 'time': datetime.now().isoformat()}), 200

# ===== TELEGRAM BOT SETUP =====
async def post_init(application):
    """Setup after initialization"""
    webhook_url = f"{config.WEBHOOK_URL}/webhook"
    await application.bot.set_webhook(url=webhook_url)
    logger.info(f"✅ Webhook set to: {webhook_url}")
    
    # Set commands
    commands = [
        BotCommand("start", "🚀 Start the bot"),
        BotCommand("app", "📱 Open Mini App"),
        BotCommand("balance", "💰 Check balance"),
        BotCommand("referrals", "👥 My referrals"),
        BotCommand("help", "❓ Help & support")
    ]
    await application.bot.set_my_commands(commands)
    
    # Send startup notification to log channel
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
    
    # Send to log channel
    try:
        await context.bot.send_message(
            chat_id=config.LOG_CHANNEL_ID,
            text=f"❌ **Error Occurred**\n\nError: {str(context.error)[:500]}\nUpdate: {str(update)[:500]}",
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

def run_flask():
    """Run Flask in separate thread"""
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"🚀 Flask server starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

async def scheduled_jobs():
    """Run scheduled jobs"""
    while True:
        try:
            # Check if it's midnight (00:00)
            now = datetime.now()
            if now.hour == 0 and now.minute == 0:
                # Process daily earnings
                count = db.process_daily_referral_earnings()
                
                # Send to log channel
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
                    
                    await bot_app.bot.send_message(
                        chat_id=config.LOG_CHANNEL_ID,
                        text=reward_text,
                        parse_mode='Markdown'
                    )
            
            await asyncio.sleep(60)  # Check every minute
            
        except Exception as e:
            logger.error(f"Scheduled job error: {e}")
            await asyncio.sleep(60)

def main():
    """Main function"""
    global bot_app
    
    logger.info("🤖 Starting FilmyFund Bot...")
    
    # Build application
    bot_app = Application.builder().token(config.BOT_TOKEN).build()
    
    # Add handlers
    bot_app.add_handler(CommandHandler("start", handlers.start))
    bot_app.add_handler(CommandHandler("app", handlers.open_app))
    bot_app.add_handler(CommandHandler("balance", handlers.check_balance))
    bot_app.add_handler(CommandHandler("referrals", handlers.show_referrals))
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
    
    # Post init
    bot_app.post_init = post_init
    
    # Start Flask thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Start scheduled jobs
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(scheduled_jobs())
    
    # Run bot
    if config.ENVIRONMENT == "development":
        logger.info("🔄 Running in polling mode...")
        bot_app.run_polling()
    else:
        logger.info(f"🔄 Running in webhook mode...")
        bot_app.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get('PORT', 8080)),
            url_path=config.BOT_TOKEN,
            webhook_url=f"{config.WEBHOOK_URL}/{config.BOT_TOKEN}"
        )

if __name__ == '__main__':
    main()
