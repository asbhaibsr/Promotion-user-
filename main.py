# main.py

import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from datetime import timedelta
from telegram import Update, BotCommand

# Local Imports
from config import (
    BOT_TOKEN, WEB_SERVER_URL, PORT, ADMIN_ID
)
from handlers import (
    start_command, earn_command, 
    show_earning_panel, show_movie_groups_menu, back_to_main_menu,
    language_menu, handle_lang_choice, show_help, show_refer_link,
    show_withdraw_details_new, claim_daily_bonus, show_refer_example,
    show_spin_panel, perform_spin, spin_fake_btn, show_missions, 
    request_withdrawal, show_tier_benefits, claim_channel_bonus,
    handle_group_messages,
    show_leaderboard, 
    show_user_pending_withdrawals, 
    show_my_referrals, 
    set_bot_commands_logic, 
    error_handler,
    show_leaderboard_info,
    verify_channel_join  # <-- YAHAN SE ADD KIYA (Import)
)

from admin_handlers import (
    admin_panel, handle_admin_callbacks, 
    handle_private_text,
    handle_withdrawal_approval
)

from games import (
    show_games_menu,
    handle_coin_flip,
    handle_coin_flip_bet_adjust, 
    handle_coin_flip_start, 
    handle_coin_flip_choice,
    handle_slot_machine_menu,
    handle_slot_machine_bet_adjust,
    handle_slot_machine_spin,
    handle_number_prediction_menu,
    handle_number_prediction_select_fee,
    handle_number_prediction_select_range,
    handle_number_prediction_play
)

from tasks import send_random_alerts_task, process_monthly_leaderboard

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main() -> None:
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is missing. Please set environment variables.")
        return

    application = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()

    application.post_init = set_bot_commands_logic

    application.add_error_handler(error_handler) 

    # --- Command Handlers ---
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("earn", earn_command)) 
    application.add_handler(CommandHandler("admin", admin_panel, filters=filters.User(ADMIN_ID)))
    
    # --- USER Callback Query Handlers ---
    application.add_handler(CallbackQueryHandler(show_earning_panel, pattern="^show_earning_panel$"))
    application.add_handler(CallbackQueryHandler(show_movie_groups_menu, pattern="^show_movie_groups_menu$"))
    application.add_handler(CallbackQueryHandler(back_to_main_menu, pattern="^back_to_main_menu$"))
    application.add_handler(CallbackQueryHandler(language_menu, pattern="^select_lang$")) 
    application.add_handler(CallbackQueryHandler(handle_lang_choice, pattern="^lang_")) 
    application.add_handler(CallbackQueryHandler(show_help, pattern="^show_help$")) 
    application.add_handler(CallbackQueryHandler(show_refer_link, pattern="^show_refer_link$"))
    application.add_handler(CallbackQueryHandler(show_withdraw_details_new, pattern="^show_withdraw_details_new$"))
    application.add_handler(CallbackQueryHandler(claim_daily_bonus, pattern="^claim_daily_bonus$")) 
    application.add_handler(CallbackQueryHandler(show_refer_example, pattern="^show_refer_example$")) 
    application.add_handler(CallbackQueryHandler(show_spin_panel, pattern="^show_spin_panel$"))
    application.add_handler(CallbackQueryHandler(perform_spin, pattern="^perform_spin$"))
    application.add_handler(CallbackQueryHandler(spin_fake_btn, pattern="^spin_fake_btn$"))
    application.add_handler(CallbackQueryHandler(show_missions, pattern="^show_missions$")) 
    application.add_handler(CallbackQueryHandler(request_withdrawal, pattern="^request_withdrawal$"))
    application.add_handler(CallbackQueryHandler(show_tier_benefits, pattern="^show_tier_benefits$")) 
    application.add_handler(CallbackQueryHandler(claim_channel_bonus, pattern="^claim_channel_bonus$")) 
    application.add_handler(CallbackQueryHandler(show_leaderboard, pattern="^show_leaderboard$"))
    application.add_handler(CallbackQueryHandler(show_user_pending_withdrawals, pattern="^show_user_pending_withdrawals$"))
    application.add_handler(CallbackQueryHandler(show_my_referrals, pattern="^show_my_referrals$"))
    application.add_handler(CallbackQueryHandler(show_leaderboard_info, pattern="^show_leaderboard_info$"))
    
    # --- Verify Button Handler (Ise show_earning_panel ke upar jodein) ---
    # Yahaan add kiya gaya hai (Request ke anusar)
    application.add_handler(CallbackQueryHandler(verify_channel_join, pattern="^verify_channel_join$"))
    
    # --- GAME HANDLERS ---
    application.add_handler(CallbackQueryHandler(show_games_menu, pattern="^show_games_menu$"))
    
    # Coin Flip Handlers
    application.add_handler(CallbackQueryHandler(handle_coin_flip, pattern="^game_coin_flip_menu$"))
    application.add_handler(CallbackQueryHandler(handle_coin_flip_bet_adjust, pattern="^game_coin_flip_bet_"))
    application.add_handler(CallbackQueryHandler(handle_coin_flip_start, pattern="^game_coin_flip_start$"))
    application.add_handler(CallbackQueryHandler(handle_coin_flip_choice, pattern="^game_coin_flip_choice_"))
    
    # Slot Machine Handlers
    application.add_handler(CallbackQueryHandler(handle_slot_machine_menu, pattern="^game_slot_machine_menu$"))
    application.add_handler(CallbackQueryHandler(handle_slot_machine_bet_adjust, pattern="^game_slot_bet_"))
    application.add_handler(CallbackQueryHandler(handle_slot_machine_spin, pattern="^game_slot_spin$"))
    
    # Number Prediction Handlers
    application.add_handler(CallbackQueryHandler(handle_number_prediction_menu, pattern="^game_number_pred_menu$"))
    application.add_handler(CallbackQueryHandler(handle_number_prediction_select_fee, pattern="^game_num_pred_fee_"))
    application.add_handler(CallbackQueryHandler(handle_number_prediction_select_range, pattern="^game_num_pred_range_"))
    application.add_handler(CallbackQueryHandler(handle_number_prediction_play, pattern="^game_num_pred_play_"))
    
    # --- ADMIN Callback Query Handlers ---
    application.add_handler(CallbackQueryHandler(handle_admin_callbacks, pattern="^admin_")) 
    application.add_handler(CallbackQueryHandler(handle_withdrawal_approval, pattern="^(approve|reject)_withdraw_\\d+$"))
    
    # --- Message Handlers ---
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_private_text)) 
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_group_messages))
    
    # --- Job Queue (Background Tasks) ---
    job_queue = application.job_queue
    
    if job_queue: 
        job_queue.run_repeating(send_random_alerts_task, interval=timedelta(hours=2), first=timedelta(minutes=5))
        logger.info("Random alert task scheduled to run every 2 hours.")

        job_queue.run_repeating(process_monthly_leaderboard, interval=timedelta(hours=1), first=timedelta(minutes=10))
        logger.info("Monthly leaderboard task scheduled to run every 1 hour (to check date).")
    else:
        logger.warning("Job Queue is not initialized. Skipping scheduled tasks (common in Webhook mode).")

    # --- Running the Bot ---
    if WEB_SERVER_URL and BOT_TOKEN:
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEB_SERVER_URL}/{BOT_TOKEN}",
            allowed_updates=Update.ALL_TYPES
        )
        logger.info(f"Bot started in Webhook Mode on port {PORT}.")
    else:
        logger.info("WEB_SERVER_URL not found, starting in Polling Mode.")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Bot started in Polling Mode.")

if __name__ == "__main__":
    main()
