# admin.py - Advanced Admin Panel

import logging
import asyncio
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from database import db
from utils import is_admin, format_balance
from bson.objectid import ObjectId

logger = logging.getLogger(__name__)

class AdminHandlers:
    
    @staticmethod
    async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show admin panel"""
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You are not admin!")
            return
        
        keyboard = [
            [InlineKeyboardButton("📊 Global Stats", callback_data="admin_global_stats")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("💰 Pending Withdrawals", callback_data="admin_withdrawals")],
            [InlineKeyboardButton("📝 User Reports", callback_data="admin_reports")],
            [InlineKeyboardButton("👥 User Management", callback_data="admin_user_mgmt")],
            [InlineKeyboardButton("🎡 Spin Stats", callback_data="admin_spin_stats")],
            [InlineKeyboardButton("📅 Monthly Reset", callback_data="admin_monthly_reset")],
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
        """Handle admin callbacks"""
        query = update.callback_query
        await query.answer()
        
        if not is_admin(query.from_user.id):
            await query.edit_message_text("❌ You are not admin!")
            return
        
        data = query.data
        
        if data == "admin_global_stats":
            stats = db.get_stats()
            
            # Format tier distribution
            tier_text = ""
            for tier, count in stats["tier_distribution"].items():
                tier_name = Config.TIERS[int(tier)]["name"]
                tier_text += f"  {tier_name}: {count}\n"
            
            msg = (
                f"📊 *GLOBAL STATISTICS*\n\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"👥 *Users*\n"
                f"  Total: {stats['total_users']}\n"
                f"  Active: {stats['active_users']}\n"
                f"  Blocked: {stats['blocked_users']}\n"
                f"  Today: {stats['today_users']}\n"
                f"  Active Today: {stats['active_today']}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💰 *Financial*\n"
                f"  Total Earned: {format_balance(stats['total_earned'])}\n"
                f"  Total Paid: {format_balance(stats['total_paid'])}\n"
                f"  Pending: {stats['pending_withdrawals']}\n"
                f"  Pending Amount: {format_balance(stats['pending_amount'])}\n"
                f"  Today Earned: {format_balance(stats['today_earned'])}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"👥 *Referrals*\n"
                f"  Total: {stats['total_referrals']}\n"
                f"  Active: {stats['active_referrals']}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🎡 *Spins*\n"
                f"  Total Spins: {stats['total_spins']}\n"
                f"  Today Spins: {stats['today_spins']}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"👑 *Tier Distribution*\n"
                f"{tier_text}"
            )
            
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
            await query.edit_message_text(
                msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "admin_broadcast":
            context.user_data["admin_action"] = "broadcast"
            await query.edit_message_text(
                "📢 *Broadcast Mode*\n\n"
                "Send your message to broadcast to all users.\n"
                "You can use Markdown formatting.\n"
                "Type /cancel to cancel.",
                parse_mode='Markdown'
            )
        
        elif data == "admin_withdrawals":
            pending = list(db.withdrawals.find(
                {"status": "pending"}
            ).sort("requested", -1).limit(10))
            
            if not pending:
                await query.edit_message_text(
                    "📝 No pending withdrawals",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Back", callback_data="admin_panel")
                    ]])
                )
                return
            
            msg = "📝 *PENDING WITHDRAWALS*\n\n"
            keyboard = []
            
            for w in pending:
                user = db.get_user(w["user_id"])
                name = user.get("full_name", "User")[:15] if user else "Deleted"
                time_ago = (datetime.now() - w["requested"]).seconds // 3600
                
                msg += (
                    f"👤 *{name}* (`{w['user_id']}`)\n"
                    f"💰 Amount: `{format_balance(w['amount'])}`\n"
                    f"🏦 Method: `{w['method']}`\n"
                    f"⏰ {time_ago}h ago\n"
                    f"──────────\n"
                )
                
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ Process {format_balance(w['amount'])}", 
                        callback_data=f"admin_process_{w['_id']}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
            
            await query.edit_message_text(
                msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data.startswith("admin_process_"):
            withdrawal_id = data.replace("admin_process_", "")
            
            # Show processing options
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{withdrawal_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{withdrawal_id}")
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="admin_withdrawals")]
            ]
            
            await query.edit_message_text(
                "💰 *Process Withdrawal*\n\n"
                "Choose action:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data.startswith("admin_approve_"):
            withdrawal_id = data.replace("admin_approve_", "")
            
            success = db.process_withdrawal(withdrawal_id, "completed", query.from_user.id)
            
            if success:
                withdrawal = db.withdrawals.find_one({"_id": ObjectId(withdrawal_id)})
                user_id = withdrawal["user_id"]
                amount = withdrawal["amount"]
                
                # Notify user
                try:
                    await context.bot.send_message(
                        user_id,
                        f"✅ *Withdrawal Approved!*\n\n"
                        f"Amount: `{format_balance(amount)}`\n"
                        f"Your payment has been sent successfully!",
                        parse_mode='Markdown'
                    )
                except:
                    pass
                
                await query.edit_message_text(
                    f"✅ Withdrawal approved successfully!",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Back", callback_data="admin_withdrawals")
                    ]])
                )
            else:
                await query.edit_message_text(
                    "❌ Failed to process withdrawal",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Back", callback_data="admin_withdrawals")
                    ]])
                )
        
        elif data.startswith("admin_reject_"):
            withdrawal_id = data.replace("admin_reject_", "")
            
            success = db.process_withdrawal(withdrawal_id, "rejected", query.from_user.id)
            
            if success:
                withdrawal = db.withdrawals.find_one({"_id": ObjectId(withdrawal_id)})
                user_id = withdrawal["user_id"]
                amount = withdrawal["amount"]
                
                # Notify user
                try:
                    await context.bot.send_message(
                        user_id,
                        f"❌ *Withdrawal Rejected*\n\n"
                        f"Amount: `{format_balance(amount)}`\n"
                        f"Reason: Please check your payment details.\n"
                        f"Amount has been refunded to your balance.",
                        parse_mode='Markdown'
                    )
                except:
                    pass
                
                await query.edit_message_text(
                    f"❌ Withdrawal rejected and refunded",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Back", callback_data="admin_withdrawals")
                    ]])
                )
            else:
                await query.edit_message_text(
                    "❌ Failed to process withdrawal",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Back", callback_data="admin_withdrawals")
                    ]])
                )
        
        elif data == "admin_reports":
            reports = list(db.reports.find(
                {"status": "pending"}
            ).sort("timestamp", -1).limit(10))
            
            if not reports:
                await query.edit_message_text(
                    "📝 No pending reports",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Back", callback_data="admin_panel")
                    ]])
                )
                return
            
            msg = "📝 *USER REPORTS*\n\n"
            keyboard = []
            
            for r in reports:
                user = db.get_user(r["user_id"])
                name = user.get("full_name", "User")[:15] if user else "Unknown"
                time_ago = (datetime.now() - r["timestamp"]).seconds // 3600
                
                msg += (
                    f"👤 *{name}* (`{r['user_id']}`)\n"
                    f"📝 Issue: `{r['issue'][:50]}...`\n"
                    f"⏰ {time_ago}h ago\n"
                    f"──────────\n"
                )
                
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ Mark Resolved", 
                        callback_data=f"admin_resolve_{r['_id']}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
            
            await query.edit_message_text(
                msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data.startswith("admin_resolve_"):
            report_id = data.replace("admin_resolve_", "")
            
            db.reports.update_one(
                {"_id": ObjectId(report_id)},
                {"$set": {"status": "resolved"}}
            )
            
            await query.edit_message_text(
                "✅ Report marked as resolved",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="admin_reports")
                ]])
            )
        
        elif data == "admin_user_mgmt":
            keyboard = [
                [InlineKeyboardButton("🔍 Search User", callback_data="admin_search_user")],
                [InlineKeyboardButton("📋 List Recent Users", callback_data="admin_recent_users")],
                [InlineKeyboardButton("🚫 Blocked Users", callback_data="admin_blocked_users")],
                [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
            ]
            
            await query.edit_message_text(
                "👥 *User Management*\n\n"
                "Choose an option:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "admin_search_user":
            context.user_data["admin_action"] = "search_user"
            await query.edit_message_text(
                "🔍 *Search User*\n\n"
                "Send me the user ID or username to search.\n"
                "Type /cancel to cancel.",
                parse_mode='Markdown'
            )
        
        elif data == "admin_recent_users":
            users = db.get_all_users(limit=10)
            
            msg = "📋 *Recent Users (Last 10)*\n\n"
            for u in users:
                joined = u.get("joined", datetime.now())
                days_ago = (datetime.now() - joined).days
                msg += (
                    f"👤 {u.get('full_name', 'User')[:15]}\n"
                    f"  ID: `{u['user_id']}`\n"
                    f"  Balance: {format_balance(u.get('balance', 0))}\n"
                    f"  Joined: {days_ago}d ago\n"
                    f"──────────\n"
                )
            
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_user_mgmt")]]
            await query.edit_message_text(
                msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "admin_blocked_users":
            blocked = list(db.users.find({"is_blocked": True}).limit(10))
            
            if not blocked:
                await query.edit_message_text(
                    "✅ No blocked users",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Back", callback_data="admin_user_mgmt")
                    ]])
                )
                return
            
            msg = "🚫 *Blocked Users*\n\n"
            for u in blocked:
                msg += f"👤 {u.get('full_name', 'User')[:15]} (`{u['user_id']}`)\n"
            
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_user_mgmt")]]
            await query.edit_message_text(
                msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "admin_spin_stats":
            # Get spin statistics
            total_spins = db.spins.count_documents({})
            today_spins = db.spins.count_documents({
                "timestamp": {"$gte": datetime.now().replace(hour=0, minute=0, second=0)}
            })
            
            # Prize distribution
            pipeline = [
                {"$group": {"_id": "$prize", "count": {"$sum": 1}}},
                {"$sort": {"_id": 1}}
            ]
            prize_dist = list(db.spins.aggregate(pipeline))
            
            msg = (
                f"🎡 *SPIN STATISTICS*\n\n"
                f"Total Spins: {total_spins}\n"
                f"Today Spins: {today_spins}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"*Prize Distribution*\n"
            )
            
            for p in prize_dist:
                prize = p["_id"]
                count = p["count"]
                percentage = (count / total_spins * 100) if total_spins > 0 else 0
                msg += f"  ₹{prize}: {count} ({percentage:.1f}%)\n"
            
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
            await query.edit_message_text(
                msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "admin_monthly_reset":
            keyboard = [
                [InlineKeyboardButton("✅ Confirm Reset", callback_data="admin_confirm_reset")],
                [InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]
            ]
            
            await query.edit_message_text(
                "⚠️ *Monthly Reset*\n\n"
                "This will:\n"
                "• Give rewards to top 10 referrers\n"
                "• Reset monthly referral counts\n"
                "• Update leaderboard\n\n"
                "Are you sure?",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "admin_confirm_reset":
            rewards = db.reset_monthly_referrals()
            
            msg = "✅ *Monthly Reset Complete*\n\n"
            if rewards:
                msg += "*Rewards Given:*\n"
                for r in rewards:
                    msg += f"  Rank #{r['rank']}: ₹{r['reward']}\n"
            else:
                msg += "No rewards given (insufficient referrals)"
            
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
                [InlineKeyboardButton("👥 User Management", callback_data="admin_user_mgmt")],
                [InlineKeyboardButton("🎡 Spin Stats", callback_data="admin_spin_stats")],
                [InlineKeyboardButton("📅 Monthly Reset", callback_data="admin_monthly_reset")],
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
        """Handle broadcast messages"""
        if not is_admin(update.effective_user.id):
            return
        
        if context.user_data.get("admin_action") != "broadcast":
            return
        
        if update.message.text == "/cancel":
            context.user_data.pop("admin_action", None)
            await update.message.reply_text("❌ Broadcast cancelled")
            return
        
        # Get all active users
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
        start_time = datetime.now()
        
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
                
                # Update progress every 10 messages
                if i % 10 == 0:
                    elapsed = (datetime.now() - start_time).seconds
                    speed = i / elapsed if elapsed > 0 else 0
                    eta = (total - i) / speed if speed > 0 else 0
                    
                    await status_msg.edit_text(
                        f"📢 *Broadcast*\n\n"
                        f"Total: {total}\n"
                        f"✅ Sent: {sent}\n"
                        f"❌ Failed: {failed}\n"
                        f"Progress: {i}/{total}\n"
                        f"Speed: {speed:.1f} msg/s\n"
                        f"ETA: {eta:.0f}s",
                        parse_mode='Markdown'
                    )
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.05)
                
            except Exception as e:
                failed += 1
                logger.error(f"Broadcast failed for {user_id}: {e}")
        
        elapsed = (datetime.now() - start_time).seconds
        await status_msg.edit_text(
            f"📢 *Broadcast Complete*\n\n"
            f"✅ *Sent:* {sent}/{total}\n"
            f"❌ *Failed:* {failed}\n"
            f"⏱️ *Time:* {elapsed}s",
            parse_mode='Markdown'
        )
        
        context.user_data.pop("admin_action", None)
    
    @staticmethod
    async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin text commands"""
        if not is_admin(update.effective_user.id):
            return
        
        text = update.message.text
        
        # Handle search user
        if context.user_data.get("admin_action") == "search_user":
            try:
                # Try to parse as user ID
                if text.isdigit():
                    user_id = int(text)
                else:
                    # Search by username
                    username = text.replace("@", "").lower()
                    user = db.users.find_one({"username": username})
                    user_id = user["user_id"] if user else None
                
                if not user_id:
                    await update.message.reply_text("❌ User not found")
                    context.user_data.pop("admin_action", None)
                    return
                
                user = db.get_user(user_id)
                if not user:
                    await update.message.reply_text("❌ User not found")
                    context.user_data.pop("admin_action", None)
                    return
                
                stats = db.get_user_stats(user_id)
                
                msg = (
                    f"👤 *User Details*\n\n"
                    f"Name: {user.get('full_name', 'N/A')}\n"
                    f"Username: @{user.get('username', 'N/A')}\n"
                    f"ID: `{user_id}`\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"💰 Balance: {format_balance(stats['balance'])}\n"
                    f"💵 Total Earned: {format_balance(stats['total_earned'])}\n"
                    f"🎰 Spins: {stats['spins']}\n"
                    f"👑 Tier: {stats['tier_name']}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"👥 Referrals: {stats['total_refs']} total, {stats['active_refs']} active\n"
                    f"📅 Streak: {stats['daily_streak']} days\n"
                    f"🔍 Searches: {stats['total_searches']}\n"
                    f"🎡 Total Spins: {stats['total_spins']}\n"
                    f"🏆 Best Spin: ₹{stats['best_spin_win']}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📅 Joined: {stats['joined'][:10]}\n"
                    f"🕐 Last Active: {stats['last_active'][:10] if stats['last_active'] else 'Never'}"
                )
                
                keyboard = [
                    [
                        InlineKeyboardButton("➕ Add Balance", callback_data=f"admin_add_{user_id}"),
                        InlineKeyboardButton("➖ Remove", callback_data=f"admin_remove_{user_id}")
                    ],
                    [
                        InlineKeyboardButton("🚫 Block", callback_data=f"admin_block_{user_id}"),
                        InlineKeyboardButton("🗑️ Clear", callback_data=f"admin_clear_{user_id}")
                    ],
                    [InlineKeyboardButton("🔙 Back", callback_data="admin_user_mgmt")]
                ]
                
                await update.message.reply_text(
                    msg,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
                
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {e}")
            
            context.user_data.pop("admin_action", None)
            return
        
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
                        f"New Balance: `{format_balance(new_balance)}`\n"
                        f"Reason: {reason}",
                        parse_mode='Markdown'
                    )
                    
                    # Notify user
                    try:
                        await context.bot.send_message(
                            user_id,
                            f"🎁 *Bonus Added!*\n\n"
                            f"You got `{format_balance(amount)}` bonus!\n"
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
                "• `earnings` - Clear only earnings & referrals\n\n"
                "Or use:\n"
                "`/clear_user [user_id] [all/earnings]`",
                parse_mode='Markdown'
            )
            context.user_data["awaiting_clear"] = True
        
        # ===== STATS =====
        elif text == "/stats":
            stats = db.get_stats()
            
            msg = (
                f"📊 *Quick Stats*\n\n"
                f"👥 Users: {stats['total_users']}\n"
                f"✅ Active Today: {stats['active_today']}\n"
                f"💰 Total Earned: {format_balance(stats['total_earned'])}\n"
                f"💸 Total Paid: {format_balance(stats['total_paid'])}\n"
                f"📝 Pending: {stats['pending_withdrawals']}\n"
                f"📅 Today Users: {stats['today_users']}"
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
        
        # Try to get user ID from replied message
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
