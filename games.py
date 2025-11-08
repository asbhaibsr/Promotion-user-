# games.py
import logging
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from config import (
    USERS_COLLECTION, DOLLAR_TO_INR, COIN_FLIP_CONFIG,
    HEAD_STICKER_ID, TAILS_STICKER_ID, PROCESSING_STICKER_ID,
    # --- NAYE IMPORTS ---
    SLOT_MACHINE_CONFIG, SLOT_SYMBOLS, SLOT_PAYOUTS, NUMBER_PREDICTION
)

logger = logging.getLogger(__name__)


async def show_games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Earning Games ka main menu dikhata hai."""
    query = update.callback_query
    if not query or not query.message:
        return
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🪙 कॉइन फ्लिप (Coin Flip)", callback_data="game_coin_flip_menu")],
        # --- BADLAV YAHAN ---
        [InlineKeyboardButton("🎰 स्लॉट मशीन (Slot Machine)", callback_data="game_slot_machine_menu")],
        [InlineKeyboardButton("🔢 नंबर प्रेडिक्शन (Number Prediction)", callback_data="game_number_pred_menu")],
        # --- BADLAV KHATAM ---
        [InlineKeyboardButton("⬅️ Back to Earning Panel", callback_data="show_earning_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = "🎮 <b>Earning Games</b>\n\nKhel chunein aur extra cash jeetein!"
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

# --------------------------------------------------------------------------------------
# --- COIN FLIP FUNCTIONS (YEH PEHLE SE HAIN, INHE NA BADLEIN) ---
# --------------------------------------------------------------------------------------

async def handle_coin_flip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Coin Flip game ka main menu dikhata hai (Bet adjustment ke saath)"""
    query = update.callback_query
    if not query or not query.message:
        return

    user = query.from_user
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    balance_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR

    min_bet = COIN_FLIP_CONFIG["min_bet"]
    current_bet = context.user_data.get('coin_flip_bet', min_bet)
    current_bet = max(min_bet, min(COIN_FLIP_CONFIG["max_bet"], current_bet))
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
    max_bet = min(COIN_FLIP_CONFIG["max_bet"], balance_inr) 
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

    current_bet = round(max(min_bet, min(max_bet, current_bet)), 2)

    if current_bet < min_bet and balance_inr < min_bet:
        await query.answer("❌ Aapke paas minimum bet (₹{:.2f}) ke liye balance nahi hai.".format(min_bet), show_alert=True)
        current_bet = balance_inr
    elif current_bet < min_bet:
        current_bet = min_bet

    context.user_data['coin_flip_bet'] = current_bet
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
        context.user_data['coin_flip_bet'] = max(COIN_FLIP_CONFIG["min_bet"], balance_inr)
        await handle_coin_flip(update, context)
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

    bet_amount_usd = bet_amount_inr / DOLLAR_TO_INR
    user_data = USERS_COLLECTION.find_one_and_update(
        {"user_id": user.id, "earnings": {"$gte": bet_amount_usd}},
        {"$inc": {"earnings": -bet_amount_usd}},
        return_document=False 
    )

    if not user_data:
        await query.answer(f"❌ Aapke paas पर्याप्त balance (₹{bet_amount_inr:.2f}) nahi hai!", show_alert=True)
        await handle_coin_flip(update, context)
        return

    try:
        await query.message.delete()
    except Exception:
        pass

    sticker_msg = await context.bot.send_sticker(
        chat_id=query.message.chat_id, 
        sticker=PROCESSING_STICKER_ID
    )
    await asyncio.sleep(3)

    result = random.choice(["head", "tails"])
    win = (user_choice == result)
    result_sticker = HEAD_STICKER_ID if result == "head" else TAILS_STICKER_ID
    result_text = "Head" if result == "head" else "Tails"

    if win:
        win_amount_inr = bet_amount_inr * COIN_FLIP_CONFIG['win_multiplier']
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
        updated_user = USERS_COLLECTION.find_one({"user_id": user.id})
        new_balance_inr = updated_user.get("earnings", 0.0) * DOLLAR_TO_INR
        message = (
            f"😢 <b>Aap Haar Gaye!</b> (Result: {result_text}) 😢\n\n"
            f"Aapne ₹{bet_amount_inr:.2f} haar diye.\n\n"
            f"Aapka naya balance: <b>₹{new_balance_inr:.2f}</b>"
        )
    try:
        await sticker_msg.delete()
    except Exception:
        pass

    await context.bot.send_sticker(chat_id=query.message.chat_id, sticker=result_sticker) 
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
    context.user_data['coin_flip_bet'] = 0

# --------------------------------------------------------------------------------------
# --- NAYA CODE: SLOT MACHINE ---
# --------------------------------------------------------------------------------------

async def handle_slot_machine_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Slot Machine game ka main menu dikhata hai"""
    query = update.callback_query
    if not query or not query.message:
        return

    user = query.from_user
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    balance_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR

    min_bet = SLOT_MACHINE_CONFIG["min_bet"]
    current_bet = context.user_data.get('slot_machine_bet', min_bet)
    current_bet = max(min_bet, min(SLOT_MACHINE_CONFIG["max_bet"], current_bet))
    if current_bet > balance_inr:
        current_bet = max(min_bet, balance_inr)
    context.user_data['slot_machine_bet'] = current_bet

    await query.answer()

    message = (
        f"🎰 <b>स्लॉट मशीन (Slot Machine)</b>\n\n"
        f"Aapka Balance: <b>₹{balance_inr:.2f}</b>\n"
        f"Aapki Bet: <b>₹{current_bet:.2f}</b>\n\n"
        f"Bet adjust karein aur 'Spin' karein.\n"
        f"Payouts: 🍒🍒🍒 (Bet x{SLOT_PAYOUTS['🍒🍒🍒']}), ⭐⭐⭐ (Bet x{SLOT_PAYOUTS['⭐⭐⭐']}), 7️⃣7️⃣7️⃣ (Bet x{SLOT_PAYOUTS['7️⃣7️⃣7️⃣']})"
    )
    keyboard = [
        [
            InlineKeyboardButton("➖", callback_data="game_slot_bet_dec"),
            InlineKeyboardButton(f"Bet: ₹{current_bet:.2f}", callback_data="none"),
            InlineKeyboardButton("➕", callback_data="game_slot_bet_inc")
        ],
        [
            InlineKeyboardButton("Min (₹{:.2f})".format(SLOT_MACHINE_CONFIG["min_bet"]), callback_data="game_slot_bet_min"),
            InlineKeyboardButton("Max (₹{:.2f})".format(SLOT_MACHINE_CONFIG["max_bet"]), callback_data="game_slot_bet_max")
        ],
        [
            InlineKeyboardButton("✅ Spin Now!", callback_data="game_slot_spin")
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
            logger.warning(f"Slot menu error: {e}")
        pass

async def handle_slot_machine_bet_adjust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Slot machine bet ko adjust karta hai"""
    query = update.callback_query
    if not query or not query.message:
        return

    action = query.data.split("_")[-1] 

    user = query.from_user
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    balance_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR

    min_bet = SLOT_MACHINE_CONFIG["min_bet"]
    max_bet = min(SLOT_MACHINE_CONFIG["max_bet"], balance_inr)
    increment = SLOT_MACHINE_CONFIG["bet_increment"]

    current_bet = context.user_data.get('slot_machine_bet', min_bet)

    if action == "inc":
        current_bet += increment
    elif action == "dec":
        current_bet -= increment
    elif action == "min":
        current_bet = min_bet
    elif action == "max":
        current_bet = max_bet

    current_bet = round(max(min_bet, min(max_bet, current_bet)), 2)

    if current_bet < min_bet and balance_inr < min_bet:
        await query.answer("❌ Aapke paas minimum bet (₹{:.2f}) ke liye balance nahi hai.".format(min_bet), show_alert=True)
        current_bet = balance_inr
    elif current_bet < min_bet:
        current_bet = min_bet

    context.user_data['slot_machine_bet'] = current_bet
    await handle_slot_machine_menu(update, context)

async def handle_slot_machine_spin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Slot machine ka game logic"""
    query = update.callback_query
    if not query or not query.message:
        return

    user = query.from_user
    bet_amount_inr = context.user_data.get('slot_machine_bet', 0)

    if bet_amount_inr < SLOT_MACHINE_CONFIG["min_bet"]:
         await query.answer(f"❌ Bet kam se kam ₹{SLOT_MACHINE_CONFIG['min_bet']:.2f} honi chahiye.", show_alert=True)
         return
    
    bet_amount_usd = bet_amount_inr / DOLLAR_TO_INR
    user_data = USERS_COLLECTION.find_one_and_update(
        {"user_id": user.id, "earnings": {"$gte": bet_amount_usd}},
        {"$inc": {"earnings": -bet_amount_usd}},
        return_document=False 
    )

    if not user_data:
        await query.answer(f"❌ Aapke paas पर्याप्त balance (₹{bet_amount_inr:.2f}) nahi hai!", show_alert=True)
        await handle_slot_machine_menu(update, context)
        return

    await query.answer("Spinning... 🎰")
    
    try:
        await query.message.delete()
    except Exception:
        pass
        
    sticker_msg = await context.bot.send_sticker(
        chat_id=query.message.chat_id, 
        sticker=PROCESSING_STICKER_ID
    )
    await asyncio.sleep(3)

    # Game Logic
    reel1 = random.choice(SLOT_SYMBOLS)
    reel2 = random.choice(SLOT_SYMBOLS)
    reel3 = random.choice(SLOT_SYMBOLS)
    
    result_key = f"{reel1}{reel2}{reel3}"
    payout_multiplier = SLOT_PAYOUTS.get(result_key, 0)

    if payout_multiplier > 0:
        win_amount_inr = bet_amount_inr * payout_multiplier
        win_amount_usd = win_amount_inr / DOLLAR_TO_INR
        updated_user = USERS_COLLECTION.find_one_and_update(
            {"user_id": user.id},
            {"$inc": {"earnings": win_amount_usd}},
            return_document=True
        )
        new_balance_inr = updated_user.get("earnings", 0.0) * DOLLAR_TO_INR
        
        message = (
            f"🎰 | {reel1} | {reel2} | {reel3} | 🎰\n\n"
            f"🎉 <b>Aap Jeet Gaye!</b> 🎉\n\n"
            f"Aapne ₹{bet_amount_inr:.2f} lagaye aur <b>₹{win_amount_inr:.2f}</b> jeete!\n\n"
            f"Aapka naya balance: <b>₹{new_balance_inr:.2f}</b>"
        )
    else:
        updated_user = USERS_COLLECTION.find_one({"user_id": user.id})
        new_balance_inr = updated_user.get("earnings", 0.0) * DOLLAR_TO_INR
        message = (
            f"🎰 | {reel1} | {reel2} | {reel3} | 🎰\n\n"
            f"😢 <b>Aap Haar Gaye!</b> 😢\n\n"
            f"Aapne ₹{bet_amount_inr:.2f} haar diye.\n\n"
            f"Aapka naya balance: <b>₹{new_balance_inr:.2f}</b>"
        )

    try:
        await sticker_msg.delete()
    except Exception:
        pass

    keyboard = [
        [InlineKeyboardButton("🔄 दोबारा खेलें (Play Again)", callback_data="game_slot_machine_menu")],
        [InlineKeyboardButton("⬅️ Back to Games", callback_data="show_games_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=query.message.chat_id, 
        text=message, 
        reply_markup=reply_markup, 
        parse_mode='HTML'
    )
    context.user_data['slot_machine_bet'] = 0

# --------------------------------------------------------------------------------------
# --- NAYA CODE: NUMBER PREDICTION (INSTANT GAME) ---
# --------------------------------------------------------------------------------------

async def handle_number_prediction_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Number Prediction ka pehla step: Entry fee chunna"""
    query = update.callback_query
    if not query or not query.message:
        return

    user = query.from_user
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    balance_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR
    await query.answer()

    entry_fees = NUMBER_PREDICTION["entry_fee"]
    win_multiplier = NUMBER_PREDICTION["win_multiplier"]
    num_range = NUMBER_PREDICTION["number_range"]
    
    message = (
        f"🔢 <b>नंबर प्रेडिक्शन (Number Prediction)</b>\n\n"
        f"Aapka Balance: <b>₹{balance_inr:.2f}</b>\n\n"
        f"Ek number ({num_range[0]}-{num_range[1]}) chunein. Agar aapka number bot ke number se match hua, "
        f"toh aap apni bet ka <b>{win_multiplier}x</b> jeet jayenge!\n\n"
        f"<b>Khelne ke liye entry fee chunein:</b>"
    )
    
    keyboard = []
    # Entry fee buttons ko 3-3 ke group mein banana
    row = []
    for fee in entry_fees:
        row.append(InlineKeyboardButton(f"₹{fee:.2f}", callback_data=f"game_num_pred_fee_{fee}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    keyboard.append([InlineKeyboardButton("⬅️ Back to Games", callback_data="show_games_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
    except TelegramError as e:
        if "Message is not modified" not in str(e):
            logger.warning(f"Number pred menu error: {e}")
        pass

async def handle_number_prediction_select_fee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry fee select karne ke baad number range poochta hai"""
    query = update.callback_query
    if not query or not query.message:
        return

    try:
        bet_amount_inr = float(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.answer("❌ Invalid fee.", show_alert=True)
        return
    
    user = query.from_user
    user_data = USERS_COLLECTION.find_one({"user_id": user.id})
    balance_inr = user_data.get("earnings", 0.0) * DOLLAR_TO_INR
    
    if balance_inr < bet_amount_inr:
        await query.answer(f"❌ Aapke paas पर्याप्त balance (₹{bet_amount_inr:.2f}) nahi hai!", show_alert=True)
        return
        
    context.user_data['number_pred_bet'] = bet_amount_inr
    await query.answer()

    num_range = NUMBER_PREDICTION["number_range"]
    message = (
        f"Aapne <b>₹{bet_amount_inr:.2f}</b> ki bet chuni hai.\n\n"
        f"Kripya <b>{num_range[0]} se {num_range[1]}</b> ke beech apna number chunein."
    )
    
    keyboard = []
    # 10 button rows (1-10, 11-20, etc.)
    for i in range(num_range[0], num_range[1] + 1, 10):
        start = i
        end = min(i + 9, num_range[1])
        keyboard.append([InlineKeyboardButton(f"{start} - {end}", callback_data=f"game_num_pred_range_{start}")])
    
    keyboard.append([InlineKeyboardButton("⬅️ Cancel (Fee waapas)", callback_data="game_number_pred_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

async def handle_number_prediction_select_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Number range select karne ke baad final number poochta hai"""
    query = update.callback_query
    if not query or not query.message:
        return

    try:
        start_num = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.answer("❌ Invalid range.", show_alert=True)
        return
        
    bet_amount_inr = context.user_data.get('number_pred_bet', 0)
    if bet_amount_inr == 0:
        await query.answer("❌ Bet error. Dobara try karein.", show_alert=True)
        await handle_number_prediction_menu(update, context) # Menu par waapas bhejo
        return
        
    await query.answer()
    
    message = (
        f"Aapne <b>₹{bet_amount_inr:.2f}</b> ki bet chuni hai.\n\n"
        f"Range: {start_num} - {start_num + 9}. <b>Apna number chunein:</b>"
    )
    
    keyboard = []
    row = []
    for i in range(start_num, start_num + 10):
        if i > NUMBER_PREDICTION["number_range"][1]:
            break
        row.append(InlineKeyboardButton(str(i), callback_data=f"game_num_pred_play_{i}"))
        if len(row) == 5: # 5 buttons per row
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    keyboard.append([InlineKeyboardButton("⬅️ Back to Fee Selection", callback_data="game_number_pred_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

async def handle_number_prediction_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Final game logic"""
    query = update.callback_query
    if not query or not query.message:
        return

    try:
        chosen_number = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.answer("❌ Invalid number.", show_alert=True)
        return

    user = query.from_user
    bet_amount_inr = context.user_data.get('number_pred_bet', 0)

    if bet_amount_inr <= 0:
        await query.answer("❌ Bet error. Dobara try karein.", show_alert=True)
        await handle_number_prediction_menu(update, context)
        return

    bet_amount_usd = bet_amount_inr / DOLLAR_TO_INR
    user_data = USERS_COLLECTION.find_one_and_update(
        {"user_id": user.id, "earnings": {"$gte": bet_amount_usd}},
        {"$inc": {"earnings": -bet_amount_usd}},
        return_document=False 
    )

    if not user_data:
        await query.answer(f"❌ Aapke paas पर्याप्त balance (₹{bet_amount_inr:.2f}) nahi hai!", show_alert=True)
        await handle_number_prediction_menu(update, context)
        return

    await query.answer("Number lock kar diya... 🤞")

    try:
        await query.message.delete()
    except Exception:
        pass
        
    sticker_msg = await context.bot.send_sticker(
        chat_id=query.message.chat_id, 
        sticker=PROCESSING_STICKER_ID
    )
    await asyncio.sleep(2)
    
    # Game Logic
    num_range = NUMBER_PREDICTION["number_range"]
    winning_number = random.randint(num_range[0], num_range[1])
    
    win = (chosen_number == winning_number)

    if win:
        win_multiplier = NUMBER_PREDICTION["win_multiplier"]
        win_amount_inr = bet_amount_inr * win_multiplier
        win_amount_usd = win_amount_inr / DOLLAR_TO_INR
        updated_user = USERS_COLLECTION.find_one_and_update(
            {"user_id": user.id},
            {"$inc": {"earnings": win_amount_usd}},
            return_document=True
        )
        new_balance_inr = updated_user.get("earnings", 0.0) * DOLLAR_TO_INR
        
        message = (
            f"🎉 <b>Aap Jeet Gaye!</b> 🎉\n\n"
            f"Aapka number: <b>{chosen_number}</b>\n"
            f"Bot ka number: <b>{winning_number}</b>\n\n"
            f"Aapne ₹{bet_amount_inr:.2f} lagaye aur <b>₹{win_amount_inr:.2f}</b> jeete!\n\n"
            f"Aapka naya balance: <b>₹{new_balance_inr:.2f}</b>"
        )
    else:
        updated_user = USERS_COLLECTION.find_one({"user_id": user.id})
        new_balance_inr = updated_user.get("earnings", 0.0) * DOLLAR_TO_INR
        message = (
            f"😢 <b>Aap Haar Gaye!</b> 😢\n\n"
            f"Aapka number: <b>{chosen_number}</b>\n"
            f"Bot ka number: <b>{winning_number}</b>\n\n"
            f"Aapne ₹{bet_amount_inr:.2f} haar diye.\n\n"
            f"Aapka naya balance: <b>₹{new_balance_inr:.2f}</b>"
        )

    try:
        await sticker_msg.delete()
    except Exception:
        pass

    keyboard = [
        [InlineKeyboardButton("🔄 दोबारा खेलें (Play Again)", callback_data="game_number_pred_menu")],
        [InlineKeyboardButton("⬅️ Back to Games", callback_data="show_games_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=query.message.chat_id, 
        text=message, 
        reply_markup=reply_markup, 
        parse_mode='HTML'
    )
    context.user_data['number_pred_bet'] = 0
