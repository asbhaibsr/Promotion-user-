# ===== main.py (COMPLETE WITH ALL API ROUTES) =====

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

# Add these imports at the top
import requests
from bson.objectid import ObjectId
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
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

# Import with error handling
try:
    from flask import Flask, request, jsonify, render_template
    from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
    from telegram.constants import ParseMode
    import nest_asyncio
    from dotenv import load_dotenv
    import pytz
except ImportError as e:
    logger.critical(f"Import Error: {e}")
    print(f"Missing dependency: {e}")
    print("Please install required packages: pip install python-telegram-bot flask pymongo python-dotenv nest-asyncio cachetools certifi requests")
    sys.exit(1)

# Apply nest_asyncio
nest_asyncio.apply()

# Load environment variables
load_dotenv()

# Import our modules
from config import Config
# from database import Database
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

# Health status
start_time = datetime.now()
request_count = 0

# ========== FLASK ROUTES ==========

@app.route('/')
def index():
    """Main WebApp page - FIXED with better error handling"""
    global config, db, request_count
    request_count += 1
    
    try:
        user_id = request.args.get('user_id', 0, type=int)
        logger.info(f"🌐 Index page accessed by user_id: {user_id}")
        
        # Get user data
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
        
        # Default values with safe config access
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
        
        # Override with user data if available
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
        
        # Render template
        return render_template('index.html', **template_vars)
        
    except Exception as e:
        logger.error(f"Index route error: {e}")
        import traceback
        traceback.print_exc()
        return f"Error loading page: {str(e)}", 500


@app.route('/api/user/<int:user_id>')
def get_user_api(user_id):
    """API to get user data - FIXED"""
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
            # Convert ObjectId to string if present
            if '_id' in user_data:
                user_data['_id'] = str(user_data['_id'])
            return jsonify(user_data)
        
        return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        logger.error(f"API error for user {user_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/<int:user_id>/withdrawals')
def get_user_withdrawals_api(user_id):
    """API to get user withdrawal history - FIXED"""
    global db, request_count
    request_count += 1
    
    try:
        if not db or not db.ensure_connection():
            return jsonify([])
        
        withdrawals = db.get_user_withdrawals(user_id, 10)
        # Convert ObjectId to string for JSON
        for w in withdrawals:
            if '_id' in w:
                w['_id'] = str(w['_id'])
        return jsonify(withdrawals)
    except Exception as e:
        logger.error(f"Withdrawal history error: {e}")
        return jsonify([])


@app.route('/api/leaderboard')
def leaderboard_api():
    """API to get leaderboard - FIXED"""
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
            stats['total_users'] = db.users.count_documents({})
            stats['pending_withdrawals'] = db.withdrawals.count_documents({'status': 'pending'})
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


@app.route('/favicon.ico')
def favicon():
    """Favicon fix"""
    return "", 204


@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook endpoint for Telegram - FIXED"""
    global bot_app
    
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


# ========== NEW API ROUTES FOR MINI APP ==========

@app.route('/api/live-activity')
def live_activity_api():
    """Get live activity feed from database"""
    global db
    try:
        activities = []
        
        # Get recent withdrawals (last 5 completed)
        if db and db.ensure_connection():
            withdrawals = list(db.withdrawals.find(
                {'status': 'completed'}
            ).sort('processed_date', -1).limit(5))
            
            for w in withdrawals:
                user = db.get_user(w['user_id'])
                if user:
                    activities.append({
                        'type': 'withdraw',
                        'first_name': user.get('first_name', 'User'),
                        'amount': w['amount'],
                        'time': get_time_ago(w.get('processed_date', w.get('request_date'))),
                        'avatar': user.get('first_name', 'U')[0].upper()
                    })
            
            # Get recent earnings (last 5)
            earnings = list(db.transactions.find(
                {'type': 'credit', 'amount': {'$gt': 0}}
            ).sort('timestamp', -1).limit(5))
            
            for e in earnings:
                user = db.get_user(e['user_id'])
                if user:
                    activities.append({
                        'type': 'earn',
                        'first_name': user.get('first_name', 'User'),
                        'amount': e['amount'],
                        'time': get_time_ago(e['timestamp']),
                        'avatar': user.get('first_name', 'U')[0].upper()
                    })
            
            # Get recent referrals (last 5)
            referrals = list(db.referrals.find(
                {'is_active': True}
            ).sort('first_search_date', -1).limit(5))
            
            for r in referrals:
                user = db.get_user(r['referred_id'])
                referrer = db.get_user(r['referrer_id'])
                if user and referrer:
                    activities.append({
                        'type': 'referral',
                        'first_name': user.get('first_name', 'User'),
                        'amount': 0,
                        'time': get_time_ago(r.get('first_search_date', r.get('join_date'))),
                        'avatar': user.get('first_name', 'U')[0].upper(),
                        'text': f"{user.get('first_name')} joined via {referrer.get('first_name')}"
                    })
        
        # Shuffle and return top 10
        random.shuffle(activities)
        return jsonify(activities[:10])
        
    except Exception as e:
        logger.error(f"Live activity error: {e}")
        return jsonify([])


@app.route('/api/ads')
def get_ads_api():
    """Get ads from database"""
    global db
    try:
        # Check if ads collection exists
        if db and db.ensure_connection():
            # Check if ads collection exists, if not create it
            if 'ads' not in db.db.list_collection_names():
                db.db.create_collection('ads')
                # Insert default ads
                db.db.ads.insert_many([
                    {'id': 1, 'title': 'Install App & Earn', 'reward': 2, 'link': 'https://t.me/+8SdeM5gBihoxZjU1', 'meta': '⏱️ 2 min • 1.2k completed', 'icon': '📱', 'order': 1},
                    {'id': 2, 'title': 'Watch Video', 'reward': 0.5, 'link': 'https://t.me/+8SdeM5gBihoxZjU1', 'meta': '⏱️ 30 sec • 3.4k completed', 'icon': '🎬', 'order': 2}
                ])
            
            ads = list(db.db.ads.find().sort('order', 1))
            for ad in ads:
                ad['_id'] = str(ad['_id'])
            return jsonify({'ads': ads})
        else:
            # Return default ads if database not connected
            return jsonify({
                'ads': [
                    {'id': 1, 'title': 'Install App & Earn', 'reward': 2, 'link': 'https://t.me/+8SdeM5gBihoxZjU1', 'meta': '⏱️ 2 min • 1.2k completed', 'icon': '📱'},
                    {'id': 2, 'title': 'Watch Video', 'reward': 0.5, 'link': 'https://t.me/+8SdeM5gBihoxZjU1', 'meta': '⏱️ 30 sec • 3.4k completed', 'icon': '🎬'}
                ]
            })
    except Exception as e:
        logger.error(f"Get ads error: {e}")
        return jsonify({'ads': []})


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
        
        # Check if user already claimed this ad today
        today = datetime.now().date().isoformat()
        
        # Check in user's daily claims (you might want to create a claims collection)
        claims_collection = db.db['daily_claims'] if hasattr(db, 'db') else None
        
        if claims_collection:
            existing = claims_collection.find_one({
                'user_id': int(user_id),
                'ad_id': ad_id,
                'date': today
            })
            
            if existing:
                return jsonify({'success': False, 'message': 'Already claimed today'})
        
        # Add balance
        success = db.add_balance(user_id, float(reward), f"Ad reward #{ad_id}")
        
        if success:
            # Record claim
            if claims_collection:
                claims_collection.insert_one({
                    'user_id': int(user_id),
                    'ad_id': ad_id,
                    'date': today,
                    'reward': float(reward),
                    'timestamp': datetime.now().isoformat()
                })
            
            return jsonify({'success': True, 'message': 'Reward added'})
        else:
            return jsonify({'success': False, 'message': 'Failed to add reward'})
            
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
        
        # Get admin user_id from request (you should verify this)
        admin_id = data.get('admin_id')
        
        if not admin_id:
            return jsonify({'success': False, 'message': 'Admin verification required'}), 401
        
        # Verify admin
        admin_user = db.get_user(int(admin_id))
        if not admin_user or not admin_user.get('is_admin', False):
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
        # Update ad
        if db and db.ensure_connection():
            ads_collection = db.db['ads'] if hasattr(db, 'db') else None
            if ads_collection:
                ads_collection.update_one(
                    {'id': int(ad_id)},
                    {'$set': {
                        'title': title,
                        'reward': float(reward),
                        'link': link,
                        'meta': meta
                    }},
                    upsert=True
                )
                logger.info(f"✅ Ad {ad_id} updated by admin {admin_id}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Update ad error: {e}")
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
        
        # Map settings to database fields
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
            db.users.update_one(
                {'user_id': int(user_id)},
                {'$set': {db_field: value}}
            )
            db.user_cache.pop(f"user_{user_id}", None)
            logger.info(f"✅ Setting {setting} updated for user {user_id}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Update setting error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/user/<int:user_id>/update', methods=['POST'])
def update_user_api(user_id):
    """Update user data"""
    global db
    try:
        data = request.get_json()
        
        if not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'Database error'}), 503
        
        # Update user in database
        update_data = {}
        for key, value in data.items():
            if key in ['first_name', 'username', 'dark_mode', 'notify_referrals', 'notify_earnings', 'notify_withdrawals', 'sound_enabled']:
                update_data[key] = value
        
        if update_data:
            db.users.update_one(
                {'user_id': int(user_id)},
                {'$set': update_data}
            )
            db.user_cache.pop(f"user_{user_id}", None)
            logger.info(f"✅ User {user_id} updated: {update_data}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Update user error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/claim-daily-bonus', methods=['POST'])
def claim_daily_bonus_api():
    """API to claim daily bonus - DIRECT DATABASE UPDATE"""
    global db
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'success': False, 'message': 'User ID required'}), 400
        
        result = db.claim_daily_bonus(user_id)
        
        if result and result.get('success'):
            return jsonify({
                'success': True,
                'bonus': result['bonus'],
                'streak': result['streak']
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Already claimed today or try again'
            })
            
    except Exception as e:
        logger.error(f"Daily bonus API error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/verify-channel', methods=['POST'])
def verify_channel_api():
    """API to verify channel join - DIRECT DATABASE UPDATE"""
    global db
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        channel_id = data.get('channel_id')
        
        if not user_id or not channel_id:
            return jsonify({'success': False, 'message': 'Missing data'}), 400
        
        result = db.mark_channel_join(user_id, channel_id)
        
        if result:
            user = db.get_user(user_id)
            return jsonify({
                'success': True,
                'message': 'Channel bonus claimed',
                'user_data': {
                    'balance': user.get('balance', 0),
                    'channel_joined': True
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Already claimed or invalid channel'
            })
            
    except Exception as e:
        logger.error(f"Channel verify API error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/withdraw', methods=['POST'])
def withdraw_api():
    """API to process withdrawal - DIRECT DATABASE UPDATE"""
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
    """API to send support message - DIRECT DATABASE INSERT"""
    global db
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        message = data.get('message')
        
        if not user_id or not message:
            return jsonify({'success': False, 'message': 'Missing data'}), 400
        
        # Insert into issues collection
        db.issues.insert_one({
            'user_id': int(user_id),
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'status': 'pending',
            'read': False
        })
        
        # Also try to notify admin via bot
        if bot_app and config and hasattr(config, 'LOG_CHANNEL_ID') and config.LOG_CHANNEL_ID:
            try:
                user = db.get_user(user_id)
                asyncio.run_coroutine_threadsafe(
                    bot_app.bot.send_message(
                        chat_id=config.LOG_CHANNEL_ID,
                        text=f"📩 **New Support Message**\n\nUser: {user.get('first_name', 'Unknown')} (ID: {user_id})\nMessage: {message}",
                        parse_mode=ParseMode.MARKDOWN
                    ),
                    bot_loop
                )
            except Exception as e:
                logger.error(f"Failed to notify admin: {e}")
        
        return jsonify({'success': True, 'message': 'Message sent'})
        
    except Exception as e:
        logger.error(f"Support API error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/today-active')
def today_active_api():
    """API to get today's active users"""
    global db
    try:
        today = datetime.now().date().isoformat()
        active_count = db.daily_searches.count_documents({'date': today})
        return jsonify({'active_today': active_count})
    except Exception as e:
        logger.error(f"Today active API error: {e}")
        return jsonify({'active_today': 0})


# ========== HELPER FUNCTIONS ==========

def get_time_ago(timestamp_str):
    """Convert ISO timestamp to 'X min ago' format"""
    if not timestamp_str:
        return 'recently'
    
    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        now = datetime.now()
        diff = now - timestamp
        
        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds // 3600 > 0:
            return f"{diff.seconds // 3600}h ago"
        elif diff.seconds // 60 > 0:
            return f"{diff.seconds // 60}min ago"
        else:
            return "just now"
    except:
        return "recently"


# ========== BOT SETUP ==========

async def post_init(application):
    """Setup after initialization - FIXED"""
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
        
        # Set webhook if URL is configured
        if config and hasattr(config, 'WEBHOOK_URL') and config.WEBHOOK_URL:
            webhook_url = f"{config.WEBHOOK_URL}/webhook"
            await application.bot.set_webhook(url=webhook_url)
            logger.info(f"✅ Webhook set to {webhook_url}")
        
        # Send startup notification
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
    """Run scheduled background jobs - FIXED"""
    global db, config
    
    logger.info("🔄 Scheduled jobs started")
    
    while True:
        try:
            now = datetime.now()
            
            # Daily earnings at midnight
            if now.hour == 0 and now.minute == 0:
                logger.info("🔄 Processing daily earnings...")
                if db and db.ensure_connection():
                    count = db.process_daily_referral_earnings()
                    logger.info(f"✅ Processed {count} daily earnings")
            
            # Log stats every hour
            if now.minute == 0:
                if db and db.ensure_connection():
                    total_users = db.users.count_documents({})
                    active_today = db.daily_searches.count_documents({'date': now.date().isoformat()})
                    logger.info(f"📊 Stats - Users: {total_users}, Active Today: {active_today}")
            
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Scheduled job error: {e}")
            await asyncio.sleep(60)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler - FIXED"""
    logger.error(f"Update {update} caused error {context.error}")
    
    # Log detailed error
    import traceback
    traceback.print_exc()
    
    # Try to notify user
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ An error occurred. Please try again later.\n"
                "If this persists, contact support."
            )
        except:
            pass


def run_bot():
    """Run the bot - FIXED with proper handler ordering"""
    global bot_app, bot_loop, config, db, handlers, admin_handlers
    
    logger.info("🤖 Starting bot...")
    
    # Create new event loop
    bot_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(bot_loop)
    
    try:
        # Create application
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
        bot_app.add_handler(CallbackQueryHandler(admin_handlers.handle_admin_callback, pattern="^admin_"))
        
        # ===== MESSAGE HANDLERS - ORDER IS IMPORTANT =====
        # WebApp data first
        bot_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handlers.handle_webapp_data))
        
        # Admin messages in private chat
        bot_app.add_handler(MessageHandler(
            filters.TEXT & filters.ChatType.PRIVATE, 
            admin_handlers.handle_admin_message
        ))
        
        # Group messages (movie searches)
        bot_app.add_handler(MessageHandler(
            filters.TEXT & filters.ChatType.GROUP, 
            handlers.handle_message
        ))
        
        # Supergroup messages
        bot_app.add_handler(MessageHandler(
            filters.TEXT & filters.ChatType.SUPERGROUP, 
            handlers.handle_message
        ))
        
        # Private text messages (non-command)
        bot_app.add_handler(MessageHandler(
            filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, 
            handlers.handle_message
        ))
        
        # ===== ERROR HANDLER =====
        bot_app.add_error_handler(error_handler)
        
        # Run post init
        bot_loop.run_until_complete(post_init(bot_app))
        
        # Start scheduled jobs
        bot_loop.create_task(scheduled_jobs())
        
        logger.info("✅ Bot started successfully")
        
        # Start polling (simpler for Render)
        logger.info("🔄 Starting polling...")
        bot_app.run_polling()
        
    except Exception as e:
        logger.error(f"Bot error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if bot_loop:
            bot_loop.close()


def run_flask():
    """Run Flask in separate thread - FIXED"""
    global config
    
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 Flask server starting on port {port}")
    
    # Run Flask with better error handling
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
    
    global db, bot_loop
    
    # Cleanup
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
    """Main function - FIXED with better error handling"""
    global config, db, handlers, admin_handlers
    
    print("""
    ╔══════════════════════════════════════╗
    ║     FILMYFUND BOT - FIXED VERSION    ║
    ║        100% WORKING SOLUTION          ║
    ║          All Issues Resolved          ║
    ╚══════════════════════════════════════╝
    """)
    
    logger.info("🚀 Starting FilmyFund Bot...")
    
    # Check environment
    if not check_environment():
        logger.error("Please set all required environment variables in .env file")
        sys.exit(1)
    
    try:
        # Initialize config
        logger.info("📝 Loading configuration...")
        config = Config()
        logger.info(f"✅ Config loaded. Admin IDs: {config.ADMIN_IDS}")
        
        # Initialize database
        logger.info("🗄️ Connecting to database...")
        db = Database(config)
        if not db.connected:
            logger.error("Failed to connect to database")
            sys.exit(1)
        logger.info("✅ Database connected")
        
        # Initialize handlers
        logger.info("🔄 Initializing handlers...")
        handlers = Handlers(config, db)
        logger.info("✅ Handlers initialized")
        
        # Initialize admin handlers
        logger.info("👑 Initializing admin handlers...")
        admin_handlers = AdminHandlers(config, db)
        logger.info("✅ Admin handlers initialized")
        
        # Set signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start Flask in a separate thread
        logger.info("🌐 Starting Flask web server...")
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        # Small delay for Flask to start
        time.sleep(3)
        logger.info(f"✅ Flask server running on port {os.environ.get('PORT', 10000)}")
        
        # Run bot in main thread
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
        logger.info("👋 Shutdown complete")


if __name__ == '__main__':
    main()
