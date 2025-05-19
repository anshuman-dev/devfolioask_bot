import os
import json
import logging
import time
import requests
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class EnhancedOpenAIEvalSystem:
    """
    Enhanced version of OpenAI Evals API integration that supports:
    1. Getting evaluation results directly from the API
    2. Extracting and storing feedback from evaluations
    3. Updating the knowledge base with improved responses
    """
    
    def __init__(self, api_key: str = None, feedback_system=None, knowledge_base=None):
        """
        Initialize the Enhanced OpenAI Eval System.
        
        Args:
            api_key: OpenAI API key (defaults to environment variable)
            feedback_system: Optional FeedbackSystem instance for integration
            knowledge_base: Optional KnowledgeBase instance for improvements
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OpenAI API key not found. Eval system will not function.")
            
        self.base_url = "https://api.openai.com/v1/evals"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Integration with other systems
        self.feedback_system = feedback_system
        self.knowledge_base = knowledge_base
        
        # Cache for eval IDs
        self.eval_cache = {}
        
        # Store evaluations for review and improvement
        self.evaluations_dir = "knowledgebase/evaluations"
        os.makedirs(self.evaluations_dir, exist_ok=True)
        
        logger.info("Enhanced OpenAI Eval System initialized")
        
    def create_eval(self, name: str, testing_criteria: List[Dict[str, Any]]) -> Optional[str]:
        """
        Create an evaluation using OpenAI's Evals API.
        
        Args:
            name: Name for the evaluation
            testing_criteria: List of testing criteria for the evaluation
            
        Returns:
            Eval ID if successful, None otherwise
        """
        try:
            data = {
                "name": name,
                "data_source_config": {
                    "type": "custom",
                    "item_schema": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"},
                            "correct_answer": {"type": "string"}
                        },
                        "required": ["question", "correct_answer"]
                    },
                    "include_sample_schema": True
                },
                "testing_criteria": testing_criteria
            }
            
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=data
            )
            
            if response.status_code == 200:
                eval_id = response.json().get("id")
                logger.info(f"Created evaluation: {name} with ID: {eval_id}")
                # Cache the eval ID
                self.eval_cache[name] = eval_id
                return eval_id
            else:
                logger.error(f"Failed to create evaluation: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating evaluation: {e}")
            return None
    
    def get_or_create_editable_eval(self) -> str:
        """
        Get or create an evaluation with detailed feedback capabilities.
        
        Returns:
            Eval ID of the editable evaluation
        """
        editable_eval_name = "DevfolioBot_Editable_Evaluation"
        
        # Check cache first
        if editable_eval_name in self.eval_cache:
            return self.eval_cache[editable_eval_name]
            
        # Create a new evaluation with detailed feedback
        editable_criteria = [{
            "type": "label_model",
            "name": "Detailed Response Feedback",
            "model": "gpt-4",
            "input": [
                {
                    "role": "developer",
                    "content": """
                    Evaluate this Devfolio bot response and provide detailed improvement suggestions.
                    
                    When evaluating, consider:
                    1. Accuracy - Is the information correct?
                    2. Completeness - Does it address all aspects of the question?
                    3. Clarity - Is it easy to understand?
                    4. Conciseness - Is it appropriately brief without omitting important details?
                    5. Helpfulness - Would it help the user resolve their issue?
                    
                    Provide your evaluation in this JSON format:
                    {
                        "overall_rating": [1-5 score],
                        "strengths": ["list", "of", "strengths"],
                        "weaknesses": ["list", "of", "weaknesses"],
                        "suggested_improvement": "Specific rewriting of the response",
                        "explanation": "Why this improvement is better"
                    }
                    """
                },
                {
                    "role": "user",
                    "content": "Question: {{ item.question }}\nResponse: {{ sample.output_text }}"
                }
            ],
            "passing_labels": ["good_response"],
            "labels": ["good_response", "needs_improvement"]
        }]
        
        eval_id = self.create_eval(editable_eval_name, editable_criteria)
        if eval_id:
            self.eval_cache[editable_eval_name] = eval_id
        
        return eval_id
        
    def evaluate_with_feedback(self, question: str, answer: str) -> Dict[str, Any]:
        """
        Evaluate a response with detailed feedback rather than just binary classification.
        
        Args:
            question: User's question
            answer: Bot's response
            
        Returns:
            Evaluation result with detailed feedback
        """
        try:
            # Get or create the editable evaluation
            eval_id = self.get_or_create_editable_eval()
            if not eval_id:
                return {"status": "error", "error": "Failed to create editable evaluation"}
            
            # Format data for the evaluation
            eval_data = [{
                "item": {
                    "question": question,
                    "correct_answer": ""  # We don't have ground truth
                }
            }]
            
            # Create a unique run name with timestamp
            run_name = f"feedback_eval_{int(time.time())}"
            
            # Create the eval run
            run_data = {
                "name": run_name,
                "data_source": {
                    "type": "completions",
                    "model": "gpt-4",
                    "input": [
                        {
                            "role": "developer",
                            "content": "You are an AI assistant that helps users with questions about the Devfolio platform. Answer the following question concisely and accurately."
                        },
                        {
                            "role": "user",
                            "content": "{{ item.question }}"
                        }
                    ],
                    "output": [
                        {
                            "role": "assistant",
                            "content": answer
                        }
                    ],
                    "source": {
                        "type": "file_content",
                        "content": eval_data
                    }
                }
            }
            
            # Make API call
            response = requests.post(
                f"{self.base_url}/{eval_id}/runs",
                headers=self.headers,
                json=run_data
            )
            
            if response.status_code == 200:
                run_id = response.json().get("id")
                logger.info(f"Created feedback eval run with ID: {run_id}")
                
                # Store for future reference and integration
                self._store_evaluation_for_review(question, answer, eval_id, run_id)
                
                # Return run ID for retrieving results later
                return {
                    "status": "success", 
                    "run_id": run_id,
                    "eval_id": eval_id,
                    "message": "Evaluation with feedback initiated"
                }
            else:
                logger.error(f"Failed to create feedback eval run: {response.status_code} - {response.text}")
                return {"status": "error", "error": response.text}
                
        except Exception as e:
            logger.error(f"Error evaluating with feedback: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_feedback_results(self, eval_id: str, run_id: str) -> Dict[str, Any]:
        """
        Get detailed feedback results from a completed evaluation run.
        
        Args:
            eval_id: ID of the evaluation
            run_id: ID of the run
            
        Returns:
            Detailed feedback results
        """
        try:
            # First, check if run is completed
            status_response = self._get_run_status(eval_id, run_id)
            if status_response.get("status") != "completed":
                logger.info(f"Run {run_id} not yet completed, status: {status_response.get('status')}")
                return {"status": "pending", "message": "Run not yet completed"}
            
            # Get output items
            response = requests.get(
                f"{self.base_url}/{eval_id}/runs/{run_id}/output_items",
                headers=self.headers
            )
            
            if response.status_code == 200:
                output_items = response.json().get("data", [])
                
                if not output_items:
                    return {"status": "error", "error": "No output items found"}
                    
                # Extract detailed feedback
                feedback_results = []
                for item in output_items:
                    results = item.get("results", [])
                    for result in results:
                        if result.get("type") == "label_model":
                            # Try to parse any JSON in the output
                            output = result.get("output", "")
                            try:
                                # Extract JSON from text output
                                import re
                                json_matches = re.findall(r'{.*}', output, re.DOTALL)
                                if json_matches:
                                    feedback_json = json.loads(json_matches[0])
                                    feedback_results.append(feedback_json)
                                else:
                                    # No JSON found, store raw text
                                    feedback_results.append({"raw_feedback": output})
                            except json.JSONDecodeError:
                                # Fallback to raw text
                                feedback_results.append({"raw_feedback": output})
                
                # Store the feedback in a format that can be reviewed
                question = output_items[0].get("datasource_item", {}).get("question", "")
                response_text = output_items[0].get("sample", {}).get("output", [{}])[0].get("content", "")
                
                # If integration is enabled, update knowledge base and feedback system
                self._integrate_feedback_with_systems(question, response_text, feedback_results)
                
                return {
                    "status": "completed",
                    "feedback": feedback_results,
                    "question": question,
                    "response": response_text
                }
            else:
                logger.error(f"Failed to get run output items: {response.status_code} - {response.text}")
                return {"status": "error", "error": response.text}
                
        except Exception as e:
            logger.error(f"Error getting feedback results: {e}")
            return {"status": "error", "error": str(e)}
    
    def _get_run_status(self, eval_id: str, run_id: str) -> Dict[str, Any]:
        """Get the status of an eval run."""
        try:
            response = requests.get(
                f"{self.base_url}/{eval_id}/runs/{run_id}",
                headers=self.headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get run status: {response.status_code} - {response.text}")
                return {"status": "error", "error": response.text}
                
        except Exception as e:
            logger.error(f"Error getting run status: {e}")
            return {"status": "error", "error": str(e)}
    
    def _store_evaluation_for_review(self, question: str, answer: str, 
                                  eval_id: str, run_id: str) -> None:
        """
        Store evaluation data for future review and integration.
        
        Args:
            question: Original question
            answer: Bot's response
            eval_id: Evaluation ID
            run_id: Run ID
        """
        try:
            # Create a unique filename
            timestamp = int(time.time())
            filename = f"eval_{timestamp}.json"
            filepath = os.path.join(self.evaluations_dir, filename)
            
            # Store evaluation data
            eval_data = {
                "question": question,
                "answer": answer,
                "eval_id": eval_id,
                "run_id": run_id,
                "timestamp": timestamp,
                "status": "pending",  # Will be updated when results are retrieved
                "feedback": None  # Will be updated when results are retrieved
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(eval_data, f, indent=2)
                
            logger.info(f"Stored evaluation for review: {filepath}")
            
        except Exception as e:
            logger.error(f"Error storing evaluation for review: {e}")
    
    def _integrate_feedback_with_systems(self, question: str, response: str, 
                                     feedback_results: List[Dict[str, Any]]) -> None:
        """
        Integrate feedback with knowledge base and feedback system if available.
        
        Args:
            question: Original question
            response: Bot's response
            feedback_results: List of feedback results
        """
        if not feedback_results:
            return
            
        try:
            # Check if first feedback result has suggested improvement
            first_feedback = feedback_results[0]
            
            if "suggested_improvement" in first_feedback and first_feedback["suggested_improvement"]:
                improved_response = first_feedback["suggested_improvement"]
                explanation = first_feedback.get("explanation", "")
                
                # Update knowledge base if available
                if self.knowledge_base:
                    logger.info(f"Updating knowledge base with improved response")
                    # Implementation depends on your knowledge base structure
                    # This is a placeholder for the actual implementation
                    self.knowledge_base.update_with_improved_response(
                        question,
                        improved_response,
                        explanation
                    )
                    
                # Update feedback system if available
                if self.feedback_system:
                    logger.info(f"Storing feedback in feedback system")
                    # Implementation depends on your feedback system structure
                    self.feedback_system.save_structured_feedback(
                        question,
                        response,
                        "AI Evaluation",
                        explanation,
                        "system"
                    )
        except Exception as e:
            logger.error(f"Error integrating feedback with systems: {e}")
            
    def process_pending_evaluations(self) -> Dict[str, Any]:
        """
        Process all pending evaluations to retrieve feedback and update systems.
        
        Returns:
            Dictionary with statistics about processed evaluations
        """
        try:
            # Get all evaluation files
            evaluations = []
            for filename in os.listdir(self.evaluations_dir):
                if filename.endswith(".json"):
                    with open(os.path.join(self.evaluations_dir, filename), 'r', encoding='utf-8') as f:
                        eval_data = json.load(f)
                        evaluations.append((filename, eval_data))
            
            # Process pending evaluations
            processed = 0
            stats = {
                "total": len(evaluations),
                "processed": 0,
                "pending": 0,
                "failed": 0,
                "improved_responses": 0
            }
            
            for filename, eval_data in evaluations:
                if eval_data.get("status") == "pending":
                    # Get results
                    eval_id = eval_data.get("eval_id")
                    run_id = eval_data.get("run_id")
                    
                    if not eval_id or not run_id:
                        continue
                        
                    results = self.get_feedback_results(eval_id, run_id)
                    
                    if results.get("status") == "completed":
                        # Update evaluation data
                        eval_data["status"] = "completed"
                        eval_data["feedback"] = results.get("feedback")
                        
                        # Check if there's an improved response
                        if results.get("feedback") and len(results["feedback"]) > 0:
                            first_feedback = results["feedback"][0]
                            if "suggested_improvement" in first_feedback:
                                eval_data["improved_response"] = first_feedback["suggested_improvement"]
                                stats["improved_responses"] += 1
                        
                        # Save updated evaluation data
                        with open(os.path.join(self.evaluations_dir, filename), 'w', encoding='utf-8') as f:
                            json.dump(eval_data, f, indent=2)
                            
                        processed += 1
                        stats["processed"] += 1
                    elif results.get("status") == "pending":
                        stats["pending"] += 1
                    else:
                        stats["failed"] += 1
            
            return {
                "status": "success",
                "stats": stats,
                "message": f"Processed {processed} pending evaluations"
            }
                
        except Exception as e:
            logger.error(f"Error processing pending evaluations: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_improvements(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get a list of response improvements from completed evaluations.
        
        Args:
            limit: Maximum number of improvements to return
            
        Returns:
            List of improvement dictionaries
        """
        try:
            improvements = []
            
            # Get all evaluation files
            for filename in os.listdir(self.evaluations_dir):
                if filename.endswith(".json"):
                    with open(os.path.join(self.evaluations_dir, filename), 'r', encoding='utf-8') as f:
                        eval_data = json.load(f)
                        
                        # Check if it has an improved response
                        if eval_data.get("status") == "completed" and "improved_response" in eval_data:
                            improvements.append({
                                "question": eval_data.get("question"),
                                "original_response": eval_data.get("answer"),
                                "improved_response": eval_data.get("improved_response"),
                                "feedback": eval_data.get("feedback"),
                                "timestamp": eval_data.get("timestamp")
                            })
            
            # Sort by timestamp (newest first)
            improvements.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            
            return improvements[:limit]
            
        except Exception as e:
            logger.error(f"Error getting improvements: {e}")
            return []