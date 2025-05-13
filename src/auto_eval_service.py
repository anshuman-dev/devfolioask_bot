import asyncio
import os
import logging
from typing import Dict, List, Any, Optional
from src.openai_eval_system import OpenAIEvalSystem

logger = logging.getLogger(__name__)

class AutoEvalService:
    """
    Service that automatically evaluates each bot response using OpenAI's Eval API.
    This ensures every interaction appears in the OpenAI Eval dashboard.
    """
    
    def __init__(self):
        """Initialize the auto-evaluation service."""
        self.eval_system = OpenAIEvalSystem()
        self.pending_evals = []  # Queue for background processing
        self.is_processing = False
        self.eval_types = ["helpfulness_eval", "clarity_eval"]  # Types of evals to run
        
    def queue_evaluation(self, question: str, answer: str) -> None:
        """
        Queue a question-answer pair for evaluation.
        
        Args:
            question: User's question
            answer: Bot's response
        """
        logger.info(f"Queuing auto-evaluation for question: {question[:30]}...")
        
        # Create evaluation data
        eval_data = {
            "question": question,
            "answer": answer,
            "correct_answer": "",  # We don't have a ground truth answer
            "timestamp": int(time.time())
        }
        
        # Add to queue
        self.pending_evals.append(eval_data)
        
        # Start background processing if not already running
        if not self.is_processing:
            asyncio.create_task(self._process_evaluation_queue())
    
    async def _process_evaluation_queue(self) -> None:
        """Process the queue of pending evaluations in the background."""
        if self.is_processing:
            return
            
        self.is_processing = True
        
        try:
            while self.pending_evals:
                # Get a batch of up to 5 evaluations to process
                batch = self.pending_evals[:5]
                self.pending_evals = self.pending_evals[5:]
                
                logger.info(f"Processing batch of {len(batch)} evaluations")
                
                # Process the batch
                await self._evaluate_batch(batch)
                
                # Small delay to avoid overwhelming the API
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error processing evaluation queue: {e}")
        finally:
            self.is_processing = False
            
            # If there are still items in the queue, start processing again
            if self.pending_evals:
                asyncio.create_task(self._process_evaluation_queue())
    
    async def _evaluate_batch(self, batch: List[Dict[str, Any]]) -> None:
        """
        Evaluate a batch of question-answer pairs.
        
        Args:
            batch: List of evaluation data dicts
        """
        try:
            # Process each item individually using the optimized method
            for item in batch:
                for eval_type in self.eval_types:
                    result = await asyncio.to_thread(
                        self.eval_system.evaluate_single_response,
                        item["question"],
                        item["answer"],
                        eval_type
                    )
                    
                    if result.get("status") != "success":
                        logger.warning(f"Evaluation failed: {result.get('error', 'Unknown error')}")
                    
            logger.info(f"Successfully evaluated batch of {len(batch)} interactions")
                
        except Exception as e:
            logger.error(f"Error evaluating batch: {e}")
    
    def evaluate_single(self, question: str, answer: str) -> None:
        """
        Immediately evaluate a single question-answer pair.
        This is a convenience method for one-off evaluations.
        
        Args:
            question: User's question
            answer: Bot's response
        """
        self.queue_evaluation(question, answer)