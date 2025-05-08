#!/usr/bin/env python3
import os
import sys
import json
import logging
import re
from typing import List, Dict, Any

# Add parent directory to path to import src modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.knowledge import KnowledgeBase
from src.scenario_knowledge import ScenarioKnowledgeBase

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def extract_keywords(text: str) -> List[str]:
    """Extract important keywords from text."""
    # Convert to lowercase and split
    words = re.findall(r'\w+', text.lower())
    
    # Common words to ignore
    stop_words = {
        "a", "an", "the", "and", "or", "but", "if", "because", "as", "what",
        "how", "when", "where", "who", "will", "is", "are", "am", "i", "to",
        "in", "on", "at", "by", "for", "with", "about", "do", "does", "did",
        "should", "can", "could", "would", "might", "may", "there", "these",
        "those", "this", "that", "then", "than", "such", "so", "some", "my",
        "your", "our", "their", "able", "understand", "tell", "me", "please", "help"
    }
    
    # Filter out stop words and short words
    keywords = [word for word in words if word not in stop_words and len(word) > 3]
    
    # Limit to top 10 most relevant keywords
    return keywords[:10]

def convert_content_to_scenario(title: str, content: str, source: str, index: int) -> Dict[str, Any]:
    """Convert a single content item to a scenario."""
    # Create a unique ID based on title
    scenario_id = f"scenario_{index:03d}_{re.sub(r'[^a-z0-9]', '_', title.lower())}"
    
    # Extract keywords
    keywords = extract_keywords(content)
    
    # Create basic canonical questions based on title
    canonical_questions = [
        f"How do I {title.lower()}?",
        f"What is {title.lower()}?",
        f"Tell me about {title.lower()}"
    ]
    
    # Create basic regex patterns
    question_patterns = [
        f".*{re.escape(title.lower())}.*",
        f".*how.*{re.escape(title.lower())}.*"
    ]
    
    # Split content into paragraphs
    paragraphs = content.split('\n\n')
    
    # Extract potential steps
    steps = []
    notes = ""
    common_issues = ""
    
    # Very basic step extraction
    for para in paragraphs:
        if re.match(r'^\d+\.', para):
            # Numbered step
            steps.append(re.sub(r'^\d+\.\s*', '', para))
        elif para.lower().startswith('note:') or para.lower().startswith('important:'):
            notes += para + "\n\n"
        elif any(term in para.lower() for term in ['issue', 'problem', 'error', 'trouble', 'fix']):
            common_issues += para + "\n\n"
    
    # Create a basic answer template
    answer_template = f"Here's how to {title.lower()}:\n\n{{steps}}\n\n{{notes}}\n\n{{common_issues}}"
    
    # Create scenario structure
    scenario = {
        "scenario_id": scenario_id,
        "title": title,
        "canonical_questions": canonical_questions,
        "question_patterns": question_patterns,
        "keywords": keywords,
        "answer_template": answer_template,
        "answer_components": {
            "steps": steps,
            "notes": notes.strip(),
            "common_issues": common_issues.strip()
        },
        "source": source,
        "related_scenarios": []
    }
    
    return scenario

def main():
    """Migrate existing knowledge base to scenarios."""
    logger.info("Starting migration to scenario-based knowledge")
    
    # Initialize knowledge bases
    kb = KnowledgeBase()
    scenarios_path = os.path.join("knowledgebase", "scenarios.json")
    
    # List to store all scenarios
    scenarios = []
    
    # Process GitBook data
    logger.info("Processing GitBook data...")
    for filename, content in kb.gitbook_data.items():
        if isinstance(content, dict) and "title" in content and "content" in content:
            title = content["title"]
            content_text = content["content"]
            logger.info(f"Converting: {title}")
            
            scenario = convert_content_to_scenario(title, content_text, f"GitBook: {filename}", len(scenarios) + 1)
            scenarios.append(scenario)
    
    # Process organizer data
    logger.info("Processing organizer data...")
    for filename, content in kb.organizer_data.items():
        if isinstance(content, dict) and "title" in content and "content" in content:
            title = content["title"]
            content_text = content["content"]
        else:
            # Use filename as title for plain text
            title = os.path.splitext(filename)[0].replace("_", " ").title()
            content_text = str(content)
            
        logger.info(f"Converting: {title}")
        scenario = convert_content_to_scenario(title, content_text, f"Organizer: {filename}", len(scenarios) + 1)
        scenarios.append(scenario)
    
    # Find potential relationships between scenarios
    logger.info("Finding relationships between scenarios...")
    for i, scenario in enumerate(scenarios):
        for j, other in enumerate(scenarios):
            if i != j:
                # Check for keyword overlap
                common_keywords = set(scenario["keywords"]) & set(other["keywords"])
                if len(common_keywords) >= 2:
                    scenario["related_scenarios"].append(other["scenario_id"])
                    
                # Limit related scenarios to 3
                if len(scenario["related_scenarios"]) >= 3:
                    break
    
    # Save scenarios to file
    os.makedirs(os.path.dirname(scenarios_path), exist_ok=True)
    with open(scenarios_path, 'w', encoding='utf-8') as f:
        json.dump(scenarios, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Migration complete. {len(scenarios)} scenarios created and saved to {scenarios_path}")
    
    # Manually create special scenarios for the known issues
    create_special_scenarios()

def create_special_scenarios():
    """Create special scenarios for known important topics."""
    logger.info("Creating special scenarios for important topics...")
    
    # Judging criteria scenario
    judging_criteria = {
        "scenario_id": "judging_criteria",
        "title": "Judging Criteria",
        "canonical_questions": [
            "How do I modify judging criteria?",
            "Can I change the judging criteria?",
            "What are the judging criteria?",
            "How to customize judging criteria?"
        ],
        "question_patterns": [
            ".*judging criteria.*",
            ".*criteria.*judg.*",
            ".*customize.*criteria.*",
            ".*modify.*criteria.*",
            ".*change.*criteria.*"
        ],
        "keywords": ["judging", "criteria", "points", "scoring", "evaluation", "customize"],
        "answer_template": """Devfolio has 5 fixed judging criteria that cannot be modified within the platform:

{steps}

{notes}

If you need custom criteria, please contact @singhanshuman8 and @AniketRaj314 on Telegram.""",
        "answer_components": {
            "steps": [
                "Technicality - Technical complexity and innovation",
                "Originality - Uniqueness and creativity of the idea",
                "Practicality - Real-world applicability and usefulness",
                "Aesthetics - User interface design and user experience",
                "Wow Factor - Overall impression and exceptional qualities"
            ],
            "notes": "These criteria are fixed and each is scored out of 10 points for a total of 50 points maximum.",
            "common_issues": "If you need custom criteria for your hackathon, this requires special configuration that cannot be done directly in the platform."
        },
        "source": "Special: Manual Entry",
        "related_scenarios": ["judge_invitation", "judging_modes"]
    }
    
    # Judge invitation scenario
    judge_invitation = {
        "scenario_id": "judge_invitation",
        "title": "Adding Judges",
        "canonical_questions": [
            "How do I add judges?",
            "How to invite judges?",
            "How to add judges to the platform?",
            "Judge invitation process",
            "How will judges receive the judging link?"
        ],
        "question_patterns": [
            ".*add.*judge.*",
            ".*invite.*judge.*",
            ".*judge.*invitation.*",
            ".*how.*judge.*receive.*link.*",
            ".*not able.*invite.*judge.*"
        ],
        "keywords": ["judge", "invitation", "add", "invite", "profile", "email", "dashboard"],
        "answer_template": """To add judges to your hackathon on Devfolio, follow these steps:

{steps}

{notes}

{common_issues}""",
        "answer_components": {
            "steps": [
                "Go to the organizer dashboard",
                "Click on the hackathon setup button",
                "Go to \"Speakers and Judges\" tab",
                "Add their profile and email address under the required text field",
                "Make sure you are choosing the right mode of judging - Main for Online or Offline judging and Sponsor for sponsor judging",
                "Save"
            ],
            "notes": "Once their profile is added with the email address, the judging invite is sent automatically.",
            "common_issues": "If judges haven't received an invitation, verify that you've entered the correct email address. They should check both their inbox and spam folders."
        },
        "source": "Special: Manual Entry",
        "related_scenarios": ["judging_criteria", "judging_modes"]
    }
    
    # Judging modes scenario
    judging_modes = {
        "scenario_id": "judging_modes",
        "title": "Judging Modes",
        "canonical_questions": [
            "What are the judging modes?",
            "What is the difference between online and offline judging?",
            "How does sponsor judging work?",
            "Which judging mode should I use?"
        ],
        "question_patterns": [
            ".*judging mode.*",
            ".*online.*judging.*",
            ".*offline.*judging.*",
            ".*sponsor.*judging.*",
            ".*which mode.*judging.*"
        ],
        "keywords": ["judging", "mode", "online", "offline", "sponsor", "difference"],
        "answer_template": """Devfolio supports three different judging modes:

{steps}

{notes}

{common_issues}""",
        "answer_components": {
            "steps": [
                "Online Judging - Judges can evaluate submissions remotely through the Devfolio platform",
                "Offline Judging - For in-person events where judges evaluate projects at the venue",
                "Sponsor Judging - Special mode for sponsor representatives to judge projects for their sponsor prizes"
            ],
            "notes": "You can choose the appropriate judging mode when adding judges in the Speakers and Judges tab.",
            "common_issues": "Make sure you select the correct mode for each judge, as this affects how they access the judging dashboard and what they can evaluate."
        },
        "source": "Special: Manual Entry",
        "related_scenarios": ["judging_criteria", "judge_invitation"]
    }
    
    # Save these special scenarios
    special_scenarios = [judging_criteria, judge_invitation, judging_modes]
    scenarios_path = os.path.join("knowledgebase", "special_scenarios.json")
    
    with open(scenarios_path, 'w', encoding='utf-8') as f:
        json.dump(special_scenarios, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Created {len(special_scenarios)} special scenarios for key topics")

if __name__ == "__main__":
    main()