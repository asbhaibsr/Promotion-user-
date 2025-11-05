# main.py

import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from datetime import timedelta
from telegram import Update, BotCommand

# Local Imports
from config import (
    BOT_TOKEN, WEB_SERVER_URL, PORT, ADMIN_ID,
    # Game configs ko import karna hai (Request 7)
    COIN_FLIP_CONFIG, DOLLAR_TO_INR, USERS_COLLECTION
)
# --- UPDATED IMPORTS FOR USER HANDLERS ---
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
    # <--- यह नई लाइन है
    show_leaderboard_info, 
    # --->
    # --- GAME IMPORTS (NEW) (Request 9 & 10) ---
    show_games_menu, 
    handle_coin_flip, 
    handle_coin_flip_play
)

# --- NEW IMPORT FOR ADMIN HANDLERS ---
from admin_handlers import (
    admin_panel, handle_admin_callbacks, handle_admin_input,
    handle_withdrawal_approval
)

# --- TASK IMPORTS ---
from tasks import send_random_alerts_task, process_monthly_leaderboard, send_fake_withdrawal_alert # New import for Request 3

# --- Logging Setup ---
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

    # Set bot commands on startup
    application.post_init = set_bot_commands_logic

    # Global Error Handler Enabled
    application.add_error_handler(error_handler) 

    # --- Command Handlers ---
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("earn", earn_command)) 
    application.add_handler(CommandHandler("admin", admin_panel, filters=filters.User(ADMIN_ID))) # Only admin can access
    
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
    
    # <--- यह नई लाइन है
    application.add_handler(CallbackQueryHandler(show_leaderboard_info, pattern="^show_leaderboard_info$"))
    # --->

    # --- GAME HANDLERS (NEW) (Request 9 & 10) ---
    application.add_handler(CallbackQueryHandler(show_games_menu, pattern="^show_games_menu$"))
    application.add_handler(CallbackQueryHandler(handle_coin_flip, pattern="^game_coin_flip_menu$"))
    application.add_handler(CallbackQueryHandler(handle_coin_flip_play, pattern="^game_coin_flip_play_"))
    
    # --- ADMIN Callback Query Handlers ---
    # Note: Filters for admin are handled within the admin_handlers.py for simplicity and context.
    application.add_handler(CallbackQueryHandler(handle_admin_callbacks, pattern="^admin_")) 
    # Withdrawal approval is specifically checked for the pattern and then access is restricted inside the function
    application.add_handler(CallbackQueryHandler(handle_withdrawal_approval, pattern="^(approve|reject)_withdraw_\\d+$"))
    
    # --- Message Handlers ---
    # This handler must be for ALL private texts (non-commands) because it handles admin state inputs.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_admin_input)) 
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_group_messages))
    
    # --- Job Queue (Background Tasks) ---
    job_queue = application.job_queue
    
    if job_queue: 
        job_queue.run_repeating(send_random_alerts_task, interval=timedelta(hours=2), first=timedelta(minutes=5))
        logger.info("Random alert task scheduled to run every 2 hours.")

        job_queue.run_repeating(process_monthly_leaderboard, interval=timedelta(hours=1), first=timedelta(minutes=10))
        logger.info("Monthly leaderboard task scheduled to run every 1 hour (to check date).")
        
        # Request 5: Fake withdrawal alerts
        job_queue.run_repeating(send_fake_withdrawal_alert, interval=timedelta(minutes=90), first=timedelta(minutes=15))
        logger.info("Fake withdrawal alert task scheduled to run every 90 minutes.")
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
