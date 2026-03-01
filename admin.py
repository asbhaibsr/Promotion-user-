# admin.py - एडमिन कमांड्स

import logging
import asyncio
import re
from datetime import datetime
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
            [InlineKeyboardButton("📊 Global Stats", callback_data="admin_global_stats")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("💰 Pending Withdrawals", callback_data="admin_withdrawals")],
            [InlineKeyboardButton("📝 User Reports", callback_data="admin_reports")],
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
                f"📝 *Pending Withdrawals:* {stats['pending_withdrawals']}\n\n"
                f"📅 *Joined Today:* {stats['today_users']}"
            )
            
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
        
        elif data == "admin_reports":
            reports = list(db.reports.find({"status": "pending"}).sort("timestamp", -1).limit(10))
            
            if not reports:
                await query.edit_message_text("📝 No pending reports")
                return
            
            msg = "📝 *User Reports*\n\n"
            for r in reports:
                user = db.get_user(r["user_id"])
                name = user.get("full_name", "User") if user else "Unknown"
                msg += (
                    f"👤 *{name}* (`{r['user_id']}`)\n"
                    f"📝 Issue: `{r['issue'][:50]}...`\n"
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
                [InlineKeyboardButton("📊 Global Stats", callback_data="admin_global_stats")],
                [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
                [InlineKeyboardButton("💰 Withdrawals", callback_data="admin_withdrawals")],
                [InlineKeyboardButton("📝 Reports", callback_data="admin_reports")],
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
        
        for i, user in enumerate(all_users, 1):
            user_id = user["user_id"]
            
            try:
                await context.bot.send_message(
                    user_id,
                    update.message.text,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
                sent += 1
                
                if i % 10 == 0:
                    await status_msg.edit_text(
                        f"📢 *Broadcast*\n\n"
                        f"Total: {total}\n"
                        f"✅ Sent: {sent}\n"
                        f"❌ Failed: {failed}\n"
                        f"Progress: {i}/{total}",
                        parse_mode='Markdown'
                    )
                
                await asyncio.sleep(0.05)
                
            except Exception as e:
                failed += 1
                logger.error(f"Broadcast failed {user_id}: {e}")
        
        await status_msg.edit_text(
            f"📢 *Broadcast Complete*\n\n"
            f"✅ *Sent:* {sent}/{total}\n"
            f"❌ *Failed:* {failed}",
            parse_mode='Markdown'
        )
        
        context.user_data.pop("admin_action", None)
    
    @staticmethod
    async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            return
        
        text = update.message.text
        
        # ===== ADD BALANCE =====
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
        
        # ===== REMOVE BALANCE =====
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
        
        # ===== CLEAR DATA =====
        elif text.startswith("/clear"):
            await update.message.reply_text(
                "🗑️ *Clear Data*\n\n"
                "Reply to this message with:\n"
                "• `all` - Clear ALL data (full reset)\n"
                "• `earnings` - Clear only earnings & referrals",
                parse_mode='Markdown'
            )
            context.user_data["awaiting_clear"] = True
        
        # ===== STATS =====
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
        
        # ===== ADMIN PANEL =====
        elif text == "/admin":
            await AdminHandlers.admin_panel(update, context)
    
    @staticmethod
    async def handle_clear_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle clear command reply"""
        if not is_admin(update.effective_user.id):
            return
        
        if not context.user_data.get("awaiting_clear"):
            return
        
        if not update.message.reply_to_message:
            return
        
        text = update.message.text.lower().strip()
        
        # Get user ID from replied message
        replied_text = update.message.reply_to_message.text
        match = re.search(r'`(\d+)`', replied_text)
        
        if not match:
            await update.message.reply_text("❌ User ID not found in replied message")
            context.user_data.pop("awaiting_clear", None)
            return
        
        user_id = int(match.group(1))
        
        if text == "all":
            db.clear_all_user_data(user_id)
            await update.message.reply_text(f"✅ *All data cleared for user `{user_id}`*", parse_mode='Markdown')
        
        elif text == "earnings":
            db.clear_user_earnings(user_id)
            await update.message.reply_text(f"✅ *Earnings cleared for user `{user_id}`*", parse_mode='Markdown')
        
        else:
            await update.message.reply_text("❌ Invalid option. Use `all` or `earnings`")
        
        context.user_data.pop("awaiting_clear", None)
