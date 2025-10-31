# db_utils.py

from telegram.ext import ContextTypes
import logging
from datetime import datetime, timedelta
from telegram.error import TelegramError, TimedOut, Forbidden

from config import (
    LOG_CHANNEL_ID, USERS_COLLECTION, SETTINGS_COLLECTION, TIERS, 
    DOLLAR_TO_INR, DAILY_BONUS_BASE, DAILY_BONUS_STREAK_MULTIPLIER, 
    MESSAGES, ADMIN_ID, DAILY_MISSIONS, REFERRALS_COLLECTION
)

logger = logging.getLogger(__name__)

async def send_log_message(context: ContextTypes.DEFAULT_TYPE, message: str):
    if LOG_CHANNEL_ID:
        try:
            await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=message, parse_mode='HTML', disable_web_page_preview=True)
        except Exception as e:
            logger.error(f"Failed to send log to channel {LOG_CHANNEL_ID}: {e}")

async def get_user_lang(user_id):
    user_data = USERS_COLLECTION.find_one({"user_id": user_id})
    return user_data.get("lang", "en") if user_data else "en"

async def set_user_lang(user_id, lang):
    USERS_COLLECTION.update_one(
        {"user_id": user_id},
        {"$set": {"lang": lang}},
        upsert=True
    )

async def get_referral_bonus_inr():
    settings = SETTINGS_COLLECTION.find_one({"_id": "referral_rate"})
    return settings.get("rate_inr", TIERS[1]["rate"]) if settings else TIERS[1]["rate"]

async def get_welcome_bonus():
    settings = SETTINGS_COLLECTION.find_one({"_id": "welcome_bonus"})
    return settings.get("amount_inr", 5.00) if settings else 5.00

async def get_user_tier(user_id):
    user_data = USERS_COLLECTION.find_one({"user_id": user_id})
    if not user_data:
        return 1
    
    earnings_usd = user_data.get("earnings", 0.0) 
    earnings_inr = earnings_usd * DOLLAR_TO_INR
    
    for tier, info in sorted(TIERS.items(), reverse=True):
        if earnings_inr >= info["min_earnings"]:
            return tier
    return 1

async def get_tier_referral_rate(tier):
    return TIERS.get(tier, TIERS[1])["rate"] 

async def update_daily_searches_and_mission(user_id):
    today = datetime.now().date()
    
    # Atomically update daily searches.
    # The crucial change: Check if last_search_date is TODAY. If not, reset it to 1. 
    # If it is today, just increment. This is for the referred user's *own* mission progress (if any is implemented).
    # Since the user wants self-searches to *not* count, we limit it to 1 max per day.
    
    result = USERS_COLLECTION.find_one_and_update(
        {"user_id": user_id},
        [
            {
                "$set": {
                    "daily_searches": {
                        "$cond": [
                            # Check if last_search_date is NOT today
                            {"$ne": [{"$dateToString": {"format": "%Y-%m-%d", "date": "$last_search_date"}}, {"$dateToString": {"format": "%Y-%m-%d", "date": datetime.now()}}]},
                            1, # Reset to 1 if it's a new day
                            {"$min": [3, {"$add": ["$daily_searches", 1]}]} # Max 3, and increment if it's the same day
                        ]
                    },
                    "last_search_date": datetime.now(),
                    # Also reset 'search_3_movies' mission if the day changed
                    "missions_completed.search_3_movies": {
                        "$cond": [
                             {"$ne": [{"$dateToString": {"format": "%Y-%m-%d", "date": "$last_search_date"}}, {"$dateToString": {"format": "%Y-%m-%d", "date": datetime.now()}}]},
                            False,
                            "$missions_completed.search_3_movies"
                        ]
                    }
                }
            }
        ],
        return_document=True
    )
    return result

async def claim_and_update_daily_bonus(user_id):
    today = datetime.now().date()
    user_data = USERS_COLLECTION.find_one({"user_id": user_id})
    if not user_data:
        return 0.0, 0.0, None, True

    last_checkin = user_data.get("last_checkin_date")
    if last_checkin and isinstance(last_checkin, datetime) and last_checkin.date() == today:
        return 0.0, 0.0, None, True # Already claimed

    streak = user_data.get("daily_bonus_streak", 0)
    
    if last_checkin and isinstance(last_checkin, datetime) and (today - last_checkin.date()).days == 1:
        streak += 1
    else:
        streak = 1

    bonus_amount_inr = DAILY_BONUS_BASE + (streak * DAILY_BONUS_STREAK_MULTIPLIER)
    bonus_amount_usd = bonus_amount_inr / DOLLAR_TO_INR
    
    updated_data = USERS_COLLECTION.find_one_and_update(
        {"user_id": user_id},
        {
            "$inc": {"earnings": bonus_amount_usd},
            "$set": {
                "last_checkin_date": datetime.now(),
                "daily_bonus_streak": streak,
                f"missions_completed.claim_daily_bonus": True 
            }
        },
        return_document=True
    )
    
    if updated_data:
        new_balance = updated_data.get("earnings", 0.0) * DOLLAR_TO_INR
        return bonus_amount_inr, new_balance, streak, False
    return None, None, None, None

async def pay_referrer_and_update_mission(context: ContextTypes.DEFAULT_TYPE, user_id: int, referrer_id: int):
    # This function is now simplified to only handle the single payment for the day.
    today = datetime.now().date()
    
    # 1. Check and Update Referral Record (Atomically)
    # Check if this user has already triggered a PAID search today.
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # --- FIX 1: Find the referral record ---
    referral_check = REFERRALS_COLLECTION.find_one({
        "referrer_id": referrer_id,
        "referred_user_id": user_id
    })

    if not referral_check:
        logger.error(f"Referral record not found for user {user_id} and referrer {referrer_id}")
        return False, 0
    
    last_paid_date = referral_check.get("last_paid_date")
    
    if last_paid_date and isinstance(last_paid_date, datetime) and last_paid_date.date() == today:
        logger.warning(f"Payment for {user_id} to {referrer_id} already processed today. Skipping.")
        return False, 0 # Already paid today

    # Atomically update the referral record for payment
    result = REFERRALS_COLLECTION.find_one_and_update(
        {
            "referrer_id": referrer_id,
            "referred_user_id": user_id,
            # CRITICAL FIX: Ensure we only update if not paid today
            "$or": [
                {"last_paid_date": None},
                {"last_paid_date": {"$lt": today_start}} # Check if not paid today
            ]
        },
        {
            # **CRITICAL FIX: Ensure last_paid_date is updated here to mark the payment for today**
            "$set": {
                "last_paid_date": datetime.now(), 
                "paid_search_count_today": 1 # Setting it to 1 to simplify logic for mission check if needed
            }
        },
        return_document=True
    )
    
    if not result:
        # This means the payment was processed by another job or just missed the race condition
        logger.warning(f"Payment update failed for user {user_id} to referrer {referrer_id}. Already processed?")
        return False, 0
    
    # 2. Process Payment and Messages
    referrer_tier = await get_user_tier(referrer_id)
    tier_rate = await get_tier_referral_rate(referrer_tier)
    earning_rate_usd = tier_rate / DOLLAR_TO_INR
    
    USERS_COLLECTION.update_one(
        {"user_id": referrer_id},
        {"$inc": {"earnings": earning_rate_usd}}
    )
    
    updated_referrer_data = USERS_COLLECTION.find_one({"user_id": referrer_id})
    new_balance_inr = updated_referrer_data.get("earnings", 0.0) * DOLLAR_TO_INR
    
    # Fetch referred user's data to send notification to referrer
    user_data = USERS_COLLECTION.find_one({"user_id": user_id})
    # If user_data is None (highly unlikely here), use fallback
    user_full_name = user_data.get("full_name", f"User {user_id}") if user_data else f"User {user_id}"
    
    # Notify Referrer (Only in private chat with the bot)
    referrer_lang = await get_user_lang(referrer_id)
    try:
        # **CRITICAL FIX: Sending message to referrer_id (private chat)**
        # This addresses the user's issue: "ये message उस user को जाये जिसने उस user को अपनी link से बायला था"
        await context.bot.send_message(
            chat_id=referrer_id, # Private chat ID
            text=MESSAGES[referrer_lang]["daily_earning_update_new"].format( # Using new key
                amount=tier_rate,
                full_name=user_full_name, # Referred user's name
                new_balance=new_balance_inr
            ),
            parse_mode='HTML'
        )
    except Forbidden:
        logger.warning(f"Referrer {referrer_id} blocked the bot. Cannot send earning update.")
    except (TelegramError, TimedOut) as e:
        logger.error(f"Could not send daily earning update to referrer {referrer_id}: {e}")
        
    
    referrer_username = f"@{updated_referrer_data.get('username')}" if updated_referrer_data and updated_referrer_data.get('username') else f"<code>{referrer_id}</code>"
    user_username = f"@{user_data.get('username')}" if user_data and user_data.get('username') else f"<code>{user_id}</code>"
    log_msg = (
        f"💸 <b>Referral Earning</b> (Daily Payment)\n"
        f"Referrer: {referrer_username}\n"
        f"From User: {user_username}\n"
        f"Amount: ₹{tier_rate:.2f}\n"
        f"New Balance: ₹{new_balance_inr:.2f}"
    )
    await send_log_message(context, log_msg)
    
    logger.info(f"Daily payment processed for {referrer_id} from {user_id}.")
    
    # 3. Check Mission Completion for Referrer (search_3_movies)
    # The mission is completed if the referrer has successfully received 3 such daily payments
    
    mission_key = "search_3_movies"
    mission = DAILY_MISSIONS[mission_key]
    referrer_data = USERS_COLLECTION.find_one({"user_id": referrer_id})
    
    # Count total paid searches today from ALL referred users
    paid_searches_today_count = 0
    # FIX: Use find with correct date query for robustness
    paid_searches_today_count = REFERRALS_COLLECTION.count_documents({
        "referrer_id": referrer_id, 
        "last_paid_date": {"$gte": today_start} # Count only payments made today
    })
             
    # Only award mission if they are at the target count AND haven't completed the mission today
    if paid_searches_today_count >= mission["target"] and not referrer_data.get("missions_completed", {}).get(mission_key):
        reward_usd = mission["reward"] / DOLLAR_TO_INR
        
        updated_referrer_result = USERS_COLLECTION.find_one_and_update(
            {"user_id": referrer_id, f"missions_completed.{mission_key}": False},
            {
                "$inc": {"earnings": reward_usd},
                "$set": {f"missions_completed.{mission_key}": True}
            },
            return_document=True
        )
        
        if updated_referrer_result:
            try:
                referrer_lang = updated_referrer_result.get("lang", "en")
                updated_earnings_inr = updated_referrer_result.get("earnings", 0.0) * DOLLAR_TO_INR
                mission_name = mission["name"] if referrer_lang == "en" else mission["name_hi"]
                
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text=MESSAGES[referrer_lang]["mission_complete"].format(
                        mission_name=mission_name,
                        reward=mission["reward"],
                        new_balance=updated_earnings_inr
                    ),
                    parse_mode='HTML'
                )
                logger.info(f"Referrer {referrer_id} completed search_3_movies mission.")
            except Exception as e:
                logger.error(f"Could not notify referrer {referrer_id} about search mission completion: {e}")
                
    return True, tier_rate

async def get_bot_stats():
    """Fetches total users and approved users for admin panel."""
    total_users = USERS_COLLECTION.count_documents({})
    approved_users = USERS_COLLECTION.count_documents({"is_approved": True})
    
    return {
        "total_users": total_users,
        "approved_users": approved_users
    }
