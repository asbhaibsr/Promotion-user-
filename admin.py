# ═══════════════════════════════════════════════════════════
# EarnZone / FilmyFund — Telegram Mini App
# Owner   : @asbhaibsr
# Channel : @asbhai_bsr
# Contact : https://t.me/asbhaibsr
# ⚠️  Unauthorized modification or redistribution prohibited.
# © 2025 @asbhaibsr — All Rights Reserved
# ═══════════════════════════════════════════════════════════

# ===== admin.py (FULLY FIXED) =====
# Fix: User data manager now works properly
# Fix: earning/all/+/- commands all work
# Fix: handle_admin_message properly routes all actions

import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from bson.objectid import ObjectId

logger = logging.getLogger(__name__)

class AdminHandlers:
    def __init__(self, config, db, bot=None):
        self.config = config
        self.db = db
        self.bot = bot
        logger.info("✅ Admin handlers initialized")

    # ========== MAIN ADMIN PANEL ==========

    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.config.ADMIN_IDS:
            await update.message.reply_text("❌ Unauthorized.")
            return

        total_users = self.db.users.count_documents({})
        pending_wd = self.db.withdrawals.count_documents({'status': 'pending'})
        pending_sup = self.db.issues.count_documents({'status': 'pending'}) if hasattr(self.db, 'issues') else 0

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
            f"📊 Users: {total_users} | WD: {pending_wd} | Support: {pending_sup}\n\n"
            "Select an option:"
        )
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

    # ========== CALLBACK HANDLER ==========

    async def handle_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data
        user_id = update.effective_user.id

        # Allow ALL users to handle broadcast OK/Delete buttons
        if data in ("bc_ok", "bc_delete"):
            if data == "bc_ok":
                try:
                    await query.edit_message_reply_markup(reply_markup=None)
                except:
                    pass
            else:
                try:
                    await query.message.delete()
                except:
                    try:
                        await query.edit_message_text("🗑️ Deleted")
                    except:
                        pass
            return

        if user_id not in self.config.ADMIN_IDS:
            await query.edit_message_text("❌ Unauthorized")
            return

        logger.info(f"Admin callback: {data} from {user_id}")

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
        elif data.startswith("user_details_"):
            try:
                target_id = int(data.replace("user_details_", ""))
                await self.show_user_details(query, context, target_id)
            except Exception as e:
                logger.error(f"user_details error: {e}")
        elif data.startswith("manage_user_"):
            try:
                target_id = int(data.replace("manage_user_", ""))
                context.user_data['managing_user'] = target_id
                context.user_data['admin_action'] = f"manage_{target_id}"
                await self.user_management_menu(query, context, target_id)
            except Exception as e:
                logger.error(f"manage_user error: {e}")
        elif data.startswith("view_support_"):
            msg_id = data.replace("view_support_", "")
            await self.view_support_message(query, context, msg_id)
        elif data.startswith("reply_support_"):
            msg_id = data.replace("reply_support_", "")
            context.user_data['replying_to'] = msg_id
            context.user_data['admin_action'] = f"reply_support_{msg_id}"
            await query.edit_message_text(
                "📝 **Reply likhiye:**",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ BACK", callback_data="admin_support")]])
            )
        elif data.startswith("approve_"):
            await self.approve_withdrawal(query, context, data.replace("approve_", ""))
        elif data.startswith("reject_"):
            await self.reject_withdrawal(query, context, data.replace("reject_", ""))
        elif data.startswith("view_withdrawal_"):
            await self.view_withdrawal_details(query, context, data.replace("view_withdrawal_", ""))
        elif data == "bc_ok":
            # User clicked OK on broadcast — just remove buttons
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except:
                pass
        elif data == "bc_delete":
            # User clicked Delete on broadcast — delete message
            try:
                await query.message.delete()
            except:
                try:
                    await query.edit_message_text("🗑️ Message deleted")
                except:
                    pass
        elif data.startswith("verify_passes_"):
            await self.verify_pass_request(query, context, data.replace("verify_passes_", ""), 'verify')
        elif data.startswith("reject_passes_"):
            await self.verify_pass_request(query, context, data.replace("reject_passes_", ""), 'reject')

    # ========== DATA MANAGER — MAIN ENTRY ==========

    async def data_manager_menu(self, query, context):
        """Step 1: Ask for user ID"""
        context.user_data['admin_action'] = 'data_manager'
        context.user_data['managing_user'] = None

        await query.edit_message_text(
            "🗑️ **User Data Manager**\n\n"
            "User ka **ID** bhejiye (numeric):\n\n"
            "Example: `1234567890`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]]),
            parse_mode=ParseMode.MARKDOWN
        )

    async def process_data_manager(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Step 2: Receive user ID, show management options"""
        try:
            target_id = int(update.message.text.strip())
            user = self.db.get_user(target_id)

            if not user:
                await update.message.reply_text(
                    f"❌ User `{target_id}` nahi mila.\nSahi ID daaliye.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            context.user_data['managing_user'] = target_id
            context.user_data['admin_action'] = f"manage_{target_id}"

            text = (
                f"👤 **User: {user.get('first_name','Unknown')}**\n"
                f"🆔 ID: `{target_id}`\n"
                f"💰 Balance: ₹{user.get('balance',0):.2f}\n"
                f"📊 Total Earned: ₹{user.get('total_earned',0):.2f}\n"
                f"👥 Active Refs: {user.get('active_refs',0)}\n\n"
                f"**Ab command bhejiye:**\n"
                f"• `earning` — Balance aur earnings reset (0 kar do)\n"
                f"• `all` — User ka **PURA DATA** delete karo\n"
                f"• `+100` — ₹100 add karo\n"
                f"• `-50` — ₹50 hatao"
            )

            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_data_manager")]]),
                parse_mode=ParseMode.MARKDOWN
            )

        except ValueError:
            await update.message.reply_text("❌ Sirf number daalo. Example: `1234567890`", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Data manager error: {e}")
            await update.message.reply_text(f"❌ Error: {e}")
        # Don't clear action here — we're waiting for next command

    async def user_management_menu(self, query, context, target_id, message=None):
        """Show user management options from callback"""
        user = self.db.get_user(target_id)
        if not user:
            txt = f"❌ User {target_id} nahi mila"
            if query:
                await query.edit_message_text(txt)
            elif message:
                await message.reply_text(txt)
            return

        context.user_data['admin_action'] = f"manage_{target_id}"
        context.user_data['managing_user'] = target_id

        text = (
            f"👤 **{user.get('first_name','Unknown')}** (ID: `{target_id}`)\n"
            f"💰 Balance: ₹{user.get('balance',0):.2f}\n"
            f"📊 Total Earned: ₹{user.get('total_earned',0):.2f}\n\n"
            f"**Command bhejiye:**\n"
            f"• `earning` — Balance reset to 0\n"
            f"• `all` — Pura data delete\n"
            f"• `+100` — Add ₹100\n"
            f"• `-50` — Remove ₹50"
        )

        kb = [[InlineKeyboardButton("◀️ BACK", callback_data="admin_data_manager")]]

        if query:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
        elif message:
            await message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

    # ========== PROCESS USER MANAGEMENT COMMANDS ==========

    async def process_user_management(self, update: Update, context: ContextTypes.DEFAULT_TYPE, target_id):
        """Process earning/all/+/- commands"""
        command = update.message.text.strip().lower()
        user = self.db.get_user(target_id)

        if not user:
            await update.message.reply_text(f"❌ User {target_id} nahi mila")
            context.user_data['admin_action'] = None
            return

        try:
            # ── CLEAR EARNINGS ────────────────────────────────
            if command == 'earning':
                old_bal = user.get('balance', 0)
                old_total = user.get('total_earned', 0)

                self.db.users.update_one(
                    {'user_id': target_id},
                    {'$set': {
                        'balance': 0.0,
                        'total_earned': 0.0,
                        'today_earned': 0.0
                    }}
                )
                self.db.transactions.delete_many({'user_id': target_id})
                self.db.user_cache.pop(f"user_{target_id}", None)

                await update.message.reply_text(
                    f"✅ **Earnings Cleared!**\n\n"
                    f"User: `{target_id}`\n"
                    f"Old Balance: ₹{old_bal:.2f} → ₹0.00\n"
                    f"Old Total: ₹{old_total:.2f} → ₹0.00\n"
                    f"Transactions: Deleted",
                    parse_mode=ParseMode.MARKDOWN
                )
                logger.info(f"Admin {update.effective_user.id} cleared earnings for {target_id}")

            # ── DELETE ALL DATA ───────────────────────────────
            elif command == 'all':
                collections_to_clear = [
                    (self.db.transactions, {'user_id': target_id}),
                    (self.db.withdrawals, {'user_id': target_id}),
                    (self.db.referrals, {'$or': [{'referrer_id': target_id}, {'referred_id': target_id}]}),
                    (self.db.daily_searches, {'user_id': target_id}),
                    (self.db.daily_bonus, {'user_id': target_id}),
                    (self.db.missions, {'user_id': target_id}),
                    (self.db.live_activity, {'user_id': target_id}),
                ]
                # Also try optional collections
                optional = ['search_logs', 'daily_claims', 'issues', 'game_states', 'channel_joins']
                for col_name in optional:
                    if hasattr(self.db, col_name):
                        col = getattr(self.db, col_name)
                        try:
                            col.delete_many({'user_id': target_id})
                        except:
                            pass

                deleted_all = 0
                for col, query_filter in collections_to_clear:
                    try:
                        r = col.delete_many(query_filter)
                        deleted_all += r.deleted_count
                    except Exception as e:
                        logger.error(f"Delete error for {col.name}: {e}")

                # Finally delete the user document
                self.db.users.delete_one({'user_id': target_id})
                self.db.user_cache.pop(f"user_{target_id}", None)

                # Decrement referrer's counts
                referrer_id = user.get('referrer_id')
                if referrer_id:
                    try:
                        was_active = user.get('active_refs', 0) > 0
                        self.db.users.update_one(
                            {'user_id': referrer_id},
                            {'$inc': {
                                'total_refs': -1,
                                'active_refs': -1 if was_active else 0,
                                'pending_refs': 0 if was_active else -1
                            }}
                        )
                        self.db.user_cache.pop(f"user_{referrer_id}", None)
                    except:
                        pass

                await update.message.reply_text(
                    f"✅ **ALL DATA DELETED!**\n\n"
                    f"User `{target_id}` ka pura data remove ho gaya.\n"
                    f"Records deleted: {deleted_all + 1}",
                    parse_mode=ParseMode.MARKDOWN
                )
                logger.info(f"Admin {update.effective_user.id} deleted ALL data for {target_id}")

            # ── ADD MONEY ─────────────────────────────────────
            elif command.startswith('+'):
                amount = float(command[1:])
                if amount <= 0 or amount > 100000:
                    await update.message.reply_text("❌ Invalid amount (1-100000)")
                    return
                old_bal = user.get('balance', 0)
                self.db.add_balance(target_id, amount, f"Admin added ₹{amount}")
                await update.message.reply_text(
                    f"✅ **₹{amount:.2f} Add Ho Gaya!**\n\n"
                    f"User: `{target_id}`\n"
                    f"Old: ₹{old_bal:.2f} → New: ₹{old_bal+amount:.2f}",
                    parse_mode=ParseMode.MARKDOWN
                )
                try:
                    await context.bot.send_message(
                        chat_id=target_id,
                        text=f"🎉 Admin ne aapke account mein ₹{amount:.2f} add kiye!"
                    )
                except:
                    pass

            # ── REMOVE MONEY ──────────────────────────────────
            elif command.startswith('-'):
                amount = float(command[1:])
                if amount <= 0:
                    await update.message.reply_text("❌ Invalid amount")
                    return
                old_bal = user.get('balance', 0)
                if old_bal < amount:
                    await update.message.reply_text(
                        f"❌ User ke paas sirf ₹{old_bal:.2f} hai.\n"
                        f"Itna nahi hata sakte: ₹{amount:.2f}"
                    )
                    return
                self.db.users.update_one({'user_id': target_id}, {'$inc': {'balance': -amount}})
                self.db.add_transaction(target_id, 'admin_remove', -amount, f"Admin removed ₹{amount}")
                self.db.user_cache.pop(f"user_{target_id}", None)
                await update.message.reply_text(
                    f"✅ **₹{amount:.2f} Remove Ho Gaya!**\n\n"
                    f"User: `{target_id}`\n"
                    f"Old: ₹{old_bal:.2f} → New: ₹{old_bal-amount:.2f}",
                    parse_mode=ParseMode.MARKDOWN
                )
                try:
                    await context.bot.send_message(
                        chat_id=target_id,
                        text=f"⚠️ Admin ne aapke account se ₹{amount:.2f} hataye."
                    )
                except:
                    pass

            else:
                await update.message.reply_text(
                    "❌ **Invalid Command!**\n\n"
                    "Use:\n"
                    "• `earning` — earnings clear karo\n"
                    "• `all` — pura data delete\n"
                    "• `+100` — ₹100 add\n"
                    "• `-50` — ₹50 remove",
                    parse_mode=ParseMode.MARKDOWN
                )
                return  # Don't clear action — let them try again

        except ValueError:
            await update.message.reply_text("❌ Invalid amount. Example: `+100` ya `-50`", parse_mode=ParseMode.MARKDOWN)
            return
        except Exception as e:
            logger.error(f"User management error: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

        # Clear action after successful command
        context.user_data['admin_action'] = None
        context.user_data['managing_user'] = None

    # ========== SEARCH USER ==========

    async def search_user_prompt(self, query, context):
        context.user_data['admin_action'] = 'search_user'
        await query.edit_message_text(
            "🔍 **Search User**\n\nUser ID bhejiye:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]])
        )

    async def process_search_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            target_id = int(update.message.text.strip())
            user = self.db.get_user(target_id)
            if user:
                keyboard = [
                    [InlineKeyboardButton("👤 VIEW", callback_data=f"user_details_{target_id}"),
                     InlineKeyboardButton("🗑️ MANAGE", callback_data=f"manage_user_{target_id}")]
                ]
                await update.message.reply_text(
                    f"✅ User `{target_id}` mila!\nName: {user.get('first_name','?')}",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(f"❌ User `{target_id}` nahi mila", parse_mode=ParseMode.MARKDOWN)
        except ValueError:
            await update.message.reply_text("❌ Sirf numeric ID daalo")
        except Exception as e:
            logger.error(f"Search error: {e}")
            await update.message.reply_text(f"❌ Error: {e}")
        context.user_data['admin_action'] = None

    # ========== SHOW USER DETAILS ==========

    async def show_user_details(self, query, context, target_id):
        user = self.db.get_user(target_id)
        if not user:
            await query.edit_message_text(
                f"❌ User {target_id} nahi mila",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ BACK", callback_data="admin_search_user")]])
            )
            return

        join_d = user.get('join_date', 'Unknown')
        if join_d and len(join_d) > 10:
            join_d = join_d[:10]

        text = (
            f"👤 **User Details**\n\n"
            f"🆔 ID: `{user['user_id']}`\n"
            f"👤 Name: {user.get('first_name','N/A')}\n"
            f"📱 Username: @{user.get('username','N/A')}\n"
            f"📅 Joined: {join_d}\n\n"
            f"💰 Balance: ₹{user.get('balance',0):.2f}\n"
            f"📊 Total Earned: ₹{user.get('total_earned',0):.2f}\n"
            f"🎟️ Passes: {user.get('passes',0)}\n\n"
            f"👥 Total Refs: {user.get('total_refs',0)}\n"
            f"✅ Active: {user.get('active_refs',0)}\n"
            f"⏳ Pending: {user.get('pending_refs',0)}\n\n"
            f"🔍 Searches: {user.get('total_searches',0)}\n"
            f"🔥 Streak: {user.get('daily_streak',0)}\n"
            f"🚫 Blocked: {user.get('withdrawal_blocked',False)}"
        )

        keyboard = [
            [InlineKeyboardButton("🗑️ MANAGE", callback_data=f"manage_user_{target_id}")],
            [InlineKeyboardButton("◀️ BACK", callback_data="admin_search_user")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

    # ========== SUPPORT MESSAGES ==========

    async def support_messages_menu(self, query, context):
        try:
            col = self.db.issues if hasattr(self.db, 'issues') else self.db.support_messages
            messages = list(col.find({'status': 'pending'}).sort('timestamp', -1).limit(10))
            if not messages:
                await query.edit_message_text(
                    "✅ Koi pending support message nahi.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]])
                )
                return

            text = f"📩 **Pending Support** ({len(messages)})\n\n"
            keyboard = []
            for msg in messages[:5]:
                uid = msg.get('user_id', '?')
                uname = msg.get('user_name', msg.get('first_name', 'User'))[:10]
                preview = msg.get('message', '')[:30]
                text += f"• {uname} (`{uid}`): {preview}...\n"
                keyboard.append([InlineKeyboardButton(f"📩 {uname}", callback_data=f"view_support_{msg['_id']}")])

            keyboard.append([InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")])
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            logger.error(f"Support menu error: {e}")
            await query.edit_message_text(
                "❌ Support messages load nahi hue.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]])
            )

    async def view_support_message(self, query, context, msg_id):
        try:
            col = self.db.issues if hasattr(self.db, 'issues') else self.db.support_messages
            msg = col.find_one({'_id': ObjectId(msg_id)})
        except:
            msg = None

        if not msg:
            await query.edit_message_text(
                "❌ Message nahi mila.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ BACK", callback_data="admin_support")]])
            )
            return

        user = self.db.get_user(msg['user_id'])
        uname = user.get('first_name', 'Unknown') if user else 'Unknown'

        text = (
            f"📩 **Support Message**\n\n"
            f"From: {uname} (`{msg['user_id']}`)\n"
            f"Time: {str(msg.get('timestamp',''))[:16]}\n"
            f"Status: {msg.get('status','pending')}\n\n"
            f"**Message:**\n{msg.get('message','')}\n"
        )
        if msg.get('admin_reply'):
            text += f"\n**Reply:**\n{msg['admin_reply']}"

        keyboard = [
            [InlineKeyboardButton("✏️ REPLY", callback_data=f"reply_support_{msg_id}")],
            [InlineKeyboardButton("👤 USER", callback_data=f"user_details_{msg['user_id']}")],
            [InlineKeyboardButton("◀️ BACK", callback_data="admin_support")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

    async def process_support_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE, msg_id):
        try:
            reply_text = update.message.text.strip()
            col = self.db.issues if hasattr(self.db, 'issues') else self.db.support_messages
            msg = col.find_one({'_id': ObjectId(msg_id)})

            if not msg:
                await update.message.reply_text("❌ Message nahi mila")
                return

            col.update_one(
                {'_id': ObjectId(msg_id)},
                {'$set': {
                    'admin_reply': reply_text,
                    'status': 'replied',
                    'reply_date': datetime.now().isoformat(),
                    'replied_by': update.effective_user.id
                }}
            )

            try:
                await context.bot.send_message(
                    chat_id=msg['user_id'],
                    text=(
                        f"📩 **Support Reply**\n\n"
                        f"Aapka message:\n_{msg.get('message','')}_\n\n"
                        f"Admin ka reply:\n{reply_text}"
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
                await update.message.reply_text("✅ Reply bhej diya!")
            except Exception as e:
                await update.message.reply_text(f"⚠️ Reply save hua par user ko nahi gaya: {e}")

        except Exception as e:
            logger.error(f"Support reply error: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

        context.user_data['admin_action'] = None
        context.user_data['replying_to'] = None

    # ========== BROADCAST ==========

    async def broadcast_menu(self, query, context):
        context.user_data['admin_action'] = 'broadcast'
        total = self.db.users.count_documents({})
        await query.edit_message_text(
            f"📢 **Broadcast**\n\nTotal users: {total}\n\n📩 Aage jo bhi message bhejoge (text/photo/video/audio/sticker) — woh sab users ko broadcast ho jayega!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]]),
            parse_mode=ParseMode.MARKDOWN
        )

    async def process_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Full media broadcast: text, photo, video, audio, voice, document, sticker, animation"""
        if context.user_data.get('admin_action') != 'broadcast':
            return
        context.user_data.pop('admin_action', None)

        message = update.message
        users = list(self.db.users.find({}, {'user_id': 1}))
        sent = 0; failed = 0; blocked = []

        status_msg = await message.reply_text(
            f"📢 Broadcasting to {len(users)} users...\n⏳ Please wait..."
        )

        for i, u in enumerate(users):
            uid = u.get('user_id')
            if not uid:
                continue
            try:
                # Use copy_message with OK/Delete buttons
                bc_kb = InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ OK", callback_data="bc_ok"),
                    InlineKeyboardButton("🗑️ Delete", callback_data="bc_delete")
                ]])
                await context.bot.copy_message(
                    chat_id=uid,
                    from_chat_id=message.chat_id,
                    message_id=message.message_id,
                    reply_markup=bc_kb
                )
                sent += 1
                # Rate limit: Telegram allows ~30 msgs/sec
                if (i + 1) % 30 == 0:
                    await status_msg.edit_text(
                        f"📢 Progress: {i+1}/{len(users)} users\n✅ Sent: {sent} | ❌ Failed: {failed}"
                    )
                    await asyncio.sleep(1)  # 1 sec pause every 30 msgs
                else:
                    await asyncio.sleep(0.035)

            except Exception as ex:
                failed += 1
                err = str(ex).lower()
                if any(w in err for w in ['blocked', 'deactivated', 'not found', 'chat not found', 'user is deactivated']):
                    blocked.append(uid)

        # Final report
        await status_msg.edit_text(
            f"✅ **Broadcast Complete!**\n\n"
            f"📨 Sent: {sent}\n"
            f"❌ Failed: {failed}\n"
            f"🚫 Blocked/Deleted: {len(blocked)}\n"
            f"👥 Total: {len(users)}",
            parse_mode='Markdown'
        )

        # Save blocked users and auto-cleanup
        if blocked:
            context.user_data['last_broadcast_blocked'] = blocked
            logger.info(f"Broadcast blocked by {len(blocked)} users — auto-cleaning")
            try:
                deleted, _ = self.db.remove_blocked_users(blocked)
                await status_msg.edit_text(
                    f"✅ **Broadcast Complete!**\n\n"
                    f"📨 Sent: {sent}\n"
                    f"❌ Failed: {failed}\n"
                    f"🚫 Blocked: {len(blocked)}\n"
                    f"🧹 Auto-cleaned: {deleted} users removed\n"
                    f"👥 Total: {len(users)}",
                    parse_mode='Markdown'
                )
                context.user_data['last_broadcast_blocked'] = []
            except Exception as ce:
                logger.error(f"Auto-cleanup error: {ce}")


    async def clear_junk_users(self, query, context):
        blocked = context.user_data.get('last_broadcast_blocked', [])
        if not blocked:
            await query.edit_message_text(
                "❌ Koi blocked user nahi.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]])
            )
            return
        await query.edit_message_text(f"🧹 {len(blocked)} users clean kar rahe hain...")
        deleted, failed = self.db.remove_blocked_users(blocked)
        await query.edit_message_text(
            f"🧹 **Cleanup Done!**\n\n✅ Removed: {deleted}\n❌ Failed: {failed}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]])
        )
        context.user_data['last_broadcast_blocked'] = []

    # ========== WITHDRAWALS ==========

    async def withdrawals_menu(self, query, context):
        wds = self.db.get_pending_withdrawals(10)
        if not wds:
            await query.edit_message_text(
                "✅ Koi pending withdrawal nahi.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]])
            )
            return

        text = f"💰 **Pending Withdrawals** ({len(wds)})\n\n"
        keyboard = []
        for w in wds[:5]:
            user = self.db.get_user(w['user_id'])
            uname = user.get('first_name', 'User')[:8] if user else 'User'
            wid = str(w['_id'])
            text += f"• {uname}: ₹{w['amount']} ({w['method']})\n"
            keyboard.append([
                InlineKeyboardButton(f"✅ {uname}", callback_data=f"approve_{wid}"),
                InlineKeyboardButton(f"❌ Reject", callback_data=f"reject_{wid}"),
                InlineKeyboardButton(f"👁️ View", callback_data=f"view_withdrawal_{wid}")
            ])

        keyboard.append([InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

    async def view_withdrawal_details(self, query, context, wid):
        try:
            w = self.db.withdrawals.find_one({'_id': ObjectId(wid)})
        except:
            w = None
        if not w:
            await query.edit_message_text("❌ Withdrawal nahi mila")
            return

        user = self.db.get_user(w['user_id'])
        uname = user.get('first_name', 'Unknown') if user else 'Unknown'

        text = (
            f"💰 **Withdrawal Details**\n\n"
            f"👤 User: {uname} (`{w['user_id']}`)\n"
            f"💵 Amount: ₹{w['amount']}\n"
            f"📱 Method: {w['method']}\n"
            f"🏦 Details: `{w.get('details','N/A')}`\n"
            f"📅 Date: {str(w.get('request_date',''))[:16]}\n"
            f"🔖 Status: {w.get('status','pending')}"
        )
        keyboard = [
            [InlineKeyboardButton("✅ APPROVE", callback_data=f"approve_{wid}"),
             InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{wid}")],
            [InlineKeyboardButton("👤 USER", callback_data=f"user_details_{w['user_id']}")],
            [InlineKeyboardButton("◀️ BACK", callback_data="admin_withdrawals")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

    async def approve_withdrawal(self, query, context, wid):
        try:
            w = self.db.withdrawals.find_one({'_id': ObjectId(wid)})
        except:
            w = None
        if not w:
            await query.edit_message_text("❌ Withdrawal nahi mila")
            return

        success = self.db.approve_withdrawal(wid, query.from_user.id)
        if not success:
            await query.edit_message_text("❌ Approve nahi ho saka")
            return

        user = self.db.get_user(w['user_id'])
        uname = user.get('first_name', 'Unknown') if user else 'Unknown'

        try:
            await context.bot.send_message(
                chat_id=w['user_id'],
                text=f"✅ Aapka ₹{w['amount']:.2f} ka withdrawal approve ho gaya!\nMethod: {w['method']}"
            )
        except:
            pass

        if self.config.LOG_CHANNEL_ID:
            try:
                await context.bot.send_message(
                    chat_id=self.config.LOG_CHANNEL_ID,
                    text=f"✅ WITHDRAWAL APPROVED\nUser: {uname} (`{w['user_id']}`)\nAmount: ₹{w['amount']}\nMethod: {w['method']}",
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass

        await query.edit_message_text(
            f"✅ **Approved!** ₹{w['amount']:.2f} for {uname}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ BACK", callback_data="admin_withdrawals")]])
        )

    async def reject_withdrawal(self, query, context, wid):
        try:
            w = self.db.withdrawals.find_one({'_id': ObjectId(wid)})
        except:
            w = None
        if not w:
            await query.edit_message_text("❌ Withdrawal nahi mila")
            return

        success = self.db.reject_withdrawal(wid, query.from_user.id)
        if not success:
            await query.edit_message_text("❌ Reject nahi ho saka")
            return

        user = self.db.get_user(w['user_id'])
        uname = user.get('first_name', 'Unknown') if user else 'Unknown'

        try:
            await context.bot.send_message(
                chat_id=w['user_id'],
                text=f"❌ Aapka ₹{w['amount']:.2f} ka withdrawal reject ho gaya.\nAmount refund ho gaya.\nSupport: {self.config.SUPPORT_USERNAME}"
            )
        except:
            pass

        if self.config.LOG_CHANNEL_ID:
            try:
                await context.bot.send_message(
                    chat_id=self.config.LOG_CHANNEL_ID,
                    text=f"❌ WITHDRAWAL REJECTED\nUser: {uname} (`{w['user_id']}`)\nAmount: ₹{w['amount']}",
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass

        await query.edit_message_text(
            f"❌ **Rejected!** ₹{w['amount']:.2f} for {uname} — Refunded.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ BACK", callback_data="admin_withdrawals")]])
        )

    # ========== VERIFY PASS REQUEST ==========

    async def verify_pass_request(self, query, context, request_id, action):
        try:
            result = self.db.process_pass_request(request_id, action, query.from_user.id)
            if not result.get('success'):
                await query.edit_message_text(f"❌ {result.get('message','Error')}")
                return

            user_id = result.get('user_id')
            passes = result.get('passes', 0)

            if action == 'verify':
                msg_user = f"✅ **Passes Add Ho Gaye!**\n\n🎟️ {passes} passes aapke account mein add ho gaye!\nGame khelo aur paise kamao! 🎮"
                msg_admin = f"✅ **Pass Request VERIFIED!**\n{passes} passes added to user `{user_id}`"
            else:
                msg_user = f"❌ **Pass Request Reject Ho Gayi**\n\nTransaction verify nahi ho saka.\nSupport se contact karo: {self.config.SUPPORT_USERNAME}"
                msg_admin = f"❌ **Pass Request REJECTED** for user `{user_id}`"

            try:
                await context.bot.send_message(chat_id=user_id, text=msg_user, parse_mode='Markdown')
            except Exception as e:
                logger.error(f"User notify error: {e}")

            await query.edit_message_text(msg_admin, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Verify pass request error: {e}")
            await query.edit_message_text(f"❌ Error: {e}")

    # ========== BACK TO ADMIN ==========

    async def back_to_admin(self, query, context):
        context.user_data['admin_action'] = None
        context.user_data['replying_to'] = None
        context.user_data['managing_user'] = None

        total = self.db.users.count_documents({})
        pending = self.db.withdrawals.count_documents({'status': 'pending'})

        keyboard = [
            [InlineKeyboardButton("🔍 SEARCH USER", callback_data="admin_search_user")],
            [InlineKeyboardButton("📢 BROADCAST", callback_data="admin_broadcast")],
            [InlineKeyboardButton("💰 WITHDRAWALS", callback_data="admin_withdrawals")],
            [InlineKeyboardButton("📩 SUPPORT MESSAGES", callback_data="admin_support")],
            [InlineKeyboardButton("🗑️ USER DATA MANAGER", callback_data="admin_data_manager")],
            [InlineKeyboardButton("❌ CLOSE", callback_data="admin_close")]
        ]
        await query.edit_message_text(
            f"👑 **Admin Panel**\n\nUsers: {total} | Pending WD: {pending}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )

    # ========== MAIN MESSAGE ROUTER ==========

    async def handle_admin_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Route all admin text messages to correct handler"""
        user_id = update.effective_user.id
        if user_id not in self.config.ADMIN_IDS:
            return  # Not admin — ignore silently

        action = context.user_data.get('admin_action', '')

        if not action:
            return  # No active action

        msg_type = "text" if update.message.text else "media"
        logger.info(f"Admin message action: '{action}' from {user_id} ({msg_type})")

        if action == 'broadcast':
            await self.process_broadcast(update, context)

        elif action == 'search_user':
            await self.process_search_user(update, context)

        elif action == 'data_manager':
            # Got user ID — now show management options
            await self.process_data_manager(update, context)

        elif action.startswith('manage_'):
            try:
                target_id = int(action.replace('manage_', ''))
                await self.process_user_management(update, context, target_id)
            except (ValueError, Exception) as e:
                logger.error(f"manage_ routing error: {e}")
                await update.message.reply_text(f"❌ Error: {e}")

        elif action.startswith('reply_support_'):
            msg_id = action.replace('reply_support_', '')
            await self.process_support_reply(update, context, msg_id)

        else:
            logger.warning(f"Unknown admin action: {action}")
