# admin_handlers.py

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.error import TelegramError, TimedOut, Forbidden, BadRequest, RetryAfter as FloodWait
from telegram.ext import ContextTypes
from datetime import datetime
import asyncio

from config import (
    USERS_COLLECTION, REFERRALS_COLLECTION, SETTINGS_COLLECTION, WITHDRAWALS_COLLECTION,
    DOLLAR_TO_INR, MESSAGES, ADMIN_ID
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
    message = MESSAGES[lang].get("admin_panel_title", "👑 <b>Admin Panel</b>\n\nSelect an action:")

    keyboard = [
        [InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_set_broadcast"),
         InlineKeyboardButton("💸 Pending Withdrawals", callback_data="admin_pending_withdrawals")],
        [InlineKeyboardButton("⚙️ Set Referral Rate", callback_data="admin_set_ref_rate"),
         InlineKeyboardButton("📊 Bot Stats", callback_data="admin_stats")],
        # --- NEW BUTTONS ---
        [InlineKeyboardButton("📊 User Stats", callback_data="admin_user_stats")],
        [InlineKeyboardButton("🗑️ Clear Junk Users", callback_data="admin_clear_junk")]
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
    elif action == "pending": # 'admin_pending' button redirects to admin_panel
        await back_to_admin_menu(update, context)
    
    # --- NEW ACTIONS ---
    elif action == "user" and sub_action == "stats":
        # 1. Prompt for User ID
        context.user_data["admin_state"] = "waiting_for_user_id_stats"
        await query.edit_message_text(
            MESSAGES[lang]["admin_user_stats_prompt"],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]])
        )
        
    elif action == "clear" and sub_action == "junk":
        # 2. Clear Junk Users
        await query.edit_message_text("🗑️ Clearing junk users (is_approved=False)... Please wait.", parse_mode='HTML')
        result = await clear_junk_users()
        await query.edit_message_text(
            MESSAGES[lang]["clear_junk_success"].format(
                users=result.get("users", 0),
                referrals=result.get("referrals", 0),
                withdrawals=result.get("withdrawals", 0)
            ),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]),
            parse_mode='HTML'
        )

    # --- YAHAN NAYA BLOCK ADD KAREIN (3.2) ---
    elif action == "reply" and sub_action == "user":
        # 3. Admin reply state set karein
        user_id_to_reply = data[3]
        context.user_data["admin_state"] = "admin_replying"
        context.user_data["reply_target_user_id"] = int(user_id_to_reply)
        
        await query.edit_message_text(
            MESSAGES[lang]["admin_reply_prompt"].format(user_id=user_id_to_reply),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]),
            parse_mode='HTML'
        )
    # --- YAHAN TAK NAYA BLOCK ADD KAREIN ---
        
    elif action == "add" and sub_action == "money":
        # 4. Prompt for Add Money
        user_id = context.user_data.get("stats_user_id")
        if not user_id:
            await query.edit_message_text("❌ Error: User ID not found in session. Please start over.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]))
            return
        context.user_data["admin_state"] = "waiting_for_add_money"
        await query.edit_message_text(
            MESSAGES[lang]["admin_add_money_prompt"].format(user_id=user_id),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]))
        
    elif action == "clear" and sub_action == "data":
        # 5. Prompt for Clear Data
        user_id = context.user_data.get("stats_user_id")
        if not user_id:
            await query.edit_message_text("❌ Error: User ID not found in session. Please start over.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]))
            return
        context.user_data["admin_state"] = "waiting_for_clear_data"
        await query.edit_message_text(
            MESSAGES[lang]["admin_clear_data_prompt"],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]))

    # --- OLD ACTIONS (Must be last) ---
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

    lang = await get_user_lang(query.from_user.id)
    stats = await get_bot_stats()

    message = MESSAGES[lang].get("stats_message", "📊 <b>Bot Stats</b>\n\nTotal Users: {total_users}\nApproved Users: {approved_users}").format(
        total_users=stats["total_users"],
        approved_users=stats["approved_users"]
    )
    
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
            
            # --- YAHAN SE BADLAV SHURU KAREIN (3.1) ---
            
            # Naya: Payment details fetch karein
            payment_details = request.get("payment_details", "N/A")

            message += f"👤 User: <code>{user_id}</code> (@{username})\n"
            message += f"💰 Amount: ₹{amount:.2f}\n"
            message += f"💳 Details: <b>{payment_details}</b>\n" # Payment details dikhayein
            
            if len(keyboard) < 5 * 2: # Show up to 5 requests, each takes 2 buttons rows
                keyboard.append([
                    InlineKeyboardButton(f"✅ Approve {user_id}", callback_data=f"approve_withdraw_{user_id}"),
                    InlineKeyboardButton(f"❌ Reject {user_id}", callback_data=f"reject_withdraw_{user_id}")
                ])
                # Naya: Reply button add karein
                keyboard.append([
                    InlineKeyboardButton(f"✉️ Reply to {user_id}", callback_data=f"admin_reply_user_{user_id}")
                ])
            
            message += "----\n" # Separator
                
        message += "\n(Showing up to 5 requests. Use buttons to process.)"
        # --- YAHAN TAK BADLAV KAREIN ---

    keyboard.append([InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_pending")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


# --- YAHAN SE POORA FUNCTION REPLACE KAREIN (handle_admin_input ki jagah) (3.3) ---

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
            # Admin se koi input expect nahi kar rahe, ignore
            return

        # --- STATE: waiting_for_user_id_stats ---
        if admin_state == "waiting_for_user_id_stats":
            try:
                user_id = int(text)
                stats = await get_user_stats(user_id)
                
                if not stats:
                    await update.message.reply_text(MESSAGES[lang]["admin_user_not_found"].format(user_id=user_id))
                    context.user_data["admin_state"] = None
                    return

                # Store user_id in session for the buttons
                context.user_data["stats_user_id"] = user_id
                context.user_data["admin_state"] = None # Clear state after successful ID capture

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
                await update.message.reply_text(MESSAGES[lang]["admin_invalid_input"])
            except Exception as e:
                await update.message.reply_text(f"An error occurred: {e}")
            
        # --- STATE: waiting_for_add_money ---
        elif admin_state == "waiting_for_add_money":
            user_id = context.user_data.get("stats_user_id")
            if not user_id:
                await update.message.reply_text("Error: Session expired. Please start over from /admin.")
                context.user_data["admin_state"] = None
                return
                
            try:
                amount_inr = float(text)
                new_balance = await admin_add_money(user_id, amount_inr)
                
                await update.message.reply_text(
                    MESSAGES[lang]["admin_add_money_success"].format(
                        amount=amount_inr, 
                        user_id=user_id, 
                        new_balance=new_balance
                    )
                )
                # Send log
                await send_log_message(context, f"ADMIN: <code>{user.id}</code> added ₹{amount_inr:.2f} to user <code>{user_id}</code>.")
                
            except ValueError:
                await update.message.reply_text(MESSAGES[lang]["admin_invalid_input"] + " Please enter a number (e.g., 10.50).")
            
            context.user_data["admin_state"] = None
            context.user_data["stats_user_id"] = None

        # --- STATE: waiting_for_clear_data ---
        elif admin_state == "waiting_for_clear_data":
            user_id = context.user_data.get("stats_user_id")
            choice = text.strip().lower()

            if not user_id:
                await update.message.reply_text("Error: Session expired. Please start over from /admin.")
                context.user_data["admin_state"] = None
                return
            
            if choice == "earning":
                await admin_clear_earnings(user_id)
                await update.message.reply_text(MESSAGES[lang]["admin_clear_earnings_success"].format(user_id=user_id))
                await send_log_message(context, f"ADMIN: <code>{user.id}</code> cleared earnings for user <code>{user_id}</code>.")
                
            elif choice == "all":
                await admin_delete_user(user_id)
                await update.message.reply_text(MESSAGES[lang]["admin_delete_user_success"].format(user_id=user_id))
                await send_log_message(context, f"ADMIN: <code>{user.id}</code> DELETED ALL data for user <code>{user_id}</code>.")
                
            else:
                await update.message.reply_text(MESSAGES[lang]["admin_invalid_input"] + " Please reply with 'all' or 'earning'.")
                return # Keep state active

            context.user_data["admin_state"] = None
            context.user_data["stats_user_id"] = None
            
        # --- STATE: waiting_for_broadcast_message ---
        elif admin_state == "waiting_for_broadcast_message":
            # ... (aapka maujooda broadcast logic ... jaisa pehle tha) ...
            
            success_count = 0
            fail_count = 0
            
            status_message = await update.message.reply_text("📢 Starting broadcast... This may take a moment. Updates will be shown here.")
            
            user_ids_cursor = USERS_COLLECTION.find({"is_approved": True}, {"user_id": 1}) 
            total_users = USERS_COLLECTION.count_documents({"is_approved": True})
            
            for i, user_data in enumerate(user_ids_cursor):
                user_id = user_data["user_id"]
                
                if i % 100 == 0 and i != 0:
                     try:
                        await context.bot.edit_message_text(
                            chat_id=status_message.chat_id, 
                            message_id=status_message.message_id,
                            text=f"📢 Broadcasting in progress...\nSent to {i} of {total_users} users.\nSuccess: {success_count} / Failed: {fail_count}"
                        )
                     except Exception as e:
                         logger.warning(f"Failed to edit broadcast status message: {e}")
                
                try:
                    await context.bot.send_message(user_id, text, parse_mode='HTML', disable_web_page_preview=True)
                    success_count += 1
                    await asyncio.sleep(0.05) 
                    
                except FloodWait as e:
                    wait_time = e.retry_after + 1 
                    logger.warning(f"FloodWait encountered for user {user_id}. Waiting for {wait_time} seconds. Success: {success_count}, Fail: {fail_count}")
                    await context.bot.edit_message_text(
                         chat_id=status_message.chat_id, 
                         message_id=status_message.message_id,
                         text=f"⚠️ **PAUSED: FloodWait**\nWaiting for {wait_time} seconds...\nSent to {i} of {total_users} users.\nSuccess: {success_count} / Failed: {fail_count}"
                    )
                    await asyncio.sleep(wait_time)
                    try:
                        await context.bot.send_message(user_id, text, parse_mode='HTML', disable_web_page_preview=True)
                        success_count += 1
                        await asyncio.sleep(0.05)
                    except Exception:
                         fail_count += 1
                    
                except (Forbidden, BadRequest) as e:
                    fail_count += 1
                    USERS_COLLECTION.update_one({"user_id": user_id}, {"$set": {"is_approved": False}}) 
                    logger.warning(f"Failed to send to user {user_id} due to API Error: {e}. User marked unapproved.")
                    
                except Exception as e:
                    fail_count += 1
                    logger.error(f"Unknown error sending to user {user.id}: {e}")
                    
            context.user_data["admin_state"] = None
            await context.bot.edit_message_text(
                chat_id=status_message.chat_id, 
                message_id=status_message.message_id,
                text=f"✅ **Broadcast complete**.\nSuccessful: {success_count}\nFailed: {fail_count}\nTotal users processed: {total_users}"
            )

        # --- STATE: waiting_for_ref_rate ---
        elif admin_state == "waiting_for_ref_rate":
            # ... (aapka maujooda ref_rate logic ... jaisa pehle tha) ...
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

        # --- NAYA STATE: admin_replying ---
        elif admin_state == "admin_replying":
            target_user_id = context.user_data.get("reply_target_user_id")
            reply_message = update.message.text
            
            if not target_user_id:
                await update.message.reply_text("Error: Session expired (user ID not found). State cleared.")
            else:
                try:
                    # User ko admin ka message bhejein
                    await context.bot.send_message(
                        chat_id=target_user_id, 
                        text=MESSAGES[lang]["user_reply_from_admin"].format(message=reply_message),
                        parse_mode='HTML'
                    )
                    await update.message.reply_text(MESSAGES[lang]["admin_reply_success"].format(user_id=target_user_id))
                except Exception as e:
                    logger.error(f"Admin reply failed to user {target_user_id}: {e}")
                    await update.message.reply_text(MESSAGES[lang]["admin_reply_fail"].format(user_id=target_user_id))
            
            # State clear karein
            context.user_data["admin_state"] = None
            context.user_data["reply_target_user_id"] = None


    # --- ROUTE 2: REGULAR USER LOGIC ---
    else:
        user_state = context.user_data.get("state")

        # --- STATE: waiting_for_payment_details ---
        if user_state == "waiting_for_payment_details":
            # User ne payment details bheji hain
            
            # 1. Timer job ko rokein
            job_name = f"clear_payment_state_{user.id}"
            existing_jobs = context.job_queue.get_jobs_by_name(job_name)
            
            if not existing_jobs:
                # Timer pehle hi expire ho chuka hai
                await update.message.reply_text(MESSAGES[lang]["withdrawal_session_expired"])
                context.user_data["state"] = None
                return
                
            # Job ko cancel karein
            for job in existing_jobs:
                job.schedule_removal()
                
            # 2. State se amount retrieve karein
            earnings_inr = context.user_data.get("withdrawal_amount", 80.0) # Fallback
            payment_details = update.message.text
            
            # 3. State clear karein
            context.user_data["state"] = None
            context.user_data["withdrawal_amount"] = None
            
            # 4. Ab withdrawal request create karein
            username_display = f"@{user.username}" if user.username else f"<code>{user.id}</code>"
            
            withdrawal_data = {
                "user_id": user.id,
                "username": user.username,
                "full_name": user.first_name + (f" {user.last_name}" if user.last_name else ""),
                "amount_inr": earnings_inr,
                "status": "pending",
                "request_date": datetime.now(),
                "approved_date": None,
                "payment_details": payment_details  # NAYA: Payment details save karein
            }
            
            WITHDRAWALS_COLLECTION.insert_one(withdrawal_data)

            # 5. Admin ko message bhejein (payment details ke saath)
            admin_message = (
                f"🔄 <b>New Withdrawal Request</b>\n\n"
                f"👤 User: {user.full_name} ({username_display})\n"
                f"🆔 ID: <code>{user.id}</code>\n"
                f"💰 Amount: ₹{earnings_inr:.2f}\n"
                f"💳 Details: <b>{payment_details}</b>"
            )
            
            await send_log_message(context, admin_message)

            if ADMIN_ID:
                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=admin_message,
                        parse_mode='HTML',
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("✅ Approve", callback_data=f"approve_withdraw_{user.id}"),
                             InlineKeyboardButton("❌ Reject", callback_data=f"reject_withdraw_{user.id}")],
                            [InlineKeyboardButton(f"✉️ Reply to {user.id}", callback_data=f"admin_reply_user_{user.id}")] # Naya button
                        ])
                    )
                except Exception as e:
                    logger.error(f"Could not notify admin about withdrawal: {e}")

            # 6. User ko success message bhejein
            await update.message.reply_text(
                MESSAGES[lang]["withdrawal_details_received"].format(amount=earnings_inr),
                parse_mode='HTML'
            )

# --- YAHAN TAK POORA FUNCTION REPLACE KAREIN (handle_admin_input ki jagah) (3.3) ---

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
    
    # We use find_one_and_update to process the first pending request for this user.
    # We must ensure to only process one at a time to prevent errors.
    withdrawal_request = WITHDRAWALS_COLLECTION.find_one_and_update(
        {"user_id": user_id, "status": "pending"},
        {"$set": {"status": action, "approved_date": datetime.now()}},
        # Important: Setting return_document=True returns the document *before* the update if not specified otherwise
        # But we need the data that was updated, so we rely on the returned document structure.
        # Since we use find_one_and_update with a filter "status": "pending", the found document has the data we need.
        return_document=True # This returns the document *after* the update by default in some Python wrappers, but here we just need the request info.
    )

    if not withdrawal_request:
        if query.message:
            await query.edit_message_text(f"❌ Withdrawal request for user <code>{user_id}</code> not found or already processed.", parse_mode='HTML')
        return

    amount_inr = withdrawal_request["amount_inr"]
    
    if action == "approve":
        amount_usd = amount_inr / DOLLAR_TO_INR
        # Deduct the amount from the user's earnings
        USERS_COLLECTION.update_one(
            {"user_id": user_id},
            {"$inc": {"earnings": -amount_usd}}
        )
        
        try:
            user_lang = await get_user_lang(user_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=MESSAGES[user_lang]["withdrawal_approved_user"].format(amount=amount_inr), 
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
                text=MESSAGES[user_lang]["withdrawal_rejected_user"].format(amount=amount_inr), 
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
         # Just go back to main admin menu
         await back_to_admin_menu(update, context) 
