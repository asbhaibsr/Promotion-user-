# handlers.py - Complete Bot Handlers with FIXED Earning System

import logging
import json
import random
import traceback
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from database import db
from utils import is_admin, format_balance, check_channel_membership

logger = logging.getLogger(__name__)

class BotHandlers:
    
    @staticmethod
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user = update.effective_user
            
            # Check for referral
            referrer = None
            if context.args and context.args[0].startswith("ref_"):
                try:
                    referrer = int(context.args[0].replace("ref_", ""))
                    logger.info(f"🔗 Referral: {referrer} -> {user.id}")
                except:
                    pass
            
            # Get user photo
            try:
                photos = await user.get_profile_photos(limit=1)
                photo_url = None
                if photos and photos.photos:
                    photo_url = photos.photos[0][-1].file_id
            except Exception as e:
                logger.error(f"Photo fetch error: {e}")
                photo_url = None
            
            # Create or get user
            db_user = db.get_user(user.id)
            if not db_user:
                db_user = db.create_user(user.id, user.username or "", user.first_name, photo_url, referrer)
                db.update_balance(user.id, Config.WELCOME_BONUS, "welcome", "Welcome Bonus")
                
                await update.message.reply_text(
                    f"🎉 *WELCOME BONUS!*\n"
                    f"You got ₹{Config.WELCOME_BONUS}!",
                    parse_mode='Markdown'
                )
            
            # Get user stats
            stats = db.get_user_stats(user.id)
            
            # Mini App Button
            keyboard = [[
                InlineKeyboardButton(
                    "🚀 OPEN MINI APP 🚀",
                    web_app={"url": f"{Config.WEB_APP_URL}/?user={user.id}"}
                )
            ]]
            
            if is_admin(user.id):
                keyboard.append([
                    InlineKeyboardButton("👑 ADMIN PANEL", callback_data="admin_panel")
                ])
            
            welcome_msg = (
                f"✨ *Hello {user.first_name}!* ✨\n\n"
                f"💰 *Balance:* {format_balance(stats['balance'])}\n"
                f"🎰 *Spins:* {stats['spins']}\n"
                f"👑 *Tier:* {stats['tier_name']}\n"
                f"👥 *Active Referrals:* {stats['active_refs']}\n\n"
                f"🎯 *Today's Missions*\n"
                f"• 3 Searches → ₹0.15 + 1 Spin\n"
                f"• 2 Referrals → ₹0.50 + 1 Spin\n"
                f"• Daily Bonus → ₹0.10 + 1 Spin\n\n"
                f"👇 *Open Mini App to Start Earning!*"
            )
            
            await update.message.reply_text(
                welcome_msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
            logger.info(f"✅ User {user.id} started bot")
            
        except Exception as e:
            logger.error(f"Start handler error: {e}")
            traceback.print_exc()
            await update.message.reply_text("❌ Technical Error. Please try again later.")
    
    @staticmethod
    async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not update.message or not update.message.chat:
                return
            
            chat = update.message.chat
            
            if chat.type not in ['group', 'supergroup']:
                await update.message.reply_text("❌ This command only works in groups!")
                return
            
            # Log group activity
            db.check_group_active(chat.id, chat.title)
            
            await update.message.reply_text(
                "✅ *I am active in this group!*\n\n"
                "Users can search movies here to activate referrals.",
                parse_mode='Markdown'
            )
            
            logger.info(f"✅ Check command used in group {chat.id}")
            
        except Exception as e:
            logger.error(f"Check command error: {e}")
    
    @staticmethod
    async def group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not update.message or not update.message.text:
                return
            
            user = update.effective_user
            if not user or user.is_bot:
                return
            
            # Track search in group
            if len(update.message.text) > 2:
                logger.info(f"📝 Search: {user.id} -> {update.message.text[:30]}...")
                
                # Activate referral if first search
                referrer = db.track_search(user.id)
                if referrer:
                    try:
                        await context.bot.send_message(
                            referrer,
                            f"🎉 *Referral Activated!*\n"
                            f"{user.first_name} did first search!\n"
                            f"✅ +1 Spin Added!",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Referrer notification failed: {e}")
                
                # Process daily payment
                amount = db.process_daily_referral_payment(user.id)
                if amount:
                    ref_doc = db.referrals.find_one({"user": user.id})
                    if ref_doc:
                        try:
                            await context.bot.send_message(
                                ref_doc["referrer"],
                                f"💰 *Daily Referral Earnings!*\n"
                                f"From {user.first_name}: {format_balance(amount)}",
                                parse_mode='Markdown'
                            )
                        except Exception as e:
                            logger.error(f"Payment notification failed: {e}")
                
                # Update mission
                db.update_mission(user.id, "daily_search")
                
        except Exception as e:
            logger.error(f"Group message error: {e}")
    
    @staticmethod
    async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle mini app data - COMPLETE FIXED VERSION"""
        try:
            if not update.effective_message or not update.effective_message.web_app_data:
                return
            
            data = update.effective_message.web_app_data.data
            logger.info(f"📱 WebApp Data: {data[:100]}...")
            
            try:
                payload = json.loads(data)
            except json.JSONDecodeError as e:
                logger.error(f"JSON Decode Error: {e}")
                await update.effective_message.reply_text(json.dumps({"error": "Invalid data format"}))
                return
            
            action = payload.get("action")
            user_id = payload.get("user_id")
            
            if not user_id:
                await update.effective_message.reply_text(json.dumps({"error": "User ID not found"}))
                return
            
            # Check if user exists
            user = db.get_user(user_id)
            if not user:
                # Create user automatically
                db.create_user(user_id, "", f"User_{user_id}", None, None)
            
            # ===== GET USER DATA =====
            if action == "get_data":
                try:
                    stats = db.get_user_stats(user_id)
                    if stats:
                        stats.update({
                            "movie_group": Config.MOVIE_GROUP_LINK,
                            "new_group": Config.NEW_MOVIE_GROUP_LINK,
                            "all_groups": Config.ALL_GROUPS_LINK,
                            "channel": Config.CHANNEL_USERNAME,
                            "channel_link": Config.CHANNEL_LINK,
                            "channel_bonus": Config.CHANNEL_BONUS,
                            "min_withdrawal": Config.MIN_WITHDRAWAL
                        })
                        await update.effective_message.reply_text(json.dumps(stats))
                        logger.info(f"📊 User {user_id} data fetched")
                    else:
                        await update.effective_message.reply_text(json.dumps({"error": "User not found"}))
                except Exception as e:
                    logger.error(f"Get data error: {e}")
                    await update.effective_message.reply_text(json.dumps({"error": str(e)}))
            
            # ===== SPIN WHEEL - FIXED =====
            elif action == "spin":
                try:
                    # ✅ FIX: Add small delay to prevent race conditions
                    await asyncio.sleep(0.1)
                    result = db.spin_wheel(user_id)
                    if result and "error" not in result:
                        logger.info(f"🎡 User {user_id} won: ₹{result.get('prize', 0)}")
                    await update.effective_message.reply_text(json.dumps(result))
                except Exception as e:
                    logger.error(f"Spin error: {e}")
                    await update.effective_message.reply_text(json.dumps({"error": "Spin failed"}))
            
            # ===== DAILY BONUS - FIXED =====
            elif action == "daily":
                try:
                    # ✅ FIX: Add small delay
                    await asyncio.sleep(0.1)
                    result = db.claim_daily(user_id)
                    if result:
                        logger.info(f"📅 User {user_id} claimed daily: ₹{result['bonus']}")
                        await update.effective_message.reply_text(json.dumps(result))
                    else:
                        await update.effective_message.reply_text(json.dumps({"error": "Already claimed today"}))
                except Exception as e:
                    logger.error(f"Daily bonus error: {e}")
                    await update.effective_message.reply_text(json.dumps({"error": "Failed to claim"}))
            
            # ===== SAVE PAYMENT =====
            elif action == "save_payment":
                try:
                    method = payload.get("method")
                    details = payload.get("details")
                    
                    db.update_user(user_id, {
                        "payment_method": method,
                        "payment_details": details
                    })
                    
                    await update.effective_message.reply_text(json.dumps({"success": True}))
                    logger.info(f"💳 User {user_id} saved payment details")
                except Exception as e:
                    logger.error(f"Save payment error: {e}")
                    await update.effective_message.reply_text(json.dumps({"error": str(e)}))
            
            # ===== WITHDRAW - FIXED =====
            elif action == "withdraw":
                try:
                    amount = float(payload.get("amount", 0))
                    method = payload.get("method")
                    details = payload.get("details")
                    
                    success, msg = db.create_withdrawal(user_id, amount, method, details)
                    
                    if success:
                        logger.info(f"💰 User {user_id} requested withdrawal: ₹{amount}")
                        
                        # Notify admins asynchronously
                        asyncio.create_task(notify_admins(context, user_id, amount, method, details))
                    
                    await update.effective_message.reply_text(json.dumps({"success": success, "message": msg}))
                    
                except Exception as e:
                    logger.error(f"Withdraw error: {e}")
                    await update.effective_message.reply_text(json.dumps({"success": False, "message": str(e)}))
            
            # ===== LEADERBOARD =====
            elif action == "leaderboard":
                try:
                    lb = db.get_current_leaderboard()
                    result = []
                    for idx, user_data in enumerate(lb, 1):
                        result.append({
                            "rank": idx,
                            "user_id": user_data.get("user_id"),
                            "name": user_data.get("full_name", "User")[:20],
                            "photo_url": user_data.get("photo_url"),
                            "refs": user_data.get("monthly_referrals", 0),
                            "balance": user_data.get("balance", 0),
                            "active_refs": user_data.get("active_referrals", 0)
                        })
                    await update.effective_message.reply_text(json.dumps(result))
                except Exception as e:
                    logger.error(f"Leaderboard error: {e}")
                    await update.effective_message.reply_text(json.dumps([]))
            
            # ===== CHANNEL JOIN - FIXED =====
            elif action == "channel_join":
                try:
                    # ✅ FIX: Add small delay
                    await asyncio.sleep(0.1)
                    joined = db.mark_channel_joined(user_id, Config.CHANNEL_USERNAME)
                    result = {
                        "success": joined,
                        "bonus": Config.CHANNEL_BONUS if joined else 0,
                        "message": f"You got ₹{Config.CHANNEL_BONUS} bonus!" if joined else "Already claimed"
                    }
                    await update.effective_message.reply_text(json.dumps(result))
                    
                    if joined:
                        logger.info(f"📢 User {user_id} joined channel, got ₹{Config.CHANNEL_BONUS}")
                        
                except Exception as e:
                    logger.error(f"Channel join error: {e}")
                    await update.effective_message.reply_text(json.dumps({"success": False, "error": str(e)}))
            
            # ===== MISSIONS - FIXED =====
            elif action == "missions":
                try:
                    # ✅ FIX: Add small delay
                    await asyncio.sleep(0.1)
                    missions = db.get_missions(user_id)
                    await update.effective_message.reply_text(json.dumps(missions))
                except Exception as e:
                    logger.error(f"Missions error: {e}")
                    await update.effective_message.reply_text(json.dumps({}))
            
            # ===== REPORT ISSUE =====
            elif action == "report_issue":
                try:
                    issue = payload.get("issue")
                    
                    # Save to database
                    db.save_report(user_id, issue)
                    
                    # Send to admins asynchronously
                    asyncio.create_task(notify_admins_report(context, user_id, issue))
                    
                    await update.effective_message.reply_text(json.dumps({"success": True}))
                    logger.info(f"📝 Report from user {user_id}: {issue[:50]}...")
                    
                except Exception as e:
                    logger.error(f"Report error: {e}")
                    await update.effective_message.reply_text(json.dumps({"success": False}))
            
            # ===== AD VIEW =====
            elif action == "ad_view":
                try:
                    ad_id = payload.get("ad_id")
                    if ad_id and Config.ENABLE_ADS:
                        db.record_ad_view(ad_id, user_id)
                        await update.effective_message.reply_text(json.dumps({"success": True}))
                except Exception as e:
                    logger.error(f"Ad view error: {e}")
            
            # ===== GET ADS =====
            elif action == "get_ads":
                try:
                    if Config.ENABLE_ADS:
                        ads = db.get_active_ads()
                        result = []
                        for ad in ads:
                            result.append({
                                "id": str(ad["_id"]),
                                "title": ad["title"],
                                "description": ad["description"],
                                "image_url": ad["image_url"],
                                "link_url": ad["link_url"]
                            })
                        await update.effective_message.reply_text(json.dumps(result))
                    else:
                        await update.effective_message.reply_text(json.dumps([]))
                except Exception as e:
                    logger.error(f"Get ads error: {e}")
                    await update.effective_message.reply_text(json.dumps([]))
            
        except Exception as e:
            logger.error(f"WebApp Data Handler Error: {e}")
            traceback.print_exc()
            try:
                await update.effective_message.reply_text(json.dumps({"error": "Internal server error"}))
            except:
                pass
    
    @staticmethod
    async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Global error handler - FIXED"""
        logger.error(f"Error in update {update}: {context.error}")
        traceback.print_exc()
        
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ *Technical Error*\n"
                    "Please try again later.\n"
                    "If problem persists, contact support.",
                    parse_mode='Markdown'
                )
        except:
            pass

# Helper function for admin notifications
async def notify_admins(context, user_id, amount, method, details):
    """Notify admins about withdrawal request"""
    for admin_id in Config.ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"💰 *New Withdrawal Request!*\n\n"
                f"👤 User: {user_id}\n"
                f"💵 Amount: ₹{amount:.2f}\n"
                f"🏦 Method: {method.upper()}\n"
                f"📝 Details: {details}",
                parse_mode='Markdown'
            )
        except:
            pass

async def notify_admins_report(context, user_id, issue):
    """Notify admins about report"""
    user_data = db.get_user(user_id)
    user_name = user_data.get("full_name", "Unknown") if user_data else "Unknown"
    
    for admin_id in Config.ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"⚠️ *NEW USER REPORT!*\n\n"
                f"👤 User: {user_name}\n"
                f"🆔 ID: {user_id}\n"
                f"📝 Issue: {issue}\n"
                f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                parse_mode='Markdown'
            )
        except:
            pass
