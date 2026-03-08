# ===== main.py (COMPLETE FIXED VERSION - ALL APIs WORKING) =====

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
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

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

start_time = datetime.now()
request_count = 0

# ========== CORS HELPER ==========
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

@app.after_request
def after_request(response):
    return add_cors_headers(response)

@app.route('/', methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path=''):
    response = jsonify({'status': 'ok'})
    return add_cors_headers(response)

# ========== MAIN PAGE ==========

@app.route('/')
def index():
    global config, db, request_count
    request_count += 1

    try:
        user_id = request.args.get('user_id', 0, type=int)
        logger.info(f"Index page accessed by user_id: {user_id}")

        user_data = None
        if user_id and user_id > 0 and db and db.ensure_connection():
            try:
                user_data = db.get_user(user_id)
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


# ========== USER APIs ==========

@app.route('/api/user/<int:user_id>')
def get_user_api(user_id):
    global db, request_count
    request_count += 1
    try:
        if user_id == 0:
            return jsonify({
                'user_id': 0, 'first_name': 'Guest', 'balance': 0,
                'total_earned': 0, 'tier': 1, 'tier_name': '🥉 BASIC',
                'total_refs': 0, 'active_refs': 0, 'pending_refs': 0,
                'daily_streak': 0, 'channel_joined': False, 'is_admin': False,
                'dark_mode': False, 'notify_referrals': True,
                'notify_earnings': True, 'notify_withdrawals': True,
                'games_won': 0, 'today_game_earned': 0
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
    try:
        if not db or not db.ensure_connection():
            return jsonify({'claimed_ads': []})
        today = datetime.now().date().isoformat()
        claimed = db.get_user_claimed_ads(user_id, today)
        return jsonify({'claimed_ads': [{'ad_id': ad, 'date': today} for ad in claimed]})
    except Exception as e:
        logger.error(f"Claimed ads error: {e}")
        return jsonify({'claimed_ads': []})


# ========== LEADERBOARD & ACTIVITY ==========

@app.route('/api/leaderboard')
def leaderboard_api():
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


# ========== ADS APIs ==========

@app.route('/api/ads')
def get_ads_api():
    global db
    try:
        if db and db.ensure_connection():
            ads = db.get_all_ads()
            return jsonify({'ads': ads})
        else:
            return jsonify({
                'ads': [
                    {'id': 1, 'title': 'Install App & Earn', 'reward': 2.0,
                     'link': 'https://t.me/+8SdeM5gBihoxZjU1',
                     'meta': '⏱️ 2 min • 1.2k completed', 'icon': '📱'},
                    {'id': 2, 'title': 'Watch Video', 'reward': 0.5,
                     'link': 'https://t.me/+8SdeM5gBihoxZjU1',
                     'meta': '⏱️ 30 sec • 3.4k completed', 'icon': '🎬'}
                ]
            })
    except Exception as e:
        logger.error(f"Get ads error: {e}")
        return jsonify({'ads': []})


@app.route('/api/claim-ad', methods=['POST'])
def claim_ad_api():
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


# ========== BONUS & MISSIONS ==========

@app.route('/api/claim-day-bonus', methods=['POST'])
def claim_day_bonus_api():
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
            return jsonify({'success': False, 'message': 'Already claimed or invalid date'})
    except Exception as e:
        logger.error(f"Claim day bonus error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/update-mission', methods=['POST'])
def update_mission_api():
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


# ========== WITHDRAWAL ==========

@app.route('/api/withdraw', methods=['POST'])
def withdraw_api():
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


# ========== SUPPORT ==========

@app.route('/api/support', methods=['POST'])
def support_api():
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
                        keyboard = [[InlineKeyboardButton(
                            "📩 VIEW MESSAGE",
                            callback_data=f"view_support_{msg_id}"
                        )]]
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


# ========== SETTINGS ==========

@app.route('/api/update-setting', methods=['POST'])
def update_setting_api():
    global db
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        setting = data.get('setting')
        value = data.get('value')

        if not all([user_id, setting]):
            return jsonify({'success': False, 'message': 'Missing data'}), 400

        if db and db.ensure_connection():
            db.update_notification_setting(user_id, setting, value)

        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Update setting error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ============================================================
# ========== GAME APIs (NEW - MAIN FIX) ==========
# ============================================================

@app.route('/api/game/state/<int:user_id>')
def get_game_state(user_id):
    """Get user's game state for today"""
    global db
    try:
        if not db or not db.ensure_connection():
            return jsonify({'error': 'Database not connected'}), 503

        today = datetime.now().date().isoformat()
        game_state = db.get_game_state(user_id, today)
        return jsonify(game_state)
    except Exception as e:
        logger.error(f"Get game state error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/game/spin', methods=['POST'])
def game_spin_api():
    """Process spin wheel game"""
    global db
    try:
        data = request.get_json()
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({'success': False, 'message': 'Missing user_id'}), 400

        if not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'Database error'}), 503

        result = db.process_game_spin(user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Spin game error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/game/guess', methods=['POST'])
def game_guess_api():
    """Process number guess game"""
    global db
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        guess = data.get('guess')
        bet = data.get('bet', 1)

        if not user_id or guess is None:
            return jsonify({'success': False, 'message': 'Missing data'}), 400

        if not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'Database error'}), 503

        result = db.process_game_guess(user_id, int(guess), float(bet))
        return jsonify(result)
    except Exception as e:
        logger.error(f"Guess game error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/game/coin', methods=['POST'])
def game_coin_api():
    """Process coin flip game"""
    global db
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        choice = data.get('choice')  # 'heads' or 'tails'
        bet = data.get('bet', 1)

        if not user_id or not choice:
            return jsonify({'success': False, 'message': 'Missing data'}), 400

        if not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'Database error'}), 503

        result = db.process_game_coin(user_id, choice, float(bet))
        return jsonify(result)
    except Exception as e:
        logger.error(f"Coin game error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/game/scratch', methods=['POST'])
def game_scratch_api():
    """Process scratch card game"""
    global db
    try:
        data = request.get_json()
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({'success': False, 'message': 'Missing user_id'}), 400

        if not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'Database error'}), 503

        result = db.process_game_scratch(user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Scratch game error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/game/earn', methods=['POST'])
def game_earn_api():
    """Add game earnings to user balance"""
    global db
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        amount = data.get('amount')
        game_type = data.get('game_type', 'game')
        description = data.get('description', 'Game reward')

        if not user_id or amount is None:
            return jsonify({'success': False, 'message': 'Missing data'}), 400

        if not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'Database error'}), 503

        result = db.add_game_earning(user_id, float(amount), game_type, description)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Game earn error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/game/deduct', methods=['POST'])
def game_deduct_api():
    """Deduct game bet from user balance"""
    global db
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        amount = data.get('amount')
        game_type = data.get('game_type', 'game')

        if not user_id or amount is None:
            return jsonify({'success': False, 'message': 'Missing data'}), 400

        if not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'Database error'}), 503

        result = db.deduct_game_balance(user_id, float(amount), game_type)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Game deduct error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ========== STATS & HEALTH ==========

@app.route('/api/stats')
def stats_api():
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
    global config
    logger.info("Running post-initialization setup...")
    try:
        commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("app", "Open Mini App"),
            BotCommand("balance", "Check balance"),
            BotCommand("referrals", "My referrals"),
            BotCommand("withdraw", "Withdraw earnings"),
            BotCommand("admin", "Admin Panel"),
            BotCommand("help", "Help")
        ]
        await application.bot.set_my_commands(commands)

        if config and hasattr(config, 'WEBHOOK_URL') and config.WEBHOOK_URL:
            webhook_url = f"{config.WEBHOOK_URL}/webhook"
            await application.bot.set_webhook(url=webhook_url)
            logger.info(f"Webhook set to {webhook_url}")

        if config and hasattr(config, 'LOG_CHANNEL_ID') and config.LOG_CHANNEL_ID:
            try:
                await application.bot.send_message(
                    chat_id=config.LOG_CHANNEL_ID,
                    text=f"Bot Started! Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Log channel error: {e}")

        logger.info("Bot initialization complete")
    except Exception as e:
        logger.error(f"Post-init error: {e}")


async def scheduled_jobs():
    global db, config
    logger.info("Scheduled jobs started")
    while True:
        try:
            now = datetime.now()
            if now.hour == 0 and now.minute == 0:
                if db and db.ensure_connection():
                    count = db.process_daily_referral_earnings()
                    logger.info(f"Processed {count} daily earnings")
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Scheduled job error: {e}")
            await asyncio.sleep(60)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    import traceback
    traceback.print_exc()
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "An error occurred. Please try again later."
            )
        except:
            pass


def run_bot():
    global bot_app, bot_loop, config, db, handlers, admin_handlers, bot_running
    logger.info("Starting bot...")

    if bot_running:
        logger.warning("Bot is already running, skipping...")
        return

    bot_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(bot_loop)

    try:
        bot_app = Application.builder().token(config.BOT_TOKEN).build()

        bot_app.add_handler(CommandHandler("start", handlers.start))
        bot_app.add_handler(CommandHandler("app", handlers.open_app))
        bot_app.add_handler(CommandHandler("balance", handlers.check_balance))
        bot_app.add_handler(CommandHandler("referrals", handlers.show_referrals))
        bot_app.add_handler(CommandHandler("withdraw", handlers.withdraw_cmd))
        bot_app.add_handler(CommandHandler("help", handlers.help_cmd))
        bot_app.add_handler(CommandHandler("admin", admin_handlers.admin_panel))

        bot_app.add_handler(CallbackQueryHandler(admin_handlers.handle_admin_callback))

        bot_app.add_handler(MessageHandler(
            filters.StatusUpdate.WEB_APP_DATA, handlers.handle_webapp_data
        ))
        bot_app.add_handler(MessageHandler(
            filters.TEXT & filters.ChatType.PRIVATE, admin_handlers.handle_admin_message
        ))
        bot_app.add_handler(MessageHandler(
            filters.TEXT & filters.ChatType.GROUP, handlers.handle_message
        ))
        bot_app.add_handler(MessageHandler(
            filters.TEXT & filters.ChatType.SUPERGROUP, handlers.handle_message
        ))
        bot_app.add_handler(MessageHandler(
            filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, handlers.handle_message
        ))

        bot_app.add_error_handler(error_handler)

        bot_loop.run_until_complete(post_init(bot_app))
        bot_loop.create_task(scheduled_jobs())

        logger.info("Bot started successfully")
        bot_running = True
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
    global config
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"Flask server starting on port {port}")
    try:
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)
    except Exception as e:
        logger.error(f"Flask error: {e}")
        sys.exit(1)


def signal_handler(sig, frame):
    logger.info("Shutting down...")
    global db, bot_loop, bot_running
    if db:
        try:
            db.cleanup()
        except Exception as e:
            logger.error(f"Error closing database: {e}")
    if bot_loop:
        try:
            bot_loop.stop()
        except:
            pass
    bot_running = False
    sys.exit(0)


def check_environment():
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
    global config, db, handlers, admin_handlers, bot_running

    print("""
    ╔══════════════════════════════════════╗
    ║     FILMYFUND BOT - FIXED VERSION    ║
    ║    ALL APIs + GAME APIs WORKING      ║
    ╚══════════════════════════════════════╝
    """)

    logger.info("Starting FilmyFund Bot...")

    if not check_environment():
        logger.error("Please set all required environment variables in .env file")
        sys.exit(1)

    try:
        config = Config()
        logger.info(f"Config loaded. Admin IDs: {config.ADMIN_IDS}")

        db = Database(config)
        if not db.connected:
            logger.error("Failed to connect to database")
            sys.exit(1)
        logger.info("Database connected")

        handlers = Handlers(config, db)
        logger.info("Handlers initialized")

        admin_handlers = AdminHandlers(config, db, None)
        logger.info("Admin handlers initialized")

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()

        time.sleep(3)
        logger.info(f"Flask server running on port {os.environ.get('PORT', 10000)}")

        admin_handlers.bot = handlers.bot = None

        run_bot()

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if db:
            try:
                db.cleanup()
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
        bot_running = False
        logger.info("Shutdown complete")


if __name__ == '__main__':
    main()
