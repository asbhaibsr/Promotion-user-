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
    """
    Scheduled job to process payment and mission check for a referred user's search.
    This runs after a 5-minute delay from handle_group_messages.
    """
    job = context.job
    user_id = job.user_id # Referred user ID
    referrer_id = job.data.get("referrer_id")
    
    if not referrer_id:
        logger.error(f"Job data missing referrer_id for user {user_id}.")
        return

    # Call the core payment logic, which also handles:
    # 1. Checking if already paid today (once-per-day rule for that referrer-referred pair).
    # 2. Updating referrer's earnings.
    # 3. Notifying referrer and referred user (confirmation).
    # 4. Checking and updating the referrer's 'search_3_movies' mission progress.
    success, amount = await pay_referrer_and_update_mission(context, user_id, referrer_id)
    
    if success:
        logger.info(f"Payment job completed for user {user_id} (referrer {referrer_id}). Amount: ₹{amount:.2f}")
    else:
        logger.info(f"Payment job finished for user {user_id}, but payment was skipped (already paid today or an error occurred).")
        

async def send_random_alerts_task(context: ContextTypes.DEFAULT_TYPE):
    """Sends random alerts to a subset of users every few hours."""
    # This is placeholder logic, but ensures the job is not empty.
    
    # Example alert logic:
    # 1. Select a random user (or users)
    user_cursor = USERS_COLLECTION.aggregate([{"$sample": {"size": 50}}])
    
    for user_data in user_cursor:
        user_id = user_data["user_id"]
        lang = user_data.get("lang", "en")
        
        alert_type = random.choice(["daily_bonus", "mission", "refer", "spin"])
        
        message_key = ""
        if alert_type == "daily_bonus":
            message_key = "alert_daily_bonus"
        elif alert_type == "mission":
            message_key = "alert_mission"
        elif alert_type == "refer":
            message_key = "alert_refer"
        elif alert_type == "spin":
            message_key = "alert_spin"
            
        message = MESSAGES[lang].get(message_key)
        
        if message:
            # Add dynamic data for 'refer' alert
            if alert_type == "refer":
                message = message.format(max_rate=TIERS[4]["rate"])
                
            try:
                await context.bot.send_message(chat_id=user_id, text=message, parse_mode='HTML')
                await asyncio.sleep(0.05) # Throttle to avoid rate limits
            except Exception as e:
                logger.debug(f"Failed to send alert to user {user_id}: {e}")

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
    last_month_end = now.replace(day=1) - timedelta(days=1) # यह ठीक है
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
                    
                    # --- language_prompt FIX ---
                    # MESSAGES डिक्शनरी से वैल्यू न मिलने पर एक डिफ़ॉल्ट स्ट्रिंग प्रदान की गई है।
                    message_text = MESSAGES.get(lang, {}).get("monthly_reward_success", 
                            f"🎉 <b>Monthly Reward!</b>\n\nCongratulations, you ranked #{i+1} and received **₹{reward_inr:.2f}** for your referrals last month! Your new balance is ₹{new_balance_inr:.2f}."
                        )

                    await context.bot.send_message(
                        chat_id=user_id,
                        text=message_text, # संदेश के लिए ठीक किए गए टेक्स्ट का उपयोग
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user {user_id} about monthly reward: {e}")

                reward_log.append(f"#{i+1}: <code>{user_id}</code> ({username_display}) received **₹{reward_inr:.2f}**.")
            else:
                reward_log.append(f"#{i+1}: <code>{user_id}</code> - Update failed.")
                
    await send_log_message(context, "\n".join(reward_log))
    logger.info("Monthly top user rewards task completed.")
