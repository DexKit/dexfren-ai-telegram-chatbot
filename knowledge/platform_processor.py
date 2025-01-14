import json
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
import requests
from bs4 import BeautifulSoup
import time

@dataclass
class PlatformData:
    url: str
    title: str
    description: str
    content: str
    category: str
    section: str
    type: str

class PlatformProcessor:
    def __init__(self, config_path: str = "config/platform_urls.json"):
        self.config_path = config_path
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def _extract_content(self, soup: BeautifulSoup, url: str) -> Dict[str, str]:
        """Extract relevant content from the page"""
        result = {
            'title': '',
            'description': '',
            'content': ''
        }

        title_selectors = [
            ('h1', {}),
            ('meta[property="og:title"]', 'content'),
            ('title', None),
            ('.page-title', None)
        ]
        
        for selector, attr in title_selectors:
            if element := soup.select_one(selector):
                result['title'] = element.get(attr) if attr else element.get_text(strip=True)
                if result['title']:
                    break

        desc_selectors = [
            ('meta[name="description"]', 'content'),
            ('meta[property="og:description"]', 'content'),
            ('.description', None),
            ('.summary', None)
        ]
        
        for selector, attr in desc_selectors:
            if element := soup.select_one(selector):
                result['description'] = element.get(attr) if attr else element.get_text(strip=True)
                if result['description']:
                    break

        content_selectors = [
            'main',
            'article',
            '.content',
            '#content',
            '.main-content',
            '.page-content'
        ]
        
        for selector in content_selectors:
            if main_content := soup.select_one(selector):
                for elem in main_content.select('script, style, nav, footer, header, aside'):
                    elem.decompose()
                
                content_parts = []
                for elem in main_content.select('h1, h2, h3, h4, h5, h6, p, li, .text'):
                    text = elem.get_text(strip=True)
                    if text:
                        if elem.name and elem.name.startswith('h'):
                            content_parts.append(f"\n## {text}\n")
                        else:
                            content_parts.append(text)
                
                result['content'] = '\n'.join(content_parts)
                break

        return result

    def _scrape_url(self, url: str, category: str, section: str, type_: str) -> Optional[PlatformData]:
        """Scrape a URL with error handling and retries"""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            content_data = self._extract_content(soup, url)
            
            return PlatformData(
                url=url,
                title=content_data['title'],
                description=content_data['description'],
                content=content_data['content'],
                category=category,
                section=section,
                type=type_
            )
            
        except Exception as e:
            logging.error(f"Error scraping {url}: {str(e)}")
            return None

    def process_platform_urls(self) -> List[PlatformData]:
        """Process all platform URLs"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            platform_data = []
            
            def process_section(data: Dict, parent_category: str = "", section: str = ""):
                for key, value in data.items():
                    if isinstance(value, str) and value.startswith('http'):
                        platform_info = self._scrape_url(
                            url=value,
                            category=parent_category,
                            section=section or key,
                            type_='platform'
                        )
                        if platform_info:
                            platform_data.append(platform_info)
                            logging.info(f"Successfully processed platform URL: {value}")
                        time.sleep(0.5)
                        
                    elif isinstance(value, dict):
                        new_parent = f"{parent_category}/{key}" if parent_category else key
                        process_section(value, new_parent, key)
            
            for section, content in config.items():
                process_section(content, section)
            
            logging.info(f"Total platform URLs processed: {len(platform_data)}")
            return platform_data
            
        except Exception as e:
            logging.error(f"Error processing platform URLs: {e}")
            return [] 