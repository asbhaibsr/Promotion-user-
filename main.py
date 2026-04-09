# ═══════════════════════════════════════════════════════════
# EarnZone / FilmyFund — Telegram Mini App
# Owner   : @asbhaibsr
# Channel : @asbhai_bsr
# Contact : https://t.me/asbhaibsr
# ⚠️  Unauthorized modification or redistribution prohibited.
# © 2025 @asbhaibsr — All Rights Reserved
# ═══════════════════════════════════════════════════════════

# ===== main.py (FULLY UPDATED - ALL NEW ROUTES) =====

import logging
import os
import sys
import asyncio
import threading
import time
import signal
from datetime import datetime, timedelta

from bson.objectid import ObjectId
from flask import Flask, request, jsonify, render_template, make_response
from functools import wraps

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
    from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Application, CommandHandler, MessageHandler,
        filters, ContextTypes, CallbackQueryHandler
    )
    from telegram.constants import ParseMode
    import nest_asyncio
    from dotenv import load_dotenv
except ImportError as e:
    logger.critical(f"Import Error: {e}")
    sys.exit(1)

nest_asyncio.apply()
load_dotenv()

from config import Config
from database import Database
from handlers import Handlers
from admin import AdminHandlers

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'filmyfund-secret-key-2024')

config = None
db = None
handlers = None
admin_handlers = None
bot_app = None
bot_loop = None
bot_running = False

start_time = datetime.now()
request_count = 0

LOG_CHANNEL_ID = -1002352329534  # Log channel ID — yahan bot messages padhta hai

# ========== CORS ==========

def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

@app.after_request
def after_request(response):
    response = add_cors_headers(response)
    # Log slow/error responses for Render dashboard
    if response.status_code >= 400:
        logger.warning(f"[{response.status_code}] {request.method} {request.path}")
    return response

@app.route('/', methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path=''):
    return add_cors_headers(jsonify({'status': 'ok'}))

# ========== MAIN PAGE ==========

@app.route('/api/health')
def health_check():
    """Health check — also warms up DB connection"""
    try:
        if db and db.ensure_connection():
            return jsonify({'status':'ok','db':'connected'})
        return jsonify({'status':'ok','db':'warming'})
    except:
        return jsonify({'status':'ok'})

@app.route('/')
def index():
    global config, db, request_count
    request_count += 1
    try:
        user_id = request.args.get('user_id', 0, type=int)
        user_data = None
        if user_id and user_id > 0 and db and db.ensure_connection():
            try:
                # FIXED: Cache clear nahi karo on index — bas cached data return karo
                # Ye hang issue fix karta hai (baar baar DB hit nahi hogi)
                user_data = db.get_user(user_id)
            except Exception as e:
                logger.error(f"Error fetching user {user_id}: {e}")
                user_data = None

        template_vars = {
            'user_id': user_id if user_id else 0, 'user_name': 'Guest', 'balance': 0,
            'total_earned': 0, 'tier': 1, 'tier_name': '🥉 BASIC', 'tier_rate': 0.30,
            'total_refs': 0, 'active_refs': 0, 'pending_refs': 0, 'daily_streak': 0,
            'channel_joined': False,
            'min_withdrawal': config.MIN_WITHDRAWAL if config else 20,
            'channel_id': config.CHANNEL_ID if config else '',
            'channel_link': config.CHANNEL_LINK if config else '',
            'channel_bonus': config.CHANNEL_JOIN_BONUS if config else 2.0,
            'movie_group_link': config.MOVIE_GROUP_LINK if config else '',
            'bot_username': config.BOT_USERNAME if config else '',
            'daily_referral_earning': config.DAILY_REFERRAL_EARNING if config else 0.10,
            'support_username': config.SUPPORT_USERNAME if config else '@support',
            # FIXED: webapp_url inject karo — frontend 404 fix
            'webapp_url': config.WEBAPP_URL if config and config.WEBAPP_URL else ''
        }

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

        response = make_response(render_template('index.html', **template_vars))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        return response
    except Exception as e:
        logger.error(f"Index route error: {e}")
        import traceback; traceback.print_exc()
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
                'total_earned': 0, 'today_earned': 0, 'tier': 1, 'total_refs': 0,
                'active_refs': 0, 'pending_refs': 0, 'daily_streak': 0,
                'channel_joined': False, 'is_admin': False, 'games_won': 0,
                'passes': 0, 'month_active_refs': 0
            })
        if not db or not db.ensure_connection():
            return jsonify({'error': 'Database not connected'}), 503
        user_data = db.get_user(user_id)
        if user_data:
            if '_id' in user_data:
                user_data['_id'] = str(user_data['_id'])
            # Auto-reset today_earned if new day
            today = datetime.now().date().isoformat()
            if user_data.get('today_date') != today:
                user_data['today_earned'] = 0.0
                db.users.update_one(
                    {'user_id': user_id},
                    {'$set': {'today_earned': 0.0, 'today_date': today}}
                )
                db.user_cache.pop(f"user_{user_id}", None)
            # Include month_active_refs in main user call
            user_data['month_active_refs'] = db.get_month_active_refs(user_id)
            # Check if user has past withdrawals (for 5 vs 20 ref rule)
            past_wd = db.withdrawals.count_documents({
                'user_id': user_id,
                'status': {'$in': ['completed', 'pending']}
            })
            user_data['has_past_withdrawals'] = past_wd > 0
            # Ensure today_earned field exists
            if 'today_earned' not in user_data:
                user_data['today_earned'] = 0.0
            # Build claimed_milestones list from individual fields
            claimed_milestones = []
            for m in [5, 10, 25, 50, 100]:
                if user_data.get(f'milestone_claimed_{m}'):
                    claimed_milestones.append(m)
            user_data['claimed_milestones'] = claimed_milestones
            # Add weekly bonus claimed status for frontend
            today_date = datetime.now().date()
            day_of_week = today_date.weekday()
            week_start = today_date - timedelta(days=day_of_week)
            user_data['weekly_bonus_claimed'] = bool(user_data.get(f'weekly_bonus_{week_start.isoformat()}', False))
            return jsonify(user_data)
        return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        logger.error(f"API error for user {user_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/<int:user_id>/withdrawals')
def get_user_withdrawals_api(user_id):
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
def get_user_missions_api(user_id):
    try:
        if not db or not db.ensure_connection():
            return jsonify({})
        missions = db.get_user_missions(user_id)
        return jsonify(missions)
    except Exception as e:
        logger.error(f"Missions error: {e}")
        return jsonify({})

@app.route('/api/user/<int:user_id>/ref-activity')
def get_ref_activity_api(user_id):
    try:
        if not db or not db.ensure_connection():
            return jsonify([])
        activity = db.get_ref_activity(user_id, 20)
        return jsonify(activity)
    except Exception as e:
        logger.error(f"Ref activity error: {e}")
        return jsonify([])

@app.route('/api/user/<int:user_id>/claimed-ads')
def get_user_claimed_ads(user_id):
    try:
        if not db or not db.ensure_connection():
            return jsonify({'claimed_ads': []})
        claimed = db.get_user_claimed_ads(user_id)
        return jsonify({'claimed_ads': [{'ad_id': ad} for ad in claimed]})
    except Exception as e:
        logger.error(f"Claimed ads error: {e}")
        return jsonify({'claimed_ads': []})

# ========== NEW: MONTH ACTIVE REFS API ==========

@app.route('/api/user/<int:user_id>/month-refs')
def get_month_refs_api(user_id):
    """
    Returns how many referrals this user activated THIS calendar month.
    Used by frontend to check withdrawal condition (need 20).
    """
    try:
        if not db or not db.ensure_connection():
            return jsonify({'month_active_refs': 0})
        count = db.get_month_active_refs(user_id)
        return jsonify({'month_active_refs': count})
    except Exception as e:
        logger.error(f"Month refs error: {e}")
        return jsonify({'month_active_refs': 0})

# ========== LEADERBOARD & ACTIVITY ==========

@app.route('/api/leaderboard')
def leaderboard_api():
    try:
        if not db or not db.ensure_connection():
            return jsonify([])
        mode = request.args.get('mode', 'weekly')
        leaderboard = db.get_leaderboard(20, mode=mode)
        return jsonify(leaderboard)
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        return jsonify([])

@app.route('/api/top-earners-today')
def top_earners_today_api():
    """Top 10 users by today_earned — for games page leaderboard"""
    try:
        if not db or not db.ensure_connection():
            return jsonify([])
        today = datetime.now().date().isoformat()
        # Get top 10 users by today_earned
        top = list(db.users.find(
            {'today_date': today, 'today_earned': {'$gt': 0}},
            {'user_id': 1, 'first_name': 1, 'today_earned': 1, '_id': 0}
        ).sort('today_earned', -1).limit(10))
        result = []
        for i, u in enumerate(top):
            result.append({
                'rank': i + 1,
                'name': u.get('first_name', 'User')[:15],
                'user_id': u.get('user_id', 0),
                'today_earned': round(u.get('today_earned', 0), 2),
                'pts': int(u.get('today_earned', 0) * 100)
            })
        return jsonify(result)
    except Exception as e:
        logger.error(f"Top earners today error: {e}")
        return jsonify([])

@app.route('/api/live-activity')
def live_activity_api():
    try:
        if not db:
            return jsonify([])
        activities = db.get_live_activity(20)
        return jsonify(activities or [])
    except Exception as e:
        logger.warning(f"Live activity: {e}")
        return jsonify([])

# ========== ADS APIs ==========

@app.route('/api/ads')
def get_ads_api():
    try:
        if db and db.ensure_connection():
            ads = db.get_all_ads()
            return jsonify({'ads': ads})
        return jsonify({'ads': []})
    except Exception as e:
        logger.error(f"Get ads error: {e}")
        return jsonify({'ads': []})

@app.route('/api/claim-ad', methods=['POST'])
def claim_ad_api():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        ad_id = data.get('ad_id')
        reward = data.get('reward')
        if not all([user_id, ad_id is not None, reward]):
            return jsonify({'success': False, 'message': 'Missing data'}), 400
        success = db.claim_ad(user_id, ad_id, reward)
        if success:
            return jsonify({'success': True, 'message': 'Reward added! +1 Pass bhi mila!'})
        return jsonify({'success': False, 'message': 'Already claimed! Admin edit hone ke baad hi dubara claim hoga.'})
    except Exception as e:
        logger.error(f"Claim ad error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/update-ad', methods=['POST'])
def update_ad_api():
    """UPDATED: now saves timer_seconds field too."""
    try:
        data = request.get_json()
        ad_id = data.get('ad_id')
        admin_id = data.get('admin_id')
        if not admin_id:
            return jsonify({'success': False, 'message': 'Admin required'}), 401
        admin_user = db.get_user(int(admin_id))
        if not admin_user or not admin_user.get('is_admin', False):
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        # UPDATED: pass timer_seconds, description, image_url, pass_reward
        timer_seconds = int(data.get('timer_seconds', 0) or 0)
        pass_reward = int(data.get('pass_reward', 0) or 0)
        success = db.update_ad(
            ad_id,
            data.get('title'),
            data.get('reward'),
            data.get('link'),
            data.get('meta'),
            data.get('icon'),
            claim_code=data.get('claim_code'),
            timer_seconds=timer_seconds,
            description=data.get('description', ''),
            image_url=data.get('image_url', ''),
            pass_reward=pass_reward
        )
        if success:
            return jsonify({'success': True, 'message': 'Ad updated! All claims reset.'})
        return jsonify({'success': False, 'message': 'Failed to update'})
    except Exception as e:
        logger.error(f"Update ad error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/delete-ad', methods=['POST'])
def delete_ad_api():
    try:
        data = request.get_json()
        ad_id = data.get('ad_id')
        admin_id = data.get('admin_id')
        if not admin_id:
            return jsonify({'success': False, 'message': 'Admin required'}), 401
        admin_user = db.get_user(int(admin_id))
        if not admin_user or not admin_user.get('is_admin', False):
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        success = db.delete_ad(ad_id)
        if success:
            return jsonify({'success': True, 'message': 'Ad deleted'})
        return jsonify({'success': False, 'message': 'Ad not found'})
    except Exception as e:
        logger.error(f"Delete ad error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/reset-ad-claims', methods=['POST'])
def reset_ad_claims_api():
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
                'streak': result['streak'],
                'passes_added': result.get('passes_added', 1)
            })
        return jsonify({'success': False, 'message': 'Already claimed or invalid date'})
    except Exception as e:
        logger.error(f"Claim day bonus error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/claim-single-mission', methods=['POST'])
def claim_single_mission_api():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        mission_id = data.get('mission_id')
        reward = data.get('reward')
        if not user_id or not mission_id or reward is None:
            return jsonify({'success': False, 'message': 'Missing data'}), 400
        result = db.claim_single_mission(user_id, mission_id, reward)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Claim single mission error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/claim-milestone', methods=['POST'])
def claim_milestone_api():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        refs_required = data.get('refs_required')
        reward = data.get('reward')
        if not user_id or refs_required is None:
            return jsonify({'success': False, 'message': 'Missing data'}), 400
        result = db.claim_milestone(user_id, refs_required, reward)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Milestone claim API error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/claim-badge', methods=['POST'])
def claim_badge_api():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        badge_idx = data.get('badge_idx')
        if user_id is None or badge_idx is None:
            return jsonify({'success': False, 'message': 'Missing data'}), 400
        if not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'DB error'}), 503
        result = db.claim_badge(int(user_id), int(badge_idx))
        return jsonify(result)
    except Exception as e:
        logger.error(f"Badge claim error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/request-passes', methods=['POST'])
def request_passes_api():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        pkg_id = data.get('pkg_id')
        passes = data.get('passes')
        price = data.get('price')
        txn_id = data.get('txn_id', '')
        screenshot = data.get('screenshot', None)
        if not user_id or not txn_id:
            return jsonify({'success': False, 'message': 'Transaction ID required'}), 400
        if not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'DB error'}), 503
        result = db.request_pass_purchase(
            int(user_id), int(pkg_id or 1),
            int(passes or 15), float(price or 50),
            txn_id.strip(), screenshot
        )
        # Notify admins via bot
        if result.get('success') and bot_app:
            user = db.get_user(int(user_id))
            uname = user.get('first_name', 'User') if user else 'User'
            req_id = result.get('request_id', '?')
            for admin_id in config.ADMIN_IDS:
                try:
                    import asyncio
                    async def notify():
                        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                        kb = [[
                            InlineKeyboardButton("✅ VERIFY", callback_data=f"verify_passes_{req_id}"),
                            InlineKeyboardButton("❌ REJECT", callback_data=f"reject_passes_{req_id}")
                        ]]
                        await bot_app.bot.send_message(
                            chat_id=admin_id,
                            text=(
                                f"💰 **PASS PURCHASE REQUEST**\n\n"
                                f"👤 User: {uname} (`{user_id}`)\n"
                                f"📦 Package: {passes} passes\n"
                                f"💵 Amount: ₹{price}\n"
                                f"🔢 TXN ID: `{txn_id}`\n"
                                f"📋 Request ID: `{req_id}`"
                            ),
                            reply_markup=InlineKeyboardMarkup(kb),
                            parse_mode='Markdown'
                        )
                    asyncio.run_coroutine_threadsafe(notify(), bot_loop)
                except Exception as e:
                    logger.error(f"Admin notify error: {e}")
        return jsonify(result)
    except Exception as e:
        logger.error(f"Request passes error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/verify-passes', methods=['POST'])
def verify_passes_api():
    try:
        data = request.get_json()
        request_id = data.get('request_id')
        action = data.get('action')  # 'verify' or 'reject'
        admin_id = data.get('admin_id')
        if not request_id or not action:
            return jsonify({'success': False, 'message': 'Missing data'}), 400
        if not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'DB error'}), 503
        result = db.process_pass_request(request_id, action, admin_id)
        # Notify user
        if result.get('success') and bot_app:
            user_id = result.get('user_id')
            passes = result.get('passes', 0)
            if action == 'verify':
                msg = f"✅ **Passes Add Ho Gaye!**\n\n🎟️ {passes} passes aapke account mein add ho gaye!\nGame khelo aur paise kamao! 🎮"
            else:
                msg = f"❌ **Pass Request Reject**\n\nAapki pass request reject ho gayi.\nTransaction proof sahi nahi tha ya already processed tha.\nSupport ke liye contact karo."
            try:
                import asyncio
                async def notify_user():
                    await bot_app.bot.send_message(chat_id=user_id, text=msg, parse_mode='Markdown')
                asyncio.run_coroutine_threadsafe(notify_user(), bot_loop)
            except Exception as e:
                logger.error(f"User notify error: {e}")
        return jsonify(result)
    except Exception as e:
        logger.error(f"Verify passes error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/claim-weekly-bonus', methods=['POST'])
def claim_weekly_bonus_api():
    """
    FIXED:
    - Proper week_start calculation
    - Claimed days count accurate
    - Already claimed check with week key
    - Cache clear after claim
    """
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': 'Missing user_id'}), 400
        if not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'DB error'}), 503

        user_id_int = int(user_id)

        # FIXED: Current week start (Monday)
        today = datetime.now().date()
        day_of_week = today.weekday()  # 0=Monday
        week_start = today - timedelta(days=day_of_week)
        week_end = week_start + timedelta(days=6)
        week_key = week_start.isoformat()

        # All 7 days of this week
        week_dates = [(week_start + timedelta(days=i)).isoformat() for i in range(7)]

        # Count claimed days this week
        claimed_this_week = db.daily_bonus.count_documents({
            'user_id': user_id_int,
            'date': {'$in': week_dates}
        })

        if claimed_this_week < 7:
            return jsonify({
                'success': False,
                'message': f'Sirf {claimed_this_week}/7 days claim ki hain. Pehle 7 din complete karo!',
                'claimed_days': claimed_this_week,
                'needed': 7
            })

        # FIXED: Already claimed this week check
        user_check = db.get_user(user_id_int)
        if not user_check:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        weekly_field = f'weekly_bonus_{week_key}'
        if user_check.get(weekly_field):
            return jsonify({'success': False, 'message': 'Is hafte ka weekly bonus already claim hua hai!'})

        # ATOMIC claim
        result = db.users.find_one_and_update(
            {'user_id': user_id_int, weekly_field: {'$ne': True}},
            {'$set': {weekly_field: True, 'weekly_bonus_claimed_at': datetime.now().isoformat()}}
        )
        if not result:
            return jsonify({'success': False, 'message': 'Weekly bonus already claimed!'})

        WEEKLY_REWARD = 1.0
        db.add_balance(user_id_int, WEEKLY_REWARD, 'Weekly bonus — 7 din complete!')
        db.add_live_activity('bonus', user_id_int, WEEKLY_REWARD, '7 din ka streak! Weekly bonus +₹1')
        db.user_cache.pop(f"user_{user_id_int}", None)

        logger.info(f"Weekly bonus claimed: user={user_id_int} week={week_key}")
        return jsonify({
            'success': True,
            'reward': WEEKLY_REWARD,
            'message': f'🎉 Weekly Bonus! +₹{WEEKLY_REWARD}',
            'week': week_key
        })
    except Exception as e:
        logger.error(f"Weekly bonus error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/claim-mission-reward', methods=['POST'])
def claim_mission_reward_api():
    """Legacy — kept for compatibility."""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': 'Missing user ID'}), 400
        return jsonify({'success': False, 'message': 'Use /api/claim-single-mission instead'})
    except Exception as e:
        logger.error(f"Claim mission reward error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/update-mission', methods=['POST'])
def update_mission_api():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        mission_id = data.get('mission_id') or data.get('mission_type')
        count = data.get('count', 1)
        if not user_id or not mission_id:
            return jsonify({'success': False, 'message': 'Missing data'}), 400
        db._update_single_mission_progress(user_id, mission_id, count)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Update mission error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ========== DAILY SEARCH ==========

@app.route('/api/record-search', methods=['POST'])
def record_search_api():
    try:
        data = request.get_json()
        referred_user_id = data.get('user_id')
        if not referred_user_id:
            return jsonify({'success': False, 'message': 'Missing user_id'}), 400
        result = db.record_daily_search(referred_user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Record search error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/self-search', methods=['POST'])
def self_search_api():
    """User khud movie search karta hai — 48 hr mein ek baar 30 pts milte hain"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': 'Missing user_id'}), 400
        if not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'DB error'}), 503
        result = db.record_self_search(int(user_id))
        return jsonify(result)
    except Exception as e:
        logger.error(f"Self search error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/self-search-status/<int:user_id>')
def self_search_status_api(user_id):
    """Check when user can next self-search"""
    try:
        if not db or not db.ensure_connection():
            return jsonify({'can_search': True})
        result = db.get_self_search_status(user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Self search status error: {e}")
        return jsonify({'can_search': True})

# ========== PASSES API ==========

@app.route('/api/user/<int:user_id>/passes')
def get_passes_api(user_id):
    try:
        if not db or not db.ensure_connection():
            return jsonify({'passes': 0})
        user = db.get_user(user_id)
        return jsonify({'passes': user.get('passes', 0) if user else 0})
    except Exception as e:
        logger.error(f"Get passes error: {e}")
        return jsonify({'passes': 0})

@app.route('/api/add-passes', methods=['POST'])
def add_passes_api():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        count = data.get('count', 1)
        admin_id = data.get('admin_id')
        if not admin_id:
            return jsonify({'success': False, 'message': 'Admin required'}), 401
        admin_user = db.get_user(int(admin_id))
        if not admin_user or not admin_user.get('is_admin', False):
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        success = db.add_passes(int(user_id), int(count), "Admin added passes")
        return jsonify({'success': success})
    except Exception as e:
        logger.error(f"Add passes error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ========== WITHDRAWAL ==========

@app.route('/api/withdraw', methods=['POST'])
def withdraw_api():
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
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        message = data.get('message')
        if not user_id or not message:
            return jsonify({'success': False, 'message': 'Missing data'}), 400
        msg_id = db.add_support_message(user_id, message)
        if msg_id:
            if bot_app and config and bot_loop:
                for admin_id in config.ADMIN_IDS:
                    try:
                        asyncio.run_coroutine_threadsafe(
                            bot_app.bot.send_message(
                                chat_id=admin_id,
                                text=f"📩 *New Support Message*\n\nUser ID: `{user_id}`\nMsg: {message[:100]}",
                                parse_mode=ParseMode.MARKDOWN
                            ),
                            bot_loop
                        )
                    except:
                        pass
            return jsonify({'success': True, 'message': 'Message sent!'})
        return jsonify({'success': False, 'message': 'Failed to send'})
    except Exception as e:
        logger.error(f"Support API error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/support-messages')
def admin_support_messages_api():
    try:
        admin_id = request.args.get('admin_id', type=int)
        if not admin_id:
            return jsonify({'error': 'Admin ID required'}), 401
        admin_user = db.get_user(admin_id)
        if not admin_user or not admin_user.get('is_admin', False):
            return jsonify({'error': 'Unauthorized'}), 403
        messages = db.get_pending_support_messages(30)
        return jsonify(messages)
    except Exception as e:
        logger.error(f"Admin support messages error: {e}")
        return jsonify([])

@app.route('/api/admin/reply-support', methods=['POST'])
def admin_reply_support_api():
    try:
        data = request.get_json()
        admin_id = data.get('admin_id')
        message_id = data.get('message_id')
        reply = data.get('reply')
        user_id = data.get('user_id')
        if not all([admin_id, message_id, reply]):
            return jsonify({'success': False, 'message': 'Missing data'}), 400
        admin_user = db.get_user(int(admin_id))
        if not admin_user or not admin_user.get('is_admin', False):
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        success = db.mark_support_replied(message_id, admin_id, reply)
        if success:
            if bot_app and bot_loop and user_id:
                try:
                    asyncio.run_coroutine_threadsafe(
                        bot_app.bot.send_message(
                            chat_id=int(user_id),
                            text=f"📩 *Support Reply*\n\n{reply}",
                            parse_mode=ParseMode.MARKDOWN
                        ),
                        bot_loop
                    )
                except:
                    pass
            return jsonify({'success': True, 'message': 'Reply sent!'})
        return jsonify({'success': False, 'message': 'Failed'})
    except Exception as e:
        logger.error(f"Admin reply support error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/delete-support', methods=['POST'])
def admin_delete_support_api():
    """Delete a support message."""
    try:
        data = request.get_json()
        admin_id = data.get('admin_id')
        message_id = data.get('message_id')
        if not all([admin_id, message_id]):
            return jsonify({'success': False, 'message': 'Missing data'}), 400
        admin_user = db.get_user(int(admin_id))
        if not admin_user or not admin_user.get('is_admin', False):
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        success = db.delete_support_message(message_id)
        if success:
            return jsonify({'success': True, 'message': 'Message deleted'})
        return jsonify({'success': False, 'message': 'Not found'})
    except Exception as e:
        logger.error(f"Admin delete support error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ========== SETTINGS ==========

@app.route('/api/update-setting', methods=['POST'])
def update_setting_api():
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

# ========== GAME APIs ==========

@app.route('/api/game/state/<int:user_id>')
def get_game_state(user_id):
    try:
        if not db or not db.ensure_connection():
            return jsonify({'error': 'Database not connected'}), 503
        today = datetime.now().date().isoformat()
        game_state = db.get_game_state(user_id, today)
        user = db.get_user(user_id)
        game_state['passes'] = user.get('passes', 0) if user else 0
        return jsonify(game_state)
    except Exception as e:
        logger.error(f"Get game state error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/game/spin', methods=['POST'])
def game_spin_api():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': 'Missing user_id'}), 400
        if not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'Database error'}), 503
        # FIXED: Fresh passes count include karo response mein
        result = db.process_game_spin(user_id)
        if result.get('success'):
            fresh_user = db.get_user(int(user_id))
            result['passes_remaining'] = fresh_user.get('passes', 0) if fresh_user else 0
        return jsonify(result)
    except Exception as e:
        logger.error(f"Spin game error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/game/guess', methods=['POST'])
def game_guess_api():
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
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        choice = data.get('choice')
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

# ========== NEW: DICE GAME API ==========

@app.route('/api/game/dice', methods=['POST'])
def game_dice_api():
    """
    Dice Roll game.
    User picks 1-6, dice rolls.
    Win = ₹0.50 if correct (with 60% house edge).
    Costs 1 Pass.
    """
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        choice = data.get('choice')
        if not user_id or choice is None:
            return jsonify({'success': False, 'message': 'Missing data'}), 400
        if not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'Database error'}), 503
        result = db.process_game_dice(user_id, int(choice))
        return jsonify(result)
    except Exception as e:
        logger.error(f"Dice game error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/game/scratch', methods=['POST'])
def game_scratch_api():
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

@app.route('/api/game/color', methods=['POST'])
def game_color_api():
    """Color Prediction game."""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        choice = data.get('choice')
        bet = data.get('bet', 1)
        if not user_id or not choice:
            return jsonify({'success': False, 'message': 'Missing data'}), 400
        if not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'Database error'}), 503
        result = db.process_game_color(user_id, choice, float(bet))
        return jsonify(result)
    except Exception as e:
        logger.error(f"Color game error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/game/crash-start', methods=['POST'])
def game_crash_start_api():
    """Crash game start — deduct pass."""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        bet = data.get('bet', 1)
        if not user_id:
            return jsonify({'success': False, 'message': 'Missing user_id'}), 400
        if not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'Database error'}), 503
        result = db.process_crash_start(user_id, float(bet))
        return jsonify(result)
    except Exception as e:
        logger.error(f"Crash start error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/game/crash-cashout', methods=['POST'])
def game_crash_cashout_api():
    """Crash game cashout — credit reward."""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        bet = data.get('bet', 1)
        multiplier = data.get('multiplier', 1.0)
        reward = data.get('reward', 0)
        if not user_id:
            return jsonify({'success': False, 'message': 'Missing user_id'}), 400
        if not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'Database error'}), 503
        result = db.process_crash_cashout(user_id, float(bet), float(multiplier), float(reward))
        return jsonify(result)
    except Exception as e:
        logger.error(f"Crash cashout error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/game/runner-start', methods=['POST'])
def runner_start_api():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        mode = data.get('mode', '10s')
        bet = data.get('bet', 1.0)
        if not user_id:
            return jsonify({'success': False, 'message': 'Missing user_id'}), 400
        if not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'Database error'}), 503
        result = db.runner_start(user_id, mode, float(bet))
        return jsonify(result)
    except Exception as e:
        logger.error(f"Runner start error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/game/runner-finish', methods=['POST'])
def runner_finish_api():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        mode = data.get('mode', '10s')
        bet = data.get('bet', 1.0)
        survived_seconds = data.get('survived_seconds', 0)
        if not user_id:
            return jsonify({'success': False, 'message': 'Missing user_id'}), 400
        if not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'Database error'}), 503
        result = db.runner_finish(user_id, mode, float(bet), int(survived_seconds))
        return jsonify(result)
    except Exception as e:
        logger.error(f"Runner finish error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/game/earn', methods=['POST'])
def game_earn_api():
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

# ========== STATS & HEALTH ==========

@app.route('/api/stats')
def stats_api():
    global request_count, start_time, db
    uptime = str(datetime.now() - start_time).split('.')[0]
    stats = {
        'uptime': uptime, 'requests': request_count,
        'status': 'healthy', 'db_connected': db.connected if db else False,
        'timestamp': datetime.now().isoformat()
    }
    if db and db.connected:
        try:
            stats.update(db.get_system_stats())
            # Add admin panel stats
            stats['total_users'] = db.users.count_documents({})
            stats['pending_withdrawals'] = db.withdrawals.count_documents({'status': 'pending'})
            stats['pending_support'] = db.issues.count_documents({'status': 'pending'}) if hasattr(db, 'issues') else 0
        except:
            pass
    return jsonify(stats)

# In-memory announcement (persists while server is running)
_announcement = {'text': '', 'ts': 0}

@app.route('/api/set-announcement', methods=['POST'])
def set_announcement_api():
    global _announcement
    try:
        data = request.get_json()
        admin_id = data.get('admin_id')
        if not admin_id or not config.is_admin(admin_id):
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        text = data.get('text', '').strip()
        _announcement = {'text': text, 'ts': datetime.now().timestamp()}
        # Persist to file so it survives restarts
        try:
            import json as _json
            with open('announcement.json', 'w') as f:
                _json.dump({'text': text, 'image_url': '', 'ts': _announcement['ts']}, f)
        except Exception:
            try:
                with open('announcement.txt', 'w') as f:
                    f.write(text)
            except Exception:
                pass
        logger.info(f"Announcement set by admin {admin_id}: {text[:50]}")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/get-announcement')
def get_announcement():
    try:
        # Check in-memory first
        if _announcement.get('text', '').strip():
            return jsonify({'text': _announcement['text'], 'image_url': ''})
        import json as _json
        try:
            with open('announcement.json', 'r') as f:
                d = _json.load(f)
            if d.get('text','').strip():
                return jsonify({'text': d.get('text',''), 'image_url': d.get('image_url','')})
        except Exception:
            pass
        try:
            with open('announcement.txt', 'r') as f:
                text = f.read().strip()
            if text:
                return jsonify({'text': text, 'image_url': ''})
        except Exception:
            pass
        return jsonify({'text': '', 'image_url': ''})
    except Exception as ex:
        return jsonify({'text': '', 'image_url': ''})


@app.route('/api/send-ref-nudge', methods=['POST'])
def send_ref_nudge():
    """Admin/user sends nudge to pending referred user"""
    try:
        data = request.get_json()
        sender_id = int(data.get('sender_id', 0))
        ref_user_id = int(data.get('ref_user_id', 0))
        sender_name = str(data.get('sender_name', 'Your Referrer'))[:50]
        if not sender_id or not ref_user_id:
            return jsonify({'success': False, 'message': 'Invalid IDs'})
        # Send via bot async
        msg = (
            f"👋 *{sender_name}* ne aapko yaad kiya!\n\n"
            f"📌 Aapne abhi tak movie search nahi ki hai.\n\n"
            f"🎬 Movie Group mein jaake koi bhi movie search karo aur shortlink pura karo:\n"
            f"👉 https://t.me/all_movies_webseries_is_here\n\n"
            f"✅ Isse *aapko bhi* 30 pts milenge aur jisne refer kiya unhe bhi paise milenge! 💰"
        )
        import asyncio as _asyncio
        async def _send():
            try:
                await bot_app.bot.send_message(
                    chat_id=ref_user_id,
                    text=msg,
                    parse_mode='Markdown'
                )
                return {'success': True}
            except Exception as ex:
                err = str(ex).lower()
                if 'blocked' in err or 'deactivated' in err:
                    return {'success': False, 'message': 'Is user ne bot block kar diya hai'}
                return {'success': False, 'message': str(ex)[:100]}
        if bot_loop and bot_loop.is_running():
            future = _asyncio.run_coroutine_threadsafe(_send(), bot_loop)
            result = future.result(timeout=10)
            return jsonify(result)
        return jsonify({'success': False, 'message': 'Bot not running'})
    except Exception as ex:
        logger.error(f"send_ref_nudge error: {ex}")
        return jsonify({'success': False, 'message': str(ex)[:100]})


# ========== NEW: SHORTLINK REMINDER API ==========

@app.route('/api/send-shortlink-reminder', methods=['POST'])
def send_shortlink_reminder_api():
    """Send reminder to pending referrals who haven't completed shortlink"""
    try:
        data = request.get_json()
        user_id = int(data.get('user_id', 0))
        if not user_id:
            return jsonify({'success': False, 'message': 'Missing user_id'})
        if not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'DB error'})

        # Find pending referrals for this user
        pending = list(db.referrals.find({
            'referrer_id': user_id,
            'is_active': False
        }).limit(10))

        sent = 0
        for ref in pending:
            ref_user_id = ref.get('referred_id')
            ref_user = db.get_user(ref_user_id)
            if not ref_user:
                continue
            ref_name = ref_user.get('first_name', 'Dost')
            try:
                import asyncio
                async def _send(rid, rname):
                    kb = [[InlineKeyboardButton("🎬 MOVIE SEARCH KARO!", url=config.MOVIE_GROUP_LINK)]]
                    await bot_app.bot.send_message(
                        chat_id=rid,
                        text=(
                            f"👋 *{rname}, yaad hai?*\n\n"
                            f"Tumne abhi tak movie search nahi ki! 😔\n\n"
                            f"🎁 *Abhi karo = 50 pts INSTANT bonus!*\n"
                            f"🎬 Group mein koi bhi movie search karo\n"
                            f"🔗 Shortlink kholo — bas 10 second!\n\n"
                            f"💰 Roz search = Roz 30 pts!\n"
                            f"🎮 Games khelo = Unlimited earning!\n\n"
                            f"⏰ *Offer limited hai — jaldi karo!*"
                        ),
                        reply_markup=InlineKeyboardMarkup(kb),
                        parse_mode='Markdown'
                    )
                if bot_loop and bot_loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(_send(ref_user_id, ref_name), bot_loop)
                    future.result(timeout=10)
                    sent += 1
            except:
                pass

        return jsonify({'success': True, 'sent': sent, 'total_pending': len(pending)})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ========== NEW: DAILY STREAK CHALLENGE API ==========

@app.route('/api/streak-challenge', methods=['POST'])
def streak_challenge_api():
    """7/30 day streak challenge — extra bonus"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        if not user_id or not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'Missing data'})

        user = db.get_user(int(user_id))
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})

        streak = user.get('daily_streak', 0)
        result = {'success': False, 'message': 'No milestone reached'}

        if streak == 7 and not user.get('streak_7_claimed'):
            bonus = config.STREAK_7_BONUS
            db.add_balance(int(user_id), bonus, f"7-day streak bonus!")
            db.users.update_one({'user_id': int(user_id)}, {'$set': {'streak_7_claimed': True}})
            db.add_live_activity('bonus', int(user_id), bonus, f"🔥 7-day streak bonus +₹{bonus}!")
            db.user_cache.pop(f"user_{user_id}", None)
            result = {'success': True, 'bonus': bonus, 'message': f'🔥 7-day streak! +₹{bonus}!'}

        elif streak == 30 and not user.get('streak_30_claimed'):
            bonus = config.STREAK_30_BONUS
            db.add_balance(int(user_id), bonus, f"30-day streak bonus!")
            db.users.update_one({'user_id': int(user_id)}, {'$set': {'streak_30_claimed': True}})
            db.add_live_activity('bonus', int(user_id), bonus, f"🏆 30-day streak bonus +₹{bonus}!")
            db.user_cache.pop(f"user_{user_id}", None)
            result = {'success': True, 'bonus': bonus, 'message': f'🏆 30-day streak! +₹{bonus}!'}

        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ========== NEW: QUIZ GAME API ==========

@app.route('/api/game/quiz', methods=['POST'])
def game_quiz_api():
    """Daily quiz game — 1 pass, answer correctly = 100 pts"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        answer_idx = data.get('answer')
        correct_idx = data.get('correct')
        if not user_id:
            return jsonify({'success': False, 'message': 'Missing data'})
        if not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'DB error'})

        user = db.get_user(int(user_id))
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        if user.get('passes', 0) < 1:
            return jsonify({'success': False, 'message': 'Not enough passes! Earn or buy passes.'})

        # Deduct 1 pass
        db.users.update_one({'user_id': int(user_id)}, {'$inc': {'passes': -1}})

        is_correct = (int(answer_idx) == int(correct_idx))
        reward = 0
        if is_correct:
            reward = 0.10  # ₹0.10 = 10pts
            db.add_balance(int(user_id), reward, "Quiz correct answer!")
            db.add_live_activity('game', int(user_id), reward, "🧠 Quiz correct! +10 pts")

        db.user_cache.pop(f"user_{user_id}", None)
        return jsonify({
            'success': True,
            'correct': is_correct,
            'reward': reward,
            'message': f'+{int(reward*100)} pts! 🎉' if is_correct else 'Galat jawab! 😞'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/health')
def health():
    status = {'status': 'ok', 'time': datetime.now().isoformat(), 'db_connected': db.connected if db else False}
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
        asyncio.run_coroutine_threadsafe(bot_app.process_update(update), bot_loop)
        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "Error", 500

# ========== BOT SETUP ==========

async def post_init(application):
    global config
    logger.info("Running post-initialization...")
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

        # Webhook delete karo — polling use ho raha hai, dono ek saath nahi chalte
        try:
            await application.bot.delete_webhook(drop_pending_updates=True)
            logger.info("Webhook deleted — polling mode active")
        except Exception as _we:
            logger.warning(f"Webhook delete error (ignore): {_we}")

        if config and config.LOG_CHANNEL_ID:
            try:
                await application.bot.send_message(
                    chat_id=config.LOG_CHANNEL_ID,
                    text=f"🤖 EarnZone Bot Started!\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
            except Exception as e:
                logger.error(f"Log channel startup message error: {e}")

        logger.info("Bot initialization complete")
    except Exception as e:
        logger.error(f"Post-init error: {e}")

async def scheduled_jobs():
    global db, config, bot_app, handlers
    logger.info("Scheduled jobs started")
    reminder_sent_today = None
    while True:
        try:
            now = datetime.now()

            # Midnight job — daily earnings
            if now.hour == 0 and now.minute == 0:
                if db and db.ensure_connection():
                    count = db.process_daily_referral_earnings()
                    logger.info(f"Midnight job: processed {count} daily earnings")

            # Evening reminder — 8 PM (once per day)
            if now.hour == 20 and now.minute == 0:
                today_str = now.date().isoformat()
                if reminder_sent_today != today_str:
                    reminder_sent_today = today_str
                    if bot_app and handlers and db:
                        try:
                            # Create a fake context-like object for the reminder
                            class FakeContext:
                                def __init__(self, bot):
                                    self.bot = bot
                            ctx = FakeContext(bot_app.bot)
                            await handlers.send_daily_reminders(ctx)
                            logger.info("✅ Daily reminders sent at 8 PM")
                        except Exception as e:
                            logger.error(f"Reminder job error: {e}")

            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Scheduled job error: {e}")
            await asyncio.sleep(60)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text("An error occurred. Please try again.")
        except:
            pass

def run_bot():
    global bot_app, bot_loop, config, db, handlers, admin_handlers, bot_running
    logger.info("Starting bot...")
    if bot_running:
        return

    bot_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(bot_loop)

    try:
        bot_app = Application.builder().token(config.BOT_TOKEN).build()

        # Commands
        bot_app.add_handler(CommandHandler("start", handlers.start))
        bot_app.add_handler(CommandHandler("app", handlers.open_app))
        bot_app.add_handler(CommandHandler("balance", handlers.check_balance))
        bot_app.add_handler(CommandHandler("referrals", handlers.show_referrals))
        bot_app.add_handler(CommandHandler("withdraw", handlers.withdraw_cmd))
        bot_app.add_handler(CommandHandler("help", handlers.help_cmd))
        bot_app.add_handler(CommandHandler("admin", admin_handlers.admin_panel))

        # Admin callbacks
        bot_app.add_handler(CallbackQueryHandler(admin_handlers.handle_admin_callback))

        # WebApp data
        bot_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handlers.handle_webapp_data))

        # ===== LOG CHANNEL HANDLER (FIXED) =====
        # IMPORTANT: Telegram channel messages come as channel_post updates
        # We use both filters to ensure we catch all messages from log channel
        from telegram.ext import filters as tg_filters
        # Filter 1: Any text in log channel (covers most cases)
        bot_app.add_handler(MessageHandler(
            tg_filters.Chat(LOG_CHANNEL_ID) & tg_filters.TEXT,
            handlers.handle_log_channel_message
        ), group=0)
        # Filter 2: Explicit channel_post type (belt + suspenders)
        try:
            bot_app.add_handler(MessageHandler(
                tg_filters.UpdateType.CHANNEL_POSTS & tg_filters.Chat(LOG_CHANNEL_ID) & tg_filters.TEXT,
                handlers.handle_log_channel_message
            ), group=0)
        except Exception as _e:
            logger.warning(f"Could not add channel_post handler: {_e}")

        # ===== GROUP MESSAGE HANDLER — Daily search earning =====
        # Jab referred users movie group mein message bhejte hain → daily earning credit
        bot_app.add_handler(MessageHandler(
            (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP) & filters.TEXT & ~filters.COMMAND,
            handlers.handle_group_message
        ))

        # Admin private messages
        # Admin handler — ALL media types for broadcast (photo, video, audio, etc)
        bot_app.add_handler(MessageHandler(
            filters.ChatType.PRIVATE & ~filters.COMMAND,
            admin_handlers.handle_admin_message
        ), group=1)

        # General private messages
        bot_app.add_handler(MessageHandler(
            filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND,
            handlers.handle_message
        ))

        bot_app.add_error_handler(error_handler)

        bot_loop.run_until_complete(post_init(bot_app))
        bot_loop.create_task(scheduled_jobs())

        logger.info("✅ Bot started successfully")
        bot_running = True
        logger.info("✅ Bot started — polling with channel_post support")
        bot_app.run_polling(
            allowed_updates=[
                "message",
                "channel_post",       # ← LOG CHANNEL ke messages ke liye ZARURI
                "edited_channel_post",
                "callback_query",
                "inline_query",
            ]
        )

    except Exception as e:
        logger.error(f"Bot error: {e}")
        import traceback; traceback.print_exc()
        bot_running = False
    finally:
        # Cancel all pending tasks before closing loop
        try:
            if bot_loop and not bot_loop.is_closed():
                pending = asyncio.all_tasks(bot_loop)
                for task in pending:
                    task.cancel()
                if pending:
                    bot_loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
        except Exception as _fe:
            pass
        if bot_loop and not bot_loop.is_closed():
            bot_loop.close()
        bot_running = False

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"Flask starting on port {port} with 16 threads")
    try:
        from waitress import serve as waitress_serve
        waitress_serve(app, host='0.0.0.0', port=port,
                      threads=16, channel_timeout=120,
                      connection_limit=500, cleanup_interval=30)
    except ImportError:
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)
    except Exception as e:
        logger.error(f"Flask server error: {e}")

def signal_handler(sig, frame):
    global db, bot_loop, bot_running
    logger.info("Shutting down...")
    if db:
        try: db.cleanup()
        except: pass
    if bot_loop:
        try: bot_loop.stop()
        except: pass
    bot_running = False
    sys.exit(0)

def check_environment():
    # BOT_TOKEN aur MONGODB_URI zaruri hain, ADMIN_IDS optional
    required = ['BOT_TOKEN', 'MONGODB_URI']
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        logger.error(f"❌ Missing REQUIRED env vars: {', '.join(missing)}")
        logger.error("Render Dashboard → Environment → ye variables add karo:")
        for v in missing:
            logger.error(f"  • {v}")
        return False
    # Warnings for optional but recommended
    optional = ['ADMIN_IDS', 'WEBAPP_URL', 'LOG_CHANNEL_ID']
    for v in optional:
        if not os.getenv(v):
            logger.warning(f"⚠️  Optional env var not set: {v}")
    return True

def main():
    global config, db, handlers, admin_handlers, bot_running

    print("""
    ╔══════════════════════════════════════════╗
    ║    EARNZONE BOT - FULLY UPDATED          ║
    ║  Dice Game + Month Refs + Timer Offers   ║
    ╚══════════════════════════════════════════╝
    """)

    if not check_environment():
        sys.exit(1)

    try:
        config = Config()
        logger.info(f"Config loaded. Admins: {config.ADMIN_IDS}")

        db = Database(config)
        if not db.connected:
            logger.error("DB connection failed")
            sys.exit(1)
        logger.info("Database connected")

        handlers = Handlers(config, db)
        admin_handlers = AdminHandlers(config, db, None)
        logger.info("Handlers initialized")

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        time.sleep(3)
        logger.info(f"Flask running on port {os.environ.get('PORT', 10000)}")

        run_bot()

    except KeyboardInterrupt:
        logger.info("Stopped by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        # Render pe crash mat karo — 30 second wait karke retry karo
        logger.info("30 seconds mein retry karega...")
        time.sleep(30)
        # Ek baar aur try karo
        try:
            main()
        except Exception as e2:
            logger.critical(f"Retry bhi fail: {e2}")
            sys.exit(1)
    finally:
        if db:
            try: db.cleanup()
            except: pass
        bot_running = False
        logger.info("Shutdown complete")

if __name__ == '__main__':
    main()
