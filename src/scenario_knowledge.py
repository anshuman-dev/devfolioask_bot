import os
import json
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

class ScenarioKnowledgeBase:
    """
    Advanced knowledge base using structured scenarios for more accurate responses.
    Designed for targeted, scenario-based knowledge retrieval to enable agentic behavior.
    """
    
    def __init__(self, scenarios_path: str = "knowledgebase/scenarios.json"):
        """
        Initialize the scenario-based knowledge base.
        
        Args:
            scenarios_path: Path to the scenarios.json file
        """
        self.scenarios_path = scenarios_path
        self.scenarios = []
        self.scenario_index = {}  # For quick lookup by ID
        self.load_scenarios()
        
    def load_scenarios(self) -> None:
        """Load all scenarios from the scenarios.json file."""
        logger.info("Loading scenario knowledge base...")
        
        if not os.path.exists(self.scenarios_path):
            logger.warning(f"Scenarios file not found: {self.scenarios_path}")
            self.scenarios = []
            return
            
        try:
            with open(self.scenarios_path, 'r', encoding='utf-8') as f:
                self.scenarios = json.load(f)
                
            # Create index for quick lookup
            self.scenario_index = {scenario["scenario_id"]: scenario for scenario in self.scenarios}
            
            # Compile regex patterns
            for scenario in self.scenarios:
                if "question_patterns" in scenario:
                    scenario["compiled_patterns"] = [re.compile(pattern, re.IGNORECASE) 
                                                    for pattern in scenario["question_patterns"]]
                                                    
            logger.info(f"Loaded {len(self.scenarios)} scenarios successfully")
        except Exception as e:
            logger.error(f"Error loading scenarios: {e}")
            self.scenarios = []
            
    def query(self, question: str) -> Tuple[Optional[Dict[str, Any]], float, List[Dict[str, Any]]]:
        """
        Find the most relevant scenario for a given question.
        
        Args:
            question: The user's question
            
        Returns:
            Tuple containing:
            - The best matching scenario (or None if no good match)
            - Confidence score (0-1)
            - List of other potentially relevant scenarios
        """
        question_lower = question.lower()
        best_scenario = None
        best_score = 0
        other_scenarios = []
        
        # 1. First try exact pattern matching (highest confidence)
        for scenario in self.scenarios:
            # Check for regex pattern matches
            if "compiled_patterns" in scenario:
                for pattern in scenario["compiled_patterns"]:
                    if pattern.search(question_lower):
                        logger.info(f"Pattern match found for scenario: {scenario['title']}")
                        return scenario, 1.0, []  # Perfect match
            
            # Check for canonical question matches
            if "canonical_questions" in scenario:
                for canonical_q in scenario["canonical_questions"]:
                    if self._text_similarity(canonical_q.lower(), question_lower) > 0.85:
                        logger.info(f"Canonical question match: {scenario['title']}")
                        return scenario, 0.95, []  # Almost perfect match
        
        # 2. Keyword matching
        keyword_matches = {}
        for scenario in self.scenarios:
            if "keywords" in scenario:
                score = 0
                for keyword in scenario["keywords"]:
                    if keyword.lower() in question_lower:
                        score += 1
                
                if score > 0:
                    keyword_matches[scenario["scenario_id"]] = score
        
        # 3. Semantic similarity for all scenarios
        for scenario in self.scenarios:
            # Start with keyword score if any
            base_score = keyword_matches.get(scenario["scenario_id"], 0) * 0.1
            
            # Add semantic similarity with canonical questions
            if "canonical_questions" in scenario:
                max_similarity = 0
                for canonical_q in scenario["canonical_questions"]:
                    similarity = self._text_similarity(canonical_q.lower(), question_lower)
                    max_similarity = max(max_similarity, similarity)
                
                # Weight the final score (keyword presence + semantic similarity)
                score = base_score + max_similarity * 0.9
                
                if score > best_score:
                    best_score = score
                    best_scenario = scenario
                elif score > 0.3:  # Only include reasonably relevant alternatives
                    other_scenarios.append((scenario, score))
        
        # Sort other scenarios by score and limit to top 3
        other_scenarios.sort(key=lambda x: x[1], reverse=True)
        other_relevant = [s[0] for s in other_scenarios[:3]]
        
        if best_score < 0.4:
            logger.warning(f"No good scenario match for: {question}")
            return None, best_score, other_relevant
            
        logger.info(f"Best scenario match: {best_scenario['title']} (score: {best_score:.2f})")
        return best_scenario, best_score, other_relevant
    
    def get_scenario_by_id(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """Get a scenario by its ID."""
        return self.scenario_index.get(scenario_id)
    
    def get_related_scenarios(self, scenario_id: str) -> List[Dict[str, Any]]:
        """Get all scenarios related to a given scenario."""
        scenario = self.get_scenario_by_id(scenario_id)
        if not scenario or "related_scenarios" not in scenario:
            return []
            
        related = []
        for related_id in scenario["related_scenarios"]:
            related_scenario = self.get_scenario_by_id(related_id)
            if related_scenario:
                related.append(related_scenario)
                
        return related
    
    # In src/scenario_knowledge.py, modify render_scenario_response method:

    def render_scenario_response(self, scenario: Dict[str, Any], variables: Dict[str, str] = None, 
                                question: str = None, is_followup: bool = False) -> str:
        """
        Render a response with more contextual awareness.
        
        Args:
            scenario: The scenario to render
            variables: Dictionary of variables to substitute
            question: Original question for contextual customization
            is_followup: Whether this is a follow-up question
        """
        if not variables:
            variables = {}
            
        # Detect tone and intent from question
        intent = "troubleshooting" if any(word in question.lower() for word in 
                                        ["not able", "can't", "cannot", "problem", "issue", "help"]) else "information"
        
        # Choose appropriate response style
        if is_followup:
            # For follow-up, create a more concise answer focusing on new information
            response = f"Regarding your follow-up about {scenario['title'].lower()}:\n\n"
        elif intent == "troubleshooting":
            # For troubleshooting questions, focus on solutions
            response = f"If you're having trouble with {scenario['title'].lower()}, here's how to resolve it:\n\n"
        else:
            # For regular info questions, use the standard template
            response = scenario["answer_template"]
    
    # Rest of the method remains the same...
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity between two strings."""
        return SequenceMatcher(None, text1, text2).ratio()
    
    def get_all_scenarios(self) -> List[Dict[str, Any]]:
        """Get all scenarios in the knowledge base."""
        return self.scenarios
        
    def save_scenarios(self) -> bool:
        """Save scenarios back to file (useful after updates)."""
        try:
            # Create a clean version without compiled patterns
            clean_scenarios = []
            for scenario in self.scenarios:
                clean_scenario = {k: v for k, v in scenario.items() if k != "compiled_patterns"}
                clean_scenarios.append(clean_scenario)
                
            with open(self.scenarios_path, 'w', encoding='utf-8') as f:
                json.dump(clean_scenarios, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Saved {len(clean_scenarios)} scenarios to {self.scenarios_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving scenarios: {e}")
            return False
    
    def add_scenario(self, scenario: Dict[str, Any]) -> bool:
        """Add a new scenario to the knowledge base."""
        try:
            # Validate required fields
            required_fields = ["scenario_id", "title", "canonical_questions"]
            for field in required_fields:
                if field not in scenario:
                    logger.error(f"Missing required field: {field}")
                    return False
                    
            # Check for duplicate ID
            if scenario["scenario_id"] in self.scenario_index:
                logger.warning(f"Scenario ID already exists: {scenario['scenario_id']}")
                return False
                
            # Add to scenarios list and index
            self.scenarios.append(scenario)
            self.scenario_index[scenario["scenario_id"]] = scenario
            
            # Compile patterns if present
            if "question_patterns" in scenario:
                scenario["compiled_patterns"] = [re.compile(pattern, re.IGNORECASE) 
                                               for pattern in scenario["question_patterns"]]
                                               
            # Save back to file
            return self.save_scenarios()
        except Exception as e:
            logger.error(f"Error adding scenario: {e}")
            return False
    
    def update_scenario(self, scenario_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing scenario."""
        if scenario_id not in self.scenario_index:
            logger.warning(f"Scenario not found: {scenario_id}")
            return False
            
        try:
            scenario = self.scenario_index[scenario_id]
            
            # Update fields
            for key, value in updates.items():
                scenario[key] = value
                
            # Recompile patterns if updated
            if "question_patterns" in updates:
                scenario["compiled_patterns"] = [re.compile(pattern, re.IGNORECASE) 
                                               for pattern in scenario["question_patterns"]]
                                               
            # Save back to file
            return self.save_scenarios()
        except Exception as e:
            logger.error(f"Error updating scenario: {e}")
            return False