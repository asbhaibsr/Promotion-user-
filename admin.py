# admin.py
import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from database import db
from utils import is_admin, format_balance

logger = logging.getLogger(__name__)

class AdminHandlers:
    
    @staticmethod
    async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You are not admin!")
            return
        
        keyboard = [
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🗑️ Clear Junk", callback_data="admin_clear_junk")],
            [InlineKeyboardButton("📊 Global Stats", callback_data="admin_global_stats")],
            [InlineKeyboardButton("💰 Add/Remove Balance", callback_data="admin_balance")],
            [InlineKeyboardButton("🚫 Block/Unblock", callback_data="admin_block")],
            [InlineKeyboardButton("📝 Pending Withdrawals", callback_data="admin_withdrawals")],
            [InlineKeyboardButton("🏆 Process Leaderboard", callback_data="admin_leaderboard")],
            [InlineKeyboardButton("❌ Close", callback_data="admin_close")]
        ]
        
        await update.message.reply_text(
            "👑 *Admin Panel*\n"
            "Choose an option:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    @staticmethod
    async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if not is_admin(query.from_user.id):
            await query.edit_message_text("❌ You are not admin!")
            return
        
        data = query.data
        
        if data == "admin_broadcast":
            context.user_data["admin_action"] = "broadcast"
            await query.edit_message_text(
                "📢 *Broadcast Mode*\n\n"
                "Send your message to broadcast to all users.\n"
                "Type /cancel to cancel.",
                parse_mode='Markdown'
            )
        
        elif data == "admin_clear_junk":
            count = db.clear_junk_users()
            await query.edit_message_text(
                f"🗑️ *Clear Junk*\n\n"
                f"✅ Cleared {count} blocked users data!",
                parse_mode='Markdown'
            )
        
        elif data == "admin_global_stats":
            stats = db.get_stats()
            
            msg = (
                f"📊 *Global Statistics*\n\n"
                f"👥 *Total Users:* {stats['total_users']}\n"
                f"✅ *Active:* {stats['active_users']}\n"
                f"🚫 *Blocked:* {stats['blocked_users']}\n"
                f"📅 *Active Today:* {stats['active_today']}\n\n"
                f"💰 *Total Earned:* {format_balance(stats['total_earned'])}\n"
                f"💸 *Total Paid:* {format_balance(stats['total_paid'])}\n"
                f"📝 *Pending:* {stats['pending_withdrawals']}\n\n"
                f"📅 *Joined Today:* {stats['today_users']}"
            )
            
            await query.edit_message_text(msg, parse_mode='Markdown')
        
        elif data == "admin_leaderboard":
            top_users = db.process_monthly_leaderboard()
            
            msg = "🏆 *Monthly Leaderboard Processed!*\n\n"
            for idx, user in enumerate(top_users[:5], 1):
                reward = Config.LEADERBOARD_REWARDS.get(idx, {}).get("reward", 0)
                msg += f"#{idx} {user.get('full_name', 'User')[:15]} - {user['monthly_referrals']} refs - ₹{reward}\n"
            
            await query.edit_message_text(msg, parse_mode='Markdown')
        
        elif data == "admin_withdrawals":
            pending = list(db.withdrawals.find({"status": "pending"}).sort("requested", -1).limit(10))
            
            if not pending:
                await query.edit_message_text("📝 No pending withdrawals")
                return
            
            msg = "📝 *Pending Withdrawals*\n\n"
            for w in pending:
                user = db.get_user(w["user_id"])
                name = user.get("full_name", "User") if user else "Deleted"
                msg += (
                    f"👤 *{name}* (`{w['user_id']}`)\n"
                    f"💰 Amount: `{format_balance(w['amount'])}`\n"
                    f"🏦 Method: `{w['method']}`\n"
                    f"──────────\n"
                )
            
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
            await query.edit_message_text(
                msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "admin_panel":
            keyboard = [
                [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
                [InlineKeyboardButton("🗑️ Clear Junk", callback_data="admin_clear_junk")],
                [InlineKeyboardButton("📊 Global Stats", callback_data="admin_global_stats")],
                [InlineKeyboardButton("💰 Add/Remove", callback_data="admin_balance")],
                [InlineKeyboardButton("🚫 Block/Unblock", callback_data="admin_block")],
                [InlineKeyboardButton("📝 Withdrawals", callback_data="admin_withdrawals")],
                [InlineKeyboardButton("🏆 Process Leaderboard", callback_data="admin_leaderboard")],
                [InlineKeyboardButton("❌ Close", callback_data="admin_close")]
            ]
            
            await query.edit_message_text(
                "👑 *Admin Panel*\n"
                "Choose an option:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "admin_close":
            await query.edit_message_text("👋 Admin Panel Closed")
    
    @staticmethod
    async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            return
        
        if context.user_data.get("admin_action") != "broadcast":
            return
        
        if update.message.text == "/cancel":
            context.user_data.pop("admin_action", None)
            await update.message.reply_text("❌ Broadcast cancelled")
            return
        
        all_users = db.get_all_users(filter_blocked=True)
        total = len(all_users)
        
        if total == 0:
            await update.message.reply_text("❌ No users found")
            context.user_data.pop("admin_action", None)
            return
        
        status_msg = await update.message.reply_text(
            f"📢 *Broadcast Started*\n\n"
            f"Total Users: {total}\n"
            f"Sending... 0/{total}",
            parse_mode='Markdown'
        )
        
        sent = 0
        failed = 0
        blocked = 0
        
        for i, user in enumerate(all_users, 1):
            user_id = user["user_id"]
            
            try:
                if update.message.text:
                    await context.bot.send_message(
                        user_id,
                        update.message.text,
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
                elif update.message.photo:
                    await context.bot.send_photo(
                        user_id,
                        update.message.photo[-1].file_id,
                        caption=update.message.caption
                    )
                
                sent += 1
                
                if i % 10 == 0:
                    await status_msg.edit_text(
                        f"📢 *Broadcast*\n\n"
                        f"Total: {total}\n"
                        f"✅ Sent: {sent}\n"
                        f"❌ Failed: {failed}\n"
                        f"🚫 Blocked: {blocked}\n"
                        f"Progress: {i}/{total}",
                        parse_mode='Markdown'
                    )
                
                await asyncio.sleep(0.05)
                
            except Exception as e:
                if "bot was blocked" in str(e).lower() or "user is deactivated" in str(e).lower():
                    db.block_user(user_id, "Blocked user")
                    blocked += 1
                else:
                    failed += 1
                    logger.error(f"Broadcast failed {user_id}: {e}")
        
        await status_msg.edit_text(
            f"📢 *Broadcast Complete*\n\n"
            f"✅ *Sent:* {sent}/{total}\n"
            f"🚫 *Blocked:* {blocked}\n"
            f"❌ *Failed:* {failed}",
            parse_mode='Markdown'
        )
        
        context.user_data.pop("admin_action", None)
    
    @staticmethod
    async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            return
        
        text = update.message.text
        
        if text.startswith("/add "):
            parts = text.split()
            if len(parts) >= 3:
                try:
                    user_id = int(parts[1])
                    amount = float(parts[2])
                    reason = " ".join(parts[3:]) if len(parts) > 3 else "Admin Bonus"
                    
                    new_balance = db.update_balance(user_id, amount, "admin_add", reason)
                    
                    await update.message.reply_text(
                        f"✅ *Balance Added*\n\n"
                        f"User: `{user_id}`\n"
                        f"Amount: `{format_balance(amount)}`\n"
                        f"New Balance: `{format_balance(new_balance)}`",
                        parse_mode='Markdown'
                    )
                    
                    try:
                        await context.bot.send_message(
                            user_id,
                            f"🎁 *Bonus!*\n\n"
                            f"You got ₹{amount} bonus!\n"
                            f"Reason: {reason}",
                            parse_mode='Markdown'
                        )
                    except:
                        pass
                    
                except Exception as e:
                    await update.message.reply_text(f"❌ Error: {e}")
        
        elif text.startswith("/remove "):
            parts = text.split()
            if len(parts) >= 3:
                try:
                    user_id = int(parts[1])
                    amount = float(parts[2])
                    
                    new_balance = db.update_balance(user_id, -amount, "admin_remove", "Admin removed")
                    
                    await update.message.reply_text(
                        f"✅ *Balance Removed*\n\n"
                        f"User: `{user_id}`\n"
                        f"Amount: `{format_balance(amount)}`\n"
                        f"New Balance: `{format_balance(new_balance)}`",
                        parse_mode='Markdown'
                    )
                    
                except Exception as e:
                    await update.message.reply_text(f"❌ Error: {e}")
        
        elif text.startswith("/block "):
            parts = text.split()
            if len(parts) >= 2:
                try:
                    user_id = int(parts[1])
                    reason = " ".join(parts[2:]) if len(parts) > 2 else "Blocked by admin"
                    
                    db.block_user(user_id, reason)
                    
                    await update.message.reply_text(
                        f"🚫 *User Blocked*\n\n"
                        f"User: `{user_id}`\n"
                        f"Reason: {reason}",
                        parse_mode='Markdown'
                    )
                    
                except Exception as e:
                    await update.message.reply_text(f"❌ Error: {e}")
        
        elif text.startswith("/unblock "):
            parts = text.split()
            if len(parts) >= 2:
                try:
                    user_id = int(parts[1])
                    
                    db.unblock_user(user_id)
                    
                    await update.message.reply_text(
                        f"✅ *User Unblocked*\n\n"
                        f"User: `{user_id}`",
                        parse_mode='Markdown'
                    )
                    
                except Exception as e:
                    await update.message.reply_text(f"❌ Error: {e}")
        
        elif text == "/stats":
            stats = db.get_stats()
            
            msg = (
                f"📊 *Global Stats*\n\n"
                f"👥 *Total Users:* {stats['total_users']}\n"
                f"✅ *Active:* {stats['active_users']}\n"
                f"🚫 *Blocked:* {stats['blocked_users']}\n"
                f"📅 *Active Today:* {stats['active_today']}\n\n"
                f"💰 *Total Earned:* {format_balance(stats['total_earned'])}\n"
                f"💸 *Total Paid:* {format_balance(stats['total_paid'])}\n"
                f"📝 *Pending:* {stats['pending_withdrawals']}\n\n"
                f"📅 *Joined Today:* {stats['today_users']}"
            )
            
            await update.message.reply_text(msg, parse_mode='Markdown')
        
        elif text == "/admin":
            await AdminHandlers.admin_panel(update, context)
