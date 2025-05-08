import os
import logging
import openai
import random
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Set OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

class OpenAIClient:
    """Client for generating responses using OpenAI API"""
    
    def __init__(self):
        self.model = "gpt-4"  # Will be updated to gpt-4.1 when in production
        self.client = openai.OpenAI(api_key=openai.api_key)
        
    # In src/openai_client.py, add better error handling:

    async def generate_response(self, question: str, context: List[Dict[str, Any]] = None, 
                            conversation_context: str = "") -> str:
        """Generate response with better error handling."""
        try:
            # Existing code...
            
            # Make the API call with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        max_tokens=500,
                        temperature=0.5
                    )
                    break  # Success, exit retry loop
                except Exception as e:
                    if attempt < max_retries - 1:
                        # Log the error and retry
                        logger.warning(f"OpenAI API error (attempt {attempt+1}): {e}. Retrying...")
                        await asyncio.sleep(1)  # Wait briefly before retry
                    else:
                        # Last attempt failed, re-raise
                        raise
                        
            # Extract and return the response content
            answer = response.choices[0].message.content
            logger.info(f"Generated response: {answer[:50]}...")
            return answer
                    
        except Exception as e:
            logger.error(f"Error generating OpenAI response: {e}")
            
            # Provide a more helpful fallback response
            if "rate limit" in str(e).lower():
                return "I'm sorry, I'm experiencing high demand right now. Please try again in a moment."
            elif "token" in str(e).lower():
                return "I'm sorry, I'm having trouble processing this complex question. Could you ask it in a simpler way?"
            else:
                # Check if we have any context we can use for a basic response
                if context and len(context) > 0:
                    # Provide a basic answer from the context
                    return f"I'm having some technical difficulties with my AI system, but I found this relevant information: {context[0]['content'][:200]}..."
                else:
                    return "I'm sorry, I encountered an error while generating a response. Please try again with a different question."
