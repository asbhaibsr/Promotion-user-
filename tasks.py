import logging
from telegram.ext import ContextTypes
from datetime import datetime
import asyncio
import random
from telegram.error import TelegramError

from config import (
    USERS_COLLECTION, REFERRALS_COLLECTION, DOLLAR_TO_INR, DAILY_MISSIONS, 
    MESSAGES, TIERS
)
from db_utils import pay_referrer_and_update_mission

logger = logging.getLogger(__name__)

async def add_payment_and_check_mission(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    user_id = job.user_id
    referrer_id = job.data["referrer_id"]
    
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Check if referred user has blocked the bot
    try:
        await context.bot.get_chat_member(chat_id=user_id, user_id=user_id)
    except Exception as e:
        if "bot was blocked by the user" in str(e):
             logger.warning(f"Skipping payment for {referrer_id} as referred user {user_id} blocked the bot.")
             return
    except TelegramError: # Catch other Telegram errors
        pass
        
    referral_doc_updated = REFERRALS_COLLECTION.find_one_and_update(
        {"referred_user_id": user_id, "referrer_id": referrer_id},
        [
            {
                "$set": {
                    "daily_earning_count": {
                        "$cond": [
                            {"$or": [
                                {"$lt": ["$last_earning_date", today_start]},
                                {"$eq": ["$last_earning_date", None]}
                            ]},
                            1,
                            {"$cond": [
                                {"$lt": ["$daily_earning_count", 3]},
                                {"$add": ["$daily_earning_count", 1]},
                                "$daily_earning_count"
                            ]}
                        ]
                    },
                    "last_earning_date": datetime.now()
                }
            }
        ],
        return_document=True
    )

    if referral_doc_updated:
        new_count = referral_doc_updated.get("daily_earning_count", 0)
        
        if new_count > 0 and new_count <= 3:
             await pay_referrer_and_update_mission(context, user_id, referrer_id, count=new_count)
        else:
            logger.info(f"Daily earning limit (3/3) reached for {referrer_id} from {user_id}. No payment.")
    else:
        logger.error(f"Referral document not found for user {user_id} and referrer {referrer_id}.")


async def send_random_alerts_task(context: ContextTypes.DEFAULT_TYPE):
    user_ids_cursor = USERS_COLLECTION.find({}, {"user_id": 1})
    all_user_ids = [user["user_id"] for user in user_ids_cursor]

    if not all_user_ids:
        logger.info("No users to send random alerts to.")
        return

    random_user_id = random.choice(all_user_ids)
    user_data = USERS_COLLECTION.find_one({"user_id": random_user_id})
    if not user_data:
        return

    lang = user_data.get("lang", "en")
    
    alert_types = ["daily_bonus", "mission", "refer", "spin"]
    chosen_alert = random.choice(alert_types)
    
    max_rate = TIERS[4]["rate"]
    
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    if chosen_alert == "daily_bonus":
        message = MESSAGES[lang]["alert_daily_bonus"]
        keyboard = [[InlineKeyboardButton("🎁 Claim Bonus / Go to Panel", callback_data="show_earning_panel")]]
    elif chosen_alert == "mission":
        message = MESSAGES[lang]["alert_mission"]
        keyboard = [[InlineKeyboardButton("🎯 See Missions / Go to Panel", callback_data="show_earning_panel")]]
    elif chosen_alert == "refer":
        message = MESSAGES[lang]["alert_refer"].format(max_rate=max_rate)
        keyboard = [[InlineKeyboardButton("🔗 Share Referral Link", callback_data="show_refer_link")]]
    elif chosen_alert == "spin":
        message = MESSAGES[lang]["alert_spin"]
        keyboard = [[InlineKeyboardButton("🎰 Spin Now / Get Spins", callback_data="show_spin_panel")]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await context.bot.send_message(
            chat_id=random_user_id,
            text=message,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        logger.info(f"Sent random alert '{chosen_alert}' to user {random_user_id}.")
    except TelegramError as e:
        if "bot was blocked by the user" in str(e):
            USERS_COLLECTION.update_one({"user_id": random_user_id}, {"$set": {"is_approved": False}}) # Optional: Mark as blocked
            logger.warning(f"User {random_user_id} blocked the bot. Skipping alert.")
        else:
            logger.error(f"Failed to send random alert to user {random_user_id}: {e}")
