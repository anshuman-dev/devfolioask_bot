import os
import json
import logging
import re
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class ResponseTemplateEngine:
    """
    Manages response templates for different scenarios and intents.
    Provides template rendering with variable substitution.
    """
    
    def __init__(self, templates_dir: str = "templates"):
        """
        Initialize the template engine.
        
        Args:
            templates_dir: Directory containing template files
        """
        self.templates_dir = templates_dir
        self.templates = {}
        self.default_templates = {}
        
        # Create templates directory if it doesn't exist
        os.makedirs(templates_dir, exist_ok=True)
        
        # Load templates
        self.load_templates()
        
    def load_templates(self) -> None:
        """Load all template files from the templates directory."""
        logger.info(f"Loading response templates from {self.templates_dir}")
        
        # Load scenario-specific templates
        scenario_template_path = os.path.join(self.templates_dir, "scenario_templates.json")
        if os.path.exists(scenario_template_path):
            try:
                with open(scenario_template_path, 'r', encoding='utf-8') as f:
                    self.templates = json.load(f)
                logger.info(f"Loaded {len(self.templates)} scenario templates")
            except Exception as e:
                logger.error(f"Error loading scenario templates: {e}")
                self.templates = {}
        
        # Load default templates
        default_template_path = os.path.join(self.templates_dir, "default_templates.json")
        if os.path.exists(default_template_path):
            try:
                with open(default_template_path, 'r', encoding='utf-8') as f:
                    self.default_templates = json.load(f)
                logger.info(f"Loaded default templates")
            except Exception as e:
                logger.error(f"Error loading default templates: {e}")
                
        # If no templates found, initialize with built-in defaults
        if not self.templates and not self.default_templates:
            logger.warning("No templates found. Using built-in defaults.")
            self.initialize_default_templates()
    
    def initialize_default_templates(self) -> None:
        """Initialize with built-in default templates."""
        # Default scenario templates for key scenarios
        self.templates = {
            "judging_criteria": {
                "question": {
                    "greeting": "Here's what you need to know about judging criteria on Devfolio:",
                    "body": "{content}",
                    "conclusion": "If you have more questions about judging on Devfolio, feel free to ask!"
                },
                "problem": {
                    "greeting": "I understand you're having an issue with judging criteria. Here's how to resolve it:",
                    "body": "{content}",
                    "conclusion": "If you continue to experience issues, please contact @singhanshuman8 on Telegram."
                }
            },
            "judge_invitation": {
                "question": {
                    "greeting": "Here's how to add judges to your hackathon on Devfolio:",
                    "body": "{content}",
                    "conclusion": "Once their profile is added with the email address, the judging invite is sent automatically."
                },
                "problem": {
                    "greeting": "If you're having trouble inviting judges, follow these steps carefully:",
                    "body": "{content}",
                    "conclusion": "If judges haven't received an invitation, verify that you've entered the correct email address. They should check both their inbox and spam folders."
                }
            }
        }
        
        # Default templates for when no scenario-specific template exists
        self.default_templates = {
            "question": {
                "greeting": "Here's the information you requested about {topic}:",
                "body": "{content}",
                "conclusion": "I hope that helps! Let me know if you have any other questions."
            },
            "problem": {
                "greeting": "I understand you're having an issue with {topic}. Here's how to resolve it:",
                "body": "{content}",
                "conclusion": "If you're still experiencing problems, please let me know."
            },
            "followup": {
                "greeting": "Regarding your follow-up about {topic}:",
                "body": "{content}",
                "conclusion": "Does that clarify things for you?"
            },
            "generic": {
                "greeting": "Here's what I found about {topic}:",
                "body": "{content}",
                "conclusion": "I hope this information helps!"
            }
        }
        
        # Save these default templates to disk
        self.save_templates()
    
    def save_templates(self) -> bool:
        """Save templates to disk."""
        try:
            # Save scenario templates
            scenario_template_path = os.path.join(self.templates_dir, "scenario_templates.json")
            with open(scenario_template_path, 'w', encoding='utf-8') as f:
                json.dump(self.templates, f, indent=2)
                
            # Save default templates
            default_template_path = os.path.join(self.templates_dir, "default_templates.json")
            with open(default_template_path, 'w', encoding='utf-8') as f:
                json.dump(self.default_templates, f, indent=2)
                
            logger.info("Templates saved to disk")
            return True
        except Exception as e:
            logger.error(f"Error saving templates: {e}")
            return False
    
    def get_template_for_scenario(self, scenario_id: str, intent: str) -> Dict[str, str]:
        """
        Get the appropriate template for a scenario and intent.
        
        Args:
            scenario_id: ID of the scenario
            intent: Intent type (question, problem, followup, etc.)
            
        Returns:
            Template dictionary with greeting, body, and conclusion
        """
        # Check if we have a template for this scenario
        scenario_templates = self.templates.get(scenario_id, {})
        
        # If we have a template for the specific intent, use it
        if intent in scenario_templates:
            return scenario_templates[intent]
            
        # If we have a generic template for this scenario, use it
        if "generic" in scenario_templates:
            return scenario_templates["generic"]
            
        # Fall back to default templates
        if intent in self.default_templates:
            return self.default_templates[intent]
            
        # Last resort, use the generic default template
        return self.default_templates.get("generic", {
            "greeting": "Here's some information that might help:",
            "body": "{content}",
            "conclusion": "I hope this helps!"
        })
    
    def render_template(self, template_name: str, scenario_id: str, 
                       data: Dict[str, Any], intent: str = "question") -> str:
        """
        Render a template with the provided data.
        
        Args:
            template_name: Name of the template to render
            scenario_id: ID of the scenario
            data: Data to substitute into the template
            intent: Intent type
            
        Returns:
            Rendered template string
        """
        # Get the appropriate template
        template = self.get_template_for_scenario(scenario_id, intent)
        
        # If template_name is not in the template, use a default approach
        if template_name not in template:
            if template_name == "full":
                # Combine all sections for a full response
                result = []
                if "greeting" in template:
                    result.append(self._substitute_variables(template["greeting"], data))
                if "body" in template:
                    result.append(self._substitute_variables(template["body"], data))
                if "conclusion" in template:
                    result.append(self._substitute_variables(template["conclusion"], data))
                return "\n\n".join(result)
            else:
                logger.warning(f"Template section '{template_name}' not found for scenario '{scenario_id}' and intent '{intent}'")
                # Return an empty string if the section doesn't exist
                return ""
        
        # Get the template section
        template_section = template[template_name]
        
        # Substitute variables
        return self._substitute_variables(template_section, data)
    
    def _substitute_variables(self, template_text: str, data: Dict[str, Any]) -> str:
        """
        Substitute variables in a template string.
        
        Args:
            template_text: Template text with {variable} placeholders
            data: Dictionary of variables to substitute
            
        Returns:
            Template with variables substituted
        """
        # Make a copy of the template text
        result = template_text
        
        # Substitute each variable
        for key, value in data.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, str(value))
            
        return result
    
    def render_full_response(self, scenario_id: str, data: Dict[str, Any], 
                            intent: str = "question") -> str:
        """
        Render a full response (greeting, body, conclusion) for a scenario.
        
        Args:
            scenario_id: ID of the scenario
            data: Data to substitute into the template
            intent: Intent type
            
        Returns:
            Full rendered response
        """
        return self.render_template("full", scenario_id, data, intent)