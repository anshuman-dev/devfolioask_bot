import asyncio
import logging
from telegram.constants import ChatAction

logger = logging.getLogger(__name__)

class TypingHandler:
    """Helper class to manage typing indicators"""
    
    @staticmethod
    async def send_typing_action(bot, chat_id, duration=5):
        """
        Send typing action for a specified duration, repeatedly to ensure it stays visible
        
        Args:
            bot: The Telegram bot instance
            chat_id: The chat ID to send the typing indicator to
            duration: How long to show the typing indicator (in seconds)
        """
        try:
            # Calculate how many times to send typing (every 4 seconds)
            iterations = max(1, int(duration / 4))
            
            # Send typing action multiple times to ensure visibility
            for _ in range(iterations):
                await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
                await asyncio.sleep(min(4, duration))  # Sleep at most 4 seconds between updates
                
        except Exception as e:
            logger.error(f"Error sending typing action: {e}")
