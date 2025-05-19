import re
import logging
import time
from typing import Dict, List, Any, Tuple, Optional

logger = logging.getLogger(__name__)

class ContextInferenceEngine:
    """
    Analyzes conversations to automatically update user context.
    Extracts insights about hackathon state, user preferences, and ongoing issues.
    """
    
    def update_context(self, current_context: Dict[str, Any], 
                      query: str, response: str) -> Dict[str, Any]:
        """
        Update user context based on the latest interaction.
        
        Args:
            current_context: Current user context
            query: User's query
            response: Bot's response
            
        Returns:
            Updated context dictionary
        """
        # Create a working copy to avoid modifying the original during processing
        updated_context = current_context.copy()
        
        # If context is empty or not properly initialized, initialize it
        if not updated_context or not isinstance(updated_context, dict):
            updated_context = self._create_default_context()
        
        # Ensure critical sections exist
        for section in ["identity", "hackathon_state", "preferences", "conversation", "feedback"]:
            if section not in updated_context:
                updated_context[section] = {}
        
        # Update basic conversation tracking
        self._update_conversation_tracking(updated_context, query, response)
        
        # Infer hackathon state
        self._infer_hackathon_state(updated_context, query, response)
        
        # Infer preferences
        self._infer_preferences(updated_context, query, response)
        
        # Detect feedback sentiment
        self._detect_feedback(updated_context, query)
        
        # Track support contact suggestions
        if "feedback" in updated_context and "@singhanshuman8" in response or "@AniketRaj314" in response:
            updated_context["feedback"]["support_contact_suggested"] = True
            
        return updated_context
    
    def _create_default_context(self) -> Dict[str, Any]:
        """Create a default context structure."""
        now = time.time()
        
        return {
            "identity": {
                "user_id": None,
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
        
    def _update_conversation_tracking(self, context: Dict[str, Any], 
                                    query: str, response: str) -> None:
        """Update basic conversation tracking information."""
        now = time.time()
        
        # Update timestamps
        context["conversation"]["last_interaction_time"] = now
        
        # Update interaction count
        if "interaction_count" not in context["conversation"]:
            context["conversation"]["interaction_count"] = 0
        context["conversation"]["interaction_count"] += 1
        
        # Add to recent questions/answers (limited to last 10)
        if "recent_questions" not in context["conversation"]:
            context["conversation"]["recent_questions"] = []
            
        if "recent_answers" not in context["conversation"]:
            context["conversation"]["recent_answers"] = []
            
        context["conversation"]["recent_questions"].append(query)
        context["conversation"]["recent_answers"].append(response)
        
        # Keep only the last 10 interactions
        if len(context["conversation"]["recent_questions"]) > 10:
            context["conversation"]["recent_questions"] = context["conversation"]["recent_questions"][-10:]
            context["conversation"]["recent_answers"] = context["conversation"]["recent_answers"][-10:]
            
        # Try to detect the last scenario discussed
        scenario_indicators = {
            "judging criteria": "judging_criteria",
            "add judges": "judge_invitation",
            "inviting judges": "judge_invitation",
            "judge invitation": "judge_invitation",
            "judging modes": "judging_modes",
            "offline judging": "judging_modes",
            "online judging": "judging_modes",
            "sponsor judging": "judging_modes"
        }
        
        # Check both query and response for scenario indicators
        for text in [query.lower(), response.lower()]:
            for indicator, scenario_id in scenario_indicators.items():
                if indicator in text:
                    context["conversation"]["last_scenario_discussed"] = scenario_id
                    break
        
    def _infer_hackathon_state(self, context: Dict[str, Any], 
                             query: str, response: str) -> None:
        """Infer the hackathon state from conversation."""
        query_lower = query.lower()
        response_lower = response.lower()
        
        # Try to extract hackathon name
        hackathon_match = re.search(r'for\s+(?:the\s+)?([A-Za-z0-9\s]+(?:hackathon|event|competition))', 
                                  query_lower, re.IGNORECASE)
        if hackathon_match:
            context["hackathon_state"]["hackathon_name"] = hackathon_match.group(1).strip()
            
        # Determine hackathon phase based on conversation
        phase_indicators = {
            "planning": [
                "planning", "going to", "want to", "thinking about", "how do I create", 
                "how to set up", "how to start"
            ],
            "setup": [
                "setting up", "configuring", "customizing", "adding judges", "invite judges",
                "add sponsor", "customize", "configure"
            ],
            "active": [
                "ongoing", "submissions", "participant", "project", "hacker",
                "currently running", "during the hackathon"
            ],
            "judging": [
                "judging", "judges are", "evaluate", "scoring", "results", "winners",
                "announcement", "leaderboard"
            ]
        }
        
        # Check for phase indicators
        for phase, indicators in phase_indicators.items():
            for indicator in indicators:
                if indicator in query_lower or indicator in response_lower:
                    # Only update if we're moving forward in the process or have no phase yet
                    current_phase = context["hackathon_state"]["current_phase"]
                    if not current_phase or self._is_later_phase(current_phase, phase):
                        context["hackathon_state"]["current_phase"] = phase
                        break
                        
        # Check if judging has been enabled
        judging_enabled_indicators = [
            "enabled judging", "judging is now enabled", "judging has been enabled",
            "have enabled judging", "turned on judging"
        ]
        
        for indicator in judging_enabled_indicators:
            if indicator in response_lower:
                context["hackathon_state"]["has_enabled_judging"] = True
                break
    
    def _infer_preferences(self, context: Dict[str, Any], 
                         query: str, response: str) -> None:
        """Infer user preferences from conversation."""
        query_lower = query.lower()
        response_lower = response.lower()
        
        # Extract judging mode preference
        judging_modes = {
            "online": ["online judging", "remote judging", "virtual judging"],
            "offline": ["offline judging", "in-person judging", "physical judging"],
            "sponsor": ["sponsor judging", "sponsor prize", "sponsor evaluation"]
        }
        
        for mode, indicators in judging_modes.items():
            for indicator in indicators:
                if indicator in query_lower or indicator in response_lower:
                    context["preferences"]["judging_mode_preference"] = mode
                    break
                    
        # Identify user concerns
        concern_indicators = {
            "login_issues": ["can't log in", "login issue", "cannot access"],
            "submission_problems": ["can't submit", "submission error", "upload issue"],
            "judge_access": ["judges can't access", "judge login", "judge invitation"],
            "customization": ["customize", "change logo", "modify criteria"]
        }
        
        for concern, indicators in concern_indicators.items():
            for indicator in indicators:
                if indicator in query_lower:
                    if "previous_concerns" not in context["preferences"]:
                        context["preferences"]["previous_concerns"] = []
                        
                    if concern not in context["preferences"]["previous_concerns"]:
                        context["preferences"]["previous_concerns"].append(concern)
    
    def _detect_feedback(self, context: Dict[str, Any], query: str) -> None:
        """Detect feedback sentiment in user messages."""
        query_lower = query.lower()
        
        # Detect positive feedback
        positive_indicators = [
            "thank", "thanks", "helpful", "appreciate", "good answer",
            "great", "excellent", "perfect", "correct", "worked"
        ]
        
        # Detect negative feedback
        negative_indicators = [
            "not helpful", "incorrect", "wrong", "doesn't work", "didn't work",
            "bad answer", "confused", "confusing", "not right", "doesn't make sense"
        ]
        
        # Check for positive feedback
        for indicator in positive_indicators:
            if indicator in query_lower:
                if "positive_feedback_count" not in context["feedback"]:
                    context["feedback"]["positive_feedback_count"] = 0
                    
                context["feedback"]["positive_feedback_count"] += 1
                break
                
        # Check for negative feedback
        for indicator in negative_indicators:
            if indicator in query_lower:
                if "negative_feedback_count" not in context["feedback"]:
                    context["feedback"]["negative_feedback_count"] = 0
                    
                context["feedback"]["negative_feedback_count"] += 1
                break
    
    def _is_later_phase(self, current_phase: str, new_phase: str) -> bool:
        """
        Determine if a new phase is later than the current phase.
        
        Args:
            current_phase: Current hackathon phase
            new_phase: New hackathon phase to check
            
        Returns:
            True if new phase is later, False otherwise
        """
        phase_order = {
            "planning": 1,
            "setup": 2,
            "active": 3,
            "judging": 4
        }
        
        current_value = phase_order.get(current_phase, 0)
        new_value = phase_order.get(new_phase, 0)
        
        return new_value > current_value