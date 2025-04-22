import os
import logging
import openai
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
        
    async def generate_response(self, question: str, context: List[Dict[str, Any]] = None) -> str:
        """
        Generate a response using OpenAI's API based on the question and knowledge context
        
        Args:
            question: User's question
            context: Relevant context from the knowledge base
            
        Returns:
            Generated response
        """
        try:
            logger.info(f"Generating AI response for: {question[:50]}...")
            
            # Prepare context string from knowledge base results
            context_str = ""
            if context:
                context_str = "Here is relevant information from Devfolio documentation:\n\n"
                for i, item in enumerate(context, 1):
                    context_str += f"Source {i}: {item['source']}\n{item['content']}\n\n"
            
            # Construct the prompt
            system_prompt = """
            You are DevfolioAsk Bot, a helpful assistant for the Devfolio platform. 
            You provide clear, concise answers about Devfolio features, workflows, and best practices.
            Format your responses in an easy-to-read way, using bullet points for steps or lists.
            If you don't know the answer, admit it clearly rather than making something up.
            Base your answers on the provided context information.
            """
            
            # Create the messages for the API call
            messages = [
                {"role": "system", "content": system_prompt},
            ]
            
            # Add context if available
            if context_str:
                messages.append({"role": "system", "content": context_str})
                
            # Add the user's question
            messages.append({"role": "user", "content": question})
            
            logger.info("Making API call to OpenAI")
            
            # Make the actual API call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )
            
            # Extract and return the response content
            answer = response.choices[0].message.content
            logger.info(f"Generated response: {answer[:50]}...")
            return answer
                
        except Exception as e:
            logger.error(f"Error generating OpenAI response: {e}")
            return f"I'm sorry, I encountered an error while generating a response: {str(e)}. Please try again later."
