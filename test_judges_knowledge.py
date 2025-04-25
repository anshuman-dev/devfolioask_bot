#!/usr/bin/env python3
import logging
import sys
from src.knowledge import KnowledgeBase

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def test_judge_queries():
    """Test the knowledge base with various judge invitation queries"""
    kb = KnowledgeBase()
    
    test_questions = [
        "How do I add judges on Devfolio?",
        "How to send invitations to judges on Devfolio?",
        "How will judges receive link to the judging dashboard?",
        "Not able to understand how to invite judges",
        "Hey can you tell me about judges invitation on your platform?"
    ]
    
    print("\nTesting judge invitation queries:")
    for question in test_questions:
        print(f"\nQuery: {question}")
        prefix, context = kb.query(question)
        
        if context:
            print(f"Found {len(context)} relevant items")
            print(f"Top source: {context[0]['source']} (score: {context[0]['relevance']})")
        else:
            print("No relevant information found")

if __name__ == "__main__":
    test_judge_queries()
