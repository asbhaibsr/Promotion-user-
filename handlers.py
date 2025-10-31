# handlers.py

import logging
import random
import time
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
# FIX: FloodWait is now explicitly imported for broadcast handling
from telegram.error import TelegramError, TimedOut, Forbidden, BadRequest, RetryAfter as FloodWait 
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import asyncio

# Assuming these functions are defined in your db_utils and config files
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
    get_bot_stats, pay_referrer_and_update_mission # Import the core logic function
)
# from tasks import add_payment_and_check_mission # OLD: Removed as we define the job here

logger = logging.getLogger(__name__)

# --- CRITICAL FIX: Job Queue Function ---
# This function is the actual job that will run after the delay
async def referral_payment_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled job to pay the referrer and update their mission status."""
    job_data = context.job.data
    referrer_id = job_data.get("referrer_id")
    referred_user_id = job_data.get("referred_user_id") # Stored referred user ID in the job
    
    if not referrer_id or not referred_user_id:
        logger.error("Job data missing referrer_id or referred_user_id.")
        return

    # Call the core logic after the delay
    success, amount = await pay_referrer_and_update_mission(context, referred_user_id, referrer_id)
    
    if success:
        logger.info(f"Job: Successfully paid referrer {referrer_id} from user {referred_user_id} (₹{amount:.2f}).")
    else:
        logger.warning(f"Job: Referral payment for {referred_user_id} to {referrer_id} failed or already processed.")


# --- Global Error Handler (New) ---
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a message to the admin."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    # Try to send a generic error message to the user/admin
    try:
        error_msg = f"❌ An error occurred! Details: {context.error}"
        if update and update.effective_chat:
            # FIX: Only reply if the message is NOT in a group to avoid spamming the group with error messages
            if update.effective_chat.type == 'private' or (update.effective_chat.type != 'private' and update.message and update.message.text and update.message.text.startswith('/')):
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ **Oops!** Something went wrong. The error has been logged.",
                    parse_mode='Markdown'
                )
        
        # Log the error to the admin
        if ADMIN_ID:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🚨 **Bot Error**:\n\n`{error_msg}`\n\n**Update:** `{update}`",
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Failed to handle error: {e}")

# --- Core Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    full_name = user.first_name + (f" {user.last_name}" if user.last_name else "")
    username_display = f"@{user.username}" if user.username else f"<code>{user.id}</code>"
    
    referral_id_str = context.args[0].replace("ref_", "") if context.args and context.args[0].startswith("ref_") else None
    referral_id = int(referral_id_str) if referral_id_str and referral_id_str.isdigit() else None

    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    is_new_user = not user_data

    # 1. User Upsert and Initialization
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
            "spins_left": SPIN_WHEEL_CONFIG["initial_free_spins"]
        }
    }
    
    USERS_COLLECTION.update_one(
        {"user_id": user.id},
        update_data,
        upsert=True
    )

    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    lang = user_data.get("lang", "en")
    
    # 2. New User Logic (Welcome Bonus, Referral)
    if is_new_user:
        log_msg = f"👤 <b>New User</b>\nID: <code>{user.id}</code>\nName: {full_name}\nUsername: {username_display}"
        
        # Welcome Bonus
        if not user_data.get("welcome_bonus_received", False):
            welcome_bonus = await get_welcome_bonus()
            welcome_bonus_usd = welcome_bonus / DOLLAR_TO_INR
            
            USERS_COLLECTION.update_one(
                {"user_id": user.id},
                {"$inc": {"earnings": welcome_bonus_usd}, "$set": {"welcome_bonus_received": True}}
            )
            try:
                # Assuming update.message is not None here for a /start command
                await update.message.reply_html(MESSAGES[lang]["welcome_bonus_received"].format(amount=welcome_bonus))
            except Exception:
                 pass
            log_msg += f"\n🎁 Welcome Bonus: ₹{welcome_bonus:.2f}"
            log_msg += f"\n🎰 Initial Spins: {SPIN_WHEEL_CONFIG['initial_free_spins']}"

        # Referral Logic
        if referral_id and referral_id != user.id:
            existing_referral = REFERRALS_COLLECTION.find_one({"referred_user_id": user.id})
            
            if not existing_referral:
                REFERRALS_COLLECTION.insert_one({
                    "referrer_id": referral_id,
                    "referred_user_id": user.id,
                    "referred_username": user.username,
                    "join_date": datetime.now(),
                    # IMPORTANT: These fields are crucial for the new daily payment logic
                    "last_paid_date": None, 
                    "paid_search_count_today": 0
                })
                
                referrer_tier = await get_user_tier(referral_id)
                tier_rate = await get_tier_referral_rate(referrer_tier)
                referral_rate_half = tier_rate / 2.0 # Join bonus is half the daily rate
                referral_rate_usd = referral_rate_half / DOLLAR_TO_INR
                
                USERS_COLLECTION.update_one(
                    {"user_id": referral_id},
                    {"$inc": {"earnings": referral_rate_usd, "spins_left": SPIN_WHEEL_CONFIG["refer_to_get_spin"]}} 
                )
                
                log_msg += f"\n🔗 Referred by: <code>{referral_id}</code> (Join Bonus: ₹{referral_rate_half:.2f} + 1 Spin)"

                try:
                    referrer_lang = await get_user_lang(referral_id)
                    await context.bot.send_message(
                        chat_id=referral_id,
                        text=MESSAGES[referrer_lang]["new_referral_notification"].format(
                            full_name=full_name, username=username_display, bonus=referral_rate_half
                        ),
                        parse_mode='HTML'
                    )
                except (TelegramError, TimedOut) as e:
                    logger.error(f"Could not notify referrer {referral_id}: {e}")
            else:
                log_msg += f"\n❌ Referral ignored (already referred by {existing_referral['referrer_id']})"

        await send_log_message(context, log_msg)

    # 3. Send Main Menu
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
    
    # Assuming update.message is safe for /start command
    if update.message:
        await update.message.reply_html(message, reply_markup=reply_markup)


async def earn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        lang = await get_user_lang(update.effective_user.id)
        keyboard = [[InlineKeyboardButton("💰 Earning Panel", callback_data="show_earning_panel")]]
        await update.message.reply_html(MESSAGES[lang]["earning_panel_message"], reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # **FIX 1: Ensure message is a text message and in a group/supergroup before proceeding.**
    if not update.message or not update.message.text:
        return
        
    chat_type = update.effective_chat.type
    if chat_type not in ["group", "supergroup"]:
        # Only process group messages here.
        return
        
    user = update.effective_user
    
    bot_info = await context.bot.get_me()
    if user.id == bot_info.id:
        return
        
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    if not user_data:
        return 

    # 1. Update User's Daily Search Count and last_search_date (for mission)
    # The function ensures a user is only credited one search per day for their *own* mission progress.
    result = await update_daily_searches_and_mission(user.id)
    
    if not result:
        logger.error(f"Failed to atomically update daily searches for user {user.id}")
        return

    # 2. Check for referrer and schedule payment task
    referral_data = REFERRALS_COLLECTION.find_one({"referred_user_id": user.id})
    
    if referral_data:
        referrer_id = referral_data["referrer_id"]
        
        # Security check: Self-referral protection
        if referrer_id == user.id:
            logger.warning(f"Self-referral detected and ignored for user {user.id}")
            return
            
        # Daily payment check: Has this referred user already triggered a payment today for the referrer?
        last_paid_date = referral_data.get("last_paid_date")
        today = datetime.now().date()
        
        # CRITICAL FIX: Check if last_paid_date exists, is a datetime, and is today
        if last_paid_date and isinstance(last_paid_date, datetime) and last_paid_date.date() == today:
            logger.info(f"Referral payment for user {user.id} to referrer {referrer_id} already processed today. Skipping job scheduling.")
            # Still send the success message to the referred user's PRIVATE CHAT
            lang = await get_user_lang(user.id)
            try:
                # User ID is used as chat_id to send to private chat
                await context.bot.send_message(chat_id=user.id, text=MESSAGES[lang]["search_success_message"], parse_mode='HTML') 
            except Exception as e:
                logger.error(f"Failed to send search success message to user {user.id} (already paid): {e}")
            return

        # If it hasn't been paid today, schedule the job.
        # Job name ensures only one job per referred user is pending at a time
        job_name = f"pay_{user.id}" 
        existing_jobs = context.job_queue.get_jobs_by_name(job_name)
        
        if not existing_jobs:
            # Payment check scheduled after a delay (e.g., 5 minutes = 300 seconds)
            # The job will call pay_referrer_and_update_mission which handles payment, message to referrer, and last_paid_date update.
            context.job_queue.run_once(
                referral_payment_job, # Use the dedicated job function
                300, # 5 minutes delay (as requested)
                # The chat_id is the referred user's ID, but only for logging purposes in the job_queue
                chat_id=user.id, 
                user_id=user.id, # The referred user
                data={"referrer_id": referrer_id, "referred_user_id": user.id}, # Pass data to the job
                name=job_name
            )
            logger.info(f"Payment task scheduled for user {user.id} (referrer {referrer_id}). Job Name: {job_name}")
        else:
             logger.info(f"Payment task for {user.id} already pending. Ignoring job creation.")
    
    # **CRITICAL FIX: Send search success message to the REFERRED USER'S PRIVATE CHAT, NOT the group.**
    # This addresses the user's issue: "bot us user ke movie search karne ke paise [...] update kr deta hai movie sewrch krne ke 5 minute baad"
    lang = await get_user_lang(user.id)
    try:
        # User ID is used as chat_id to send to private chat
        await context.bot.send_message(chat_id=user.id, text=MESSAGES[lang]["search_success_message"], parse_mode='HTML') 
    except Exception as e:
        # This will catch cases where the user has not started the bot (Forbidden error)
        logger.error(f"Failed to send search success message to user {user.id} (Private Chat): {e}")


# --- Callback Handlers (Menus, Actions) ---
# ... (All other handlers remain the same as provided)
# The rest of the handlers are the same to minimize risk outside the critical path.
# ...

async def show_earning_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    
    # Check 1: Ensure query object exists
    if not query:
        logger.warning("show_earning_panel called without a callback query.")
        return 
        
    user = query.from_user
    lang = await get_user_lang(user.id)
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    
    await query.answer()

    if not user_data:
        await query.answer("User data not found.", show_alert=True)
        # Check 2: Ensure message object exists before editing/sending
        if query.message: 
             try:
                 await query.edit_message_text("User data not found.")
             except Exception:
                  await context.bot.send_message(user.id, "User data not found.")
        return
    
    earnings_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR
    # Count only non-self referrals
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

    # सारे बटन अब काम कर रहे हैं और 'Top Users' को यहाँ जोड़ा गया है।
    keyboard = [
        [InlineKeyboardButton("🔗 My Refer Link", callback_data="show_refer_link"), 
         InlineKeyboardButton("💡 Referral Example", callback_data="show_refer_example")], # काम कर रहा है
        
        [InlineKeyboardButton("🎁 Daily Bonus", callback_data="claim_daily_bonus"),
         InlineKeyboardButton("🎯 Daily Missions", callback_data="show_missions")],

        [InlineKeyboardButton(MESSAGES[lang]["spin_wheel_button"].format(spins_left=spins_left), callback_data="show_spin_panel"),
         InlineKeyboardButton("📊 Top 10 Users", callback_data="show_top_users")], # नया बटन
         
        [InlineKeyboardButton("💸 Request Withdrawal", callback_data="show_withdraw_details_new"), # काम कर रहा है (show_withdraw_details_new)
         InlineKeyboardButton("📈 Tier Benefits", callback_data="show_tier_benefits")], # काम कर रहा है
         
        [InlineKeyboardButton(channel_button_text, callback_data="claim_channel_bonus")],
        
        [InlineKeyboardButton("🆘 Help", callback_data="show_help"), # काम कर रहा है
         InlineKeyboardButton("⬅️ Back", callback_data="back_to_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query.message: # Check 3: Final check before edit
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
    
    user_tier = await get_user_tier(user.id)
    tier_rate = await get_tier_referral_rate(user_tier)
    
    message = (
        f"<b>🤑 ₹{TIERS[4]['rate']:.2f} Per Referral! Get Rich Fast!</b>\n\n"
        f"{MESSAGES[lang]['ref_link_message'].format(referral_link=referral_link, tier_rate=tier_rate)}\n\n"
        f"<b>💡 Secret Tip:</b> Your friends must <b>search 3 movies</b> in the group to get your full daily earning! Share this now!"
    )

    share_message_text = (
        f"🎉 <b>सबसे बेहतरीन मूवी बॉट को अभी जॉइन करें और रोज़ कमाएँ!</b>\n\n"
        f"🎬 हर नई हॉलीवुड/बॉलीवुड मूवी पाएँ!\n"
        f"💰 <b>₹{await get_welcome_bonus():.2f} वेलकम बोनस</b> तुरंत पाएँ!\n"
        f"💸 <b>हर रेफ़र पर ₹{TIERS[4]['rate']:.2f} तक</b> कमाएँ!\n\n"
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
    if not query or not query.message: # Added safety check for query and message
        return
        
    user = query.from_user
    lang = await get_user_lang(user.id)
    username_display = f"@{user.username}" if user.username else f"<code>{user.id}</code>"
    
    bonus_amount, new_balance, streak, already_claimed = await claim_and_update_daily_bonus(user.id)
    
    if already_claimed:
        await query.answer(MESSAGES[lang]["daily_bonus_already_claimed"], show_alert=True)
        await query.edit_message_text(
            MESSAGES[lang]["daily_bonus_already_claimed"],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
        )
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
            new_balance=new_balance,
            streak_message=streak_message
        ),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
    )
    
    log_msg = f"🎁 <b>Daily Bonus</b>\nUser: {username_display}\nAmount: ₹{bonus_amount:.2f}\nStreak: {streak} days\nNew Balance: ₹{new_balance:.2f}"
    await send_log_message(context, log_msg)


async def show_spin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: # Added safety check
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
        message += "\n\n❌ <b>No Spins Left!</b> Refer a friend to get 1 free spin."
        keyboard = [
            [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
        ]
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def perform_spin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: # Added safety check
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

    # UI Animation Simulation
    button_prizes = list(SPIN_PRIZES)
    random.shuffle(button_prizes)
    if len(button_prizes) < 8: button_prizes.extend([0.0] * (8 - len(button_prizes)))
    btn_list = [InlineKeyboardButton(f"₹{p:.2f}", callback_data="spin_fake_btn") for p in button_prizes[:8]]
    middle_btn = InlineKeyboardButton("🎡 Spinning...", callback_data="spin_fake_btn")
    spin_keyboard = [ [btn_list[0], btn_list[1], btn_list[2]], [btn_list[3], middle_btn, btn_list[4]], [btn_list[5], btn_list[6], btn_list[7]] ]
    reply_markup = InlineKeyboardMarkup(spin_keyboard)

    try:
        await query.edit_message_text(text=MESSAGES[lang]["spin_wheel_animating"], reply_markup=reply_markup, parse_mode='HTML')
    except TelegramError: pass 

    await asyncio.sleep(3)

    # Actual Spin Result and Database Update
    prize_inr = random.choices(SPIN_PRIZES, weights=SPIN_WEIGHTS, k=1)[0]
    prize_usd = prize_inr / DOLLAR_TO_INR
    
    USERS_COLLECTION.update_one({"user_id": user.id}, {"$inc": {"earnings": prize_usd}})
    updated_data = USERS_COLLECTION.find_one({"user_id": user.id})
    final_balance_usd = updated_data.get("earnings", 0.0) 

    log_msg = f"🎡 <b>Spin Wheel</b>\nUser: {username_display}\nCost: 1 Spin\n"
    
    if prize_inr > 0:
        message = MESSAGES[lang]["spin_wheel_win"].format(amount=prize_inr, new_balance=final_balance_usd * DOLLAR_TO_INR, spins_left=spins_left_after_deduct)
        log_msg += f"Win: ₹{prize_inr:.2f}"
    else:
        message = MESSAGES[lang]["spin_wheel_lose"].format(new_balance=final_balance_usd * DOLLAR_TO_INR, spins_left=spins_left_after_deduct)
        log_msg += "Win: ₹0.00 (Lost)"
    
    log_msg += f"\nRemaining Spins: {spins_left_after_deduct}\nNew Balance: ₹{final_balance_usd * DOLLAR_TO_INR:.2f}"
    await send_log_message(context, log_msg)

    keyboard = [
        [InlineKeyboardButton(MESSAGES[lang]["spin_wheel_button"].format(spins_left=spins_left_after_deduct), callback_data="perform_spin")],
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Use context.bot.edit_message_text as query.edit_message_text might fail after the sleep/animation
    await context.bot.edit_message_text(
        chat_id=query.message.chat_id, message_id=query.message.message_id, text=message, 
        reply_markup=reply_markup, parse_mode='HTML'
    )


async def spin_fake_btn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query: # Check 4: Safety check for query
        await query.answer("🎡 Spinning... Please wait!", show_alert=False)


async def show_missions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: # Added safety check
        return
        
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    if not user_data:
        await query.answer("User data not found.", show_alert=True)
        return
        
    await query.answer()
    
    today = datetime.now().date()
    
    # Reset mission status and counts if the date has changed
    last_search_date = user_data.get("last_search_date")
    last_checkin_date = user_data.get("last_checkin_date")
    
    # Check and reset daily searches and mission completion for 'search_3_movies' and 'claim_daily_bonus' if needed
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
        
    # Get the count of referred users who have triggered a payment today (1 user = 1 paid trigger/day)
    # The mission is now **completed when 3 referred users have successfully triggered a payment (3 paid searches) today**.
    
    # Fetch all referral records for the current user (referrer)
    # FIX: This logic needs to be robust, counting only unique *referred_user_id* that have been paid *today*
    paid_searches_today_count = 0
    referral_records = list(REFERRALS_COLLECTION.find({"referrer_id": user.id}))
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # FIX: Recalculate paid_searches_today_count based on successful daily payments
    for ref_record in referral_records:
        if ref_record.get("last_paid_date") and isinstance(ref_record["last_paid_date"], datetime) and ref_record["last_paid_date"] >= today_start:
             paid_searches_today_count += 1
        
    # Mission: Refer 2 Friends (New user joins)
    referrals_today_count = REFERRALS_COLLECTION.count_documents({
        "referrer_id": user.id,
        "referred_user_id": {"$ne": user.id}, # Exclude self-referral checks
        "join_date": {"$gte": today_start} # Use today_start
    })
    
    user_data = USERS_COLLECTION.find_one({"user_id": user.id}) # Re-fetch updated data
    missions_completed = user_data.get("missions_completed", {})
    daily_searches = user_data.get("daily_searches", 0) # This is the user's *own* search count
    
    message = f"{MESSAGES[lang]['missions_title']}\n\n"
    newly_completed_message = ""
    total_reward = 0.0

    # 1. search_3_movies Mission (Completed by referred users' paid searches)
    mission_key = "search_3_movies"
    mission = DAILY_MISSIONS[mission_key]
    name = mission["name"] if lang == "en" else mission["name_hi"]
    
    if paid_searches_today_count >= mission['target'] and not missions_completed.get(mission_key):
        # Mission completed, give reward
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
        missions_completed[mission_key] = True # Update local dict for message display
        message += f"✅ {name} ({mission['target']}/{mission['target']}) [<b>Completed</b>]\n"
    elif missions_completed.get(mission_key):
        message += f"✅ {name} ({mission['target']}/{mission['target']}) [<b>Completed</b>]\n"
    else:
        message += MESSAGES[lang]["mission_search_note"].format(
            current=min(paid_searches_today_count, mission['target']), # Show actual paid searches count
            target=mission['target']
        ) + "\n"
        
    # 2. refer_2_friends Mission
    mission_key = "refer_2_friends"
    mission = DAILY_MISSIONS[mission_key]
    name = mission["name"] if lang == "en" else mission["name_hi"]
    
    if referrals_today_count >= mission['target'] and not missions_completed.get(mission_key):
        # Mission completed, give reward
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
        missions_completed[mission_key] = True # Update local dict for message display
        message += f"✅ {name} ({mission['target']}/{mission['target']}) [<b>Completed</b>]\n"
    elif missions_completed.get(mission_key):
        message += f"✅ {name} ({mission['target']}/{mission['target']}) [<b>Completed</b>]\n"
    else:
        message += f"⏳ {name} ({min(referrals_today_count, mission['target'])}/{mission['target']}) [In Progress]\n"

    # 3. claim_daily_bonus Mission
    mission_key = "claim_daily_bonus"
    mission = DAILY_MISSIONS[mission_key]
    name = mission["name"] if lang == "en" else mission["name_hi"]
    
    if missions_completed.get(mission_key):
        message += f"✅ {name} [<b>Completed</b>]\n"
    else:
        message += f"⏳ {name} [In Progress]\n"

    # Display total reward if any new missions were completed
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
    if not query or not query.message: # Added safety check
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
        await query.edit_message_text(
            "❌ <b>Request Already Pending!</b>\n\nYour previous withdrawal request is still being processed.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
        )
        return
    
    withdrawal_data = {
        "user_id": user.id,
        "username": user.username,
        "full_name": user.full_name,
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
            # Added a unique identifier to the callback_data for withdrawal ID if available, 
            # though using user_id is fine for simple pending checks.
            # withdrawal_id = withdrawal_data.get("_id") # Assuming MongoDB provides this after insert
            
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

# --- Other Menu Handlers (Language, Help, Groups, Tier) ---

async def language_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: # Added safety check for query and message
        return
        
    await query.answer()
    lang = await get_user_lang(query.from_user.id)
    
    keyboard = [
        [InlineKeyboardButton("English 🇬🇧", callback_data="lang_en")],
        [InlineKeyboardButton("हिन्दी 🇮🇳", callback_data="lang_hi")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Fix: Use 'language_prompt' which was added to config.py
    try:
        message_text = MESSAGES[lang]["language_prompt"]
    except KeyError:
        logger.error(f"KeyError: 'language_prompt' missing for language '{lang}'. Using fallback.")
        message_text = "Please select your language:" # Fallback message

    await query.edit_message_text(message_text, reply_markup=reply_markup)


async def handle_lang_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
        
    await query.answer()
    new_lang = query.data.split("_")[1]
    
    await set_user_lang(query.from_user.id, new_lang)
    
    # Re-send main menu in the new language
    await back_to_main_menu(update, context) 


async def show_withdraw_details_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: # Added safety check
        return
        
    await query.answer()
    user = query.from_user
    lang = await get_user_lang(user.id)
    
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    
    # --- Pending Withdrawal Check ---
    pending_count = WITHDRAWALS_COLLECTION.count_documents({"user_id": user.id, "status": "pending"})
    
    earnings_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR
    
    message = MESSAGES[lang]["withdrawal_details_message"].format(
        balance=f"₹{earnings_inr:.2f}"
    )
    
    # "Pending Withdrawal" बटन का लॉजिक
    pending_button = InlineKeyboardButton(f"⏳ Pending Withdrawals ({pending_count})", callback_data="show_user_pending_withdrawals")
    
    keyboard = [
        [InlineKeyboardButton("💸 Request Withdrawal (Min ₹80)", callback_data="request_withdrawal")],
        [pending_button], # नया बटन जोड़ा गया है
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

# --- नया फ़ंक्शन: यूज़र के लिए लंबित निकासी (Pending Withdrawals) दिखाना ---
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
        # In python, use simple formatting for the description
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
    if not query or not query.message: # Added safety check
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
    
    # Check 5: Handle cases where a callback query might be missing (e.g., direct /start or old query)
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
    
    # Handle message edit/send based on whether it's a callback or a new command/menu
    if query: # If it came from a callback
        if query.message: # Check 6: Ensure message exists before deleting/editing
            if query.message.photo:
                try:
                    await query.message.delete()
                except Exception:
                    pass
                    
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=message, 
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            else:
                try: # Check 7: Added try-except for edit_message_text (common source of 'NoneType' or 'Message not modified')
                    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
                except TelegramError as e:
                    if "Message is not modified" not in str(e):
                        logger.error(f"Error editing message in back_to_main_menu: {e}")
                    pass
        else:
             # Fallback if query exists but message is None (very rare, means message was deleted)
             await context.bot.send_message(chat_id=user.id, text=message, reply_markup=reply_markup, parse_mode='HTML')
             
    elif update.message: # If it came from a /command
        await update.message.reply_html(message, reply_markup=reply_markup)


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: # Added safety check
        return
        
    await query.answer()
    lang = await get_user_lang(query.from_user.id)
    
    # Fix: Corrected key from help_message to help_message_text
    message = MESSAGES[lang].get("help_message", MESSAGES["en"]["help_message"]).format(
        telegram_handle=YOUR_TELEGRAM_HANDLE
    )
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def show_tier_benefits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: # Added safety check
        return
        
    await query.answer()
    lang = await get_user_lang(query.from_user.id)
    
    # Fix: Corrected key from tier_benefits_message to tier_benefits_message
    message = MESSAGES[lang].get("tier_benefits_message", MESSAGES["en"]["tier_benefits_message"])
    
    # Display table of tiers/rates (you need to construct this message dynamically from TIERS)
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def show_refer_example(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: # Added safety check
        return
        
    await query.answer()
    user = query.from_user
    lang = await get_user_lang(query.from_user.id)
    
    # 'Referral Example' बटन को काम करने के लिए, मैंने एक अस्थायी मैसेज दिया है।
    # आप इसे 'MESSAGES' कॉन्फ़िग में 'refer_example_message' से बदल सकते हैं।
    message_template = MESSAGES[lang].get("refer_example_message", MESSAGES["en"]["refer_example_message"])
    
    # Added dynamic rate to the message if it uses the placeholder
    rate = TIERS[4]["rate"]
    message = message_template.format(rate=rate)
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send message with photo - Added delete on success check
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
                # Original message delete
                await query.message.delete()
            except:
                pass
        except Exception as e:
            logger.error(f"Failed to send photo in show_refer_example: {e}")
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def claim_channel_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: # Added safety check
        return
        
    user = query.from_user
    lang = await get_user_lang(user.id)
    username_display = f"@{user.username}" if user.username else f"<code>{user.id}</code>"
    
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    if user_data.get("channel_bonus_received"):
        await query.answer("✅ Channel Bonus Already Claimed!", show_alert=True)
        return
        
    await query.answer("Checking channel membership...")
    
    try:
        # Check membership (replace with actual channel ID if different from CHANNEL_USERNAME)
        member = await context.bot.get_chat_member(CHANNEL_ID, user.id)
        is_member = member.status in ["member", "administrator", "creator"]
    except TelegramError as e:
        logger.error(f"Error checking channel membership for {user.id}: {e}")
        is_member = False
        
    if is_member:
        bonus_usd = CHANNEL_BONUS / DOLLAR_TO_INR
        
        result = USERS_COLLECTION.find_one_and_update(
            {"user_id": user.id, "channel_bonus_received": False},
            {"$inc": {"earnings": bonus_usd}, "$set": {"channel_bonus_received": True}},
            return_document=True
        )
        
        if result:
            new_balance_inr = result.get("earnings", 0.0) * DOLLAR_TO_INR
            # Button name change is handled by config update
            await query.edit_message_text(
                MESSAGES[lang]["channel_bonus_claimed"].format(amount=CHANNEL_BONUS, new_balance=new_balance_inr, channel=CHANNEL_USERNAME), # Fix: Added channel name to format
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
            )
            log_msg = f"🎁 <b>Channel Bonus Claimed</b>\nUser: {username_display}\nAmount: ₹{CHANNEL_BONUS:.2f}\nNew Balance: ₹{new_balance_inr:.2f}"
            await send_log_message(context, log_msg)
            return
            
    # If not a member or update failed
    # Channel name button change: Now using JOIN_CHANNEL_LINK for the URL
    await query.edit_message_text(
        MESSAGES[lang]["channel_bonus_failure"].format(channel=CHANNEL_USERNAME), # Fix: Using correct key and formatting
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(MESSAGES[lang]["join_channel_button_text"], url=JOIN_CHANNEL_LINK)],
            [InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]
        ]),
        parse_mode='HTML'
    )

# --- Admin Handlers ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the main admin panel menu."""
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        if update.message:
            try:
                await update.message.reply_text("❌ Access Denied.")
            except:
                pass
        return

    # Store state for admin inputs
    context.user_data["admin_state"] = None
    
    # Fix: Use message from config (admin_panel_title)
    lang = await get_user_lang(user.id)
    message = MESSAGES[lang].get("admin_panel_title", "👑 <b>Admin Panel</b>\n\nSelect an action:")

    # 'Top Users' बटन हटा दिया गया है
    # 'Broadcast' और 'Set Referral Rate' बटन अब काम करते हैं
    keyboard = [
        [InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_set_broadcast"),
         InlineKeyboardButton("💸 Pending Withdrawals", callback_data="admin_pending_withdrawals")],
        [InlineKeyboardButton("⚙️ Set Referral Rate", callback_data="admin_set_ref_rate"),
         InlineKeyboardButton("📊 Bot Stats", callback_data="admin_stats")], # New button for Bot Stats
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message: # Check 8: Ensure message exists for command handler
        await update.message.reply_html(message, reply_markup=reply_markup)
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

# Added a function to go back to admin menu for clarity
async def back_to_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query:
        await query.answer()
    await admin_panel(update, context)


async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    
    # Check 9: Ensure query and message objects exist to avoid NoneType error
    if not query or not query.message:
        logger.warning("handle_admin_callbacks called without query or message.")
        return
        
    await query.answer()
    
    user = query.from_user
    if user.id != ADMIN_ID:
        await query.edit_message_text("❌ Access Denied.")
        return

    # Correct parsing of callback data
    data = query.data.split("_")
    action = data[1]
    sub_action = data[2] if len(data) > 2 else None
    
    if action == "clearjunk":
        await clearjunk_logic(update, context) # Placeholder, not requested in final fix but kept
    elif action == "pending" and sub_action == "withdrawals":
        await show_pending_withdrawals(update, context)
    elif action == "stats": # New logic for Bot Stats
        await show_bot_stats(update, context)
    elif action == "set": 
        if sub_action == "broadcast":
            context.user_data["admin_state"] = "waiting_for_broadcast_message"
            await query.edit_message_text("✍️ Enter the **message** you want to broadcast to all users:")
        elif sub_action == "ref" and data[3] == "rate":
             context.user_data["admin_state"] = "waiting_for_ref_rate"
             await query.edit_message_text("✍️ Enter the **NEW Tier 1 Referral Rate** in INR (e.g., 5.0 for ₹5 per referral):")
    elif action == "pending" or action == "stats": # Back button from withdrawals or stats
        await back_to_admin_menu(update, context) 
    
    # Withdrawal approval/rejection is handled by handle_withdrawal_approval


async def show_bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows overall bot statistics."""
    query = update.callback_query
    if not query or not query.message:
        return

    lang = await get_user_lang(query.from_user.id)
    stats = await get_bot_stats() # New function in db_utils.py

    message = MESSAGES[lang].get("stats_message", "📊 <b>Bot Stats</b>\n\nTotal Users: {total_users}\nApproved Users: {approved_users}").format(
        total_users=stats["total_users"],
        approved_users=stats["approved_users"]
    )
    
    keyboard = [[InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_pending")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def show_pending_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: # Added safety check
        return
        
    pending_withdrawals = WITHDRAWALS_COLLECTION.find({"status": "pending"}).sort("request_date", 1)
    
    message = "<b>💸 Pending Withdrawals</b>\n\n"
    keyboard = []
    
    # Using count_documents() is better if you only need the count
    count = WITHDRAWALS_COLLECTION.count_documents({"status": "pending"})

    if count == 0:
        message += "✅ No pending withdrawal requests."
    else:
        # Iterate over the cursor
        for request in pending_withdrawals:
            user_id = request["user_id"]
            amount = request["amount_inr"]
            username = request.get("username", "N/A")
            
            message += f"👤 User: <code>{user_id}</code> (@{username})\n💰 Amount: ₹{amount:.2f}\n"
            
            # Add buttons for each request (limited to prevent huge messages)
            if len(keyboard) < 5: 
                keyboard.append([
                    InlineKeyboardButton(f"Approve {user_id}", callback_data=f"approve_withdraw_{user_id}"),
                    InlineKeyboardButton(f"Reject {user_id}", callback_data=f"reject_withdraw_{user_id}")
                ])
                
        message += "\n(Showing up to 5 requests. Use buttons to process.)"


    keyboard.append([InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_pending")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles text input from the admin based on the current admin_state."""
    user = update.effective_user
    if user.id != ADMIN_ID or not update.message:
        return
        
    admin_state = context.user_data.get("admin_state")
    text = update.message.text
    
    # Fix: Reset admin state if user sends /admin to ensure smooth navigation
    if admin_state is None and update.message.text and update.message.text.startswith('/admin'):
        await admin_panel(update, context)
        return

    if admin_state == "waiting_for_broadcast_message":
        # Broadcast logic
        success_count = 0
        fail_count = 0
        
        # Initial message to admin
        status_message = await update.message.reply_text("📢 Starting broadcast... This may take a moment. Updates will be shown here.")
        
        # Find approved users (Assuming `is_approved` is correct flag)
        user_ids_cursor = USERS_COLLECTION.find({"is_approved": True}, {"user_id": 1}) 
        total_users = USERS_COLLECTION.count_documents({"is_approved": True})
        
        for i, user_data in enumerate(user_ids_cursor):
            user_id = user_data["user_id"]
            
            # Update admin message every 100 users
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
                # Use HTML parse mode for the broadcast message
                await context.bot.send_message(user_id, text, parse_mode='HTML', disable_web_page_preview=True)
                success_count += 1
                await asyncio.sleep(0.05) # Throttle to respect rate limits (20 messages per minute in private chats)
                
            except FloodWait as e:
                wait_time = e.retry_after + 1 
                logger.warning(f"FloodWait encountered for user {user_id}. Waiting for {wait_time} seconds. Success: {success_count}, Fail: {fail_count}")
                await context.bot.edit_message_text(
                     chat_id=status_message.chat_id, 
                     message_id=status_message.message_id,
                     text=f"⚠️ **PAUSED: FloodWait**\nWaiting for {wait_time} seconds...\nSent to {i} of {total_users} users.\nSuccess: {success_count} / Failed: {fail_count}"
                )
                await asyncio.sleep(wait_time)
                # After waiting, retry sending to the *current* user (important!)
                try:
                    await context.bot.send_message(user_id, text, parse_mode='HTML', disable_web_page_preview=True)
                    success_count += 1
                    await asyncio.sleep(0.05)
                except Exception:
                     fail_count += 1
                
            except (Forbidden, BadRequest) as e:
                # Forbidden: User blocked the bot. BadRequest: Chat not found, message invalid, etc.
                fail_count += 1
                USERS_COLLECTION.update_one({"user_id": user_id}, {"$set": {"is_approved": False}}) # Optional: Mark as unapproved
                logger.warning(f"Failed to send to user {user_id} due to API Error: {e}. User marked unapproved (optional).")
                
            except Exception as e:
                fail_count += 1
                logger.error(f"Unknown error sending to user {user_id}: {e}")
                
        context.user_data["admin_state"] = None
        # Final status update
        await context.bot.edit_message_text(
            chat_id=status_message.chat_id, 
            message_id=status_message.message_id,
            text=f"✅ **Broadcast complete**.\nSuccessful: {success_count}\nFailed: {fail_count}\nTotal users processed: {total_users}"
        )


    elif admin_state == "waiting_for_ref_rate":
        # Set new referral rate logic - Fix: This now uses SETTINGS_COLLECTION for Tier 1
        try:
            new_rate = float(text)
            if new_rate <= 0:
                 raise ValueError
            
            # Update the global setting for Tier 1 rate in SETTINGS_COLLECTION
            SETTINGS_COLLECTION.update_one(
                {"_id": "referral_rate"}, # Assuming get_referral_bonus_inr uses this
                {"$set": {"rate_inr": new_rate}},
                upsert=True
            )
            
            # Note: The TIERS dict in config.py is hardcoded, but db_utils gets the rate from SETTINGS if available.
            
            context.user_data["admin_state"] = None
            await update.message.reply_text(f"✅ Referral rate successfully updated to **₹{new_rate:.2f}** per referral.")
            
        except ValueError:
            await update.message.reply_text("❌ Invalid input. Please enter a valid number for the new rate (e.g., 5.0).")
            
    # Add other admin input handlers here


async def handle_withdrawal_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query: # Added safety check
        return
        
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        if query.message:
            await query.edit_message_text("❌ Access Denied.")
        return
        
    parts = query.data.split("_")
    action = parts[0] # approve or reject
    user_id_str = parts[2]
    user_id = int(user_id_str)

    withdrawal_request = WITHDRAWALS_COLLECTION.find_one_and_update(
        {"user_id": user_id, "status": "pending"},
        {"$set": {"status": action, "approved_date": datetime.now()}},
        return_document=True
    )

    if not withdrawal_request:
        if query.message:
            await query.edit_message_text(f"❌ Withdrawal request for user <code>{user_id}</code> not found or already processed.", parse_mode='HTML')
        return

    amount_inr = withdrawal_request["amount_inr"]
    
    if action == "approve":
        # Deduct earnings
        amount_usd = amount_inr / DOLLAR_TO_INR
        USERS_COLLECTION.update_one(
            {"user_id": user_id},
            {"$inc": {"earnings": -amount_usd}}
        )
        
        # Notify user
        try:
            user_lang = await get_user_lang(user_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=MESSAGES[user_lang]["withdrawal_approved_user"].format(amount=amount_inr), # Fix: Use _user version
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Could not notify user {user_id} of approval: {e}")
        
        if query.message:
            await query.edit_message_text(f"✅ Request for user <code>{user_id}</code> (**₹{amount_inr:.2f}**) **APPROVED**.\nFunds deducted.", parse_mode='HTML')
        log_msg = f"💸 <b>Withdrawal Approved</b>\nAdmin: <code>{query.from_user.id}</code>\nUser: <code>{user_id}</code>\nAmount: ₹{amount_inr:.2f}"
    
    else: # reject
        # Notify user
        try:
            user_lang = await get_user_lang(user_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=MESSAGES[user_lang]["withdrawal_rejected_user"].format(amount=amount_inr), # Fix: Use _user version
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Could not notify user {user_id} of rejection: {e}")
        
        if query.message:
            await query.edit_message_text(f"❌ Request for user <code>{user_id}</code> (**₹{amount_inr:.2f}**) **REJECTED**.", parse_mode='HTML')
        log_msg = f"🚫 <b>Withdrawal Rejected</b>\nAdmin: <code>{query.from_user.id}</code>\nUser: <code>{user_id}</code>\nAmount: ₹{amount_inr:.2f}"

    await send_log_message(context, log_msg)
    # Re-show pending withdrawals if the message exists
    if query.message:
        # Avoid show_pending_withdrawals if it came from the earning panel withdraw button
        if "admin" in query.data:
            await show_pending_withdrawals(update, context) # Refresh list

# --- Top Users Logic (Moved to Earning Panel) ---
async def show_top_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message:
        return
        
    await query.answer()
    
    # Find top 10 users by earnings
    top_users_cursor = USERS_COLLECTION.find().sort("earnings", -1).limit(10)
    
    message = "🏆 <b>Top 10 Earners</b> 🏆\n\n"
    keyboard_links = []
    
    for i, user_data in enumerate(top_users_cursor):
        user_id = user_data["user_id"]
        earnings_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR
        username = user_data.get("username")
        
        display_name = f"@{username}" if username else f"User {user_id}"
        
        # Link Logic: Blue name, click to view profile. 
        # Using a t.me link for profile view.
        user_link = f"tg://user?id={user_id}"
        
        # Add to the message as bold/blue text (HTML 'a' tag)
        message += f"{i+1}. <a href='{user_link}'><b>{display_name}</b></a>: ₹{earnings_inr:.2f}\n"

    keyboard = [[InlineKeyboardButton("⬅️ Back to Earning Panel", callback_data="show_earning_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
    

async def topusers_logic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # This is the old admin logic, which is now obsolete but kept for reference/cleanup.
    # The actual 'Top Users' logic is in show_top_users
    await show_top_users(update, context) # Forwarding to the new public view


async def clearjunk_logic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: # Added safety check
        return
        
    # Example: Logic to find and delete junk data (e.g., users with 0 earnings who never completed a mission)
    # NOTE: Implement this carefully!
    
    # junk_count = USERS_COLLECTION.count_documents({
    #     "earnings": 0.0,
    #     "welcome_bonus_received": False,
    #     "spins_left": 0
    # })
    
    # delete_result = USERS_COLLECTION.delete_many({
    #     "earnings": 0.0,
    #     "welcome_bonus_received": False,
    #     "spins_left": 0
    # })
    
    # Use delete_many with a specific, safe query if needed, or leave it as a placeholder:
    delete_result = {"deleted_count": 0} # Placeholder
    
    message = f"🗑️ **Clear Junk Operation**\n\nCompleted! Deleted {delete_result['deleted_count']} inactive user records."
    
    keyboard = [[InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_pending")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

# --- Utility Handlers ---
async def set_bot_commands_logic(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sets the bot commands for both user and admin in the BotFather menu."""
    user_commands = [
        BotCommand("start", "Start the bot and see the main menu"),
        BotCommand("earn", "Go to the earning panel"),
    ]
    admin_commands = user_commands + [
        BotCommand("admin", "Admin Panel (for admin only)")
    ]

    await context.bot.set_my_commands(user_commands)
    # BotCommandScopeChat is not imported in the original code, this line will likely fail
    # await context.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=ADMIN_ID)) 
    logger.info("Bot commands set successfully.")
