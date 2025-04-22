from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os
import logging
from dotenv import load_dotenv
from src.knowledge import KnowledgeBase
from src.openai_client import OpenAIClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Get environment variables
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USERNAMES = os.getenv("ALLOWED_USERNAMES", "").split(",")

# Initialize knowledge base and OpenAI client
knowledge_base = KnowledgeBase()
openai_client = OpenAIClient()

# Log configuration on startup
logger.info(f"Starting bot with token: {TOKEN[:5]}...")
logger.info(f"Allowed usernames: {ALLOWED_USERNAMES}")

# Check if a user is authorized to add the bot to a group
def is_authorized(username):
    logger.debug(f"Checking if username '{username}' is authorized among {ALLOWED_USERNAMES}")
    if not username:
        return False
    return username in ALLOWED_USERNAMES or not ALLOWED_USERNAMES[0]  # Allow all if empty

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    logger.info(f"Start command from user: {user.id} ({user.username})")
    await update.message.reply_text(f"Hi {user.first_name}! I'm DevfolioAsk Bot. How can I help you?")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    logger.info(f"Help command from user: {update.effective_user.id} ({update.effective_user.username})")
    help_text = """
I'm DevfolioAsk Bot, your Devfolio assistant!

In a group chat:
- Mention me with @devfolioask_bot followed by your question
- Example: @devfolioask_bot How to add judges to the platform?
- Or use /ask followed by your question

In private chat:
- Just send your question directly
- Use /give_feedback to provide feedback on previous answers

I'll do my best to provide accurate information based on Devfolio documentation.
    """
    await update.message.reply_text(help_text)

async def process_question(question: str) -> str:
    """
    Process a question using knowledge base and OpenAI.
    
    Args:
        question: The user's question
        
    Returns:
        The answer to the question
    """
    # Query the knowledge base for relevant information
    answer_prefix, context = knowledge_base.query(question)
    
    # Generate response using OpenAI
    if context:
        answer = await openai_client.generate_response(question, context)
    else:
        answer = await openai_client.generate_response(
            question, 
            [{"source": "No specific source", "content": "No specific information found in the knowledge base."}]
        )
    
    return answer

async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /ask command."""
    question = " ".join(context.args)
    
    if not question:
        await update.message.reply_text("Please include your question after /ask")
        return
        
    logger.info(f"Question via /ask command: {question[:30]}...")
    
    # Process the question
    answer = await process_question(question)
    
    # Send the response
    await update.message.reply_text(answer)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages."""
    if not update.message or not update.message.text:
        return
        
    message = update.message
    text = message.text
    user = update.effective_user
    chat_type = message.chat.type
    
    logger.info(f"Received message in {chat_type} from {user.id} ({user.username}): {text[:20]}...")
    
    # Handle direct messages to the bot
    if chat_type == "private":
        logger.debug("Processing direct message")
        
        # Process the question
        answer = await process_question(text)
        
        # Send the response
        await message.reply_text(answer)
        return
    
    # Handle group messages
    if chat_type in ["group", "supergroup"]:
        # Check if the message mentions our bot
        bot_mention = "@devfolioask_bot"
        if bot_mention in text:
            logger.info(f"Bot mentioned in group message")
            
            # Extract question (everything after the mention)
            parts = text.split(bot_mention, 1)
            question = parts[1].strip() if len(parts) > 1 else ""
            
            if question:
                logger.info(f"Question extracted: {question[:30]}...")
                
                # Process the question
                answer = await process_question(question)
                
                # Send the response
                await message.reply_text(answer)
            else:
                await message.reply_text("Please include a question after mentioning me.")

async def handle_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome new members and check authorization for adding the bot."""
    message = update.message
    new_members = message.new_chat_members
    
    try:
        # Get bot info
        bot_info = await context.bot.get_me()
        bot_id = bot_info.id
        
        for member in new_members:
            if member.id == bot_id:
                # Bot was added to a new group
                added_by = message.from_user.username
                logger.info(f"Bot was added to group {message.chat.id} by {added_by}")
                
                # Send welcome message
                await message.reply_text(
                    "👋 Hello everyone! I'm DevfolioAsk Bot, your Devfolio assistant!\n\n"
                    "I can help answer questions about Devfolio platform features, workflows, and best practices. To ask me something:\n\n"
                    "• Mention me: @devfolioask_bot How do I create a hackathon?\n"
                    "• Or use command: /ask How do I create a hackathon?\n\n"
                    "I'm here to make your Devfolio experience smoother! 🚀"
                )
                
                # Check authorization
                if not is_authorized(added_by):
                    logger.warning(f"Unauthorized user {added_by} tried to add the bot")
                    await message.reply_text("I'm not authorized to join this group. Goodbye!")
                    await context.bot.leave_chat(message.chat_id)
    except Exception as e:
        logger.error(f"Error in handle_new_chat_members: {e}", exc_info=True)

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ask", ask_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat_members))

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
