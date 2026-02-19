# handlers.py

import logging
import random
import time
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, ChatJoinRequest
from telegram.error import TelegramError, TimedOut, Forbidden, BadRequest, RetryAfter as FloodWait 
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import asyncio

from config import (
    USERS_COLLECTION, REFERRALS_COLLECTION, SETTINGS_COLLECTION, WITHDRAWALS_COLLECTION,
    DOLLAR_TO_INR, MESSAGES, ADMIN_ID, YOUR_TELEGRAM_HANDLE, 
    SPIN_WHEEL_CONFIG, SPIN_PRIZES, SPIN_WEIGHTS, TIERS, DAILY_MISSIONS,
    CHANNEL_USERNAME, CHANNEL_BONUS, FORCE_JOIN_CHANNELS, MIN_WITHDRAWAL_INR,
    NEW_MOVIE_GROUP_LINK, MOVIE_GROUP_LINK, ALL_GROUPS_LINK, EXAMPLE_SCREENSHOT_URL,
    WITHDRAWAL_REQUIREMENTS, WITHDRAWAL_METHODS, PRIVATE_CHANNELS, REQUEST_MODE,
    JOIN_REQUESTS_COLLECTION, FORCE_SUB_IMAGE_URL
)
from db_utils import (
    send_log_message, get_user_lang, set_user_lang, get_referral_bonus_inr, 
    get_welcome_bonus, get_user_tier, get_tier_referral_rate, 
    claim_and_update_daily_bonus, update_daily_searches_and_mission,
    get_bot_stats, pay_referrer_and_update_mission,
    get_user_stats, admin_add_money, admin_clear_earnings, admin_delete_user, clear_junk_users
)
from image_utils import generate_leaderboard_image

logger = logging.getLogger(__name__)


# --- 1. NEW HANDLER: CAPTURE JOIN REQUEST ---
async def on_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Jab user 'Request to Join' click karega, ye trigger hoga."""
    request = update.chat_join_request
    user_id = request.from_user.id
    chat_id = request.chat.id
    
    logger.info(f"Join Request Received: User {user_id} -> Channel {chat_id}")
    
    # DB mein save kar lo ki isne request bhej di hai
    JOIN_REQUESTS_COLLECTION.update_one(
        {"user_id": user_id, "chat_id": chat_id},
        {"$set": {"requested_at": datetime.now(), "status": "pending"}},
        upsert=True
    )
    # Admin (Tum) baad mein approve karte rehna, user DB mein aa gaya.


# --- 2. UPDATED CHECK FUNCTION (Request + Join dono check karega) ---
async def check_channel_membership(bot, user_id):
    """Checks if user is member OR has sent a join request (Fix for Private Channels)."""
    try:
        for channel_id in FORCE_JOIN_CHANNELS:
            is_verified = False
            
            # 1. पहले चेक करें कि क्या वो पहले से मेंबर है
            try:
                member = await bot.get_chat_member(channel_id, user_id)
                if member.status in ["member", "administrator", "creator"]:
                    is_verified = True
            except Exception:
                pass # अगर एरर आया (मतलब मेंबर नहीं है), तो हम रिक्वेस्ट चेक करेंगे

            # 2. अगर मेंबर नहीं है, तो चेक करें कि क्या उसने रिक्वेस्ट भेजी है?
            # यह Database (JOIN_REQUESTS_COLLECTION) चेक करेगा जो on_join_request में save होता है
            if not is_verified and REQUEST_MODE and channel_id in PRIVATE_CHANNELS:
                # DB check
                request_found = JOIN_REQUESTS_COLLECTION.find_one({"user_id": user_id, "chat_id": channel_id})
                if request_found:
                    is_verified = True

            # अगर दोनों चेक फेल हो गए, तो False return करें
            if not is_verified:
                return False
            
        return True # सब पास हो गए
    except Exception as e:
        logger.error(f"Force Subscribe Check Failed: {e}")
        return False


# --- VERIFY CHANNEL JOIN CALLBACK (MULTI-CHANNEL) ---
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
        await query.answer("❌ You have NOT joined all channels! Join first.", show_alert=True)
        
        # Generate invite links for all channels
        keyboard = []
        for i, channel_id in enumerate(FORCE_JOIN_CHANNELS):
            try:
                # Agar Private Channel hai aur Request Mode ON hai
                if channel_id in PRIVATE_CHANNELS and REQUEST_MODE:
                    # Create Request Link
                    link_obj = await context.bot.create_chat_invite_link(
                        chat_id=channel_id,
                        name=f"Bot_Req_{user.id}",
                        creates_join_request=True 
                    )
                    link = link_obj.invite_link
                    btn_text = f"🔐 Request Join Channel {i+1}"
                else:
                    chat = await context.bot.get_chat(channel_id)
                    link = chat.invite_link
                    if not link:
                        link = await context.bot.export_chat_invite_link(channel_id)
                    btn_text = f"🚀 Join Channel {i+1}"
                    
                keyboard.append([InlineKeyboardButton(btn_text, url=link)])
            except Exception as e:
                logger.error(f"Failed to get invite link for {channel_id}: {e}")
                keyboard.append([InlineKeyboardButton(f"🚀 Join Channel {i+1}", url=f"https://t.me/c/{str(channel_id)[4:]}")])
        
        keyboard.append([InlineKeyboardButton("🔄 Try Again / Verify", callback_data="verify_channel_join")])
        
        await query.edit_message_text(
            "⚠️ **Access Denied!**\n\nआपको आगे बढ़ने के लिए नीचे दिए गए सभी चैनल्स को जॉइन करना होगा।",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    error_detail = str(context.error)
    if "Message is not modified" in error_detail:
        logger.warning("Ignoring 'Message is not modified' error.")
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


# --- UPDATED START COMMAND WITH MULTI-CHANNEL FORCE JOIN ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    full_name = user.first_name + (f" {user.last_name}" if user.last_name else "")
    username_display = f"<a href='tg://user?id={user.id}'>{full_name}</a>"
    
    # --- FORCE JOIN CHECK (MULTI-CHANNEL) ---
    is_member = await check_channel_membership(context.bot, user.id)
    
    if not is_member:
        # Generate invite links for all channels
        keyboard = []
        for i, channel_id in enumerate(FORCE_JOIN_CHANNELS):
            try:
                # Agar Private Channel hai aur Request Mode ON hai
                if channel_id in PRIVATE_CHANNELS and REQUEST_MODE:
                    # Create Request Link (creates_join_request=True)
                    link_obj = await context.bot.create_chat_invite_link(
                        chat_id=channel_id,
                        name=f"Bot_Ref_{user.id}",
                        creates_join_request=True 
                    )
                    link = link_obj.invite_link
                    btn_text = f"🔐 Request Join Channel {i+1}"
                else:
                    # Public Channel Logic
                    chat = await context.bot.get_chat(channel_id)
                    link = chat.invite_link
                    if not link:
                        link = await context.bot.export_chat_invite_link(channel_id)
                    btn_text = f"🚀 Join Channel {i+1}"
                
                keyboard.append([InlineKeyboardButton(btn_text, url=link)])
            except Exception as e:
                logger.error(f"Link Generation Failed for {channel_id}: {e}")
                keyboard.append([InlineKeyboardButton(f"🚀 Join Channel {i+1}", url=f"https://t.me/c/{str(channel_id)[4:]}")])
        
        keyboard.append([InlineKeyboardButton("✅ Verify Join", callback_data="verify_channel_join")])
        
        msg = (
            f"👋 <b>Hello {user.first_name}!</b>\n\n"
            f"⛔️ <b>Access Denied!</b>\n"
            f"You must join our official channels to use this bot.\n"
            f"<i>(Private channel ke liye Request bhejein, bot turant verify kar lega)</i>"
        )
        if update.message:
            await update.message.reply_photo(
                photo=FORCE_SUB_IMAGE_URL,
                caption=msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
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
            "monthly_referrals": 0,
            "payment_method": None,
            "payment_details": None
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


# --- UPDATED GROUP MESSAGE HANDLER (NO JOB QUEUE) ---
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

    # 1. Update Daily Searches
    await update_daily_searches_and_mission(user.id)
    
    # 2. Check Referral Logic (DIRECT EXECUTION - NO JOB QUEUE)
    referral_data = REFERRALS_COLLECTION.find_one({"referred_user_id": user.id})
    
    if referral_data:
        referrer_id = referral_data["referrer_id"]
        
        if referrer_id != user.id:
            # Check if already paid today
            last_paid_date = referral_data.get("last_paid_date")
            today = datetime.now().date()
            
            already_paid = False
            if last_paid_date and isinstance(last_paid_date, datetime) and last_paid_date.date() == today:
                already_paid = True
            
            if not already_paid:
                # Direct Pay Function Call
                success, daily_amount = await pay_referrer_and_update_mission(context, user.id, referrer_id)
                if success:
                    logger.info(f"Referral Paid INSTANTLY: {referrer_id} from {user.id} (Amount: {daily_amount})")


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
        [InlineKeyboardButton("💸 Withdraw Money", callback_data="request_withdrawal"),
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


# --- NEW ADVANCED WITHDRAWAL SYSTEM WITH TOP/BOTTOM BUTTONS ---

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
    method = user_data.get("payment_method")
    details = user_data.get("payment_details")
    
    # पेंडिंग रिक्वेस्ट चेक करें
    pending = WITHDRAWALS_COLLECTION.find_one({"user_id": user.id, "status": "pending"})
    
    text = f"💰 **Withdrawal Manager**\n\n"
    text += f"💵 **Balance:** ₹{earnings_inr:.2f}\n"
    
    keyboard = []
    
    # TOP BUTTON: Withdraw (बड़ा बटन)
    if pending:
        text += f"⏳ **Status:** Request Pending (₹{pending['amount_inr']:.2f})\n"
        keyboard.append([InlineKeyboardButton("⏳ Processing...", callback_data="dummy")])
    elif earnings_inr < MIN_WITHDRAWAL_INR:
        text += f"❌ **Minimum ₹{MIN_WITHDRAWAL_INR} required!**\n"
        keyboard.append([InlineKeyboardButton(f"💸 Need ₹{MIN_WITHDRAWAL_INR} to Withdraw", callback_data="dummy")])
    elif method and details:
        keyboard.append([InlineKeyboardButton("💸 WITHDRAW MONEY 💸", callback_data="process_withdraw_final")])
    else:
        keyboard.append([InlineKeyboardButton("⚠️ Setup Payment Details", callback_data="select_withdraw_method")])

    # MIDDLE: Show Saved Details
    if method:
        text += f"💳 **Method:** {method.upper()}\n📝 **Details:** {details}\n"
        btn_text = "✏️ Edit Details"
    else:
        text += "❌ **Payment Details Not Set!**\n"
        btn_text = "➕ Add Details"

    # BOTTOM BUTTONS
    keyboard.append([InlineKeyboardButton(btn_text, callback_data="select_withdraw_method")])
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def show_withdrawal_method_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    msg = "🏦 <b>Select Withdrawal Method:</b>\n\nChoose where you want to receive your money."
    keyboard = [
        [InlineKeyboardButton("🇮🇳 UPI (GPay/PhonePe)", callback_data="set_method_upi")],
        [InlineKeyboardButton("🏦 Bank Transfer", callback_data="set_method_bank")],
        [InlineKeyboardButton("⬅️ Cancel", callback_data="request_withdrawal")]
    ]
    try:
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except:
        await context.bot.send_message(query.from_user.id, msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def handle_method_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    method = query.data.split("_")[2] # upi or bank
    context.user_data["setup_withdraw_method"] = method
    context.user_data["state"] = "waiting_for_withdraw_details"
    
    msg = ""
    if method == "upi":
        msg = "✍️ <b>Enter your UPI ID:</b>\n\nExample: `username@oksbi`"
    else:
        msg = "✍️ <b>Enter Bank Details:</b>\n\nFormat: `AccountNo, IFSC, HolderName`"
    
    msg += "\n\n<i>Send your details in the next message.</i>"
    
    await query.edit_message_text(msg, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Cancel", callback_data="request_withdrawal")]]))


async def process_withdraw_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Processing...", show_alert=False)
    
    user = query.from_user
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    earnings_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR
    
    # Minimum balance check
    if earnings_inr < MIN_WITHDRAWAL_INR:
        await query.answer(f"❌ Minimum ₹{MIN_WITHDRAWAL_INR} required!", show_alert=True)
        return
    
    # TIERED REFERRAL CHECK
    referrals_count = REFERRALS_COLLECTION.count_documents({"referrer_id": user.id})
    required_referrals = 0
    
    for requirement in WITHDRAWAL_REQUIREMENTS:
        if earnings_inr >= requirement["min_balance"]:
            required_referrals = requirement["required_refs"]
            break 
    
    if referrals_count < required_referrals:
        msg = (
            f"❌ <b>Insufficient Referrals!</b>\n\n"
            f"Your balance is <b>₹{earnings_inr:.2f}</b>, you need <b>{required_referrals} referrals</b> to withdraw.\n\n"
            f"👤 Your Current Referrals: {referrals_count}/{required_referrals}"
        )
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]), parse_mode='HTML')
        return

    # Pending check
    existing_request = WITHDRAWALS_COLLECTION.find_one({"user_id": user.id, "status": "pending"})
    if existing_request:
        await query.edit_message_text("⚠️ You already have a pending request!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]))
        return

    # Create Request
    payment_details = f"{user_data['payment_method'].upper()}: {user_data['payment_details']}"
    
    withdrawal_data = {
        "user_id": user.id,
        "username": user.username,
        "full_name": user.first_name,
        "amount_inr": earnings_inr,
        "status": "pending",
        "request_date": datetime.now(),
        "approved_date": None,
        "payment_details": payment_details
    }
    
    WITHDRAWALS_COLLECTION.insert_one(withdrawal_data)
    
    # Notify Admin
    if ADMIN_ID:
        admin_msg = (
            f"🔄 <b>New Withdrawal Request</b>\n"
            f"User: {user.first_name} (ID: {user.id})\n"
            f"Amount: <b>₹{earnings_inr:.2f}</b>\n"
            f"Details: {payment_details}"
        )
        try:
            await context.bot.send_message(ADMIN_ID, admin_msg, parse_mode='HTML', 
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Approve", callback_data=f"approve_withdraw_{user.id}"),
                     InlineKeyboardButton("❌ Reject", callback_data=f"reject_withdraw_{user.id}")]
                ]))
        except: pass

    await query.edit_message_text(
        f"✅ <b>Request Sent!</b>\n\nAmount: ₹{earnings_inr:.2f}\nDetails: {payment_details}\n\nYou will receive it within 24 hours.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]])
    )

# --- END NEW WITHDRAWAL SYSTEM ---


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
            
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]
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
    
    message = MESSAGES[lang]["help_message"].format(
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
        # Check all channels for bonus eligibility (using first channel for bonus)
        channel_id = FORCE_JOIN_CHANNELS[0] if FORCE_JOIN_CHANNELS else 0
        member = await context.bot.get_chat_member(channel_id, user.id)
        is_member = member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Error checking channel membership for {user.id}: {e}")

        await send_log_message(
            context, 
            f"🚨 **Channel Check Error!**\n\nFailed to check membership for User <code>{user.id}</code> in channel <code>{channel_id}</code>.\nError: <code>{e}</code>\n\n<b>FIX:</b> Ensure bot is admin in the channel."
        )

        await query.answer(MESSAGES[lang]["channel_bonus_error"].format(channel=CHANNEL_USERNAME), show_alert=True)

        # Generate dynamic link for retry
        try:
            chat = await context.bot.get_chat(channel_id)
            invite_link = chat.invite_link
            if not invite_link:
                invite_link = await context.bot.export_chat_invite_link(channel_id)
        except:
            invite_link = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"

        join_button = InlineKeyboardButton("🔗 Join Channel", url=invite_link)
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
        
    # Generate dynamic link for failure case
    try:
        chat = await context.bot.get_chat(channel_id)
        invite_link = chat.invite_link
        if not invite_link:
            invite_link = await context.bot.export_chat_invite_link(channel_id)
    except:
        invite_link = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
        
    join_button = InlineKeyboardButton("🔗 Join Channel", url=invite_link)
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


# --- UPDATED SHOW LEADERBOARD (Wait Message + Image) ---
async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message:
        return
        
    await query.answer()
    
    user_id = query.from_user.id
    
    # 1. Please Wait Message (User ki tassalli ke liye)
    wait_msg = await query.message.reply_text("⏳ <b>Generating Leaderboard...</b>\n<i>Please wait while we load top users...</i>", parse_mode='HTML')
    
    try:
        # 2. Data Fetch
        top_users = list(USERS_COLLECTION.find().sort("monthly_referrals", -1).limit(10))
        
        leaderboard_data = []
        for usr in top_users:
            leaderboard_data.append({
                "name": usr.get("full_name", "Unknown"),
                "refs": usr.get("monthly_referrals", 0)
            })

        if not leaderboard_data:
            await wait_msg.edit_text("❌ No data yet.")
            return

        # 3. Image Generation (Blocking code ko alag thread mein run karein)
        loop = asyncio.get_running_loop()
        # image_utils wali function call
        photo_bio = await loop.run_in_executor(None, generate_leaderboard_image, leaderboard_data)
        
        # 4. Send Photo
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_earning_panel")]]
        
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=photo_bio,
            caption="🏆 <b>Top 10 Leaderboard</b>",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # 5. Cleanup
        await wait_msg.delete() # Wait message delete
        try:
            await query.message.delete() # Old menu delete
        except: pass

    except Exception as e:
        logger.error(f"LB Error: {e}")
        await wait_msg.edit_text("❌ Error loading leaderboard.")


async def show_leaderboard_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message:
        return
    
    await query.answer()
    lang = await get_user_lang(query.from_user.id)
    
    message = f"<b>💡 Leaderboard Benefits</b>\n\n{MESSAGES[lang]['leaderboard_info_text']}"
    
    keyboard = [[InlineKeyboardButton("⬅️ Back to Leaderboard", callback_data="show_leaderboard")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
