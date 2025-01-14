from dataclasses import dataclass
from typing import List, Dict, Set
import json
import os

@dataclass
class DocReference:
    url: str
    title: str
    description: str = ""
    priority: int = 2
    content_type: str = "documentation"

class DocumentationManager:
    def __init__(self):
        self.platform_urls = self._load_json('config/platform_urls.json')
        self.docs_urls = self._load_json('config/documentation_urls.json')
        self.video_urls = self._load_json('config/youtube_videos.json')
        
    def _load_json(self, path: str) -> Dict:
        """Load and validate JSON configuration file"""
        if not os.path.exists(path):
            print(f"Warning: Config file not found: {path}")
            return {}
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {path}: {str(e)}")
            return {}

    def find_relevant_docs(self, query: str, max_results: int = 3) -> List[DocReference]:
        """Find relevant documentation links and platform URLs"""
        relevant_docs = []
        query_terms = set(query.lower().split())
        
        platform_refs = self._get_platform_references(query_terms)
        if platform_refs:
            relevant_docs.extend(platform_refs)
        
        if len(relevant_docs) < max_results:
            video_refs = self._find_relevant_videos(query_terms)
            relevant_docs.extend(video_refs[:max_results - len(relevant_docs)])
        
        return relevant_docs[:max_results]

    def _get_platform_references(self, query_terms: Set[str]) -> List[DocReference]:
        """Get platform references based on query context"""
        refs = []
        admin_urls = self.platform_urls.get('products', {}).get('dexappbuilder', {}).get('dexkit-dexappbuilder-admin', {})
        
        for key, url in admin_urls.items():
            if isinstance(url, str) and self._is_url_relevant(key, query_terms):
                refs.append(DocReference(
                    url=url,
                    title=self._generate_title(key),
                    description=self._generate_description(key),
                    priority=1,
                    content_type="platform"
                ))
            elif isinstance(url, dict):
                for subkey, suburl in url.items():
                    if self._is_url_relevant(subkey, query_terms):
                        refs.append(DocReference(
                            url=suburl,
                            title=self._generate_title(subkey),
                            description=self._generate_description(subkey),
                            priority=1,
                            content_type="platform"
                        ))
        return refs

    def _is_url_relevant(self, key: str, query_terms: Set[str]) -> bool:
        """Determine if a URL is relevant based on its key and query terms"""
        key_terms = set(key.lower().replace('-', ' ').split())
        return bool(key_terms & query_terms)

    def _generate_title(self, key: str) -> str:
        """Generate a human-readable title from a URL key"""
        clean_key = key.replace('dexkit-dexappbuilder-admin-', '')
        return clean_key.replace('-', ' ').title()

    def _generate_description(self, key: str) -> str:
        """Generate a description based on the URL key"""
        if 'create' in key:
            return "Create and deploy your DApp"
        elif 'quick' in key:
            return "Quick build options"
        elif 'dashboard' in key:
            return "Manage your DApps"
        return "Platform access"

    def _find_relevant_videos(self, query_terms: Set[str]) -> List[DocReference]:
        """Find relevant videos based on query context"""
        relevant_videos = []
        
        for category, data in self.video_urls.items():
            if isinstance(data, dict):
                for subcategory, videos in data.items():
                    if isinstance(videos, list):
                        for video in videos:
                            if self._video_matches_query(video, query_terms):
                                relevant_videos.append(DocReference(
                                    url=video['url'],
                                    title=video['title'],
                                    description=f"Video tutorial - {video.get('category', 'general')}",
                                    priority=2,
                                    content_type="video"
                                ))
        
        return sorted(relevant_videos, key=lambda x: x.priority)

    def _video_matches_query(self, video: Dict, query_terms: Set[str]) -> bool:
        """Check if a video matches the query terms"""
        video_text = f"{video['title']} {video.get('category', '')}".lower()
        return any(term in video_text for term in query_terms) 