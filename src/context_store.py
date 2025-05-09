import os
import json
import logging
import time
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ContextStore:
    """
    Handles saving and loading of user contexts to/from disk.
    Provides persistence between bot sessions.
    """
    
    def __init__(self, storage_dir: str = "storage/contexts"):
        """
        Initialize the context store.
        
        Args:
            storage_dir: Directory to store context files
        """
        self.storage_dir = storage_dir
        self.contexts_cache = {}  # In-memory cache
        self.dirty_contexts = set()  # Track modified contexts
        self.last_save_time = time.time()
        self.save_interval = 300  # Save every 5 minutes
        self.interaction_count = 0  # Count interactions since last full save
        
        # Ensure storage directory exists
        os.makedirs(self.storage_dir, exist_ok=True)
        
        logger.info(f"ContextStore initialized with storage directory: {storage_dir}")
        
    def get_user_context(self, user_id: str) -> Dict[str, Any]:
        """
        Get a user's context, loading from disk if not in memory.
        
        Args:
            user_id: User ID to get context for
            
        Returns:
            User context dictionary
        """
        # Check cache first
        if user_id in self.contexts_cache:
            return self.contexts_cache[user_id]
            
        # Try to load from disk
        context = self._load_from_disk(user_id)
        
        # If no context found, create a new one
        if not context:
            context = self._create_default_context(user_id)
            
        # Store in cache
        self.contexts_cache[user_id] = context
        
        return context
        
    def update_user_context(self, user_id: str, context: Dict[str, Any]) -> None:
        """
        Update a user's context in memory and mark for saving.
        
        Args:
            user_id: User ID to update context for
            context: New context dictionary
        """
        # Update cache
        self.contexts_cache[user_id] = context
        
        # Mark as dirty (needs saving)
        self.dirty_contexts.add(user_id)
        
        # Increment interaction count
        self.interaction_count += 1
        
        # Check if we should save
        now = time.time()
        if (now - self.last_save_time > self.save_interval) or (self.interaction_count >= 50):
            self.save_all_dirty()
            self.last_save_time = now
            self.interaction_count = 0
            
    def save_all_dirty(self) -> None:
        """Save all modified contexts to disk."""
        if not self.dirty_contexts:
            return
            
        logger.info(f"Saving {len(self.dirty_contexts)} dirty contexts")
        
        for user_id in list(self.dirty_contexts):
            self._save_to_disk(user_id, self.contexts_cache[user_id])
            self.dirty_contexts.remove(user_id)
            
    def _create_default_context(self, user_id: str) -> Dict[str, Any]:
        """
        Create a default context for a new user.
        
        Args:
            user_id: User ID
            
        Returns:
            Default context dictionary
        """
        now = time.time()
        
        return {
            "identity": {
                "user_id": user_id,
                "first_interaction": now,
                "username": None
            },
            "hackathon_state": {
                "current_phase": None,  # planning, setup, active, judging
                "hackathon_name": None,
                "has_enabled_judging": False
            },
            "preferences": {
                "judging_mode_preference": None,
                "previous_concerns": []
            },
            "conversation": {
                "recent_questions": [],
                "recent_answers": [],
                "interaction_count": 0,
                "last_interaction_time": now,
                "last_scenario_discussed": None
            },
            "feedback": {
                "positive_feedback_count": 0,
                "negative_feedback_count": 0,
                "support_contact_suggested": False
            }
        }
        
    def _get_filepath(self, user_id: str) -> str:
        """Get the filepath for a user's context file."""
        return os.path.join(self.storage_dir, f"context_{user_id}.json")
        
    def _load_from_disk(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a user's context from disk.
        
        Args:
            user_id: User ID to load
            
        Returns:
            Context dictionary if found, None otherwise
        """
        filepath = self._get_filepath(user_id)
        
        if not os.path.exists(filepath):
            return None
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                context = json.load(f)
                logger.info(f"Loaded context for user {user_id} from disk")
                return context
        except Exception as e:
            logger.error(f"Error loading context for user {user_id}: {e}")
            return None
            
    def _save_to_disk(self, user_id: str, context: Dict[str, Any]) -> bool:
        """
        Save a user's context to disk.
        
        Args:
            user_id: User ID to save
            context: Context dictionary to save
            
        Returns:
            True if successful, False otherwise
        """
        filepath = self._get_filepath(user_id)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(context, f, indent=2)
                logger.info(f"Saved context for user {user_id} to disk")
                return True
        except Exception as e:
            logger.error(f"Error saving context for user {user_id}: {e}")
            return False