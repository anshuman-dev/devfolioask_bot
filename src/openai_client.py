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
        
    async def generate_response(self, question: str, context: List[Dict[str, Any]] = None, conversation_context: str = "") -> str:
        """
        Generate a response using OpenAI's API based on the question and knowledge context
        
        Args:
            question: User's question
            context: Relevant context from the knowledge base
            conversation_context: Previous conversation context
            
        Returns:
            Generated response
        """
        try:
            logger.info(f"Generating AI response for: {question[:50]}...")
            
            # Prepare context string from knowledge base results
            context_str = ""
            if context:
                # Log what we're using
                logger.info(f"Using {len(context)} context items to generate response")
                for i, item in enumerate(context):
                    logger.info(f"Context {i+1}: {item['source']} (relevance: {item['relevance']})")
                
                # Create context string
                context_str = "Here is relevant information from Devfolio documentation:\n\n"
                for i, item in enumerate(context, 1):
                    content = item['content']
                    # Clean up content for better readability
                    content = content.replace("\n", "\n")
                    context_str += f"Source {i} ({item['source']}):\n{content}\n\n"
            
            # Construct a more directive prompt with conversation context included
            system_prompt = f"""
            You are DevfolioAsk Bot, a helpful assistant for the Devfolio platform. Your task is to answer questions about Devfolio based on the provided documentation.
            
            INSTRUCTIONS:
            1. Answer ONLY what is asked in the question.
            2. Provide CONCISE, DIRECT answers.
            3. Use bullet points for steps or multiple items.
            4. If information is clearly provided in the context, use it confidently.
            5. If information is not in the context, simply say "The documentation doesn't specify information about [topic]."
            6. Don't fabricate information not found in the provided context.
            7. Keep responses under 200 words.
            
            {conversation_context if conversation_context else ""}
            
            Remember: You are an expert on Devfolio documentation, not a general assistant.
            """
            
            # Create the messages for the API call with clear instructions
            messages = [
                {"role": "system", "content": system_prompt},
            ]
            
            # Add context if available
            if context_str:
                messages.append({"role": "user", "content": "Here is the documentation information you should use to answer questions:\n\n" + context_str})
                messages.append({"role": "assistant", "content": "I've reviewed this documentation and will use it to provide accurate answers about Devfolio."})
            
            # Format the question with clear instructions
            user_prompt = f"""
            Question: {question}
            
            Instructions:
            - Answer this specific question directly based on the Devfolio documentation
            - Be concise and to the point
            - Don't provide general information not related to the question
            - Use bullet points where appropriate
            """
            
            messages.append({"role": "user", "content": user_prompt})
            
            logger.info("Making API call to OpenAI")
            
            # Make the API call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=350,  # Cap token length for conciseness
                temperature=0.3   # Lower temperature for more focused responses
            )
            
            # Extract and return the response content
            answer = response.choices[0].message.content
            logger.info(f"Generated response: {answer[:50]}...")
            return answer
                
        except Exception as e:
            logger.error(f"Error generating OpenAI response: {e}")
            return f"I'm sorry, I encountered an error while generating a response. Please try again later."
