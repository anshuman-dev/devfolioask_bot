import os
import logging
from telegram import Update, BotCommand
from telegram.ext import CommandHandler, ContextTypes, filters, MessageHandler
from kb_manager import get_knowledge, save_query_log, get_stats
from gitbook_scraper import refresh_knowledge_base

logger = logging.getLogger(__name__)

ADMIN_IDS = [int(id) for id in os.environ.get("ADMIN_IDS", "").split(",") if id]

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Hey {user.first_name}! I'm your judging helper bot. I can answer questions about setting up judging, rooms, and inviting judges.\n\n"
        "Use these commands:\n"
        "/help - Show all commands\n"
        "/search your question - Search for answers\n"
        "/judging your question - For judging questions\n"
        "/setup your question - For setup questions\n"
        "/invite your question - For judge invitation questions"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "How to use this bot:\n\n"
        "/start - Get a welcome message\n"
        "/help - See this help message\n"
        "/search question - Search all topics\n"
        "/judging question - Find judging info\n"
        "/setup question - Get platform setup help\n"
        "/invite question - Learn about inviting judges\n"
        "/contact - Get human support contacts\n\n"
        "Examples:\n"
        "/search how to create a judging room\n"
        "/judging scoring criteria"
    )

async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    user = update.effective_user
    
    if not query:
        await update.message.reply_text("You need to add a search term. Try something like: /search how to add judges")
        return
    
    save_query_log(user.id, user.username or "unknown", "search", query)
    
    results = get_knowledge(query)
    if not results:
        await update.message.reply_text(
            "Hmm, I couldn't find anything about that. Try different keywords or use /contact to reach a human."
        )
        return
    
    response = f"Found some info about '{query}':\n\n"
    
    for i, result in enumerate(results, 1):
        response += f"{i}. *{result['title']}*\n{result['content']}\n"
        if result['url']:
            response += f"More: {result['url']}\n"
        response += "\n"
    
    # Reply to the message that triggered this command
    await update.message.reply_text(response, parse_mode="Markdown")

async def category_search(update: Update, context: ContextTypes.DEFAULT_TYPE, category):
    query = " ".join(context.args)
    user = update.effective_user
    
    if not query:
        await update.message.reply_text(f"Please add a search term. Example: /{category} adding judges")
        return
    
    save_query_log(user.id, user.username or "unknown", category, query)
    
    results = get_knowledge(query, category)
    if not results:
        await update.message.reply_text(
            f"Couldn't find {category} info about that. Try a general /search instead."
        )
        return
    
    response = f"Here's what I know about '{query}' in {category}:\n\n"
    
    for i, result in enumerate(results, 1):
        response += f"{i}. *{result['title']}*\n{result['content']}\n"
        if result['url']:
            response += f"More: {result['url']}\n"
        response += "\n"
    
    # Reply to the message that triggered this command
    await update.message.reply_text(response, parse_mode="Markdown")

async def judging_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await category_search(update, context, "judging")

async def setup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await category_search(update, context, "setup")

async def invite_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await category_search(update, context, "invite")

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
    
    await update.message.reply_text("Starting knowledge base refresh, this might take a minute...")
    
    try:
        kb_info = refresh_knowledge_base()
        await update.message.reply_text(
            f"✅ Knowledge base updated successfully!\n"
            f"Found {kb_info['topic_count']} topics\n"
            f"Last updated: {kb_info['timestamp']}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error updating knowledge base: {str(e)}")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("Sorry, only admins can do that.")
        return
    
    stats = get_stats()
    
    await update.message.reply_text(stats)

async def handle_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle when the bot is mentioned with a question"""
    message = update.message
    
    # Get bot's username
    bot_username = context.bot.username
    
    # Check if this is really a mention message
    if not message.text or f"@{bot_username}" not in message.text:
        return
        
    # Extract the query (everything after the mention)
    query = message.text.split(f"@{bot_username}", 1)[1].strip()
    
    if not query:
        await message.reply_text("How can I help you? Try asking me a specific question.")
        return
        
    # Log the query
    user = update.effective_user
    save_query_log(user.id, user.username or "unknown", "mention", query)
    
    # Search for information
    results = get_knowledge(query)
    if not results:
        await message.reply_text(
            "I don't have information about that yet. Try a different question or use /search command."
        )
        return
    
    response = f"Here's what I found about your question:\n\n"
    
    for i, result in enumerate(results, 1):
        response += f"{i}. *{result['title']}*\n{result['content']}\n"
        if result['url']:
            response += f"More: {result['url']}\n"
        response += "\n"
    
    await message.reply_text(response, parse_mode="Markdown")

async def set_commands(application):
    """Set up the bot commands in the Telegram UI"""
    commands = [
        BotCommand("start", "Get started with the bot"),
        BotCommand("help", "See available commands"),
        BotCommand("search", "Search for any information"),
        BotCommand("judging", "Find judging-related information"),
        BotCommand("setup", "Get help with platform setup"),
        BotCommand("invite", "Learn about inviting judges"),
        BotCommand("contact", "Get human support contact info")
    ]
    
    await application.bot.set_my_commands(commands)

def setup_handlers(application):
    # Set up commands in Telegram UI
    application.post_init = set_commands
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("search", search_cmd))
    application.add_handler(CommandHandler("judging", judging_cmd))
    application.add_handler(CommandHandler("setup", setup_cmd))
    application.add_handler(CommandHandler("invite", invite_cmd))
    application.add_handler(CommandHandler("contact", contact_cmd))
    
    # Admin commands
    application.add_handler(CommandHandler("refresh", refresh_cmd))
    application.add_handler(CommandHandler("stats", stats_cmd))
    
    # Handle mentions like @bot_name how to add judges?
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Entity("mention"), 
        handle_mention
    ))
    
    # Handle unknown commands
    application.add_handler(MessageHandler(filters.COMMAND, unknown_cmd))

async def unknown_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Not sure what that command is. Try /help to see what I can do."
    )