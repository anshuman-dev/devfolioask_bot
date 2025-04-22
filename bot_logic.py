import os
import logging
import json
import datetime
from telegram import Update, BotCommand, BotCommandScopeChat
from telegram.ext import (
    CommandHandler, ContextTypes, filters, MessageHandler,
    ChatMemberHandler
)
from ai_engine import ai_engine

logger = logging.getLogger(__name__)

# Configuration
ADMIN_IDS = [int(id) for id in os.environ.get("ADMIN_IDS", "").split(",") if id]
LOG_FILE = "query_logs.json"

# Logging functions
def _load_query_logs():
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r') as f:
                return json.load(f)
        return []
    except:
        return []

def save_query_log(user_id, username, command, query):
    logs = _load_query_logs()
    
    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "user_id": user_id,
        "username": username,
        "command": command,
        "query": query
    }
    
    logs.append(log_entry)
    
    with open(LOG_FILE, 'w') as f:
        json.dump(logs, f, indent=2)
        
    # Return a unique ID for this query (timestamp can serve as ID)
    return log_entry["timestamp"]

def get_authorized_users():
    """Get list of authorized usernames"""
    authorized_users_file = "authorized_users.json"
    
    try:
        if os.path.exists(authorized_users_file):
            with open(authorized_users_file, 'r') as f:
                data = json.load(f)
                return data.get("authorized_users", [])
    except Exception as e:
        logger.error(f"Error loading authorized users: {e}")
    
    # Default authorized users if file doesn't exist or has an error
    return []

# Command handlers
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    authorized_users = get_authorized_users()
    
    # Check if user is authorized for direct chat
    if update.message.chat.type == "private" and user.username not in authorized_users and user.id not in ADMIN_IDS:
        await update.message.reply_text(
            "Sorry, I'm only accessible in group chats unless you're an authorized user. "
            "Please add me to a group chat to interact with me."
        )
        return
    
    await update.message.reply_text(
        f"Hey {user.first_name}! I'm your AI-powered judging helper bot. I can answer questions about setting up judging, rooms, and inviting judges.\n\n"
        "To ask me a question, simply mention me in a message like this:\n"
        f"@{context.bot.username} how do I add judges?\n\n"
        "I'll respond with the information you need."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    authorized_users = get_authorized_users()
    
    # Check if user is authorized for direct chat
    if update.message.chat.type == "private" and user.username not in authorized_users and user.id not in ADMIN_IDS:
        await update.message.reply_text(
            "Sorry, I'm only accessible in group chats unless you're an authorized user."
        )
        return
    
    await update.message.reply_text(
        "I'm an AI-powered assistant that helps with judging-related questions.\n\n"
        "To use me, simply mention me in your message followed by your question:\n"
        f"@{context.bot.username} how do I set up judging?\n\n"
        "I'll respond with helpful information based on the Devfolio documentation."
    )

async def refresh_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("Sorry, only admins can do that.")
        return
    
    await update.message.reply_text("Refreshing my knowledge base, this might take a few minutes...")
    
    # Show typing indicator during the process
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    result = ai_engine.refresh_knowledge_base()
    
    if result["success"]:
        await update.message.reply_text(
            f"✅ Knowledge base updated successfully!\n"
            f"Indexed {result.get('chunk_count', 'unknown')} chunks of information."
        )
    else:
        await update.message.reply_text(f"❌ Error updating knowledge base: {result.get('error', 'unknown error')}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle direct messages or mentions in groups"""
    message = update.message
    
    # Only respond to text messages
    if not message.text:
        return
    
    # Get bot's username
    bot_username = context.bot.username
    
    # Debug log
    logger.info(f"Received message: '{message.text}' in chat type: {message.chat.type}")
    logger.info(f"Bot username is: {bot_username}")
    
    # In groups, only respond to mentions
    if message.chat.type in ["group", "supergroup"]:
        mention_text = f"@{bot_username}"
        logger.info(f"Looking for mention: '{mention_text}' in text")
        
        if mention_text.lower() in message.text.lower():
            logger.info("Found mention in message")
            # Extract query from mention
            query = message.text.replace(mention_text, "").strip()
            
            if not query:
                logger.info("Empty query after mention")
                await message.reply_text("How can I help you? Please include your question after mentioning me.")
                return
            
            logger.info(f"Extracted query: '{query}'")
            
            # Log the query
            user = update.effective_user
            save_query_log(user.id, user.username or "unknown", "mention", query)
            
            # Show typing indicator
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            try:
                # Get answer from AI
                logger.info(f"Sending query to AI engine: '{query}'")
                answer = ai_engine.answer_query(query, user.id, user.username)
                logger.info(f"Received answer from AI engine: '{answer[:50]}...'")
                
                # Send response
                await message.reply_text(answer)
                logger.info("Sent response to user")
            except Exception as e:
                logger.error(f"Error getting answer from AI: {e}")
                await message.reply_text("Sorry, I encountered an error while processing your question. Please try again later.")
        else:
            logger.info(f"No mention found in message")

async def handle_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle updates to the bot's chat member status (added/removed from groups)"""
    chat_member_update = update.my_chat_member
    
    # Only process group/supergroup events
    chat = chat_member_update.chat
    if chat.type not in ["group", "supergroup"]:
        return
    
    # Check if the bot was added to a group
    old_status = chat_member_update.old_chat_member.status
    new_status = chat_member_update.new_chat_member.status
    
    if old_status in ["left", "kicked"] and new_status in ["member", "administrator"]:
        # Bot was added to a group - check who added it
        user = chat_member_update.from_user
        authorized_users = get_authorized_users()
        
        if user.username not in authorized_users and user.id not in ADMIN_IDS:
            # Unauthorized user added the bot - leave the group
            await context.bot.send_message(
                chat_id=chat.id,
                text="Sorry, only authorized users can add me to groups. I'll be leaving this chat."
            )
            await context.bot.leave_chat(chat.id)

async def set_commands(application):
    """Set up minimal commands in the Telegram UI"""
    commands = [
        BotCommand("start", "Get information about the bot"),
        BotCommand("help", "Learn how to use the bot")
    ]
    
    # Only show admin commands to admins
    admin_commands = [
        BotCommand("refresh", "Update knowledge base (admin only)")
    ]
    
    # Set regular commands for all users
    await application.bot.set_my_commands(commands)
    
    # Set admin commands for admin users
    for admin_id in ADMIN_IDS:
        try:
            await application.bot.set_my_commands(
                commands + admin_commands,
                scope=BotCommandScopeChat(chat_id=admin_id)
            )
        except Exception as e:
            logger.error(f"Failed to set admin commands for {admin_id}: {e}")

def setup_handlers(application):
    # Set up commands in Telegram UI
    application.post_init = set_commands
    
    # Register minimal command handlers
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    
    # Admin commands
    application.add_handler(CommandHandler("refresh", refresh_cmd))
    
    # The main functionality: Handle direct messages and mentions
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_message
    ))
    
    # Handle chat member updates (for group invite restrictions)
    application.add_handler(ChatMemberHandler(
        handle_my_chat_member,
        ChatMemberHandler.MY_CHAT_MEMBER
    ))
    
    # Handle unknown commands
    application.add_handler(MessageHandler(filters.COMMAND, unknown_cmd))

async def unknown_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    authorized_users = get_authorized_users()
    
    # Check if user is authorized for direct chat
    if update.message.chat.type == "private" and user.username not in authorized_users and user.id not in ADMIN_IDS:
        await update.message.reply_text(
            "Sorry, I'm only accessible in group chats unless you're an authorized user."
        )
        return
    
    await update.message.reply_text(
        f"I don't respond to commands. Just mention me like this:\n@{context.bot.username} your question"
    )