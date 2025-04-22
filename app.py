import os
import logging
import json
from dotenv import load_dotenv
from telegram.ext import Application
from bot_logic import setup_handlers
from ai_engine import ai_engine

load_dotenv()

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    # Load environment variables
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    ENV = os.environ.get("ENVIRONMENT", "production").lower()
    
    if not BOT_TOKEN:
        logger.error("No BOT_TOKEN provided in environment variables!")
        return
    
    # Initialize AI engine
    logger.info("Initializing AI knowledge base...")
    success = ai_engine.initialize_knowledge_base()
    if not success:
        logger.warning("Failed to initialize knowledge base. Bot will have limited functionality.")
    
    # Create and configure the application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    setup_handlers(app)
    
    # Start the bot differently based on environment
    if ENV == "development":
        logger.info("Starting bot in development mode (polling)")
        app.run_polling()
    else:
        # Production mode with webhook
        webhook_url = os.environ.get("WEBHOOK_URL")
        PORT = int(os.environ.get("PORT", 8080))
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