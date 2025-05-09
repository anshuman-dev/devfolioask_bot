import logging
import json
from typing import Dict, List, Any, Tuple, Optional

logger = logging.getLogger(__name__)

#plan executor for various kind scenarios
class PlanExecutor:
    """
    Executes reasoning plans created by the DevfolioAgent.
    Handles different plan types and executes steps in sequence.
    """
    
    def __init__(self, knowledge_base, scenario_kb, openai_client, semantic_matcher):
        """
        Initialize the plan executor with required components.
        
        Args:
            knowledge_base: Knowledge base for retrieving information
            scenario_kb: Scenario-based knowledge base
            openai_client: OpenAI client for generating responses
            semantic_matcher: Semantic matcher for finding relevant scenarios
        """
        self.knowledge_base = knowledge_base
        self.scenario_kb = scenario_kb
        self.openai_client = openai_client
        self.semantic_matcher = semantic_matcher
        
    async def execute_plan(self, plan: Dict[str, Any], 
                     processed_query: Dict[str, Any],
                     conversation_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a plan based on its type.
        
        Args:
            plan: Plan dictionary with execution steps
            processed_query: Processed query data
            conversation_context: Conversation history and context
            
        Returns:
            Dictionary with execution results
        """
        plan_type = plan.get("type", "unknown")
        logger.info(f"Executing plan type: {plan_type}")
        
        # Route to the appropriate executor based on plan type
        if plan_type == "direct_scenario":
            return await self._execute_direct_scenario_plan(plan, processed_query)
            
        elif plan_type == "followup_scenario":
            return await self._execute_followup_scenario_plan(plan, processed_query, conversation_context)
            
        elif plan_type == "hybrid_scenario":
            return await self._execute_hybrid_scenario_plan(plan, processed_query, conversation_context)
            
        elif plan_type == "reasoning_plan":
            return await self._execute_reasoning_plan(plan, processed_query, conversation_context)
            
        else:
            # Fallback for unknown plan types
            logger.warning(f"Unknown plan type: {plan_type}. Using basic execution.")
            return await self._execute_basic_plan(plan, processed_query, conversation_context)
    
    async def _execute_direct_scenario_plan(self, plan: Dict[str, Any], 
                                  processed_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a direct scenario plan where a high-confidence match was found.
        
        Args:
            plan: Direct scenario plan
            processed_query: Processed query data
            
        Returns:
            Execution results
        """
        scenario_id = plan.get("scenario_id")
        scenario = self.scenario_kb.get_scenario_by_id(scenario_id)
        
        if not scenario:
            logger.error(f"Scenario not found for ID: {scenario_id}")
            return {
                "success": False,
                "error": f"Scenario not found: {scenario_id}",
                "steps": [{"type": "error", "message": "Scenario not found"}]
            }
            
        # Extract variables from the query
        variables = self._extract_variables(processed_query, scenario)
        
        # Add hackathon context if available
        if "hackathon_context" in plan and plan["hackathon_context"]:
            hc = plan["hackathon_context"]
            if "name" in hc:
                variables["hackathon_name"] = hc["name"]
        
        # Get related scenarios if specified
        related_scenarios = []
        for related_id in plan.get("related_scenarios", []):
            related = self.scenario_kb.get_scenario_by_id(related_id)
            if related:
                related_scenarios.append(related)
        
        # Render the scenario response
        response = self.scenario_kb.render_scenario_response(
            scenario, 
            variables, 
            question=processed_query.get("cleaned_query")
        )
        
        # Add related scenario information
        if related_scenarios:
            related_info = "\n\nRelated topics you might find helpful:\n"
            for related in related_scenarios:
                related_info += f"- {related['title']}\n"
            response += related_info
            
        # Add phase-specific guidance if available
        if "hackathon_context" in plan and plan["hackathon_context"].get("phase"):
            phase = plan["hackathon_context"]["phase"]
            if phase == "planning":
                response += "\n\nSince you're in the planning phase, you might also want to look at setting up your hackathon page and configuring the basic settings."
            elif phase == "setup":
                response += "\n\nAs you're in the setup phase, remember to also configure your submission requirements and customize your hackathon page."
            elif phase == "active":
                response += "\n\nSince your hackathon is active, consider monitoring submissions and preparing for the judging phase."
            elif phase == "judging":
                response += "\n\nWith judging in progress, ensure all your judges have access and understand how to evaluate projects."
                
        return {
            "success": True,
            "steps": [
                {"type": "retrieve_scenario", "scenario_id": scenario_id},
                {"type": "extract_variables", "variables": variables},
                {"type": "render_response", "scenario_title": scenario.get("title")}
            ],
            "final_response": response,
            "scenario_used": scenario,
            "related_scenarios": related_scenarios
        }
    
    async def _execute_reasoning_plan(self, plan: Dict[str, Any], 
                                processed_query: Dict[str, Any],
                                conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a complex reasoning plan using the OpenAI-generated plan.
        
        Args:
            plan: Reasoning plan with detailed steps
            processed_query: Processed query
            conversation_context: Conversation context
            
        Returns:
            Execution results
        """
        # Initialize tracking of steps and gathered information
        execution_steps = []
        retrieved_information = {}
        
        # Step 1: Gather information from specified knowledge sources
        knowledge_sources = plan.get("knowledge_sources", ["scenario_kb", "general_kb"])
        
        if "scenario_kb" in knowledge_sources:
            # Find relevant scenarios
            query = processed_query.get("cleaned_query", processed_query.get("original_query", ""))
            scenario_matches = self.semantic_matcher.find_matching_scenarios(query, top_k=3)
            
            if scenario_matches:
                retrieved_information["scenarios"] = []
                for scenario, score in scenario_matches:
                    retrieved_information["scenarios"].append({
                        "title": scenario.get("title"),
                        "id": scenario.get("scenario_id"),
                        "confidence": score,
                        "content": self._extract_scenario_content(scenario)
                    })
                    
                execution_steps.append({
                    "type": "retrieve_scenarios",
                    "num_retrieved": len(retrieved_information["scenarios"]),
                    "confidence_scores": [s["confidence"] for s in retrieved_information["scenarios"]]
                })
                
        if "general_kb" in knowledge_sources:
            # Query the general knowledge base
            prefix, kb_results = self.knowledge_base.query(processed_query.get("cleaned_query", ""))
            
            if kb_results:
                retrieved_information["general_knowledge"] = []
                for result in kb_results:
                    retrieved_information["general_knowledge"].append({
                        "source": result.get("source"),
                        "content": result.get("content")[:500]  # Limit to avoid token issues
                    })
                    
                execution_steps.append({
                    "type": "retrieve_general_knowledge",
                    "num_retrieved": len(retrieved_information["general_knowledge"])
                })
                
        # Step 2: Process the reasoning steps
        reasoning_steps = plan.get("reasoning_steps", [])
        reasoning_output = {}
        
        if reasoning_steps:
            # Use OpenAI to process the reasoning steps
            reasoning_prompt = f"""
            Process the following information according to these reasoning steps:
            
            USER QUERY: {processed_query.get('cleaned_query')}
            
            RETRIEVED INFORMATION:
            {json.dumps(retrieved_information, indent=2)}
            
            REASONING STEPS TO FOLLOW:
            {json.dumps(reasoning_steps, indent=2)}
            
            GOAL: 
            {plan.get('response_structure', 'Provide a clear, accurate answer to the user\'s question.')}
            
            Analyze the information and provide:
            1. The key findings from each step
            2. Any logical connections or inferences
            3. A clear conclusion that directly answers the user's query
            
            Format your response as a JSON object with these keys:
            "step_findings": The results of each reasoning step
            "connections": Any logical connections identified
            "conclusion": The direct answer to the user's question
            """
            
            # Make the API call
            try:
                reasoning_response = await self.openai_client.simple_completion(reasoning_prompt)
                
                # Try to parse the JSON response
                try:
                    if reasoning_response.startswith("```json"):
                        reasoning_response = reasoning_response.replace("```json", "").replace("```", "").strip()
                    elif reasoning_response.startswith("```"):
                        reasoning_response = reasoning_response.replace("```", "").strip()
                        
                    reasoning_output = json.loads(reasoning_response)
                except json.JSONDecodeError:
                    # Handle non-JSON response gracefully
                    reasoning_output = {
                        "step_findings": [],
                        "connections": [],
                        "conclusion": reasoning_response
                    }
                    
                execution_steps.append({
                    "type": "process_reasoning_steps",
                    "num_steps": len(reasoning_steps)
                })
                
            except Exception as e:
                logger.error(f"Error in reasoning step processing: {e}")
                reasoning_output = {
                    "error": str(e),
                    "conclusion": "Could not complete reasoning process"
                }
                
                execution_steps.append({
                    "type": "reasoning_error",
                    "error": str(e)
                })
                
        # Step 3: Check if any clarifications are needed
        clarifications_needed = plan.get("clarifications_needed", [])
        if clarifications_needed:
            retrieved_information["clarifications_needed"] = clarifications_needed
            execution_steps.append({
                "type": "identify_clarifications",
                "clarifications": clarifications_needed
            })
            
        # Step 4: Generate the response according to the specified structure
        response_structure = plan.get("response_structure", "Direct answer")
        
        # Compile all gathered information for response generation
        compiled_data = {
            "query": processed_query,
            "retrieved_information": retrieved_information,
            "reasoning_output": reasoning_output,
            "response_structure": response_structure,
            "execution_steps": execution_steps
        }
        
        # Generate the final response
        response = await self.openai_client.generate_agent_response(compiled_data)
        
        return {
            "success": True,
            "steps": execution_steps,
            "retrieved_information": retrieved_information,
            "reasoning_output": reasoning_output,
            "final_response": response
        }
    
    async def _execute_basic_plan(self, plan: Dict[str, Any], 
                           processed_query: Dict[str, Any],
                           conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a basic fallback plan when no specific plan type is available.
        
        Args:
            plan: Basic plan
            processed_query: Processed query
            conversation_context: Conversation context
            
        Returns:
            Execution results
        """
        # Simple retrieval from knowledge base
        _, knowledge_results = self.knowledge_base.query(processed_query.get("cleaned_query", ""))
        
        # Format context from conversation if available
        context_info = ""
        if conversation_context:
            context_info = self._format_conversation_context(conversation_context)
            
        # Generate a simple response
        if knowledge_results:
            response = await self.openai_client.generate_response(
                processed_query.get("cleaned_query", ""),
                knowledge_results,
                context_info
            )
        else:
            # No knowledge found, generate a generic response
            response = f"I don't have specific information about '{processed_query.get('cleaned_query', '')}' in my knowledge base. Could you please provide more details or ask about a different aspect of the Devfolio platform?"
            
        return {
            "success": True,
            "steps": [
                {"type": "basic_knowledge_retrieval", "found": bool(knowledge_results)},
                {"type": "generate_simple_response"}
            ],
            "final_response": response
        }
        
    def _extract_variables(self, processed_query: Dict[str, Any], scenario: Dict[str, Any]) -> Dict[str, str]:
        """Extract variables from the processed query for scenario templates."""
        variables = {}
        
        # Use extracted entities if available
        if "entities" in processed_query and processed_query["entities"]:
            entities = processed_query["entities"]
            
            # Map common entity types to variables
            if "hackathon_name" in entities:
                variables["hackathon_name"] = entities["hackathon_name"]
                
            if "judging_mode" in entities:
                variables["judging_mode"] = entities["judging_mode"]
                
        # Fall back to regex for any missing required variables
        if "required_variables" in scenario:
            for var_name in scenario["required_variables"]:
                if var_name not in variables:
                    # Try to extract using regex patterns
                    if var_name == "hackathon_name" and "hackathon_name" not in variables:
                        import re
                        query = processed_query.get("cleaned_query", "")
                        match = re.search(r'for\s+(?:the\s+)?([A-Za-z0-9\s]+hackathon)', query, re.IGNORECASE)
                        if match:
                            variables["hackathon_name"] = match.group(1)
                        else:
                            variables["hackathon_name"] = "your hackathon"
                            
        return variables
        
    def _format_conversation_context(self, conversation_context: Dict[str, Any]) -> str:
        """Format conversation context for OpenAI prompt."""
        context_info = ""
        
        # Add judging mode preference if available
        if "judging_mode_preference" in conversation_context and conversation_context["judging_mode_preference"]:
            context_info += f"The user has previously shown interest in {conversation_context['judging_mode_preference']} judging. "
        
        # Add recent conversation history for context
        if "recent_questions" in conversation_context and conversation_context["recent_questions"]:
            context_info += "Recent conversation history: "
            num_history = min(3, len(conversation_context["recent_questions"]))
            for i in range(num_history):
                context_info += f"User: {conversation_context['recent_questions'][-(i+1)]} | Bot: {conversation_context['recent_answers'][-(i+1)]} "
                
        return context_info
        
    def _extract_scenario_content(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """Extract the relevant content from a scenario for reasoning."""
        content = {
            "title": scenario.get("title", ""),
            "steps": [],
            "notes": "",
            "common_issues": ""
        }
        
        # Get components if available
        if "answer_components" in scenario:
            components = scenario["answer_components"]
            if "steps" in components:
                content["steps"] = components["steps"]
            if "notes" in components:
                content["notes"] = components["notes"]
            if "common_issues" in components:
                content["common_issues"] = components["common_issues"]
                
        return content