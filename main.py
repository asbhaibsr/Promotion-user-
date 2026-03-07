# ===== main.py (FINAL - WITH ALL APIs) =====

import logging
import os
import sys
import asyncio
import threading
import time
import json
import signal
import random
from datetime import datetime, timedelta

import requests
from bson.objectid import ObjectId
from flask import Flask, request, jsonify, render_template
from functools import wraps

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
logging.getLogger('pymongo').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

try:
    from flask import Flask, request, jsonify, render_template
    from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
    from telegram.constants import ParseMode
    import nest_asyncio
    from dotenv import load_dotenv
except ImportError as e:
    logger.critical(f"Import Error: {e}")
    print(f"Missing dependency: {e}")
    print("Please install required packages: pip install python-telegram-bot flask pymongo python-dotenv nest-asyncio cachetools certifi requests")
    sys.exit(1)

nest_asyncio.apply()
load_dotenv()

from config import Config
from database import Database
from handlers import Handlers
from admin import AdminHandlers

# ========== FLASK APP ==========
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'filmyfund-secret-key-2024')

# Global references
config = None
db = None
handlers = None
admin_handlers = None
bot_app = None
bot_loop = None
bot_running = False

# Health status
start_time = datetime.now()
request_count = 0

# ========== FLASK ROUTES ==========

@app.route('/')
def index():
    """Main WebApp page"""
    global config, db, request_count
    request_count += 1
    
    try:
        user_id = request.args.get('user_id', 0, type=int)
        logger.info(f"🌐 Index page accessed by user_id: {user_id}")
        
        user_data = None
        if user_id and user_id > 0 and db and db.ensure_connection():
            try:
                user_data = db.get_user(user_id)
                if user_data:
                    logger.info(f"✅ User data loaded for {user_id}")
                else:
                    logger.warning(f"⚠️ User {user_id} not found in database")
            except Exception as e:
                logger.error(f"Error fetching user {user_id}: {e}")
        
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
            'min_withdrawal': config.MIN_WITHDRAWAL if config and hasattr(config, 'MIN_WITHDRAWAL') else 50,
            'channel_id': config.CHANNEL_ID if config and hasattr(config, 'CHANNEL_ID') else '',
            'channel_link': config.CHANNEL_LINK if config and hasattr(config, 'CHANNEL_LINK') else '',
            'channel_bonus': config.CHANNEL_JOIN_BONUS if config and hasattr(config, 'CHANNEL_JOIN_BONUS') else 2.0,
            'movie_group_link': config.MOVIE_GROUP_LINK if config and hasattr(config, 'MOVIE_GROUP_LINK') else '',
            'movie_group_id': config.MOVIE_GROUP_ID if config and hasattr(config, 'MOVIE_GROUP_ID') else '',
            'all_groups_link': config.ALL_GROUPS_LINK if config and hasattr(config, 'ALL_GROUPS_LINK') else '',
            'bot_username': config.BOT_USERNAME if config and hasattr(config, 'BOT_USERNAME') else '',
            'daily_referral_earning': config.DAILY_REFERRAL_EARNING if config and hasattr(config, 'DAILY_REFERRAL_EARNING') else 0.30,
            'support_username': config.SUPPORT_USERNAME if config and hasattr(config, 'SUPPORT_USERNAME') else '@support'
        }
        
        if user_data:
            template_vars.update({
                'user_name': user_data.get('first_name', 'User'),
                'balance': user_data.get('balance', 0),
                'total_earned': user_data.get('total_earned', 0),
                'tier': user_data.get('tier', 1),
                'tier_name': config.get_tier_name(user_data.get('tier', 1)) if config and hasattr(config, 'get_tier_name') else '🥉 BASIC',
                'tier_rate': config.get_tier_rate(user_data.get('tier', 1)) if config and hasattr(config, 'get_tier_rate') else 0.30,
                'total_refs': user_data.get('total_refs', 0),
                'active_refs': user_data.get('active_refs', 0),
                'pending_refs': user_data.get('pending_refs', 0),
                'daily_streak': user_data.get('daily_streak', 0),
                'channel_joined': user_data.get('channel_joined', False)
            })
        
        return render_template('index.html', **template_vars)
        
    except Exception as e:
        logger.error(f"Index route error: {e}")
        import traceback
        traceback.print_exc()
        return f"Error loading page: {str(e)}", 500


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
                'channel_joined': False,
                'is_admin': False,
                'dark_mode': False,
                'notify_referrals': True,
                'notify_earnings': True,
                'notify_withdrawals': True
            })
        
        if not db or not db.ensure_connection():
            return jsonify({'error': 'Database not connected'}), 503
        
        user_data = db.get_user(user_id)
        if user_data:
            if '_id' in user_data:
                user_data['_id'] = str(user_data['_id'])
            return jsonify(user_data)
        
        return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        logger.error(f"API error for user {user_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/<int:user_id>/withdrawals')
def get_user_withdrawals_api(user_id):
    """API to get user withdrawal history"""
    global db, request_count
    request_count += 1
    
    try:
        if not db or not db.ensure_connection():
            return jsonify([])
        
        withdrawals = db.get_user_withdrawals(user_id, 10)
        for w in withdrawals:
            if '_id' in w:
                w['_id'] = str(w['_id'])
        return jsonify(withdrawals)
    except Exception as e:
        logger.error(f"Withdrawal history error: {e}")
        return jsonify([])


@app.route('/api/user/<int:user_id>/bonus-days')
def get_user_bonus_days(user_id):
    """Get user's claimed bonus days"""
    try:
        if not db or not db.ensure_connection():
            return jsonify({'claimed_days': []})
        
        claimed_days = db.get_user_bonus_days(user_id)
        return jsonify({'claimed_days': claimed_days})
        
    except Exception as e:
        logger.error(f"Bonus days error: {e}")
        return jsonify({'claimed_days': []})


@app.route('/api/user/<int:user_id>/missions')
def get_user_missions(user_id):
    """Get user's mission progress"""
    try:
        if not db or not db.ensure_connection():
            return jsonify({})
        
        missions = db.get_user_missions(user_id)
        if missions:
            return jsonify({
                'mission1': missions.get('mission1', {}),
                'mission2': missions.get('mission2', {}),
                'reward_claimed': missions.get('reward_claimed', False)
            })
        
        return jsonify({})
        
    except Exception as e:
        logger.error(f"Missions error: {e}")
        return jsonify({})


@app.route('/api/user/<int:user_id>/claimed-ads')
def get_user_claimed_ads(user_id):
    """Get user's claimed ads"""
    try:
        if not db or not db.ensure_connection():
            return jsonify({'claimed_ads': []})
        
        today = datetime.now().date().isoformat()
        claimed = db.get_user_claimed_ads(user_id, today)
        return jsonify({'claimed_ads': [{'ad_id': ad, 'date': today} for ad in claimed]})
        
    except Exception as e:
        logger.error(f"Claimed ads error: {e}")
        return jsonify({'claimed_ads': []})


@app.route('/api/leaderboard')
def leaderboard_api():
    """API to get leaderboard"""
    global db, request_count
    request_count += 1
    
    try:
        if not db or not db.ensure_connection():
            return jsonify([])
        
        leaderboard = db.get_leaderboard(10)
        return jsonify(leaderboard)
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        return jsonify([])


@app.route('/api/live-activity')
def live_activity_api():
    """API to get live activity feed"""
    global db
    try:
        if not db or not db.ensure_connection():
            return jsonify([])
        
        activities = db.get_live_activity(20)
        
        for act in activities:
            if 'user_id' not in act:
                act['user_id'] = 0
        
        return jsonify(activities)
        
    except Exception as e:
        logger.error(f"Live activity error: {e}")
        return jsonify([])


@app.route('/api/ads')
def get_ads_api():
    """Get ads from database"""
    global db
    try:
        if db and db.ensure_connection():
            ads = db.get_all_ads()
            return jsonify({'ads': ads})
        else:
            return jsonify({
                'ads': [
                    {'id': 1, 'title': 'Install App & Earn', 'reward': 2.0, 'link': 'https://t.me/+8SdeM5gBihoxZjU1', 'meta': '⏱️ 2 min • 1.2k completed', 'icon': '📱'},
                    {'id': 2, 'title': 'Watch Video', 'reward': 0.5, 'link': 'https://t.me/+8SdeM5gBihoxZjU1', 'meta': '⏱️ 30 sec • 3.4k completed', 'icon': '🎬'}
                ]
            })
    except Exception as e:
        logger.error(f"Get ads error: {e}")
        return jsonify({'ads': []})


@app.route('/api/claim-day-bonus', methods=['POST'])
def claim_day_bonus_api():
    """Claim bonus for specific day"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        date_str = data.get('date')
        
        if not user_id or not date_str:
            return jsonify({'success': False, 'message': 'Missing data'}), 400
        
        result = db.claim_day_bonus(user_id, date_str)
        
        if result and result.get('success'):
            return jsonify({
                'success': True,
                'bonus': result['bonus'],
                'streak': result['streak']
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Already claimed today or invalid date'
            })
            
    except Exception as e:
        logger.error(f"Claim day bonus error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/update-mission', methods=['POST'])
def update_mission_api():
    """Update mission progress"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        mission_type = data.get('mission_type')
        count = data.get('count', 1)
        
        if not user_id or not mission_type:
            return jsonify({'success': False, 'message': 'Missing data'}), 400
        
        missions = db.update_mission_progress(user_id, mission_type, count)
        
        if missions:
            return jsonify({
                'success': True,
                'missions': {
                    'mission1': missions.get('mission1', {}),
                    'mission2': missions.get('mission2', {})
                }
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to update'})
            
    except Exception as e:
        logger.error(f"Update mission error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/claim-mission-reward', methods=['POST'])
def claim_mission_reward_api():
    """Claim daily mission reward"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'success': False, 'message': 'Missing user ID'}), 400
        
        result = db.claim_mission_reward(user_id)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Claim mission reward error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/claim-ad', methods=['POST'])
def claim_ad_api():
    """Claim ad reward"""
    global db
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        ad_id = data.get('ad_id')
        reward = data.get('reward')
        
        if not all([user_id, ad_id, reward]):
            return jsonify({'success': False, 'message': 'Missing data'}), 400
        
        success = db.claim_ad(user_id, ad_id, reward)
        
        if success:
            return jsonify({'success': True, 'message': 'Reward added'})
        else:
            return jsonify({'success': False, 'message': 'Already claimed today'})
            
    except Exception as e:
        logger.error(f"Claim ad error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/update-ad', methods=['POST'])
def update_ad_api():
    """Update ad (admin only)"""
    global db
    try:
        data = request.get_json()
        ad_id = data.get('ad_id')
        title = data.get('title')
        reward = data.get('reward')
        link = data.get('link')
        meta = data.get('meta')
        icon = data.get('icon')
        admin_id = data.get('admin_id')
        
        if not admin_id:
            return jsonify({'success': False, 'message': 'Admin verification required'}), 401
        
        admin_user = db.get_user(int(admin_id))
        if not admin_user or not admin_user.get('is_admin', False):
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
        success = db.update_ad(ad_id, title, reward, link, meta, icon)
        
        if success:
            db.reset_ad_claims(ad_id)
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Failed to update'})
        
    except Exception as e:
        logger.error(f"Update ad error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/delete-ad', methods=['POST'])
def delete_ad_api():
    """Delete an ad (admin only)"""
    global db
    try:
        data = request.get_json()
        ad_id = data.get('ad_id')
        admin_id = data.get('admin_id')
        
        if not admin_id:
            return jsonify({'success': False, 'message': 'Admin verification required'}), 401
        
        admin_user = db.get_user(int(admin_id))
        if not admin_user or not admin_user.get('is_admin', False):
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
        success = db.delete_ad(ad_id)
        
        if success:
            return jsonify({'success': True, 'message': 'Ad deleted'})
        else:
            return jsonify({'success': False, 'message': 'Ad not found'})
        
    except Exception as e:
        logger.error(f"Delete ad error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/reset-ad-claims', methods=['POST'])
def reset_ad_claims_api():
    """Reset all claims for an ad (when admin edits)"""
    global db
    try:
        data = request.get_json()
        ad_id = data.get('ad_id')
        admin_id = data.get('admin_id')
        
        admin_user = db.get_user(int(admin_id))
        if not admin_user or not admin_user.get('is_admin', False):
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
        success = db.reset_ad_claims(ad_id)
        return jsonify({'success': success})
        
    except Exception as e:
        logger.error(f"Reset ad claims error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/update-setting', methods=['POST'])
def update_setting_api():
    """Update user settings"""
    global db
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        setting = data.get('setting')
        value = data.get('value')
        
        if not all([user_id, setting]):
            return jsonify({'success': False, 'message': 'Missing data'}), 400
        
        setting_map = {
            'dark_mode': 'dark_mode',
            'sound_enabled': 'sound_enabled',
            'notifications': 'notify_earnings',
            'notify_referrals': 'notify_referrals',
            'notify_earnings': 'notify_earnings',
            'notify_withdrawals': 'notify_withdrawals'
        }
        
        db_field = setting_map.get(setting)
        if db_field and db and db.ensure_connection():
            db.update_notification_setting(user_id, setting, value)
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Update setting error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/withdraw', methods=['POST'])
def withdraw_api():
    """API to process withdrawal"""
    global db
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        amount = data.get('amount')
        method = data.get('method')
        details = data.get('details')
        
        if not all([user_id, amount, method, details]):
            return jsonify({'success': False, 'message': 'Missing data'}), 400
        
        result = db.process_withdrawal(user_id, amount, method, details)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Withdraw API error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/support', methods=['POST'])
def support_api():
    """API to send support message"""
    global db, bot_app, bot_loop
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        message = data.get('message')
        
        if not user_id or not message:
            return jsonify({'success': False, 'message': 'Missing data'}), 400
        
        msg_id = db.add_support_message(user_id, message)
        
        if msg_id:
            if bot_app and config:
                for admin_id in config.ADMIN_IDS:
                    try:
                        keyboard = [[InlineKeyboardButton("📩 VIEW MESSAGE", callback_data=f"view_support_{msg_id}")]]
                        
                        asyncio.run_coroutine_threadsafe(
                            bot_app.bot.send_message(
                                chat_id=admin_id,
                                text=(
                                    f"📩 **New Support Message**\n\n"
                                    f"User ID: `{user_id}`\n"
                                    f"Message: {message[:100]}...\n\n"
                                    f"Click below to reply:"
                                ),
                                reply_markup=InlineKeyboardMarkup(keyboard)
                            ),
                            bot_loop
                        )
                    except:
                        pass
            
            return jsonify({'success': True, 'message': 'Message sent to support'})
        else:
            return jsonify({'success': False, 'message': 'Failed to send message'})
        
    except Exception as e:
        logger.error(f"Support API error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


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
    
    if db and db.connected:
        try:
            system_stats = db.get_system_stats()
            stats.update(system_stats)
        except:
            pass
    
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


@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook endpoint for Telegram"""
    global bot_app, bot_loop
    
    if not bot_app:
        return "Bot not initialized", 503
    
    try:
        update = Update.de_json(request.get_json(force=True), bot_app.bot)
        asyncio.run_coroutine_threadsafe(
            bot_app.process_update(update),
            bot_loop
        )
        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "Error", 500


# ========== BOT SETUP ==========

async def post_init(application):
    """Setup after initialization"""
    global config
    
    logger.info("🚀 Running post-initialization setup...")
    
    try:
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
        
        if config and hasattr(config, 'WEBHOOK_URL') and config.WEBHOOK_URL:
            webhook_url = f"{config.WEBHOOK_URL}/webhook"
            await application.bot.set_webhook(url=webhook_url)
            logger.info(f"✅ Webhook set to {webhook_url}")
        
        if config and hasattr(config, 'LOG_CHANNEL_ID') and config.LOG_CHANNEL_ID:
            try:
                await application.bot.send_message(
                    chat_id=config.LOG_CHANNEL_ID,
                    text=(
                        f"🚀 **Bot Started!**\n\n"
                        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"Mode: {'Webhook' if config.WEBHOOK_URL else 'Polling'}"
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
            
            if now.hour == 0 and now.minute == 0:
                logger.info("🔄 Processing daily earnings...")
                if db and db.ensure_connection():
                    count = db.process_daily_referral_earnings()
                    logger.info(f"✅ Processed {count} daily earnings")
            
            if now.minute == 0:
                if db and db.ensure_connection():
                    total_users = db.users.count_documents({})
                    active_today = db.daily_searches.count_documents({'date': now.date().isoformat()})
                    pending_support = db.issues.count_documents({'status': 'pending'})
                    logger.info(f"📊 Stats - Users: {total_users}, Active Today: {active_today}, Support: {pending_support}")
            
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Scheduled job error: {e}")
            await asyncio.sleep(60)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler"""
    logger.error(f"Update {update} caused error {context.error}")
    
    import traceback
    traceback.print_exc()
    
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ An error occurred. Please try again later.\n"
                "If this persists, contact support."
            )
        except:
            pass


def run_bot():
    """Run the bot"""
    global bot_app, bot_loop, config, db, handlers, admin_handlers, bot_running
    
    logger.info("🤖 Starting bot...")
    
    if bot_running:
        logger.warning("⚠️ Bot is already running, skipping...")
        return
    
    bot_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(bot_loop)
    
    try:
        bot_app = Application.builder().token(config.BOT_TOKEN).build()
        
        # ===== COMMAND HANDLERS =====
        bot_app.add_handler(CommandHandler("start", handlers.start))
        bot_app.add_handler(CommandHandler("app", handlers.open_app))
        bot_app.add_handler(CommandHandler("balance", handlers.check_balance))
        bot_app.add_handler(CommandHandler("referrals", handlers.show_referrals))
        bot_app.add_handler(CommandHandler("withdraw", handlers.withdraw_cmd))
        bot_app.add_handler(CommandHandler("help", handlers.help_cmd))
        bot_app.add_handler(CommandHandler("admin", admin_handlers.admin_panel))
        
        # ===== CALLBACK HANDLERS =====
        bot_app.add_handler(CallbackQueryHandler(admin_handlers.handle_admin_callback))
        
        # ===== MESSAGE HANDLERS =====
        bot_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handlers.handle_webapp_data))
        bot_app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, admin_handlers.handle_admin_message))
        bot_app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUP, handlers.handle_message))
        bot_app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.SUPERGROUP, handlers.handle_message))
        bot_app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, handlers.handle_message))
        
        # ===== ERROR HANDLER =====
        bot_app.add_error_handler(error_handler)
        
        # Run post init
        bot_loop.run_until_complete(post_init(bot_app))
        
        # Start scheduled jobs
        bot_loop.create_task(scheduled_jobs())
        
        logger.info("✅ Bot started successfully")
        bot_running = True
        
        # Start polling
        logger.info("🔄 Starting polling...")
        bot_app.run_polling()
        
    except Exception as e:
        logger.error(f"Bot error: {e}")
        import traceback
        traceback.print_exc()
        bot_running = False
    finally:
        if bot_loop:
            bot_loop.close()
        bot_running = False


def run_flask():
    """Run Flask in separate thread"""
    global config
    
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 Flask server starting on port {port}")
    
    try:
        app.run(
            host='0.0.0.0',
            port=port,
            debug=False,
            use_reloader=False,
            threaded=True
        )
    except Exception as e:
        logger.error(f"Flask error: {e}")
        sys.exit(1)


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("🛑 Shutting down...")
    
    global db, bot_loop, bot_running
    
    if db:
        try:
            db.cleanup()
            logger.info("✅ Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database: {e}")
    
    if bot_loop:
        try:
            bot_loop.stop()
            logger.info("✅ Bot loop stopped")
        except:
            pass
    
    bot_running = False
    logger.info("👋 Shutdown complete")
    sys.exit(0)


def check_environment():
    """Check if all required environment variables are set"""
    required_vars = ['BOT_TOKEN', 'MONGODB_URI', 'ADMIN_IDS']
    missing = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        return False
    
    return True


def main():
    """Main function"""
    global config, db, handlers, admin_handlers, bot_running
    
    print("""
    ╔══════════════════════════════════════╗
    ║     FILMYFUND BOT - FINAL VERSION    ║
    ║         ALL FEATURES WORKING          ║
    ║     Search User | Broadcast | WD     ║
    ║    Calendar | Missions | Support     ║
    ║    Live Activity | Log Channel       ║
    ╚══════════════════════════════════════╝
    """)
    
    logger.info("🚀 Starting FilmyFund Bot...")
    
    if not check_environment():
        logger.error("Please set all required environment variables in .env file")
        sys.exit(1)
    
    try:
        logger.info("📝 Loading configuration...")
        config = Config()
        logger.info(f"✅ Config loaded. Admin IDs: {config.ADMIN_IDS}")
        
        logger.info("🗄️ Connecting to database...")
        db = Database(config)
        if not db.connected:
            logger.error("Failed to connect to database")
            sys.exit(1)
        logger.info("✅ Database connected")
        
        logger.info("🔄 Initializing handlers...")
        handlers = Handlers(config, db)
        logger.info("✅ Handlers initialized")
        
        logger.info("👑 Initializing admin handlers...")
        admin_handlers = AdminHandlers(config, db, None)
        logger.info("✅ Admin handlers initialized")
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("🌐 Starting Flask web server...")
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        time.sleep(3)
        logger.info(f"✅ Flask server running on port {os.environ.get('PORT', 10000)}")
        
        admin_handlers.bot = handlers.bot = None
        
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
            try:
                db.cleanup()
                logger.info("✅ Database cleanup complete")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
        bot_running = False
        logger.info("👋 Shutdown complete")


if __name__ == '__main__':
    main()
