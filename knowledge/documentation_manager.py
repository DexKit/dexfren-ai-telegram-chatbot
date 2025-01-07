import json
import os
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class DocReference:
    url: str
    title: str
    description: str

class DocumentationManager:
    def __init__(self, config_path: str = "config/documentation_urls.json"):
        self.config_path = config_path
        self.docs_map: Dict[str, DocReference] = {}
        self.load_documentation()
    
    def load_documentation(self):
        """Load documentation URLs from JSON config"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Documentation config not found at {self.config_path}")
            
        with open(self.config_path, 'r') as f:
            self.config = json.load(f)
            
        # Flatten URLs but limit depth to save processing
        self._flatten_urls(self.config, max_depth=2)
    
    def _flatten_urls(self, config: dict, prefix: str = "", current_depth: int = 0, max_depth: int = 2):
        """Recursively flatten nested URL structure with depth limit"""
        if current_depth >= max_depth:
            return
            
        for key, value in config.items():
            if isinstance(value, str) and key != "base_url":
                if value.startswith("http"):
                    full_url = value
                else:
                    base = config.get("base_url", prefix)
                    full_url = base + value
                
                # Simplified metadata
                self.docs_map[key] = DocReference(
                    url=full_url,
                    title=key.replace("_", " ").title(),
                    description=""
                )
            elif isinstance(value, dict):
                new_prefix = config.get("base_url", prefix)
                self._flatten_urls(
                    value, 
                    new_prefix, 
                    current_depth + 1, 
                    max_depth
                )
    
    def find_relevant_docs(self, query: str, max_results: int = 3) -> List[DocReference]:
        """Find relevant documentation links for a given query with limit"""
        relevant_docs = []
        query_terms = set(query.lower().split())
        
        for key, doc in self.docs_map.items():
            key_terms = set(key.lower().split('_'))
            if query_terms & key_terms:  # If there's any intersection
                relevant_docs.append(doc)
                if len(relevant_docs) >= max_results:
                    break
        
        return relevant_docs

    def get_url(self, key: str) -> str:
        """Get URL by key"""
        doc = self.docs_map.get(key)
        return doc.url if doc else None 