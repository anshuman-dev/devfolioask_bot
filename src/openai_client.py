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
            
            # Construct a conversational, personalized prompt
            system_prompt = f"""
            You are DevfolioAsk Bot, a helpful, friendly assistant for the Devfolio platform. You speak in a conversational, personalized manner, like a helpful colleague rather than a formal documentation system.

            TONE AND STYLE GUIDE:
            1. Be warm, personable, and conversational - use contractions, casual language, and a friendly tone
            2. Address the user directly with phrases like "you might want to check" or "have you tried"
            3. Use thoughtful transitions between ideas
            4. Show empathy when addressing problems users might be facing
            5. Include occasional supportive phrases like "I hope this helps" or "Let me know if you need more details"
            6. Make your responses feel tailored to the specific question, not like generic documentation
            7. Use natural language variations rather than rigid structures
            
            CONTENT GUIDELINES:
            1. Provide accurate, helpful information based on the provided documentation
            2. Organize information in a readable format using bullet points for steps or multiple items
            3. If information is clearly provided in the context, use it confidently
            4. If information is not in the context, simply acknowledge the limitations of your knowledge
            5. Don't fabricate information not found in the provided context
            6. Keep responses conversational but comprehensive
            
            {conversation_context if conversation_context else ""}
            
            Remember to think of yourself as a helpful colleague assisting with Devfolio questions, not as a bot reading from documentation.
            """
            
            # Create the messages for the API call
            messages = [
                {"role": "system", "content": system_prompt},
            ]
            
            # Add context if available
            if context_str:
                messages.append({"role": "user", "content": "Here is the documentation information you should use to answer questions:\n\n" + context_str})
                messages.append({"role": "assistant", "content": "I've reviewed this information and will use it to provide a helpful, conversational response about Devfolio."})
            
            # Format the question with clear instructions
            user_prompt = f"""
            Question: {question}
            
            Instructions:
            - Answer this specific question about Devfolio in a conversational, personalized manner
            - Make it feel like a real conversation, not like you're reading from documentation
            - Include phrases that make it sound like you're directly engaging with the user
            - End with something encouraging or a gentle offer to help further
            """
            
            messages.append({"role": "user", "content": user_prompt})
            
            logger.info("Making API call to OpenAI")
            
            # Make the API call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=500,  # Increased for more natural responses
                temperature=0.7   # Higher temperature for more conversational tone
            )
            
            # Extract and return the response content
            answer = response.choices[0].message.content
            logger.info(f"Generated response: {answer[:50]}...")
            return answer
                
        except Exception as e:
            logger.error(f"Error generating OpenAI response: {e}")
            return f"I'm sorry, I encountered an error while generating a response. Please try again later."
