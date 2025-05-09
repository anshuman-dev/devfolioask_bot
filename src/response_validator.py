import re
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

class ResponseValidator:
    """
    Validates and improves bot responses to ensure high quality.
    Checks for completeness, accuracy, and appropriate structure.
    """
    
    def __init__(self):
        """Initialize the response validator."""
        pass
        
    def validate_response(self, response: str, query_data: Dict[str, Any], 
                        scenario_data: Dict[str, Any]) -> Tuple[bool, str, List[str]]:
        """
        Validate a response for quality and completeness.
        
        Args:
            response: The response to validate
            query_data: Data about the query
            scenario_data: Data about the scenario
            
        Returns:
            Tuple of (is_valid, improved_response, issues)
        """
        issues = []
        improved_response = response
        
        # Check for minimum length
        if len(response) < 50:
            issues.append("Response is too short")
            
        # Check for maximum length (avoid overwhelming responses)
        if len(response) > 1000:
            issues.append("Response is too long and may overwhelm the user")
        
        # Check if response contains structured steps when needed
        if self._requires_steps(query_data, scenario_data):
            if not self._has_numbered_steps(response):
                issues.append("Response should include numbered steps")
                improved_response = self._add_numbered_steps(improved_response, scenario_data)
        
        # Check for proper sections
        if not self._has_proper_sections(response):
            issues.append("Response lacks clear sections (greeting, content, conclusion)")
            improved_response = self._improve_sections(improved_response)
        
        # Check if response addresses the query intent
        intent = query_data.get("intent", {}).get("type", "question")
        if not self._addresses_intent(response, intent):
            issues.append(f"Response doesn't properly address {intent} intent")
            improved_response = self._improve_for_intent(improved_response, intent)
        
        # Check for required disclaimers or notes
        required_notes = self._get_required_notes(scenario_data)
        if required_notes and not self._contains_notes(response, required_notes):
            issues.append("Response is missing required notes or disclaimers")
            improved_response = self._add_notes(improved_response, required_notes)
        
        # Check for personalization when context is available
        if query_data.get("hackathon_context") and not self._is_personalized(response, query_data):
            issues.append("Response lacks personalization")
            improved_response = self._add_personalization(improved_response, query_data)
        
        # Determine if the response is valid overall
        is_valid = len(issues) <= 1  # Allow one minor issue
        
        return is_valid, improved_response, issues
    
    def _requires_steps(self, query_data: Dict[str, Any], scenario_data: Dict[str, Any]) -> bool:
        """Check if the response requires steps."""
        # Check if scenario has steps
        if scenario_data and "answer_components" in scenario_data and "steps" in scenario_data["answer_components"]:
            steps = scenario_data["answer_components"]["steps"]
            if steps and len(steps) > 0:
                return True
                
        # Check query for step indicators
        query = query_data.get("cleaned_query", "").lower()
        step_indicators = ["how to", "how do i", "steps to", "process for", "procedure"]
        return any(indicator in query for indicator in step_indicators)
    
    def _has_numbered_steps(self, response: str) -> bool:
        """Check if response contains numbered steps."""
        # Look for patterns like "1.", "2.", etc.
        step_pattern = re.compile(r'\b\d+\.\s')
        matches = step_pattern.findall(response)
        return len(matches) >= 2  # At least 2 steps
    
    def _add_numbered_steps(self, response: str, scenario_data: Dict[str, Any]) -> str:
        """Add numbered steps to a response."""
        if not scenario_data or "answer_components" not in scenario_data or "steps" not in scenario_data["answer_components"]:
            return response
            
        steps = scenario_data["answer_components"]["steps"]
        if not steps:
            return response
            
        # Format steps
        formatted_steps = "\n\n"
        for i, step in enumerate(steps):
            formatted_steps += f"{i+1}. {step}\n"
        formatted_steps += "\n"
        
        # Find insertion point (after first paragraph)
        parts = response.split('\n\n', 1)
        if len(parts) > 1:
            return parts[0] + "\n\n" + formatted_steps + parts[1]
        else:
            return response + formatted_steps
    
    def _has_proper_sections(self, response: str) -> bool:
        """Check if response has proper sections."""
        # Should have at least 2 paragraphs
        paragraphs = response.split('\n\n')
        return len(paragraphs) >= 2
    
    def _improve_sections(self, response: str) -> str:
        """Improve response sections."""
        paragraphs = response.split('\n\n')
        
        # If only one paragraph, try to split it
        if len(paragraphs) == 1:
            # Try to split at sentences
            sentences = re.split(r'(?<=[.!?])\s+', response)
            
            if len(sentences) >= 3:
                greeting = sentences[0]
                content = ' '.join(sentences[1:-1])
                conclusion = sentences[-1]
                
                return f"{greeting}\n\n{content}\n\n{conclusion}"
        
        return response
    
    def _addresses_intent(self, response: str, intent: str) -> bool:
        """Check if response addresses the intent."""
        response_lower = response.lower()
        
        intent_indicators = {
            "problem": ["issue", "problem", "trouble", "fix", "resolve", "solution"],
            "followup": ["regarding", "to clarify", "to answer", "follow-up"],
            "clarification": ["mean", "refers to", "definition", "clarify"]
        }
        
        # For question intent, we assume it's addressed by default
        if intent not in intent_indicators:
            return True
            
        # Check for intent-specific indicators
        indicators = intent_indicators[intent]
        return any(indicator in response_lower for indicator in indicators)
    
    def _improve_for_intent(self, response: str, intent: str) -> str:
        """Improve response for a specific intent."""
        intent_prefixes = {
            "problem": "I understand you're having an issue. ",
            "followup": "Regarding your follow-up question, ",
            "clarification": "To clarify, "
        }
        
        prefix = intent_prefixes.get(intent, "")
        if prefix and not response.startswith(prefix):
            return prefix + response
            
        return response
    
    def _get_required_notes(self, scenario_data: Dict[str, Any]) -> List[str]:
        """Get required notes for a scenario."""
        required_notes = []
        
        if scenario_data:
            # Judging criteria scenario requires a note about contacting support for customization
            if scenario_data.get("scenario_id") == "judging_criteria":
                required_notes.append("custom criteria require contacting @singhanshuman8")
                
            # Judge invitation scenario requires a note about automatic emails
            elif scenario_data.get("scenario_id") == "judge_invitation":
                required_notes.append("judging invite is sent automatically")
                
            # Add scenario-specific notes
            if "answer_components" in scenario_data and "notes" in scenario_data["answer_components"]:
                notes = scenario_data["answer_components"]["notes"]
                if notes:
                    # Split notes into individual sentences
                    note_sentences = re.split(r'(?<=[.!?])\s+', notes)
                    required_notes.extend(note_sentences)
        
        return required_notes
    
    def _contains_notes(self, response: str, required_notes: List[str]) -> bool:
        """Check if response contains required notes."""
        response_lower = response.lower()
        
        for note in required_notes:
            # Convert to lowercase and get key terms
            note_lower = note.lower()
            key_terms = [term for term in note_lower.split() if len(term) > 4]
            
            # Check if all key terms are in the response
            if key_terms and all(term in response_lower for term in key_terms):
                continue
                
            # If key terms not found, check for the general meaning
            if not any(self._similar_meaning(note_lower, sentence.lower()) 
                     for sentence in re.split(r'(?<=[.!?])\s+', response_lower)):
                return False
                
        return True
    
    def _similar_meaning(self, note: str, sentence: str) -> bool:
        """Check if a sentence has similar meaning to a note."""
        # Extract key terms from both
        note_terms = set(term for term in note.split() if len(term) > 4)
        sentence_terms = set(term for term in sentence.split() if len(term) > 4)
        
        # Check overlap
        if not note_terms or not sentence_terms:
            return False
            
        overlap = note_terms.intersection(sentence_terms)
        return len(overlap) >= min(len(note_terms) // 2, 2)  # At least half or 2 terms
    
    def _add_notes(self, response: str, required_notes: List[str]) -> str:
        """Add missing notes to a response."""
        # Find sentences already in the response
        response_sentences = set(sentence.lower() for sentence in re.split(r'(?<=[.!?])\s+', response.lower()))
        
        # Filter notes that are truly missing
        missing_notes = []
        for note in required_notes:
            note_lower = note.lower()
            if not any(self._similar_meaning(note_lower, sentence) for sentence in response_sentences):
                missing_notes.append(note)
                
        if not missing_notes:
            return response
            
        # Add missing notes at the end
        note_paragraph = "\n\nNote: " + " ".join(missing_notes)
        
        return response + note_paragraph
    
    def _is_personalized(self, response: str, query_data: Dict[str, Any]) -> bool:
        """Check if response is personalized."""
        # Check for hackathon name
        hackathon_context = query_data.get("hackathon_context", {})
        if hackathon_context.get("name") and hackathon_context["name"] not in response:
            return False
            
        # Check for phase-specific content
        if hackathon_context.get("phase"):
            phase = hackathon_context["phase"]
            phase_terms = {
                "planning": ["plan", "planning", "prepare", "setting up"],
                "setup": ["setup", "configure", "setting up", "customizing"],
                "active": ["ongoing", "running", "current", "active", "monitor"],
                "judging": ["judging", "evaluation", "scoring", "results"]
            }
            
            terms = phase_terms.get(phase, [])
            if terms and not any(term in response.lower() for term in terms):
                return False
                
        return True
    
    def _add_personalization(self, response: str, query_data: Dict[str, Any]) -> str:
        """Add personalization to a response."""
        hackathon_context = query_data.get("hackathon_context", {})
        
        # Add hackathon name if missing
        if hackathon_context.get("name") and hackathon_context["name"] not in response:
            # Replace generic "your hackathon" with the specific name
            response = response.replace("your hackathon", f"your {hackathon_context['name']} hackathon")
            
        # Add phase-specific guidance if missing
        if hackathon_context.get("phase") and not self._is_personalized(response, query_data):
            phase = hackathon_context["phase"]
            phase_tips = {
                "planning": "\n\nSince you're in the planning phase, remember to also think about your hackathon's overall structure and theme.",
                "setup": "\n\nAs you're in the setup phase, don't forget to configure your submission requirements and customize your hackathon page.",
                "active": "\n\nSince your hackathon is currently active, consider monitoring submissions and preparing for the judging phase.",
                "judging": "\n\nWith judging in progress, ensure all your judges have access and understand how to evaluate projects."
            }
            
            tip = phase_tips.get(phase, "")
            if tip:
                # Add the tip before the last paragraph
                paragraphs = response.split('\n\n')
                if len(paragraphs) > 1:
                    response = '\n\n'.join(paragraphs[:-1]) + tip + '\n\n' + paragraphs[-1]
                else:
                    response += tip
                    
        return response