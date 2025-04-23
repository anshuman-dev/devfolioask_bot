from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
import os
import logging
import time
import json
from dotenv import load_dotenv
from src.knowledge import KnowledgeBase
from src.openai_client import OpenAIClient
from src.feedback import FeedbackSystem

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

# Initialize knowledge base, OpenAI client, and feedback system
knowledge_base = KnowledgeBase()
openai_client = OpenAIClient()
feedback_system = FeedbackSystem()

# Conversation context storage
user_contexts = {}

# Log configuration on startup
logger.info(f"Starting bot with token: {TOKEN[:5]}...")
logger.info(f"Allowed usernames: {ALLOWED_USERNAMES}")

# Check if a user is authorized to add the bot to a group
def is_authorized(username):
    logger.debug(f"Checking if username '{username}' is authorized among {ALLOWED_USERNAMES}")
    if not username:
        return False
    return username in ALLOWED_USERNAMES or not ALLOWED_USERNAMES[0]  # Allow all if empty

# Get or initialize user context
def get_user_context(user_id):
    if user_id not in user_contexts:
        user_contexts[user_id] = {
            "recent_questions": [],
            "recent_answers": [],
            "judging_mode_preference": None,
            "last_interaction_time": time.time()
        }
    return user_contexts[user_id]

# Update user context
def update_user_context(user_id, question, answer):
    context = get_user_context(user_id)
    
    # Add to recent interactions
    context["recent_questions"].append(question)
    context["recent_answers"].append(answer)
    
    # Keep only last 5 interactions
    if len(context["recent_questions"]) > 5:
        context["recent_questions"] = context["recent_questions"][-5:]
        context["recent_answers"] = context["recent_answers"][-5:]
    
    # Update last interaction time
    context["last_interaction_time"] = time.time()
    
    # Extract possible judging mode preference
    if "online judging" in question.lower() or "online judging" in answer.lower():
        context["judging_mode_preference"] = "online"
    elif "offline judging" in question.lower() or "offline judging" in answer.lower():
        context["judging_mode_preference"] = "offline"
    elif "sponsor judging" in question.lower() or "sponsor judging" in answer.lower():
        context["judging_mode_preference"] = "sponsor"
    
    # Save updated context
    user_contexts[user_id] = context

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    user_id = str(user.id)
    logger.info(f"Start command from user: {user_id} ({user.username})")
    
    response = f"Hi {user.first_name}! I'm DevfolioAsk Bot. How can I help you with managing your hackathon on Devfolio?"
    await update.message.reply_text(response)
    
    # Store this interaction
    feedback_system.store_interaction(user_id, "/start", response)
    update_user_context(user_id, "/start", response)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    user = update.effective_user
    user_id = str(user.id)
    logger.info(f"Help command from user: {user_id} ({user.username})")
    
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
    
    # Store this interaction
    feedback_system.store_interaction(user_id, "/help", help_text)
    update_user_context(user_id, "/help", help_text)

async def process_question(question: str, user_id: str = None) -> tuple:
    """
    Process a question using knowledge base and OpenAI.
    
    Args:
        question: The user's question
        user_id: The user's Telegram ID for tracking interactions
        
    Returns:
        A tuple of (answer, interaction_id)
    """
    try:
        # Get user context if available
        context_info = ""
        if user_id and user_id in user_contexts:
            user_context = user_contexts[user_id]
            
            # Add judging mode preference if available
            if user_context["judging_mode_preference"]:
                context_info += f"The user has previously shown interest in {user_context['judging_mode_preference']} judging. "
            
            # Add recent conversation history for context
            if user_context["recent_questions"]:
                context_info += "Recent conversation history: "
                for i in range(min(3, len(user_context["recent_questions"]))):
                    context_info += f"User: {user_context['recent_questions'][-(i+1)]} | Bot: {user_context['recent_answers'][-(i+1)]} "
        
        # Query the knowledge base for relevant information
        answer_prefix, knowledge_context = knowledge_base.query(question)
        
        # Generate response using OpenAI with conversation context
        if knowledge_context:
            answer = await openai_client.generate_response(question, knowledge_context, context_info)
        else:
            answer = await openai_client.generate_response(
                question, 
                [{"source": "No specific source", "content": "No specific information found in the knowledge base."}],
                context_info
            )
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        answer = f"I'm sorry, I encountered an error while generating a response. Please try again later."
    
    # Store the interaction for potential feedback if user_id provided
    interaction_id = None
    if user_id:
        interaction_id = feedback_system.store_interaction(user_id, question, answer)
        # Update conversation context
        update_user_context(user_id, question, answer)
    
    return answer, interaction_id

async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /ask command."""
    question = " ".join(context.args)
    
    if not question:
        await update.message.reply_text("Please include your question after /ask")
        return
        
    logger.info(f"Question via /ask command: {question[:30]}...")
    
    # Process the question
    user_id = str(update.effective_user.id)
    answer, interaction_id = await process_question(question, user_id)
    
    # Send the response
    await update.message.reply_text(answer)

async def give_feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /give_feedback command to start feedback process."""
    # Only allow in private chats
    if update.message.chat.type != "private":
        await update.message.reply_text("The feedback command can only be used in private chats with me.")
        return
    
    user_id = str(update.effective_user.id)
    
    # Get recent interactions
    interactions = feedback_system.get_recent_interactions(user_id)
    
    if not interactions:
        await update.message.reply_text("You don't have any recent interactions to provide feedback on.")
        return
    
    # Start feedback process
    feedback_system.start_feedback(user_id)
    
    # Build message with recent interactions
    message = "Please select which interaction you'd like to provide feedback for by sending its number (1-5):\n\n"
    
    for i, interaction in enumerate(interactions[:5], 1):  # Limit to 5 most recent
        # Truncate question/answer for display
        q_short = interaction["question"][:50] + "..." if len(interaction["question"]) > 50 else interaction["question"]
        a_short = interaction["answer"][:50] + "..." if len(interaction["answer"]) > 50 else interaction["answer"]
        
        message += f"{i}. Q: {q_short}\nA: {a_short}\n\n"
    
    message += "To provide feedback, send the number (1-5) of the interaction you want to comment on."
    
    await update.message.reply_text(message)
    
    # Store this interaction
    feedback_system.store_interaction(user_id, "/give_feedback", message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages."""
    if not update.message or not update.message.text:
        return
        
    message = update.message
    text = message.text
    user = update.effective_user
    user_id = str(user.id)
    chat_type = message.chat.type
    
    logger.info(f"Received message in {chat_type} from {user_id} ({user.username}): {text[:20]}...")
    
    # Handle feedback process in private chat
    if chat_type == "private" and user_id in feedback_system.pending_feedback:
        result = feedback_system.process_feedback_message(user_id, text)
        
        if result["status"] == "success":
            if result["next_step"] == "provide_feedback":
                await message.reply_text(result["message"])
            elif result["next_step"] == "complete":
                await message.reply_text(result["message"])
        else:
            await message.reply_text(result["message"])
        
        return
    
    # Handle direct messages to the bot
    if chat_type == "private":
        logger.debug("Processing direct message")
        
        # Process the question
        answer, interaction_id = await process_question(text, user_id)
        
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
                answer, interaction_id = await process_question(question, user_id)
                
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
                welcome_message = (
                    "👋 Hello everyone! I'm DevfolioAsk Bot, your Devfolio assistant!\n\n"
                    "I can help answer questions about Devfolio platform features, workflows, and best practices. To ask me something:\n\n"
                    "• Mention me: @devfolioask_bot How do I create a hackathon?\n"
                    "• Or use command: /ask How do I create a hackathon?\n\n"
                    "I'm here to make your Devfolio experience smoother! 🚀"
                )
                await message.reply_text(welcome_message)
                
                # Store this interaction for the user who added the bot
                user_id = str(message.from_user.id)
                feedback_system.store_interaction(user_id, "Bot added to group", welcome_message)
                
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
    application.add_handler(CommandHandler("give_feedback", give_feedback_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat_members))

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
