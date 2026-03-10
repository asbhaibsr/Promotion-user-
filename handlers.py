# ===== handlers.py (FIXED - LOG CHANNEL VERIFY + NO MOVIE SEARCH + PASSES=1) =====

import logging
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

LOG_CHANNEL_ID = -1002352329534  # Your log channel

class Handlers:
    def __init__(self, config, db):
        self.config = config
        self.db = db
        self.bot = None  # Set after bot init
        logger.info("✅ Handlers initialized")

    # ========== MAIN COMMANDS ==========

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        try:
            user = update.effective_user
            args = context.args

            referrer_id = None
            if args and args[0].startswith('ref_'):
                try:
                    referrer_id = int(args[0].replace('ref_', ''))
                    if referrer_id == user.id:
                        referrer_id = None
                except:
                    pass

            user_data = {
                'user_id': user.id,
                'first_name': user.first_name or "User",
                'username': user.username,
                'referrer_id': referrer_id
            }

            is_new = self.db.add_user(user_data)

            if is_new:
                self.db.add_live_activity('join', user.id, 0, "Joined the bot")

                if self.config.LOG_CHANNEL_ID:
                    try:
                        referrer_name = "Direct"
                        if referrer_id:
                            ref_user = self.db.get_user(referrer_id)
                            if ref_user:
                                rname = ref_user.get('first_name', '')
                                rusername = ref_user.get('username', '')
                                referrer_name = f"{rname} (@{rusername})" if rusername else rname

                        log_text = (
                            f"👤 **NEW USER JOINED**\n\n"
                            f"**Name:** {user.first_name}\n"
                            f"**User ID:** `{user.id}`\n"
                            f"**Username:** @{user.username if user.username else 'N/A'}\n"
                            f"**Referred by:** {referrer_name}\n"
                            f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        await context.bot.send_message(
                            chat_id=self.config.LOG_CHANNEL_ID,
                            text=log_text,
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logger.error(f"Log channel error: {e}")

                for admin_id in self.config.ADMIN_IDS:
                    try:
                        keyboard = [[InlineKeyboardButton("👤 VIEW USER", callback_data=f"user_details_{user.id}")]]
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=(
                                f"👤 **New User Joined!**\n\n"
                                f"Name: {user.first_name}\n"
                                f"ID: `{user.id}`\n"
                                f"Referred by: {referrer_id if referrer_id else 'Direct'}"
                            ),
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except:
                        pass

                if referrer_id:
                    try:
                        referrer = self.db.get_user(referrer_id)
                        if referrer:
                            notify = referrer.get('notify_referrals', True)
                            if notify:
                                await context.bot.send_message(
                                    chat_id=referrer_id,
                                    text=(
                                        f"🎉 **Naya Referral!**\n\n"
                                        f"**{user.first_name}** aapke link se join kar liya!\n\n"
                                        f"✅ Jab wo Log Channel pe shortlink complete karega,\n"
                                        f"aapka referral active ho jayega aur aapko **3 passes + ₹ bonus** milega!"
                                    ),
                                    parse_mode=ParseMode.MARKDOWN
                                )
                    except Exception as e:
                        logger.error(f"Failed to notify referrer: {e}")

            welcome_text = (
                f"🎬 **Welcome {user.first_name}!**\n\n"
                f"👇 Neeche click karke Mini App kholo:"
            )

            keyboard = [
                [InlineKeyboardButton(
                    "📱 MINI APP KHOLO",
                    web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user.id}")
                )],
                [InlineKeyboardButton(
                    "🎬 MOVIE GROUP JOIN KARO",
                    url=self.config.MOVIE_GROUP_LINK
                )]
            ]

            await update.message.reply_text(
                welcome_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )

            ref_link = f"https://t.me/{self.config.BOT_USERNAME}?start=ref_{user.id}"
            await update.message.reply_text(
                f"🔗 **Aapka Referral Link:**\n`{ref_link}`\n\n"
                f"📢 Share karo aur passes + paise kamao!",
                parse_mode=ParseMode.MARKDOWN
            )

        except Exception as e:
            logger.error(f"Start command error: {e}")
            await update.message.reply_text("❌ Error. Please /start dobara try karo.")

    # ========== LOG CHANNEL MESSAGE HANDLER ==========

    async def handle_log_channel_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Log channel se #NewUser message detect karo aur referral activate karo.
        Expected format:
            #NewUser
            ID - 123456789
            Nᴀᴍᴇ - username
        """
        try:
            message = update.channel_post or update.message
            if not message:
                return

            chat_id = message.chat.id
            if chat_id != LOG_CHANNEL_ID:
                return

            text = message.text or ""
            if "#NewUser" not in text:
                return

            # Parse user ID from message
            user_id = None
            for line in text.split('\n'):
                line = line.strip()
                if line.startswith('ID'):
                    parts = line.split('-', 1)
                    if len(parts) == 2:
                        try:
                            user_id = int(parts[1].strip())
                        except:
                            pass
                    break

            if not user_id:
                logger.warning(f"Could not parse user_id from log channel message: {text[:100]}")
                return

            logger.info(f"🔔 Log channel #NewUser detected: user_id={user_id}")

            # Check if user exists in our DB
            user = self.db.get_user(user_id)
            if not user:
                logger.warning(f"User {user_id} not found in DB for log channel verify")
                return

            # Activate referral if exists and not already active
            result = self.db.activate_referral_by_log_channel(user_id)

            if result and result.get('activated'):
                referrer_id = result.get('referrer_id')
                referrer = self.db.get_user(referrer_id) if referrer_id else None

                referrer_name = "Unknown"
                if referrer:
                    referrer_name = referrer.get('first_name', 'Unknown')

                user_name = user.get('first_name', 'User')

                logger.info(f"✅ Referral activated: {user_id} referred by {referrer_id}")

                # Notify referrer
                if referrer_id:
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=(
                                f"🎉 **Referral Active Ho Gaya!**\n\n"
                                f"👤 **User:** {user_name}\n"
                                f"✅ Shortlink complete ho gayi!\n\n"
                                f"🎟️ **+3 Passes** aur **₹ bonus** aapke account mein add ho gaya!"
                            ),
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logger.error(f"Could not notify referrer {referrer_id}: {e}")

                # Notify new user
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=(
                            f"✅ **Verify Ho Gaye!**\n\n"
                            f"Aap successfully verify ho gaye hain!\n"
                            f"Aapke referrer **{referrer_name}** ko bonus mil gaya.\n\n"
                            f"📱 Mini App kholo aur earning shuru karo!"
                        ),
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    logger.error(f"Could not notify user {user_id}: {e}")

            else:
                logger.info(f"Referral for {user_id} already active or no referrer found")

        except Exception as e:
            logger.error(f"Log channel handler error: {e}")

    async def open_app(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        keyboard = [[InlineKeyboardButton(
            "📱 MINI APP KHOLO",
            web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user.id}")
        )]]
        await update.message.reply_text(
            "Neeche click karo FilmyFund Mini App kholne ke liye:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def check_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            user = self.db.get_user(user_id)
            if user:
                daily_potential = user.get('active_refs', 0) * self.config.DAILY_REFERRAL_EARNING
                text = (
                    f"💰 **Aapka Balance**\n\n"
                    f"Available: ₹{user.get('balance', 0):.2f}\n"
                    f"Total Earned: ₹{user.get('total_earned', 0):.2f}\n\n"
                    f"👥 **Referrals**\n"
                    f"Active: {user.get('active_refs', 0)}\n"
                    f"Pending: {user.get('pending_refs', 0)}\n"
                    f"Daily Potential: ₹{daily_potential:.2f}\n\n"
                    f"🏆 **Tier:** {self.config.get_tier_name(user.get('tier', 1))}"
                )
            else:
                text = "Pehle /start use karo"
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Balance error: {e}")

    async def show_referrals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            user = self.db.get_user(user_id)
            if user:
                ref_link = f"https://t.me/{self.config.BOT_USERNAME}?start=ref_{user_id}"
                daily_earning = user.get('active_refs', 0) * self.config.DAILY_REFERRAL_EARNING
                text = (
                    f"👥 **Aapke Referrals**\n\n"
                    f"Total: {user.get('total_refs', 0)}\n"
                    f"Active: {user.get('active_refs', 0)}\n"
                    f"Pending: {user.get('pending_refs', 0)}\n\n"
                    f"💰 **Daily Earnings:** ₹{daily_earning:.2f}\n\n"
                    f"🔗 **Aapka Link:**\n`{ref_link}`"
                )
            else:
                text = "Pehle /start use karo"
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Referrals error: {e}")

    async def withdraw_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            user = self.db.get_user(user_id)
            if not user:
                await update.message.reply_text("Pehle /start use karo")
                return
            balance = user.get('balance', 0)
            if balance < self.config.MIN_WITHDRAWAL:
                await update.message.reply_text(
                    f"❌ Minimum withdrawal ₹{self.config.MIN_WITHDRAWAL} hai\n"
                    f"Aapka balance: ₹{balance:.2f}\n\nAur friends refer karo!"
                )
                return
            keyboard = [[InlineKeyboardButton(
                "💸 WITHDRAW NOW",
                web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user_id}&page=withdraw")
            )]]
            await update.message.reply_text(
                f"💰 Balance: ₹{balance:.2f}\nNeeche click karo:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Withdraw cmd error: {e}")

    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            text = (
                "❓ **Help & FAQ**\n\n"
                "**Commands:**\n"
                "/start - Bot start karo\n"
                "/app - Mini App kholo\n"
                "/balance - Balance check karo\n"
                "/referrals - Referrals dekho\n"
                "/withdraw - Paise nikalo\n"
                "/help - Ye message\n\n"
                "**Paise Kaise Kamayein:**\n"
                "1️⃣ Apna referral link share karo\n"
                "2️⃣ Dost bot join kare aur Movie Group pe movie search kare\n"
                "3️⃣ Dost Movie Bot pe shortlink complete kare\n"
                "4️⃣ Tumhara referral active! **3 Passes + ₹ bonus** milega\n\n"
                "**⚠️ Rules:**\n"
                "• Sirf apne referrals ki activity se earning hoti hai\n"
                "• Fake activity = withdrawal band\n"
                "• Admin sab check karta hai\n\n"
                f"**Support:** {self.config.SUPPORT_USERNAME}"
            )
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Help error: {e}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle private messages only (movie search system removed)"""
        try:
            user = update.effective_user
            chat = update.effective_chat
            message = update.message
            if not user or not message:
                return
            message_text = message.text or ""
            if chat.type == 'private':
                if message_text.lower() in ['hi', 'hello', 'hey', 'hii', 'helo']:
                    await message.reply_text(
                        f"Namaskar {user.first_name}! 🙏\n"
                        f"/start use karo earning shuru karne ke liye!\n"
                        f"Ya Mini App kholo: {self.config.WEBAPP_URL}/?user_id={user.id}"
                    )
        except Exception as e:
            logger.error(f"Message handler error: {e}")

    async def handle_webapp_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            web_app_data = update.effective_message.web_app_data
            if not web_app_data:
                return
            user = update.effective_user
            data = json.loads(web_app_data.data)
            action = data.get('action')
            response = {'success': False, 'message': 'Unknown action'}
            if action == 'support':
                response = await self.process_support_message(data, context)
            await update.effective_message.reply_text(text=json.dumps(response))
        except Exception as e:
            logger.error(f"WebApp data error: {e}")

    async def process_support_message(self, data, context=None):
        try:
            user_id = data.get('user_id')
            message = data.get('message')
            if not user_id or not message:
                return {'success': False, 'message': 'Missing data'}
            msg_id = self.db.add_support_message(user_id, message)
            if msg_id:
                if context:
                    for admin_id in self.config.ADMIN_IDS:
                        try:
                            keyboard = [[InlineKeyboardButton("📩 VIEW MESSAGE", callback_data=f"view_support_{msg_id}")]]
                            await context.bot.send_message(
                                chat_id=admin_id,
                                text=(
                                    f"📩 **New Support Message**\n\n"
                                    f"User ID: `{user_id}`\n"
                                    f"Message: {message[:100]}"
                                ),
                                reply_markup=InlineKeyboardMarkup(keyboard),
                                parse_mode=ParseMode.MARKDOWN
                            )
                        except:
                            pass
                return {'success': True, 'message': 'Message sent to support'}
            return {'success': False, 'message': 'Failed to send message'}
        except Exception as e:
            logger.error(f"Support message error: {e}")
            return {'success': False, 'message': str(e)}
