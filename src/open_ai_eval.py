import os
import json
import logging
import time
import requests
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class OpenAIEvalSystem:
    """
    Integrates with OpenAI's Evals API to evaluate bot responses
    and provide insights for improvement.
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize the OpenAI Eval System.
        
        Args:
            api_key: OpenAI API key (defaults to environment variable)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OpenAI API key not found. Eval system will not function.")
            
        self.base_url = "https://api.openai.com/v1/evals"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Cache for eval IDs
        self.eval_cache = {}
        
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
    
    def get_or_create_common_evals(self) -> Dict[str, str]:
        """
        Get or create common evaluations used for bot responses.
        
        Returns:
            Dictionary of eval_name: eval_id
        """
        evals = {}
        
        # 1. Accuracy Evaluation
        accuracy_criteria = [{
            "type": "string_check",
            "name": "Response accuracy check",
            "input": "{{ sample.output_text }}",
            "operation": "contains",
            "reference": "{{ item.correct_answer }}"
        }]
        
        accuracy_eval_id = self.eval_cache.get("accuracy_eval") or self.create_eval(
            "DevfolioBot Accuracy Evaluation", 
            accuracy_criteria
        )
        
        if accuracy_eval_id:
            evals["accuracy_eval"] = accuracy_eval_id
        
        # 2. Helpfulness Evaluation
        helpfulness_criteria = [{
            "type": "label_model",
            "name": "Response helpfulness evaluation",
            "model": "gpt-4",
            "input": [
                {
                    "role": "developer",
                    "content": """Evaluate how helpful this response is to the user's question.
                    A helpful response:
                    - Directly addresses the user's question
                    - Provides specific, actionable information
                    - Is clear and easy to understand
                    - Includes relevant context and examples
                    
                    Rate the response as either 'helpful' or 'not_helpful'.
                    """
                },
                {
                    "role": "user",
                    "content": "Question: {{ item.question }}\nResponse: {{ sample.output_text }}"
                }
            ],
            "passing_labels": ["helpful"],
            "labels": ["helpful", "not_helpful"]
        }]
        
        helpfulness_eval_id = self.eval_cache.get("helpfulness_eval") or self.create_eval(
            "DevfolioBot Helpfulness Evaluation", 
            helpfulness_criteria
        )
        
        if helpfulness_eval_id:
            evals["helpfulness_eval"] = helpfulness_eval_id
            
        # 3. Clarity Evaluation
        clarity_criteria = [{
            "type": "label_model",
            "name": "Response clarity evaluation",
            "model": "gpt-4",
            "input": [
                {
                    "role": "developer",
                    "content": """Evaluate how clear and well-structured this response is.
                    A clear response:
                    - Has a logical structure (greeting, answer, conclusion)
                    - Uses simple, concise language
                    - Avoids jargon without explanation
                    - Has well-organized steps or points (if applicable)
                    
                    Rate the response as either 'clear' or 'unclear'.
                    """
                },
                {
                    "role": "user",
                    "content": "Response: {{ sample.output_text }}"
                }
            ],
            "passing_labels": ["clear"],
            "labels": ["clear", "unclear"]
        }]
        
        clarity_eval_id = self.eval_cache.get("clarity_eval") or self.create_eval(
            "DevfolioBot Clarity Evaluation", 
            clarity_criteria
        )
        
        if clarity_eval_id:
            evals["clarity_eval"] = clarity_eval_id
            
        return evals
    
    def create_eval_run(self, eval_id: str, model: str, data: List[Dict[str, Any]]) -> Optional[str]:
        """
        Create an eval run to evaluate responses using the specified evaluation.
        
        Args:
            eval_id: ID of the evaluation to use
            model: Model used to generate responses
            data: Test data containing questions and correct answers
            
        Returns:
            Run ID if successful, None otherwise
        """
        try:
            run_data = {
                "name": f"Run_{int(time.time())}",
                "data_source": {
                    "type": "completions",
                    "model": model,
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
                    "source": {
                        "type": "file_content",
                        "content": data
                    }
                }
            }
            
            response = requests.post(
                f"{self.base_url}/{eval_id}/runs",
                headers=self.headers,
                json=run_data
            )
            
            if response.status_code == 200:
                run_id = response.json().get("id")
                logger.info(f"Created eval run with ID: {run_id}")
                return run_id
            else:
                logger.error(f"Failed to create eval run: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating eval run: {e}")
            return None
    
    def get_run_status(self, eval_id: str, run_id: str) -> Dict[str, Any]:
        """
        Get the status of an eval run.
        
        Args:
            eval_id: ID of the evaluation
            run_id: ID of the run
            
        Returns:
            Run status information
        """
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
    
    def collect_run_results(self, eval_id: str, run_id: str) -> Dict[str, Any]:
        """
        Collect detailed results from a completed eval run.
        
        Args:
            eval_id: ID of the evaluation
            run_id: ID of the run
            
        Returns:
            Detailed run results
        """
        try:
            # First, check if run is completed
            status_response = self.get_run_status(eval_id, run_id)
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
                
                # Process and summarize results
                results = {
                    "status": "completed",
                    "total_items": len(output_items),
                    "passed_items": sum(1 for item in output_items if item.get("status") == "pass"),
                    "failed_items": sum(1 for item in output_items if item.get("status") == "fail"),
                    "pass_rate": 0,
                    "items": []
                }
                
                if results["total_items"] > 0:
                    results["pass_rate"] = (results["passed_items"] / results["total_items"]) * 100
                
                # Add detailed item results
                for item in output_items:
                    results["items"].append({
                        "question": item.get("datasource_item", {}).get("question", ""),
                        "expected": item.get("datasource_item", {}).get("correct_answer", ""),
                        "response": item.get("sample", {}).get("output", [{}])[0].get("content", ""),
                        "status": item.get("status", "unknown"),
                        "detailed_results": item.get("results", [])
                    })
                
                return results
            else:
                logger.error(f"Failed to get run output items: {response.status_code} - {response.text}")
                return {"status": "error", "error": response.text}
                
        except Exception as e:
            logger.error(f"Error collecting run results: {e}")
            return {"status": "error", "error": str(e)}
    
    def evaluate_responses(self, 
                          questions_and_answers: List[Dict[str, str]], 
                          eval_type: str = "accuracy_eval",
                          model: str = "gpt-4") -> Dict[str, Any]:
        """
        Evaluate a set of question-answer pairs using the specified evaluation type.
        
        Args:
            questions_and_answers: List of dicts with 'question', 'answer', and 'correct_answer' keys
            eval_type: Type of evaluation to run
            model: Model identifier
            
        Returns:
            Evaluation results
        """
        # Get or create the common evals
        evals = self.get_or_create_common_evals()
        
        if eval_type not in evals:
            logger.error(f"Evaluation type {eval_type} not available")
            return {"status": "error", "error": f"Evaluation type {eval_type} not available"}
        
        eval_id = evals[eval_type]
        
        # Format data for the evaluation
        eval_data = []
        for qa in questions_and_answers:
            eval_data.append({
                "item": {
                    "question": qa["question"],
                    "correct_answer": qa["correct_answer"]
                }
            })
        
        # Create the eval run
        run_id = self.create_eval_run(eval_id, model, eval_data)
        if not run_id:
            return {"status": "error", "error": "Failed to create evaluation run"}
        
        # Initial status check
        status = self.get_run_status(eval_id, run_id)
        
        # Poll until completion (with timeout)
        start_time = time.time()
        timeout = 300  # 5 minutes timeout
        
        while status.get("status") not in ["completed", "failed", "canceled", "error"]:
            if time.time() - start_time > timeout:
                return {"status": "timeout", "message": "Evaluation run timed out", "run_id": run_id}
            
            # Wait before checking again
            time.sleep(10)
            status = self.get_run_status(eval_id, run_id)
        
        # Collect and return results
        if status.get("status") == "completed":
            results = self.collect_run_results(eval_id, run_id)
            results["eval_type"] = eval_type
            results["model"] = model
            return results
        else:
            return {
                "status": "failed", 
                "error": f"Evaluation run failed or was canceled: {status.get('status')}",
                "details": status
            }

    # Add these optimizations to the src/openai_eval_system.py file

def evaluate_single_response(self, question: str, answer: str, 
                          eval_type: str = "helpfulness_eval") -> Dict[str, Any]:
    """
    Efficiently evaluate a single question-answer pair.
    Optimized for auto-evaluation of individual interactions.
    
    Args:
        question: The user's question
        answer: The bot's response
        eval_type: Type of evaluation to run
        
    Returns:
        Evaluation result
    """
    try:
        # Check if we have the required eval
        evals = self.get_or_create_common_evals()
        
        if eval_type not in evals:
            logger.error(f"Evaluation type {eval_type} not available")
            return {"status": "error", "error": f"Evaluation type {eval_type} not available"}
        
        eval_id = evals[eval_type]
        
        # Format data for the evaluation
        eval_data = [{
            "item": {
                "question": question,
                "correct_answer": ""  # We don't have ground truth
            }
        }]
        
        # Create a unique run name with timestamp
        run_name = f"auto_eval_{int(time.time())}"
        
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
            logger.info(f"Created single-response eval run with ID: {run_id}")
            return {
                "status": "success", 
                "run_id": run_id,
                "eval_type": eval_type,
                "question": question[:50] + "..."
            }
        else:
            logger.error(f"Failed to create eval run: {response.status_code} - {response.text}")
            return {"status": "error", "error": response.text}
            
    except Exception as e:
        logger.error(f"Error evaluating single response: {e}")
        return {"status": "error", "error": str(e)}