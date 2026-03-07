# ===== admin.py (FIXED - WITH USER DATA MANAGEMENT) =====

import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from bson.objectid import ObjectId

logger = logging.getLogger(__name__)

class AdminHandlers:
    def __init__(self, config, db, bot):
        self.config = config
        self.db = db
        self.bot = bot
        logger.info("✅ Admin handlers initialized")
    
    # ========== MAIN ADMIN PANEL ==========
    
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main admin panel command (/admin)"""
        user_id = update.effective_user.id
        
        if user_id not in self.config.ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        total_users = self.db.users.count_documents({})
        pending_withdrawals = self.db.withdrawals.count_documents({'status': 'pending'})
        pending_support = self.db.issues.count_documents({'status': 'pending'})
        
        keyboard = [
            [InlineKeyboardButton("🔍 SEARCH USER", callback_data="admin_search_user")],
            [InlineKeyboardButton("📢 BROADCAST", callback_data="admin_broadcast")],
            [InlineKeyboardButton("💰 WITHDRAWALS", callback_data="admin_withdrawals")],
            [InlineKeyboardButton("📩 SUPPORT MESSAGES", callback_data="admin_support")],
            [InlineKeyboardButton("🗑️ USER DATA MANAGER", callback_data="admin_data_manager")],
            [InlineKeyboardButton("❌ CLOSE", callback_data="admin_close")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = (
            "👑 **Admin Panel**\n\n"
            f"📊 **Quick Stats:**\n"
            f"• Total Users: {total_users}\n"
            f"• Pending Withdrawals: {pending_withdrawals}\n"
            f"• Pending Support: {pending_support}\n\n"
            f"Select an option below:"
        )
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    # ========== CALLBACK HANDLER ==========
    
    async def handle_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all admin callback queries"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id
        
        if user_id not in self.config.ADMIN_IDS:
            await query.edit_message_text("❌ Unauthorized")
            return
        
        logger.info(f"Admin callback: {data}")
        
        if data == "admin_search_user":
            await self.search_user_prompt(query, context)
            
        elif data == "admin_broadcast":
            await self.broadcast_menu(query, context)
            
        elif data == "admin_withdrawals":
            await self.withdrawals_menu(query, context)
            
        elif data == "admin_support":
            await self.support_messages_menu(query, context)
            
        elif data == "admin_data_manager":
            await self.data_manager_menu(query, context)
            
        elif data == "admin_clear_junk":
            await self.clear_junk_users(query, context)
            
        elif data == "admin_close":
            await query.edit_message_text("🔒 Admin panel closed.")
            
        elif data == "back_to_admin":
            await self.back_to_admin(query, context)
            
        # ===== USER DETAILS =====
        elif data.startswith("user_details_"):
            try:
                target_id = int(data.replace("user_details_", ""))
                await self.show_user_details(query, context, target_id)
            except Exception as e:
                logger.error(f"Error: {e}")
        
        # ===== USER DATA MANAGEMENT =====
        elif data.startswith("manage_user_"):
            try:
                target_id = int(data.replace("manage_user_", ""))
                context.user_data['managing_user'] = target_id
                await self.user_management_menu(query, context, target_id)
            except Exception as e:
                logger.error(f"Error: {e}")
        
        # ===== SUPPORT MESSAGES =====
        elif data.startswith("view_support_"):
            try:
                msg_id = data.replace("view_support_", "")
                await self.view_support_message(query, context, msg_id)
            except Exception as e:
                logger.error(f"Error: {e}")
                await query.edit_message_text(
                    "❌ Error loading support message. It may have been deleted.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("◀️ BACK", callback_data="admin_support")
                    ]])
                )
        
        elif data.startswith("reply_support_"):
            try:
                msg_id = data.replace("reply_support_", "")
                context.user_data['replying_to'] = msg_id
                context.user_data['admin_action'] = f"reply_support_{msg_id}"
                
                await query.edit_message_text(
                    f"📝 **Reply to Support Message**\n\n"
                    f"Please type your reply:",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("◀️ BACK", callback_data="admin_support")
                    ]])
                )
            except Exception as e:
                logger.error(f"Error: {e}")
        
        # ===== WITHDRAWAL ACTIONS =====
        elif data.startswith("approve_"):
            withdrawal_id = data.replace("approve_", "")
            await self.approve_withdrawal(query, context, withdrawal_id)
            
        elif data.startswith("reject_"):
            withdrawal_id = data.replace("reject_", "")
            await self.reject_withdrawal(query, context, withdrawal_id)
            
        elif data.startswith("view_withdrawal_"):
            try:
                withdrawal_id = data.replace("view_withdrawal_", "")
                await self.view_withdrawal_details(query, context, withdrawal_id)
            except Exception as e:
                logger.error(f"Error: {e}")
    
    # ========== DATA MANAGER MENU ==========
    
    async def data_manager_menu(self, query, context):
        """Show data manager options"""
        context.user_data['admin_action'] = 'data_manager'
        
        keyboard = [[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🗑️ **User Data Manager**\n\n"
            "Please enter the user ID to manage:\n\n"
            "You can then:\n"
            "• Clear user's earnings (balance reset to 0)\n"
            "• Delete ALL user data (complete removal)\n"
            "• Add money (+100)\n"
            "• Remove money (-50)",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def process_data_manager(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process user ID for data management"""
        try:
            target_id = int(update.message.text.strip())
            user = self.db.get_user(target_id)
            
            if user:
                context.user_data['managing_user'] = target_id
                await self.user_management_menu(None, context, target_id, update.message)
            else:
                await update.message.reply_text(f"❌ User {target_id} not found")
                
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID. Please enter a numeric ID.")
        except Exception as e:
            logger.error(f"Data manager error: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
        
        context.user_data['admin_action'] = None
    
    async def user_management_menu(self, query, context, target_id, message=None):
        """Show user management options"""
        user = self.db.get_user(target_id)
        if not user:
            text = f"❌ User {target_id} not found"
            if query:
                await query.edit_message_text(text)
            else:
                await message.reply_text(text)
            return
        
        text = (
            f"👤 **User: {user.get('first_name', 'Unknown')}**\n"
            f"ID: `{target_id}`\n"
            f"💰 Balance: ₹{user.get('balance', 0):.2f}\n"
            f"📊 Total Earned: ₹{user.get('total_earned', 0):.2f}\n\n"
            f"**Choose action:**\n\n"
            f"• Send `+100` to add ₹100\n"
            f"• Send `-50` to remove ₹50\n"
            f"• Send `earning` to clear earnings (balance=0)\n"
            f"• Send `all` to delete ALL user data\n\n"
            f"Reply to this message with your command:"
        )
        
        keyboard = [[InlineKeyboardButton("◀️ BACK", callback_data="admin_data_manager")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        context.user_data['admin_action'] = f"manage_{target_id}"
        
        if query:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        else:
            await message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    # ========== PROCESS USER MANAGEMENT COMMANDS ==========
    
    async def process_user_management(self, update: Update, context: ContextTypes.DEFAULT_TYPE, target_id):
        """Process user management commands (earning/all/+/-)"""
        try:
            command = update.message.text.strip().lower()
            user = self.db.get_user(target_id)
            
            if not user:
                await update.message.reply_text(f"❌ User {target_id} not found")
                return
            
            # ===== CLEAR EARNINGS ONLY =====
            if command == 'earning':
                old_balance = user.get('balance', 0)
                old_total = user.get('total_earned', 0)
                
                # Reset balance and total_earned to 0
                self.db.users.update_one(
                    {'user_id': target_id},
                    {'$set': {'balance': 0, 'total_earned': 0}}
                )
                
                # Clear transactions
                self.db.transactions.delete_many({'user_id': target_id})
                
                self.db.user_cache.pop(f"user_{target_id}", None)
                
                await update.message.reply_text(
                    f"✅ **Earnings Cleared** for user {target_id}\n\n"
                    f"Old Balance: ₹{old_balance:.2f}\n"
                    f"Old Total: ₹{old_total:.2f}\n"
                    f"New Balance: ₹0.00",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                self.db.log_system_event('earnings_cleared', f"User {target_id} by admin {update.effective_user.id}")
            
            # ===== DELETE ALL USER DATA =====
            elif command == 'all':
                # Delete all user data
                self.db.users.delete_one({'user_id': target_id})
                self.db.transactions.delete_many({'user_id': target_id})
                self.db.withdrawals.delete_many({'user_id': target_id})
                self.db.referrals.delete_many({
                    '$or': [
                        {'referrer_id': target_id},
                        {'referred_id': target_id}
                    ]
                })
                self.db.daily_searches.delete_many({'user_id': target_id})
                self.db.search_logs.delete_many({'user_id': target_id})
                self.db.daily_bonus.delete_many({'user_id': target_id})
                self.db.missions.delete_many({'user_id': target_id})
                self.db.daily_claims.delete_many({'user_id': target_id})
                self.db.issues.delete_many({'user_id': target_id})
                self.db.live_activity.delete_many({'user_id': target_id})
                
                self.db.user_cache.pop(f"user_{target_id}", None)
                
                await update.message.reply_text(
                    f"✅ **ALL DATA DELETED** for user {target_id}\n\n"
                    f"User has been completely removed from database.",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                self.db.log_system_event('user_deleted', f"User {target_id} by admin {update.effective_user.id}")
            
            # ===== ADD MONEY (+amount) =====
            elif command.startswith('+'):
                try:
                    amount = float(command[1:])
                    if amount <= 0:
                        await update.message.reply_text("❌ Amount must be positive")
                        return
                    
                    old_balance = user.get('balance', 0)
                    
                    self.db.add_balance(target_id, amount, f"Admin added ₹{amount}")
                    
                    new_balance = old_balance + amount
                    
                    await update.message.reply_text(
                        f"✅ **Added ₹{amount:.2f}** to user {target_id}\n\n"
                        f"Old Balance: ₹{old_balance:.2f}\n"
                        f"New Balance: ₹{new_balance:.2f}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                    # Notify user
                    try:
                        await context.bot.send_message(
                            chat_id=target_id,
                            text=f"✅ Admin added ₹{amount:.2f} to your balance!"
                        )
                    except:
                        pass
                    
                except ValueError:
                    await update.message.reply_text("❌ Invalid amount format. Use +100")
            
            # ===== REMOVE MONEY (-amount) =====
            elif command.startswith('-'):
                try:
                    amount = float(command[1:])
                    if amount <= 0:
                        await update.message.reply_text("❌ Amount must be positive")
                        return
                    
                    old_balance = user.get('balance', 0)
                    
                    if old_balance < amount:
                        await update.message.reply_text(
                            f"❌ User only has ₹{old_balance:.2f}. Cannot remove ₹{amount:.2f}"
                        )
                        return
                    
                    new_balance = old_balance - amount
                    
                    self.db.users.update_one(
                        {'user_id': target_id},
                        {'$inc': {'balance': -amount}}
                    )
                    
                    self.db.add_transaction(target_id, 'admin_remove', -amount, f"Admin removed ₹{amount}")
                    self.db.user_cache.pop(f"user_{target_id}", None)
                    
                    await update.message.reply_text(
                        f"✅ **Removed ₹{amount:.2f}** from user {target_id}\n\n"
                        f"Old Balance: ₹{old_balance:.2f}\n"
                        f"New Balance: ₹{new_balance:.2f}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                    # Notify user
                    try:
                        await context.bot.send_message(
                            chat_id=target_id,
                            text=f"⚠️ Admin removed ₹{amount:.2f} from your balance."
                        )
                    except:
                        pass
                    
                except ValueError:
                    await update.message.reply_text("❌ Invalid amount format. Use -50")
            
            else:
                await update.message.reply_text(
                    "❌ **Invalid Command**\n\n"
                    "Use:\n"
                    "• `+100` - Add ₹100\n"
                    "• `-50` - Remove ₹50\n"
                    "• `earning` - Clear earnings (balance=0)\n"
                    "• `all` - Delete ALL user data",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Clear admin action
            context.user_data['admin_action'] = None
            context.user_data['managing_user'] = None
            
        except Exception as e:
            logger.error(f"User management error: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    # ========== SEARCH USER ==========
    
    async def search_user_prompt(self, query, context):
        """Prompt for user ID to search"""
        context.user_data['admin_action'] = 'search_user'
        
        keyboard = [[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🔍 **Search User**\n\n"
            "Please enter the user ID to search:",
            reply_markup=reply_markup
        )
    
    async def process_search_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process user search"""
        try:
            target_id = int(update.message.text.strip())
            user = self.db.get_user(target_id)
            
            if user:
                keyboard = [
                    [InlineKeyboardButton("👤 VIEW DETAILS", callback_data=f"user_details_{target_id}")],
                    [InlineKeyboardButton("🗑️ MANAGE USER", callback_data=f"manage_user_{target_id}")]
                ]
                await update.message.reply_text(
                    f"✅ User {target_id} found!",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await update.message.reply_text(f"❌ User {target_id} not found")
                
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID. Please enter a numeric ID.")
        except Exception as e:
            logger.error(f"Search user error: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
        
        context.user_data['admin_action'] = None
    
    # ========== SHOW USER DETAILS ==========
    
    async def show_user_details(self, query, context, target_id):
        """Show detailed stats for a specific user"""
        user = self.db.get_user(target_id)
        
        if not user:
            await query.edit_message_text(
                f"❌ User {target_id} not found",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ BACK", callback_data="admin_search_user")
                ]])
            )
            return
        
        text = (
            f"👤 **User Details**\n\n"
            f"**Basic Info:**\n"
            f"ID: `{user['user_id']}`\n"
            f"Name: {user.get('first_name', 'N/A')}\n"
            f"Username: @{user.get('username', 'N/A')}\n"
            f"Joined: {user.get('join_date', 'Unknown')[:10]}\n\n"
            f"💰 **Financial**\n"
            f"Balance: ₹{user.get('balance', 0):.2f}\n"
            f"Total Earned: ₹{user.get('total_earned', 0):.2f}\n\n"
            f"👥 **Referrals**\n"
            f"Total: {user.get('total_refs', 0)}\n"
            f"Active: {user.get('active_refs', 0)}\n"
            f"Pending: {user.get('pending_refs', 0)}\n\n"
            f"📊 **Activity**\n"
            f"Searches: {user.get('total_searches', 0)}\n"
            f"Last Active: {user.get('last_active', 'Unknown')[:10]}"
        )
        
        keyboard = [
            [InlineKeyboardButton("🗑️ MANAGE USER", callback_data=f"manage_user_{target_id}")],
            [InlineKeyboardButton("◀️ BACK", callback_data="admin_search_user")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    # ========== SUPPORT MESSAGES ==========
    
    async def support_messages_menu(self, query, context):
        """Show pending support messages"""
        try:
            messages = self.db.get_pending_support_messages(10)
            
            if not messages:
                await query.edit_message_text(
                    "📩 **No pending support messages.**",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")
                    ]])
                )
                return
            
            text = f"📩 **Pending Support Messages** ({len(messages)})\n\n"
            
            for i, msg in enumerate(messages[:5], 1):
                text += f"{i}. {msg.get('user_name', 'User')} (ID: `{msg['user_id']}`)\n"
                text += f"   Message: {msg['message'][:50]}...\n"
                text += f"   Time: {msg['timestamp'][:16]}\n\n"
            
            keyboard = []
            for msg in messages[:3]:
                keyboard.append([
                    InlineKeyboardButton(f"📩 View {msg['user_name'][:10]}", callback_data=f"view_support_{msg['_id']}")
                ])
            
            keyboard.append([InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")])
            
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            
        except Exception as e:
            logger.error(f"Support menu error: {e}")
            await query.edit_message_text(
                "❌ Error loading support messages.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")
                ]])
            )
    
    async def view_support_message(self, query, context, msg_id):
        """View single support message"""
        try:
            msg = self.db.issues.find_one({'_id': ObjectId(msg_id)})
        except:
            msg = None
        
        if not msg:
            await query.edit_message_text(
                "❌ Message not found or may have been deleted.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ BACK", callback_data="admin_support")
                ]])
            )
            return
        
        user = self.db.get_user(msg['user_id'])
        user_name = user.get('first_name', 'Unknown') if user else 'Unknown'
        
        text = (
            f"📩 **Support Message**\n\n"
            f"**From:** {user_name} (ID: `{msg['user_id']}`)\n"
            f"**Time:** {msg['timestamp'][:16]}\n"
            f"**Status:** {msg['status']}\n\n"
            f"**Message:**\n{msg['message']}\n\n"
        )
        
        if msg.get('admin_reply'):
            text += f"**Your Reply:**\n{msg['admin_reply']}\n"
            text += f"**Replied:** {msg.get('reply_date', '')[:16]}\n"
        
        keyboard = [
            [InlineKeyboardButton("✏️ REPLY", callback_data=f"reply_support_{msg_id}")],
            [InlineKeyboardButton("👤 VIEW USER", callback_data=f"user_details_{msg['user_id']}")],
            [InlineKeyboardButton("◀️ BACK", callback_data="admin_support")]
        ]
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def process_support_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE, msg_id):
        """Process reply to support message"""
        try:
            reply_text = update.message.text.strip()
            
            msg = self.db.issues.find_one({'_id': ObjectId(msg_id)})
            if not msg:
                await update.message.reply_text("❌ Message not found")
                return
            
            self.db.mark_support_replied(msg_id, update.effective_user.id, reply_text)
            
            try:
                await context.bot.send_message(
                    chat_id=msg['user_id'],
                    text=(
                        f"📩 **Reply to your support message**\n\n"
                        f"**Your message:**\n{msg['message']}\n\n"
                        f"**Admin Reply:**\n{reply_text}\n\n"
                        f"Thank you for contacting support!"
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
                
                await update.message.reply_text("✅ Reply sent to user!")
                
            except Exception as e:
                logger.error(f"Could not send reply to user: {e}")
                await update.message.reply_text("⚠️ Reply saved but could not send to user (user may have blocked bot)")
            
            if self.config.LOG_CHANNEL_ID:
                try:
                    await context.bot.send_message(
                        chat_id=self.config.LOG_CHANNEL_ID,
                        text=(
                            f"📩 **Support Reply**\n\n"
                            f"User: {msg['user_name']} (ID: `{msg['user_id']}`)\n"
                            f"Reply: {reply_text}\n"
                            f"Admin: {update.effective_user.id}"
                        ),
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
            
        except Exception as e:
            logger.error(f"Support reply error: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
        
        context.user_data['admin_action'] = None
        context.user_data['replying_to'] = None
    
    # ========== BROADCAST ==========
    
    async def broadcast_menu(self, query, context):
        """Broadcast message menu"""
        context.user_data['admin_action'] = 'broadcast'
        
        keyboard = [[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        total_users = self.db.users.count_documents({})
        
        await query.edit_message_text(
            f"📢 **Broadcast Message**\n\n"
            f"Total users: {total_users}\n\n"
            f"Send me the message you want to broadcast.\n"
            f"(Text, photo, video, or any media)",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def process_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process broadcast message and track blocked/deleted users"""
        message = update.message
        users = list(self.db.users.find({}, {'user_id': 1}))
        
        sent = 0
        failed = 0
        blocked_users = []
        
        status_msg = await update.message.reply_text(f"📢 Broadcasting to {len(users)} users...")
        
        for i, user in enumerate(users):
            try:
                if message.text:
                    await context.bot.send_message(
                        chat_id=user['user_id'],
                        text=message.text
                    )
                elif message.photo:
                    await context.bot.send_photo(
                        chat_id=user['user_id'],
                        photo=message.photo[-1].file_id,
                        caption=message.caption
                    )
                elif message.video:
                    await context.bot.send_video(
                        chat_id=user['user_id'],
                        video=message.video.file_id,
                        caption=message.caption
                    )
                sent += 1
                
                if (i+1) % 100 == 0:
                    await status_msg.edit_text(f"📢 Progress: {i+1}/{len(users)} users...")
                    
                await asyncio.sleep(0.05)
            except Exception as e:
                failed += 1
                if "blocked" in str(e).lower() or "deactivated" in str(e).lower():
                    blocked_users.append(user['user_id'])
                    logger.info(f"User {user['user_id']} blocked/deleted bot")
                logger.error(f"Broadcast failed: {e}")
        
        context.user_data['last_broadcast_blocked'] = blocked_users
        
        keyboard = [[InlineKeyboardButton("🧹 CLEAR JUNK", callback_data="admin_clear_junk")]]
        
        await status_msg.edit_text(
            f"✅ **Broadcast Completed!**\n\n"
            f"📨 Sent: {sent}\n"
            f"❌ Failed: {failed}\n"
            f"🚫 Blocked/Deleted: {len(blocked_users)}\n\n"
            f"Click below to remove blocked/deleted users from database:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
        context.user_data['admin_action'] = None
        self.db.log_system_event('broadcast', f"Sent to {sent} users, {len(blocked_users)} blocked")
    
    async def clear_junk_users(self, query, context):
        """Remove blocked/deleted users from database"""
        blocked_users = context.user_data.get('last_broadcast_blocked', [])
        
        if not blocked_users:
            await query.edit_message_text(
                "❌ No blocked users found to clear.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")
                ]])
            )
            return
        
        await query.edit_message_text(f"🧹 Cleaning up {len(blocked_users)} users... Please wait.")
        
        deleted_count, failed_count = self.db.remove_blocked_users(blocked_users)
        
        await query.edit_message_text(
            f"🧹 **Cleanup Completed!**\n\n"
            f"✅ Removed: {deleted_count}\n"
            f"❌ Failed: {failed_count}\n\n"
            f"Total: {len(blocked_users)} users processed.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")
            ]])
        )
        
        context.user_data['last_broadcast_blocked'] = []
        self.db.log_system_event('cleanup', f"Removed {deleted_count} junk users, failed {failed_count}")
    
    # ========== WITHDRAWALS WITH 3 BUTTONS ==========
    
    async def withdrawals_menu(self, query, context):
        """Show pending withdrawals"""
        withdrawals = self.db.get_pending_withdrawals(10)
        
        if not withdrawals:
            await query.edit_message_text(
                "✅ No pending withdrawals.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")
                ]])
            )
            return
        
        text = f"💰 **Pending Withdrawals** ({len(withdrawals)})\n\n"
        
        for i, w in enumerate(withdrawals[:5], 1):
            user = self.db.get_user(w['user_id'])
            user_name = user.get('first_name', 'Unknown')[:10] if user else 'Unknown'
            text += f"{i}. {user_name}: ₹{w['amount']} - {w['method']}\n"
            text += f"   ID: `{str(w['_id'])[-8:]}`\n\n"
        
        keyboard = []
        for w in withdrawals[:3]:
            keyboard.append([
                InlineKeyboardButton(f"✅ Approve {str(w['_id'])[-6:]}", callback_data=f"approve_{w['_id']}"),
                InlineKeyboardButton(f"❌ Reject {str(w['_id'])[-6:]}", callback_data=f"reject_{w['_id']}")
            ])
        
        keyboard.append([InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")])
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def view_withdrawal_details(self, query, context, withdrawal_id):
        """Show withdrawal details with action buttons"""
        try:
            withdrawal = self.db.withdrawals.find_one({'_id': ObjectId(withdrawal_id)})
        except:
            withdrawal = None
        
        if not withdrawal:
            await query.edit_message_text("❌ Withdrawal not found")
            return
        
        user = self.db.get_user(withdrawal['user_id'])
        user_name = user.get('first_name', 'Unknown') if user else 'Unknown'
        
        text = (
            f"📝 **WITHDRAWAL DETAILS**\n\n"
            f"**ID:** `{withdrawal_id[-8:]}`\n"
            f"**User:** {user_name} (ID: `{withdrawal['user_id']}`)\n"
            f"**Amount:** ₹{withdrawal['amount']}\n"
            f"**Method:** {withdrawal['method']}\n"
            f"**Details:** `{withdrawal.get('details', 'N/A')}`\n"
            f"**Status:** {withdrawal['status']}\n"
            f"**Requested:** {withdrawal['request_date'][:16]}\n"
        )
        
        if withdrawal.get('processed_date'):
            text += f"**Processed:** {withdrawal['processed_date'][:16]}\n"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ APPROVE", callback_data=f"approve_{withdrawal_id}"),
                InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{withdrawal_id}")
            ],
            [InlineKeyboardButton("👤 VIEW USER", callback_data=f"user_details_{withdrawal['user_id']}")],
            [InlineKeyboardButton("◀️ BACK", callback_data="admin_withdrawals")]
        ]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def approve_withdrawal(self, query, context, withdrawal_id):
        """Approve a withdrawal with owner notification (3 buttons)"""
        try:
            withdrawal = self.db.withdrawals.find_one({'_id': ObjectId(withdrawal_id)})
        except:
            withdrawal = None
        
        if not withdrawal:
            await query.edit_message_text("❌ Withdrawal not found")
            return
        
        success = self.db.approve_withdrawal(withdrawal_id, query.from_user.id)
        
        if not success:
            await query.edit_message_text("❌ Failed to approve withdrawal")
            return
        
        user = self.db.get_user(withdrawal['user_id'])
        user_name = user.get('first_name', 'Unknown') if user else 'Unknown'
        
        try:
            await context.bot.send_message(
                chat_id=withdrawal['user_id'],
                text=(
                    f"✅ **Withdrawal Approved!**\n\n"
                    f"Amount: ₹{withdrawal['amount']:.2f}\n"
                    f"Method: {withdrawal['method']}\n\n"
                    f"Your withdrawal has been approved and will be processed shortly."
                ),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Could not notify user: {e}")
        
        if self.config.LOG_CHANNEL_ID:
            try:
                log_text = (
                    f"📤 **WITHDRAWAL APPROVED**\n\n"
                    f"**User:** {user_name}\n"
                    f"**User ID:** `{withdrawal['user_id']}`\n"
                    f"**Amount:** ₹{withdrawal['amount']}\n"
                    f"**Method:** {withdrawal['method']}\n"
                    f"**Approved by:** Admin {query.from_user.id}"
                )
                
                await context.bot.send_message(
                    chat_id=self.config.LOG_CHANNEL_ID,
                    text=log_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Log channel error: {e}")
        
        keyboard = [
            [
                InlineKeyboardButton("👤 VIEW USER", callback_data=f"user_details_{withdrawal['user_id']}"),
                InlineKeyboardButton("📝 VIEW WD", callback_data=f"view_withdrawal_{withdrawal_id}")
            ],
            [InlineKeyboardButton("❌ CLOSE", callback_data="admin_close")]
        ]
        
        owner_text = (
            f"👑 **WITHDRAWAL APPROVED**\n\n"
            f"**User:** {user_name}\n"
            f"**Amount:** ₹{withdrawal['amount']}\n"
            f"**Method:** {withdrawal['method']}\n\n"
            f"✅ **Approved by Admin**"
        )
        
        for admin_id in self.config.ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=owner_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Could not notify admin {admin_id}: {e}")
        
        await query.edit_message_text(
            f"✅ Withdrawal ₹{withdrawal['amount']:.2f} approved!\n\n"
            f"✅ Owner notified with 3 buttons.\n"
            f"✅ Log channel updated.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ BACK TO WITHDRAWALS", callback_data="admin_withdrawals")
            ]])
        )
    
    async def reject_withdrawal(self, query, context, withdrawal_id):
        """Reject a withdrawal with owner notification (3 buttons)"""
        try:
            withdrawal = self.db.withdrawals.find_one({'_id': ObjectId(withdrawal_id)})
        except:
            withdrawal = None
        
        if not withdrawal:
            await query.edit_message_text("❌ Withdrawal not found")
            return
        
        success = self.db.reject_withdrawal(withdrawal_id, query.from_user.id)
        
        if not success:
            await query.edit_message_text("❌ Failed to reject withdrawal")
            return
        
        user = self.db.get_user(withdrawal['user_id'])
        user_name = user.get('first_name', 'Unknown') if user else 'Unknown'
        
        try:
            await context.bot.send_message(
                chat_id=withdrawal['user_id'],
                text=(
                    f"❌ **Withdrawal Rejected**\n\n"
                    f"Amount: ₹{withdrawal['amount']:.2f}\n"
                    f"Method: {withdrawal['method']}\n\n"
                    f"Your withdrawal was rejected. Amount refunded.\n"
                    f"Contact support: {self.config.SUPPORT_USERNAME}"
                ),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Could not notify user: {e}")
        
        if self.config.LOG_CHANNEL_ID:
            try:
                log_text = (
                    f"📤 **WITHDRAWAL REJECTED**\n\n"
                    f"**User:** {user_name}\n"
                    f"**User ID:** `{withdrawal['user_id']}`\n"
                    f"**Amount:** ₹{withdrawal['amount']}\n"
                    f"**Method:** {withdrawal['method']}\n"
                    f"**Rejected by:** Admin {query.from_user.id}"
                )
                
                await context.bot.send_message(
                    chat_id=self.config.LOG_CHANNEL_ID,
                    text=log_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Log channel error: {e}")
        
        keyboard = [
            [
                InlineKeyboardButton("👤 VIEW USER", callback_data=f"user_details_{withdrawal['user_id']}"),
                InlineKeyboardButton("📝 VIEW WD", callback_data=f"view_withdrawal_{withdrawal_id}")
            ],
            [InlineKeyboardButton("❌ CLOSE", callback_data="admin_close")]
        ]
        
        owner_text = (
            f"👑 **WITHDRAWAL REJECTED**\n\n"
            f"**User:** {user_name}\n"
            f"**Amount:** ₹{withdrawal['amount']}\n"
            f"**Method:** {withdrawal['method']}\n\n"
            f"❌ **Rejected by Admin**\n"
            f"Amount refunded to user."
        )
        
        for admin_id in self.config.ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=owner_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Could not notify admin {admin_id}: {e}")
        
        await query.edit_message_text(
            f"❌ Withdrawal ₹{withdrawal['amount']:.2f} rejected!\n\n"
            f"✅ Owner notified with 3 buttons.\n"
            f"✅ Log channel updated.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ BACK TO WITHDRAWALS", callback_data="admin_withdrawals")
            ]])
        )
    
    # ========== BACK TO ADMIN ==========
    
    async def back_to_admin(self, query, context):
        """Return to main admin panel"""
        context.user_data['admin_action'] = None
        context.user_data['replying_to'] = None
        context.user_data['managing_user'] = None
        
        total_users = self.db.users.count_documents({})
        pending = self.db.withdrawals.count_documents({'status': 'pending'})
        pending_support = self.db.issues.count_documents({'status': 'pending'})
        
        keyboard = [
            [InlineKeyboardButton("🔍 SEARCH USER", callback_data="admin_search_user")],
            [InlineKeyboardButton("📢 BROADCAST", callback_data="admin_broadcast")],
            [InlineKeyboardButton("💰 WITHDRAWALS", callback_data="admin_withdrawals")],
            [InlineKeyboardButton("📩 SUPPORT MESSAGES", callback_data="admin_support")],
            [InlineKeyboardButton("🗑️ USER DATA MANAGER", callback_data="admin_data_manager")],
            [InlineKeyboardButton("❌ CLOSE", callback_data="admin_close")]
        ]
        
        text = (
            "👑 **Admin Panel**\n\n"
            f"📊 Users: {total_users} | Pending WD: {pending} | Support: {pending_support}"
        )
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== HANDLE ADMIN MESSAGES ==========
    
    async def handle_admin_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin messages"""
        user_id = update.effective_user.id
        
        if user_id not in self.config.ADMIN_IDS:
            return
        
        action = context.user_data.get('admin_action')
        
        if action == 'broadcast':
            await self.process_broadcast(update, context)
        
        elif action == 'search_user':
            await self.process_search_user(update, context)
        
        elif action == 'data_manager':
            await self.process_data_manager(update, context)
        
        elif action and action.startswith('manage_'):
            try:
                target_id = int(action.replace('manage_', ''))
                await self.process_user_management(update, context, target_id)
            except Exception as e:
                logger.error(f"User management error: {e}")
                await update.message.reply_text("❌ Error processing command")
        
        elif action and action.startswith('reply_support_'):
            try:
                msg_id = action.replace('reply_support_', '')
                await self.process_support_reply(update, context, msg_id)
            except Exception as e:
                logger.error(f"Support reply error: {e}")
                await update.message.reply_text("❌ Error processing reply")
