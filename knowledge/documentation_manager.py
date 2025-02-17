import json
import os
from typing import List, Dict
from dataclasses import dataclass
import requests

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
        query_terms = set(query.lower().split())
        
        priority_terms = {
            'contract': {
                'high': {'contract', 'token', 'erc20', 'erc721', 'erc1155', 'thirdweb'},
                'medium': {'deploy', 'create', 'mint', 'airdrop', 'stake'},
                'low': {'manage', 'update', 'list'}
            },
            'dapp': {
                'high': {'dapp', 'application', 'builder'},
                'medium': {'template', 'customize', 'configure'},
                'low': {'manage', 'update'}
            }
        }
        
        scored_docs = []
        for key, doc in self.docs_map.items():
            key_terms = set(key.lower().replace('-', '_').split('_'))
            path_terms = set(doc.url.lower().split('/'))
            
            searchable_terms = key_terms | path_terms
            
            intersection = query_terms & searchable_terms
            
            if intersection:
                base_score = len(intersection)
                bonus_score = 0
                
                for category, terms in priority_terms.items():
                    if query_terms & terms['high']:
                        if category == 'contract' and 'thirdweb' in key_terms:
                            bonus_score += 3
                        bonus_score += 2
                    if query_terms & terms['medium']:
                        bonus_score += 1
                    if query_terms & terms['low']:
                        bonus_score += 0.5
                
                if any(term in doc.url.lower() for term in query_terms):
                    bonus_score += 1
                    
                final_score = base_score + bonus_score
                scored_docs.append((final_score, doc))
        
        scored_docs.sort(reverse=True, key=lambda x: x[0])
        return [doc for _, doc in scored_docs[:max_results]]

    def get_url(self, key: str) -> str:
        """Get URL by key"""
        doc = self.docs_map.get(key)
        return doc.url if doc else None 

    def validate_url(self, url: str) -> bool:
        try:
            response = requests.head(url)
            return response.status_code == 200
        except:
            return False 

    def reload_configuration(self):
        """Reload configuration without restarting the bot"""
        self.load_documentation()
        self.create_knowledge_base() 

    def debug_search(self, query: str) -> None:
        """Helps to debug the search results showing the scores"""
        query_terms = set(query.lower().split())
        print(f"\nSearch for: '{query}'")
        print(f"Search terms: {query_terms}")
        
        results = self.find_relevant_docs(query, max_results=5)
        for i, doc in enumerate(results, 1):
            print(f"\n{i}. {doc.title}")
            print(f"   URL: {doc.url}") 