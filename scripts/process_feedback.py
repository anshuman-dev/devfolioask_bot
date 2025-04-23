#!/usr/bin/env python3
import os
import sys
import logging
from datetime import datetime
import json

# Add parent directory to path to import src modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.feedback import FeedbackSystem

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    """Process feedback and generate summary report."""
    logger.info("Starting weekly feedback processing")
    
    # Initialize feedback system
    feedback_system = FeedbackSystem()
    
    # Process all feedback
    result = feedback_system.process_scheduled_feedback()
    
    if result["status"] == "success":
        logger.info(f"Successfully processed {result['processed']} of {result['total_files']} feedback items")
        
        # Create summary report
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_feedback": result["total_files"],
            "processed_feedback": result["processed"],
            "status": "success"
        }
        
        # Save report
        report_dir = "reports"
        os.makedirs(report_dir, exist_ok=True)
        
        report_path = os.path.join(report_dir, f"feedback_report_{datetime.now().strftime('%Y%m%d')}.json")
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
            
        logger.info(f"Feedback report saved to {report_path}")
    else:
        logger.error(f"Failed to process feedback: {result['message']}")

if __name__ == "__main__":
    main()
