# task.py

import logging
from telegram.ext import ContextTypes
from datetime import datetime, timedelta 
import asyncio
import random
from telegram.error import TelegramError

from config import (
    USERS_COLLECTION, REFERRALS_COLLECTION, DOLLAR_TO_INR, DAILY_MISSIONS, 
    MESSAGES, TIERS, ADMIN_ID, LEADERBOARD_CONFIG
)
from db_utils import pay_referrer_and_update_mission, send_log_message

logger = logging.getLogger(__name__)

async def add_payment_and_check_mission(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    user_id = job.user_id
    referrer_id = job.data.get("referrer_id")
    
    if not referrer_id:
        logger.error(f"Job data missing referrer_id for user {user_id}.")
        return

    success, amount = await pay_referrer_and_update_mission(context, user_id, referrer_id)
    
    if success:
        logger.info(f"Payment job completed for user {user_id} (referrer {referrer_id}). Amount: ₹{amount:.2f}")
    else:
        logger.info(f"Payment job finished for user {user_id}, but payment was skipped.")
        

async def send_random_alerts_task(context: ContextTypes.DEFAULT_TYPE):
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
            if alert_type == "refer":
                message = message.format(max_rate=TIERS[4]["rate"])
                
            try:
                await context.bot.send_message(chat_id=user_id, text=message, parse_mode='HTML')
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.debug(f"Failed to send alert to user {user_id}: {e}")

async def send_fake_withdrawal_alert(context: ContextTypes.DEFAULT_TYPE):
    try:
        winner_cursor = USERS_COLLECTION.aggregate([
            {"$sample": {"size": 1}},
            {"$project": {"full_name": 1}}
        ])
        winner_list = list(winner_cursor)
        if not winner_list:
            logger.warning("FakeWithdrawal: No users found to feature.")
            return

        winner_name = winner_list[0].get("full_name", "Ek User")
        if ' ' in winner_name:
            winner_name = winner_name.split(' ')[0]
        
        amounts = [80, 100, 120, 150, 200, 250, 300, 400, 500, 600, 750, 1000]
        random_amount = random.choice(amounts)

        message_hi = (
            f"🤑 <b>Bada Payment!</b>\n\n"
            f"Hamare user '<b>{winner_name}</b>' ne abhi-abhi bot se <b>₹{random_amount:.2f}</b> ka withdrawal kiya hai!\n\n"
            f"Aap bhi kama sakte hain, 'Earning Panel' check karein!"
        )
        message_en = (
            f"🤑 <b>Big Payment!</b>\n\n"
            f"Our user '<b>{winner_name}</b>' just withdrew <b>₹{random_amount:.2f}</b> from the bot!\n\n"
            f"You can earn too, check the 'Earning Panel'!"
        )

        recipients_cursor = USERS_COLLECTION.aggregate([
            {"$sample": {"size": 20}},
            {"$project": {"user_id": 1, "lang": 1}}
        ])

        for user in recipients_cursor:
            user_id = user["user_id"]
            lang = user.get("lang", "en")
            
            message = message_en if lang == "en" else message_hi

            try:
                await context.bot.send_message(chat_id=user_id, text=message, parse_mode='HTML')
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.debug(f"FakeWithdrawal: Failed to send to {user_id}: {e}")
        
        logger.info(f"Fake withdrawal alert (User: {winner_name}, Amount: {random_amount}) sent to 20 users.")

    except Exception as e:
        logger.error(f"Error in send_fake_withdrawal_alert: {e}")

async def process_monthly_leaderboard(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    if now.day != 1 or now.hour < 5:
        logger.info(f"Skipping monthly leaderboard: Not the 1st of the month (Day: {now.day}, Hour: {now.hour}).")
        return
        
    last_run = context.bot_data.get("last_leaderboard_run", None)
    if last_run and (now - last_run) < timedelta(days=1):
         logger.info("Monthly leaderboard logic already ran today. Skipping.")
         return
         
    context.bot_data["last_leaderboard_run"] = now
    logger.info("--- STARTING MONTHLY LEADERBOARD PROCESSING ---")

    from config import LEADERBOARD_CONFIG, DOLLAR_TO_INR
    
    top_users_cursor = USERS_COLLECTION.find(
        {"monthly_referrals": {"$gt": 0}}
    ).sort("monthly_referrals", -1).limit(10)
    
    top_users = list(top_users_cursor)
    
    if not top_users:
        await send_log_message(context, "🏆 <b>Monthly Leaderboard:</b> No users had any monthly referrals. No rewards given.")
        return

    reward_log = ["🏆 Monthly Leaderboard Rewards Log 🏆"]
    
    # Process rewards with NEW Logic
    for i, user_data in enumerate(top_users):
        rank = i + 1
        user_id = user_data["user_id"]
        lang = user_data.get("lang", "en")
        monthly_refs = user_data.get("monthly_referrals", 0)
        
        tier_data = LEADERBOARD_CONFIG.get(rank)
        
        if not tier_data:
            continue
            
        reward_inr = tier_data["reward"]
        min_refs_needed = tier_data["min_refs"]
        
        # Condition Check: Kya user ne minimum referrals kiye hain?
        if monthly_refs >= min_refs_needed:
            reward_usd = reward_inr / DOLLAR_TO_INR
            
            result = USERS_COLLECTION.find_one_and_update(
                {"user_id": user_id},
                {"$inc": {"earnings": reward_usd}},
                return_document=True
            )
            
            if result:
                new_balance_inr = result.get("earnings", 0.0) * DOLLAR_TO_INR
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=MESSAGES[lang]["monthly_reward_notification"].format(
                            rank=rank,
                            reward=reward_inr,
                            new_balance=new_balance_inr
                        ),
                        parse_mode='HTML'
                    )
                    reward_log.append(f"✅ Rank #{rank}: <code>{user_id}</code> ({monthly_refs} refs) WON ₹{reward_inr:.2f}.")
                except Exception as e:
                    logger.error(f"Failed to notify user {user_id} about reward: {e}")
                    reward_log.append(f"⚠️ Rank #{rank}: <code>{user_id}</code> ({monthly_refs} refs) WON ₹{reward_inr:.2f}. NOTIFICATION FAILED.")
        else:
            reward_log.append(f"❌ Rank #{rank}: <code>{user_id}</code> ({monthly_refs} refs) FAILED. (Needs {min_refs_needed} refs)")

    reset_result = USERS_COLLECTION.update_many(
        {"monthly_referrals": {"$gt": 0}},
        {"$set": {"monthly_referrals": 0}}
    )
    
    reward_log.append(f"\n✅ **Referrals Reset!** {reset_result.modified_count} users' monthly referrals have been reset to 0.")
    
    await send_log_message(context, "\n".join(reward_log))
    logger.info("--- COMPLETED MONTHLY LEADERBOARD PROCESSING ---")
