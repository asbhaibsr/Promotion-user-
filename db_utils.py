# db_utils.py 

import logging
from datetime import datetime, timedelta
import random
from telegram.ext import ContextTypes

from config import (
    USERS_COLLECTION, REFERRALS_COLLECTION, SETTINGS_COLLECTION, WITHDRAWALS_COLLECTION,
    DOLLAR_TO_INR, DAILY_BONUS_BASE, DAILY_BONUS_STREAK_MULTIPLIER, 
    TIERS, DAILY_MISSIONS, SPIN_WHEEL_CONFIG, LOG_CHANNEL_ID, ADMIN_ID
)

logger = logging.getLogger(__name__)

# ================== HELPER FUNCTIONS ==================

async def send_log_message(context: ContextTypes.DEFAULT_TYPE, message: str) -> None:
    """Send log message to admin and log channel."""
    if LOG_CHANNEL_ID:
        try:
            await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=message, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Failed to send log to channel: {e}")
    if ADMIN_ID and ADMIN_ID != LOG_CHANNEL_ID:
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=message, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Failed to send log to admin: {e}")


async def get_user_lang(user_id: int) -> str:
    """Get user's language preference."""
    user = USERS_COLLECTION.find_one({"user_id": user_id}, {"lang": 1})
    return user.get("lang", "en") if user else "en"


async def set_user_lang(user_id: int, lang: str) -> None:
    """Set user's language preference."""
    USERS_COLLECTION.update_one({"user_id": user_id}, {"$set": {"lang": lang}})


async def get_referral_bonus_inr() -> float:
    """Get referral bonus amount in INR from settings."""
    setting = SETTINGS_COLLECTION.find_one({"_id": "referral_rate"})
    if setting and "rate_inr" in setting:
        return float(setting["rate_inr"])
    return TIERS[1]["rate"]


async def get_welcome_bonus() -> float:
    """Get welcome bonus amount in INR."""
    setting = SETTINGS_COLLECTION.find_one({"_id": "welcome_bonus"})
    if setting and "bonus_inr" in setting:
        return float(setting["bonus_inr"])
    return 5.00  # Default ₹5


async def get_user_tier(user_id: int) -> int:
    """Determine user's tier based on total earnings."""
    user = USERS_COLLECTION.find_one({"user_id": user_id})
    if not user:
        return 1
    
    earnings_usd = user.get("earnings", 0.0)
    earnings_inr = earnings_usd * DOLLAR_TO_INR
    
    tier = 1
    for t, config in sorted(TIERS.items(), key=lambda item: item[1]["min_earnings"], reverse=True):
        if earnings_inr >= config["min_earnings"]:
            tier = t
            break
    return tier


async def get_tier_referral_rate(user_id: int) -> float:
    """Get referral rate in INR for user based on their tier."""
    tier = await get_user_tier(user_id)
    return TIERS[tier]["rate"]


async def claim_and_update_daily_bonus(user_id: int):
    """Claim daily bonus and update streak. Returns (bonus_amount_inr, new_balance_inr, streak, already_claimed)."""
    user = USERS_COLLECTION.find_one({"user_id": user_id})
    if not user:
        return None, None, None, False

    last_checkin = user.get("last_checkin_date")
    today = datetime.now().date()
    streak = user.get("daily_bonus_streak", 0)
    earnings_usd = user.get("earnings", 0.0)

    if last_checkin and isinstance(last_checkin, datetime) and last_checkin.date() == today:
        return None, None, None, True

    if last_checkin and isinstance(last_checkin, datetime) and last_checkin.date() == (today - timedelta(days=1)):
        streak += 1
    else:
        streak = 1

    # Daily bonus = base + (streak * multiplier)
    bonus_usd = DAILY_BONUS_BASE + (streak * DAILY_BONUS_STREAK_MULTIPLIER)
    bonus_inr = bonus_usd * DOLLAR_TO_INR

    USERS_COLLECTION.update_one(
        {"user_id": user_id},
        {
            "$inc": {"earnings": bonus_usd},
            "$set": {"last_checkin_date": datetime.now(), "daily_bonus_streak": streak}
        }
    )

    updated_user = USERS_COLLECTION.find_one({"user_id": user_id})
    new_balance_usd = updated_user.get("earnings", 0.0)
    new_balance_inr = new_balance_usd * DOLLAR_TO_INR

    return bonus_inr, new_balance_inr, streak, False


async def update_daily_searches_and_mission(user_id: int) -> None:
    """Update daily search count for a user."""
    today = datetime.now().date()
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    user = USERS_COLLECTION.find_one({"user_id": user_id})
    
    last_search = user.get("last_search_date") if user else None
    
    if last_search and isinstance(last_search, datetime) and last_search.date() == today:
        USERS_COLLECTION.update_one(
            {"user_id": user_id},
            {"$inc": {"daily_searches": 1}}
        )
    else:
        USERS_COLLECTION.update_one(
            {"user_id": user_id},
            {"$set": {"daily_searches": 1, "last_search_date": datetime.now(), "missions_completed.search_3_movies": False}}
        )


async def pay_referrer_and_update_mission(context, referred_user_id: int, referrer_id: int):
    """Pay referrer for a search and update missions."""
    try:
        daily_amount_inr = await get_tier_referral_rate(referrer_id)
        daily_amount_usd = daily_amount_inr / DOLLAR_TO_INR
        
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        referral_doc = REFERRALS_COLLECTION.find_one_and_update(
            {"referrer_id": referrer_id, "referred_user_id": referred_user_id},
            {
                "$set": {"last_paid_date": datetime.now()},
                "$inc": {"paid_search_count_today": 1}
            },
            return_document=True
        )
        
        if not referral_doc:
            logger.error(f"Referral document not found for referrer {referrer_id}, referred {referred_user_id}")
            return False, 0.0
        
        # Update referrer's earnings
        result = USERS_COLLECTION.find_one_and_update(
            {"user_id": referrer_id},
            {"$inc": {"earnings": daily_amount_usd}},
            return_document=True
        )
        
        if not result:
            logger.error(f"Failed to update earnings for referrer {referrer_id}")
            return False, 0.0
        
        new_balance_usd = result.get("earnings", 0.0)
        new_balance_inr = new_balance_usd * DOLLAR_TO_INR
        
        # Send notification to referrer
        referred_user = USERS_COLLECTION.find_one({"user_id": referred_user_id})
        referred_name = referred_user.get("full_name", f"User {referred_user_id}") if referred_user else f"User {referred_user_id}"
        
        try:
            referrer_lang = await get_user_lang(referrer_id)
            msg = (
                f"💰 Daily Referral Earning!\n\n"
                f"You earned ₹{daily_amount_inr:.2f} from your referral {referred_name} for a paid search today.\n"
                f"New balance: ₹{new_balance_inr:.2f}"
            )
            await context.bot.send_message(chat_id=referrer_id, text=msg)
        except Exception as e:
            logger.error(f"Could not notify referrer {referrer_id}: {e}")
        
        # Check and update search mission for referrer
        paid_searches_today_count = 0
        referral_records = REFERRALS_COLLECTION.find({"referrer_id": referrer_id, "referred_user_id": {"$ne": referrer_id}})
        
        for record in referral_records:
            last_paid = record.get("last_paid_date")
            if last_paid and isinstance(last_paid, datetime) and last_paid.date() == today_start.date():
                paid_searches_today_count += 1
        
        referrer_data = USERS_COLLECTION.find_one({"user_id": referrer_id})
        missions_completed = referrer_data.get("missions_completed", {})
        
        if paid_searches_today_count >= DAILY_MISSIONS["search_3_movies"]["target"] and not missions_completed.get("search_3_movies"):
            reward_usd = DAILY_MISSIONS["search_3_movies"]["reward"] / DOLLAR_TO_INR
            USERS_COLLECTION.update_one(
                {"user_id": referrer_id},
                {
                    "$inc": {"earnings": reward_usd, "spins_left": 1},
                    "$set": {"missions_completed.search_3_movies": True}
                }
            )
            
            try:
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text=f"🎉 Mission Completed!\nYou earned ₹{DAILY_MISSIONS['search_3_movies']['reward']:.2f} +1 Spin for 'Search 3 Movies' mission!"
                )
            except Exception as e:
                logger.error(f"Could not notify referrer {referrer_id} about mission completion: {e}")
        
        return True, daily_amount_inr
        
    except Exception as e:
        logger.error(f"Error in pay_referrer_and_update_mission: {e}")
        return False, 0.0


async def get_bot_stats():
    """Get bot statistics."""
    total_users = USERS_COLLECTION.count_documents({})
    approved_users = USERS_COLLECTION.count_documents({"is_approved": True})
    
    return {
        "total_users": total_users,
        "approved_users": approved_users
    }


async def get_user_stats(user_id: int):
    """Get statistics for a specific user."""
    user = USERS_COLLECTION.find_one({"user_id": user_id})
    if not user:
        return None
    
    referrals = REFERRALS_COLLECTION.count_documents({"referrer_id": user_id, "referred_user_id": {"$ne": user_id}})
    
    earnings_inr = user.get("earnings", 0.0) * DOLLAR_TO_INR
    
    return {
        "user_id": user_id,
        "username": user.get("username", "N/A"),
        "full_name": user.get("full_name", f"User {user_id}"),
        "earnings_inr": earnings_inr,
        "referrals": referrals,
        "joined_date": user.get("joined_date"),
        "spins_left": user.get("spins_left", 0),
        "monthly_referrals": user.get("monthly_referrals", 0)
    }


async def admin_add_money(user_id: int, amount_inr: float):
    """Add money to user's balance."""
    amount_usd = amount_inr / DOLLAR_TO_INR
    result = USERS_COLLECTION.find_one_and_update(
        {"user_id": user_id},
        {"$inc": {"earnings": amount_usd}},
        return_document=True
    )
    
    if result:
        new_balance_usd = result.get("earnings", 0.0)
        new_balance_inr = new_balance_usd * DOLLAR_TO_INR
        return new_balance_inr
    return None


async def admin_clear_earnings(user_id: int):
    """Clear user's earnings."""
    USERS_COLLECTION.update_one(
        {"user_id": user_id},
        {"$set": {"earnings": 0.0}}
    )
    return True


async def admin_delete_user(user_id: int):
    """Delete all user data."""
    USERS_COLLECTION.delete_one({"user_id": user_id})
    REFERRALS_COLLECTION.delete_many({"referrer_id": user_id})
    REFERRALS_COLLECTION.delete_many({"referred_user_id": user_id})
    WITHDRAWALS_COLLECTION.delete_many({"user_id": user_id})
    return True


async def clear_junk_users():
    """Delete all users with is_approved=False."""
    junk_users = USERS_COLLECTION.find({"is_approved": False})
    users_deleted = 0
    referrals_deleted = 0
    withdrawals_deleted = 0
    
    for user in junk_users:
        user_id = user["user_id"]
        referrals_deleted += REFERRALS_COLLECTION.delete_many({"referrer_id": user_id}).deleted_count
        referrals_deleted += REFERRALS_COLLECTION.delete_many({"referred_user_id": user_id}).deleted_count
        withdrawals_deleted += WITHDRAWALS_COLLECTION.delete_many({"user_id": user_id}).deleted_count
        USERS_COLLECTION.delete_one({"user_id": user_id})
        users_deleted += 1
    
    return {
        "users": users_deleted,
        "referrals": referrals_deleted,
        "withdrawals": withdrawals_deleted
    }
