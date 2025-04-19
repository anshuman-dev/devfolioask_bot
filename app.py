import os
import logging
from dotenv import load_dotenv
from telegram.ext import Application
from apscheduler.schedulers.background import BackgroundScheduler
from bot_logic import setup_handlers
from gitbook_scraper import refresh_knowledge_base

load_dotenv()

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def setup_scheduler():
    scheduler = BackgroundScheduler()
    
    # Weekly refresh on Sunday at 2 AM
    scheduler.add_job(refresh_knowledge_base, 'cron', day_of_week='sun', hour=2)
    
    # Start the scheduler
    scheduler.start()
    logger.info("Scheduler started - weekly refresh set for Sunday 2 AM")
    return scheduler

def main():
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    PORT = int(os.environ.get("PORT", 8080))
    ENV = os.environ.get("ENVIRONMENT", "production").lower()
    
    if not BOT_TOKEN:
        logger.error("No BOT_TOKEN provided in environment variables!")
        return
    
    # Start scheduler for regular updates
    scheduler = setup_scheduler()
    
    # Create and configure the application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    setup_handlers(app)
    
    # Run initial knowledge base refresh if not already populated
    refresh_knowledge_base()
    
    # Start the bot differently based on environment
    if ENV == "development":
        logger.info("Starting bot in development mode (polling)")
        app.run_polling()
    else:
        # Production mode with webhook
        webhook_url = os.environ.get("WEBHOOK_URL")
        if not webhook_url:
            logger.error("No WEBHOOK_URL provided for production environment!")
            return
            
        logger.info(f"Starting bot in production mode (webhook: {webhook_url})")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=webhook_url
        )

if __name__ == "__main__":
    main()