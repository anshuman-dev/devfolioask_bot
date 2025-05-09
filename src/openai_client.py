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
    async def create_plan(self, query_data: Dict[str, Any], user_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Create a reasoning plan for answering a query using OpenAI.
    
    Args:
        query_data: Processed query data
        user_context: User's conversation context
        
    Returns:
        Plan dictionary with steps to execute
    """
    try:
        # Format the context in a readable way
        context_str = "No previous conversation context."
        if user_context and user_context.get("recent_questions"):
            context_str = "Previous conversation:\n"
            recent_questions = user_context.get("recent_questions", [])
            recent_answers = user_context.get("recent_answers", [])
            
            # Get the last 2 turns of conversation
            for i in range(min(2, len(recent_questions))):
                idx = -(i+1)  # Start from the most recent
                context_str += f"User: {recent_questions[idx]}\nBot: {recent_answers[idx]}\n\n"
                
        # Determine the intent type
        intent_type = query_data.get("intent", {}).get("type", "question")
        
        # Create the planning prompt
        planning_prompt = f"""
        You are an AI assistant planning how to answer a query about the Devfolio platform. 
        Create a detailed, step-by-step plan for answering the user's question.
        
        USER QUERY: {query_data.get('cleaned_query', query_data.get('original_query', 'Unknown query'))}
        INTENT TYPE: {intent_type}
        CONVERSATION CONTEXT: {context_str}
        
        Your task is to create a reasoning plan with the following steps:
        
        1. IDENTIFY INFORMATION NEEDED: What specific information is needed to answer this query?
        2. KNOWLEDGE SOURCES: Which knowledge sources should be consulted? Options include:
           - Scenario knowledge base (for specific how-to instructions)
           - General Devfolio knowledge (for platform information)
           - Previous conversation context (for follow-up questions)
        3. REASONING STRATEGY: How should the information be processed and reasoned about?
        4. RESPONSE STRUCTURE: How should the final response be structured?
        
        The output should be a JSON plan with the following structure:
        {{
            "type": "reasoning_plan",
            "information_needed": ["list of specific information pieces needed"],
            "knowledge_sources": ["list of knowledge sources to consult"],
            "reasoning_steps": ["list of logical steps to process the information"],
            "response_structure": "description of how to structure the response",
            "clarifications_needed": ["any clarifications that might be needed from the user"]
        }}
        
        ONLY output the JSON plan, nothing else.
        """
        
        # Make the API call
        messages = [
            {"role": "system", "content": "You are an AI assistant creating reasoning plans for answering queries about the Devfolio platform."},
            {"role": "user", "content": planning_prompt}
        ]
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=800,
            temperature=0.2  # Lower temperature for more deterministic planning
        )
        
        plan_text = response.choices[0].message.content.strip()
        
        # Clean up the response in case it includes markdown or other formatting
        if plan_text.startswith("```json"):
            plan_text = plan_text.replace("```json", "").replace("```", "").strip()
        elif plan_text.startswith("```"):
            plan_text = plan_text.replace("```", "").strip()
            
        # Parse the JSON plan
        try:
            plan = json.loads(plan_text)
            return plan
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing plan JSON: {e}. Plan text: {plan_text}")
            # Fallback to a basic plan
            return {
                "type": "reasoning_plan",
                "information_needed": [query_data.get('cleaned_query', "information about the query")],
                "knowledge_sources": ["scenario_kb", "general_kb"],
                "reasoning_steps": ["retrieve relevant information", "synthesize into coherent response"],
                "response_structure": "Direct answer to the user's question",
                "clarifications_needed": []
            }
            
    except Exception as e:
        logger.error(f"Error creating plan: {e}")
        # Return a minimal default plan
        return {
            "type": "basic_plan",
            "steps": ["retrieve information", "generate response"]
        }

    async def generate_agent_response(self, response_data: Dict[str, Any]) -> str:
        """
        Generate a final response based on execution results and query information.
        
        Args:
            response_data: Dictionary containing query, execution results, and context
            
        Returns:
            Formatted response string
        """
        try:
            query = response_data.get("query", {})
            execution_results = response_data.get("execution_results", {})
            context = response_data.get("context", {})
            
            # Create a prompt for generating the final response
            response_prompt = f"""
            Based on the user's query and the information retrieved, create a helpful response.
            
            USER QUERY: {query.get('cleaned_query', query.get('original_query', 'Unknown query'))}
            
            INTENT: {query.get('intent', {}).get('type', 'question')}
            
            INFORMATION RETRIEVED:
            {json.dumps(execution_results.get('retrieved_information', {}), indent=2)}
            
            EXECUTION STEPS COMPLETED:
            {json.dumps(execution_results.get('steps', []), indent=2)}
            
            REASONING RESULTS:
            {json.dumps(execution_results.get('reasoning_output', {}), indent=2)}
            
            Your response should:
            1. Be helpful, accurate, and directly address the user's query
            2. Include specific details from the retrieved information
            3. Be conversational and friendly in tone
            4. Be concise but thorough
            5. Include specific steps or actions the user should take, if applicable
            6. Mention any caveats or limitations, if relevant
            
            RESPONSE:
            """
            
            # Make the API call
            messages = [
                {"role": "system", "content": "You are an AI assistant providing helpful information about the Devfolio platform."},
                {"role": "user", "content": response_prompt}
            ]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=800,
                temperature=0.7  # Slightly higher temperature for more natural responses
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating agent response: {e}")
            return f"I've analyzed your question about the Devfolio platform, but encountered an error when generating the final response. Please try asking in a different way."


    async def simple_completion(self, prompt: str) -> str:
        """
        Generate a simple text completion using OpenAI.
        
        Args:
            prompt: The prompt to complete
            
        Returns:
            Generated completion text
        """
        try:
            messages = [
                {"role": "user", "content": prompt}
            ]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=800,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error in simple completion: {e}")
            return f"Error generating completion: {str(e)}"

        async def generate_enhanced_response(self, query_data: Dict[str, Any], 
                               scenario_data: Dict[str, Any],
                               user_context: Dict[str, Any],
                               execution_results: Dict[str, Any]) -> str:
    """
    Generate a high-quality response using enhanced prompting.
    
    Args:
        query_data: Processed query information
        scenario_data: Scenario knowledge
        user_context: User context information
        execution_results: Results from plan execution
        
    Returns:
        Generated response text
    """
    try:
        # Extract intent for better tone
        intent = query_data.get("intent", {}).get("type", "question")
        
        # Extract query information
        query = query_data.get("cleaned_query", query_data.get("original_query", "Unknown query"))
        
        # Format scenario information
        scenario_info = ""
        if scenario_data:
            scenario_info = f"# Scenario: {scenario_data.get('title', 'Unknown')} #\n\n"
            
            # Add template if available
            if "answer_template" in scenario_data:
                scenario_info += f"Template: {scenario_data['answer_template']}\n\n"
                
            # Add components if available
            if "answer_components" in scenario_data:
                components = scenario_data["answer_components"]
                
                if "steps" in components and components["steps"]:
                    scenario_info += "Steps:\n" + "\n".join([f"- {step}" for step in components["steps"]]) + "\n\n"
                    
                if "notes" in components and components["notes"]:
                    scenario_info += f"Notes: {components['notes']}\n\n"
                    
                if "common_issues" in components and components["common_issues"]:
                    scenario_info += f"Common issues: {components['common_issues']}\n\n"
        
        # Format user context
        context_info = ""
        if user_context:
            context_info = "# User Context #\n\n"
            
            # Add hackathon state
            if "hackathon_state" in user_context:
                hackathon_state = user_context["hackathon_state"]
                if hackathon_state.get("hackathon_name"):
                    context_info += f"Hackathon name: {hackathon_state['hackathon_name']}\n"
                if hackathon_state.get("current_phase"):
                    context_info += f"Current phase: {hackathon_state['current_phase']}\n"
                if hackathon_state.get("has_enabled_judging"):
                    context_info += "Judging is enabled.\n"
                    
            # Add preferences
            if "preferences" in user_context:
                preferences = user_context["preferences"]
                if preferences.get("judging_mode_preference"):
                    context_info += f"Preferred judging mode: {preferences['judging_mode_preference']}\n"
                
            context_info += "\n"
            
            # Add conversation info
            if "conversation" in user_context:
                conversation = user_context["conversation"]
                if conversation.get("interaction_count"):
                    context_info += f"Interaction count: {conversation['interaction_count']}\n"
                if conversation.get("last_scenario_discussed"):
                    context_info += f"Last topic discussed: {conversation['last_scenario_discussed']}\n"
        
        # Format execution results
        execution_info = ""
        if execution_results:
            execution_info = "# Execution Results #\n\n"
            
            # Add retrieved information
            if "retrieved_information" in execution_results:
                info = execution_results["retrieved_information"]
                if isinstance(info, dict):
                    execution_info += json.dumps(info, indent=2) + "\n\n"
                else:
                    execution_info += str(info) + "\n\n"
                    
            # Add reasoning output
            if "reasoning_output" in execution_results:
                reasoning = execution_results["reasoning_output"]
                if isinstance(reasoning, dict) and "conclusion" in reasoning:
                    execution_info += f"Reasoning conclusion: {reasoning['conclusion']}\n\n"
        
        # Create the system prompt
        system_prompt = f"""
        You are DevfolioAsk, an intelligent assistant that provides helpful, accurate information about the Devfolio hackathon platform.
        
        ## GUIDELINES FOR RESPONDING TO THIS QUERY ##
        
        1. TONE AND STYLE:
           - Be conversational but concise and to the point
           - This is a {intent} request, so your tone should be {self._get_tone_for_intent(intent)}
           - Start with a brief, friendly greeting
           - Focus the body of your response on direct answers with specific steps when relevant
           - End with a brief helpful closing sentence
        
        2. CONTENT REQUIREMENTS:
           - If specific steps are provided, include ALL of them in your response
           - Order steps logically and number them clearly
           - Emphasize important information by placing it early in your response
           - If there are common issues or troubleshooting notes, include them after the main content
           - Keep explanations accurate and factual based on the Devfolio platform
        
        3. FORMATTING:
           - Use clear paragraph breaks between main sections
           - Use numbered lists for steps (1., 2., 3., etc.)
           - Use concise language, avoiding unnecessary words
           - Keep your total response under 350 words unless the query requires detailed explanation
        
        4. PERSONALIZATION:
           - Use the user's context to personalize the response when relevant
           - If the user has mentioned a specific hackathon, refer to it by name
           - Adjust your response based on the hackathon phase (planning, setup, active, judging)
        
        ## SCENARIO INFORMATION ##
        {scenario_info}
        
        ## USER CONTEXT ##
        {context_info}
        
        ## EXECUTION RESULTS ##
        {execution_info}
        """
        
        # Create the user prompt
        user_prompt = f"Question from user: {query}\n\nPlease provide a helpful response following the guidelines."
        
        # Make the API call
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=600,
            temperature=0.7  # Slightly higher for more natural responses
        )
        
        # Extract and return the response content
        answer = response.choices[0].message.content.strip()
        logger.info(f"Generated enhanced response: {answer[:50]}...")
        
        # Validate and improve the response
        return self._validate_response(answer, query_data, scenario_data)
        
    except Exception as e:
        logger.error(f"Error generating enhanced response: {e}")
        return f"I apologize, but I encountered an error while generating a detailed response. Please try asking in a different way."
    
def _get_tone_for_intent(self, intent: str) -> str:
    """Get the appropriate tone for an intent."""
    tone_map = {
        "question": "helpful and informative",
        "problem": "empathetic and solution-focused",
        "followup": "clarifying and direct",
        "greeting": "warm and welcoming",
        "feedback": "appreciative and receptive",
        "clarification": "patient and thorough"
    }
    
    return tone_map.get(intent, "helpful and informative")

def _validate_response(self, response: str, query_data: Dict[str, Any], 
                      scenario_data: Dict[str, Any]) -> str:
    """
    Validate and improve a generated response.
    
    Args:
        response: Generated response to validate
        query_data: Query information
        scenario_data: Scenario data
        
    Returns:
        Validated and potentially improved response
    """
    # Check if the response is empty or too short
    if not response or len(response) < 50:
        return "I apologize, but I couldn't generate a helpful response. Could you please rephrase your question?"
    
    # Check if this is a step-by-step instruction scenario
    if scenario_data and "answer_components" in scenario_data and "steps" in scenario_data["answer_components"]:
        steps = scenario_data["answer_components"]["steps"]
        
        # Check if response contains steps
        contains_steps = any(f"{i+1}." in response for i in range(len(steps)))
        
        # If there are steps but the response doesn't have them formatted properly, add them
        if steps and not contains_steps:
            # Find where to insert steps
            step_insertion_point = response.find("\n\n")
            if step_insertion_point == -1:
                step_insertion_point = len(response) // 2  # Insert in the middle if no clear break
                
            # Format steps
            formatted_steps = "\n\n"
            for i, step in enumerate(steps):
                formatted_steps += f"{i+1}. {step}\n"
            formatted_steps += "\n"
            
            # Insert steps
            response = response[:step_insertion_point] + formatted_steps + response[step_insertion_point:]
    
    # Check if this is a problem-solving intent but the response doesn't address it
    intent = query_data.get("intent", {}).get("type", "")
    if intent == "problem" and "problem" not in response.lower() and "issue" not in response.lower() and "troubleshoot" not in response.lower():
        response = "I understand you're experiencing an issue. " + response
    
    return response