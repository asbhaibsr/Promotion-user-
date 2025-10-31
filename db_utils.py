from telegram.ext import ContextTypes
import logging
from datetime import datetime, timedelta
from telegram.error import TelegramError, TimedOut

from config import (
    LOG_CHANNEL_ID, USERS_COLLECTION, SETTINGS_COLLECTION, TIERS, 
    DOLLAR_TO_INR, DAILY_BONUS_BASE, DAILY_BONUS_STREAK_MULTIPLIER, 
    MESSAGES, ADMIN_ID, DAILY_MISSIONS, WITHDRAWALS_COLLECTION
)

logger = logging.getLogger(__name__)

async def send_log_message(context: ContextTypes.DEFAULT_TYPE, message: str):
    if LOG_CHANNEL_ID:
        try:
            # FIX: Convert LOG_CHANNEL_ID to int if it's stored as a string
            chat_id = int(LOG_CHANNEL_ID) 
            await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML', disable_web_page_preview=True)
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
    # This fetches the base rate from config.py TIERS dict, which is dynamic
    return TIERS.get(tier, TIERS[1])["rate"] 

async def update_daily_searches_and_mission(user_id):
    """
    Updates the user's *self* daily search count and resets mission flags if date changed.
    NOTE: The referral earning count is updated in the task itself.
    """
    today = datetime.now().date()
    
    # 1. Reset check for the user's *self* search mission
    # This is mainly for mission display and does *not* affect referral earning
    
    # Atomically reset daily_searches and search_3_movies mission if the date has changed
    update_result = USERS_COLLECTION.find_one_and_update(
        {"user_id": user_id},
        [
            {
                "$set": {
                    # Reset daily_searches if last_search_date is not today
                    "daily_searches": {
                        "$cond": [
                            {"$ne": [{"$dateToString": {"format": "%Y-%m-%d", "date": "$last_search_date"}}, {"$dateToString": {"format": "%Y-%m-%d", "date": datetime.now()}}]},
                            1, # Set to 1 if new day
                            {"$add": ["$daily_searches", 1]} # Increment if same day
                        ]
                    },
                    "last_search_date": datetime.now(),
                    # Reset mission status if new day
                    "missions_completed.search_3_movies": {
                         "$cond": [
                            {"$ne": [{"$dateToString": {"format": "%Y-%m-%d", "date": "$last_search_date"}}, {"$dateToString": {"format": "%Y-%m-%d", "date": datetime.now()}}]},
                            False, 
                            "$missions_completed.search_3_movies"
                        ]
                    },
                     "last_referrer_earning_date": {
                         "$cond": [
                            {"$ne": [{"$dateToString": {"format": "%Y-%m-%d", "date": "$last_referrer_earning_date"}}, {"$dateToString": {"format": "%Y-%m-%d", "date": datetime.now()}}]},
                            datetime.now().replace(hour=0, minute=0, second=0, microsecond=0), # Reset to start of day
                            "$last_referrer_earning_date"
                        ]
                    },
                     "referrer_daily_earning_count": {
                         "$cond": [
                            {"$ne": [{"$dateToString": {"format": "%Y-%m-%d", "date": "$last_referrer_earning_date"}}, {"$dateToString": {"format": "%Y-%m-%d", "date": datetime.now()}}]},
                            0, 
                            "$referrer_daily_earning_count"
                        ]
                    }
                }
            }
        ],
        return_document=True
    )
    return update_result


async def claim_and_update_daily_bonus(user_id):
    today = datetime.now().date()
    user_data = USERS_COLLECTION.find_one({"user_id": user_id})
    if not user_data:
        return None, None, None, None

    last_checkin = user_data.get("last_checkin_date")
    if last_checkin and isinstance(last_checkin, datetime) and last_checkin.date() == today:
        return 0.0, user_data.get("earnings", 0.0) * DOLLAR_TO_INR, user_data.get("daily_bonus_streak", 0), True # Already claimed

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


async def pay_referrer_and_update_mission(context: ContextTypes.DEFAULT_TYPE, user_id: int, referrer_id: int, count: int):
    """
    The main logic to pay the referrer and update the referred user's daily count 
    and the referrer's mission status.
    This runs after the 5-minute delay.
    """

    # 1. Update the referred user's search count (atomically)
    # Only increment if the payment count is one more than the current count (ensures no double payment from race conditions)
    referred_user_update = USERS_COLLECTION.find_one_and_update(
        {"user_id": user_id, "referrer_daily_earning_count": count - 1},
        {"$set": {
            "referrer_daily_earning_count": count,
            "last_referrer_earning_date": datetime.now() # Update date on successful earning
        }},
        return_document=True
    )
    
    if not referred_user_update:
        # This means the payment was already processed or the count is wrong (race condition or duplicate job)
        logger.warning(f"Payment skipped for {user_id} (referrer {referrer_id}). Count mismatch or already processed.")
        # FIX: Send a log message for this scenario
        await send_log_message(context, f"⚠️ <b>Referral Payment Skipped:</b>\nUser: <code>{user_id}</code> (Referrer: <code>{referrer_id}</code>).\nReason: Count mismatch or already paid for search #{count}.")
        return


    # 2. Calculate and pay the referrer
    referrer_tier = await get_user_tier(referrer_id)
    tier_rate = await get_tier_referral_rate(referrer_tier)
    earning_rate_usd = tier_rate / DOLLAR_TO_INR
    
    USERS_COLLECTION.update_one(
        {"user_id": referrer_id},
        {"$inc": {"earnings": earning_rate_usd}}
    )
    
    updated_referrer_data = USERS_COLLECTION.find_one({"user_id": referrer_id})
    new_balance_inr = updated_referrer_data.get("earnings", 0.0) * DOLLAR_TO_INR
    
    user_data = USERS_COLLECTION.find_one({"user_id": user_id})
    user_full_name = user_data.get("full_name", f"User {user_id}")
    
    # 3. Notify referrer and log
    referrer_lang = updated_referrer_data.get("lang", "en")
    try:
        # FIX: Added a message about shortlink completion
        await context.bot.send_message(
            chat_id=referrer_id,
            text=MESSAGES[referrer_lang]["daily_earning_update"].format(
                count=count,
                amount=tier_rate,
                full_name=user_full_name, 
                new_balance=new_balance_inr,
                # FIX: Added required format args
                delay_minutes=5,
                user_name_or_id=f"<code>{user_id}</code>" 
            ),
            parse_mode='HTML'
        )
    except (TelegramError, TimedOut) as e:
        logger.error(f"Could not send daily earning update to referrer {referrer_id}: {e}")
    
    referrer_username = f"@{updated_referrer_data.get('username')}" if updated_referrer_data.get('username') else f"<code>{referrer_id}</code>"
    user_username = f"@{user_data.get('username')}" if user_data.get('username') else f"<code>{user_id}</code>"
    log_msg = (
        f"💸 <b>Referral Earning!</b> ({count}/3)\n"
        f"Referrer: {referrer_username}\n"
        f"From User: {user_username}\n"
        f"Amount: ₹{tier_rate:.2f}\n"
        f"New Balance: ₹{new_balance_inr:.2f}"
    )
    await send_log_message(context, log_msg)
    
    logger.info(f"Payment {count}/3 processed for {referrer_id} from {user_id}")
    
    # 4. Check referrer mission completion for search_3_movies
    mission_key = "search_3_movies"
    mission = DAILY_MISSIONS[mission_key]
    referrer_data = USERS_COLLECTION.find_one({"user_id": referrer_id})

    if count >= mission["target"] and not referrer_data.get("missions_completed", {}).get(mission_key):
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
                # Re-fetch lang and balance after update
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


async def get_bot_stats():
    """Fetches key statistics for the admin panel."""
    
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Total Users
    total_users = USERS_COLLECTION.count_documents({})
    
    # Active Users Today (Joined or searched today)
    active_users_today = USERS_COLLECTION.count_documents({
        "$or": [
            {"joined_date": {"$gte": today}},
            {"last_search_date": {"$gte": today}},
            {"last_checkin_date": {"$gte": today}}
        ]
    })
    
    # Total Earnings (sum of earnings field across all users)
    total_earnings_cursor = USERS_COLLECTION.aggregate([
        {"$group": {"_id": None, "total_usd": {"$sum": "$earnings"}}}
    ])
    total_earnings_usd = next(total_earnings_cursor, {"total_usd": 0})["total_usd"]
    total_earnings_inr = total_earnings_usd * DOLLAR_TO_INR
    
    # Total Referrals
    total_referrals = REFERRALS_COLLECTION.count_documents({})
    
    # Pending Withdrawals
    pending_withdrawals = WITHDRAWALS_COLLECTION.count_documents({"status": "pending"})
    
    return {
        "total_users": total_users,
        "active_users_today": active_users_today,
        "total_earnings": total_earnings_inr,
        "total_referrals": total_referrals,
        "pending_withdrawals": pending_withdrawals
    }
