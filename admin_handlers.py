# admin_handlers.py

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError, Forbidden, BadRequest, RetryAfter as FloodWait
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import asyncio
import hashlib
from io import BytesIO

from config import (
    USERS_COLLECTION, REFERRALS_COLLECTION, SETTINGS_COLLECTION, WITHDRAWALS_COLLECTION, BONUS_COLLECTION,
    DOLLAR_TO_INR, MESSAGES, ADMIN_ID, DB
)
from db_utils import (
    send_log_message, get_user_lang, get_bot_stats, 
    get_user_stats, admin_add_money, admin_clear_earnings, admin_delete_user, clear_junk_users
)

logger = logging.getLogger(__name__)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        if update.message:
            try:
                await update.message.reply_text("❌ Access Denied.")
            except:
                pass
        return

    context.user_data["admin_state"] = None
    context.user_data["stats_user_id"] = None 
    
    lang = await get_user_lang(user.id)
    message = "👑 <b>Admin Panel</b>\n\nSelect an action:"

    keyboard = [
        [InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_set_broadcast"),
         InlineKeyboardButton("💸 Pending Withdrawals", callback_data="admin_pending_withdrawals")],
        [InlineKeyboardButton("⚙️ Set Referral Rate", callback_data="admin_set_ref_rate"),
         InlineKeyboardButton("📊 Bot Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("📊 User Stats", callback_data="admin_user_stats"),
         InlineKeyboardButton("🗑️ Clear Junk Users", callback_data="admin_clear_junk")],
        [InlineKeyboardButton("📋 User Report (95 Referrals)", callback_data="admin_user_report")],
        # ====== NEW BONUS BUTTON ======
        [InlineKeyboardButton("🎁 Send Bonus to User", callback_data="admin_send_bonus")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message: 
        await update.message.reply_html(message, reply_markup=reply_markup)
    elif update.callback_query and update.callback_query.message:
        try:
            await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
        except TelegramError as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Error editing message in admin_panel: {e}")

async def back_to_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query:
        await query.answer()
    await admin_panel(update, context)

async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    
    if not query or not query.message:
        logger.warning("handle_admin_callbacks called without query or message.")
        return
        
    await query.answer()
    
    user = query.from_user
    if user.id != ADMIN_ID:
        await query.edit_message_text("❌ Access Denied.")
        return

    data = query.data.split("_")
    action = data[1]
    sub_action = data[2] if len(data) > 2 else None
    
    lang = await get_user_lang(user.id)
    
    if action == "pending" and sub_action == "withdrawals":
        await show_pending_withdrawals(update, context)
    elif action == "stats" and sub_action is None: 
        await show_bot_stats(update, context)
    elif action == "user" and sub_action == "stats":
        context.user_data["admin_state"] = "waiting_for_user_id_stats"
        await query.edit_message_text(
            "✍️ Please reply to this message with the User ID you want to check:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]])
        )
    elif action == "user" and sub_action == "report":
        context.user_data["admin_state"] = "waiting_for_user_id_report"
        await query.edit_message_text(
            "✍️ Please reply to this message with the User ID you want to generate report for:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]])
        )
    elif action == "clear" and sub_action == "junk":
        await query.edit_message_text("🗑️ Clearing junk users (is_approved=False)... Please wait.", parse_mode='HTML')
        result = await clear_junk_users()
        await query.edit_message_text(
            f"✅ Junk Data Cleared!\n\nUsers deleted: {result.get('users', 0)}\nReferral records cleared: {result.get('referrals', 0)}\nWithdrawals cleared: {result.get('withdrawals', 0)}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]),
            parse_mode='HTML'
        )
    elif action == "reply" and sub_action == "user":
        user_id_to_reply = data[3]
        context.user_data["admin_state"] = "admin_replying"
        context.user_data["reply_target_user_id"] = int(user_id_to_reply)
        
        await query.edit_message_text(
            f"✍️ <b>Reply to User {user_id_to_reply}</b>\n\nYour next message will be sent directly to this user. Send your reply now.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]),
            parse_mode='HTML'
        )
    elif action == "add" and sub_action == "money":
        user_id = context.user_data.get("stats_user_id")
        if not user_id:
            await query.edit_message_text("❌ Error: User ID not found in session. Please start over.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]))
            return
        context.user_data["admin_state"] = "waiting_for_add_money"
        await query.edit_message_text(
            f"💰 Please reply with the amount (in INR, e.g., 10.50 or 100+ or 50-) you want to add/deduct from user {user_id}:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]))
    elif action == "clear" and sub_action == "data":
        user_id = context.user_data.get("stats_user_id")
        if not user_id:
            await query.edit_message_text("❌ Error: User ID not found in session. Please start over.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]))
            return
        context.user_data["admin_state"] = "waiting_for_clear_data"
        await query.edit_message_text(
            "⚠️ Are you sure?\nTo clear only earnings, reply with: earning\nTo delete all user data, reply with: all",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]))
    elif action == "set": 
        if sub_action == "broadcast":
            context.user_data["admin_state"] = "waiting_for_broadcast_message"
            await query.edit_message_text("✍️ Enter the message you want to broadcast to all users:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]))
        elif sub_action == "ref" and data[3] == "rate":
             context.user_data["admin_state"] = "waiting_for_ref_rate"
             await query.edit_message_text("✍️ Enter the NEW Tier 1 Referral Rate in INR (e.g., 5.0 for ₹5 per referral):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]))
    # ====== NEW BONUS HANDLER ======
    elif action == "send" and sub_action == "bonus":
        context.user_data["admin_state"] = "waiting_for_bonus_user"
        await query.edit_message_text(
            "✍️ Please reply with the user's Telegram ID (number) who should receive the bonus:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]])
        )

async def show_bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message:
        return

    stats = await get_bot_stats()
    active_refs = REFERRALS_COLLECTION.count_documents({"is_active": True})
    pending_refs = REFERRALS_COLLECTION.count_documents({"is_active": False})

    message = f"📊 <b>Bot Stats</b>\n\n"
    message += f"Total Users: {stats['total_users']}\n"
    message += f"Approved Users: {stats['approved_users']}\n"
    message += f"Active Referrals: {active_refs}\n"
    message += f"Pending Referrals: {pending_refs}"
    
    keyboard = [[InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_pending")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

async def show_pending_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message: 
        return
        
    pending_withdrawals = WITHDRAWALS_COLLECTION.find({"status": "pending"}).sort("request_date", 1)
    
    message = "<b>💸 Pending Withdrawals</b>\n\n"
    keyboard = []
    
    count = WITHDRAWALS_COLLECTION.count_documents({"status": "pending"})

    if count == 0:
        message += "✅ No pending withdrawal requests."
    else:
        for request in pending_withdrawals:
            user_id = request["user_id"]
            amount = request["amount_inr"]
            username = request.get("username", "N/A")
            payment_details = request.get("payment_details", "N/A")

            message += f"👤 User: <code>{user_id}</code> (@{username})\n"
            message += f"💰 Amount: ₹{amount:.2f}\n"
            message += f"💳 Details: <b>{payment_details}</b>\n"
            
            if len(keyboard) < 5 * 2:
                keyboard.append([
                    InlineKeyboardButton(f"✅ Approve {user_id}", callback_data=f"approve_withdraw_{user_id}"),
                    InlineKeyboardButton(f"❌ Reject {user_id}", callback_data=f"reject_withdraw_{user_id}")
                ])
                keyboard.append([
                    InlineKeyboardButton(f"✉️ Reply to {user_id}", callback_data=f"admin_reply_user_{user_id}")
                ])
            
            message += "----\n"
                
        message += "\n(Showing up to 5 requests. Use buttons to process.)"

    keyboard.append([InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_pending")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

async def handle_withdrawal_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query: 
        return
        
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        if query.message:
            await query.edit_message_text("❌ Access Denied.")
        return
        
    parts = query.data.split("_")
    action = parts[0] 
    user_id_str = parts[2]
    user_id = int(user_id_str)
    
    withdrawal_request = WITHDRAWALS_COLLECTION.find_one_and_update(
        {"user_id": user_id, "status": "pending"},
        {"$set": {"status": action, "approved_date": datetime.now()}},
        return_document=True
    )

    if not withdrawal_request:
        if query.message:
            await query.edit_message_text(f"❌ Withdrawal request for user <code>{user_id}</code> not found or already processed.", parse_mode='HTML')
        return

    amount_inr = withdrawal_request["amount_inr"]
    
    if action == "approve":
        try:
            user_lang = await get_user_lang(user_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ Withdrawal Approved!\n\nYour withdrawal of ₹{amount_inr:.2f} has been approved. Payment will be processed within 24 hours.", 
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Could not notify user {user_id} of approval: {e}")
        
        if query.message:
            await query.edit_message_text(f"✅ Request for user <code>{user_id}</code> (₹{amount_inr:.2f}) APPROVED.", parse_mode='HTML')
        log_msg = f"💸 <b>Withdrawal Approved</b>\nAdmin: <code>{query.from_user.id}</code>\nUser: <code>{user_id}</code>\nAmount: ₹{amount_inr:.2f}"
    
    else:
        try:
            user_lang = await get_user_lang(user_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ Withdrawal Rejected!\n\nYour withdrawal of ₹{amount_inr:.2f} was rejected. Please contact admin for details.", 
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Could not notify user {user_id} of rejection: {e}")
        
        if query.message:
            await query.edit_message_text(f"❌ Request for user <code>{user_id}</code> (₹{amount_inr:.2f}) REJECTED.", parse_mode='HTML')
        log_msg = f"🚫 <b>Withdrawal Rejected</b>\nAdmin: <code>{query.from_user.id}</code>\nUser: <code>{user_id}</code>\nAmount: ₹{amount_inr:.2f}"

    await send_log_message(context, log_msg)
    
    if query.message and "Pending Withdrawals" in query.message.text: 
         await show_pending_withdrawals(update, context) 
    elif query.message:
         await back_to_admin_menu(update, context)

# ================== BONUS CONFIRMATION HANDLER ==================

async def handle_bonus_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """बोनस कन्फर्मेशन बटन हैंडलर"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Access Denied.")
        return
        
    parts = query.data.split("_")
    target_user_id = int(parts[2])
    bonus_amount = float(parts[3])
    
    # यूनिक कोड जनरेट करो
    unique_code = hashlib.md5(f"{target_user_id}_{bonus_amount}_{datetime.now().timestamp()}".encode()).hexdigest()[:8]
    
    # डेटाबेस में सेव करो (24 घंटे एक्सपायरी)
    BONUS_COLLECTION.insert_one({
        "code": unique_code,
        "target_user_id": target_user_id,
        "amount": bonus_amount,
        "created_by": query.from_user.id,
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(hours=24),
        "claimed_by": None,
        "claimed_at": None,
        "status": "active"
    })
    
    # क्लेम बटन बनाओ
    claim_button = InlineKeyboardButton(
        f"🎁 CLAIM ₹{bonus_amount:.2f} BONUS", 
        callback_data=f"claim_bonus_{unique_code}"
    )
    
    # यूजर को मैसेज भेजो
    try:
        expiry = (datetime.now() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M")
        
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"🎁 <b>SPECIAL BONUS OFFER!</b>\n\n"
                 f"Admin has sent you a special bonus of <b>₹{bonus_amount:.2f}</b>!\n\n"
                 f"⚠️ <b>FIRST COME, FIRST SERVED!</b>\n"
                 f"Only the first person to click the button below will receive this bonus.\n\n"
                 f"⏰ Expires: {expiry}",
            reply_markup=InlineKeyboardMarkup([[claim_button]]),
            parse_mode='HTML'
        )
        
        await query.edit_message_text(
            f"✅ <b>BONUS SENT!</b>\n\n"
            f"User <code>{target_user_id}</code> will receive a special bonus button.\n"
            f"Amount: ₹{bonus_amount:.2f}\n"
            f"Code: {unique_code}\n\n"
            f"The first person to click the button gets the money!",
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Failed to send bonus to user {target_user_id}: {e}")
        await query.edit_message_text(
            f"❌ Failed to send bonus.\n"
            f"Error: {str(e)[:100]}",
            parse_mode='HTML'
        )
    
    context.user_data["admin_state"] = None

# ================== PRIVATE TEXT HANDLER ==================

async def handle_private_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not update.message or not update.message.text:
        return
        
    lang = await get_user_lang(user.id)
    text = update.message.text

    # --- ADMIN LOGIC ---
    if user.id == ADMIN_ID:
        admin_state = context.user_data.get("admin_state")
        
        if admin_state is None and update.message.text.startswith('/admin'):
            await admin_panel(update, context)
            return
        
        if admin_state is None:
            return

        # STATE: waiting_for_user_id_stats
        if admin_state == "waiting_for_user_id_stats":
            try:
                user_id = int(text)
                stats = await get_user_stats(user_id)
                
                if not stats:
                    await update.message.reply_text(f"❌ User {user_id} not found in the database.")
                    context.user_data["admin_state"] = None
                    return

                context.user_data["stats_user_id"] = user_id
                context.user_data["admin_state"] = None

                # Get active referrals count
                active_refs = REFERRALS_COLLECTION.count_documents({"referrer_id": user_id, "is_active": True})
                pending_refs = REFERRALS_COLLECTION.count_documents({"referrer_id": user_id, "is_active": False})

                message = (
                    f"📊 <b>User Stats for {stats['full_name']}</b>\n\n"
                    f"<b>ID:</b> <code>{stats['user_id']}</code>\n"
                    f"<b>Username:</b> @{stats['username']}\n"
                    f"<b>Balance:</b> ₹{stats['earnings_inr']:.2f}\n"
                    f"<b>Active Referrals:</b> {active_refs}\n"
                    f"<b>Pending Referrals:</b> {pending_refs}\n"
                    f"<b>Total Referrals:</b> {stats['referrals']}"
                )
                
                keyboard = [
                    [InlineKeyboardButton("💰 Add Money", callback_data="admin_add_money"),
                     InlineKeyboardButton("🗑️ Clear Data", callback_data="admin_clear_data")],
                    [InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_pending")]
                ]
                await update.message.reply_html(message, reply_markup=InlineKeyboardMarkup(keyboard))
                
            except ValueError:
                await update.message.reply_text("❌ Invalid input. Please enter a valid User ID (numbers only).")
            except Exception as e:
                await update.message.reply_text(f"An error occurred: {e}")
                
        # STATE: waiting_for_user_id_report
        elif admin_state == "waiting_for_user_id_report":
            try:
                target_id = int(text)
                
                await update.message.reply_text(f"📊 Generating report for user {target_id}...")
                
                referrals = REFERRALS_COLLECTION.find({"referrer_id": target_id})
                
                report = f"📊 REPORT FOR USER: {target_id}\n"
                report += f"{'Referred ID':<15} | {'Active?':<10} | {'First Search':<15}\n"
                report += "-"*45 + "\n"
                
                active, pending = 0, 0
                for r in referrals:
                    status = "YES" if r.get("is_active", False) else "NO"
                    if status == "YES": 
                        active += 1 
                    else: 
                        pending += 1
                    first_search = r.get("first_search_date", "Not yet")
                    if isinstance(first_search, datetime):
                        first_search = first_search.strftime("%Y-%m-%d")
                    report += f"{r['referred_user_id']:<15} | {status:<10} | {first_search:<15}\n"
                    
                report += f"\n✅ Active: {active}\n⏳ Pending: {pending}"
                
                bio = BytesIO(report.encode())
                bio.name = f"Report_{target_id}.txt"
                await context.bot.send_document(
                    chat_id=user.id, 
                    document=bio, 
                    caption=f"User {target_id} Analysis"
                )
                
                context.user_data["admin_state"] = None
                
            except ValueError:
                await update.message.reply_text("❌ Invalid input. Please enter a valid User ID (numbers only).")
            except Exception as e:
                await update.message.reply_text(f"An error occurred: {e}")

        # STATE: waiting_for_add_money
        elif admin_state == "waiting_for_add_money":
            user_id = context.user_data.get("stats_user_id")
            if not user_id:
                await update.message.reply_text("Error: Session expired. Start over.")
                context.user_data["admin_state"] = None
                return
            
            text_input = text.strip()
            
            try:
                amount_to_process = 0.0
                operation = "add"

                if text_input.endswith("+"):
                    amount_to_process = float(text_input[:-1])
                    operation = "add"
                elif text_input.endswith("-"):
                    amount_to_process = float(text_input[:-1])
                    operation = "subtract"
                else:
                    amount_to_process = float(text_input)
                    operation = "add"

                current_stats = await get_user_stats(user_id)
                current_balance_inr = current_stats['earnings_inr']

                if operation == "add":
                    new_balance = await admin_add_money(user_id, amount_to_process)
                    msg = f"✅ Added ₹{amount_to_process:.2f}.\nOld Balance: ₹{current_balance_inr:.2f}\n🆕 New Balance: ₹{new_balance:.2f}"
                    log_text = f"ADMIN ADD: ₹{amount_to_process} to User {user_id}"
                
                elif operation == "subtract":
                    new_balance = await admin_add_money(user_id, -amount_to_process)
                    msg = f"🔻 Deducted ₹{amount_to_process:.2f}.\nOld Balance: ₹{current_balance_inr:.2f}\n🆕 New Balance: ₹{new_balance:.2f}"
                    log_text = f"ADMIN DEDUCT: ₹{amount_to_process} from User {user_id}"

                await update.message.reply_text(msg)
                await send_log_message(context, log_text)
                
            except ValueError:
                await update.message.reply_text("❌ Invalid format.\nUse 100+ to add\nUse 50- to deduct.")
            
            context.user_data["admin_state"] = None
            context.user_data["stats_user_id"] = None

        # STATE: waiting_for_clear_data
        elif admin_state == "waiting_for_clear_data":
            user_id = context.user_data.get("stats_user_id")
            choice = text.strip().lower()

            if not user_id:
                await update.message.reply_text("Error: Session expired. Please start over from /admin.")
                context.user_data["admin_state"] = None
                return
            
            if choice == "earning":
                await admin_clear_earnings(user_id)
                await update.message.reply_text(f"✅ Successfully cleared earnings for user {user_id}. New balance: ₹0.00")
                await send_log_message(context, f"ADMIN: <code>{user.id}</code> cleared earnings for user <code>{user_id}</code>.")
                
            elif choice == "all":
                await admin_delete_user(user_id)
                await update.message.reply_text(f"✅ Successfully deleted all data for user {user_id}.")
                await send_log_message(context, f"ADMIN: <code>{user.id}</code> DELETED ALL data for user <code>{user_id}</code>.")
                
            else:
                await update.message.reply_text("❌ Invalid input. Please reply with 'all' or 'earning'.")
                return

            context.user_data["admin_state"] = None
            context.user_data["stats_user_id"] = None
            
        # STATE: admin_replying
        elif admin_state == "admin_replying":
            target_user_id = context.user_data.get("reply_target_user_id")
            reply_message = update.message.text
            
            if not target_user_id:
                await update.message.reply_text("Error: Session expired (user ID not found). State cleared.")
            else:
                try:
                    await context.bot.send_message(
                        chat_id=target_user_id, 
                        text=f"🔔 <b>A Message from Admin:</b>\n\n{reply_message}",
                        parse_mode='HTML'
                    )
                    await update.message.reply_text(f"✅ Message successfully sent to user {target_user_id}.")
                except Exception as e:
                    logger.error(f"Admin reply failed to user {target_user_id}: {e}")
                    await update.message.reply_text(f"❌ Failed to send message to user {target_user_id}. They may have blocked the bot.")
            
            context.user_data["admin_state"] = None
            context.user_data["reply_target_user_id"] = None

        # STATE: waiting_for_broadcast_message (ADVANCED - CHUNKED)
        elif admin_state == "waiting_for_broadcast_message":
            broadcast_text = text
            success_count = 0
            fail_count = 0
            
            status_message = await update.message.reply_text(
                "📢 <b>Starting ADVANCED broadcast...</b>\n\n"
                "This will send messages in chunks of 100 users with delays to avoid limits.\n"
                "Progress will be updated every 100 users.",
                parse_mode='HTML'
            )
            
            all_users = list(USERS_COLLECTION.find({"is_approved": True}, {"user_id": 1}))
            total_users = len(all_users)
            
            if total_users == 0:
                await status_message.edit_text("❌ No approved users found.")
                context.user_data["admin_state"] = None
                return
            
            await status_message.edit_text(
                f"📢 Broadcast started...\n"
                f"Total users: {total_users}\n"
                f"Sending in chunks of 100 with 3-second pauses..."
            )
            
            chunk_size = 100
            for i in range(0, total_users, chunk_size):
                chunk = all_users[i:i+chunk_size]
                chunk_success = 0
                chunk_fail = 0
                
                for user_data in chunk:
                    user_id = user_data["user_id"]
                    
                    try:
                        await context.bot.send_message(
                            user_id, 
                            broadcast_text, 
                            parse_mode='HTML', 
                            disable_web_page_preview=True
                        )
                        chunk_success += 1
                        success_count += 1
                        
                        await asyncio.sleep(0.1)
                        
                    except FloodWait as e:
                        wait_time = e.retry_after + 2
                        logger.warning(f"FloodWait: Waiting {wait_time}s")
                        
                        await status_message.edit_text(
                            f"⚠️ Rate limit hit! Waiting {wait_time}s...\n"
                            f"Progress: {i}/{total_users}\n"
                            f"Success: {success_count} | Fail: {fail_count}"
                        )
                        
                        await asyncio.sleep(wait_time)
                        
                        try:
                            await context.bot.send_message(
                                user_id, 
                                broadcast_text, 
                                parse_mode='HTML', 
                                disable_web_page_preview=True
                            )
                            chunk_success += 1
                            success_count += 1
                        except Exception:
                            chunk_fail += 1
                            fail_count += 1
                            
                    except (Forbidden, BadRequest) as e:
                        chunk_fail += 1
                        fail_count += 1
                        USERS_COLLECTION.update_one(
                            {"user_id": user_id}, 
                            {"$set": {"is_approved": False}}
                        )
                        
                    except Exception as e:
                        chunk_fail += 1
                        fail_count += 1
                        logger.error(f"Unknown error for {user_id}: {e}")
                
                progress_pct = min(100, int((i + chunk_size) / total_users * 100))
                
                await status_message.edit_text(
                    f"📢 Broadcast in progress...\n"
                    f"📊 Progress: {progress_pct}% ({min(i+chunk_size, total_users)}/{total_users})\n"
                    f"✅ Success: {success_count}\n"
                    f"❌ Failed: {fail_count}\n\n"
                    f"⏸️ Pausing for 3 seconds before next chunk..."
                )
                
                context.bot_data["broadcast_checkpoint"] = {
                    "last_index": i + chunk_size,
                    "success": success_count,
                    "fail": fail_count
                }
                
                await asyncio.sleep(3)
            
            await status_message.edit_text(
                f"✅ <b>BROADCAST COMPLETE!</b>\n\n"
                f"📊 Final Statistics:\n"
                f"👥 Total Users: {total_users}\n"
                f"✅ Successful: {success_count}\n"
                f"❌ Failed: {fail_count}\n"
                f"📈 Success Rate: {(success_count/total_users*100):.1f}%\n\n"
                f"Unapproved users (blocked) were automatically marked.",
                parse_mode='HTML'
            )
            
            if "broadcast_checkpoint" in context.bot_data:
                del context.bot_data["broadcast_checkpoint"]
            
            context.user_data["admin_state"] = None
            await send_log_message(
                context,
                f"📢 <b>Broadcast Completed</b>\n"
                f"Total: {total_users}\n"
                f"Success: {success_count}\n"
                f"Fail: {fail_count}"
            )

        # STATE: waiting_for_ref_rate
        elif admin_state == "waiting_for_ref_rate":
            try:
                new_rate = float(text)
                if new_rate <= 0:
                     raise ValueError
                
                SETTINGS_COLLECTION.update_one(
                    {"_id": "referral_rate"}, 
                    {"$set": {"rate_inr": new_rate}},
                    upsert=True
                )
                
                context.user_data["admin_state"] = None
                await update.message.reply_text(f"✅ Referral rate successfully updated to ₹{new_rate:.2f} per referral.")
                
            except ValueError:
                await update.message.reply_text("❌ Invalid input. Please enter a valid number for the new rate (e.g., 5.0).")

        # ====== NEW BONUS STATES ======
        elif admin_state == "waiting_for_bonus_user":
            try:
                bonus_user_id = int(text.strip())
                context.user_data["bonus_target_user"] = bonus_user_id
                context.user_data["admin_state"] = "waiting_for_bonus_amount"
                
                user_exists = USERS_COLLECTION.find_one({"user_id": bonus_user_id})
                if user_exists:
                    user_name = user_exists.get("full_name", "Unknown")
                    await update.message.reply_text(
                        f"✅ User found: {user_name} (ID: {bonus_user_id})\n\n"
                        f"Now enter the bonus amount in INR (e.g., 10, 50, 100):"
                    )
                else:
                    await update.message.reply_text(
                        f"⚠️ User ID {bonus_user_id} not found in database.\n"
                        f"Enter amount anyway? (They will receive when they start bot)\n\n"
                        f"Send amount or /cancel"
                    )
            except ValueError:
                await update.message.reply_text("❌ Invalid User ID. Please enter numbers only.")
                
        elif admin_state == "waiting_for_bonus_amount":
            try:
                bonus_amount = float(text.strip())
                target_user_id = context.user_data.get("bonus_target_user")
                
                if not target_user_id:
                    await update.message.reply_text("❌ Session expired. Start over.")
                    context.user_data["admin_state"] = None
                    return
                    
                context.user_data["bonus_amount"] = bonus_amount
                context.user_data["admin_state"] = "waiting_for_bonus_confirm"
                
                user_data = USERS_COLLECTION.find_one({"user_id": target_user_id})
                user_name = user_data.get("full_name", "Unknown") if user_data else "Unknown (Not in DB)"
                
                keyboard = [
                    [InlineKeyboardButton("✅ CONFIRM & SEND BONUS", callback_data=f"confirm_bonus_{target_user_id}_{bonus_amount}")],
                    [InlineKeyboardButton("❌ Cancel", callback_data="admin_pending")]
                ]
                
                await update.message.reply_text(
                    f"📋 <b>BONUS CONFIRMATION</b>\n\n"
                    f"👤 User: {user_name}\n"
                    f"🆔 ID: <code>{target_user_id}</code>\n"
                    f"💰 Amount: ₹{bonus_amount:.2f}\n\n"
                    f"Click CONFIRM to send this bonus. The user will get a special button to claim it instantly.\n\n"
                    f"<b>FIRST USER TO CLICK GETS THE MONEY!</b>",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
                
            except ValueError:
                await update.message.reply_text("❌ Invalid amount. Please enter a number (e.g., 50)")

    # --- REGULAR USER LOGIC ---
    else:
        user_state = context.user_data.get("state")

        if user_state == "waiting_for_withdraw_details":
            method = context.user_data.get("setup_withdraw_method")
            details = update.message.text.strip()
            
            USERS_COLLECTION.update_one(
                {"user_id": user.id},
                {"$set": {"payment_method": method, "payment_details": details}}
            )
            
            context.user_data["state"] = None
            
            msg = (
                f"✅ <b>Details Saved!</b>\n\n"
                f"Method: {method.upper()}\n"
                f"Details: {details}\n\n"
                f"Now you can proceed to withdraw."
            )
            keyboard = [[InlineKeyboardButton("💸 Withdraw Now", callback_data="process_withdraw_final")]]
            
            await update.message.reply_html(msg, reply_markup=InlineKeyboardMarkup(keyboard))
