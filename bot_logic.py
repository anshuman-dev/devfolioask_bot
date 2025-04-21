import os
import logging
import json
import datetime
from telegram import Update, BotCommand
from telegram.ext import CommandHandler, ContextTypes, filters, MessageHandler
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

# Command handlers
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Hey {user.first_name}! I'm your AI-powered judging helper bot. I can answer questions about setting up judging, rooms, and inviting judges.\n\n"
        "Use these commands:\n"
        "/help - Show all commands\n"
        "/ask your question - Ask me anything about judging\n"
        "/refresh - Admin only: update my knowledge"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "How to use this AI bot:\n\n"
        "/start - Get a welcome message\n"
        "/help - See this help message\n"
        "/ask question - Ask me anything about judging\n"
        "/contact - Get human support contacts\n\n"
        "Examples:\n"
        "/ask how do I create a judging room?\n"
        "/ask what's the best way to invite judges?"
    )

async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    user = update.effective_user
    
    if not query:
        await update.message.reply_text("Please include your question. For example: /ask how do I set up judging?")
        return
    
    # Log the query
    save_query_log(user.id, user.username or "unknown", "ask", query)
    
    # Show typing indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # Get answer from AI
    answer = ai_engine.answer_query(query, user.id, user.username)
    
    await update.message.reply_text(answer)

async def contact_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Need to talk to a human? Contact our team:\n"
        "Email: support@example.com\n"
        "Telegram: @your_support_username"
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
        
    # In groups, only respond to mentions
    if message.chat.type in ["group", "supergroup"]:
        bot_username = context.bot.username
        if not f"@{bot_username}" in message.text:
            return
            
        # Extract query from mention
        query = message.text.replace(f"@{bot_username}", "").strip()
        if not query:
            return
    else:
        # In private chats, respond to any message
        query = message.text
    
    # Log the query
    user = update.effective_user
    save_query_log(user.id, user.username or "unknown", "message", query)
    
    # Show typing indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # Get answer from AI
    answer = ai_engine.answer_query(query, user.id, user.username)
    
    await message.reply_text(answer)

async def set_commands(application):
    """Set up the bot commands in the Telegram UI"""
    commands = [
        BotCommand("start", "Get started with the bot"),
        BotCommand("help", "See available commands"),
        BotCommand("ask", "Ask me anything about judging"),
        BotCommand("contact", "Get human support contact info")
    ]
    
    await application.bot.set_my_commands(commands)

def setup_handlers(application):
    # Set up commands in Telegram UI
    application.post_init = set_commands
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("ask", ask_cmd))
    application.add_handler(CommandHandler("contact", contact_cmd))
    
    # Admin commands
    application.add_handler(CommandHandler("refresh", refresh_cmd))
    
    # Handle direct messages and mentions
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_message
    ))
    
    # Handle unknown commands
    application.add_handler(MessageHandler(filters.COMMAND, unknown_cmd))

async def unknown_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Not sure what that command is. Try /help to see what I can do."
    )