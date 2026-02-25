# admin_handlers.py

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError, Forbidden, BadRequest, RetryAfter as FloodWait
from telegram.ext import ContextTypes
from datetime import datetime
import asyncio
from io import BytesIO

from config import (
    USERS_COLLECTION, REFERRALS_COLLECTION, SETTINGS_COLLECTION, WITHDRAWALS_COLLECTION,
    DOLLAR_TO_INR, MESSAGES, ADMIN_ID, BROADCAST_BATCH_SIZE, BROADCAST_DELAY
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

    # Clear state on entering admin panel
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
        [InlineKeyboardButton("📋 User Report (95 Referrals)", callback_data="admin_user_report")]
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
            pass


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
    
    # User Stats
    elif action == "user" and sub_action == "stats":
        context.user_data["admin_state"] = "waiting_for_user_id_stats"
        await query.edit_message_text(
            "✍️ Please reply to this message with the User ID you want to check:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]])
        )
    
    # --- NEW: User Report Generation (95 Referrals Check) ---
    elif action == "user" and sub_action == "report":
        context.user_data["admin_state"] = "waiting_for_user_id_report"
        await query.edit_message_text(
            "✍️ Please reply to this message with the User ID you want to generate report for:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]])
        )
        
    # Clear Junk Users
    elif action == "clear" and sub_action == "junk":
        await query.edit_message_text("🗑️ Clearing junk users (is_approved=False)... Please wait.", parse_mode='HTML')
        result = await clear_junk_users()
        await query.edit_message_text(
            f"✅ Junk Data Cleared!\n\nUsers deleted: {result.get('users', 0)}\nReferral records cleared: {result.get('referrals', 0)}\nWithdrawals cleared: {result.get('withdrawals', 0)}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]),
            parse_mode='HTML'
        )

    # Reply to User
    elif action == "reply" and sub_action == "user":
        user_id_to_reply = data[3]
        context.user_data["admin_state"] = "admin_replying"
        context.user_data["reply_target_user_id"] = int(user_id_to_reply)
        
        await query.edit_message_text(
            f"✍️ <b>Reply to User {user_id_to_reply}</b>\n\nYour next message will be sent directly to this user. Send your reply now.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]),
            parse_mode='HTML'
        )
        
    # Add Money
    elif action == "add" and sub_action == "money":
        user_id = context.user_data.get("stats_user_id")
        if not user_id:
            await query.edit_message_text("❌ Error: User ID not found in session. Please start over.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]))
            return
        context.user_data["admin_state"] = "waiting_for_add_money"
        await query.edit_message_text(
            f"💰 Please reply with the amount (in INR, e.g., 10.50 or 100+ or 50-) you want to add/deduct from user {user_id}:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]))
        
    # Clear Data
    elif action == "clear" and sub_action == "data":
        user_id = context.user_data.get("stats_user_id")
        if not user_id:
            await query.edit_message_text("❌ Error: User ID not found in session. Please start over.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]))
            return
        context.user_data["admin_state"] = "waiting_for_clear_data"
        await query.edit_message_text(
            "⚠️ Are you sure?\nTo clear only earnings, reply with: `earning`\nTo delete all user data, reply with: `all`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]))

    # Broadcast and Set Rate
    elif action == "set": 
        if sub_action == "broadcast":
            context.user_data["admin_state"] = "waiting_for_broadcast_message"
            await query.edit_message_text("✍️ Enter the **message** you want to broadcast to all users:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]))
        elif sub_action == "ref" and data[3] == "rate":
             context.user_data["admin_state"] = "waiting_for_ref_rate"
             await query.edit_message_text("✍️ Enter the **NEW Tier 1 Referral Rate** in INR (e.g., 5.0 for ₹5 per referral):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]))


async def show_bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message:
        return

    stats = await get_bot_stats()

    message = f"📊 <b>Bot Stats</b>\n\nTotal Users: {stats['total_users']}\nApproved Users: {stats['approved_users']}"
    
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
            
            if len(keyboard) < 5 * 2: # Show up to 5 requests
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


async def handle_private_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not update.message or not update.message.text:
        return
        
    lang = await get_user_lang(user.id)
    text = update.message.text

    # --- ROUTE 1: ADMIN LOGIC ---
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

                message = (
                    f"📊 <b>User Stats for {stats['full_name']}</b>\n\n"
                    f"<b>ID:</b> <code>{stats['user_id']}</code>\n"
                    f"<b>Username:</b> @{stats['username']}\n"
                    f"<b>Balance:</b> ₹{stats['earnings_inr']:.2f}\n"
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
                
        # --- NEW: waiting_for_user_id_report ---
        elif admin_state == "waiting_for_user_id_report":
            try:
                target_id = int(text)
                
                await update.message.reply_text(f"📊 Generating report for user {target_id}...")
                
                # Get all referrals for this user
                referrals = REFERRALS_COLLECTION.find({"referrer_id": target_id})
                
                report = f"📊 REPORT FOR USER: {target_id}\n"
                report += f"{'Referred ID':<15} | {'Active?':<10}\n"
                report += "-"*30 + "\n"
                
                real, fake = 0, 0
                for r in referrals:
                    # अगर उसने कभी सर्च किया है (last_paid_date मौजूद है)
                    status = "YES" if r.get("last_paid_date") else "NO"
                    if status == "YES": 
                        real += 1 
                    else: 
                        fake += 1
                    report += f"{r['referred_user_id']:<15} | {status:<10}\n"
                    
                report += f"\n✅ Real (Paid): {real}\n❌ Fake (No Search): {fake}"
                
                # फाइल बनाकर भेजें
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

        # STATE: waiting_for_add_money (UPDATED with 100+ and 100- support)
        elif admin_state == "waiting_for_add_money":
            user_id = context.user_data.get("stats_user_id")
            if not user_id:
                await update.message.reply_text("Error: Session expired. Start over.")
                context.user_data["admin_state"] = None
                return
            
            text_input = text.strip() # यूजर का मैसेज (e.g., "100+" या "50-" या "20")
            
            try:
                amount_to_process = 0.0
                operation = "add" # Default

                # चेक करें कि क्या यूजर ने + या - लगाया है
                if text_input.endswith("+"):
                    amount_to_process = float(text_input[:-1]) # "100+" -> 100.0
                    operation = "add"
                elif text_input.endswith("-"):
                    amount_to_process = float(text_input[:-1]) # "50-" -> 50.0
                    operation = "subtract"
                else:
                    # अगर कोई साइन नहीं है, तो उसे सीधा add मानेंगे
                    amount_to_process = float(text_input)
                    operation = "add"

                current_stats = await get_user_stats(user_id)
                current_balance_inr = current_stats['earnings_inr']

                if operation == "add":
                    # पैसे जोड़ें
                    new_balance = await admin_add_money(user_id, amount_to_process)
                    msg = f"✅ Added ₹{amount_to_process:.2f}.\nOld Balance: ₹{current_balance_inr:.2f}\n🆕 New Balance: ₹{new_balance:.2f}"
                    log_text = f"ADMIN ADD: ₹{amount_to_process} to User {user_id}"
                
                elif operation == "subtract":
                    # पैसे काटें (Minus में add negative number)
                    # admin_add_money फंक्शन में हम negative value भेजेंगे
                    new_balance = await admin_add_money(user_id, -amount_to_process)
                    msg = f"🔻 Deducted ₹{amount_to_process:.2f}.\nOld Balance: ₹{current_balance_inr:.2f}\n🆕 New Balance: ₹{new_balance:.2f}"
                    log_text = f"ADMIN DEDUCT: ₹{amount_to_process} from User {user_id}"

                await update.message.reply_text(msg)
                await send_log_message(context, log_text)
                
            except ValueError:
                await update.message.reply_text("❌ Invalid format.\nUse `100+` to add\nUse `50-` to deduct.")
            
            # स्टेट क्लियर करें
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

        # STATE: waiting_for_broadcast_message (FIXED - Now works for 4000+ users)
        elif admin_state == "waiting_for_broadcast_message":
            broadcast_message = text
            
            success_count = 0
            fail_count = 0
            blocked_count = 0
            
            status_message = await update.message.reply_text("📢 Starting broadcast... This may take a moment. Updates will be shown here.")
            
            # Get all approved users
            user_cursor = USERS_COLLECTION.find({"is_approved": True}, {"user_id": 1})
            all_users = list(user_cursor)
            total_users = len(all_users)
            
            # Process in batches to avoid flooding
            for i in range(0, total_users, BROADCAST_BATCH_SIZE):
                batch = all_users[i:i+BROADCAST_BATCH_SIZE]
                
                # Update status every batch
                try:
                    await context.bot.edit_message_text(
                        chat_id=status_message.chat_id, 
                        message_id=status_message.message_id,
                        text=f"📢 Broadcasting...\nProcessed: {i} of {total_users}\n✅ Success: {success_count} | ❌ Failed: {fail_count} | 🚫 Blocked: {blocked_count}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to edit broadcast status message: {e}")
                
                # Send messages in parallel (asyncio.gather for speed)
                tasks = []
                for user_data in batch:
                    user_id = user_data["user_id"]
                    tasks.append(send_single_broadcast(context, user_id, broadcast_message))
                
                # Wait for all messages in this batch to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Count results
                for result in results:
                    if isinstance(result, Exception):
                        fail_count += 1
                    elif result is False:
                        blocked_count += 1
                        fail_count += 1
                    elif result is True:
                        success_count += 1
                
                # Small delay between batches to avoid rate limits
                await asyncio.sleep(1)
            
            # Final status
            context.user_data["admin_state"] = None
            await context.bot.edit_message_text(
                chat_id=status_message.chat_id, 
                message_id=status_message.message_id,
                text=f"✅ **Broadcast Complete**\n\n"
                     f"Total Users: {total_users}\n"
                     f"✅ Successful: {success_count}\n"
                     f"❌ Failed: {fail_count}\n"
                     f"🚫 Blocked Bot: {blocked_count}"
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
                await update.message.reply_text(f"✅ Referral rate successfully updated to **₹{new_rate:.2f}** per referral.")
                
            except ValueError:
                await update.message.reply_text("❌ Invalid input. Please enter a valid number for the new rate (e.g., 5.0).")

    # --- ROUTE 2: REGULAR USER LOGIC ---
    else:
        user_state = context.user_data.get("state")

        # STATE: waiting_for_withdraw_details
        if user_state == "waiting_for_withdraw_details":
            method = context.user_data.get("setup_withdraw_method")
            details = update.message.text.strip()
            
            # Save to Database Permanently
            USERS_COLLECTION.update_one(
                {"user_id": user.id},
                {"$set": {"payment_method": method, "payment_details": details}}
            )
            
            context.user_data["state"] = None
            
            # Confirmation Message
            msg = (
                f"✅ <b>Details Saved!</b>\n\n"
                f"Method: {method.upper()}\n"
                f"Details: {details}\n\n"
                f"Now you can proceed to withdraw."
            )
            keyboard = [[InlineKeyboardButton("💸 Withdraw Now", callback_data="process_withdraw_final")]]
            
            await update.message.reply_html(msg, reply_markup=InlineKeyboardMarkup(keyboard))


# Helper function for broadcast (parallel sending)
async def send_single_broadcast(context, user_id, message):
    """Send a single broadcast message to a user"""
    try:
        await context.bot.send_message(
            chat_id=user_id, 
            text=message, 
            parse_mode='HTML', 
            disable_web_page_preview=True
        )
        await asyncio.sleep(BROADCAST_DELAY)  # Small delay to avoid rate limits
        return True
    except FloodWait as e:
        # Handle rate limiting
        wait_time = e.retry_after + 1
        logger.warning(f"FloodWait for user {user_id}. Waiting {wait_time}s")
        await asyncio.sleep(wait_time)
        try:
            await context.bot.send_message(
                chat_id=user_id, 
                text=message, 
                parse_mode='HTML', 
                disable_web_page_preview=True
            )
            return True
        except Exception:
            return False
    except (Forbidden, BadRequest) as e:
        # User blocked the bot or deleted account
        USERS_COLLECTION.update_one({"user_id": user_id}, {"$set": {"is_approved": False}})
        logger.warning(f"User {user_id} blocked bot or deleted account")
        return False
    except Exception as e:
        logger.error(f"Unknown error sending to user {user_id}: {e}")
        return False


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
        amount_usd = amount_inr / DOLLAR_TO_INR
        USERS_COLLECTION.update_one(
            {"user_id": user_id},
            {"$inc": {"earnings": -amount_usd}}
        )
        
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
            await query.edit_message_text(f"✅ Request for user <code>{user_id}</code> (**₹{amount_inr:.2f}**) **APPROVED**.\nFunds deducted.", parse_mode='HTML')
        log_msg = f"💸 <b>Withdrawal Approved</b>\nAdmin: <code>{query.from_user.id}</code>\nUser: <code>{user_id}</code>\nAmount: ₹{amount_inr:.2f}"
    
    else: # action == "reject"
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
            await query.edit_message_text(f"❌ Request for user <code>{user_id}</code> (**₹{amount_inr:.2f}**) **REJECTED**.", parse_mode='HTML')
        log_msg = f"🚫 <b>Withdrawal Rejected</b>\nAdmin: <code>{query.from_user.id}</code>\nUser: <code>{user_id}</code>\nAmount: ₹{amount_inr:.2f}"

    await send_log_message(context, log_msg)
    
    # Reload the pending list if the callback came from that view
    if query.message and "Pending Withdrawals" in query.message.text: 
         await show_pending_withdrawals(update, context) 
    elif query.message:
         await back_to_admin_menu(update, context)
