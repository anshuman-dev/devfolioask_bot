import asyncio
import os
import logging
import time
import traceback
from typing import Dict, List, Any, Optional
from src.enhanced_openai_eval_system import EnhancedOpenAIEvalSystem

logger = logging.getLogger(__name__)

class AutoEvalService:
    """
    Service that automatically evaluates each bot response using OpenAI's Eval API.
    This ensures every interaction appears in the OpenAI Eval dashboard.
    """
    
    def __init__(self):
        """Initialize the auto-evaluation service."""
        try:
            # Log OpenAI API key status (without revealing the key)
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.error("⚠️ OPENAI_API_KEY not found in environment variables! Auto-evaluation will not work.")
            else:
                logger.info(f"OPENAI_API_KEY found in environment variables (starts with: {api_key[:3]}***)")
            
            self.eval_system = EnhancedOpenAIEvalSystem()
            self.pending_evals = []  # Queue for background processing
            self.is_processing = False
            
            # FIX: Don't start periodic processing in __init__
            # We'll start it manually when needed
            logger.info("AutoEvalService initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing AutoEvalService: {e}")
            logger.error(traceback.format_exc())
            # Don't re-raise to avoid breaking the bot if eval doesn't work
        
    def queue_evaluation(self, question: str, answer: str) -> None:
        """
        Queue a question-answer pair for evaluation.
        
        Args:
            question: User's question
            answer: Bot's response
        """
        logger.info(f"Queuing auto-evaluation for question: {question[:30]}...")
        
        try:
            # Skip evaluations for error messages
            if "I encountered an error" in answer or "I'm sorry" in answer and "try again" in answer:
                logger.info("Skipping evaluation for error response")
                return
                
            # Skip very short responses
            if len(answer.strip()) < 20:
                logger.info("Skipping evaluation for very short response")
                return
                
            # Create evaluation data
            eval_data = {
                "question": question,
                "answer": answer,
                "timestamp": int(time.time())
            }
            
            # Add to queue
            self.pending_evals.append(eval_data)
            logger.info(f"Added to evaluation queue. Current queue size: {len(self.pending_evals)}")
            
            # Start background processing if not already running
            if not self.is_processing:
                # FIX: Instead of creating a task, just process in-place
                self._process_evaluation_sync(eval_data)
                
        except Exception as e:
            logger.error(f"Error queuing evaluation: {e}")
            logger.error(traceback.format_exc())
    
    def _process_evaluation_sync(self, eval_data: Dict[str, Any]) -> None:
        """
        Process a single evaluation synchronously without asyncio.
        
        Args:
            eval_data: The evaluation data to process
        """
        try:
            logger.info(f"Processing evaluation for question: {eval_data['question'][:30]}...")
            
            # Use the enhanced eval system
            result = self.eval_system.evaluate_with_feedback(
                eval_data["question"],
                eval_data["answer"]
            )
            
            if result.get("status") == "success":
                logger.info(f"Evaluation with feedback initiated: {result.get('run_id')}")
            else:
                logger.warning(f"Evaluation failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error evaluating: {e}")
            logger.error(traceback.format_exc())
    
    def evaluate_single(self, question: str, answer: str) -> None:
        """
        Immediately evaluate a single question-answer pair.
        This is a convenience method for one-off evaluations.
        
        Args:
            question: User's question
            answer: Bot's response
        """
        self.queue_evaluation(question, answer)