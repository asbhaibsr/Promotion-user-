# ═══════════════════════════════════════════════════════════
# EarnZone / FilmyFund — Telegram Mini App
# Owner   : @asbhaibsr
# Channel : @asbhai_bsr
# Contact : https://t.me/asbhaibsr
# ⚠️  Unauthorized modification or redistribution prohibited.
# © 2025 @asbhaibsr — All Rights Reserved
# ═══════════════════════════════════════════════════════════

# ===== handlers.py (FULLY UPDATED) =====
# Changes:
# 1. start() — duplicate user check + notify referrer with user details
# 2. handle_group_message() — group pe movie search detect karo → daily earning credit karo
# 3. handle_log_channel_message() — already working, kept as is
# 4. Live activity pe daily search bhi dikhta hai

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
        self.bot = None
        logger.info("✅ Handlers initialized")

    # ========== START COMMAND ==========

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler — with duplicate referral check"""
        try:
            user = update.effective_user
            args = context.args

            referrer_id = None
            if args and args[0].startswith('ref_'):
                try:
                    referrer_id = int(args[0].replace('ref_', ''))
                    if referrer_id == user.id:
                        referrer_id = None  # self-refer nahi hoga
                except:
                    pass

            user_data = {
                'user_id': user.id,
                'first_name': user.first_name or "User",
                'username': user.username,
                'referrer_id': referrer_id
            }

            add_result = self.db.add_user(user_data)

            # ── DUPLICATE USER — already on bot ──────────────────────
            if isinstance(add_result, dict) and add_result.get('already_on_bot'):
                info = add_result
                uname = info.get('username', '')
                uname_txt = f"@{uname}" if uname else "No username"
                join_d = info.get('join_date', 'Unknown')
                act = info.get('active_refs', 0)
                bal = info.get('balance', 0)
                orig_ref_id = info.get('original_referrer_id')

                # Notify the person who tried to refer
                if referrer_id:
                    orig_txt = ""
                    if orig_ref_id and orig_ref_id != referrer_id:
                        orig_ref_user = self.db.get_user(orig_ref_id)
                        if orig_ref_user:
                            orig_name = orig_ref_user.get('first_name', 'Someone')
                            orig_txt = f"\n⚠️ Inhe pehle se **{orig_name}** ne refer kiya hua hai."

                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=(
                                f"⚠️ **Ye user pehle se bot pe hai!**\n\n"
                                f"👤 **Name:** {info.get('first_name', 'User')}\n"
                                f"🔗 **Username:** {uname_txt}\n"
                                f"📅 **Joined:** {join_d}\n"
                                f"👥 **Active refs:** {act}\n"
                                f"💰 **Balance:** ₹{bal:.2f}"
                                f"{orig_txt}\n\n"
                                f"❌ Ye user aapke referral se count **nahi** hoga.\n"
                                f"💡 Naye users share karo jo abhi tak bot pe nahi hain!"
                            ),
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logger.error(f"Could not notify referrer about duplicate: {e}")

                # Show app to returning user normally
                keyboard = [
                    [InlineKeyboardButton(
                        "📱 MINI APP KHOLO",
                        web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user.id}")
                    )],
                    [InlineKeyboardButton("🎬 MOVIE GROUP", url=self.config.MOVIE_GROUP_LINK)]
                ]
                await update.message.reply_text(
                    f"👋 Welcome back **{user.first_name}!**\n\nMini App kholo:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            is_new = bool(add_result)

            # ── NEW USER ──────────────────────────────────────────────
            if is_new:
                self.db.add_live_activity('join', user.id, 0, "Joined the bot")

                # Log to channel
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

                # Notify admins
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

                # Notify referrer
                if referrer_id:
                    try:
                        referrer = self.db.get_user(referrer_id)
                        if referrer and referrer.get('notify_referrals', True):
                            await context.bot.send_message(
                                chat_id=referrer_id,
                                text=(
                                    f"🎉 **Naya Referral!**\n\n"
                                    f"**{user.first_name}** aapke link se join kar liya!\n\n"
                                    f"✅ Jab wo Movie Group pe movie search karke shortlink complete karega,\n"
                                    f"aapka referral active ho jayega aur aapko **3 Passes + ₹{self.config.REFERRAL_BONUS} bonus** milega!\n\n"
                                    f"⏳ Abhi status: **Pending**"
                                ),
                                parse_mode=ParseMode.MARKDOWN
                            )
                    except Exception as e:
                        logger.error(f"Failed to notify referrer: {e}")

            # ── WELCOME MESSAGE (new + returning) ────────────────────
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

    # ========== GROUP MESSAGE HANDLER — Daily Search ==========

    async def handle_group_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Movie group pe messages detect karo.
        Jab koi referred user message bhejta hai (movie search):
        - record_daily_search() call karo
        - Sirf 1 baar per day credit hoga
        - Pending referrals wale users ke liye bhi track karo
          (unka credit tab milega jab referral activate ho)
        """
        try:
            message = update.message or update.channel_post
            if not message:
                return

            user = update.effective_user
            if not user:
                return

            chat = update.effective_chat
            if not chat or chat.type not in ['group', 'supergroup']:
                return

            # Sirf MOVIE_GROUP_ID pe handle karo agar configured hai
            if self.config.MOVIE_GROUP_ID:
                try:
                    if str(chat.id) != str(self.config.MOVIE_GROUP_ID):
                        return
                except:
                    pass

            # Ignore bots
            if user.is_bot:
                return

            # Ignore very short messages (commands etc.)
            msg_text = message.text or message.caption or ""
            if len(msg_text.strip()) < 2:
                return

            user_id = user.id
            logger.info(f"Group message from user {user_id} in {chat.id}")

            # Record daily search — sirf 1 baar per day credit hoga
            result = self.db.record_daily_search(user_id)

            if result.get('success'):
                referrer_id = result.get('referrer_id')
                earning = result.get('earning', 0.30)
                logger.info(f"✅ Daily search credited: user={user_id} referrer={referrer_id} +₹{earning}")

                # Notify referrer (optional — silent by default to avoid spam)
                # Uncomment if you want notification:
                # try:
                #     await context.bot.send_message(
                #         chat_id=referrer_id,
                #         text=f"💰 {user.first_name} ne aaj movie search ki! +₹{earning}"
                #     )
                # except:
                #     pass

            elif result.get('reason') == 'already_credited_today':
                logger.info(f"Already credited today for user {user_id}")
            elif result.get('reason') == 'no_active_referral':
                logger.info(f"No active referral for user {user_id} — pending or no referral")

        except Exception as e:
            logger.error(f"Group message handler error: {e}")

    # ========== LOG CHANNEL HANDLER ==========

    async def handle_log_channel_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Log channel se messages detect karo.

        FORMAT 1 — #NewUser (new user joined via referral):
            #NewUser
            ID - 8098997823
            Nᴀᴍᴇ - Sandip

        FORMAT 2 — #Verifyshortlink (user completed shortlink):
            #Verifyshortlink
            ID - 8098997823
            Nᴀᴍᴇ - Sandip

        FORMAT 3 — ✅ Shortlink Verified (alternate format):
            ✅ Shortlink Verified
            👤 Sandip (8098997823)
            🔗 softurl.in
        """
        try:
            message = update.channel_post or update.message
            if not message:
                return

            chat_id = message.chat.id
            if str(chat_id) != str(LOG_CHANNEL_ID):
                logger.debug(f"Ignoring chat {chat_id} (expected {LOG_CHANNEL_ID})")
                return

            text = (message.text or message.caption or "").strip()
            if not text:
                return

            logger.info(f"📨 Log channel msg: {text[:80]}")

            # Detect message type
            has_newuser      = '#NewUser' in text or 'NewUser' in text
            has_verifyshort  = '#Verifyshortlink' in text or 'Verifyshortlink' in text or '#Verify' in text
            has_shortlink_v  = 'Shortlink Verified' in text or '✅ Shortlink' in text

            if has_newuser or has_verifyshort or has_shortlink_v:
                user_id, name = self._parse_id_and_name(text)
                if not user_id:
                    logger.warning(f"Could not parse user_id from: {text[:100]}")
                    return

                logger.info(f"✅ Parsed: user_id={user_id} name={name} type={'NewUser' if has_newuser else 'Verify'}")

                # Both types: try activate referral first, then record daily search
                await self._process_log_event(user_id, name, has_newuser, context)
            else:
                logger.debug(f"Unrecognized log message: {text[:60]}")

        except Exception as e:
            logger.error(f"Log channel handler error: {e}", exc_info=True)

    def _parse_id_and_name(self, text):
        """
        Parse user_id and name from log channel message.
        Handles formats:
          ID - 8098997823 / Nᴀᴍᴇ - Sandip
          👤 Sandip (8098997823)
        Returns (user_id, name) or (None, None)
        """
        import re
        user_id = None
        name = "User"
        lines = [l.strip() for l in text.split('\n')]

        for line in lines:
            # Format: ID - 1234567890 or ID: 1234567890
            if re.match(r'^ID\s*[-:]\s*\d', line, re.IGNORECASE):
                m = re.search(r'(\d{6,12})', line)
                if m:
                    try: user_id = int(m.group(1))
                    except: pass

            # Name line: Nᴀᴍᴇ - Sandip or Name - Sandip
            if re.match(r'^N[^\s]*\s*[-:]\s*', line, re.IGNORECASE) and 'ID' not in line.upper():
                parts = re.split(r'[-:]', line, 1)
                if len(parts) == 2:
                    name = parts[1].strip() or "User"

            # Format: 👤 Name (1234567890)
            if '👤' in line:
                m = re.search(r'\((\d{6,12})\)', line)
                if m:
                    try: user_id = int(m.group(1))
                    except: pass
                name_part = line.replace('👤','').strip()
                name_part = re.sub(r'\(\d+\)', '', name_part).strip()
                if name_part: name = name_part

        # Fallback: any 7-12 digit number
        if not user_id:
            nums = re.findall(r'\b(\d{7,12})\b', text)
            if nums:
                try: user_id = int(nums[0])
                except: pass

        return user_id, name

    async def _process_log_event(self, user_id, name, is_new_user, context):
        """Handle both NewUser and Verifyshortlink events"""
        # 1. Get or check user in DB
        user = self.db.get_user(user_id)
        if not user:
            logger.warning(f"User {user_id} not in DB yet — may join bot later")
            return

        # 2. Try to activate referral (works for both first-time and subsequent)
        ref_result = self.db.activate_referral_by_log_channel(user_id)

        if ref_result and ref_result.get('activated'):
            # First time activation!
            referrer_id   = ref_result.get('referrer_id')
            referrer_name = ref_result.get('referrer_name', 'Unknown')

            logger.info(f"✅ Referral activated: {user_id} ({name}) → {referrer_id}")

            # Notify referrer
            if referrer_id:
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=(
                            f"🎉 **Referral Active Ho Gaya!**\n\n"
                            f"👤 **User:** {name}\n"
                            f"✅ Verification complete!\n\n"
                            f"🎟️ **+3 Passes** aur **₹{self.config.REFERRAL_BONUS}** add ho gaya!\n\n"
                            f"💡 Ab jab bhi ye user movie search karega,\n"
                            f"aapko **₹{self.config.DAILY_REFERRAL_EARNING} daily** milega!"
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
                        f"✅ **Aap Verify Ho Gaye!**\n\n"
                        f"Shortlink complete ho gayi!\n"
                        f"Aapke referrer **{referrer_name}** ko bonus mil gaya.\n\n"
                        f"📱 Mini App kholo aur daily earning shuru karo!"
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Could not notify user {user_id}: {e}")

        else:
            # Already active — record daily search
            reason = ref_result.get('reason', '') if ref_result else 'no_result'
            logger.info(f"Referral already active for {user_id} ({reason}) — recording daily search")

            search_result = self.db.record_daily_search(user_id)
            if search_result.get('success'):
                referrer_id = search_result.get('referrer_id')
                earning     = search_result.get('earning', self.config.DAILY_REFERRAL_EARNING)
                logger.info(f"✅ Daily search: user={user_id} referrer={referrer_id} +₹{earning}")

                if referrer_id:
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=(
                                f"💰 **Daily Earning!**\n\n"
                                f"👤 {name} ne aaj movie search ki!\n"
                                f"✅ +₹{earning} aapke account mein add ho gaya!"
                            ),
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logger.error(f"Could not notify referrer {referrer_id}: {e}")

            elif search_result.get('reason') == 'already_credited_today':
                logger.info(f"Already credited today for {user_id}")
            else:
                logger.info(f"No active referral for {user_id}: {search_result.get('reason','')}")

    def _parse_shortlink_url(self, text):
        """Parse shortlink URL from message"""
        import re
        for line in text.split('\n'):
            if '🔗' in line or 'softurl' in line.lower():
                m = re.search(r'[\w\-\.]+\.(?:in|com|net|link|io)\S*', line)
                if m: return m.group(0)
                parts = line.replace('🔗','').strip()
                if parts: return parts
        return 'shortlink'

    async def _handle_shortlink_verified(self, text, context):
        """Handle ✅ Shortlink Verified format (alternate)"""
        user_id, name = self._parse_id_and_name(text)
        if not user_id:
            logger.warning(f"Shortlink Verified: could not parse user_id from: {text[:100]}")
            return
        await self._process_log_event(user_id, name, False, context)

    async def _handle_new_user_log(self, text, context):
        """Handle #NewUser format"""
        user_id, name = self._parse_id_and_name(text)
        if not user_id:
            logger.warning(f"#NewUser: could not parse from: {text[:100]}")
            return
        await self._process_log_event(user_id, name, True, context)

    def _parse_shortlink_url(self, text):
        """Parse shortlink URL from message"""
        import re
        lines = text.split('\n')
        for line in lines:
            if '🔗' in line or 'softurl' in line.lower() or '.in' in line:
                # Extract URL-like string
                m = re.search(r'[\w\-\.]+\.(?:in|com|net|link|io)\S*', line)
                if m:
                    return m.group(0)
                parts = line.replace('🔗','').strip()
                if parts:
                    return parts
        return 'shortlink'

    async def _handle_shortlink_verified(self, text, context):
        """
        Handle ✅ Shortlink Verified message from log channel.
        This fires when a user completes a shortlink (movie search verification).
        Use this for BOTH:
          1. Initial activation (first shortlink = referral activate)
          2. Daily search tracking (subsequent shortlinks = ₹0.30 per day)
        """
        import re
        user_id = self._parse_user_id_from_shortlink(text)
        if not user_id:
            logger.warning(f"Shortlink Verified: could not parse user_id from: {text[:120]}")
            return

        shortlink_url = self._parse_shortlink_url(text)
        logger.info(f"🔗 Shortlink Verified: user_id={user_id} url={shortlink_url}")

        user = self.db.get_user(user_id)
        if not user:
            logger.warning(f"Shortlink Verified: user {user_id} not found in DB")
            return

        # ── Step 1: Try to activate referral (first time) ────────
        ref_result = self.db.activate_referral_by_log_channel(user_id)

        if ref_result and ref_result.get('activated'):
            # FIRST TIME — referral now active!
            referrer_id = ref_result.get('referrer_id')
            referred_name = ref_result.get('referred_name', user.get('first_name', 'User'))
            referrer_name = ref_result.get('referrer_name', 'Unknown')

            logger.info(f"✅ Referral ACTIVATED via shortlink: {user_id} → {referrer_id}")

            # Notify referrer
            if referrer_id:
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=(
                            f"🎉 **Referral Active Ho Gaya!**\n\n"
                            f"👤 **User:** {referred_name}\n"
                            f"🔗 **Shortlink:** {shortlink_url}\n"
                            f"✅ Verification complete!\n\n"
                            f"🎟️ **+3 Passes** aur **₹{self.config.REFERRAL_BONUS}** aapke account mein add ho gaya!\n\n"
                            f"💡 Ab jab bhi ye user movie search karega,\n"
                            f"aapko **₹{self.config.DAILY_REFERRAL_EARNING} daily** milega!"
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
                        f"✅ **Aap Verify Ho Gaye!**\n\n"
                        f"Shortlink complete ho gayi!\n"
                        f"Aapke referrer **{referrer_name}** ko bonus mil gaya.\n\n"
                        f"📱 Mini App kholo aur daily earning shuru karo!"
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Could not notify user {user_id}: {e}")

        else:
            # ── Step 2: Already active — record daily search ──────
            reason = ref_result.get('reason', '') if ref_result else ''
            logger.info(f"Shortlink for already-active user {user_id}: {reason}")

            # Record as daily search (for ₹0.30 earning to referrer)
            search_result = self.db.record_daily_search(user_id)

            if search_result.get('success'):
                referrer_id = search_result.get('referrer_id')
                earning = search_result.get('earning', self.config.DAILY_REFERRAL_EARNING)
                logger.info(f"✅ Daily search via shortlink: user={user_id} referrer={referrer_id} +₹{earning}")

                # Notify referrer about daily earning (optional but helpful)
                if referrer_id:
                    try:
                        uname = user.get('first_name', 'User')
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=(
                                f"💰 **Daily Earning!**\n\n"
                                f"👤 {uname} ne aaj movie search ki!\n"
                                f"🔗 {shortlink_url}\n"
                                f"✅ +₹{earning} aapke account mein add ho gaya!"
                            ),
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logger.error(f"Could not notify referrer {referrer_id}: {e}")

            elif search_result.get('reason') == 'already_credited_today':
                logger.info(f"Already credited today for user {user_id} via shortlink")
            elif search_result.get('reason') == 'no_active_referral':
                # User has no referral — but still record for future
                logger.info(f"No active referral for shortlink user {user_id}")

    async def _handle_new_user_log(self, text, context):
        """Handle old #NewUser format from log channel (backup)"""
        user_id = None
        for line in text.split('\n'):
            line = line.strip()
            if line.upper().startswith('ID'):
                parts = line.split('-', 1)
                if len(parts) == 2:
                    try:
                        user_id = int(parts[1].strip())
                    except:
                        pass
                break

        if not user_id:
            logger.warning(f"#NewUser: could not parse user_id from: {text[:100]}")
            return

        logger.info(f"🔔 Log channel #NewUser: user_id={user_id}")
        user = self.db.get_user(user_id)
        if not user:
            return

        result = self.db.activate_referral_by_log_channel(user_id)
        if result and result.get('activated'):
            referrer_id = result.get('referrer_id')
            referred_name = result.get('referred_name', user.get('first_name', 'User'))
            referrer_name = result.get('referrer_name', 'Unknown')

            if referrer_id:
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=(
                            f"🎉 **Referral Active Ho Gaya!**\n\n"
                            f"👤 **User:** {referred_name}\n"
                            f"✅ Verification complete!\n\n"
                            f"🎟️ **+3 Passes** aur **₹{self.config.REFERRAL_BONUS}** add ho gaya!"
                        ),
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass

            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ Verify ho gaye! Referrer **{referrer_name}** ko bonus mila.\n\nMini App kholo!",
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass

    # ========== OTHER COMMANDS ==========

    async def open_app(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        keyboard = [[InlineKeyboardButton(
            "📱 MINI APP KHOLO",
            web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user.id}")
        )]]
        await update.message.reply_text(
            "Neeche click karo Mini App kholne ke liye:",
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
                    f"Total Earned: ₹{user.get('total_earned', 0):.2f}\n"
                    f"Aaj Kamaya: ₹{user.get('today_earned', 0):.2f}\n\n"
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
                "4️⃣ Tumhara referral active! **3 Passes + ₹ bonus** milega\n"
                "5️⃣ Har roz dost movie search kare → tumhe **₹0.30 daily** milega!\n\n"
                "**⚠️ Rules:**\n"
                "• Sirf apne referrals ki activity se earning hoti hai\n"
                "• 1 user = 1 search per day = ₹0.30\n"
                "• Fake activity = withdrawal band\n"
                "• Admin sab check karta hai\n\n"
                f"**Support:** {self.config.SUPPORT_USERNAME}"
            )
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Help error: {e}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle private messages"""
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

    # ========== DAILY REMINDER ==========

    async def send_daily_reminders(self, context):
        """
        Roz evening (7-10 PM) mein users ko reminder bheja jata hai
        jo bonus/missions claim nahi kiye hain.
        Job scheduler se call hoti hai.
        """
        try:
            pending_users = self.db.get_pending_reminders()
            if not pending_users:
                logger.info("No pending reminder users")
                return

            webapp_url = self.config.WEBAPP_URL
            sent = 0
            failed = 0

            for u in pending_users:
                uid = u['user_id']
                name = u.get('first_name', 'User')
                try:
                    keyboard = [[InlineKeyboardButton(
                        "📱 Mini App Kholo",
                        web_app=WebAppInfo(url=f"{webapp_url}/?user_id={uid}")
                    )]]
                    await context.bot.send_message(
                        chat_id=uid,
                        text=(
                            f"⏰ **{name}, aaj ka kaam baaki hai!**\n\n"
                            f"🎁 **Daily Bonus** claim nahi kiya — claim karo aur streak badhao!\n"
                            f"🎯 **Daily Missions** complete karo → 600+ pts kamao!\n"
                            f"💎 **Sponsored Offers** dekho — free pts!\n\n"
                            f"👥 Refer karo dosto ko → 60 pts + 3 Passes turant!\n\n"
                            f"⚡ Raat ko aur late mat karo — streak toot jayegi!"
                        ),
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode=ParseMode.MARKDOWN
                    )
                    self.db.mark_user_reminded(uid)
                    sent += 1
                    import asyncio
                    await asyncio.sleep(0.05)  # rate limit
                except Exception as e:
                    failed += 1
                    logger.error(f"Reminder failed for {uid}: {e}")

            logger.info(f"✅ Daily reminders sent: {sent}, failed: {failed}")

        except Exception as e:
            logger.error(f"Daily reminder error: {e}")
