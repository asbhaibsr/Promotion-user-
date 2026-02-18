# admin_handlers.py 

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
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

# ==================== ADMIN PANEL ====================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin panel"""
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        if update.message:
            await update.message.reply_text("❌ Access Denied.")
        return
    
    context.user_data.clear()
    
    keyboard = [
        [InlineKeyboardButton("📊 Bot Stats", callback_data="admin_stats"),
         InlineKeyboardButton("💸 Pending", callback_data="admin_pending_withdrawals")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_set_broadcast"),
         InlineKeyboardButton("⚙️ Set Rate", callback_data="admin_set_ref_rate")],
        [InlineKeyboardButton("📊 User Stats", callback_data="admin_user_stats"),
         InlineKeyboardButton("🗑️ Clear Junk", callback_data="admin_clear_junk")]
    ]
    
    msg = "👑 <b>Admin Panel</b>\n\nSelect an option:"
    
    if update.message:
        await update.message.reply_html(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    elif update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

# ==================== ADMIN CALLBACKS ====================

async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin callback queries"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Access Denied.")
        return
    
    data = query.data.split("_")
    action = data[1]
    sub = data[2] if len(data) > 2 else None
    
    lang = await get_user_lang(ADMIN_ID)
    
    # Bot Stats
    if action == "stats" and sub is None:
        stats = await get_bot_stats()
        msg = f"📊 <b>Bot Stats</b>\n\nTotal Users: {stats['total_users']}\nActive: {stats['approved_users']}"
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    
    # Pending Withdrawals
    elif action == "pending" and sub == "withdrawals":
        await show_pending_withdrawals(update, context)
    
    # User Stats
    elif action == "user" and sub == "stats":
        context.user_data["admin_state"] = "waiting_for_user_id_stats"
        await query.edit_message_text(
            "✍️ Send User ID to check:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]])
        )
    
    # Clear Junk
    elif action == "clear" and sub == "junk":
        await query.edit_message_text("🗑️ Clearing junk data...")
        result = await clear_junk_users()
        msg = MESSAGES[lang]["clear_junk_success"].format(
            users=result.get("users", 0),
            referrals=result.get("referrals", 0),
            withdrawals=result.get("withdrawals", 0)
        )
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    
    # Set Broadcast
    elif action == "set" and sub == "broadcast":
        context.user_data["admin_state"] = "waiting_for_broadcast_message"
        await query.edit_message_text(
            "✍️ Enter broadcast message:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]])
        )
    
    # Set Referral Rate
    elif action == "set" and sub == "ref":
        context.user_data["admin_state"] = "waiting_for_ref_rate"
        await query.edit_message_text(
            "✍️ Enter new Tier 1 rate (INR):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]])
        )
    
    # Reply to User
    elif action == "reply" and sub == "user":
        target = data[3]
        context.user_data["admin_state"] = "admin_replying"
        context.user_data["reply_target"] = int(target)
        await query.edit_message_text(
            f"✍️ Reply to user {target}:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]])
        )
    
    # Add Money
    elif action == "add" and sub == "money":
        uid = context.user_data.get("stats_user_id")
        if uid:
            context.user_data["admin_state"] = "waiting_for_add_money"
            await query.edit_message_text(
                f"💰 Enter amount to add to {uid}:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]])
            )
    
    # Clear Data
    elif action == "clear" and sub == "data":
        uid = context.user_data.get("stats_user_id")
        if uid:
            context.user_data["admin_state"] = "waiting_for_clear_data"
            await query.edit_message_text(
                "⚠️ Reply 'earning' or 'all':",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]])
            )
    
    # Back
    elif action == "pending":
        await admin_panel(update, context)

# ==================== PENDING WITHDRAWALS ====================

async def show_pending_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show pending withdrawals with payment details"""
    query = update.callback_query
    
    pendings = list(WITHDRAWALS_COLLECTION.find({"status": "pending"}).sort("request_date", 1).limit(5))
    count = WITHDRAWALS_COLLECTION.count_documents({"status": "pending"})
    
    if not pendings:
        msg = "✅ No pending withdrawals."
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return
    
    msg = f"<b>💸 Pending Withdrawals ({count})</b>\n\n"
    keyboard = []
    
    for p in pendings:
        uid = p["user_id"]
        amount = p["amount_inr"]
        details = p.get("payment_details", "N/A")
        date = p["request_date"].strftime("%d %b %H:%M")
        
        msg += f"👤 <code>{uid}</code>\n"
        msg += f"💰 ₹{amount:.2f}\n"
        msg += f"💳 {details}\n"
        msg += f"📅 {date}\n\n"
        
        keyboard.append([
            InlineKeyboardButton(f"✅ Approve {uid}", callback_data=f"approve_withdraw_{uid}"),
            InlineKeyboardButton(f"❌ Reject {uid}", callback_data=f"reject_withdraw_{uid}")
        ])
        keyboard.append([
            InlineKeyboardButton(f"✉️ Reply {uid}", callback_data=f"admin_reply_user_{uid}")
        ])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")])
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

# ==================== WITHDRAWAL APPROVAL ====================

async def handle_withdrawal_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Approve or reject withdrawal"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Access Denied.")
        return
    
    action = query.data.split("_")[0]
    uid = int(query.data.split("_")[2])
    
    # Find and update request
    req = WITHDRAWALS_COLLECTION.find_one_and_update(
        {"user_id": uid, "status": "pending"},
        {"$set": {"status": action, "approved_date": datetime.now()}},
        return_document=True
    )
    
    if not req:
        await query.edit_message_text(f"❌ No pending request for {uid}")
        return
    
    amount = req["amount_inr"]
    
    if action == "approve":
        # Deduct from user
        USERS_COLLECTION.update_one(
            {"user_id": uid},
            {"$inc": {"earnings": -amount/DOLLAR_TO_INR}}
        )
        
        # Notify user
        try:
            user_lang = await get_user_lang(uid)
            await context.bot.send_message(
                uid,
                MESSAGES[user_lang]["withdrawal_approved"].format(amount=f"₹{amount:.2f}"),
                parse_mode='HTML'
            )
        except:
            pass
        
        msg = f"✅ Approved ₹{amount:.2f} for {uid}"
        log = f"💸 Withdrawal Approved: {uid} - ₹{amount:.2f}"
    
    else:  # reject
        try:
            user_lang = await get_user_lang(uid)
            await context.bot.send_message(
                uid,
                MESSAGES[user_lang]["withdrawal_rejected"].format(amount=f"₹{amount:.2f}"),
                parse_mode='HTML'
            )
        except:
            pass
        
        msg = f"❌ Rejected ₹{amount:.2f} for {uid}"
        log = f"🚫 Withdrawal Rejected: {uid} - ₹{amount:.2f}"
    
    await query.edit_message_text(msg, parse_mode='HTML')
    await send_log_message(context, log)
    
    # Go back to pending list
    await show_pending_withdrawals(update, context)

# ==================== ADMIN TEXT HANDLER ====================

async def handle_private_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle private messages (both admin and users)"""
    user = update.effective_user
    text = update.message.text
    
    # ===== ADMIN ROUTES =====
    if user.id == ADMIN_ID:
        state = context.user_data.get("admin_state")
        
        # Waiting for user ID stats
        if state == "waiting_for_user_id_stats":
            try:
                uid = int(text)
                stats = await get_user_stats(uid)
                
                if not stats:
                    await update.message.reply_text(f"❌ User {uid} not found.")
                    context.user_data["admin_state"] = None
                    return
                
                context.user_data["stats_user_id"] = uid
                context.user_data["admin_state"] = None
                
                msg = f"📊 <b>User {uid}</b>\n\n"
                msg += f"Balance: ₹{stats['earnings_inr']:.2f}\n"
                msg += f"Referrals: {stats['referrals']}\n"
                msg += f"Name: {stats['full_name']}"
                
                keyboard = [
                    [InlineKeyboardButton("💰 Add Money", callback_data="admin_add_money"),
                     InlineKeyboardButton("🗑️ Clear Data", callback_data="admin_clear_data")],
                    [InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]
                ]
                await update.message.reply_html(msg, reply_markup=InlineKeyboardMarkup(keyboard))
                
            except ValueError:
                await update.message.reply_text("❌ Invalid User ID.")
                context.user_data["admin_state"] = None
        
        # Waiting for add money
        elif state == "waiting_for_add_money":
            uid = context.user_data.get("stats_user_id")
            try:
                amount = float(text)
                new_balance = await admin_add_money(uid, amount)
                await update.message.reply_text(f"✅ Added ₹{amount:.2f} to {uid}. New balance: ₹{new_balance:.2f}")
                await send_log_message(context, f"ADMIN: Added ₹{amount:.2f} to {uid}")
            except:
                await update.message.reply_text("❌ Invalid amount.")
            
            context.user_data["admin_state"] = None
        
        # Waiting for clear data
        elif state == "waiting_for_clear_data":
            uid = context.user_data.get("stats_user_id")
            choice = text.strip().lower()
            
            if choice == "earning":
                await admin_clear_earnings(uid)
                await update.message.reply_text(f"✅ Cleared earnings for {uid}")
                await send_log_message(context, f"ADMIN: Cleared earnings for {uid}")
            elif choice == "all":
                await admin_delete_user(uid)
                await update.message.reply_text(f"✅ Deleted all data for {uid}")
                await send_log_message(context, f"ADMIN: Deleted user {uid}")
            else:
                await update.message.reply_text("❌ Invalid. Use 'earning' or 'all'.")
            
            context.user_data["admin_state"] = None
        
        # Waiting for broadcast
        elif state == "waiting_for_broadcast_message":
            await update.message.reply_text("📢 Broadcasting... This may take a while.")
            
            users = USERS_COLLECTION.find({"is_approved": True}, {"user_id": 1})
            success = 0
            fail = 0
            
            for u in users:
                try:
                    await context.bot.send_message(u["user_id"], text, parse_mode='HTML')
                    success += 1
                    await asyncio.sleep(0.05)
                except:
                    fail += 1
            
            await update.message.reply_text(f"✅ Broadcast complete.\nSuccess: {success}\nFailed: {fail}")
            await send_log_message(context, f"📢 Broadcast sent. Success: {success}, Fail: {fail}")
            context.user_data["admin_state"] = None
        
        # Waiting for referral rate
        elif state == "waiting_for_ref_rate":
            try:
                rate = float(text)
                SETTINGS_COLLECTION.update_one(
                    {"_id": "referral_rate"},
                    {"$set": {"rate_inr": rate}},
                    upsert=True
                )
                await update.message.reply_text(f"✅ Referral rate set to ₹{rate:.2f}")
                await send_log_message(context, f"ADMIN: Set referral rate to ₹{rate:.2f}")
            except:
                await update.message.reply_text("❌ Invalid number.")
            
            context.user_data["admin_state"] = None
        
        # Admin replying to user
        elif state == "admin_replying":
            target = context.user_data.get("reply_target")
            if target:
                try:
                    await context.bot.send_message(
                        target,
                        f"🔔 <b>Admin:</b>\n\n{text}",
                        parse_mode='HTML'
                    )
                    await update.message.reply_text(f"✅ Message sent to {target}")
                except:
                    await update.message.reply_text(f"❌ Failed to send to {target}")
            
            context.user_data["admin_state"] = None
            context.user_data["reply_target"] = None
        
        return  # End admin routes
    
    # ===== USER ROUTES =====
    lang = await get_user_lang(user.id)
    user_state = context.user_data.get("state")
    
    # User is sending withdrawal details
    if user_state == "waiting_for_withdraw_details":
        method = context.user_data.get("setup_withdraw_method")
        details = text.strip()
        
        # Save to user profile
        USERS_COLLECTION.update_one(
            {"user_id": user.id},
            {"$set": {
                "payment_method": method,
                "payment_details": details
            }}
        )
        
        context.user_data["state"] = None
        context.user_data["setup_withdraw_method"] = None
        
        # Show confirmation and offer to withdraw
        msg = f"✅ <b>Details Saved!</b>\n\nMethod: {method.upper()}\nDetails: {details}\n\nNow you can withdraw."
        keyboard = [[InlineKeyboardButton("💸 Withdraw Now", callback_data="process_withdraw_final")]]
        await update.message.reply_html(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # User was in old withdrawal flow (for backward compatibility)
    elif user_state == "waiting_for_payment_details":
        earnings = context.user_data.get("withdrawal_amount", 80)
        
        # Create request
        withdrawal = {
            "user_id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "amount_inr": earnings,
            "status": "pending",
            "request_date": datetime.now(),
            "payment_details": text
        }
        WITHDRAWALS_COLLECTION.insert_one(withdrawal)
        
        # Notify admin
        if ADMIN_ID:
            admin_msg = f"🔄 New Withdrawal\nUser: {user.id}\nAmount: ₹{earnings:.2f}\nDetails: {text}"
            await context.bot.send_message(
                ADMIN_ID, admin_msg,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Approve", callback_data=f"approve_withdraw_{user.id}"),
                     InlineKeyboardButton("❌ Reject", callback_data=f"reject_withdraw_{user.id}")]
                ])
            )
        
        await update.message.reply_text(
            f"✅ Request sent!\nAmount: ₹{earnings:.2f}\n\nYou'll receive payment within 24h.",
            parse_mode='HTML'
        )
        
        context.user_data["state"] = None
        context.user_data["withdrawal_amount"] = None
