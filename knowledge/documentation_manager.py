import json
import os
from typing import List, Dict, Optional
from dataclasses import dataclass
import requests
from bs4 import BeautifulSoup
import logging
from urllib.parse import urljoin, urlparse
import time

@dataclass
class DocReference:
    url: str
    title: str
    description: str
    content: str
    category: str
    last_updated: Optional[str] = None

class DocumentationManager:
    def __init__(self, config_path: str = "config/documentation_urls.json"):
        self.config_path = config_path
        self.docs_map: Dict[str, DocReference] = {}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.load_documentation()
    
    def _extract_content(self, soup: BeautifulSoup, url: str) -> Dict[str, str]:
        """Extract relevant content more effectively"""
        result = {
            'title': '',
            'description': '',
            'content': '',
            'last_updated': None
        }

        title_tag = (
            soup.find('h1') or 
            soup.find('meta', property='og:title') or 
            soup.find('meta', {'name': 'title'})
        )
        if title_tag:
            result['title'] = title_tag.get_text() if hasattr(title_tag, 'get_text') else title_tag.get('content', '')

        desc_tag = (
            soup.find('meta', property='og:description') or 
            soup.find('meta', {'name': 'description'}) or
            soup.find('div', class_=['description', 'summary', 'intro'])
        )
        if desc_tag:
            result['description'] = desc_tag.get('content', '') if desc_tag.get('content') else desc_tag.get_text()

        main_content = None
        content_selectors = [
            ('main', {}),
            ('article', {}),
            ('div', {'class': ['content', 'documentation', 'docs-content', 'main-content']}),
            ('div', {'id': ['content', 'main-content', 'documentation']}),
        ]

        for tag, attrs in content_selectors:
            main_content = soup.find(tag, attrs)
            if main_content:
                break

        if main_content:
            for elem in main_content.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                elem.decompose()

            paragraphs = []
            for elem in main_content.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li']):
                text = elem.get_text(strip=True)
                if text:
                    if elem.name.startswith('h'):
                        paragraphs.append(f"\n## {text}\n")
                    else:
                        paragraphs.append(text)

            result['content'] = '\n'.join(paragraphs)

        date_selectors = [
            ('meta', {'name': 'last-modified'}),
            ('time', {}),
            ('span', {'class': ['date', 'last-updated', 'modified-date']})
        ]
        
        for tag, attrs in date_selectors:
            date_elem = soup.find(tag, attrs)
            if date_elem:
                result['last_updated'] = date_elem.get('content', date_elem.get_text())
                break

        return result

    def _scrape_url(self, url: str, category: str) -> Optional[DocReference]:
        """Improved URL scraping with error handling and retries"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            content_data = self._extract_content(soup, url)
            
            return DocReference(
                url=url,
                title=content_data['title'],
                description=content_data['description'],
                content=content_data['content'],
                category=category,
                last_updated=content_data['last_updated']
            )
            
        except requests.RequestException as e:
            logging.error(f"Error scraping {url}: {str(e)}")
            return None
            
    def load_documentation(self):
        """Load and process documentation with better structure handling"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Documentation config not found at {self.config_path}")
            
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
                
            for product, config in self.config.items():
                if isinstance(config, dict):
                    base_url = config.get("base_url", "")
                    self._process_urls(config, product, base_url)
                    
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing JSON in {self.config_path}: {e}")
            raise
        except Exception as e:
            logging.error(f"Error loading documentation: {e}")
            raise
        
    def _process_urls(self, config: dict, parent_category: str = "", base_url: str = ""):
        """Process URLs recursively with better categorization"""
        if not isinstance(config, dict):
            return

        if "base_url" in config:
            base_url = config["base_url"]

        if "sections" in config:
            sections = config["sections"]
        else:
            sections = config

        for key, value in sections.items():
            if key == "base_url":
                continue

            if isinstance(value, str):
                if value.startswith('http'):
                    url = value
                else:
                    url = base_url + value if base_url else value

                if url.startswith('http'):
                    category = f"{parent_category}/{key}" if parent_category else key
                    doc_ref = self._scrape_url(url, category)
                    if doc_ref:
                        self.docs_map[key] = doc_ref
                        logging.info(f"Successfully processed: {url}")
                    time.sleep(0.5)

            elif isinstance(value, dict):
                new_parent = f"{parent_category}/{key}" if parent_category else key
                
                if "base" in value:
                    new_base = base_url + value["base"] if base_url else value["base"]
                else:
                    new_base = base_url

                if "subsections" in value:
                    for subkey, subvalue in value["subsections"].items():
                        if isinstance(subvalue, str):
                            url = new_base + subvalue if new_base else subvalue
                            if url.startswith('http'):
                                category = f"{new_parent}/{subkey}"
                                doc_ref = self._scrape_url(url, category)
                                if doc_ref:
                                    self.docs_map[f"{key}_{subkey}"] = doc_ref
                                    logging.info(f"Successfully processed: {url}")
                                time.sleep(0.5)
                else:
                    self._process_urls(value, new_parent, new_base)

    def find_relevant_docs(self, query: str, max_results: int = 3) -> List[DocReference]:
        """Improved document search"""
        query_terms = set(query.lower().split())
        
        priority_terms = {
            'token': 3,
            'contract': 3,
            'erc20': 3,
            'deploy': 2,
            'create': 2,
            'dapp': 2,
            'builder': 2,
            'template': 1.5
        }
        
        scored_docs = []
        for doc in self.docs_map.values():
            score = 0
            content_lower = doc.content.lower()
            
            for term, weight in priority_terms.items():
                if term in content_lower:
                    score += weight
            
            for term in query_terms:
                if term in content_lower:
                    score += 1
                if term in doc.title.lower():
                    score += 2
                if term in doc.description.lower():
                    score += 1.5
            
            if score > 0:
                scored_docs.append((score, doc))
        
        scored_docs.sort(reverse=True, key=lambda x: x[0])
        return [doc for _, doc in scored_docs[:max_results]]

    def get_url(self, key: str) -> Optional[str]:
        """Get URL with validation"""
        doc = self.docs_map.get(key)
        if doc and self.validate_url(doc.url):
            return doc.url
        return None

    def validate_url(self, url: str) -> bool:
        """Improved URL validation"""
        try:
            response = self.session.head(url, timeout=5)
            return response.status_code == 200
        except:
            return False

    def reload_configuration(self):
        """Reload configuration and update knowledge base"""
        self.docs_map.clear()
        self.load_documentation() 