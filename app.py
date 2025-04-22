import os
import logging
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
    
    # Print some debug info
    print(f"Starting bot with token: {BOT_TOKEN[:5]}...{BOT_TOKEN[-5:]}")
    
    # Initialize AI engine
    logger.info("Initializing AI knowledge base...")
    success = ai_engine.initialize_knowledge_base()
    if not success:
        logger.warning("Failed to initialize knowledge base. Bot will have limited functionality.")
    
    # Create and configure the application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    setup_handlers(app)
    
    # Start the bot in polling mode for development
    logger.info("Starting bot in polling mode")
    
    # Use a simple callback to print bot info when the application starts
    async def post_init(application):
        me = await application.bot.get_me()
        print(f"Bot info - ID: {me.id}, Name: {me.first_name}, Username: {me.username}")
    
    app.post_init = post_init
    app.run_polling()

if __name__ == "__main__":
    main()