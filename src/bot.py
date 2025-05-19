from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
import asyncio
import os
import logging
import time
import json
import re
from dotenv import load_dotenv
from src.knowledge import KnowledgeBase
from src.openai_client import OpenAIClient
from src.feedback import FeedbackSystem
from src.open_ai_eval import OpenAIEvalSystem
from src.agentic_processor import AgenticProcessor
from src.context_store import ContextStore
from src.context_inference_engine import ContextInferenceEngine
# Add to the imports section at the top of bot.py:
import time
from src.auto_eval_service import AutoEvalService

# Add after the other service initializations:

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG
)
logger = logging.getLogger(__name__)

auto_eval_service = AutoEvalService()
logger.info("Auto-evaluation service initialized")

# Get environment variables
TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USERNAMES = os.getenv("ALLOWED_USERNAMES", "").split(",")

# Initialize knowledge base, OpenAI client, and feedback system
knowledge_base = KnowledgeBase()
openai_client = OpenAIClient()
feedback_system = FeedbackSystem()
agentic_processor = AgenticProcessor()
openai_eval_system = OpenAIEvalSystem()

# Initialize context management
context_store = ContextStore()
context_inference_engine = ContextInferenceEngine()

# Pending questions/mentions tracking
pending_mentions = {}  # User mentioned bot but no question yet
pending_questions = {}  # User asked question but no bot mention yet

# Conversation states for feedback
SELECTING_INTERACTION, SELECTING_FEEDBACK_TYPE, PROVIDING_FEEDBACK, CONFIRMING_FEEDBACK = range(4)

# Log configuration on startup
logger.info(f"Starting bot with token: {TOKEN[:5] if TOKEN else 'None'}...")
logger.info(f"Allowed usernames: {ALLOWED_USERNAMES}")

# Check if a user is authorized to add the bot to a group
def is_authorized(username):
    logger.debug(f"Checking if username '{username}' is authorized among {ALLOWED_USERNAMES}")
    if not username:
        return False
    return username in ALLOWED_USERNAMES or not ALLOWED_USERNAMES[0]  # Allow all if empty

def get_user_context(user_id: str, username: str = None) -> Dict[str, Any]:
    """
    Get user context with enhanced structure.
    
    Args:
        user_id: User ID to get context for
        username: Optional username to store in context
        
    Returns:
        User context dictionary
    """
    # Get context from store
    context = context_store.get_user_context(user_id)
    
    # Update username if provided
    if username and not context["identity"]["username"]:
        context["identity"]["username"] = username
        context_store.update_user_context(user_id, context)
        
    return context

def update_user_context(user_id: str, question: str, answer: str) -> Dict[str, Any]:
    """
    Update user context with enhanced inference.
    
    Args:
        user_id: User ID to update context for
        question: User's question
        answer: Bot's answer
        
    Returns:
        Updated context dictionary
    """
    # Get current context
    context = get_user_context(user_id)
    
    # Use inference engine to update context based on conversation
    updated_context = context_inference_engine.update_context(context, question, answer)
    
    # Save to context store
    context_store.update_user_context(user_id, updated_context)
    
    return updated_context

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

# Update the process_question function in bot.py to add auto-evaluation

async def process_question(question: str, user_id: str = None, chat_id: str = None, bot = None) -> tuple:
    """
    Process a question using the agentic processor and auto-evaluate the response.
    
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
        if user_id:
            conversation_context = get_user_context(user_id)
        
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
        
        # Auto-evaluate every response
        auto_eval_service.queue_evaluation(question, answer)
        logger.info(f"Queued auto-evaluation for interaction: {interaction_id if interaction_id else 'unknown'}")
        
        return answer, interaction_id
        
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        answer = f"I'm sorry, I encountered an error while generating a response. Please try again later."
        return answer, None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    user_id = str(user.id)
    username = user.username
    logger.info(f"Start command from user: {user_id} ({username})")
    
    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, 
        action=ChatAction.TYPING
    )
    
    # Get user context with username
    user_context = get_user_context(user_id, username)
    
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
    
    user = update.effective_user
    user_id = str(user.id)
    username = user.username
    
    # Check if user is authorized for DM feedback
    if not feedback_system.is_authorized_for_dm_feedback(username):
        await update.message.reply_text("Sorry, you're not authorized to provide feedback via DM.")
        return
    
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
    message = "Please select which interaction you'd like to provide feedback for by tapping the number:\n\n"
    
    # Create inline keyboard with buttons for each interaction
    keyboard = []
    for i, interaction in enumerate(interactions[:5], 1):  # Limit to 5 most recent
        # Truncate question for display
        q_short = interaction["question"][:50] + "..." if len(interaction["question"]) > 50 else interaction["question"]
        
        message += f"{i}. Q: {q_short}\n\n"
        keyboard.append([InlineKeyboardButton(f"{i}", callback_data=f"feedback_interaction_{i}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(message, reply_markup=reply_markup)
    
    # Store this interaction
    feedback_system.store_interaction(user_id, "/give_feedback", message)
    
    return SELECTING_INTERACTION

async def feedback_interaction_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle interaction selection for feedback."""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    # Extract the selected interaction number
    interaction_number = int(query.data.split("_")[-1])
    
    # Get the interactions and find the selected one
    interactions = feedback_system.get_recent_interactions(user_id)
    if interaction_number <= len(interactions):
        selected_interaction = interactions[interaction_number-1]
        interaction_id = selected_interaction["id"]
        
        # Update feedback state
        feedback_system.pending_feedback[user_id] = {
            "state": "awaiting_feedback_type",
            "interaction_id": interaction_id
        }
        
        # Show feedback type options
        feedback_types = feedback_system.get_feedback_types()
        keyboard = []
        for i, feedback_type in enumerate(feedback_types, 1):
            keyboard.append([InlineKeyboardButton(feedback_type, callback_data=f"feedback_type_{i}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Show the question and answer for reference
        q_full = selected_interaction["question"]
        a_full = selected_interaction["answer"]
        
        message = f"You selected:\n\nQuestion: {q_full}\n\nAnswer: {a_full}\n\nPlease select a feedback type:"
        
        # Edit the message to show feedback type options
        await query.edit_message_text(message, reply_markup=reply_markup)
        
        return SELECTING_FEEDBACK_TYPE
    else:
        await query.edit_message_text("Invalid selection. Please try again.")
        return ConversationHandler.END

async def feedback_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle feedback type selection."""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    # Extract the selected feedback type
    feedback_type_idx = int(query.data.split("_")[-1])
    feedback_types = feedback_system.get_feedback_types()
    feedback_type = feedback_types[feedback_type_idx-1]
    
    # Update feedback state
    feedback_system.pending_feedback[user_id]["state"] = "awaiting_feedback_text"
    feedback_system.pending_feedback[user_id]["feedback_type"] = feedback_type
    
    # Ask for detailed feedback
    message = f"You selected '{feedback_type}'. Please type your detailed feedback about this response:"
    
    await query.edit_message_text(message)
    
    return PROVIDING_FEEDBACK

async def feedback_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle receiving detailed feedback text."""
    user_id = str(update.effective_user.id)
    feedback_text = update.message.text
    
    # Update feedback state
    feedback_system.pending_feedback[user_id]["state"] = "awaiting_confirmation"
    feedback_system.pending_feedback[user_id]["feedback_text"] = feedback_text
    
    # Ask for confirmation
    keyboard = [
        [InlineKeyboardButton("Yes", callback_data="feedback_more_yes")],
        [InlineKeyboardButton("No", callback_data="feedback_more_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("Thank you for your feedback. Would you like to add more feedback?", reply_markup=reply_markup)
    
    return CONFIRMING_FEEDBACK

async def feedback_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle feedback confirmation."""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    add_more = query.data == "feedback_more_yes"
    
    if add_more:
        # Ask for more feedback
        feedback_system.pending_feedback[user_id]["state"] = "awaiting_feedback_text"
        await query.edit_message_text("Please provide additional feedback:")
        return PROVIDING_FEEDBACK
    else:
        # Save the feedback
        interaction_id = feedback_system.pending_feedback[user_id]["interaction_id"]
        feedback_type = feedback_system.pending_feedback[user_id]["feedback_type"]
        feedback_text = feedback_system.pending_feedback[user_id]["feedback_text"]
        
        interaction = feedback_system.recent_interactions.get(interaction_id)
        if not interaction:
            # Clean up the pending state
            if user_id in feedback_system.pending_feedback:
                del feedback_system.pending_feedback[user_id]
            await query.edit_message_text("Interaction not found. Feedback process canceled.")
            return ConversationHandler.END
        
        # Save the feedback
        feedback_saved = feedback_system.save_structured_feedback(
            interaction["question"],
            interaction["answer"],
            feedback_type,
            feedback_text,
            user_id
        )
        
        # Clean up the pending state
        if user_id in feedback_system.pending_feedback:
            del feedback_system.pending_feedback[user_id]
        
        if feedback_saved:
            await query.edit_message_text("Thank you for your feedback! It will help improve the bot.")
            
            # Trigger OpenAI eval for this feedback
            try:
                # Only run eval for certain feedback types
                if feedback_type in ["Not Helpful", "Incorrect", "Confusing"]:
                    # Create eval data
                    eval_data = [{
                        "question": interaction["question"],
                        "answer": interaction["answer"],
                        "correct_answer": "",  # We don't have a ground truth here
                        "feedback": feedback_text,
                        "feedback_type": feedback_type
                    }]
                    
                    # Schedule async eval (don't await to avoid blocking)
                    context.application.create_task(
                        run_openai_eval(eval_data, interaction["question"], interaction["answer"])
                    )
            except Exception as e:
                logger.error(f"Error scheduling OpenAI eval: {e}")
            
        else:
            await query.edit_message_text("Failed to save feedback. Please try again later.")
        
        return ConversationHandler.END

async def run_openai_eval(eval_data, question, answer):
    """Run OpenAI eval for a feedback item asynchronously."""
    try:
        logger.info(f"Running OpenAI eval for question: {question[:30]}...")
        
        # Run helpfulness eval
        result = await asyncio.to_thread(
            openai_eval_system.evaluate_responses,
            [{"question": question, "answer": answer, "correct_answer": ""}],
            "helpfulness_eval",
            "gpt-4"
        )
        
        # Log results
        logger.info(f"OpenAI eval results: {result.get('status')} - Pass rate: {result.get('pass_rate', 0)}%")
        
    except Exception as e:
        logger.error(f"Error running OpenAI eval: {e}")

async def save_contexts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to manually save all contexts."""
    user = update.effective_user
    user_id = str(user.id)
    
    # Check if user is an admin
    if user_id not in os.getenv("ADMIN_IDS", "").split(","):
        await update.message.reply_text("Sorry, only admins can use this command.")
        return
        
    # Save all contexts
    context_store.save_all_dirty()
    
    await update.message.reply_text("All user contexts have been saved.")

async def run_eval_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to run an evaluation of recent responses."""
    user = update.effective_user
    user_id = str(user.id)
    
    # Check if user is an admin
    if user_id not in os.getenv("ADMIN_IDS", "").split(","):
        await update.message.reply_text("Sorry, only admins can use this command.")
        return
    
    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, 
        action=ChatAction.TYPING
    )
    
    try:
        # Get recent interactions for evaluation
        all_interactions = []
        for int_id, data in feedback_system.recent_interactions.items():
            all_interactions.append({
                "id": int_id,
                "question": data["question"],
                "answer": data["answer"],
                "timestamp": data["timestamp"],
                "user_id": data["user_id"]
            })
        
        # Sort by timestamp (newest first) and take the most recent 10
        all_interactions.sort(key=lambda x: x["timestamp"], reverse=True)
        recent_interactions = all_interactions[:10]
        
        if not recent_interactions:
            await update.message.reply_text("No recent interactions found for evaluation.")
            return
        
        # Prepare eval data
        eval_data = []
        for interaction in recent_interactions:
            eval_data.append({
                "question": interaction["question"],
                "answer": interaction["answer"],
                "correct_answer": ""  # We don't have ground truth here
            })
        
        await update.message.reply_text("Evaluation started. This may take a few minutes...")
        
        # Run helpfulness eval asynchronously
        result = await asyncio.to_thread(
            openai_eval_system.evaluate_responses,
            eval_data,
            "helpfulness_eval",
            "gpt-4"
        )
        
        # Format and send results
        if result.get("status") == "completed":
            summary = f"Evaluation Results (Helpfulness):\n\n"
            summary += f"Total Items: {result.get('total_items', 0)}\n"
            summary += f"Passed: {result.get('passed_items', 0)}\n"
            summary += f"Failed: {result.get('failed_items', 0)}\n"
            summary += f"Pass Rate: {result.get('pass_rate', 0):.1f}%\n\n"
            
            # Include detailed results
            if "items" in result:
                summary += "Detailed Results:\n\n"
                for i, item in enumerate(result["items"][:5], 1):  # Show first 5 items
                    summary += f"{i}. Q: {item.get('question', '')[:50]}...\n"
                    summary += f"   Status: {item.get('status', 'unknown')}\n\n"
            
            await update.message.reply_text(summary)
        else:
            await update.message.reply_text(f"Evaluation failed: {result.get('error', 'Unknown error')}")
        
    except Exception as e:
        logger.error(f"Error running evaluation: {e}")
        await update.message.reply_text(f"Error running evaluation: {str(e)}")

async def cancel_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the feedback conversation."""
    user_id = str(update.effective_user.id)
    
    # Clean up pending feedback state
    if user_id in feedback_system.pending_feedback:
        del feedback_system.pending_feedback[user_id]
    
    await update.message.reply_text("Feedback process canceled.")
    
    return ConversationHandler.END

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
            if result["next_step"] == "select_feedback_type":
                # Create inline keyboard for feedback types
                keyboard = []
                for i, option in enumerate(result["options"], 1):
                    keyboard.append([InlineKeyboardButton(option, callback_data=f"feedback_type_{i}")])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await message.reply_text(result["message"], reply_markup=reply_markup)
                
            elif result["next_step"] == "provide_feedback_text":
                await message.reply_text(result["message"])
                
            elif result["next_step"] == "confirm_feedback":
                # Create inline keyboard for confirmation
                keyboard = [
                    [InlineKeyboardButton("Yes", callback_data="feedback_more_yes")],
                    [InlineKeyboardButton("No", callback_data="feedback_more_no")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await message.reply_text(result["message"], reply_markup=reply_markup)
                
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
    application.add_handler(CommandHandler("save_contexts", save_contexts_command))
    application.add_handler(CommandHandler("run_eval", run_eval_command))
    
    # Add conversation handler for feedback
    feedback_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("give_feedback", give_feedback_command)],
        states={
            SELECTING_INTERACTION: [
                CallbackQueryHandler(feedback_interaction_selected, pattern=r"^feedback_interaction_\d+$"),
            ],
            SELECTING_FEEDBACK_TYPE: [
                CallbackQueryHandler(feedback_type_selected, pattern=r"^feedback_type_\d+$"),
            ],
            PROVIDING_FEEDBACK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, feedback_text_received),
            ],
            CONFIRMING_FEEDBACK: [
                CallbackQueryHandler(feedback_confirmation, pattern=r"^feedback_more_(yes|no)$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_feedback)],
    )
    application.add_handler(feedback_conv_handler)

    # Regular message handler (must come after conversation handlers)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat_members))

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot is starting...")
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    finally:
        # Save all contexts on shutdown
        logger.info("Bot shutting down, saving all contexts...")
        context_store.save_all_dirty()

if __name__ == "__main__":
    main()