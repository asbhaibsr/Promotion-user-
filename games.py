# games.py
import logging
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from config import (
    USERS_COLLECTION, DOLLAR_TO_INR, COIN_FLIP_CONFIG,
    HEAD_STICKER_ID, TAILS_STICKER_ID, PROCESSING_STICKER_ID
)

logger = logging.getLogger(__name__)


# --- YEH SABHI FUNCTIONS handlers.py SE MOVE KIYE GAYE HAIN (PROBLEM 2) ---

async def show_games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Earning Games ka main menu dikhata hai."""
    query = update.callback_query
    if not query or not query.message:
        return
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🪙 कॉइन फ्लिप (Coin Flip)", callback_data="game_coin_flip_menu")],
        # Neeche diye gaye buttons abhi kaam nahi karenge jab tak aap unke function na banayein
        [InlineKeyboardButton("🎰 स्लॉट मशीन (Coming Soon)", callback_data="coming_soon")],
        [InlineKeyboardButton("🔢 नंबर प्रेडिक्शन (Coming Soon)", callback_data="coming_soon")],
        [InlineKeyboardButton("⬅️ Back to Earning Panel", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = "🎮 <b>Earning Games</b>\n\nKhel chunein aur extra cash jeetein!"
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

# --------------------------------------------------------------------------------------
# --- NEW COIN FLIP FUNCTIONS START HERE (REPLACING OLD ONES) ---
# --------------------------------------------------------------------------------------

async def handle_coin_flip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Coin Flip game ka main menu dikhata hai (Bet adjustment ke saath)"""
    query = update.callback_query
    if not query or not query.message:
        return

    user = query.from_user
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    balance_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR

    # User ki current bet ko context se fetch karo, ya default set karo
    min_bet = COIN_FLIP_CONFIG["min_bet"]
    current_bet = context.user_data.get('coin_flip_bet', min_bet)

    # Bet ko min/max ke andar rakho
    current_bet = max(min_bet, min(COIN_FLIP_CONFIG["max_bet"], current_bet))

    # Bet ko balance ke andar bhi rakho
    if current_bet > balance_inr:
        current_bet = max(min_bet, balance_inr)

    context.user_data['coin_flip_bet'] = current_bet

    await query.answer()

    message = (
        f"🪙 <b>कॉइन फ्लिप गेम (Coin Flip)</b>\n\n"
        f"Aapka Balance: <b>₹{balance_inr:.2f}</b>\n"
        f"Aapki Bet: <b>₹{current_bet:.2f}</b>\n\n"
        f"Bet ko adjust karne ke liye '+' ya '-' dabayein aur fir 'Start' karein.\n"
        f"Jeetne par <b>{COIN_FLIP_CONFIG['win_multiplier']}x</b> inaam milega."
    )

    # Buttons
    keyboard = [
        [
            InlineKeyboardButton("➖", callback_data="game_coin_flip_bet_dec"),
            InlineKeyboardButton(f"Bet: ₹{current_bet:.2f}", callback_data="none"),
            InlineKeyboardButton("➕", callback_data="game_coin_flip_bet_inc")
        ],
        [
            InlineKeyboardButton("Min (₹{:.2f})".format(COIN_FLIP_CONFIG["min_bet"]), callback_data="game_coin_flip_bet_min"),
            InlineKeyboardButton("Max (₹{:.2f})".format(COIN_FLIP_CONFIG["max_bet"]), callback_data="game_coin_flip_bet_max")
        ],
        [
            InlineKeyboardButton("✅ Start Game", callback_data="game_coin_flip_start")
        ],
        [
            InlineKeyboardButton("⬅️ Back to Games", callback_data="show_games_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
    except TelegramError as e:
        if "Message is not modified" not in str(e):
            logger.warning(f"Coin flip menu error: {e}")
        pass

async def handle_coin_flip_bet_adjust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bet ko '+' ya '-' karta hai"""
    query = update.callback_query
    if not query or not query.message:
        return

    action = query.data.split("_")[-1] # 'inc', 'dec', 'min', 'max'

    user = query.from_user
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    balance_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR

    min_bet = COIN_FLIP_CONFIG["min_bet"]
    max_bet = min(COIN_FLIP_CONFIG["max_bet"], balance_inr) # Max bet balance se zyada nahi ho sakti
    increment = COIN_FLIP_CONFIG["bet_increment"]

    current_bet = context.user_data.get('coin_flip_bet', min_bet)

    if action == "inc":
        current_bet += increment
    elif action == "dec":
        current_bet -= increment
    elif action == "min":
        current_bet = min_bet
    elif action == "max":
        current_bet = max_bet

    # Bet ko min/max ke beech clamp karo
    current_bet = round(max(min_bet, min(max_bet, current_bet)), 2)

    # Agar max_bet hi min_bet se kam hai (balance nahi hai)
    if current_bet < min_bet and balance_inr < min_bet:
        await query.answer("❌ Aapke paas minimum bet (₹{:.2f}) ke liye balance nahi hai.".format(min_bet), show_alert=True)
        current_bet = balance_inr
    elif current_bet < min_bet:
        current_bet = min_bet

    context.user_data['coin_flip_bet'] = current_bet

    # Menu ko update karne ke liye handle_coin_flip ko call karo
    await handle_coin_flip(update, context)

async def handle_coin_flip_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bet set hone ke baad Head/Tails poochta hai"""
    query = update.callback_query
    if not query or not query.message:
        return

    user = query.from_user
    bet_amount_inr = context.user_data.get('coin_flip_bet', 0)

    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    balance_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR

    if bet_amount_inr < COIN_FLIP_CONFIG["min_bet"]:
         await query.answer(f"❌ Bet kam se kam ₹{COIN_FLIP_CONFIG['min_bet']:.2f} honi chahiye.", show_alert=True)
         return

    if balance_inr < bet_amount_inr:
        await query.answer(f"❌ Aapke paas पर्याप्त balance (₹{bet_amount_inr:.2f}) nahi hai!", show_alert=True)
        context.user_data['coin_flip_bet'] = max(COIN_FLIP_CONFIG["min_bet"], balance_inr) # Bet ko balance par reset kar do
        await handle_coin_flip(update, context) # Menu refresh karo
        return

    await query.answer()

    message = (
        f"Aapne <b>₹{bet_amount_inr:.2f}</b> ki bet lagai hai.\n\n"
        f"Apna side chunein:"
    )
    keyboard = [
        [
            InlineKeyboardButton("🪙 Head", callback_data="game_coin_flip_choice_head"),
            InlineKeyboardButton("🪙 Tails", callback_data="game_coin_flip_choice_tails")
        ],
        [
            InlineKeyboardButton("⬅️ Cancel (Bet waapas)", callback_data="game_coin_flip_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

async def handle_coin_flip_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asli game khelta hai (processing sticker ke saath)"""
    query = update.callback_query
    if not query or not query.message:
        return

    user_choice = query.data.split("_")[-1] # 'head' ya 'tails'
    user = query.from_user

    bet_amount_inr = context.user_data.get('coin_flip_bet', 0)

    if bet_amount_inr <= 0:
        await query.answer("❌ Bet error. Dobara try karein.", show_alert=True)
        await handle_coin_flip(update, context)
        return

    await query.answer("Sikka uchhal raha hai...")

    # 1. Bet ki rakam kaat lo
    bet_amount_usd = bet_amount_inr / DOLLAR_TO_INR
    user_data = USERS_COLLECTION.find_one_and_update(
        {"user_id": user.id, "earnings": {"$gte": bet_amount_usd}},
        {"$inc": {"earnings": -bet_amount_usd}},
        return_document=False # Humein purana data nahi chahiye
    )

    if not user_data:
        # Aisa tab ho sakta hai jab user ke paas paise na ho (double check)
        await query.answer(f"❌ Aapke paas पर्याप्त balance (₹{bet_amount_inr:.2f}) nahi hai!", show_alert=True)
        await handle_coin_flip(update, context)
        return

    # 2. Processing sticker bhejo (User ke request ke mutabik)
    try:
        # Purana message delete karo
        await query.message.delete()
    except Exception:
        pass

    sticker_msg = await context.bot.send_sticker(
        chat_id=query.message.chat_id, 
        sticker=PROCESSING_STICKER_ID
    )

    # 3. 3 second ruko
    await asyncio.sleep(3)

    # 4. Game ka result nikalo
    # random module yahan import ho chuka hai
    result = random.choice(["head", "tails"])
    win = (user_choice == result)

    result_sticker = HEAD_STICKER_ID if result == "head" else TAILS_STICKER_ID
    result_text = "Head" if result == "head" else "Tails"

    # 5. Result process karo
    if win:
        win_amount_inr = bet_amount_inr * COIN_FLIP_CONFIG['win_multiplier']
        # Jeetne ki rakam (profit) add karo. 
        # Note: win_amount_usd = total jeet. Humne bet pehle hi kaat li hai. 
        # isliye humein total amount (bet + profit) waapas add karna hoga
        # Example: Bet 1.0, Win 1.8. Humne 1.0 kaata. Ab 1.8 add karenge.
        win_amount_usd = win_amount_inr / DOLLAR_TO_INR

        updated_user = USERS_COLLECTION.find_one_and_update(
            {"user_id": user.id},
            {"$inc": {"earnings": win_amount_usd}},
            return_document=True
        )
        new_balance_inr = updated_user.get("earnings", 0.0) * DOLLAR_TO_INR

        message = (
            f"🎉 <b>Aap Jeet Gaye!</b> (Result: {result_text}) 🎉\n\n"
            f"Aapne ₹{bet_amount_inr:.2f} lagaye aur <b>₹{win_amount_inr:.2f}</b> jeete!\n\n"
            f"Aapka naya balance: <b>₹{new_balance_inr:.2f}</b>"
        )
    else:
        # Haar gaye, paise pehle hi kat chuke hain
        updated_user = USERS_COLLECTION.find_one({"user_id": user.id})
        new_balance_inr = updated_user.get("earnings", 0.0) * DOLLAR_TO_INR

        message = (
            f"😢 <b>Aap Haar Gaye!</b> (Result: {result_text}) 😢\n\n"
            f"Aapne ₹{bet_amount_inr:.2f} haar diye.\n\n"
            f"Aapka naya balance: <b>₹{new_balance_inr:.2f}</b>"
        )

    # 6. Processing sticker delete karo
    try:
        await sticker_msg.delete()
    except Exception:
        pass

    # 7. Result sticker bhejo 
    await context.bot.send_sticker(chat_id=query.message.chat_id, sticker=result_sticker) 

    # 8. Result message bhejo
    keyboard = [
        [InlineKeyboardButton("🔄 दोबारा खेलें (Play Again)", callback_data="game_coin_flip_menu")],
        [InlineKeyboardButton("⬅️ Back to Games", callback_data="show_games_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=query.message.chat_id, 
        text=message, 
        reply_markup=reply_markup, 
        parse_mode='HTML'
    )

    # 9. Bet ko user_data se clear karo
    context.user_data['coin_flip_bet'] = 0

# --------------------------------------------------------------------------------------
# --- NEW COIN FLIP FUNCTIONS END HERE ---
# --------------------------------------------------------------------------------------
