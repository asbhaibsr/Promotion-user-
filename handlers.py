#Handlers.py

import logging
import random
import time
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.error import TelegramError, TimedOut, Forbidden, BadRequest
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import asyncio

from config import (
    USERS_COLLECTION, REFERRALS_COLLECTION, SETTINGS_COLLECTION, WITHDRAWALS_COLLECTION,
    DOLLAR_TO_INR, MESSAGES, ADMIN_ID, YOUR_TELEGRAM_HANDLE, 
    SPIN_WHEEL_CONFIG, SPIN_PRIZES, SPIN_WEIGHTS, TIERS, DAILY_MISSIONS,
    CHANNEL_USERNAME, CHANNEL_ID, CHANNEL_BONUS,
    NEW_MOVIE_GROUP_LINK, MOVIE_GROUP_LINK, ALL_GROUPS_LINK, EXAMPLE_SCREENSHOT_URL,
    WITHDRAWAL_REQUIREMENTS, WITHDRAWAL_METHODS
)
from db_utils import (
    send_log_message, get_user_lang, set_user_lang, get_referral_bonus_inr, 
    get_welcome_bonus, get_user_tier, get_tier_referral_rate, 
    claim_and_update_daily_bonus, update_daily_searches_and_mission,
    get_bot_stats, pay_referrer_and_update_mission,
    get_user_stats, admin_add_money, admin_clear_earnings, admin_delete_user, clear_junk_users
)

logger = logging.getLogger(__name__)

# ==================== HELPER FUNCTIONS ====================

async def check_channel_membership(bot, user_id):
    """Check if user is member of channel"""
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Channel check failed: {e}")
        return False

async def get_dynamic_invite_link(context):
    """Get or create channel invite link dynamically"""
    try:
        chat = await context.bot.get_chat(CHANNEL_ID)
        if chat.invite_link:
            return chat.invite_link
        return await context.bot.export_chat_invite_link(CHANNEL_ID)
    except Exception as e:
        logger.error(f"Link generation failed: {e}")
        return f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"

# ==================== VERIFY CALLBACK ====================

async def verify_channel_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Verify channel join and show main menu"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    is_member = await check_channel_membership(context.bot, user.id)
    
    if is_member:
        await query.answer("✅ Verified!", show_alert=True)
        lang = await get_user_lang(user.id)
        
        keyboard = [
            [InlineKeyboardButton("🎬 Movie Groups", callback_data="show_movie_groups_menu")],
            [InlineKeyboardButton("💰 Earning Panel", callback_data="show_earning_panel")],
            [InlineKeyboardButton(MESSAGES[lang]["language_choice"], callback_data="select_lang")]
        ]
        
        msg = MESSAGES[lang]["start_greeting"].format(name=user.first_name)
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    else:
        await query.answer("❌ Join channel first!", show_alert=True)

# ==================== START COMMAND (UPDATED) ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command with dynamic channel link"""
    user = update.effective_user
    
    # FORCE JOIN CHECK
    is_member = await check_channel_membership(context.bot, user.id)
    
    if not is_member:
        invite_link = await get_dynamic_invite_link(context)
        msg = f"👋 <b>Hello {user.first_name}!</b>\n\n⛔️ Join channel to use bot:"
        keyboard = [
            [InlineKeyboardButton("🚀 Join Channel", url=invite_link)],
            [InlineKeyboardButton("✅ Verify Join", callback_data="verify_channel_join")]
        ]
        if update.message:
            await update.message.reply_html(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # Handle referral
    referral_id = None
    if context.args and context.args[0].startswith("ref_"):
        try:
            referral_id = int(context.args[0].replace("ref_", ""))
        except:
            pass
    
    # Create/update user
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    is_new = not user_data
    
    update_data = {
        "$setOnInsert": {
            "user_id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "lang": "en",
            "earnings": 0.0,
            "spins_left": SPIN_WHEEL_CONFIG["initial_free_spins"],
            "joined_date": datetime.now(),
            "payment_method": None,
            "payment_details": None
        }
    }
    
    USERS_COLLECTION.update_one({"user_id": user.id}, update_data, upsert=True)
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    lang = user_data.get("lang", "en")
    
    # Welcome bonus for new users
    if is_new and not user_data.get("welcome_bonus_received"):
        welcome_bonus = await get_welcome_bonus()
        USERS_COLLECTION.update_one(
            {"user_id": user.id},
            {"$inc": {"earnings": welcome_bonus/DOLLAR_TO_INR},
             "$set": {"welcome_bonus_received": True}}
        )
    
    # Handle referral
    if is_new and referral_id and referral_id != user.id:
        existing = REFERRALS_COLLECTION.find_one({"referred_user_id": user.id})
        if not existing:
            REFERRALS_COLLECTION.insert_one({
                "referrer_id": referral_id,
                "referred_user_id": user.id,
                "join_date": datetime.now(),
                "last_paid_date": None
            })
            USERS_COLLECTION.update_one(
                {"user_id": referral_id},
                {"$inc": {"monthly_referrals": 1, "spins_left": 1}}
            )
    
    # Show main menu
    keyboard = [
        [InlineKeyboardButton("🎬 Movie Groups", callback_data="show_movie_groups_menu")],
        [InlineKeyboardButton("💰 Earning Panel", callback_data="show_earning_panel")],
        [InlineKeyboardButton(MESSAGES[lang]["language_choice"], callback_data="select_lang")]
    ]
    
    msg = MESSAGES[lang]["start_greeting"].format(name=user.first_name)
    if update.message:
        await update.message.reply_html(msg, reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== EARN COMMAND ====================

async def earn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Redirect to earning panel"""
    lang = await get_user_lang(update.effective_user.id)
    keyboard = [[InlineKeyboardButton("💰 Earning Panel", callback_data="show_earning_panel")]]
    await update.message.reply_html("💰 Earning Panel", reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== GROUP MESSAGE HANDLER (FIXED - NO JOB QUEUE) ====================

async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle group messages - DIRECT referral payment (NO JOB QUEUE)"""
    if not update.message or not update.message.text:
        return
    
    if update.effective_chat.type not in ["group", "supergroup"]:
        return
    
    user = update.effective_user
    bot = await context.bot.get_me()
    if user.id == bot.id:
        return
    
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    if not user_data:
        return
    
    # Update daily searches
    await update_daily_searches_and_mission(user.id)
    
    # REFERRAL PAYMENT - DIRECT EXECUTION
    referral = REFERRALS_COLLECTION.find_one({"referred_user_id": user.id})
    if referral:
        referrer_id = referral["referrer_id"]
        if referrer_id == user.id:
            return
        
        # Check if already paid today
        last_paid = referral.get("last_paid_date")
        today = datetime.now().date()
        
        if last_paid and isinstance(last_paid, datetime) and last_paid.date() == today:
            return
        
        # PAY DIRECTLY
        success, amount = await pay_referrer_and_update_mission(context, user.id, referrer_id)
        if success:
            logger.info(f"Direct referral payment: {referrer_id} from {user.id} (₹{amount})")

# ==================== EARNING PANEL ====================

async def show_earning_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show main earning panel"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    data = USERS_COLLECTION.find_one({"user_id": user.id})
    
    if not data:
        return
    
    earnings = data.get("earnings", 0) * DOLLAR_TO_INR
    refs = REFERRALS_COLLECTION.count_documents({"referrer_id": user.id})
    tier = await get_user_tier(user.id)
    rate = TIERS[tier]["rate"]
    spins = data.get("spins_left", 0)
    
    msg = MESSAGES[lang]["earning_panel"].format(
        balance=f"₹{earnings:.2f}",
        refs=refs,
        tier=TIERS[tier]["name"],
        rate=rate
    )
    
    keyboard = [
        [InlineKeyboardButton(MESSAGES[lang]["daily_bonus"].format(amount="0.10-0.50"), callback_data="claim_daily_bonus"),
         InlineKeyboardButton(MESSAGES[lang]["spin_wheel"].format(spins=spins), callback_data="show_spin_panel")],
        [InlineKeyboardButton("🔗 My Refer Link", callback_data="show_refer_link"),
         InlineKeyboardButton("👥 My Referrals", callback_data="show_my_referrals")],
        [InlineKeyboardButton("🎯 Daily Missions", callback_data="show_missions"),
         InlineKeyboardButton("🏆 Leaderboard", callback_data="show_leaderboard")],
        [InlineKeyboardButton(MESSAGES[lang]["withdraw"], callback_data="request_withdrawal"),
         InlineKeyboardButton(f"🎁 Channel Bonus", callback_data="claim_channel_bonus")],
        [InlineKeyboardButton("🎮 Games", callback_data="show_games_menu"),
         InlineKeyboardButton("🆘 Help", callback_data="show_help")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_main_menu")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

# ==================== REFERRAL SYSTEM ====================

async def show_refer_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user's referral link"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    bot = await context.bot.get_me()
    link = f"https://t.me/{bot.username}?start=ref_{user.id}"
    
    msg = MESSAGES[lang]["refer_link"].format(link=link)
    
    share = f"Join and earn! {link}"
    encoded = urllib.parse.quote_plus(share)
    
    keyboard = [
        [InlineKeyboardButton("📤 Share", url=f"https://t.me/share/url?url={link}&text={encoded}")],
        [InlineKeyboardButton("💡 How to Earn", callback_data="show_refer_example")],
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def show_my_referrals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user's referrals"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    refs = list(REFERRALS_COLLECTION.find({"referrer_id": user.id}).sort("join_date", -1).limit(10))
    total = REFERRALS_COLLECTION.count_documents({"referrer_id": user.id})
    
    msg = f"👥 <b>My Referrals ({total})</b>\n\n"
    
    if not refs:
        msg += "No referrals yet. Share your link!"
    else:
        for i, r in enumerate(refs[:10], 1):
            uid = r["referred_user_id"]
            date = r["join_date"].strftime("%d %b")
            last = r.get("last_paid_date")
            status = "✅" if last and last.date() == datetime.now().date() else "⏳"
            msg += f"{i}. <code>{uid}</code> {status} ({date})\n"
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def show_refer_example(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show how referral works"""
    query = update.callback_query
    await query.answer()
    
    lang = await get_user_lang(query.from_user.id)
    rate = TIERS[max(TIERS.keys())]["rate"]
    
    msg = MESSAGES[lang]["refer_example"].format(rate=rate)
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]
    
    if EXAMPLE_SCREENSHOT_URL:
        try:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=EXAMPLE_SCREENSHOT_URL,
                caption=msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            await query.message.delete()
        except:
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    else:
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

# ==================== DAILY BONUS ====================

async def claim_daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Claim daily bonus"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    amount, new_balance, streak, claimed = await claim_and_update_daily_bonus(user.id)
    
    if claimed:
        await query.answer("Already claimed today!", show_alert=True)
        return
    
    if amount:
        msg = MESSAGES[lang]["daily_bonus"].format(amount=f"₹{amount:.2f}")
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        
        await send_log_message(context, f"🎁 Daily Bonus: {user.id} - ₹{amount:.2f}")

# ==================== SPIN WHEEL ====================

async def show_spin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show spin wheel panel"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    data = USERS_COLLECTION.find_one({"user_id": user.id})
    spins = data.get("spins_left", 0)
    
    msg = MESSAGES[lang]["spin_wheel"].format(spins=spins)
    
    if spins > 0:
        keyboard = [[InlineKeyboardButton("🎡 SPIN", callback_data="perform_spin")]]
    else:
        msg += "\n\nRefer a friend to get 1 spin!"
        keyboard = []
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")])
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def perform_spin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Perform a spin"""
    query = update.callback_query
    await query.answer("Spinning...")
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    # Deduct spin
    result = USERS_COLLECTION.find_one_and_update(
        {"user_id": user.id, "spins_left": {"$gte": 1}},
        {"$inc": {"spins_left": -1}},
        return_document=True
    )
    
    if not result:
        await query.answer("No spins left!", show_alert=True)
        return
    
    spins_left = result.get("spins_left", 0)
    
    # Animation
    temp = [InlineKeyboardButton("🎡", callback_data="spin_fake")]
    temp_kb = [temp*3, temp*3, temp*3]
    await query.edit_message_text("🎡 Spinning...", reply_markup=InlineKeyboardMarkup(temp_kb))
    await asyncio.sleep(2)
    
    # Prize
    prize = random.choices(SPIN_PRIZES, weights=SPIN_WEIGHTS)[0]
    
    if prize > 0:
        USERS_COLLECTION.update_one(
            {"user_id": user.id},
            {"$inc": {"earnings": prize/DOLLAR_TO_INR}}
        )
        new_data = USERS_COLLECTION.find_one({"user_id": user.id})
        new_balance = new_data.get("earnings", 0) * DOLLAR_TO_INR
        msg = f"🎉 You won ₹{prize:.2f}!\n\nNew balance: ₹{new_balance:.2f}\nSpins left: {spins_left}"
    else:
        msg = f"😢 Better luck next time!\nSpins left: {spins_left}"
    
    keyboard = [[InlineKeyboardButton("🎡 Spin Again", callback_data="show_spin_panel")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    
    if prize > 0:
        await send_log_message(context, f"🎡 Spin: {user.id} won ₹{prize:.2f}")

async def spin_fake_btn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fake button for animation"""
    await update.callback_query.answer()

# ==================== MISSIONS ====================

async def show_missions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show daily missions"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    # Get counts
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Paid searches today (from referrals)
    refs = list(REFERRALS_COLLECTION.find({"referrer_id": user.id}))
    paid_searches = sum(1 for r in refs if r.get("last_paid_date") and r["last_paid_date"] >= today)
    
    # Referrals today
    new_refs = REFERRALS_COLLECTION.count_documents({
        "referrer_id": user.id,
        "join_date": {"$gte": today}
    })
    
    # Daily bonus claimed?
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    last_checkin = user_data.get("last_checkin_date")
    bonus_claimed = last_checkin and last_checkin >= today
    
    # Update missions
    missions = user_data.get("missions_completed", {})
    
    s1 = 1 if paid_searches >= 3 or missions.get("search_3_movies") else 0
    s2 = 1 if new_refs >= 2 or missions.get("refer_2_friends") else 0
    s3 = 1 if bonus_claimed or missions.get("claim_daily_bonus") else 0
    
    msg = MESSAGES[lang]["missions"].format(s1=paid_searches, s2=new_refs, s3=int(bonus_claimed))
    
    # Auto-complete missions
    if paid_searches >= 3 and not missions.get("search_3_movies"):
        USERS_COLLECTION.update_one(
            {"user_id": user.id},
            {"$inc": {"earnings": 0.6/DOLLAR_TO_INR, "spins_left": 1},
             "$set": {"missions_completed.search_3_movies": True}}
        )
        msg += "\n\n✅ Mission completed: +₹0.60 +1 Spin"
    
    if new_refs >= 2 and not missions.get("refer_2_friends"):
        USERS_COLLECTION.update_one(
            {"user_id": user.id},
            {"$inc": {"earnings": 1.4/DOLLAR_TO_INR, "spins_left": 1},
             "$set": {"missions_completed.refer_2_friends": True}}
        )
        msg += "\n\n✅ Mission completed: +₹1.40 +1 Spin"
    
    if bonus_claimed and not missions.get("claim_daily_bonus"):
        USERS_COLLECTION.update_one(
            {"user_id": user.id},
            {"$inc": {"earnings": 0.2/DOLLAR_TO_INR, "spins_left": 1},
             "$set": {"missions_completed.claim_daily_bonus": True}}
        )
        msg += "\n\n✅ Mission completed: +₹0.20 +1 Spin"
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

# ==================== LEADERBOARD ====================

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show leaderboard"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    # Get top 10
    top = list(USERS_COLLECTION.find().sort("monthly_referrals", -1).limit(10))
    
    # User's rank
    user_refs = USERS_COLLECTION.find_one({"user_id": user.id}, {"monthly_referrals": 1})
    user_refs = user_refs.get("monthly_referrals", 0) if user_refs else 0
    rank = USERS_COLLECTION.count_documents({"monthly_referrals": {"$gt": user_refs}}) + 1
    
    ranks_text = ""
    for i, u in enumerate(top, 1):
        name = u.get("full_name", f"User {u['user_id']}")[:15]
        refs = u.get("monthly_referrals", 0)
        ranks_text += f"{i}. {name}: {refs} refs\n"
    
    msg = MESSAGES[lang]["leaderboard"].format(ranks=ranks_text, rank=rank)
    
    keyboard = [
        [InlineKeyboardButton("💡 Prizes", callback_data="show_leaderboard_info")],
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def show_leaderboard_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show leaderboard prize info"""
    query = update.callback_query
    await query.answer()
    
    lang = await get_user_lang(query.from_user.id)
    msg = MESSAGES[lang]["leaderboard_info"]
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_leaderboard")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

# ==================== CHANNEL BONUS ====================

async def claim_channel_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Claim channel join bonus"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    data = USERS_COLLECTION.find_one({"user_id": user.id})
    if data.get("channel_bonus_received"):
        await query.answer(MESSAGES[lang]["channel_already_claimed"], show_alert=True)
        return
    
    is_member = await check_channel_membership(context.bot, user.id)
    
    if is_member:
        bonus_usd = CHANNEL_BONUS / DOLLAR_TO_INR
        result = USERS_COLLECTION.find_one_and_update(
            {"user_id": user.id, "channel_bonus_received": False},
            {"$inc": {"earnings": bonus_usd}, "$set": {"channel_bonus_received": True}},
            return_document=True
        )
        
        if result:
            new_balance = result.get("earnings", 0) * DOLLAR_TO_INR
            msg = MESSAGES[lang]["channel_bonus_claimed"].format(
                amount=f"₹{CHANNEL_BONUS:.2f}",
                balance=f"₹{new_balance:.2f}"
            )
            keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
            
            await send_log_message(context, f"🎁 Channel Bonus: {user.id} - ₹{CHANNEL_BONUS:.2f}")
    else:
        invite = await get_dynamic_invite_link(context)
        msg = MESSAGES[lang]["channel_bonus_error"].format(channel=CHANNEL_USERNAME)
        keyboard = [
            [InlineKeyboardButton("🚀 Join", url=invite)],
            [InlineKeyboardButton("✅ Verify", callback_data="claim_channel_bonus")],
            [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

# ==================== NEW WITHDRAWAL SYSTEM ====================

async def request_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Main withdrawal handler - shows method selection or saved details"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    data = USERS_COLLECTION.find_one({"user_id": user.id})
    
    earnings = data.get("earnings", 0) * DOLLAR_TO_INR
    
    # Minimum balance check
    if earnings < 80:
        await query.edit_message_text(
            MESSAGES[lang]["withdrawal_insufficient"],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
        )
        return
    
    # Check pending request
    pending = WITHDRAWALS_COLLECTION.find_one({"user_id": user.id, "status": "pending"})
    if pending:
        await query.edit_message_text(
            "⏳ You already have a pending request!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
        )
        return
    
    # Check if saved details exist
    saved_method = data.get("payment_method")
    saved_details = data.get("payment_details")
    
    if saved_method and saved_details:
        # Show confirm screen
        msg = f"💸 <b>Confirm Withdrawal</b>\n\n"
        msg += f"Amount: <b>₹{earnings:.2f}</b>\n"
        msg += f"Method: <b>{saved_method.upper()}</b>\n"
        msg += f"Details: <b>{saved_details}</b>\n\n"
        msg += "Proceed with these details?"
        
        keyboard = [
            [InlineKeyboardButton("✅ Yes, Withdraw", callback_data="process_withdraw_final")],
            [InlineKeyboardButton("✏️ Change Details", callback_data="select_withdraw_method")],
            [InlineKeyboardButton("⬅️ Cancel", callback_data="show_earning_panel")]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    else:
        # Show method selection
        await show_withdrawal_method_menu(update, context)

async def show_withdrawal_method_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show method selection menu"""
    query = update.callback_query
    msg = "🏦 <b>Select Withdrawal Method:</b>"
    keyboard = [
        [InlineKeyboardButton("🇮🇳 UPI", callback_data="set_method_upi")],
        [InlineKeyboardButton("🏦 Bank Transfer", callback_data="set_method_bank")],
        [InlineKeyboardButton("⬅️ Cancel", callback_data="show_earning_panel")]
    ]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def handle_method_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle method selection and ask for details"""
    query = update.callback_query
    await query.answer()
    
    method = query.data.split("_")[2]  # upi or bank
    context.user_data["setup_withdraw_method"] = method
    context.user_data["state"] = "waiting_for_withdraw_details"
    
    if method == "upi":
        msg = "✍️ <b>Enter your UPI ID:</b>\n\nExample: `username@oksbi`"
    else:
        msg = "✍️ <b>Enter Bank Details:</b>\n\nFormat: `AccountNo, IFSC, HolderName`"
    
    msg += "\n\n<i>Send your details in the next message.</i>"
    
    keyboard = [[InlineKeyboardButton("⬅️ Cancel", callback_data="show_earning_panel")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def process_withdraw_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process final withdrawal with saved details"""
    query = update.callback_query
    await query.answer("Processing...")
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    data = USERS_COLLECTION.find_one({"user_id": user.id})
    
    earnings = data.get("earnings", 0) * DOLLAR_TO_INR
    
    # Double-check pending
    pending = WITHDRAWALS_COLLECTION.find_one({"user_id": user.id, "status": "pending"})
    if pending:
        await query.edit_message_text(
            "⏳ You already have a pending request!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
        )
        return
    
    # Create request
    method = data.get("payment_method", "unknown")
    details = data.get("payment_details", "N/A")
    payment_info = f"{method.upper()}: {details}"
    
    withdrawal = {
        "user_id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "amount_inr": earnings,
        "status": "pending",
        "request_date": datetime.now(),
        "payment_details": payment_info
    }
    
    WITHDRAWALS_COLLECTION.insert_one(withdrawal)
    
    # Notify admin
    if ADMIN_ID:
        admin_msg = f"🔄 New Withdrawal\nUser: {user.id}\nAmount: ₹{earnings:.2f}\nDetails: {payment_info}"
        await context.bot.send_message(
            ADMIN_ID, admin_msg,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Approve", callback_data=f"approve_withdraw_{user.id}"),
                 InlineKeyboardButton("❌ Reject", callback_data=f"reject_withdraw_{user.id}")]
            ])
        )
    
    # Confirm to user
    msg = MESSAGES[lang]["withdrawal_details_received"].format(
        amount=f"₹{earnings:.2f}",
        details=payment_info
    )
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    
    await send_log_message(context, f"💸 Withdrawal Request: {user.id} - ₹{earnings:.2f}")

async def show_user_pending_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's pending withdrawals"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    pendings = list(WITHDRAWALS_COLLECTION.find({"user_id": user.id, "status": "pending"}).sort("request_date", -1))
    
    if not pendings:
        msg = "✅ No pending withdrawals."
    else:
        msg = "⏳ <b>Pending Withdrawals</b>\n\n"
        for p in pendings:
            date = p["request_date"].strftime("%d %b %H:%M")
            msg += f"• ₹{p['amount_inr']:.2f} ({date})\n"
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="request_withdrawal")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

# ==================== LANGUAGE ====================

async def language_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show language selection menu"""
    query = update.callback_query
    await query.answer()
    
    lang = await get_user_lang(query.from_user.id)
    keyboard = [
        [InlineKeyboardButton("English 🇬🇧", callback_data="lang_en")],
        [InlineKeyboardButton("हिन्दी 🇮🇳", callback_data="lang_hi")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_main_menu")]
    ]
    await query.edit_message_text(
        MESSAGES[lang]["language_prompt"],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_lang_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle language selection"""
    query = update.callback_query
    await query.answer()
    
    new_lang = query.data.split("_")[1]
    await set_user_lang(query.from_user.id, new_lang)
    
    await back_to_main_menu(update, context)

# ==================== HELP ====================

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help message"""
    query = update.callback_query
    await query.answer()
    
    lang = await get_user_lang(query.from_user.id)
    msg = MESSAGES[lang]["help"].format(handle=YOUR_TELEGRAM_HANDLE)
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

# ==================== MOVIE GROUPS ====================

async def show_movie_groups_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show movie groups menu"""
    query = update.callback_query
    await query.answer()
    
    lang = await get_user_lang(query.from_user.id)
    
    keyboard = [
        [InlineKeyboardButton("🆕 New Movie Group", url=NEW_MOVIE_GROUP_LINK)],
        [InlineKeyboardButton("🎬 Movies Group", url=MOVIE_GROUP_LINK)],
        [InlineKeyboardButton("📢 All Groups", url=ALL_GROUPS_LINK)],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_main_menu")]
    ]
    
    msg = "🎬 <b>Movie Groups</b>\n\nJoin and search movies to earn!"
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

# ==================== BACK TO MAIN MENU ====================

async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return to main menu"""
    query = update.callback_query
    if query:
        await query.answer()
    
    user = update.effective_user
    lang = await get_user_lang(user.id)
    
    keyboard = [
        [InlineKeyboardButton("🎬 Movie Groups", callback_data="show_movie_groups_menu")],
        [InlineKeyboardButton("💰 Earning Panel", callback_data="show_earning_panel")],
        [InlineKeyboardButton(MESSAGES[lang]["language_choice"], callback_data="select_lang")]
    ]
    
    msg = MESSAGES[lang]["start_greeting"].format(name=user.first_name)
    
    if query and query.message:
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    elif update.message:
        await update.message.reply_html(msg, reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== TIER BENEFITS ====================

async def show_tier_benefits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show tier benefits"""
    query = update.callback_query
    await query.answer()
    
    msg = "👑 <b>Tier Benefits</b>\n\n"
    for t, info in TIERS.items():
        msg += f"Tier {t} ({info['name']}): ₹{info['rate']:.2f}/ref\n"
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

# ==================== ERROR HANDLER ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if "Message is not modified" in str(context.error):
        return
    
    if update and update.effective_chat:
        try:
            await context.bot.send_message(
                update.effective_chat.id,
                "❌ An error occurred. Please try again."
            )
        except:
            pass

# ==================== SET BOT COMMANDS ====================

async def set_bot_commands_logic(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set bot commands"""
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("earn", "Go to earning panel"),
    ]
    await context.bot.set_my_commands(commands)
    logger.info("Bot commands set")
