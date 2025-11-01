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
    JOIN_CHANNEL_LINK 
)
from db_utils import (
    send_log_message, get_user_lang, set_user_lang, get_referral_bonus_inr, 
    get_welcome_bonus, get_user_tier, get_tier_referral_rate, 
    claim_and_update_daily_bonus, update_daily_searches_and_mission,
    get_bot_stats, pay_referrer_and_update_mission,
    # Yahaan add karen:
    get_user_stats, admin_add_money, admin_clear_earnings, admin_delete_user, clear_junk_users
)

logger = logging.getLogger(__name__)


async def referral_payment_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    job_data = context.job.data
    referrer_id = job_data.get("referrer_id")
    referred_user_id = job_data.get("referred_user_id") 
    
    if not referrer_id or not referred_user_id:
        logger.error("Job data missing referrer_id or referred_user_id.")
        return

    success, amount = await pay_referrer_and_update_mission(context, referred_user_id, referrer_id)
    
    if success:
        logger.info(f"Job: Successfully paid referrer {referrer_id} from user {referred_user_id} (₹{amount:.2f}).")
    else:
        logger.warning(f"Job: Referral payment for {referred_user_id} to {referrer_id} failed or already processed.")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    # --- FIX 1: Add a specific check for "Message is not modified" error.
    error_detail = str(context.error)
    if "Message is not modified" in error_detail:
        logger.warning("Ignoring 'Message is not modified' error.")
        # Do not send a message to the user for this specific, benign error
        # but still log the event to the admin if necessary.
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
    # --- END FIX 1

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


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    full_name = user.first_name + (f" {user.last_name}" if user.last_name else "")
    username_display = f"@{user.username}" if user.username else f"<code>{user.id}</code>"
    
    referral_id_str = context.args[0].replace("ref_", "") if context.args and context.args[0].startswith("ref_") else None
    referral_id = int(referral_id_str) if referral_id_str and referral_id_str.isdigit() else None

    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    is_new_user = not user_data

    # --- START Change 2.1: update_data variable
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
            "monthly_referrals": 0  # <-- YEH NAYI LINE ADD KAREN
        }
    }
    # --- END Change 2.1
    
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
                
                # --- START Change 2.2: Increment monthly referral count
                # Increment monthly referral count for the referrer
                USERS_COLLECTION.update_one(
                    {"user_id": referral_id},
                    {"$inc": {"monthly_referrals": 1}}
                )
                # --- END Change 2.2
                
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

    # --- START FIX: Top 10 button to Leaderboard (Big Button) ---
    keyboard = [
        # New Big Leaderboard Button
        [InlineKeyboardButton("🏆 Earning Leaderboard (Top 10)", callback_data="show_leaderboard")],

        [InlineKeyboardButton("🔗 My Refer Link", callback_data="show_refer_link"), 
         InlineKeyboardButton("👥 My Referrals", callback_data="show_my_referrals")],
        
        [InlineKeyboardButton("🎁 Daily Bonus", callback_data="claim_daily_bonus"),
         InlineKeyboardButton("🎯 Daily Missions", callback_data="show_missions")],

        [InlineKeyboardButton(MESSAGES[lang]["spin_wheel_button"].format(spins_left=spins_left), callback_data="show_spin_panel"),
         InlineKeyboardButton("📈 Tier Benefits", callback_data="show_tier_benefits")], 
         
        [InlineKeyboardButton("💸 Request Withdrawal", callback_data="show_withdraw_details_new"),
         InlineKeyboardButton(channel_button_text, callback_data="claim_channel_bonus")],
         
        [InlineKeyboardButton("🆘 Help", callback_data="show_help"),
         InlineKeyboardButton("⬅️ Back", callback_data="back_to_main_menu")]
    ]
    # --- END FIX ---
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query.message: 
        try:
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
        # --- FIX 2: Handle "Message is not modified" error gracefully.
        except TelegramError as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Error editing message in show_earning_panel: {e}")
            pass
        # --- END FIX 2


# --- START Change 3: Replace show_my_referrals Function
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
        
        # Fetch user data for the first 10 referrals to get their names
        referred_ids = [ref['referred_user_id'] for ref in referral_records[:10]]
        referred_users_data = USERS_COLLECTION.find({"user_id": {"$in": referred_ids}})
        
        # Create a map of user_id -> full_name
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

            # Use the fetched name, or fallback to User ID
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
# --- END Change 3


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
        # --- FIX 3: Add a try-except for 'Message is not modified' error
        try:
            await query.edit_message_text(
                MESSAGES[lang]["daily_bonus_already_claimed"],
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
            )
        except TelegramError as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Error editing message in claim_daily_bonus (already_claimed): {e}")
            pass
        # --- END FIX 3
        return
    
    if bonus_amount is None:
        await query.answer("User data not found or error occurred.", show_alert=True)
        return

    await query.answer("Claiming bonus...")

    streak_message = f"🔥 You are on a {streak}-day streak! Keep it up for bigger bonuses!"
    if lang == "hi":
        streak_message = f"🔥 आप {streak}-दिन की स्ट्रीक पर हैं! बड़े बोनस के लिए इसे जारी रखें!"
        
    await query.edit_message_text(
        MESSAGES[lang]["daily_bonus_success"].format(
            bonus_amount=bonus_amount,
            new_balance=new_balance_inr,
            streak_message=streak_message
        ),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
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
            "❌ Failed to deduct spin. Try again.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
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
                "$inc": {"earnings": reward_usd},
                "$set": {f"missions_completed.{mission_key}": True}
            }
        )
        newly_completed_message += f"✅ <b>{name}</b>: +₹{mission['reward']:.2f}\n"
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
                "$inc": {"earnings": reward_usd},
                "$set": {f"missions_completed.{mission_key}": True}
            }
        )
        newly_completed_message += f"✅ <b>{name}</b>: +₹{mission['reward']:.2f}\n"
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
                    "$inc": {"earnings": reward_usd},
                    "$set": {f"missions_completed.{mission_key}": True}
                }
            )
            newly_completed_message += f"✅ <b>{name}</b>: +₹{mission['reward']:.2f}\n"
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


async def request_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: 
        return
        
    user = query.from_user
    lang = await get_user_lang(user.id)
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    username_display = f"@{user.username}" if user.username else f"<code>{user.id}</code>"

    if not user_data:
        await query.answer("User data not found.", show_alert=True)
        return
        
    await query.answer("Processing withdrawal request...")

    earnings_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR
    
    if earnings_inr < 80:
        await query.edit_message_text(
            MESSAGES[lang]["withdrawal_insufficient"],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
        )
        return

    existing_request = WITHDRAWALS_COLLECTION.find_one({"user_id": user.id, "status": "pending"})
    if existing_request:
        # --- FIX 4: Add a try-except for 'Message is not modified' error
        try:
            await query.edit_message_text(
                "❌ <b>Request Already Pending!</b>\n\nYour previous withdrawal request is still being processed.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
            )
        except TelegramError as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Error editing message in request_withdrawal (already pending): {e}")
            pass
        # --- END FIX 4
        return
    
    withdrawal_data = {
        "user_id": user.id,
        "username": user.username,
        "full_name": user.first_name + (f" {user.last_name}" if user.last_name else ""),
        "amount_inr": earnings_inr,
        "status": "pending",
        "request_date": datetime.now(),
        "approved_date": None
    }
    
    WITHDRAWALS_COLLECTION.insert_one(withdrawal_data)

    admin_message = (
        f"🔄 <b>New Withdrawal Request</b>\n\n"
        f"👤 User: {user.full_name} ({username_display})\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"💰 Amount: ₹{earnings_inr:.2f}"
    )
    
    await send_log_message(context, admin_message)

    if ADMIN_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_message,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve_withdraw_{user.id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_withdraw_{user.id}")
                ]])
            )
        except Exception as e:
            logger.error(f"Could not notify admin about withdrawal: {e}")

    await query.edit_message_text(
        MESSAGES[lang]["withdrawal_request_sent"].format(amount=earnings_inr),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
    )


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
            # --- FIX 5: Handle messages with photos/captions gracefully
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
                # Delete the previous message (which likely had no photo/caption)
                await query.message.delete()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Failed to send photo in show_refer_example: {e}")
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


# --- START Change 4: Replace claim_channel_bonus Function
async def claim_channel_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: 
        return
        
    user = query.from_user
    lang = await get_user_lang(user.id)
    username_display = f"@{user.username}" if user.username else f"<code>{user.id}</code>"
    
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    
    # Check 1: Already claimed
    if user_data.get("channel_bonus_received"):
        await query.answer(MESSAGES[lang]["channel_already_claimed"], show_alert=True)
        # Directly call show_earning_panel to update the message
        await show_earning_panel(update, context) 
        return
        
    await query.answer("Checking channel membership...")
    
    is_member = False
    # --- START Change 4 (Fix for exceptions) ---
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user.id)
        is_member = member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Error checking channel membership for {user.id}: {e}")

        # Notify admin about the error
        await send_log_message(
            context, 
            f"🚨 **Channel Check Error!**\n\nFailed to check membership for User <code>{user.id}</code> in channel <code>{CHANNEL_ID}</code>.\nError: <code>{e}</code>\n\n<b>FIX:</b> Ensure bot is admin in the channel."
        )

        # Notify user about the error
        await query.answer(MESSAGES[lang]["channel_bonus_error"].format(channel=CHANNEL_USERNAME), show_alert=True)

        # Send the error message in the chat
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

        return # Stop execution here
    # --- END Change 4 (Fix for exceptions) ---
        
    # Check 2: Member and not claimed
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
        
    # Check 3: Not a member or update failed
    
    join_button = InlineKeyboardButton(
        "🔗 Join Channel", 
        url=JOIN_CHANNEL_LINK 
    )
    retry_button = InlineKeyboardButton(
        "🔄 Try Again", 
        callback_data="claim_channel_bonus"
    )
    back_button = InlineKeyboardButton("⬅️ Back to Earning Panel", callback_data="show_earning_panel")
    
    keyboard = [
        [join_button, retry_button],
        [back_button] 
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # --- FIX 7: Add a try-except for 'Message is not modified' error when showing failure
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
    # --- END FIX 7
# --- END Change 4


# --- START Change 5: Replace admin_panel Function
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        if update.message:
            try:
                await update.message.reply_text("❌ Access Denied.")
            except:
                pass
        return

    context.user_data["admin_state"] = None
    context.user_data["stats_user_id"] = None # Clear any pending user ID
    
    lang = await get_user_lang(user.id)
    message = MESSAGES[lang].get("admin_panel_title", "👑 <b>Admin Panel</b>\n\nSelect an action:")

    keyboard = [
        [InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_set_broadcast"),
         InlineKeyboardButton("💸 Pending Withdrawals", callback_data="admin_pending_withdrawals")],
        [InlineKeyboardButton("⚙️ Set Referral Rate", callback_data="admin_set_ref_rate"),
         InlineKeyboardButton("📊 Bot Stats", callback_data="admin_stats")],
        # --- NEW BUTTONS ---
        [InlineKeyboardButton("📊 User Stats", callback_data="admin_user_stats")],
        [InlineKeyboardButton("🗑️ Clear Junk Users", callback_data="admin_clear_junk")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message: 
        await update.message.reply_html(message, reply_markup=reply_markup)
    elif update.callback_query and update.callback_query.message:
        try:
            await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
        except TelegramError as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Error editing message in admin_panel: {e}")
            pass
# --- END Change 5


async def back_to_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query:
        await query.answer()
    await admin_panel(update, context)


# --- START Change 6: Replace handle_admin_callbacks Function
async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    
    if not query or not query.message:
        logger.warning("handle_admin_callbacks called without query or message.")
        return
        
    await query.answer()
    
    user = query.from_user
    if user.id != ADMIN_ID:
        await query.edit_message_text("❌ Access Denied.")
        return

    data = query.data.split("_")
    action = data[1]
    sub_action = data[2] if len(data) > 2 else None
    
    lang = await get_user_lang(user.id)
    
    if action == "pending" and sub_action == "withdrawals":
        await show_pending_withdrawals(update, context)
    elif action == "stats" and sub_action is None: 
        await show_bot_stats(update, context)
    elif action == "pending":
        await back_to_admin_menu(update, context)
    
    # --- NEW ACTIONS ---
    elif action == "user" and sub_action == "stats":
        # 1. Prompt for User ID
        context.user_data["admin_state"] = "waiting_for_user_id_stats"
        await query.edit_message_text(
            MESSAGES[lang]["admin_user_stats_prompt"],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]])
        )
        
    elif action == "clear" and sub_action == "junk":
        # 2. Clear Junk Users
        await query.edit_message_text("🗑️ Clearing junk users (is_approved=False)... Please wait.", parse_mode='HTML')
        result = await clear_junk_users()
        await query.edit_message_text(
            MESSAGES[lang]["clear_junk_success"].format(
                users=result.get("users", 0),
                referrals=result.get("referrals", 0),
                withdrawals=result.get("withdrawals", 0)
            ),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]),
            parse_mode='HTML'
        )
        
    elif action == "add" and sub_action == "money":
        # 3. Prompt for Add Money
        user_id = context.user_data.get("stats_user_id")
        if not user_id:
            await query.edit_message_text("❌ Error: User ID not found in session. Please start over.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]))
            return
        context.user_data["admin_state"] = "waiting_for_add_money"
        await query.edit_message_text(
            MESSAGES[lang]["admin_add_money_prompt"].format(user_id=user_id),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]))
        
    elif action == "clear" and sub_action == "data":
        # 4. Prompt for Clear Data
        user_id = context.user_data.get("stats_user_id")
        if not user_id:
            await query.edit_message_text("❌ Error: User ID not found in session. Please start over.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]))
            return
        context.user_data["admin_state"] = "waiting_for_clear_data"
        await query.edit_message_text(
            MESSAGES[lang]["admin_clear_data_prompt"],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]))

    # --- OLD ACTIONS (Must be last) ---
    elif action == "set": 
        if sub_action == "broadcast":
            context.user_data["admin_state"] = "waiting_for_broadcast_message"
            await query.edit_message_text("✍️ Enter the **message** you want to broadcast to all users:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]))
        elif sub_action == "ref" and data[3] == "rate":
             context.user_data["admin_state"] = "waiting_for_ref_rate"
             await query.edit_message_text("✍️ Enter the **NEW Tier 1 Referral Rate** in INR (e.g., 5.0 for ₹5 per referral):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]))
# --- END Change 6


async def show_bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message:
        return

    lang = await get_user_lang(query.from_user.id)
    stats = await get_bot_stats()

    message = MESSAGES[lang].get("stats_message", "📊 <b>Bot Stats</b>\n\nTotal Users: {total_users}\nApproved Users: {approved_users}").format(
        total_users=stats["total_users"],
        approved_users=stats["approved_users"]
    )
    
    keyboard = [[InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_pending")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def show_pending_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: 
        return
        
    pending_withdrawals = WITHDRAWALS_COLLECTION.find({"status": "pending"}).sort("request_date", 1)
    
    message = "<b>💸 Pending Withdrawals</b>\n\n"
    keyboard = []
    
    count = WITHDRAWALS_COLLECTION.count_documents({"status": "pending"})

    if count == 0:
        message += "✅ No pending withdrawal requests."
    else:
        for request in pending_withdrawals:
            user_id = request["user_id"]
            amount = request["amount_inr"]
            username = request.get("username", "N/A")
            
            message += f"👤 User: <code>{user_id}</code> (@{username})\n💰 Amount: ₹{amount:.2f}\n"
            
            if len(keyboard) < 5: 
                keyboard.append([
                    InlineKeyboardButton(f"✅ Approve {user_id}", callback_data=f"approve_withdraw_{user_id}"),
                    InlineKeyboardButton(f"❌ Reject {user_id}", callback_data=f"reject_withdraw_{user_id}")
                ])
                
        message += "\n(Showing up to 5 requests. Use buttons to process.)"


    keyboard.append([InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_pending")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


# --- START Change 7: Replace handle_admin_input Function
async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id != ADMIN_ID or not update.message or not update.message.text:
        return
        
    admin_state = context.user_data.get("admin_state")
    text = update.message.text
    lang = await get_user_lang(user.id)
    
    if admin_state is None and update.message.text and update.message.text.startswith('/admin'):
        await admin_panel(update, context)
        return
    
    if admin_state is None:
        # Not waiting for any specific input, ignore
        return

    # --- STATE: waiting_for_user_id_stats ---
    if admin_state == "waiting_for_user_id_stats":
        try:
            user_id = int(text)
            stats = await get_user_stats(user_id)
            
            if not stats:
                await update.message.reply_text(MESSAGES[lang]["admin_user_not_found"].format(user_id=user_id))
                return

            # Store user_id in session for the buttons
            context.user_data["stats_user_id"] = user_id
            context.user_data["admin_state"] = None # Clear state

            message = (
                f"📊 <b>User Stats for {stats['full_name']}</b>\n\n"
                f"<b>ID:</b> <code>{stats['user_id']}</code>\n"
                f"<b>Username:</b> @{stats['username']}\n"
                f"<b>Balance:</b> ₹{stats['earnings_inr']:.2f}\n"
                f"<b>Total Referrals:</b> {stats['referrals']}"
            )
            
            keyboard = [
                [InlineKeyboardButton("💰 Add Money", callback_data="admin_add_money"),
                 InlineKeyboardButton("🗑️ Clear Data", callback_data="admin_clear_data")],
                [InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_pending")]
            ]
            await update.message.reply_html(message, reply_markup=InlineKeyboardMarkup(keyboard))
            
        except ValueError:
            await update.message.reply_text(MESSAGES[lang]["admin_invalid_input"])
        except Exception as e:
            await update.message.reply_text(f"An error occurred: {e}")
            
    # --- STATE: waiting_for_add_money ---
    elif admin_state == "waiting_for_add_money":
        user_id = context.user_data.get("stats_user_id")
        if not user_id:
            await update.message.reply_text("Error: Session expired. Please start over from /admin.")
            context.user_data["admin_state"] = None
            return
            
        try:
            amount_inr = float(text)
            new_balance = await admin_add_money(user_id, amount_inr)
            
            await update.message.reply_text(
                MESSAGES[lang]["admin_add_money_success"].format(
                    amount=amount_inr, 
                    user_id=user_id, 
                    new_balance=new_balance
                )
            )
            # Send log
            await send_log_message(context, f"ADMIN: <code>{user.id}</code> added ₹{amount_inr:.2f} to user <code>{user_id}</code>.")
            
        except ValueError:
            await update.message.reply_text(MESSAGES[lang]["admin_invalid_input"] + " Please enter a number (e.g., 10.50).")
        
        context.user_data["admin_state"] = None
        context.user_data["stats_user_id"] = None

    # --- STATE: waiting_for_clear_data ---
    elif admin_state == "waiting_for_clear_data":
        user_id = context.user_data.get("stats_user_id")
        choice = text.strip().lower()

        if not user_id:
            await update.message.reply_text("Error: Session expired. Please start over from /admin.")
            context.user_data["admin_state"] = None
            return
        
        if choice == "earning":
            await admin_clear_earnings(user_id)
            await update.message.reply_text(MESSAGES[lang]["admin_clear_earnings_success"].format(user_id=user_id))
            await send_log_message(context, f"ADMIN: <code>{user.id}</code> cleared earnings for user <code>{user_id}</code>.")
            
        elif choice == "all":
            await admin_delete_user(user_id)
            await update.message.reply_text(MESSAGES[lang]["admin_delete_user_success"].format(user_id=user_id))
            await send_log_message(context, f"ADMIN: <code>{user.id}</code> DELETED ALL data for user <code>{user_id}</code>.")
            
        else:
            await update.message.reply_text(MESSAGES[lang]["admin_invalid_input"] + " Please reply with 'all' or 'earning'.")
            return # Keep state active

        context.user_data["admin_state"] = None
        context.user_data["stats_user_id"] = None
            
    # --- STATE: waiting_for_broadcast_message ---
    elif admin_state == "waiting_for_broadcast_message":
        success_count = 0
        fail_count = 0
        
        status_message = await update.message.reply_text("📢 Starting broadcast... This may take a moment. Updates will be shown here.")
        
        user_ids_cursor = USERS_COLLECTION.find({"is_approved": True}, {"user_id": 1}) 
        total_users = USERS_COLLECTION.count_documents({"is_approved": True})
        
        for i, user_data in enumerate(user_ids_cursor):
            user_id = user_data["user_id"]
            
            if i % 100 == 0 and i != 0:
                 try:
                    await context.bot.edit_message_text(
                        chat_id=status_message.chat_id, 
                        message_id=status_message.message_id,
                        text=f"📢 Broadcasting in progress...\nSent to {i} of {total_users} users.\nSuccess: {success_count} / Failed: {fail_count}"
                    )
                 except Exception as e:
                     logger.warning(f"Failed to edit broadcast status message: {e}")
            
            try:
                await context.bot.send_message(user_id, text, parse_mode='HTML', disable_web_page_preview=True)
                success_count += 1
                await asyncio.sleep(0.05) 
                
            except FloodWait as e:
                wait_time = e.retry_after + 1 
                logger.warning(f"FloodWait encountered for user {user_id}. Waiting for {wait_time} seconds. Success: {success_count}, Fail: {fail_count}")
                await context.bot.edit_message_text(
                     chat_id=status_message.chat_id, 
                     message_id=status_message.message_id,
                     text=f"⚠️ **PAUSED: FloodWait**\nWaiting for {wait_time} seconds...\nSent to {i} of {total_users} users.\nSuccess: {success_count} / Failed: {fail_count}"
                )
                await asyncio.sleep(wait_time)
                try:
                    await context.bot.send_message(user_id, text, parse_mode='HTML', disable_web_page_preview=True)
                    success_count += 1
                    await asyncio.sleep(0.05)
                except Exception:
                     fail_count += 1
                
            except (Forbidden, BadRequest) as e:
                fail_count += 1
                USERS_COLLECTION.update_one({"user_id": user_id}, {"$set": {"is_approved": False}}) 
                logger.warning(f"Failed to send to user {user_id} due to API Error: {e}. User marked unapproved.")
                
            except Exception as e:
                fail_count += 1
                logger.error(f"Unknown error sending to user {user.id}: {e}")
                
        context.user_data["admin_state"] = None
        await context.bot.edit_message_text(
            chat_id=status_message.chat_id, 
            message_id=status_message.message_id,
            text=f"✅ **Broadcast complete**.\nSuccessful: {success_count}\nFailed: {fail_count}\nTotal users processed: {total_users}"
        )

    # --- STATE: waiting_for_ref_rate ---
    elif admin_state == "waiting_for_ref_rate":
        try:
            new_rate = float(text)
            if new_rate <= 0:
                 raise ValueError
            
            SETTINGS_COLLECTION.update_one(
                {"_id": "referral_rate"}, 
                {"$set": {"rate_inr": new_rate}},
                upsert=True
            )
            
            context.user_data["admin_state"] = None
            await update.message.reply_text(f"✅ Referral rate successfully updated to **₹{new_rate:.2f}** per referral.")
            
        except ValueError:
            await update.message.reply_text("❌ Invalid input. Please enter a valid number for the new rate (e.g., 5.0).")
# --- END Change 7


async def handle_withdrawal_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query: 
        return
        
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        if query.message:
            await query.edit_message_text("❌ Access Denied.")
        return
        
    parts = query.data.split("_")
    action = parts[0] 
    user_id_str = parts[2]
    user_id = int(user_id_str)

    withdrawal_request = WITHDRAWALS_COLLECTION.find_one_and_update(
        {"user_id": user.id, "status": "pending"},
        {"$set": {"status": action, "approved_date": datetime.now()}},
        return_document=True
    )

    if not withdrawal_request:
        if query.message:
            await query.edit_message_text(f"❌ Withdrawal request for user <code>{user_id}</code> not found or already processed.", parse_mode='HTML')
        return

    amount_inr = withdrawal_request["amount_inr"]
    
    if action == "approve":
        amount_usd = amount_inr / DOLLAR_TO_INR
        USERS_COLLECTION.update_one(
            {"user_id": user_id},
            {"$inc": {"earnings": -amount_usd}}
        )
        
        try:
            user_lang = await get_user_lang(user_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=MESSAGES[user_lang]["withdrawal_approved_user"].format(amount=amount_inr), 
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Could not notify user {user_id} of approval: {e}")
        
        if query.message:
            await query.edit_message_text(f"✅ Request for user <code>{user_id}</code> (**₹{amount_inr:.2f}**) **APPROVED**.\nFunds deducted.", parse_mode='HTML')
        log_msg = f"💸 <b>Withdrawal Approved</b>\nAdmin: <code>{query.from_user.id}</code>\nUser: <code>{user_id}</code>\nAmount: ₹{amount_inr:.2f}"
    
    else: 
        try:
            user_lang = await get_user_lang(user_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=MESSAGES[user_lang]["withdrawal_rejected_user"].format(amount=amount_inr), 
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Could not notify user {user_id} of rejection: {e}")
        
        if query.message:
            await query.edit_message_text(f"❌ Request for user <code>{user_id}</code> (**₹{amount_inr:.2f}**) **REJECTED**.", parse_mode='HTML')
        log_msg = f"🚫 <b>Withdrawal Rejected</b>\nAdmin: <code>{query.from_user.id}</code>\nUser: <code>{user_id}</code>\nAmount: ₹{amount_inr:.2f}"

    await send_log_message(context, log_msg)
    if query.message:
        if "admin" in query.data:
            await show_pending_withdrawals(update, context) 


# --- START Change 8: Replace show_top_users with show_leaderboard
async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message:
        return
        
    await query.answer()
    lang = await get_user_lang(query.from_user.id)
    
    # Sort by monthly referrals, descending
    top_users_cursor = USERS_COLLECTION.find().sort("monthly_referrals", -1).limit(10)
    
    # Leaderboard Title from your request
    message = "🏆 <b>Earning Leaderboard (Top 10)</b>\n\n"
    
    found_users = False
    for i, user_data in enumerate(top_users_cursor):
        found_users = True
        user_id = user_data["user_id"]
        earnings_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR
        username = user_data.get("username")
        full_name = user_data.get("full_name", f"User {user_id}")
        monthly_refs = user_data.get("monthly_referrals", 0)
        
        display_name = f"@{username}" if username else full_name
        user_link = f"tg://user?id={user_id}"
        
        message += f"<b>{i+1}.</b> <a href='{user_link}'><b>{display_name}</b></a>\n"
        # Since I don't have the original MESSAGES[lang]["leaderboard_rank_entry"], 
        # I'll create a default one based on the logic:
        message += f"   - 👥 Referrals this month: <b>{monthly_refs}</b>\n"
        message += f"   - 💵 Total Balance: ₹{earnings_inr:.2f}\n"

    if not found_users:
        message += "❌ No referrals recorded this month yet."

    keyboard = [[InlineKeyboardButton("⬅️ Back to Earning Panel", callback_data="show_earning_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
# --- END Change 8


# --- START Change 9.1: Replace topusers_logic
async def topusers_logic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_leaderboard(update, context)
# --- END Change 9.1

# --- Change 9.2: clearjunk_logic function has been REMOVED as per instruction ---

async def set_bot_commands_logic(context: ContextTypes.DEFAULT_TYPE) -> None:
    user_commands = [
        BotCommand("start", "Start the bot and see the main menu"),
        BotCommand("earn", "Go to the earning panel"),
    ]
    admin_commands = user_commands + [
        BotCommand("admin", "Admin Panel (for admin only)")
    ]

    await context.bot.set_my_commands(user_commands)
    logger.info("Bot commands set successfully.")
