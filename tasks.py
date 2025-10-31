# tasks.py

import logging
from telegram.ext import ContextTypes
# यहाँ बदलाव किया गया है! (Change made here!)
from datetime import datetime, timedelta 
import asyncio
import random
from telegram.error import TelegramError

from config import (
    USERS_COLLECTION, REFERRALS_COLLECTION, DOLLAR_TO_INR, DAILY_MISSIONS, 
    MESSAGES, TIERS, ADMIN_ID
)
from db_utils import pay_referrer_and_update_mission, send_log_message

logger = logging.getLogger(__name__)

async def add_payment_and_check_mission(context: ContextTypes.DEFAULT_TYPE):
    # ... (remains the same)

async def send_random_alerts_task(context: ContextTypes.DEFAULT_TYPE):
    # ... (remains the same)


async def monthly_top_user_rewards(context: ContextTypes.DEFAULT_TYPE):
    """
    Checks on the 1st of every month to give rewards to the top 3 referrers
    who have referred at least 10 users.
    """
    now = datetime.now()
    if now.day != 1:
        logger.info("Skipping monthly reward task: Not the 1st of the month.")
        return

    # Calculate the range for "last month" to count referrals
    last_month_end = now.replace(day=1) - timedelta(days=1) # अब यह काम करेगा (This will work now)
    last_month_start = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 1. Find all users with >= 10 total referrals
    eligible_referrers = REFERRALS_COLLECTION.aggregate([
        {"$match": {"join_date": {"$lt": now}}}, # Only check existing referrals
        {"$group": {"_id": "$referrer_id", "total_referrals": {"$sum": 1}}},
        {"$match": {"total_referrals": {"$gte": 10}}}
    ])
    
    eligible_user_ids = [doc["_id"] for doc in eligible_referrers]

    if not eligible_user_ids:
        await send_log_message(context, "🏆 <b>Monthly Reward:</b> No users were eligible (>= 10 total referrals).")
        return

    # 2. Find the top 3 among eligible users based on total earnings
    # We use a simpler approach: rank them by total earnings, but only check the top 3.
    top_eligible_users_cursor = USERS_COLLECTION.find(
        {"user_id": {"$in": eligible_user_ids}}
    ).sort("earnings", -1).limit(3)
    
    top_users = list(top_eligible_users_cursor)
    
    rewards = {0: 90.0, 1: 60.0, 2: 30.0} # INR
    reward_log = ["🏆 **Monthly Top User Rewards** 🏆"]
    
    for i, user_data in enumerate(top_users):
        user_id = user_data["user_id"]
        reward_inr = rewards.get(i)
        
        if reward_inr is not None:
            reward_usd = reward_inr / DOLLAR_TO_INR
            
            # Auto-add reward to the user's account
            result = USERS_COLLECTION.update_one(
                {"user_id": user_id},
                {"$inc": {"earnings": reward_usd}}
            )
            
            if result.modified_count > 0:
                updated_user_data = USERS_COLLECTION.find_one({"user_id": user_id})
                new_balance_inr = updated_user_data.get("earnings", 0.0) * DOLLAR_TO_INR
                username_display = f"@{updated_user_data.get('username', f'User {user_id}')}"

                # Notify user
                try:
                    lang = updated_user_data.get("lang", "en")
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=MESSAGES[lang].get("monthly_reward_success", 
                            f"🎉 <b>Monthly Reward!</b>\n\nCongratulations, you ranked #{i+1} and received **₹{reward_inr:.2f}** for your referrals last month! Your new balance is ₹{new_balance_inr:.2f}."
                        ),
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user {user_id} about monthly reward: {e}")

                reward_log.append(f"#{i+1}: <code>{user_id}</code> ({username_display}) received **₹{reward_inr:.2f}**.")
            else:
                reward_log.append(f"#{i+1}: <code>{user_id}</code> - Update failed.")
                
    await send_log_message(context, "\n".join(reward_log))
    logger.info("Monthly top user rewards task completed.")
