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
            question: The user's question
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
                    content = item['content'].replace("\n", "\n")
                    context_str += f"Source {i} ({item['source']}):\n{content}\n\n"
            
            # Determine if this is a key question type that needs specific handling
            is_judging_criteria = any(term in question.lower() for term in ["judging criteria", "criteria", "update criteria", "modify criteria"])
            is_inviting_judges = any(term in question.lower() for term in ["invite judge", "inviting judge", "add judge", "adding judge"])
            
            # Construct a better prompt based on the question type
            system_prompt = f"""
            You are DevfolioAsk Bot, a helpful assistant for the Devfolio platform. Your primary goal is to provide ACCURATE information from Devfolio documentation.

            IMPORTANT RULES:
            1. ONLY answer using information from the provided context/documentation 
            2. If the context doesn't contain specific information about a topic, admit it clearly instead of making up an answer
            3. Keep your answers factually accurate based on the documentation
            4. Format your responses in a clear, readable way
            5. Start with a brief friendly greeting and end with a brief helpful closing, but keep the main content factual and accurate

            RESPONSE STRUCTURE:
            - Brief friendly greeting (1 line)
            - Direct answer to the question based ONLY on provided documentation
            - If providing steps, number them clearly
            - Brief helpful closing (1 line)

            {conversation_context if conversation_context else ""}
            """
            
            # Add special instructions for specific question types
            if is_judging_criteria:
                system_prompt += """
                SPECIAL INSTRUCTIONS FOR JUDGING CRITERIA QUESTIONS:
                - Be sure to mention that Devfolio has 5 fixed judging criteria that CANNOT be modified within the platform
                - List all 5 criteria: Technicality, Originality, Practicality, Aesthetics, and Wow Factor
                - Clearly state that custom criteria require contacting @singhanshuman8 and @AniketRaj314 on Telegram
                """
            elif is_inviting_judges:
                system_prompt += """
                SPECIAL INSTRUCTIONS FOR INVITING JUDGES QUESTIONS:
                - Provide the exact step-by-step process for inviting judges on Devfolio
                - Mention that judges need to be added through the 'Speakers and Judges' tab
                - Explain that judges must create a Devfolio account using the same email they were invited with
                """
            
            # Create the messages for the API call
            messages = [
                {"role": "system", "content": system_prompt},
            ]
            
            # Add context if available
            if context_str:
                messages.append({"role": "user", "content": "Documentation information to use when answering questions:\n\n" + context_str})
                messages.append({"role": "assistant", "content": "I'll use this documentation to provide accurate information about Devfolio."})
            
            # Format the question
            user_prompt = f"Question from user: {question}\n\nProvide an accurate, helpful response based ONLY on the documentation provided."
            
            messages.append({"role": "user", "content": user_prompt})
            
            logger.info("Making API call to OpenAI")
            
            # Make the API call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=500,
                temperature=0.5  # Lower temperature for more accurate responses
            )
            
            # Extract and return the response content
            answer = response.choices[0].message.content
            logger.info(f"Generated response: {answer[:50]}...")
            return answer
                
        except Exception as e:
            logger.error(f"Error generating OpenAI response: {e}")
            return f"I'm sorry, I encountered an error while generating a response. Please try again later."
