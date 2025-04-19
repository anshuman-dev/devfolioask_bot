import os
import logging
from dotenv import load_dotenv
from telegram.ext import Application
from apscheduler.schedulers.background import BackgroundScheduler
from bot_logic import setup_handlers
from gitbook_scraper import refresh_knowledge_base

load_dotenv()

# Quick setup for logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def setup_scheduler():
    scheduler = BackgroundScheduler()
    
    # Add the weekly job - Sunday 2AM
    scheduler.add_job(refresh_knowledge_base, 'cron', day_of_week='sun', hour=2)
    
    # Start the scheduler
    scheduler.start()
    logger.info("Scheduler started - weekly refresh set for Sunday 2AM")
    return scheduler

def main():
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    PORT = int(os.environ.get("PORT", 8080))
    
    if not BOT_TOKEN:
        logger.error("No BOT_TOKEN provided in environment variables!")
        return
    
    # Start scheduler for regular updates
    scheduler = setup_scheduler()
    
    # Create and configure the application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    setup_handlers(app)
    
    # Run initial knowledge base refresh
    refresh_knowledge_base()
    
    # Start the bot - using webhook for production
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=os.environ.get("WEBHOOK_URL")
    )

if __name__ == "__main__":
    main()