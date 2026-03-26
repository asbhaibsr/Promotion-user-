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
from flask import Flask, request, jsonify, render_template
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

LOG_CHANNEL_ID = -1002352329534

# ========== CORS ==========

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
    return add_cors_headers(jsonify({'status': 'ok'}))

# ========== MAIN PAGE ==========

@app.route('/')
def index():
    global config, db, request_count
    request_count += 1
    try:
        user_id = request.args.get('user_id', 0, type=int)
        user_data = None
        if user_id and user_id > 0 and db and db.ensure_connection():
            try:
                user_data = db.get_user(user_id)
            except Exception as e:
                logger.error(f"Error fetching user {user_id}: {e}")

        template_vars = {
            'user_id': user_id, 'user_name': 'Guest', 'balance': 0,
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
            'support_username': config.SUPPORT_USERNAME if config else '@support'
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

        return render_template('index.html', **template_vars)
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
            # Ensure today_earned field exists
            if 'today_earned' not in user_data:
                user_data['today_earned'] = 0.0
            # Build claimed_milestones list from individual fields
            claimed_milestones = []
            for m in [5, 10, 25, 50, 100]:
                if user_data.get(f'milestone_claimed_{m}'):
                    claimed_milestones.append(m)
            user_data['claimed_milestones'] = claimed_milestones
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
        leaderboard = db.get_leaderboard(20)
        return jsonify(leaderboard)
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        return jsonify([])

@app.route('/api/live-activity')
def live_activity_api():
    try:
        if not db or not db.ensure_connection():
            return jsonify([])
        activities = db.get_live_activity(20)
        return jsonify(activities)
    except Exception as e:
        logger.error(f"Live activity error: {e}")
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
        # UPDATED: pass timer_seconds
        timer_seconds = int(data.get('timer_seconds', 0) or 0)
        success = db.update_ad(
            ad_id,
            data.get('title'),
            data.get('reward'),
            data.get('link'),
            data.get('meta'),
            data.get('icon'),
            claim_code=data.get('claim_code'),
            timer_seconds=timer_seconds
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
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': 'Missing user_id'}), 400
        if not db or not db.ensure_connection():
            return jsonify({'success': False, 'message': 'DB error'}), 503
        # Check this week's claimed days
        today = datetime.now().date()
        day_of_week = today.weekday()  # 0=Mon
        week_start = today - timedelta(days=day_of_week)
        week_dates = [(week_start + timedelta(days=i)).isoformat() for i in range(7)]
        user_id_int = int(user_id)
        claimed_this_week = db.daily_bonus.count_documents({
            'user_id': user_id_int,
            'date': {'$in': week_dates}
        })
        if claimed_this_week < 7:
            return jsonify({'success': False, 'message': f'Sirf {claimed_this_week}/7 days claimed. 7 chahiye!'})
        # Check already claimed this week
        result = db.users.find_one_and_update(
            {'user_id': user_id_int, f'weekly_bonus_{week_start.isoformat()}': {'$ne': True}},
            {'$set': {f'weekly_bonus_{week_start.isoformat()}': True}}
        )
        if not result:
            return jsonify({'success': False, 'message': 'Weekly bonus already claimed!'})
        db.add_balance(user_id_int, 1.0, 'Weekly bonus — 7 day streak!')
        db.add_live_activity('bonus', user_id_int, 1.0, '7 din ka streak! Weekly bonus +₹1')
        db.user_cache.pop(f"user_{user_id_int}", None)
        return jsonify({'success': True, 'reward': 1.0, 'message': '🎉 Weekly Bonus! +₹1'})
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
        result = db.process_game_spin(user_id)
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
        except:
            pass
    return jsonify(stats)

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

        if config and config.WEBHOOK_URL:
            webhook_url = f"{config.WEBHOOK_URL}/webhook"
            await application.bot.set_webhook(url=webhook_url)
            logger.info(f"Webhook set to {webhook_url}")

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

        # ===== LOG CHANNEL HANDLER =====
        bot_app.add_handler(MessageHandler(
            filters.Chat(LOG_CHANNEL_ID) & filters.TEXT,
            handlers.handle_log_channel_message
        ))

        # ===== GROUP MESSAGE HANDLER — Daily search earning =====
        # Jab referred users movie group mein message bhejte hain → daily earning credit
        bot_app.add_handler(MessageHandler(
            (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP) & filters.TEXT & ~filters.COMMAND,
            handlers.handle_group_message
        ))

        # Admin private messages
        bot_app.add_handler(MessageHandler(
            filters.TEXT & filters.ChatType.PRIVATE,
            admin_handlers.handle_admin_message
        ))

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
        bot_app.run_polling()

    except Exception as e:
        logger.error(f"Bot error: {e}")
        import traceback; traceback.print_exc()
        bot_running = False
    finally:
        if bot_loop:
            bot_loop.close()
        bot_running = False

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"Flask starting on port {port}")
    try:
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)
    except Exception as e:
        logger.error(f"Flask error: {e}")
        sys.exit(1)

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
    required = ['BOT_TOKEN', 'MONGODB_URI', 'ADMIN_IDS']
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        logger.error(f"Missing env vars: {', '.join(missing)}")
        return False
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
        import traceback; traceback.print_exc()
    finally:
        if db:
            try: db.cleanup()
            except: pass
        bot_running = False
        logger.info("Shutdown complete")

if __name__ == '__main__':
    main()
