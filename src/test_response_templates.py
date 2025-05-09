#!/usr/bin/env python3
import os
import sys
import logging
from src.response_templates import ResponseTemplateEngine
from src.response_validator import ResponseValidator

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def test_response_templates():
    """Test the response template engine."""
    engine = ResponseTemplateEngine()
    validator = ResponseValidator()
    
    # Test data
    scenario_id = "judge_invitation"
    data = {
        "content": "1. Go to the organizer dashboard\n2. Click on the hackathon setup button\n3. Go to \"Speakers and Judges\" tab\n4. Add their profile and email address\n5. Choose the judging mode\n6. Save",
        "topic": "Adding Judges",
        "hackathon_name": "TechFest 2025"
    }
    
    # Test different intents
    intents = ["question", "problem", "followup"]
    
    for intent in intents:
        print(f"\n=== Testing template for '{scenario_id}' with '{intent}' intent ===")
        response = engine.render_full_response(scenario_id, data, intent)
        print(response)
        
        # Validate the response
        is_valid, improved, issues = validator.validate_response(
            response, 
            {"intent": {"type": intent}, "hackathon_context": {"name": "TechFest 2025"}}, 
            {"scenario_id": scenario_id, "title": "Adding Judges"}
        )
        
        print(f"\nValid: {is_valid}")
        if issues:
            print(f"Issues: {issues}")
            print("\nImproved response:")
            print(improved)

if __name__ == "__main__":
    test_response_templates()