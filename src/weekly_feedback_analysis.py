#!/usr/bin/env python3
import os
import sys
import logging
import json
from datetime import datetime
from typing import List, Dict, Any

# Add parent directory to path to import src modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.feedback import FeedbackSystem
from src.openai_eval_system import OpenAIEvalSystem
from src.knowledge import KnowledgeBase

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

class FeedbackAnalyzer:
    """
    Analyzes collected feedback and generates insights for improving the bot.
    """
    
    def __init__(self, feedback_system: FeedbackSystem, 
                 eval_system: OpenAIEvalSystem,
                 knowledge_base: KnowledgeBase,
                 report_dir: str = "reports"):
        """
        Initialize the feedback analyzer.
        
        Args:
            feedback_system: FeedbackSystem instance
            eval_system: OpenAIEvalSystem instance
            knowledge_base: KnowledgeBase instance
            report_dir: Directory to store reports
        """
        self.feedback_system = feedback_system
        self.eval_system = eval_system
        self.knowledge_base = knowledge_base
        self.report_dir = report_dir
        
        # Ensure report directory exists
        os.makedirs(report_dir, exist_ok=True)
    
    def analyze_weekly_feedback(self) -> Dict[str, Any]:
        """
        Analyze feedback collected during the week.
        
        Returns:
            Dictionary with analysis report
        """
        # Process feedback through the feedback system
        logger.info("Processing weekly feedback")
        result = self.feedback_system.process_scheduled_feedback()
        
        if result["status"] != "success":
            logger.error(f"Failed to process feedback: {result.get('message', 'Unknown error')}")
            return {
                "status": "error",
                "error": result.get("message", "Unknown error"),
                "timestamp": datetime.now().isoformat()
            }
        
        # Extract feedback statistics
        stats = result.get("stats", {})
        
        # Analyze feedback by type
        feedback_by_type = stats.get("by_type", {})
        
        # Calculate satisfaction score
        total_feedback = stats.get("total", 0)
        if total_feedback > 0:
            helpful_count = feedback_by_type.get("Helpful", 0)
            satisfaction_score = (helpful_count / total_feedback) * 100
        else:
            satisfaction_score = 0
        
        # Identify top issues
        top_issues = []
        for update in stats.get("knowledge_updates", []):
            if "feedback_type" in update and update["feedback_type"] in ["Not Helpful", "Incorrect", "Confusing"]:
                top_issues.append(update)
        
        # Generate analysis report
        report = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "period": {
                "start": (datetime.now().replace(hour=0, minute=0, second=0) - 
                         datetime.timedelta(days=7)).isoformat(),
                "end": datetime.now().isoformat()
            },
            "statistics": {
                "total_feedback": total_feedback,
                "by_type": feedback_by_type,
                "satisfaction_score": satisfaction_score
            },
            "insights": {
                "top_issues": top_issues[:5],  # Top 5 issues
                "recommendations": self._generate_recommendations(stats)
            }
        }
        
        # Save report
        self._save_report(report)
        
        return report
    
    def _generate_recommendations(self, stats: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate recommendations based on feedback analysis.
        
        Args:
            stats: Feedback statistics
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Extract knowledge updates from the stats
        updates = stats.get("knowledge_updates", [])
        
        # Group updates by feedback type
        updates_by_type = {}
        for update in updates:
            feedback_type = update.get("feedback_type", "General Feedback")
            if feedback_type not in updates_by_type:
                updates_by_type[feedback_type] = []
            updates_by_type[feedback_type].append(update)
        
        # Generate recommendations for each feedback type
        if "Not Helpful" in updates_by_type and len(updates_by_type["Not Helpful"]) > 0:
            recommendations.append({
                "type": "Improve Response Completeness",
                "description": "Several responses were marked as not helpful. Consider enhancing responses with more specific details and actionable steps.",
                "count": len(updates_by_type["Not Helpful"])
            })
        
        if "Incorrect" in updates_by_type and len(updates_by_type["Incorrect"]) > 0:
            recommendations.append({
                "type": "Address Factual Errors",
                "description": "Some responses contained incorrect information. Review and update the knowledge base with accurate information.",
                "count": len(updates_by_type["Incorrect"])
            })
        
        if "Confusing" in updates_by_type and len(updates_by_type["Confusing"]) > 0:
            recommendations.append({
                "type": "Improve Clarity",
                "description": "Responses marked as confusing need clearer structure and simpler language. Consider revising templates.",
                "count": len(updates_by_type["Confusing"])
            })
        
        # Add general recommendation if very few positive feedback
        if "Helpful" not in updates_by_type or len(updates_by_type.get("Helpful", [])) < len(updates) * 0.3:
            recommendations.append({
                "type": "General Quality Improvement",
                "description": "Overall feedback is trending negative. Consider a comprehensive review of response templates and knowledge base quality.",
                "count": len(updates)
            })
        
        return recommendations
    
    def _save_report(self, report: Dict[str, Any]) -> bool:
        """
        Save the analysis report to a file.
        
        Args:
            report: Report data to save
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"feedback_analysis_{timestamp}.json"
            filepath = os.path.join(self.report_dir, filename)
            
            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)
                
            logger.info(f"Analysis report saved to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving analysis report: {e}")
            return False
    
    def run_performance_eval(self) -> Dict[str, Any]:
        """
        Run OpenAI evals on recent interactions to assess bot performance.
        
        Returns:
            Dictionary with eval results
        """
        try:
            logger.info("Running performance evaluation")
            
            # Get recent interactions for evaluation
            all_interactions = []
            for int_id, data in self.feedback_system.recent_interactions.items():
                all_interactions.append({
                    "id": int_id,
                    "question": data["question"],
                    "answer": data["answer"],
                    "timestamp": data["timestamp"],
                    "user_id": data["user_id"]
                })
            
            # Sort by timestamp (newest first) and take the most recent 20
            all_interactions.sort(key=lambda x: x["timestamp"], reverse=True)
            recent_interactions = all_interactions[:20]
            
            if not recent_interactions:
                logger.warning("No recent interactions found for evaluation")
                return {
                    "status": "error",
                    "error": "No recent interactions found for evaluation"
                }
            
            # Prepare eval data
            eval_data = []
            for interaction in recent_interactions:
                eval_data.append({
                    "question": interaction["question"],
                    "answer": interaction["answer"],
                    "correct_answer": ""  # We don't have ground truth here
                })
            
            # Run helpfulness evaluation
            helpfulness_result = self.eval_system.evaluate_responses(
                eval_data,
                "helpfulness_eval",
                "gpt-4"
            )
            
            # Run clarity evaluation
            clarity_result = self.eval_system.evaluate_responses(
                eval_data,
                "clarity_eval",
                "gpt-4"
            )
            
            # Combine results
            combined_result = {
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "sample_size": len(eval_data),
                "helpfulness": {
                    "pass_rate": helpfulness_result.get("pass_rate", 0),
                    "passed_items": helpfulness_result.get("passed_items", 0),
                    "failed_items": helpfulness_result.get("failed_items", 0)
                },
                "clarity": {
                    "pass_rate": clarity_result.get("pass_rate", 0),
                    "passed_items": clarity_result.get("passed_items", 0),
                    "failed_items": clarity_result.get("failed_items", 0)
                },
                "overall_score": (helpfulness_result.get("pass_rate", 0) + 
                                  clarity_result.get("pass_rate", 0)) / 2
            }
            
            # Save eval results
            self._save_eval_results(combined_result)
            
            return combined_result
            
        except Exception as e:
            logger.error(f"Error running performance evaluation: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _save_eval_results(self, results: Dict[str, Any]) -> bool:
        """
        Save evaluation results to a file.
        
        Args:
            results: Evaluation results to save
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_eval_{timestamp}.json"
            filepath = os.path.join(self.report_dir, filename)
            
            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2)
                
            logger.info(f"Evaluation results saved to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving evaluation results: {e}")
            return False

def main():
    """Main function to run weekly feedback analysis."""
    logger.info("Starting weekly feedback analysis")
    
    # Initialize components
    feedback_system = FeedbackSystem()
    eval_system = OpenAIEvalSystem()
    knowledge_base = KnowledgeBase()
    
    # Initialize analyzer
    analyzer = FeedbackAnalyzer(feedback_system, eval_system, knowledge_base)
    
    # Analyze feedback
    analysis_report = analyzer.analyze_weekly_feedback()
    
    # Print summary
    if analysis_report["status"] == "success":
        stats = analysis_report["statistics"]
        logger.info(f"Analyzed {stats['total_feedback']} feedback items")
        logger.info(f"Satisfaction score: {stats['satisfaction_score']:.1f}%")
        
        # Print recommendations
        recommendations = analysis_report["insights"]["recommendations"]
        if recommendations:
            logger.info("Recommendations:")
            for i, rec in enumerate(recommendations, 1):
                logger.info(f"{i}. {rec['type']}: {rec['description']}")
    else:
        logger.error(f"Analysis failed: {analysis_report.get('error', 'Unknown error')}")
    
    # Run performance evaluation
    logger.info("Running performance evaluation")
    eval_results = analyzer.run_performance_eval()
    
    if eval_results["status"] == "success":
        logger.info(f"Evaluation completed on {eval_results['sample_size']} interactions")
        logger.info(f"Overall performance score: {eval_results['overall_score']:.1f}%")
        logger.info(f"Helpfulness score: {eval_results['helpfulness']['pass_rate']:.1f}%")
        logger.info(f"Clarity score: {eval_results['clarity']['pass_rate']:.1f}%")
    else:
        logger.error(f"Evaluation failed: {eval_results.get('error', 'Unknown error')}")

if __name__ == "__main__":
    main()