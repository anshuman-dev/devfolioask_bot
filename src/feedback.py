import os
import json
import logging
import time
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)

class FeedbackSystem:
    """
    Enhanced system for collecting, storing, and processing user feedback on bot responses.
    Supports both structured feedback collection and Telegram-specific interactive feedback flow.
    """
    
    def __init__(self, feedback_dir: str = "knowledgebase/feedback"):
        """
        Initialize the feedback system.
        
        Args:
            feedback_dir: Directory where feedback is stored
        """
        self.feedback_dir = feedback_dir
        self.recent_interactions = {}  # Store recent Q&A for feedback reference
        self.pending_feedback = {}  # Store users with pending feedback
        
        # For enhanced feedback collection
        self.authorized_dm_users = ["singhanshuman8", "AniketRaj314"]  # Authorized users for DM feedback
        self.feedback_types = ["Helpful", "Not Helpful", "Incorrect", "Confusing"]  # Feedback categories
        
        # Ensure feedback directory exists
        os.makedirs(self.feedback_dir, exist_ok=True)
        
    def store_interaction(self, user_id: str, question: str, answer: str) -> str:
        """
        Store a Q&A interaction for potential future feedback.
        
        Args:
            user_id: Telegram user ID
            question: User's question
            answer: Bot's answer
            
        Returns:
            Interaction ID for reference
        """
        # Use a simple incremental ID with timestamp for easier readability
        timestamp = int(time.time())
        interaction_id = f"int_{timestamp}_{user_id[-4:]}"
        
        # Store in memory
        self.recent_interactions[interaction_id] = {
            "user_id": user_id,
            "question": question,
            "answer": answer,
            "timestamp": timestamp
        }
        
        # Limit to 10 recent interactions per user
        user_interactions = [k for k, v in self.recent_interactions.items() 
                            if v["user_id"] == user_id]
        
        if len(user_interactions) > 10:
            # Sort by timestamp (oldest first)
            user_interactions.sort(
                key=lambda k: self.recent_interactions[k]["timestamp"]
            )
            # Remove oldest
            del self.recent_interactions[user_interactions[0]]
            
        logger.info(f"Stored interaction {interaction_id} for user {user_id}")
        return interaction_id
        
    def get_recent_interactions(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get recent interactions for a user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            List of recent interactions with IDs
        """
        interactions = []
        
        for int_id, data in self.recent_interactions.items():
            if data["user_id"] == user_id:
                interactions.append({
                    "id": int_id,
                    "question": data["question"],
                    "answer": data["answer"],
                    "timestamp": data["timestamp"]
                })
                
        # Sort by timestamp (newest first)
        interactions.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return interactions
        
    def start_feedback(self, user_id: str, interaction_id: Optional[str] = None) -> bool:
        """
        Start the feedback process for a user.
        
        Args:
            user_id: Telegram user ID
            interaction_id: Optional specific interaction ID to get feedback for
            
        Returns:
            True if feedback process started, False otherwise
        """
        # Check if interaction exists if ID provided
        if interaction_id and interaction_id not in self.recent_interactions:
            logger.warning(f"Interaction {interaction_id} not found for feedback")
            return False
            
        # Set pending feedback state
        self.pending_feedback[user_id] = {
            "state": "awaiting_interaction" if not interaction_id else "awaiting_feedback_type",
            "interaction_id": interaction_id
        }
        
        logger.info(f"Started feedback process for user {user_id}")
        return True
        
    def process_feedback_message(self, user_id: str, message: str) -> Dict[str, Any]:
        """
        Process a message from a user in the feedback workflow.
        
        Args:
            user_id: Telegram user ID
            message: User's message
            
        Returns:
            Dict with status and next_step information
        """
        # Check if user has pending feedback
        if user_id not in self.pending_feedback:
            return {
                "status": "error",
                "message": "No active feedback session"
            }
            
        # Get current state
        current_state = self.pending_feedback[user_id]["state"]
        
        # Handle awaiting interaction ID
        if current_state == "awaiting_interaction":
            # If user sent a number instead of full ID, try to map it
            if message.isdigit() and 1 <= int(message) <= 10:
                # Get the nth most recent interaction
                interactions = self.get_recent_interactions(user_id)
                if int(message) <= len(interactions):
                    interaction_id = interactions[int(message)-1]["id"]
                    self.pending_feedback[user_id] = {
                        "state": "awaiting_feedback_type",
                        "interaction_id": interaction_id
                    }
                    return {
                        "status": "success",
                        "next_step": "select_feedback_type",
                        "message": "Please select a feedback type:",
                        "options": self.feedback_types
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"No interaction found with number {message}. Please select a valid number from the list."
                    }
            
            # Check if message is a valid interaction ID
            elif message in self.recent_interactions:
                self.pending_feedback[user_id] = {
                    "state": "awaiting_feedback_type",
                    "interaction_id": message
                }
                return {
                    "status": "success",
                    "next_step": "select_feedback_type",
                    "message": "Please select a feedback type:",
                    "options": self.feedback_types
                }
            else:
                return {
                    "status": "error",
                    "message": "Invalid selection. Please enter a number from the list (1-5) or the full interaction ID."
                }
        
        # Handle awaiting feedback type
        elif current_state == "awaiting_feedback_type":
            # Check if the feedback type is valid
            if message in self.feedback_types or message.isdigit() and 1 <= int(message) <= len(self.feedback_types):
                # Convert digit to feedback type if necessary
                if message.isdigit():
                    feedback_type = self.feedback_types[int(message)-1]
                else:
                    feedback_type = message
                
                # Update state
                self.pending_feedback[user_id]["state"] = "awaiting_feedback_text"
                self.pending_feedback[user_id]["feedback_type"] = feedback_type
                
                return {
                    "status": "success",
                    "next_step": "provide_feedback_text",
                    "message": f"You selected {feedback_type}. Please provide detailed feedback about this response:"
                }
            else:
                return {
                    "status": "error",
                    "message": f"Invalid feedback type. Please select one of: {', '.join(self.feedback_types)}"
                }
                
        # Handle awaiting feedback text
        elif current_state == "awaiting_feedback_text":
            interaction_id = self.pending_feedback[user_id]["interaction_id"]
            feedback_type = self.pending_feedback[user_id]["feedback_type"]
            
            # Update state
            self.pending_feedback[user_id]["state"] = "awaiting_confirmation"
            self.pending_feedback[user_id]["feedback_text"] = message
            
            return {
                "status": "success",
                "next_step": "confirm_feedback",
                "message": "Thank you for your feedback. Is there anything else you'd like to add?",
                "options": ["Yes", "No"]
            }
            
        # Handle awaiting confirmation
        elif current_state == "awaiting_confirmation":
            # Check if user wants to add more feedback
            if message.lower() in ["yes", "y", "1"]:
                # Update state back to awaiting_feedback_text
                self.pending_feedback[user_id]["state"] = "awaiting_feedback_text"
                return {
                    "status": "success",
                    "next_step": "provide_feedback_text",
                    "message": "Please provide additional feedback:"
                }
            else:
                # Save the feedback
                interaction_id = self.pending_feedback[user_id]["interaction_id"]
                feedback_type = self.pending_feedback[user_id]["feedback_type"]
                feedback_text = self.pending_feedback[user_id]["feedback_text"]
                
                interaction = self.recent_interactions.get(interaction_id)
                if not interaction:
                    # Clean up the pending state
                    del self.pending_feedback[user_id]
                    return {
                        "status": "error",
                        "message": "Interaction not found. Feedback process canceled."
                    }
                
                # Save the feedback
                feedback_saved = self.save_structured_feedback(
                    interaction["question"],
                    interaction["answer"],
                    feedback_type,
                    feedback_text,
                    user_id
                )
                
                # Clean up the pending state
                del self.pending_feedback[user_id]
                
                if feedback_saved:
                    # Update knowledge base with feedback
                    self._update_knowledge_with_feedback(
                        interaction["question"],
                        interaction["answer"],
                        feedback_type,
                        feedback_text
                    )
                    
                    return {
                        "status": "success",
                        "next_step": "complete",
                        "message": "Thank you for your feedback! It will help improve the bot."
                    }
                else:
                    return {
                        "status": "error",
                        "message": "Failed to save feedback. Please try again later."
                    }
                
        # Handle unknown state
        return {
            "status": "error",
            "message": "Unknown feedback state. Please restart the feedback process."
        }
        
    def save_structured_feedback(self, question: str, answer: str, 
                               feedback_type: str, feedback_text: str, 
                               user_id: str) -> bool:
        """
        Save structured feedback to the feedback knowledge base.
        
        Args:
            question: Original question
            answer: Bot's answer
            feedback_type: Type of feedback (e.g., "Helpful", "Not Helpful")
            feedback_text: Detailed feedback text
            user_id: Telegram user ID (anonymized)
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Create a unique filename
            timestamp = int(time.time())
            filename = f"feedback_{timestamp}.json"
            filepath = os.path.join(self.feedback_dir, filename)
            
            # Create feedback entry
            feedback_entry = {
                "question": question,
                "answer": answer,
                "feedback_type": feedback_type,
                "feedback_text": feedback_text,
                "user_id": user_id[-6:],  # Store only last 6 chars for privacy
                "timestamp": timestamp
            }
            
            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(feedback_entry, f, indent=2)
                
            logger.info(f"Structured feedback saved to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving structured feedback: {e}")
            return False
            
    def save_feedback(self, question: str, answer: str, feedback: str, user_id: str) -> bool:
        """
        Save feedback to the feedback knowledge base (legacy method).
        
        Args:
            question: Original question
            answer: Bot's answer
            feedback: User's feedback
            user_id: Telegram user ID (anonymized)
            
        Returns:
            True if saved successfully, False otherwise
        """
        # Call structured method with default feedback type
        return self.save_structured_feedback(
            question, 
            answer, 
            "General Feedback", 
            feedback, 
            user_id
        )
            
    def process_scheduled_feedback(self) -> Dict[str, Any]:
        """
        Process all feedback collected during the week and integrate into knowledge base.
        
        Returns:
            Dict with statistics about processed feedback
        """
        # This would be called by a scheduler weekly
        feedback_files = []
        try:
            # List all feedback files
            for filename in os.listdir(self.feedback_dir):
                if filename.startswith("feedback_") and filename.endswith(".json"):
                    feedback_files.append(os.path.join(self.feedback_dir, filename))
                    
            # Process each file
            processed = 0
            feedback_stats = {
                "total": len(feedback_files),
                "by_type": {},
                "knowledge_updates": []
            }
            
            for filepath in feedback_files:
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        feedback_data = json.load(f)
                        
                    # Update stats
                    feedback_type = feedback_data.get("feedback_type", "General Feedback")
                    if feedback_type not in feedback_stats["by_type"]:
                        feedback_stats["by_type"][feedback_type] = 0
                    feedback_stats["by_type"][feedback_type] += 1
                    
                    # Apply knowledge updates based on feedback
                    update = self._update_knowledge_with_feedback(
                        feedback_data.get("question", ""),
                        feedback_data.get("answer", ""),
                        feedback_type,
                        feedback_data.get("feedback_text", "")
                    )
                    
                    if update:
                        feedback_stats["knowledge_updates"].append(update)
                        processed += 1
                        
                except Exception as e:
                    logger.error(f"Error processing feedback file {filepath}: {e}")
                    
            feedback_stats["processed"] = processed
            
            return {
                "status": "success",
                "stats": feedback_stats
            }
            
        except Exception as e:
            logger.error(f"Error processing scheduled feedback: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
            
    def _update_knowledge_with_feedback(self, question: str, answer: str, 
                                      feedback_type: str, feedback_text: str) -> Optional[Dict[str, Any]]:
        """
        Update knowledge base based on feedback.
        
        Args:
            question: Original question
            answer: Bot's answer
            feedback_type: Type of feedback
            feedback_text: Detailed feedback
            
        Returns:
            Dict with update information if successful, None otherwise
        """
        try:
            # For now, just log the feedback - in a real implementation this would
            # trigger knowledge base updates or model fine-tuning
            logger.info(f"Knowledge update triggered by feedback type: {feedback_type}")
            logger.info(f"Question: {question[:50]}...")
            logger.info(f"Feedback: {feedback_text[:50]}...")
            
            # Placeholder for future implementation
            # This would analyze feedback and make appropriate updates to the knowledge base
            
            return {
                "timestamp": int(time.time()),
                "feedback_type": feedback_type,
                "action": "logged",  # Would be "updated", "created", etc. in real implementation
                "details": "Feedback logged for future knowledge base improvement"
            }
            
        except Exception as e:
            logger.error(f"Error updating knowledge with feedback: {e}")
            return None
    
    def is_authorized_for_dm_feedback(self, username: str) -> bool:
        """
        Check if a user is authorized to provide feedback via DM.
        
        Args:
            username: Telegram username
            
        Returns:
            True if authorized, False otherwise
        """
        return username in self.authorized_dm_users
    
    def get_feedback_types(self) -> List[str]:
        """
        Get available feedback types.
        
        Returns:
            List of feedback type strings
        """
        return self.feedback_types