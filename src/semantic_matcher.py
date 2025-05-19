import logging
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from sentence_transformers import SentenceTransformer

# Fix the import - use hf_hub_download instead of cached_download
#from huggingface_hub import HfApi, HfFolder, Repository, hf_hub_url, hf_hub_download as cached_download
from huggingface_hub import HfApi, HfFolder, Repository, hf_hub_url
from huggingface_shim import cached_download

logger = logging.getLogger(__name__)

class SemanticMatcher:
    """
    Uses sentence transformers to match queries to relevant scenarios 
    based on semantic similarity.
    """
    
    def __init__(self, scenarios: List[Dict[str, Any]], 
                model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the semantic matcher with scenarios and model.
        
        Args:
            scenarios: List of scenario dictionaries with canonical questions
            model_name: Name of the sentence transformer model to use
        """
        logger.info(f"Initializing SemanticMatcher with sentence-transformers...")
        self.model = SentenceTransformer(model_name)
        self.scenarios = scenarios
        
        # Extract canonical questions from scenarios
        self.canonical_questions = []
        self.scenario_map = {}
        
        for scenario in scenarios:
            if "canonical_questions" in scenario:
                for question in scenario["canonical_questions"]:
                    self.canonical_questions.append(question)
                    self.scenario_map[question] = scenario
        
        logger.info(f"Computing embeddings for {len(self.canonical_questions)} canonical questions")
        # Compute embeddings for canonical questions
        if self.canonical_questions:
            self.question_embeddings = self.model.encode(
                self.canonical_questions, 
                show_progress_bar=True,
                convert_to_tensor=True
            )
        else:
            logger.warning("No canonical questions found in scenarios")
            # Initialize with empty tensor
            self.question_embeddings = np.array([])
            
        logger.info("Loaded sentence-transformer model successfully")
    
    def find_matching_scenarios(self, query: str, top_k: int = 3, 
                              threshold: float = 0.5) -> List[Tuple[Dict[str, Any], float]]:
        """
        Find matching scenarios for a query based on semantic similarity.
        
        Args:
            query: User's query text
            top_k: Number of top matching scenarios to return
            threshold: Minimum similarity score to include a scenario
            
        Returns:
            List of tuples containing (scenario, similarity_score)
        """
        if not self.canonical_questions:
            logger.warning("No canonical questions available for matching")
            return []
            
        # Encode the query
        query_embedding = self.model.encode(query, convert_to_tensor=True)
        
        # Compute cosine similarities
        similarities = []
        for i, question in enumerate(self.canonical_questions):
            # Get embedding for the canonical question
            question_embedding = self.question_embeddings[i]
            
            # Compute cosine similarity
            similarity = self._cosine_similarity(query_embedding, question_embedding)
            similarities.append((question, similarity))
        
        # Sort by similarity score (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Get top-k matches above threshold
        top_matches = []
        seen_scenarios = set()
        
        for question, score in similarities[:top_k * 2]:  # Get more to filter duplicates
            if score < threshold:
                continue
                
            scenario = self.scenario_map[question]
            scenario_id = scenario.get("scenario_id")
            
            # Skip duplicates
            if scenario_id in seen_scenarios:
                continue
                
            seen_scenarios.add(scenario_id)
            top_matches.append((scenario, score))
            
            if len(top_matches) >= top_k:
                break
                
        return top_matches
    
    def _cosine_similarity(self, a, b):
        """
        Compute cosine similarity between two vectors.
        
        Args:
            a: First vector
            b: Second vector
            
        Returns:
            Cosine similarity score
        """
        # Convert to numpy arrays if they're not already
        if hasattr(a, 'cpu') and callable(a.cpu):
            a = a.cpu().numpy()
        if hasattr(b, 'cpu') and callable(b.cpu):
            b = b.cpu().numpy()
            
        # Ensure we have numpy arrays
        a = np.array(a)
        b = np.array(b)
        
        # Compute cosine similarity
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))