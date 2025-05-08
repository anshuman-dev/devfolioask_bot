from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
import asyncio
from src.typing_handler import TypingHandler
import os
import logging
import time
import json
import re
from dotenv import load_dotenv
from src.knowledge import KnowledgeBase
from src.openai_client import OpenAIClient
from src.feedback import FeedbackSystem
from src.agentic_processor import AgenticProcessor

# Load environment variables
load_dotenv()

agentic_processor = AgenticProcessor()

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

# Pending questions/mentions tracking
pending_mentions = {}  # User mentioned bot but no question yet
pending_questions = {}  # User asked question but no bot mention yet

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
# Get or initialize user context
# Get or initialize user context
def get_user_context(user_id):
    if user_id not in user_contexts:
        user_contexts[user_id] = {
            "recent_questions": [],
            "recent_answers": [],
            "judging_mode_preference": None,
            "judging_enabled": False,
            "support_contact_suggested": False,
            "last_interaction_time": time.time()
        }
    return user_contexts[user_id]

# Update user context
# Update user context
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
    
    # Track judging-related information
    question_lower = question.lower()
    answer_lower = answer.lower()
    
    # Extract judging mode preferences
    if "online judging" in question_lower or "online judging" in answer_lower:
        context["judging_mode_preference"] = "online"
    elif "offline judging" in question_lower or "offline judging" in answer_lower:
        context["judging_mode_preference"] = "offline"
    elif "sponsor judging" in question_lower or "sponsor judging" in answer_lower:
        context["judging_mode_preference"] = "sponsor"
    
    # Track if judging has been enabled
    if ("enabled judging" in answer_lower or "judging is now enabled" in answer_lower or 
        "have enabled" in answer_lower and "judging" in answer_lower):
        context["judging_enabled"] = True
    
    # Track if user has been instructed to contact support
    if "@singhanshuman8" in answer:
        context["support_contact_suggested"] = True
    
    # Save updated context
    user_contexts[user_id] = context

# Check if message is a simple greeting
def is_greeting(text):
    greetings = ["hi", "hello", "hey", "hola", "namaste", "greetings", "yo", "hiya", "howdy", "hii", "hiii", "hiiii"]
    text_lower = text.lower().strip()
    
    # Check if the text is just a greeting
    for greeting in greetings:
        if text_lower == greeting or text_lower.startswith(greeting + " ") or text_lower.endswith(" " + greeting):
            return True
            
    # Check common greeting patterns like "hi there", "hello everyone"
    common_patterns = [
        r'^hi\s+\w+$',
        r'^hello\s+\w+$',
        r'^hey\s+\w+$',
        r'^hi+$',  # Matches "hiii", "hiiiiii", etc.
    ]
    
    for pattern in common_patterns:
        if re.match(pattern, text_lower):
            return True
            
    return False

# Generate greeting response
def get_greeting_response():
    greetings = [
        "Hello! I'm DevfolioAsk Bot, your assistant for Devfolio platform questions. How can I help you today?",
        "Hi there! I'm here to answer your questions about the Devfolio platform. What would you like to know?",
        "Hey! I'm DevfolioAsk Bot. I can provide information about Devfolio's features, including hackathon setup, judging, submissions, and more. What can I help you with?",
        "Greetings! I'm your Devfolio assistant bot. How can I assist you with your hackathon organization needs?",
        "Hello! I'm here to help with your Devfolio questions. Feel free to ask me about setting up hackathons, judging, or other platform features."
    ]
    
    import random
    return random.choice(greetings)

# Check for pending mention
def check_pending_mention(chat_id, user_id):
    key = f"{chat_id}_{user_id}"
    now = time.time()
    
    if key in pending_mentions:
        timestamp, _ = pending_mentions[key]
        # If mention is less than 60 seconds old, it's still valid
        if now - timestamp < 60:
            return True
    return False

# Set pending mention
def set_pending_mention(chat_id, user_id):
    key = f"{chat_id}_{user_id}"
    pending_mentions[key] = (time.time(), None)
    
    # Schedule cleanup of old mentions
    cleanup_old_pendings()

# Get and clear pending mention
def get_and_clear_pending_mention(chat_id, user_id):
    key = f"{chat_id}_{user_id}"
    if key in pending_mentions:
        result = pending_mentions[key]
        del pending_mentions[key]
        return result
    return None

# Check for pending question
def check_pending_question(chat_id, user_id):
    key = f"{chat_id}_{user_id}"
    now = time.time()
    
    if key in pending_questions:
        timestamp, question = pending_questions[key]
        # If question is less than 60 seconds old, it's still valid
        if now - timestamp < 60:
            return question
    return None

# Set pending question
def set_pending_question(chat_id, user_id, question):
    key = f"{chat_id}_{user_id}"
    pending_questions[key] = (time.time(), question)
    
    # Schedule cleanup of old questions
    cleanup_old_pendings()

# Get and clear pending question
def get_and_clear_pending_question(chat_id, user_id):
    key = f"{chat_id}_{user_id}"
    if key in pending_questions:
        result = pending_questions[key]
        del pending_questions[key]
        return result
    return None

# Cleanup old pending mentions and questions
def cleanup_old_pendings():
    now = time.time()
    
    # Clean up mentions older than 60 seconds
    for key in list(pending_mentions.keys()):
        timestamp, _ = pending_mentions[key]
        if now - timestamp > 60:
            del pending_mentions[key]
    
    # Clean up questions older than 60 seconds
    for key in list(pending_questions.keys()):
        timestamp, _ = pending_questions[key]
        if now - timestamp > 60:
            del pending_questions[key]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    user_id = str(user.id)
    logger.info(f"Start command from user: {user_id} ({user.username})")
    
    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, 
        action=ChatAction.TYPING
    )
    
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
    
    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, 
        action=ChatAction.TYPING
    )
    
    help_text = """
I'm DevfolioAsk Bot, your Devfolio assistant!

In a group chat:
- Mention me with @devfolioask_bot followed by your question
- Example: @devfolioask_bot How to add judges to the platform?


I'll do my best to provide accurate information based on Devfolio documentation.
    """
    await update.message.reply_text(help_text)
    
    # Store this interaction
    feedback_system.store_interaction(user_id, "/help", help_text)
    update_user_context(user_id, "/help", help_text)

async def process_question(question: str, user_id: str = None, chat_id: str = None, bot = None) -> tuple:
    """
    Process a question using the agentic processor.
    
    Args:
        question: The user's question
        user_id: The user's Telegram ID for tracking interactions
        chat_id: Chat ID for sending typing indicators
        bot: Bot instance for sending typing indicators
        
    Returns:
        A tuple of (answer, interaction_id)
    """
    try:
        # Get user context if available
        conversation_context = None
        if user_id and user_id in user_contexts:
            conversation_context = user_contexts[user_id]
        
        # Process using agentic processor
        answer, interaction_id = await agentic_processor.process_question(
            question, 
            user_id=user_id, 
            chat_id=chat_id, 
            bot=bot, 
            conversation_context=conversation_context
        )
    
        # Store the interaction for potential feedback if user_id provided
        if user_id:
            if not interaction_id:
                interaction_id = feedback_system.store_interaction(user_id, question, answer)
            # Update conversation context
            update_user_context(user_id, question, answer)
        
        return answer, interaction_id
        
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        answer = f"I'm sorry, I encountered an error while generating a response. Please try again later."
        return answer, None

async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /ask command."""
    question = " ".join(context.args)
    
    if not question:
        await update.message.reply_text("Please include your question after /ask")
        return
        
    logger.info(f"Question via /ask command: {question[:30]}...")
    
    # Process the question
    user_id = str(update.effective_user.id)
    chat_id = update.effective_chat.id
    answer, interaction_id = await process_question(question, user_id, chat_id, context.bot)
    
    # Send the response
    await update.message.reply_text(answer)

async def give_feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /give_feedback command to start feedback process."""
    # Only allow in private chats
    if update.message.chat.type != "private":
        await update.message.reply_text("The feedback command can only be used in private chats with me.")
        return
    
    user_id = str(update.effective_user.id)
    
    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, 
        action=ChatAction.TYPING
    )
    
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

# Extract question from message with bot mention
def extract_question_from_mention(text, bot_username):
    """
    Extract question from a message that mentions the bot.
    
    This handles various patterns:
    - Mention at start: "@bot how do I..."
    - Mention in middle: "I want to ask @bot how do I..."
    - Mention at end: "How do I add judges? @bot"
    - Mention on separate line: "How do I add judges?\n@bot"
    """
    # Log the original text for debugging
    logger.debug(f"Extracting question from: {text}")
    
    # Full bot mention with @ symbol
    bot_mention = f"@{bot_username}"
    
    # Check if the text contains the bot mention
    if bot_mention.lower() not in text.lower():
        return ""
    
    # CASE 1: Simple greeting with bot mention - treat the whole thing as a greeting
    text_without_mention = re.sub(f'@{bot_username}', '', text, flags=re.IGNORECASE).strip()
    if is_greeting(text_without_mention) or not text_without_mention:
        logger.debug("Detected greeting with bot mention")
        return "greeting"
        
    # CASE 2: If mention is at the beginning, take everything after as the question
    if text.lower().strip().startswith(bot_mention.lower()):
        question = text[text.lower().find(bot_mention.lower()) + len(bot_mention):].strip()
        logger.debug(f"Bot mention at beginning. Question: {question}")
        if question:
            return question
        else:
            return "greeting"  # Just the mention with nothing after
    
    # CASE 3: If mention is at the end, take everything before as the question
    if text.lower().strip().endswith(bot_mention.lower()):
        question = text[:text.lower().rfind(bot_mention.lower())].strip()
        logger.debug(f"Bot mention at end. Question: {question}")
        return question
    
    # CASE 4: If mention is on its own line, get the surrounding content
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if bot_mention.lower() in line.lower() and line.strip().lower() == bot_mention.lower():
            # If mention is on last line, take everything before
            if i == len(lines) - 1:
                question = '\n'.join(lines[:i]).strip()
                logger.debug(f"Bot mention on last line. Question: {question}")
                return question
            # If mention is on first line, take everything after
            elif i == 0 and len(lines) > 1:
                question = '\n'.join(lines[1:]).strip()
                logger.debug(f"Bot mention on first line. Question: {question}")
                return question
            # If mention is in the middle on its own line, take everything
            else:
                question_before = '\n'.join(lines[:i]).strip()
                question_after = '\n'.join(lines[i+1:]).strip()
                # Prefer what comes after the mention if available
                if question_after:
                    logger.debug(f"Bot mention in middle (own line). Using after: {question_after}")
                    return question_after
                else:
                    logger.debug(f"Bot mention in middle (own line). Using before: {question_before}")
                    return question_before
    
    # CASE 5: Mention is in the middle of text on same line
    parts = re.split(f'@{bot_username}', text, flags=re.IGNORECASE)
    if len(parts) == 2:
        before = parts[0].strip()
        after = parts[1].strip()
        
        # Prefer what comes after the mention
        if after:
            logger.debug(f"Bot mention in middle (same line). Using after: {after}")
            return after
        # Otherwise use what comes before
        elif before:
            logger.debug(f"Bot mention in middle (same line). Using before: {before}")
            return before
    
    # CASE 6: Just take the whole message as the question
    logger.debug(f"Using entire message as question: {text}")
    return text

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages."""
    if not update.message or not update.message.text:
        return
        
    message = update.message
    text = message.text
    user = update.effective_user
    user_id = str(user.id)
    chat_type = message.chat.type
    chat_id = update.effective_chat.id
    
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
        answer, interaction_id = await process_question(text, user_id, chat_id, context.bot)
        
        # Send the response
        await message.reply_text(answer)
        return
    
    # Handle group messages
    if chat_type in ["group", "supergroup"]:
        # Get bot info
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username
        
        # Check if the message mentions the bot
        bot_mentioned = f"@{bot_username}".lower() in text.lower()
        
        # Case 1: Message contains bot mention
        if bot_mentioned:
            # Extract question from the current message
            question = extract_question_from_mention(text, bot_username)
            
            # If no question in current message, check for pending question
            if not question or question == "greeting":
                pending_q = get_and_clear_pending_question(chat_id, user_id)
                
                if pending_q:
                    # Use the pending question from previous message
                    timestamp, question = pending_q
                    logger.info(f"Using pending question from {time.time() - timestamp:.1f}s ago: {question[:30]}...")
                else:
                    # No question found, set pending mention for future question
                    set_pending_mention(chat_id, user_id)
                    
                    if question == "greeting":
                        # It's a simple greeting, respond with greeting
                        answer = get_greeting_response()
                        await message.reply_text(answer)
                    else:
                        # No question, ask for one
                        await message.reply_text("I'm here! How can I help you with Devfolio?")
                    return
                
            # Process the question
            answer, interaction_id = await process_question(question, user_id, chat_id, context.bot)
            
            # Send the response
            await message.reply_text(answer)
            
        # Case 2: Message doesn't mention bot but might be a question for a previous mention
        else:
            # Check if there's a pending mention waiting for a question
            if check_pending_mention(chat_id, user_id):
                logger.info(f"Found pending mention for user {user_id}, processing as question: {text[:30]}...")
                
                # Clear the pending mention
                get_and_clear_pending_mention(chat_id, user_id)
                
                # Process this as a question
                answer, interaction_id = await process_question(text, user_id, chat_id, context.bot)
                
                # Send the response
                await message.reply_text(answer)
            else:
                # No pending mention, but store this as a potential question for future mention
                # Only store if it seems like a question (contains question-like words or ends with ?)
                question_indicators = ["how", "what", "where", "when", "why", "who", "which", "?", "can", "is", "are", "will"]
                is_likely_question = any(indicator in text.lower() for indicator in question_indicators) or text.strip().endswith("?")
                
                if is_likely_question:
                    logger.debug(f"Storing potential question for future mention: {text[:30]}...")
                    set_pending_question(chat_id, user_id, text)

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
                
                # Show typing indicator
                await context.bot.send_chat_action(
                    chat_id=update.effective_chat.id, 
                    action=ChatAction.TYPING
                )
                
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
