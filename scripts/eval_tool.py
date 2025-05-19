#!/usr/bin/env python

import os
import argparse
import logging
import json
import tabulate
import time
from datetime import datetime
from typing import List, Dict, Any

from src.enhanced_openai_eval_system import EnhancedOpenAIEvalSystem
from src.feedback import FeedbackSystem
from src.knowledge import KnowledgeBase

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def list_evaluations(eval_system: EnhancedOpenAIEvalSystem, args):
    """List all evaluations with their status."""
    try:
        # Get all evaluation files
        evaluations = []
        for filename in os.listdir(eval_system.evaluations_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(eval_system.evaluations_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    eval_data = json.load(f)
                    
                    # Format for display
                    question = eval_data.get("question", "")
                    if len(question) > 50:
                        question = question[:47] + "..."
                        
                    timestamp = eval_data.get("timestamp", 0)
                    date_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                    
                    has_improvement = "Yes" if "improved_response" in eval_data else "No"
                    
                    evaluations.append([
                        filename,
                        question,
                        eval_data.get("status", "unknown"),
                        date_str,
                        has_improvement
                    ])
        
        # Sort by timestamp (newest first)
        evaluations.sort(key=lambda x: x[3], reverse=True)
        
        # Display as table
        if evaluations:
            headers = ["Filename", "Question", "Status", "Date", "Has Improvement"]
            print(tabulate.tabulate(evaluations, headers=headers, tablefmt="grid"))
        else:
            print("No evaluations found.")
            
    except Exception as e:
        logger.error(f"Error listing evaluations: {e}")
        print(f"Error: {e}")

def process_evaluations(eval_system: EnhancedOpenAIEvalSystem, args):
    """Process pending evaluations."""
    try:
        print("Processing pending evaluations...")
        result = eval_system.process_pending_evaluations()
        
        if result.get("status") == "success":
            stats = result.get("stats", {})
            print(f"Total evaluations: {stats.get('total', 0)}")
            print(f"Processed: {stats.get('processed', 0)}")
            print(f"Still pending: {stats.get('pending', 0)}")
            print(f"Failed: {stats.get('failed', 0)}")
            print(f"Improved responses: {stats.get('improved_responses', 0)}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Error processing evaluations: {e}")
        print(f"Error: {e}")

def show_improvements(eval_system: EnhancedOpenAIEvalSystem, args):
    """Show all improvements generated from evaluations."""
    try:
        improvements = eval_system.get_improvements(limit=args.limit)
        
        if not improvements:
            print("No improvements found.")
            return
            
        print(f"Found {len(improvements)} improvements:\n")
        
        for i, imp in enumerate(improvements, 1):
            question = imp.get("question", "")
            original = imp.get("original_response", "")
            improved = imp.get("improved_response", "")
            
            timestamp = imp.get("timestamp", 0)
            date_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            
            # Format the output
            print(f"=== Improvement {i} - {date_str} ===")
            print(f"Question: {question}")
            print("\nOriginal Response:")
            print("-" * 50)
            print(original)
            print("\nImproved Response:")
            print("-" * 50)
            print(improved)
            
            # Show feedback if available and not too verbose
            if not args.no_feedback and "feedback" in imp and imp["feedback"]:
                print("\nFeedback:")
                print("-" * 50)
                
                feedback = imp["feedback"]
                if isinstance(feedback, list) and len(feedback) > 0:
                    first_feedback = feedback[0]
                    
                    # Format the feedback
                    if "overall_rating" in first_feedback:
                        print(f"Overall Rating: {first_feedback.get('overall_rating')}/5")
                        
                    if "strengths" in first_feedback:
                        print("\nStrengths:")
                        for strength in first_feedback.get("strengths", []):
                            print(f"- {strength}")
                            
                    if "weaknesses" in first_feedback:
                        print("\nWeaknesses:")
                        for weakness in first_feedback.get("weaknesses", []):
                            print(f"- {weakness}")
                            
                    if "explanation" in first_feedback:
                        print("\nExplanation:")
                        print(first_feedback.get("explanation"))
            
            print("\n" + "=" * 70 + "\n")
            
    except Exception as e:
        logger.error(f"Error showing improvements: {e}")
        print(f"Error: {e}")

def show_detail(eval_system: EnhancedOpenAIEvalSystem, args):
    """Show detailed information for a specific evaluation."""
    try:
        # Check if file exists
        filepath = os.path.join(eval_system.evaluations_dir, args.filename)
        if not os.path.exists(filepath):
            print(f"Evaluation file not found: {args.filename}")
            return
            
        # Load the evaluation data
        with open(filepath, 'r', encoding='utf-8') as f:
            eval_data = json.load(f)
            
        # Format the output
        timestamp = eval_data.get("timestamp", 0)
        date_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"=== Evaluation Detail - {date_str} ===")
        print(f"Status: {eval_data.get('status', 'unknown')}")
        print(f"Question: {eval_data.get('question', '')}")
        
        print("\nOriginal Response:")
        print("-" * 50)
        print(eval_data.get("answer", ""))
        
        if "improved_response" in eval_data:
            print("\nImproved Response:")
            print("-" * 50)
            print(eval_data.get("improved_response", ""))
            
        # Show feedback if available
        if "feedback" in eval_data and eval_data["feedback"]:
            print("\nFeedback:")
            print("-" * 50)
            
            feedback = eval_data["feedback"]
            if isinstance(feedback, list) and len(feedback) > 0:
                first_feedback = feedback[0]
                
                # Format the feedback
                if "overall_rating" in first_feedback:
                    print(f"Overall Rating: {first_feedback.get('overall_rating')}/5")
                    
                if "strengths" in first_feedback:
                    print("\nStrengths:")
                    for strength in first_feedback.get("strengths", []):
                        print(f"- {strength}")
                        
                if "weaknesses" in first_feedback:
                    print("\nWeaknesses:")
                    for weakness in first_feedback.get("weaknesses", []):
                        print(f"- {weakness}")
                        
                if "explanation" in first_feedback:
                    print("\nExplanation:")
                    print(first_feedback.get("explanation"))
                
                # Raw feedback if available and requested
                if args.raw and "raw_feedback" in first_feedback:
                    print("\nRaw Feedback:")
                    print(first_feedback.get("raw_feedback"))
            
    except Exception as e:
        logger.error(f"Error showing evaluation detail: {e}")
        print(f"Error: {e}")

def main():
    """Main function to run the enhanced evaluation tool."""
    parser = argparse.ArgumentParser(description="Enhanced OpenAI Evaluation Tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # List evaluations command
    list_parser = subparsers.add_parser("list", help="List all evaluations")
    
    # Process pending evaluations command
    process_parser = subparsers.add_parser("process", help="Process pending evaluations")
    
    # Show improvements command
    improvements_parser = subparsers.add_parser("improvements", help="Show improvements from evaluations")
    improvements_parser.add_argument("--limit", type=int, default=10, help="Maximum number of improvements to show")
    improvements_parser.add_argument("--no-feedback", action="store_true", help="Don't show feedback details")
    
    # Show detail command
    detail_parser = subparsers.add_parser("detail", help="Show detail for a specific evaluation")
    detail_parser.add_argument("filename", help="Filename of the evaluation to show")
    detail_parser.add_argument("--raw", action="store_true", help="Show raw feedback")
    
    args = parser.parse_args()
    
    # Initialize systems
    feedback_system = FeedbackSystem()
    knowledge_base = KnowledgeBase()
    eval_system = EnhancedOpenAIEvalSystem(
        feedback_system=feedback_system,
        knowledge_base=knowledge_base
    )
    
    # Execute command
    if args.command == "list":
        list_evaluations(eval_system, args)
    elif args.command == "process":
        process_evaluations(eval_system, args)
    elif args.command == "improvements":
        show_improvements(eval_system, args)
    elif args.command == "detail":
        show_detail(eval_system, args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()