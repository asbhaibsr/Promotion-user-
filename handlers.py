# Handlers.py

import logging
import random
import time
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.error import TelegramError, TimedOut, Forbidden, BadRequest, RetryAfter as FloodWait 
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import asyncio

from config import (
    USERS_COLLECTION, REFERRALS_COLLECTION, SETTINGS_COLLECTION, WITHDRAWALS_COLLECTION,
    DOLLAR_TO_INR, MESSAGES, ADMIN_ID, YOUR_TELEGRAM_HANDLE, 
    SPIN_WHEEL_CONFIG, SPIN_PRIZES, SPIN_WEIGHTS, TIERS, DAILY_MISSIONS,
    CHANNEL_USERNAME, CHANNEL_ID, CHANNEL_BONUS,
    NEW_MOVIE_GROUP_LINK, MOVIE_GROUP_LINK, ALL_GROUPS_LINK, EXAMPLE_SCREENSHOT_URL,
    JOIN_CHANNEL_LINK, WITHDRAWAL_REQUIREMENTS  # <-- YEH ADD KIYA
)
from db_utils import (
    send_log_message, get_user_lang, set_user_lang, get_referral_bonus_inr, 
    get_welcome_bonus, get_user_tier, get_tier_referral_rate, 
    claim_and_update_daily_bonus, update_daily_searches_and_mission,
    get_bot_stats, pay_referrer_and_update_mission,
    get_user_stats, admin_add_money, admin_clear_earnings, admin_delete_user, clear_junk_users
)

logger = logging.getLogger(__name__)


# --- FORCE JOIN HELPER FUNCTION (NEW) ---
async def check_channel_membership(bot, user_id):
    """Helper function to strictly check channel membership."""
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
    except Exception as e:
        logger.error(f"Force Subscribe Check Failed: {e}")
        return False
    return False


# --- VERIFY CHANNEL JOIN CALLBACK (NEW) ---
async def verify_channel_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    
    is_member = await check_channel_membership(context.bot, user.id)
    
    if is_member:
        await query.answer("✅ Verified! Welcome back.", show_alert=True)
        lang = await get_user_lang(user.id)
        
        keyboard = [
            [InlineKeyboardButton("🎬 Movie Groups", callback_data="show_movie_groups_menu")],
            [InlineKeyboardButton("💰 Earning Panel", callback_data="show_earning_panel")],
            [InlineKeyboardButton(MESSAGES[lang]["language_choice"], callback_data="select_lang")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = (
            f"{MESSAGES[lang]['start_greeting']}\n\n"
            f"<b>1.</b> {MESSAGES[lang]['start_step1']}\n"
            f"<b>2.</b> {MESSAGES[lang]['start_step2']}\n"
            f"<b>3.</b> {MESSAGES[lang]['start_step3']}"
        )
        try:
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
        except:
            await context.bot.send_message(user.id, message, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await query.answer("❌ You have NOT joined yet! Join first.", show_alert=True)


async def referral_payment_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    job_data = context.job.data
    referrer_id = job_data.get("referrer_id")
    referred_user_id = job_data.get("referred_user_id") 
    
    if not referrer_id or not referred_user_id:
        logger.error("Job data missing referrer_id or referred_user_id.")
        return

    is_first_payment = False
    try:
        referral_data = REFERRALS_COLLECTION.find_one({"referred_user_id": referred_user_id, "referrer_id": referrer_id})
        if referral_data and referral_data.get("last_paid_date") is None:
            is_first_payment = True
    except Exception as e:
        logger.error(f"Error checking referral data in job: {e}")
        
    success, daily_amount = await pay_referrer_and_update_mission(context, referred_user_id, referrer_id)
    
    if success:
        logger.info(f"Job: Successfully paid DAILY search bonus to {referrer_id} from user {referred_user_id} (₹{daily_amount:.2f}).")
        
        if is_first_payment:
            try:
                bonus_inr = await get_tier_referral_rate(referrer_id)
                bonus_usd = bonus_inr / DOLLAR_TO_INR
                
                USERS_COLLECTION.update_one(
                    {"user_id": referrer_id},
                    {"$inc": {"spins_left": 1, "earnings": bonus_usd}}
                )
                
                logger.info(f"Job: Awarded FIRST referral bonus to {referrer_id}: ₹{bonus_inr:.2f} + 1 Spin.")
                
            except Exception as e:
                logger.error(f"Job: Failed to award first referral bonus/spin to {referrer_id}: {e}")
    else:
        logger.warning(f"Job: Daily referral payment for {referred_user_id} to {referrer_id} failed or already processed.")


async def clear_payment_state_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    job_data = context.job.data
    user_id = job_data["user_id"]
    
    user_context = context.application.user_data.get(user_id)
    
    if user_context and user_context.get("state") == "waiting_for_payment_details":
        user_context["state"] = None
        lang = await get_user_lang(user_id)
        try:
            await context.bot.send_message(
                chat_id=user_id, 
                text=MESSAGES[lang].get("withdrawal_session_expired", "Session expired. Try again.")
            )
        except Exception as e:
            logger.warning(f"Could not send session expired message to {user_id}: {e}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    error_detail = str(context.error)
    if "Message is not modified" in error_detail:
        logger.warning("Ignoring 'Message is not modified' error.")
        if ADMIN_ID:
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"⚠️ **Bot Warning: Message Not Modified**:\n\n`{error_detail}`\n\n**Update:** `{update}`",
                    parse_mode='Markdown'
                )
            except Exception:
                pass
        return

    try:
        error_msg = f"❌ An error occurred! Details: {context.error}"
        if update and update.effective_chat:
            if update.effective_chat.type == 'private' or (update.effective_chat.type != 'private' and update.message and update.message.text and update.message.text.startswith('/')):
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ **Oops!** Something went wrong. The error has been logged.",
                    parse_mode='Markdown'
                )
        
        if ADMIN_ID:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🚨 **Bot Error**:\n\n`{error_msg}`\n\n**Update:** `{update}`",
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Failed to handle error: {e}")


# --- UPDATED START COMMAND WITH STRICT FORCE JOIN ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    full_name = user.first_name + (f" {user.last_name}" if user.last_name else "")
    username_display = f"<a href='tg://user?id={user.id}'>{full_name}</a>"
    
    # --- FORCE JOIN CHECK (STRICT) ---
    is_member = await check_channel_membership(context.bot, user.id)
    
    if not is_member:
        msg = (
            f"👋 <b>Hello {user.first_name}!</b>\n\n"
            f"⛔️ <b>Access Denied!</b>\n"
            f"You must join our official channel to use this bot.\n\n"
            f"👇 <b>Click below to Join & Verify:</b>"
        )
        keyboard = [
            [InlineKeyboardButton("🚀 Join Channel", url=JOIN_CHANNEL_LINK)],
            [InlineKeyboardButton("✅ Verify Join", callback_data="verify_channel_join")]
        ]
        if update.message:
            await update.message.reply_html(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return 
    # --- END FORCE JOIN CHECK ---
    
    referral_id_str = context.args[0].replace("ref_", "") if context.args and context.args[0].startswith("ref_") else None
    referral_id = int(referral_id_str) if referral_id_str and referral_id_str.isdigit() else None

    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    is_new_user = not user_data

    update_data = {
        "$setOnInsert": {
            "user_id": user.id,
            "username": user.username,
            "full_name": full_name,
            "lang": "en",
            "is_approved": True,
            "earnings": 0.0,
            "last_checkin_date": None,
            "daily_bonus_streak": 0,
            "missions_completed": {},
            "welcome_bonus_received": False,
            "joined_date": datetime.now(),
            "daily_searches": 0, 
            "last_search_date": None,
            "channel_bonus_received": False, 
            "spins_left": SPIN_WHEEL_CONFIG["initial_free_spins"],
            "monthly_referrals": 0
        }
    }
    
    USERS_COLLECTION.update_one(
        {"user_id": user.id},
        update_data,
        upsert=True
    )

    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    lang = user_data.get("lang", "en")
    
    if is_new_user:
        log_msg = f"👤 <b>New User</b>\nID: <code>{user.id}</code>\nName: {full_name}\nUsername: {username_display}"
        
        if not user_data.get("welcome_bonus_received", False):
            welcome_bonus_inr = await get_welcome_bonus()
            welcome_bonus_usd = welcome_bonus_inr / DOLLAR_TO_INR
            
            USERS_COLLECTION.update_one(
                {"user_id": user.id},
                {"$inc": {"earnings": welcome_bonus_usd}, "$set": {"welcome_bonus_received": True}}
            )
            try:
                await update.message.reply_html(MESSAGES[lang]["welcome_bonus_received"].format(amount=welcome_bonus_inr))
            except Exception:
                 pass
            log_msg += f"\n🎁 Welcome Bonus: ₹{welcome_bonus_inr:.2f}"
            log_msg += f"\n🎰 Initial Spins: {SPIN_WHEEL_CONFIG['initial_free_spins']}"

        if referral_id and referral_id != user.id:
            existing_referral = REFERRALS_COLLECTION.find_one({"referred_user_id": user.id})
            
            if not existing_referral:
                REFERRALS_COLLECTION.insert_one({
                    "referrer_id": referral_id,
                    "referred_user_id": user.id,
                    "referred_username": user.username,
                    "join_date": datetime.now(),
                    "last_paid_date": None, 
                    "paid_search_count_today": 0 
                })
                
                USERS_COLLECTION.update_one(
                    {"user_id": referral_id},
                    {"$inc": {"monthly_referrals": 1}}
                )
                
                log_msg += f"\n🔗 Referred by: <code>{referral_id}</code> (Referral Recorded, Payment Pending on Search)"

                try:
                    referrer_lang = await get_user_lang(referral_id)
                    await context.bot.send_message(
                        chat_id=referral_id,
                        text=MESSAGES[referrer_lang]["new_referral_notification"].format(
                            full_name=full_name, username=username_display, bonus=0.00 
                        ),
                        parse_mode='HTML'
                    )
                except (TelegramError, TimedOut) as e:
                    logger.error(f"Could not notify referrer {referral_id}: {e}")
            else:
                log_msg += f"\n❌ Referral ignored (already referred by {existing_referral['referrer_id']})"

        await send_log_message(context, log_msg)

    keyboard = [
        [InlineKeyboardButton("🎬 Movie Groups", callback_data="show_movie_groups_menu")],
        [InlineKeyboardButton("💰 Earning Panel", callback_data="show_earning_panel")],
        [InlineKeyboardButton(MESSAGES[lang]["language_choice"], callback_data="select_lang")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        f"{MESSAGES[lang]['start_greeting']}\n\n"
        f"<b>1.</b> {MESSAGES[lang]['start_step1']}\n"
        f"<b>2.</b> {MESSAGES[lang]['start_step2']}\n"
        f"<b>3.</b> {MESSAGES[lang]['start_step3']}"
    )
    
    if update.message:
        await update.message.reply_html(message, reply_markup=reply_markup)


async def earn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        lang = await get_user_lang(update.effective_user.id)
        keyboard = [[InlineKeyboardButton("💰 Earning Panel", callback_data="show_earning_panel")]]
        await update.message.reply_html(MESSAGES[lang]["earning_panel_message"], reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
        
    chat_type = update.effective_chat.type
    if chat_type not in ["group", "supergroup"]:
        return
        
    user = update.effective_user
    
    bot_info = await context.bot.get_me()
    if user.id == bot_info.id:
        return
        
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    if not user_data:
        return 

    await update_daily_searches_and_mission(user.id)
    
    referral_data = REFERRALS_COLLECTION.find_one({"referred_user_id": user.id})
    
    if referral_data:
        referrer_id = referral_data["referrer_id"]
        
        if referrer_id == user.id:
            logger.warning(f"Self-referral detected and ignored for user {user.id}")
            return
            
        last_paid_date = referral_data.get("last_paid_date")
        today = datetime.now().date()
        
        if last_paid_date and isinstance(last_paid_date, datetime) and last_paid_date.date() == today:
            logger.info(f"Referral payment for user {user.id} to referrer {referrer_id} already processed today. Skipping job scheduling.")
            return

        job_name = f"pay_{user.id}" 
        existing_jobs = context.job_queue.get_jobs_by_name(job_name)
        
        if not existing_jobs:
            context.job_queue.run_once(
                referral_payment_job, 
                300, 
                chat_id=user.id, 
                user_id=user.id, 
                data={"referrer_id": referrer_id, "referred_user_id": user.id}, 
                name=job_name
            )
            logger.info(f"Payment task scheduled for user {user.id} (referrer {referrer_id}). Job Name: {job_name}")
        else:
             logger.info(f"Payment task for {user.id} already pending. Ignoring job creation.")
    

async def show_earning_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    
    if not query:
        logger.warning("show_earning_panel called without a callback query.")
        return 
        
    user = query.from_user
    lang = await get_user_lang(user.id)
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    
    await query.answer()

    if not user_data:
        await query.answer("User data not found.", show_alert=True)
        if query.message: 
             try:
                 await query.edit_message_text("User data not found.")
             except Exception:
                  await context.bot.send_message(user.id, "User data not found.")
        return
    
    earnings_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR
    
    referrals_count = REFERRALS_COLLECTION.count_documents({"referrer_id": user.id, "referred_user_id": {"$ne": user.id}})
    user_tier = await get_user_tier(user.id)
    tier_info = TIERS.get(user_tier, TIERS[1]) 
    spins_left = user_data.get("spins_left", 0)
    
    message = (
        f"<b>💰 Earning Panel</b>\n\n"
        f"🏅 <b>Current Tier:</b> {tier_info['name']} (Level {user_tier})\n"
        f"💵 <b>Balance:</b> ₹{earnings_inr:.2f}\n"
        f"👥 <b>Total Referrals:</b> {referrals_count}\n"
        f"🎯 <b>Referral Rate:</b> ₹{tier_info['rate']:.2f}/referral\n\n"
        f"<i>Earn more to unlock higher tiers with better rates!</i>"
    )
    
    channel_button_text = f"🎁 Join Channel & Claim ₹{CHANNEL_BONUS:.2f}"
    if user_data.get("channel_bonus_received"):
        channel_button_text = f"✅ Channel Bonus Claimed (₹{CHANNEL_BONUS:.2f})"

    keyboard = [
        [InlineKeyboardButton("🏆 Earning Leaderboard (Top 10)", callback_data="show_leaderboard")],
        [InlineKeyboardButton("🔗 My Refer Link", callback_data="show_refer_link"), 
         InlineKeyboardButton("👥 My Referrals", callback_data="show_my_referrals")],
        [InlineKeyboardButton("🎁 Daily Bonus", callback_data="claim_daily_bonus"),
         InlineKeyboardButton("🎯 Daily Missions", callback_data="show_missions")],
        [InlineKeyboardButton(MESSAGES[lang]["spin_wheel_button"].format(spins_left=spins_left), callback_data="show_spin_panel"),
         InlineKeyboardButton("📈 Tier Benefits", callback_data="show_tier_benefits")], 
        [InlineKeyboardButton("🎮 Earning Games", callback_data="show_games_menu")],
        [InlineKeyboardButton("💸 Request Withdrawal", callback_data="show_withdraw_details_new"),
         InlineKeyboardButton(channel_button_text, callback_data="claim_channel_bonus")],
        [InlineKeyboardButton("🆘 Help", callback_data="show_help"),
         InlineKeyboardButton("⬅️ Back", callback_data="back_to_main_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query.message: 
        try:
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
        except TelegramError as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Error editing message in show_earning_panel: {e}")
            pass


async def show_my_referrals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message:
        return
        
    user = query.from_user
    lang = await get_user_lang(user.id)
    await query.answer()

    referral_records = list(REFERRALS_COLLECTION.find({"referrer_id": user.id, "referred_user_id": {"$ne": user.id}}).sort("join_date", -1))
    
    total_referrals = len(referral_records)
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    paid_searches_today_count = 0
    for ref_record in referral_records:
        last_paid = ref_record.get("last_paid_date")
        if last_paid and isinstance(last_paid, datetime) and last_paid.date() == today_start.date():
             paid_searches_today_count += 1
        
    
    message = f"👥 <b>My Referrals</b>\n\n"
    message += f"🔗 Total Referrals: <b>{total_referrals}</b>\n"
    message += f"✅ Paid Referrals Today: <b>{paid_searches_today_count}</b>\n"
    
    if total_referrals == 0:
        message += "\n❌ You have not referred anyone yet. Share your link now!"
    else:
        message += f"ℹ️ <i>Showing last 10 referrals.</i>\n\n"
        
        referred_ids = [ref['referred_user_id'] for ref in referral_records[:10]]
        referred_users_data = USERS_COLLECTION.find({"user_id": {"$in": referred_ids}})
        
        user_names_map = {
            user_doc["user_id"]: user_doc.get("full_name", f"User {user_doc['user_id']}")
            for user_doc in referred_users_data
        }

        for i, ref_record in enumerate(referral_records[:10]):
            referred_id = ref_record['referred_user_id']
            join_date = ref_record['join_date'].strftime("%d %b %Y")
            last_paid = ref_record.get('last_paid_date')
            
            status_emoji = "❌ (Pending Search)"
            if last_paid and last_paid.date() == today_start.date():
                 status_emoji = "✅ (Paid Today)"
            elif last_paid:
                 if (today_start.date() - last_paid.date()).days == 1:
                     status_emoji = f"⚠️ (Last Paid: Yesterday)"
                 else:
                     status_emoji = f"⚠️ (Last Paid: {last_paid.strftime('%d %b')})"

            full_name = user_names_map.get(referred_id, f"User {referred_id}")
            display_name_link = f"<a href='tg://user?id={referred_id}'>{full_name}</a>"
            
            message += f"🔸 <b>{i+1}. {display_name_link}</b>\n"
            message += f"   - Joined: {join_date}\n"
            message += f"   - Status: {status_emoji}\n"

    keyboard = [
        [InlineKeyboardButton("💡 Referral Example", callback_data="show_refer_example")],
        [InlineKeyboardButton("⬅️ Back to Earning Panel", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def show_refer_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
        
    await query.answer()
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    referral_link = f"https://t.me/{bot_username}?start=ref_{user.id}"
    
    max_tier_rate = TIERS[max(TIERS.keys())]["rate"]
    
    message = (
        f"<b>🤑 ₹{max_tier_rate:.2f} Per Referral! Get Rich Fast!</b>\n\n"
        f"{MESSAGES[lang]['ref_link_message'].format(referral_link=referral_link, tier_rate=max_tier_rate)}\n\n"
        f"<b>💡 Secret Tip:</b> Your friends must <b>search one movie</b> in the group to unlock your daily earning! Share this now!"
    )

    share_message_text = (
        f"🎉 <b>सबसे बेहतरीन मूवी बॉट को अभी जॉइन करें और रोज़ कमाएँ!</b>\n\n"
        f"🎬 हर नई हॉलीवुड/बॉलीवुड मूवी पाएँ!\n"
        f"💰 <b>₹{await get_welcome_bonus():.2f} वेलकम बोनस</b> तुरंत पाएँ!\n"
        f"💸 <b>हर रेफ़र पर ₹{max_tier_rate:.2f} तक</b> कमाएँ! (जब आपका दोस्त मूवी सर्च करेगा)\n\n"
        f"🚀 <b>मेरी स्पेशल लिंक से जॉइन करें और अपनी कमाई शुरू करें:</b> {referral_link}"
    )
    
    encoded_text = urllib.parse.quote_plus(share_message_text)

    keyboard = [
        [InlineKeyboardButton("🔗 Share Your Link Now!", url=f"https://t.me/share/url?url={referral_link}&text={encoded_text}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query.message:
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def claim_daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: 
        return
        
    user = query.from_user
    lang = await get_user_lang(user.id)
    username_display = f"@{user.username}" if user.username else f"<code>{user.id}</code>"
    
    bonus_amount, new_balance_inr, streak, already_claimed = await claim_and_update_daily_bonus(user.id)
    
    if already_claimed:
        await query.answer(MESSAGES[lang]["daily_bonus_already_claimed"], show_alert=True)
        try:
            await query.edit_message_text(
                MESSAGES[lang]["daily_bonus_already_claimed"],
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
            )
        except TelegramError as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Error editing message in claim_daily_bonus (already_claimed): {e}")
            pass
        return
    
    if bonus_amount is None:
        await query.answer("User data not found or error occurred.", show_alert=True)
        return

    await query.answer("Claiming bonus...")

    streak_message = f"🔥 You are on a {streak}-day streak! Keep it up for bigger bonuses!"
    if lang == "hi":
        streak_message = f"🔥 आप {streak}-दिन की स्ट्रीक पर हैं! बड़े बोनस के लिए इसे जारी रखें!"
        
    keyboard = [
        [InlineKeyboardButton("💰 Earn More", callback_data="show_earning_panel")],
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        MESSAGES[lang]["daily_bonus_success"].format(
            bonus_amount=bonus_amount,
            new_balance=new_balance_inr,
            streak_message=streak_message
        ),
        reply_markup=reply_markup
    )
    
    log_msg = f"🎁 <b>Daily Bonus</b>\nUser: {username_display}\nAmount: ₹{bonus_amount:.2f}\nStreak: {streak} days\nNew Balance: ₹{new_balance_inr:.2f}"
    await send_log_message(context, log_msg)


async def show_spin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: 
        return
        
    await query.answer()
    
    user = query.from_user
    lang = await get_user_lang(user.id)
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    
    spins_left = user_data.get("spins_left", 0)

    message = MESSAGES[lang]["spin_wheel_title"].format(spins_left=spins_left)
    
    if spins_left > 0:
        keyboard = [
            [InlineKeyboardButton(MESSAGES[lang]["spin_wheel_button"].format(spins_left=spins_left), callback_data="perform_spin")],
            [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
        ]
    else:
        message += "\n\n❌ <b>No Spins Left!</b> Get 1 free spin when your referred friend searches a movie in the group."
        keyboard = [
            [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
        ]
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def perform_spin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: 
        return
        
    user = query.from_user
    lang = await get_user_lang(user.id)
    username_display = f"@{user.username}" if user.username else f"<code>{user.id}</code>"

    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    if not user_data:
        await query.answer("User data not found.", show_alert=True)
        return

    spins_left = user_data.get("spins_left", 0)
    
    if spins_left <= 0:
        await query.answer(MESSAGES[lang]["spin_wheel_insufficient_spins"], show_alert=True)
        await show_spin_panel(update, context) 
        return
        
    await query.answer("Spinning the wheel...") 

    result = USERS_COLLECTION.find_one_and_update(
        {"user_id": user.id, "spins_left": {"$gte": 1}},
        {"$inc": {"spins_left": -1}},
        return_document=True
    )
    
    if not result:
        await query.edit_message_text(
            "❌ <b>Failed to deduct spin. Try again.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]),
            parse_mode='HTML'
        )
        return
        
    spins_left_after_deduct = result.get("spins_left", 0)

    button_prizes = list(SPIN_PRIZES)
    random.shuffle(button_prizes)
    temp_prizes = [p for p in SPIN_PRIZES if p > 0.0]
    while len(temp_prizes) < 8: temp_prizes.append(0.0) 
    
    btn_list = [InlineKeyboardButton(f"₹{p:.2f}", callback_data="spin_fake_btn") for p in temp_prizes[:8]]
    middle_btn = InlineKeyboardButton("🎡 Spinning...", callback_data="spin_fake_btn")
    spin_keyboard = [ [btn_list[0], btn_list[1], btn_list[2]], [btn_list[3], middle_btn, btn_list[4]], [btn_list[5], btn_list[6], btn_list[7]] ]
    reply_markup = InlineKeyboardMarkup(spin_keyboard)

    try:
        await query.edit_message_text(text=MESSAGES[lang]["spin_wheel_animating"], reply_markup=reply_markup, parse_mode='HTML')
    except TelegramError: pass 

    await asyncio.sleep(3)

    prize_inr = random.choices(SPIN_PRIZES, weights=SPIN_WEIGHTS, k=1)[0]
    prize_usd = prize_inr / DOLLAR_TO_INR
    
    USERS_COLLECTION.update_one({"user_id": user.id}, {"$inc": {"earnings": prize_usd}})
    updated_data = USERS_COLLECTION.find_one({"user_id": user.id})
    final_balance_usd = updated_data.get("earnings", 0.0) 
    final_balance_inr = final_balance_usd * DOLLAR_TO_INR

    log_msg = f"🎡 <b>Spin Wheel</b>\nUser: {username_display}\nCost: 1 Spin\n"
    
    if prize_inr > 0:
        message = MESSAGES[lang]["spin_wheel_win"].format(amount=prize_inr, new_balance=final_balance_inr, spins_left=spins_left_after_deduct)
        log_msg += f"Win: ₹{prize_inr:.2f}"
    else:
        message = MESSAGES[lang]["spin_wheel_lose"].format(new_balance=final_balance_inr, spins_left=spins_left_after_deduct)
        log_msg += "Win: ₹0.00 (Lost)"
    
    log_msg += f"\nRemaining Spins: {spins_left_after_deduct}\nNew Balance: ₹{final_balance_inr:.2f}"
    await send_log_message(context, log_msg)

    keyboard = [
        [InlineKeyboardButton(MESSAGES[lang]["spin_wheel_button"].format(spins_left=spins_left_after_deduct), callback_data="perform_spin")],
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.edit_message_text(
        chat_id=query.message.chat_id, message_id=query.message.message_id, text=message, 
        reply_markup=reply_markup, parse_mode='HTML'
    )


async def spin_fake_btn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query: 
        await query.answer("🎡 Spinning... Please wait!", show_alert=False)


async def show_missions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: 
        return
        
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    if not user_data:
        await query.answer("User data not found.", show_alert=True)
        return
        
    await query.answer()
    
    today = datetime.now().date()
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    last_search_date = user_data.get("last_search_date")
    last_checkin_date = user_data.get("last_checkin_date")
    
    if not last_search_date or not isinstance(last_search_date, datetime) or last_search_date.date() != today:
        USERS_COLLECTION.update_one(
            {"user_id": user.id},
            {"$set": {"daily_searches": 0, "missions_completed.search_3_movies": False}}
        )
    
    is_bonus_claimed_today = last_checkin_date and isinstance(last_checkin_date, datetime) and last_checkin_date.date() == today
    if not is_bonus_claimed_today:
        USERS_COLLECTION.update_one(
            {"user_id": user.id},
            {"$set": {"missions_completed.claim_daily_bonus": False}}
        )
        
    paid_searches_today_count = 0
    referral_records = list(REFERRALS_COLLECTION.find({"referrer_id": user.id, "referred_user_id": {"$ne": user.id}}))
    
    for ref_record in referral_records:
        last_paid = ref_record.get("last_paid_date")
        if last_paid and isinstance(last_paid, datetime) and last_paid.date() == today_start.date():
             paid_searches_today_count += 1
        
    referrals_today_count = REFERRALS_COLLECTION.count_documents({
        "referrer_id": user.id,
        "referred_user_id": {"$ne": user.id}, 
        "join_date": {"$gte": today_start}
    })
    
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    missions_completed = user_data.get("missions_completed", {})
    daily_searches = user_data.get("daily_searches", 0) 
    
    message = f"{MESSAGES[lang]['missions_title']}\n\n"
    newly_completed_message = ""
    total_reward = 0.0

    mission_key = "search_3_movies"
    mission = DAILY_MISSIONS[mission_key]
    name = mission["name"] if lang == "en" else mission["name_hi"]
    
    if paid_searches_today_count >= mission['target'] and not missions_completed.get(mission_key):
        reward_usd = mission["reward"] / DOLLAR_TO_INR
        total_reward += mission["reward"]
        USERS_COLLECTION.update_one(
            {"user_id": user.id},
            {
                "$inc": {"earnings": reward_usd, "spins_left": 1},
                "$set": {f"missions_completed.{mission_key}": True}
            }
        )
        newly_completed_message += f"✅ <b>{name}</b>: +₹{mission['reward']:.2f} +1 Spin 🎰\n"
        missions_completed[mission_key] = True 
        message += f"✅ {name} ({mission['target']}/{mission['target']}) [<b>Completed</b>]\n"
    elif missions_completed.get(mission_key):
        message += f"✅ {name} ({mission['target']}/{mission['target']}) [<b>Completed</b>]\n"
    else:
        message += f"⏳ {name} ({min(paid_searches_today_count, mission['target'])}/{mission['target']}) [In Progress]\n"
        message += f"   - <i>Tip: Your referred user must search a movie for this count to increase!</i>\n"
        
    mission_key = "refer_2_friends"
    mission = DAILY_MISSIONS[mission_key]
    name = mission["name"] if lang == "en" else mission["name_hi"]
    
    if referrals_today_count >= mission['target'] and not missions_completed.get(mission_key):
        reward_usd = mission["reward"] / DOLLAR_TO_INR
        total_reward += mission["reward"]
        USERS_COLLECTION.update_one(
            {"user_id": user.id},
            {
                "$inc": {"earnings": reward_usd, "spins_left": 1},
                "$set": {f"missions_completed.{mission_key}": True}
            }
        )
        newly_completed_message += f"✅ <b>{name}</b>: +₹{mission['reward']:.2f} +1 Spin 🎰\n"
        missions_completed[mission_key] = True 
        message += f"✅ {name} ({mission['target']}/{mission['target']}) [<b>Completed</b>]\n"
    elif missions_completed.get(mission_key):
        message += f"✅ {name} ({mission['target']}/{mission['target']}) [<b>Completed</b>]\n"
    else:
        message += f"⏳ {name} ({min(referrals_today_count, mission['target'])}/{mission['target']}) [In Progress]\n"

    mission_key = "claim_daily_bonus"
    mission = DAILY_MISSIONS[mission_key]
    name = mission["name"] if lang == "en" else mission["name_hi"]
    
    if is_bonus_claimed_today:
        if not missions_completed.get(mission_key):
            reward_usd = mission["reward"] / DOLLAR_TO_INR
            total_reward += mission["reward"]
            USERS_COLLECTION.update_one(
                {"user_id": user.id},
                {
                    "$inc": {"earnings": reward_usd, "spins_left": 1},
                    "$set": {f"missions_completed.{mission_key}": True}
                }
            )
            newly_completed_message += f"✅ <b>{name}</b>: +₹{mission['reward']:.2f} +1 Spin 🎰\n"
            missions_completed[mission_key] = True 
            message += f"✅ {name} [<b>Completed</b>]\n"
        else:
            message += f"✅ {name} [<b>Completed</b>]\n"
    else:
        message += f"⏳ {name} [In Progress]\n"


    if total_reward > 0:
        updated_data = USERS_COLLECTION.find_one({"user_id": user.id})
        updated_earnings_inr = updated_data.get("earnings", 0.0) * DOLLAR_TO_INR
        message += "\n"
        message += f"🎉 <b>Mission Rewards Claimed!</b>\n"
        message += newly_completed_message
        message += f"New Balance: ₹{updated_earnings_inr:.2f}"

    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


# --- UPDATED WITHDRAWAL REQUEST WITH TIERED REQUIREMENTS ---
async def request_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: 
        return
        
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    if not user_data:
        await query.answer("User data not found.", show_alert=True)
        return
        
    await query.answer("Checking requirements...")

    earnings_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR
    
    # Minimum balance check
    if earnings_inr < 80:
        await query.edit_message_text(
            MESSAGES[lang]["withdrawal_insufficient"],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
        )
        return

    # --- NEW: TIERED REFERRAL CHECK ---
    referrals_count = REFERRALS_COLLECTION.count_documents({"referrer_id": user.id})
    required_referrals = 0
    
    # Find required referrals based on balance
    for requirement in WITHDRAWAL_REQUIREMENTS:
        if earnings_inr >= requirement["min_balance"]:
            required_referrals = requirement["required_refs"]
            break 
    
    # Minimum requirement is 20 referrals (as per config)
    if referrals_count < required_referrals:
        msg = (
            f"❌ <b>Insufficient Referrals!</b>\n\n"
            f"Your balance is <b>₹{earnings_inr:.2f}</b>, you need <b>{required_referrals} referrals</b> to withdraw.\n\n"
            f"👤 Your Current Referrals: {referrals_count}/{required_referrals}"
        )
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]), parse_mode='HTML')
        return
    # --- END NEW CHECK ---

    # Pending Request Check
    existing_request = WITHDRAWALS_COLLECTION.find_one({"user_id": user.id, "status": "pending"})
    if existing_request:
        try:
            await query.edit_message_text(
                "❌ <b>Request Already Pending!</b>\n\nYour previous withdrawal request is still being processed.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]),
                parse_mode='HTML'
            )
        except TelegramError as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Error editing message in request_withdrawal (already pending): {e}")
            pass
        return
    
    # All checks passed - Ask for payment details
    context.user_data["state"] = "waiting_for_payment_details"
    context.user_data["withdrawal_amount"] = earnings_inr
    
    job_name = f"clear_payment_state_{user.id}"
    
    existing_jobs = context.job_queue.get_jobs_by_name(job_name)
    for job in existing_jobs:
        job.schedule_removal()

    context.job_queue.run_once(
        clear_payment_state_job, 
        30,
        chat_id=user.id, 
        data={"user_id": user.id}, 
        name=job_name
    )

    await query.edit_message_text(
        MESSAGES[lang]["withdrawal_prompt_details"],
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]),
        parse_mode='HTML'
    )
# --- END WITHDRAWAL UPDATE ---


async def language_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: 
        return
        
    await query.answer()
    lang = await get_user_lang(query.from_user.id)
    
    keyboard = [
        [InlineKeyboardButton("English 🇬🇧", callback_data="lang_en")],
        [InlineKeyboardButton("हिन्दी 🇮🇳", callback_data="lang_hi")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        message_text = MESSAGES[lang]["language_prompt"]
    except KeyError:
        logger.error(f"KeyError: 'language_prompt' missing for language '{lang}'. Using fallback.")
        message_text = "Please select your language:"

    await query.edit_message_text(message_text, reply_markup=reply_markup)


async def handle_lang_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
        
    await query.answer()
    new_lang = query.data.split("_")[1]
    
    await set_user_lang(query.from_user.id, new_lang)
    
    await back_to_main_menu(update, context) 


async def show_withdraw_details_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: 
        return
        
    await query.answer()
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    
    pending_count = WITHDRAWALS_COLLECTION.count_documents({"user_id": user.id, "status": "pending"})
    
    earnings_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR
    
    message = MESSAGES[lang]["withdrawal_details_message"].format(
        balance=f"₹{earnings_inr:.2f}"
    )
    
    pending_button = InlineKeyboardButton(f"⏳ Pending Withdrawals ({pending_count})", callback_data="show_user_pending_withdrawals")
    
    keyboard = [
        [InlineKeyboardButton("💸 Request Withdrawal (Min ₹80)", callback_data="request_withdrawal")],
        [pending_button], 
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def show_user_pending_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message:
        return
        
    user = query.from_user
    lang = await get_user_lang(user.id)
    await query.answer()

    pending_requests = WITHDRAWALS_COLLECTION.find({"user_id": user.id, "status": "pending"}).sort("request_date", -1)
    pending_count = WITHDRAWALS_COLLECTION.count_documents({"user_id": user.id, "status": "pending"})

    message = f"<b>💸 Your Pending Withdrawal Requests ({pending_count})</b>\n\n"
    
    if pending_count == 0:
        message += "✅ You have no pending withdrawal requests."
    else:
        for i, request in enumerate(pending_requests):
            date_str = request["request_date"].strftime("%d %b %Y %H:%M")
            message += f"**{i+1}.** Amount: ₹{request['amount_inr']:.2f}\n"
            message += f"   - Requested On: {date_str}\n"
            message += f"   - Status: ⏳ Pending\n\n"
            
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_withdraw_details_new")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def show_movie_groups_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: 
        return
        
    await query.answer()

    lang = await get_user_lang(query.from_user.id)

    keyboard = [
        [InlineKeyboardButton("🆕 New Movie Group", url=NEW_MOVIE_GROUP_LINK)],
        [InlineKeyboardButton("Join Movies Group", url=MOVIE_GROUP_LINK)],
        [InlineKeyboardButton("Join All Movie Groups", url=ALL_GROUPS_LINK)],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = (
        f"<b>🎬 Movie Groups</b>\n\n"
        f"{MESSAGES[lang]['start_step1']}"
    )

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    
    if not query and not update.message:
        logger.warning("back_to_main_menu called without update.message or update.callback_query.")
        return

    user = update.effective_user
    lang = await get_user_lang(user.id)
    
    if query:
        await query.answer()

    keyboard = [
        [InlineKeyboardButton("🎬 Movie Groups", callback_data="show_movie_groups_menu")],
        [InlineKeyboardButton("💰 Earning Panel", callback_data="show_earning_panel")],
        [InlineKeyboardButton(MESSAGES[lang]["language_choice"], callback_data="select_lang")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = (
        f"{MESSAGES[lang]['start_greeting']}\n\n"
        f"<b>1.</b> {MESSAGES[lang]['start_step1']}\n"
        f"<b>2.</b> {MESSAGES[lang]['start_step2']}\n"
        f"<b>3.</b> {MESSAGES[lang]['start_step3']}"
    )
    
    if query: 
        if query.message: 
            if query.message.photo:
                try:
                    await query.message.delete()
                except Exception as e:
                    logger.warning(f"Failed to delete photo message in back_to_main_menu: {e}")
                    pass
                    
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=message, 
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            else:
                try: 
                    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
                except TelegramError as e:
                    if "Message is not modified" not in str(e):
                        logger.error(f"Error editing message in back_to_main_menu: {e}")
                    pass
        else:
             await context.bot.send_message(chat_id=user.id, text=message, reply_markup=reply_markup, parse_mode='HTML')
             
    elif update.message: 
        await update.message.reply_html(message, reply_markup=reply_markup)


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: 
        return
        
    await query.answer()
    lang = await get_user_lang(query.from_user.id)
    
    message = MESSAGES[lang].get("help_message", MESSAGES["en"]["help_message"]).format(
        telegram_handle=YOUR_TELEGRAM_HANDLE
    )
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def show_tier_benefits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: 
        return
        
    await query.answer()
    lang = await get_user_lang(query.from_user.id)
    
    message = MESSAGES[lang].get("tier_benefits_message", MESSAGES["en"]["tier_benefits_message"])
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def show_refer_example(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: 
        return
        
    await query.answer()
    user = query.from_user
    lang = await get_user_lang(query.from_user.id)
    
    message_template = MESSAGES[lang].get("refer_example_message", MESSAGES["en"]["refer_example_message"])
    
    rate = TIERS[max(TIERS.keys())]["rate"]
    message = message_template.format(rate=rate)
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if EXAMPLE_SCREENSHOT_URL:
        try:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=EXAMPLE_SCREENSHOT_URL,
                caption=message,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            try:
                await query.message.delete()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Failed to send photo in show_refer_example: {e}")
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


# --- UPDATED CLAIM CHANNEL BONUS ---
async def claim_channel_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: 
        return
        
    user = query.from_user
    lang = await get_user_lang(user.id)
    username_display = f"@{user.username}" if user.username else f"<code>{user.id}</code>"
    
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    
    if user_data.get("channel_bonus_received"):
        await query.answer(MESSAGES[lang]["channel_already_claimed"], show_alert=True)
        await show_earning_panel(update, context) 
        return
        
    await query.answer("Checking channel membership...")
    
    is_member = False
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user.id)
        is_member = member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Error checking channel membership for {user.id}: {e}")

        await send_log_message(
            context, 
            f"🚨 **Channel Check Error!**\n\nFailed to check membership for User <code>{user.id}</code> in channel <code>{CHANNEL_ID}</code>.\nError: <code>{e}</code>\n\n<b>FIX:</b> Ensure bot is admin in the channel."
        )

        await query.answer(MESSAGES[lang]["channel_bonus_error"].format(channel=CHANNEL_USERNAME), show_alert=True)

        join_button = InlineKeyboardButton("🔗 Join Channel", url=JOIN_CHANNEL_LINK)
        retry_button = InlineKeyboardButton("🔄 Try Again", callback_data="claim_channel_bonus")
        back_button = InlineKeyboardButton("⬅️ Back to Earning Panel", callback_data="show_earning_panel")
        keyboard = [[join_button, retry_button], [back_button]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await query.edit_message_text(
                MESSAGES[lang]["channel_bonus_error"].format(channel=CHANNEL_USERNAME), 
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except TelegramError: pass

        return
        
    if is_member:
        bonus_usd = CHANNEL_BONUS / DOLLAR_TO_INR
        
        result = USERS_COLLECTION.find_one_and_update(
            {"user_id": user.id, "channel_bonus_received": False},
            {"$inc": {"earnings": bonus_usd}, "$set": {"channel_bonus_received": True}},
            return_document=True
        )
        
        if result:
            new_balance_inr = result.get("earnings", 0.0) * DOLLAR_TO_INR
            await query.edit_message_text(
                MESSAGES[lang]["channel_bonus_claimed"].format(amount=CHANNEL_BONUS, new_balance=new_balance_inr, channel=CHANNEL_USERNAME), 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
            )
            log_msg = f"🎁 <b>Channel Bonus Claimed</b>\nUser: {username_display}\nAmount: ₹{CHANNEL_BONUS:.2f}\nNew Balance: ₹{new_balance_inr:.2f}"
            await send_log_message(context, log_msg)
            return
        
    join_button = InlineKeyboardButton("🔗 Join Channel", url=JOIN_CHANNEL_LINK)
    retry_button = InlineKeyboardButton("🔄 Try Again", callback_data="claim_channel_bonus")
    back_button = InlineKeyboardButton("⬅️ Back to Earning Panel", callback_data="show_earning_panel")
    
    keyboard = [
        [join_button, retry_button],
        [back_button] 
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(
            MESSAGES[lang]["channel_bonus_failure"].format(channel=CHANNEL_USERNAME), 
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    except TelegramError as e:
        if "Message is not modified" not in str(e):
            logger.error(f"Error editing message in claim_channel_bonus (failure): {e}")
        pass
# --- END CHANNEL BONUS UPDATE ---


# --- UPDATED LEADERBOARD FUNCTION ---
async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message:
        return
        
    await query.answer()
    user_id = query.from_user.id
    lang = await get_user_lang(user_id)
    
    user_data_for_rank = USERS_COLLECTION.find_one({"user_id": user_id}, {"monthly_referrals": 1})
    user_refs = user_data_for_rank.get("monthly_referrals", 0) if user_data_for_rank else 0
    
    user_rank = USERS_COLLECTION.count_documents({"monthly_referrals": {"$gt": user_refs}}) + 1
    
    top_users_cursor = USERS_COLLECTION.find().sort("monthly_referrals", -1).limit(10)
    
    message = "🏆 <b>Earning Leaderboard (Top 10)</b>\n\n"
    
    message += f"✨ <b>Your Rank: #{user_rank}</b>\n   (Your monthly referrals: {user_refs})\n\n"
    
    found_users = False
    for i, user_data in enumerate(top_users_cursor):
        found_users = True
        current_user_id = user_data["user_id"]
        earnings_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR
        username = user_data.get("username")
        full_name = user_data.get("full_name", f"User {current_user_id}")
        monthly_refs = user_data.get("monthly_referrals", 0)
        
        display_name = f"@{username}" if username else full_name
        user_link = f"tg://user?id={current_user_id}"
        
        message += f"<b>{i+1}.</b> <a href='{user_link}'><b>{display_name}</b></a>"
        
        if current_user_id == user_id:
            message += " (You) "
            
        message += "\n"
        message += f"   - 👥 Referrals this month: <b>{monthly_refs}</b>\n"
        message += f"   - 💵 Total Balance: ₹{earnings_inr:.2f}\n"

    if not found_users:
        message += "❌ No referrals recorded this month yet."

    keyboard = [
        [InlineKeyboardButton("💡 Leaderboard Benefits", callback_data="show_leaderboard_info")],
        [InlineKeyboardButton("⬅️ Back to Earning Panel", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
# --- END LEADERBOARD UPDATE ---


async def show_leaderboard_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message:
        return
    
    await query.answer()
    lang = await get_user_lang(query.from_user.id)
    
    title = MESSAGES[lang].get("leaderboard_info_title", MESSAGES["en"]["leaderboard_info_title"])
    text = MESSAGES[lang].get("leaderboard_info_text", MESSAGES["en"]["leaderboard_info_text"])
    
    message = f"<b>{title}</b>\n\n{text}"
    
    keyboard = [[InlineKeyboardButton("⬅️ Back to Leaderboard", callback_data="show_leaderboard")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def set_bot_commands_logic(context: ContextTypes.DEFAULT_TYPE) -> None:
    user_commands = [
        BotCommand("start", "Start the bot and see the main menu"),
        BotCommand("earn", "Go to the earning panel"),
    ]
    
    await context.bot.set_my_commands(user_commands)
    logger.info("User-level bot commands set successfully.")
