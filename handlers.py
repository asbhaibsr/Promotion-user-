# ═══════════════════════════════════════════════════════════
# EarnZone / FilmyFund — Telegram Mini App
# Owner   : @asbhaibsr
# ⚠️  Unauthorized modification or redistribution prohibited.
# © 2025 @asbhaibsr — All Rights Reserved
# ═══════════════════════════════════════════════════════════

# ===== handlers.py — LOG CHANNEL VERIFY COMPLETELY FIXED =====
#
# ASLI PROBLEM THI:
#   1. bot_app.run_polling() mein channel_post allowed_updates nahi tha
#   2. Handler filter sahi nahi tha channel posts ke liye
#   3. ID parsing Unicode small caps handle nahi karta tha properly
#
# FIXES:
#   ✅ Log channel pe #VerifyComplete → referral activate
#   ✅ Log channel pe #FileSent → referral activate  
#   ✅ Log channel pe #NewUser → SIRF log, activate NAHI
#   ✅ Unicode ID parse (ɪᴅ - 7142838312)
#   ✅ Normal ID parse (ID - 7142838312)
#   ✅ Bracket ID parse (As Name (7142838312))
#   ✅ Referrer ko notify — jab referred user group pe aaye
#   ✅ Referral active hone pe dono users ko message

import logging
import re
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

# ⚠️ APNA LOG CHANNEL ID YAHAN DAALO
LOG_CHANNEL_ID = -1002352329534


class Handlers:
    def __init__(self, config, db):
        self.config = config
        self.db = db
        self.bot = None
        self._group_notified = {}  # user_id -> last_notify_timestamp
        logger.info("✅ Handlers initialized")

    # ══════════════════════════════════════════════════════════════
    # START COMMAND
    # ══════════════════════════════════════════════════════════════

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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

            add_result = self.db.add_user(user_data)

            # ── Duplicate user ──
            if isinstance(add_result, dict) and add_result.get('already_on_bot'):
                info = add_result
                uname = info.get('username', '')
                uname_txt = f"@{uname}" if uname else "No username"
                orig_ref_id = info.get('original_referrer_id')

                if referrer_id:
                    orig_txt = ""
                    if orig_ref_id and orig_ref_id != referrer_id:
                        orig_ref_user = self.db.get_user(orig_ref_id)
                        if orig_ref_user:
                            orig_name = orig_ref_user.get('first_name', 'Someone')
                            orig_txt = f"\n⚠️ Inhe pehle se *{orig_name}* ne refer kiya hua hai."
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=(
                                f"⚠️ *Ye user pehle se bot pe hai!*\n\n"
                                f"👤 Name: {info.get('first_name', 'User')}\n"
                                f"🔗 Username: {uname_txt}\n"
                                f"📅 Joined: {info.get('join_date', 'Unknown')}\n"
                                f"👥 Active refs: {info.get('active_refs', 0)}\n"
                                f"💰 Balance: ₹{info.get('balance', 0):.2f}"
                                f"{orig_txt}\n\n"
                                f"❌ Ye user aapke referral se count *nahi* hoga.\n"
                                f"💡 Naye users share karo!"
                            ),
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logger.error(f"Notify referrer duplicate: {e}")

                keyboard = [
                    [InlineKeyboardButton("📱 MINI APP KHOLO",
                        web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user.id}"))],
                    [InlineKeyboardButton("🎬 MOVIE GROUP", url=self.config.MOVIE_GROUP_LINK)]
                ]
                await update.message.reply_text(
                    f"👋 Welcome back *{user.first_name}!*\n\nMini App kholo:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            is_new = bool(add_result)

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
                        await context.bot.send_message(
                            chat_id=self.config.LOG_CHANNEL_ID,
                            text=(
                                f"👤 *NEW USER JOINED*\n\n"
                                f"Name: {user.first_name}\n"
                                f"ID: `{user.id}`\n"
                                f"Username: @{user.username if user.username else 'N/A'}\n"
                                f"Referred by: {referrer_name}\n"
                                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                            ),
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logger.error(f"Log channel new user error: {e}")

                # Notify admins
                for admin_id in self.config.ADMIN_IDS:
                    try:
                        kb = [[InlineKeyboardButton("👤 VIEW USER", callback_data=f"user_details_{user.id}")]]
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=(
                                f"👤 *New User!*\nName: {user.first_name}\n"
                                f"ID: `{user.id}`\nRef by: {referrer_id or 'Direct'}"
                            ),
                            reply_markup=InlineKeyboardMarkup(kb),
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
                                    f"🎉 *Naya Referral!*\n\n"
                                    f"*{user.first_name}* aapke link se join kar liya!\n\n"
                                    f"📋 *Ab kya karna hai:*\n"
                                    f"1️⃣ Inhe Movie Group pe jaane kaho\n"
                                    f"2️⃣ Koi bhi movie search kare\n"
                                    f"3️⃣ Movie bot ka shortlink complete kare\n\n"
                                    f"✅ Shortlink complete = *Referral Active!*\n"
                                    f"🎁 Aapko milega: *3 Passes + ₹{self.config.REFERRAL_BONUS}*\n\n"
                                    f"⏳ Status: *Pending*"
                                ),
                                parse_mode=ParseMode.MARKDOWN
                            )
                    except Exception as e:
                        logger.error(f"Notify referrer on join: {e}")

            # Welcome message
            ref_link = f"https://t.me/{self.config.BOT_USERNAME}?start=ref_{user.id}"
            movie_group = getattr(self.config, 'MOVIE_GROUP_LINK', 'https://t.me/all_movies_webseries_is_here')

            if referrer_id and is_new:
                welcome_text = (
                    f"🎬 *FilmyFund mein Swagat Hai, {user.first_name}!*\n\n"
                    f"✅ Aap referral se aaye hain!\n\n"
                    f"📌 *3 Steps mein Earning:*\n\n"
                    f"*Step 1️⃣* → 🎬 MOVIE GROUP join karo\n"
                    f"*Step 2️⃣* → Koi bhi movie search karo (jaise: Pushpa 2)\n"
                    f"*Step 3️⃣* → Movie bot jo link bheje — kholo aur 10 sec wait karo\n\n"
                    f"✅ *Reward:*\n"
                    f"• 50 pts turant! 🎁\n"
                    f"• Roz search = 30 pts daily 💰\n"
                    f"• Games = aur zyada! 🎮"
                )
                keyboard = [
                    [InlineKeyboardButton("🎬 MOVIE GROUP JOIN KARO", url=movie_group)],
                    [InlineKeyboardButton("📱 MINI APP", web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user.id}"))],
                ]
                await update.message.reply_text(
                    welcome_text, reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN
                )
                # 2hr auto reminder
                try:
                    import asyncio
                    async def _remind_2hr():
                        await asyncio.sleep(7200)
                        try:
                            if not self.db.referrals.find_one({'referred_id': user.id, 'is_active': True}):
                                kb = [[InlineKeyboardButton("🎬 MOVIE SEARCH KARO!", url=movie_group)]]
                                await context.bot.send_message(
                                    chat_id=user.id,
                                    text=(
                                        f"⏰ *{user.first_name}, shortlink abhi baaki hai!*\n\n"
                                        f"🎁 50 pts bonus abhi bhi available!\n"
                                        f"Bas ek movie search karo aur shortlink complete karo."
                                    ),
                                    reply_markup=InlineKeyboardMarkup(kb),
                                    parse_mode=ParseMode.MARKDOWN
                                )
                        except Exception as e:
                            logger.error(f"2hr reminder: {e}")
                    asyncio.ensure_future(_remind_2hr())
                except:
                    pass
            else:
                keyboard = [
                    [InlineKeyboardButton("💰 MINI APP KHOLO",
                        web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user.id}"))],
                    [InlineKeyboardButton("🎬 MOVIE GROUP", url=movie_group)]
                ]
                await update.message.reply_text(
                    f"🎬 *FilmyFund mein Swagat Hai, {user.first_name}!*\n\n"
                    f"🎯 Refer karo • Movie search karo • Paise kamao!\n\n"
                    f"👇 Mini App kholo:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN
                )

            if is_new:
                await update.message.reply_text(
                    f"🔗 *Aapka Referral Link:*\n`{ref_link}`\n\n"
                    f"📢 Share karo:\n• Active refer = 3 Passes + ₹{self.config.REFERRAL_BONUS}\n"
                    f"• Roz search = 30 pts/day!",
                    parse_mode=ParseMode.MARKDOWN
                )

        except Exception as e:
            logger.error(f"Start error: {e}", exc_info=True)
            try:
                await update.message.reply_text("❌ Error. /start dobara try karo.")
            except:
                pass

    # ══════════════════════════════════════════════════════════════
    # GROUP MESSAGE — Sirf referrer ko notify karo
    # ══════════════════════════════════════════════════════════════

    async def handle_group_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Movie group pe message aaya — referrer ko notify karo ki user aa gaya.
        VERIFY/ACTIVATE sirf log channel se hoga.
        """
        try:
            message = update.message or update.channel_post
            if not message:
                return
            user = update.effective_user
            if not user or user.is_bot:
                return
            chat = update.effective_chat
            if not chat or chat.type not in ['group', 'supergroup']:
                return

            # Sirf configured movie group pe
            if self.config.MOVIE_GROUP_ID:
                try:
                    if str(chat.id) != str(self.config.MOVIE_GROUP_ID):
                        return
                except:
                    pass

            msg_text = message.text or message.caption or ""
            if len(msg_text.strip()) < 2:
                return

            user_id = user.id
            referral = self.db.referrals.find_one({'referred_id': user_id})
            if not referral:
                return

            referrer_id = referral.get('referrer_id')
            is_active = referral.get('is_active', False)

            # Pending referral — referrer ko ek baar notify karo
            if not is_active and referrer_id:
                now_ts = datetime.now().timestamp()
                last_notified = self._group_notified.get(user_id, 0)
                if now_ts - last_notified > 21600:  # 6 hr cooldown
                    self._group_notified[user_id] = now_ts
                    try:
                        referrer = self.db.get_user(referrer_id)
                        if referrer and referrer.get('notify_referrals', True):
                            await context.bot.send_message(
                                chat_id=referrer_id,
                                text=(
                                    f"📢 *{user.first_name} Group Pe Aa Gaye!*\n\n"
                                    f"✅ Movie search kar di!\n\n"
                                    f"⏳ Abhi shortlink complete baki hai...\n"
                                    f"Jaise hi shortlink puri hogi — referral *auto active* ho jayega! 🎉"
                                ),
                                parse_mode=ParseMode.MARKDOWN
                            )
                    except Exception as e:
                        logger.error(f"Group notify referrer {referrer_id}: {e}")
        except Exception as e:
            logger.error(f"Group message handler: {e}")

    # ══════════════════════════════════════════════════════════════
    # LOG CHANNEL HANDLER — MAIN VERIFY LOGIC
    # ══════════════════════════════════════════════════════════════

    async def handle_log_channel_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Log channel pe movie bot ka message aata hai → bot verify karta hai.

        SUPPORTED FORMATS:
        ─────────────────────────────────────────────────────────────
        FORMAT 1 — #VerifyComplete (shortlink puri hui):
          ✅ #VerifyComplete
          ɪᴅ - 7142838312
          Nᴀᴍᴇ - ʀɪᴛɪᴋᴀ
          sʜᴏʀᴛʟɪɴᴋ - softurl.in
          ᴛɪᴍᴇ - 05 Apr 16:03 IST

        FORMAT 2 — #FileSent (file bheji = movie search done):
          #FileSent — File pahunch gayi! ✈️
          As Bʜᴀɪ Bsʀ (7315805581)
          Kill 2023 Hindi ORG 480p ...
          358.7 MB
          Premium: ✅ VIP
          05 Apr 15:55 IST

        FORMAT 3 — #NewUser (SIRF info, activate NAHI):
          #NewUser ID - 7346280916 Nᴀᴍᴇ - Abhinav
        ─────────────────────────────────────────────────────────────

        RULE: Sirf #VerifyComplete aur #FileSent pe activate karo.
              #NewUser pe kuch mat karo.
        """
        try:
            # Channel post ya regular message dono handle karo
            message = update.channel_post or update.message
            if not message:
                logger.debug("handle_log_channel_message: no message object")
                return

            chat_id = message.chat.id

            # ── STRICT chat ID check ──
            if chat_id != LOG_CHANNEL_ID:
                logger.debug(f"Ignoring chat_id={chat_id}, want {LOG_CHANNEL_ID}")
                return

            text = (message.text or message.caption or "").strip()
            if not text:
                return

            # ── Detailed log karo ──
            logger.info(f"═══ LOG CHANNEL MSG RECEIVED ═══")
            logger.info(f"Chat: {chat_id} | Len: {len(text)}")
            logger.info(f"Text preview: {text[:200]}")
            logger.info(f"═══════════════════════════════")

            # ── Message type detect ──
            text_upper = text.upper()
            has_verify  = '#VERIFYCOMPLETE' in text_upper or 'VERIFYCOMPLETE' in text_upper
            has_filesent = '#FILESENT' in text_upper or 'FILESENT' in text_upper
            has_newuser  = '#NEWUSER' in text_upper
            has_vshort   = '#VERIFYSHORTLINK' in text_upper or 'VERIFYSHORTLINK' in text_upper
            has_slv      = 'SHORTLINK VERIFIED' in text_upper

            logger.info(f"Detect: VerifyComplete={has_verify} FileSent={has_filesent} NewUser={has_newuser} VerifyShort={has_vshort}")

            # ── #NewUser — sirf log, kuch action nahi ──
            if has_newuser and not has_verify and not has_filesent and not has_vshort and not has_slv:
                uid, name = self._parse_user_id_and_name(text)
                logger.info(f"#NewUser message — ID={uid} Name={name} — NO ACTION")
                return

            # ── Verify messages — activate karo ──
            if has_verify or has_filesent or has_vshort or has_slv:
                uid, name = self._parse_user_id_and_name(text)
                logger.info(f"VERIFY MSG parsed: uid={uid} name={name}")

                if not uid:
                    logger.warning(f"⚠️ Could not parse user_id from:\n{text}")
                    return

                msg_type = (
                    'VerifyComplete' if has_verify else
                    'FileSent'       if has_filesent else
                    'Verifyshortlink' if has_vshort else
                    'ShortlinkVerified'
                )
                logger.info(f"Processing: type={msg_type} uid={uid} name={name}")
                await self._activate_and_notify(uid, name, context)

            else:
                logger.debug(f"Unrecognized log format (no action): {text[:100]}")

        except Exception as e:
            logger.error(f"handle_log_channel_message ERROR: {e}", exc_info=True)

    # ══════════════════════════════════════════════════════════════
    # USER ID + NAME PARSER — All formats
    # ══════════════════════════════════════════════════════════════

    def _parse_user_id_and_name(self, text: str):
        """
        Log channel message se user_id aur name extract karo.

        Supported formats:
          • "ID - 1234567890"           (ASCII normal)
          • "ɪᴅ - 1234567890"           (Unicode small caps)
          • "ID: 1234567890"            (colon format)
          • "As SomeName (1234567890)"  (#FileSent format)
          • "👤 SomeName (1234567890)"  (emoji format)
          • Fallback: any 7-15 digit number in text

        Returns (user_id: int | None, name: str)
        """
        user_id = None
        name = "User"

        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # ── Method 1: Normal "ID - 12345" or "ID: 12345" ──
            m = re.match(r'^ID\s*[-:]\s*(\d{5,15})', line, re.IGNORECASE)
            if m:
                try:
                    user_id = int(m.group(1))
                    logger.debug(f"ID parsed (normal): {user_id} from '{line}'")
                except:
                    pass

            # ── Method 2: Unicode small caps "ɪᴅ - 12345" ──
            # ɪ = U+026A, ᴅ = U+1D05 (both look like ID)
            if not user_id:
                # Normalize Unicode to ASCII-like
                normalized = line.replace('ɪ', 'I').replace('ᴅ', 'D').replace('ɴ', 'N')
                m2 = re.match(r'^ID\s*[-:–—]\s*(\d{5,15})', normalized, re.IGNORECASE)
                if m2:
                    try:
                        user_id = int(m2.group(1))
                        logger.debug(f"ID parsed (unicode norm): {user_id} from '{line}'")
                    except:
                        pass

            # ── Method 3: "As SomeName (12345)" — #FileSent format ──
            if not user_id:
                m3 = re.search(r'\((\d{5,15})\)', line)
                if m3:
                    try:
                        candidate = int(m3.group(1))
                        if candidate > 10000:  # valid Telegram ID range
                            user_id = candidate
                            # Extract name: everything before "("
                            name_part = re.sub(r'\(.*\)', '', line)
                            # Remove "As " prefix if present
                            name_part = re.sub(r'^As\s+', '', name_part.strip())
                            # Remove emoji prefixes
                            name_part = re.sub(r'^[👤📤✅#\s]+', '', name_part).strip()
                            if name_part:
                                name = name_part[:50]
                            logger.debug(f"ID parsed (bracket): {user_id} from '{line}'")
                    except:
                        pass

            # ── Name parsing: "Nᴀᴍᴇ - SomeName" or "Name - SomeName" ──
            norm_line = line.replace('ᴀ', 'A').replace('ᴍ', 'M').replace('ᴇ', 'E').replace('ɴ', 'N')
            nm = re.match(r'^NAME\s*[-:–—]\s*(.+)', norm_line, re.IGNORECASE)
            if nm:
                candidate_name = nm.group(1).strip()
                if candidate_name and not re.search(r'^\d+$', candidate_name):
                    name = candidate_name[:50]

        # ── Fallback: any standalone 7-15 digit number ──
        if not user_id:
            # Find all 7-15 digit numbers not surrounded by more digits
            candidates = re.findall(r'(?<!\d)(\d{7,15})(?!\d)', text)
            for c in candidates:
                try:
                    n = int(c)
                    # Basic Telegram user ID sanity check (not year/time like 2023, 1503 etc)
                    if n > 1_000_000:
                        user_id = n
                        logger.debug(f"ID parsed (fallback): {user_id}")
                        break
                except:
                    pass

        logger.info(f"_parse_user_id_and_name → uid={user_id} name={name}")
        return user_id, name

    # ══════════════════════════════════════════════════════════════
    # ACTIVATE REFERRAL + NOTIFY
    # ══════════════════════════════════════════════════════════════

    async def _activate_and_notify(self, user_id: int, name: str, context):
        """
        Referral activate karo ya daily search record karo.
        Dono cases mein relevant users ko notify karo.
        """
        # 1. Check user exists in DB
        user = self.db.get_user(user_id)
        if not user:
            logger.warning(f"User {user_id} DB mein nahi — bot se /start nahi kiya hoga")
            return

        # 2. Referral activate karne ki koshish karo
        result = self.db.activate_referral_by_log_channel(user_id)
        logger.info(f"activate_referral_by_log_channel({user_id}) → {result}")

        if result and result.get('activated'):
            # ── First time activation ──
            referrer_id   = result.get('referrer_id')
            referrer_name = result.get('referrer_name', 'Unknown')

            logger.info(f"✅ REFERRAL ACTIVATED: user={user_id} ({name}) → referrer={referrer_id}")

            # Referrer ko khushkhabri
            if referrer_id:
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=(
                            f"🎉 *Referral Active Ho Gaya!*\n\n"
                            f"👤 User: *{name}*\n"
                            f"✅ Shortlink complete kar li!\n\n"
                            f"🎟️ *+3 Passes* add ho gaye!\n"
                            f"💰 *+₹{self.config.REFERRAL_BONUS}* balance mein add!\n\n"
                            f"💡 Ab jab bhi ye user movie search karega,\n"
                            f"aapko *₹{self.config.DAILY_REFERRAL_EARNING} daily* milega!"
                        ),
                        parse_mode=ParseMode.MARKDOWN
                    )
                    logger.info(f"Referrer {referrer_id} notified of activation")
                except Exception as e:
                    logger.error(f"Notify referrer {referrer_id} FAILED: {e}")

            # Referred user ko bhi batao
            try:
                keyboard = [[InlineKeyboardButton(
                    "📱 Mini App Kholo",
                    web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user_id}")
                )]]
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"✅ *Aap Verify Ho Gaye!*\n\n"
                        f"Shortlink complete ho gayi!\n"
                        f"Aapke referrer *{referrer_name}* ko bonus mil gaya. 🎁\n\n"
                        f"📱 Mini App kholo aur daily earning shuru karo!\n"
                        f"Roz movie search karo = *30 pts daily!*"
                    ),
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN
                )
                logger.info(f"User {user_id} notified of verification")
            except Exception as e:
                logger.error(f"Notify user {user_id} FAILED: {e}")

        else:
            # ── Already active — daily search record karo ──
            reason = result.get('reason', 'unknown') if result else 'no_result'
            logger.info(f"Referral already active for {user_id} (reason={reason}) — recording daily search")

            search = self.db.record_daily_search(user_id)
            logger.info(f"record_daily_search({user_id}) → {search}")

            if search.get('success'):
                referrer_id = search.get('referrer_id')
                earning     = search.get('earning', self.config.DAILY_REFERRAL_EARNING)
                logger.info(f"✅ Daily search credited: user={user_id} ref={referrer_id} +₹{earning}")

                if referrer_id:
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=(
                                f"💰 *Daily Earning!*\n\n"
                                f"👤 *{name}* ne aaj movie search ki!\n"
                                f"✅ *+₹{earning}* aapke account mein add ho gaya!"
                            ),
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logger.error(f"Daily earning notify referrer {referrer_id}: {e}")

            elif search.get('reason') == 'already_credited_today':
                logger.info(f"Already credited today for {user_id}")
            else:
                logger.info(f"No active referral for {user_id}: {search.get('reason', '')}")

    # ══════════════════════════════════════════════════════════════
    # OTHER COMMANDS
    # ══════════════════════════════════════════════════════════════

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
                    f"💰 *Aapka Balance*\n\n"
                    f"Available: ₹{user.get('balance', 0):.2f}\n"
                    f"Total Earned: ₹{user.get('total_earned', 0):.2f}\n"
                    f"Aaj Kamaya: ₹{user.get('today_earned', 0):.2f}\n\n"
                    f"👥 *Referrals*\n"
                    f"Active: {user.get('active_refs', 0)}\n"
                    f"Pending: {user.get('pending_refs', 0)}\n"
                    f"Daily Potential: ₹{daily_potential:.2f}\n\n"
                    f"🏆 *Tier:* {self.config.get_tier_name(user.get('tier', 1))}"
                )
            else:
                text = "Pehle /start use karo"
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Balance: {e}")

    async def show_referrals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            user = self.db.get_user(user_id)
            if user:
                ref_link = f"https://t.me/{self.config.BOT_USERNAME}?start=ref_{user_id}"
                daily_earning = user.get('active_refs', 0) * self.config.DAILY_REFERRAL_EARNING
                text = (
                    f"👥 *Aapke Referrals*\n\n"
                    f"Total: {user.get('total_refs', 0)}\n"
                    f"Active: {user.get('active_refs', 0)}\n"
                    f"Pending: {user.get('pending_refs', 0)}\n\n"
                    f"💰 *Daily Earnings:* ₹{daily_earning:.2f}\n\n"
                    f"🔗 *Aapka Link:*\n`{ref_link}`"
                )
            else:
                text = "Pehle /start use karo"
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Referrals: {e}")

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
            logger.error(f"Withdraw cmd: {e}")

    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            text = (
                "❓ *Help & FAQ*\n\n"
                "*Commands:*\n"
                "/start - Bot start karo\n"
                "/app - Mini App kholo\n"
                "/balance - Balance check karo\n"
                "/referrals - Referrals dekho\n"
                "/withdraw - Paise nikalo\n"
                "/help - Ye message\n\n"
                "*Earning Process:*\n"
                "1️⃣ Referral link share karo\n"
                "2️⃣ Dost bot join kare\n"
                "3️⃣ Movie Group pe movie search kare\n"
                "4️⃣ Movie bot ka shortlink complete kare\n"
                "5️⃣ Log channel pe message aata hai → *referral auto active!*\n"
                "6️⃣ Roz shortlink = *daily ₹0.30*\n\n"
                "*⚠️ Rules:*\n"
                "• Shortlink puri hone ke baad hi active hoga\n"
                "• 1 user = 1 search per day\n"
                "• Fake activity = withdrawal band\n\n"
                f"*Support:* {self.config.SUPPORT_USERNAME}"
            )
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Help: {e}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user = update.effective_user
            chat = update.effective_chat
            message = update.message
            if not user or not message:
                return
            message_text = message.text or ""
            if chat.type == 'private' and message_text.lower() in ['hi', 'hello', 'hey', 'hii', 'helo']:
                await message.reply_text(
                    f"Namaskar {user.first_name}! 🙏\n"
                    f"/start use karo earning shuru karne ke liye!"
                )
        except Exception as e:
            logger.error(f"handle_message: {e}")

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
            logger.error(f"WebApp data: {e}")

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
                            kb = [[InlineKeyboardButton("📩 VIEW", callback_data=f"view_support_{msg_id}")]]
                            await context.bot.send_message(
                                chat_id=admin_id,
                                text=f"📩 *New Support*\n\nUser: `{user_id}`\nMsg: {message[:100]}",
                                reply_markup=InlineKeyboardMarkup(kb),
                                parse_mode=ParseMode.MARKDOWN
                            )
                        except:
                            pass
                return {'success': True, 'message': 'Sent!'}
            return {'success': False, 'message': 'Failed'}
        except Exception as e:
            logger.error(f"Support message: {e}")
            return {'success': False, 'message': str(e)}

    async def send_daily_reminders(self, context):
        try:
            pending_users = self.db.get_pending_reminders()
            if not pending_users:
                return
            sent = 0
            webapp_url = self.config.WEBAPP_URL
            for u in pending_users:
                uid = u['user_id']
                name = u.get('first_name', 'User')
                try:
                    kb = [[InlineKeyboardButton("📱 Mini App Kholo",
                        web_app=WebAppInfo(url=f"{webapp_url}/?user_id={uid}"))]]
                    await context.bot.send_message(
                        chat_id=uid,
                        text=(
                            f"⏰ *{name}, aaj ka kaam baaki hai!*\n\n"
                            f"🎁 Daily Bonus claim karo!\n"
                            f"🎬 Movie search karo = 30 pts!\n"
                            f"⚡ _Streak toot jayegi!_"
                        ),
                        reply_markup=InlineKeyboardMarkup(kb),
                        parse_mode=ParseMode.MARKDOWN
                    )
                    self.db.mark_user_reminded(uid)
                    sent += 1
                    import asyncio
                    await asyncio.sleep(0.05)
                except Exception as e:
                    logger.error(f"Reminder {uid}: {e}")
            logger.info(f"Reminders sent: {sent}")
        except Exception as e:
            logger.error(f"send_daily_reminders: {e}")
