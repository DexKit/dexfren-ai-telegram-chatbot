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
            
        # Flatten URLs for easy access
        self._flatten_urls(self.config)
    
    def _flatten_urls(self, config: dict, prefix: str = ""):
        """Recursively flatten nested URL structure"""
        for key, value in config.items():
            if isinstance(value, str) and key != "base_url":
                if value.startswith("http"):
                    full_url = value
                else:
                    base = config.get("base_url", prefix)
                    full_url = base + value
                self.docs_map[key] = DocReference(
                    url=full_url,
                    title=key.replace("_", " ").title(),
                    description=""  # Could be loaded from a separate file
                )
            elif isinstance(value, dict):
                new_prefix = config.get("base_url", prefix)
                self._flatten_urls(value, new_prefix)
    
    def find_relevant_docs(self, query: str) -> List[DocReference]:
        """Find relevant documentation links for a given query"""
        relevant_docs = []
        query_terms = query.lower().split()
        
        for key, doc in self.docs_map.items():
            if any(term in key.lower() for term in query_terms):
                relevant_docs.append(doc)
        
        return relevant_docs

    def get_url(self, key: str) -> str:
        """Get URL by key"""
        doc = self.docs_map.get(key)
        return doc.url if doc else None 