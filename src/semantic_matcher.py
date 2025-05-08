import numpy as np
import logging
from typing import List, Dict, Any, Tuple
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class SemanticMatcher:
    """
    Uses sentence embeddings to match queries to scenarios semantically.
    This enables more natural language understanding beyond keyword matching.
    """
    
    def __init__(self, scenarios_data: List[Dict[str, Any]]):
        """
        Initialize the semantic matcher with scenario data.
        
        Args:
            scenarios_data: List of scenario dictionaries
        """
        logger.info("Initializing SemanticMatcher with sentence-transformers...")
        try:
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Loaded sentence-transformer model successfully")
        except Exception as e:
            logger.error(f"Error loading sentence-transformer model: {e}")
            logger.warning("Falling back to simpler matching methods")
            self.model = None
            
        self.scenarios = scenarios_data
        self.scenario_embeddings = None
        self.canonical_questions = []
        self.scenario_mapping = {}  # Maps embedding index to scenario
        
        if self.model:
            self.scenario_embeddings = self._compute_embeddings()
    
    def _compute_embeddings(self) -> np.ndarray:
        """
        Compute embeddings for all canonical questions in the scenarios.
        
        Returns:
            Numpy array of embeddings
        """
        all_questions = []
        self.canonical_questions = []
        self.scenario_mapping = {}
        
        # Collect all canonical questions from scenarios
        embedding_idx = 0
        for scenario_idx, scenario in enumerate(self.scenarios):
            if "canonical_questions" in scenario:
                for question in scenario["canonical_questions"]:
                    all_questions.append(question)
                    self.canonical_questions.append(question)
                    self.scenario_mapping[embedding_idx] = scenario_idx
                    embedding_idx += 1
            
            # Also encode the title as a potential match point
            all_questions.append(scenario["title"])
            self.canonical_questions.append(scenario["title"])
            self.scenario_mapping[embedding_idx] = scenario_idx
            embedding_idx += 1
        
        # Compute embeddings
        if not all_questions:
            logger.warning("No canonical questions found in scenarios")
            return np.array([])
            
        try:
            logger.info(f"Computing embeddings for {len(all_questions)} canonical questions")
            return self.model.encode(all_questions, convert_to_numpy=True)
        except Exception as e:
            logger.error(f"Error computing embeddings: {e}")
            return np.array([])
    
    def find_matching_scenarios(self, query: str, top_k: int = 3) -> List[Tuple[Dict[str, Any], float]]:
        """
        Find scenarios matching the query using semantic similarity.
        
        Args:
            query: User's query
            top_k: Number of top matches to return
            
        Returns:
            List of tuples containing (scenario, similarity_score)
        """
        if not self.model or len(self.scenario_embeddings) == 0:
            logger.warning("Semantic matching unavailable, returning empty results")
            return []
            
        try:
            # Compute query embedding
            query_embedding = self.model.encode(query, convert_to_numpy=True)
            
            # Calculate cosine similarity
            similarities = np.dot(self.scenario_embeddings, query_embedding) / (
                np.linalg.norm(self.scenario_embeddings, axis=1) * np.linalg.norm(query_embedding)
            )
            
            # Get top-k matches
            top_indices = np.argsort(-similarities)[:top_k*2]  # Get more to filter duplicates
            
            # Collect unique scenarios with their highest similarity score
            seen_scenarios = set()
            results = []
            
            for idx in top_indices:
                scenario_idx = self.scenario_mapping[idx]
                similarity = similarities[idx]
                
                if scenario_idx not in seen_scenarios and similarity > 0.5:  # Threshold for meaningful similarity
                    seen_scenarios.add(scenario_idx)
                    results.append((self.scenarios[scenario_idx], float(similarity)))
                    
                    if len(results) >= top_k:
                        break
            
            logger.info(f"Semantic matcher found {len(results)} relevant scenarios")
            return results
            
        except Exception as e:
            logger.error(f"Error in semantic matching: {e}")
            return []
    
    def update_scenarios(self, new_scenarios: List[Dict[str, Any]]) -> None:
        """
        Update the scenarios data and recompute embeddings.
        
        Args:
            new_scenarios: New list of scenario dictionaries
        """
        self.scenarios = new_scenarios
        if self.model:
            self.scenario_embeddings = self._compute_embeddings()