# main.py

import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from datetime import timedelta
from telegram import Update, BotCommand

# Local Imports
from config import (
    BOT_TOKEN, WEB_SERVER_URL, PORT, USER_COMMANDS, ADMIN_COMMANDS
)
from handlers import (
    start_command, earn_command, admin_panel,
    show_earning_panel, show_movie_groups_menu, back_to_main_menu,
    language_menu, handle_lang_choice, show_help, show_refer_link,
    show_withdraw_details_new, claim_daily_bonus, show_refer_example,
    show_spin_panel, perform_spin, spin_fake_btn, show_missions, 
    request_withdrawal, show_tier_benefits, claim_channel_bonus,
    handle_admin_callbacks, handle_withdrawal_approval, handle_group_messages,
    handle_admin_input, show_bot_stats, # New: Bot Stats Handler
    show_top_users, 
    show_user_pending_withdrawals, 
    error_handler # FIX: Import the new error handler
)
from tasks import send_random_alerts_task

# --- Logging Setup ---
logging.basicConfig(
    # FIX: Corrected format string
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main() -> None:
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is missing. Please set environment variables.")
        return

    application = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()

    # FIX: Global Error Handler
    # application.add_error_handler(error_handler) 
    # Note: Use the commented line if you want a global error handler.

    # --- Command Handlers ---
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("earn", earn_command)) 
    application.add_handler(CommandHandler("admin", admin_panel))
    
    # --- Callback Query Handlers ---
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
    
    # New Handlers
    application.add_handler(CallbackQueryHandler(show_top_users, pattern="^show_top_users$"))
    application.add_handler(CallbackQueryHandler(show_user_pending_withdrawals, pattern="^show_user_pending_withdrawals$"))
    
    # Admin & Withdrawal Handlers
    application.add_handler(CallbackQueryHandler(handle_admin_callbacks, pattern="^admin_")) 
    application.add_handler(CallbackQueryHandler(handle_withdrawal_approval, pattern="^(approve|reject)_withdraw_\\d+$"))
    
    # --- Message Handlers ---
    # Handle admin input in private chat (for broadcast, setrate etc.)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_admin_input)) 
    
    # Handle group messages (movie searches)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_group_messages))
    
    # --- Job Queue (Background Tasks) ---
    job_queue = application.job_queue
    
    if job_queue: 
        job_queue.run_repeating(send_random_alerts_task, interval=timedelta(hours=2), first=timedelta(minutes=5))
        logger.info("Random alert task scheduled to run every 2 hours.")
    else:
        logger.warning("Job Queue is not initialized. Skipping random alert task (common in Webhook mode).")


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
