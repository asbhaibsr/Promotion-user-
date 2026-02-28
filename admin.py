# admin.py
import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from database import db
from utils import is_admin, format_balance, escape_markdown

logger = logging.getLogger(__name__)

class AdminHandlers:
    
    @staticmethod
    async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """एडमिन पैनल कमांड"""
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ आप एडमिन नहीं हैं!")
            return
        
        keyboard = [
            [InlineKeyboardButton("📢 ब्रॉडकास्ट", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🗑️ क्लियर जंक", callback_data="admin_clear_junk")],
            [InlineKeyboardButton("📊 यूजर स्टैट्स", callback_data="admin_user_stats")],
            [InlineKeyboardButton("💰 बैलेंस ऐड/रिमूव", callback_data="admin_balance")],
            [InlineKeyboardButton("🚫 ब्लॉक/अनब्लॉक", callback_data="admin_block")],
            [InlineKeyboardButton("📈 ग्लोबल स्टैट्स", callback_data="admin_global_stats")],
            [InlineKeyboardButton("📝 पेंडिंग विड्रॉल", callback_data="admin_withdrawals")],
            [InlineKeyboardButton("📊 एनालिटिक्स", callback_data="admin_analytics")],
            [InlineKeyboardButton("🔄 डेटा क्लीनअप", callback_data="admin_cleanup")],
            [InlineKeyboardButton("❌ बंद करें", callback_data="admin_close")]
        ]
        
        await update.message.reply_text(
            "👑 *एडमिन पैनल*\n"
            "कृपया एक विकल्प चुनें:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    @staticmethod
    async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """एडमिन कॉलबैक हैंडलर"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        if not is_admin(user_id):
            await query.edit_message_text("❌ आप एडमिन नहीं हैं!")
            return
        
        data = query.data
        
        if data == "admin_broadcast":
            context.user_data["admin_action"] = "broadcast"
            await query.edit_message_text(
                "📢 *ब्रॉडकास्ट मोड*\n\n"
                "अपना मैसेज भेजें जो सभी यूजर्स को जाना चाहिए।\n"
                "यह मैसेज टेक्स्ट, फोटो, वीडियो या डॉक्यूमेंट हो सकता है।\n\n"
                "⚠️ *API लिमिट का ध्यान रखा जाएगा*\n"
                "❌ कैंसल करने के लिए /cancel टाइप करें",
                parse_mode='Markdown'
            )
        
        elif data == "admin_clear_junk":
            # क्लियर जंक फंक्शन
            count = db.clear_junk_users()
            await query.edit_message_text(
                f"🗑️ *क्लियर जंक*\n\n"
                f"✅ {count} ब्लॉक/डिलीट यूजर्स का डेटा साफ किया गया!",
                parse_mode='Markdown'
            )
            
            # एनालिटिक्स लॉग करें
            db.analytics.insert_one({
                "type": "admin_action",
                "action": "clear_junk",
                "admin": user_id,
                "count": count,
                "timestamp": datetime.now()
            })
        
        elif data == "admin_global_stats":
            stats = db.get_stats()
            
            msg = (
                f"📊 *ग्लोबल स्टैट्स*\n\n"
                f"👥 *कुल यूजर्स:* {stats['total_users']}\n"
                f"✅ *एक्टिव:* {stats['active_users']}\n"
                f"🚫 *ब्लॉक:* {stats['blocked_users']}\n\n"
                f"💰 *कुल कमाई:* {format_balance(stats['total_earned'])}\n"
                f"💸 *कुल पेमेंट:* {format_balance(stats['total_paid'])}\n"
                f"📝 *पेंडिंग:* {stats['pending_withdrawals']}\n\n"
                f"📅 *आज जॉइन:* {stats['today_users']}"
            )
            
            await query.edit_message_text(msg, parse_mode='Markdown')
        
        elif data == "admin_withdrawals":
            pending = list(db.withdrawals.find({"status": "pending"}).sort("requested", -1).limit(10))
            
            if not pending:
                await query.edit_message_text("📝 कोई पेंडिंग विड्रॉल नहीं है")
                return
            
            msg = "📝 *पेंडिंग विड्रॉल (लास्ट 10)*\n\n"
            for w in pending:
                user = db.get_user(w["user_id"])
                name = user.get("full_name", "यूजर") if user else "डिलीट"
                msg += (
                    f"👤 *{name}* (`{w['user_id']}`)\n"
                    f"💰 रकम: `{format_balance(w['amount'])}`\n"
                    f"🏦 तरीका: `{w['method']}`\n"
                    f"📝 डिटेल्स: `{w['details'][:30]}`\n"
                    f"🕐 {w['requested'].strftime('%d %b %H:%M')}\n"
                    f"───────────────\n"
                )
            
            # एप्रूव/रिजेक्ट के लिए बटन
            keyboard = []
            for w in pending[:5]:  # सिर्फ 5 के लिए बटन
                w_id = str(w["_id"])
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ एप्रूव {w['user_id']}",
                        callback_data=f"approve_withdraw_{w_id}"
                    ),
                    InlineKeyboardButton(
                        f"❌ रिजेक्ट {w['user_id']}",
                        callback_data=f"reject_withdraw_{w_id}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("🔙 बैक", callback_data="admin_panel")])
            
            await query.edit_message_text(
                msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data.startswith("approve_withdraw_") or data.startswith("reject_withdraw_"):
            # विड्रॉल एप्रूव/रिजेक्ट
            parts = data.split("_")
            action = parts[0]
            w_id = parts[2]
            
            from bson.objectid import ObjectId
            withdrawal = db.withdrawals.find_one({"_id": ObjectId(w_id)})
            
            if not withdrawal:
                await query.edit_message_text("❌ विड्रॉल नहीं मिला")
                return
            
            if action == "approve":
                db.withdrawals.update_one(
                    {"_id": ObjectId(w_id)},
                    {"$set": {"status": "completed", "processed": datetime.now()}}
                )
                
                # यूजर को नोटिफिकेशन
                try:
                    await context.bot.send_message(
                        withdrawal["user_id"],
                        f"✅ *विड्रॉल एप्रूव!*\n\n"
                        f"आपकी {format_balance(withdrawal['amount'])} की रिक्वेस्ट एप्रूव हो गई है!\n"
                        f"जल्द ही पेमेंट कर दिया जाएगा।",
                        parse_mode='Markdown'
                    )
                except:
                    pass
                
                await query.edit_message_text(
                    f"✅ विड्रॉल एप्रूव किया गया!\n"
                    f"यूजर: {withdrawal['user_id']}\n"
                    f"रकम: {format_balance(withdrawal['amount'])}"
                )
            
            elif action == "reject":
                # बैलेंस वापस करें
                db.update_balance(
                    withdrawal["user_id"],
                    withdrawal["amount"],
                    "withdrawal_reject",
                    "विड्रॉल रिजेक्ट हुआ, बैलेंस वापस"
                )
                
                db.withdrawals.update_one(
                    {"_id": ObjectId(w_id)},
                    {"$set": {"status": "rejected", "processed": datetime.now()}}
                )
                
                # यूजर को नोटिफिकेशन
                try:
                    await context.bot.send_message(
                        withdrawal["user_id"],
                        f"❌ *विड्रॉल रिजेक्ट*\n\n"
                        f"आपकी {format_balance(withdrawal['amount'])} की रिक्वेस्ट रिजेक्ट हो गई।\n"
                        f"बैलेंस वापस कर दिया गया है।",
                        parse_mode='Markdown'
                    )
                except:
                    pass
                
                await query.edit_message_text(
                    f"❌ विड्रॉल रिजेक्ट किया गया!\n"
                    f"यूजर: {withdrawal['user_id']}\n"
                    f"रकम: {format_balance(withdrawal['amount'])}"
                )
        
        elif data == "admin_panel":
            # वापस एडमिन पैनल
            keyboard = [
                [InlineKeyboardButton("📢 ब्रॉडकास्ट", callback_data="admin_broadcast")],
                [InlineKeyboardButton("🗑️ क्लियर जंक", callback_data="admin_clear_junk")],
                [InlineKeyboardButton("📊 यूजर स्टैट्स", callback_data="admin_user_stats")],
                [InlineKeyboardButton("💰 बैलेंस ऐड/रिमूव", callback_data="admin_balance")],
                [InlineKeyboardButton("🚫 ब्लॉक/अनब्लॉक", callback_data="admin_block")],
                [InlineKeyboardButton("📈 ग्लोबल स्टैट्स", callback_data="admin_global_stats")],
                [InlineKeyboardButton("📝 पेंडिंग विड्रॉल", callback_data="admin_withdrawals")],
                [InlineKeyboardButton("📊 एनालिटिक्स", callback_data="admin_analytics")],
                [InlineKeyboardButton("🔄 डेटा क्लीनअप", callback_data="admin_cleanup")],
                [InlineKeyboardButton("❌ बंद करें", callback_data="admin_close")]
            ]
            
            await query.edit_message_text(
                "👑 *एडमिन पैनल*\n"
                "कृपया एक विकल्प चुनें:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "admin_close":
            await query.edit_message_text("👋 एडमिन पैनल बंद किया गया")
    
    @staticmethod
    async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ब्रॉडकास्ट मैसेज हैंडल करें"""
        if not is_admin(update.effective_user.id):
            return
        
        if context.user_data.get("admin_action") != "broadcast":
            return
        
        # कैंसल चेक करें
        if update.message.text == "/cancel":
            context.user_data.pop("admin_action", None)
            await update.message.reply_text("❌ ब्रॉडकास्ट कैंसल किया गया")
            return
        
        # सभी यूजर्स प्राप्त करें (सिर्फ अनब्लॉक)
        all_users = db.get_all_users(filter_blocked=True)
        total = len(all_users)
        
        if total == 0:
            await update.message.reply_text("❌ कोई यूजर नहीं मिला")
            context.user_data.pop("admin_action", None)
            return
        
        # प्रोसेसिंग मैसेज
        status_msg = await update.message.reply_text(
            f"📢 *ब्रॉडकास्ट शुरू*\n\n"
            f"कुल यूजर्स: {total}\n"
            f"भेजा जा रहा है... 0/{total}",
            parse_mode='Markdown'
        )
        
        # ब्रॉडकास्ट प्रोसेस
        sent = 0
        failed = 0
        blocked = 0
        
        for i, user in enumerate(all_users, 1):
            user_id = user["user_id"]
            
            try:
                # अलग-अलग टाइप के मैसेज हैंडल करें
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
                elif update.message.video:
                    await context.bot.send_video(
                        user_id,
                        update.message.video.file_id,
                        caption=update.message.caption
                    )
                elif update.message.document:
                    await context.bot.send_document(
                        user_id,
                        update.message.document.file_id,
                        caption=update.message.caption
                    )
                
                sent += 1
                
                # स्टेटस अपडेट (हर 10 यूजर पर)
                if i % 10 == 0:
                    await status_msg.edit_text(
                        f"📢 *ब्रॉडकास्ट*\n\n"
                        f"कुल: {total}\n"
                        f"✅ सफल: {sent}\n"
                        f"❌ फेल: {failed}\n"
                        f"🚫 ब्लॉक: {blocked}\n"
                        f"प्रोसेस: {i}/{total}",
                        parse_mode='Markdown'
                    )
                
                # API लिमिट के लिए स्लीप
                await asyncio.sleep(0.05)  # 20 मैसेज/सेकंड
                
            except Exception as e:
                if "bot was blocked" in str(e).lower() or "user is deactivated" in str(e).lower():
                    # यूजर ने ब्लॉक किया है
                    db.block_user(user_id, "ब्लॉक यूजर")
                    blocked += 1
                else:
                    failed += 1
                    logger.error(f"ब्रॉडकास्ट फेल {user_id}: {e}")
        
        # फाइनल रिपोर्ट
        await status_msg.edit_text(
            f"📢 *ब्रॉडकास्ट कम्पलीट*\n\n"
            f"✅ *सफल:* {sent}/{total}\n"
            f"🚫 *ब्लॉक यूजर:* {blocked}\n"
            f"❌ *अन्य एरर:* {failed}\n\n"
            f"ब्लॉक यूजर्स को डेटाबेस में मार्क कर दिया गया है।",
            parse_mode='Markdown'
        )
        
        # क्लियर स्टेटस
        context.user_data.pop("admin_action", None)
        
        # एनालिटिक्स
        db.analytics.insert_one({
            "type": "broadcast",
            "admin": update.effective_user.id,
            "total": total,
            "sent": sent,
            "blocked": blocked,
            "failed": failed,
            "timestamp": datetime.now()
        })
    
    @staticmethod
    async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """एडमिन टेक्स्ट कमांड हैंडल करें"""
        if not is_admin(update.effective_user.id):
            return
        
        text = update.message.text
        
        # बैलेंस ऐड/रिमूव कमांड
        if text.startswith("/add "):
            parts = text.split()
            if len(parts) >= 3:
                try:
                    user_id = int(parts[1])
                    amount = float(parts[2])
                    reason = " ".join(parts[3:]) if len(parts) > 3 else "एडमिन बोनस"
                    
                    new_balance = db.update_balance(user_id, amount, "admin_add", reason)
                    
                    await update.message.reply_text(
                        f"✅ *बैलेंस ऐड किया*\n\n"
                        f"यूजर: `{user_id}`\n"
                        f"रकम: `{format_balance(amount)}`\n"
                        f"नया बैलेंस: `{format_balance(new_balance)}`\n"
                        f"कारण: {reason}",
                        parse_mode='Markdown'
                    )
                    
                    # यूजर को नोटिफिकेशन
                    try:
                        await context.bot.send_message(
                            user_id,
                            f"🎁 *बोनस!*\n\n"
                            f"आपको ₹{amount} का बोनस मिला!\n"
                            f"कारण: {reason}",
                            parse_mode='Markdown'
                        )
                    except:
                        pass
                    
                except Exception as e:
                    await update.message.reply_text(f"❌ एरर: {e}")
        
        elif text.startswith("/remove "):
            parts = text.split()
            if len(parts) >= 3:
                try:
                    user_id = int(parts[1])
                    amount = float(parts[2])
                    
                    new_balance = db.update_balance(user_id, -amount, "admin_remove", "एडमिन ने हटाया")
                    
                    await update.message.reply_text(
                        f"✅ *बैलेंस हटाया*\n\n"
                        f"यूजर: `{user_id}`\n"
                        f"रकम: `{format_balance(amount)}`\n"
                        f"नया बैलेंस: `{format_balance(new_balance)}`",
                        parse_mode='Markdown'
                    )
                    
                except Exception as e:
                    await update.message.reply_text(f"❌ एरर: {e}")
        
        elif text.startswith("/block "):
            parts = text.split()
            if len(parts) >= 2:
                try:
                    user_id = int(parts[1])
                    reason = " ".join(parts[2:]) if len(parts) > 2 else "एडमिन द्वारा ब्लॉक"
                    
                    db.block_user(user_id, reason)
                    
                    await update.message.reply_text(
                        f"🚫 *यूजर ब्लॉक किया*\n\n"
                        f"यूजर: `{user_id}`\n"
                        f"कारण: {reason}",
                        parse_mode='Markdown'
                    )
                    
                except Exception as e:
                    await update.message.reply_text(f"❌ एरर: {e}")
        
        elif text.startswith("/unblock "):
            parts = text.split()
            if len(parts) >= 2:
                try:
                    user_id = int(parts[1])
                    
                    db.unblock_user(user_id)
                    
                    await update.message.reply_text(
                        f"✅ *यूजर अनब्लॉक किया*\n\n"
                        f"यूजर: `{user_id}`",
                        parse_mode='Markdown'
                    )
                    
                except Exception as e:
                    await update.message.reply_text(f"❌ एरर: {e}")
        
        elif text == "/stats":
            stats = db.get_stats()
            
            msg = (
                f"📊 *ग्लोबल स्टैट्स*\n\n"
                f"👥 *कुल यूजर्स:* {stats['total_users']}\n"
                f"✅ *एक्टिव:* {stats['active_users']}\n"
                f"🚫 *ब्लॉक:* {stats['blocked_users']}\n\n"
                f"💰 *कुल कमाई:* {format_balance(stats['total_earned'])}\n"
                f"💸 *कुल पेमेंट:* {format_balance(stats['total_paid'])}\n"
                f"📝 *पेंडिंग:* {stats['pending_withdrawals']}\n\n"
                f"📅 *आज जॉइन:* {stats['today_users']}"
            )
            
            await update.message.reply_text(msg, parse_mode='Markdown')
        
        elif text == "/admin":
            await AdminHandlers.admin_panel(update, context)
