from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import requests
from bs4 import BeautifulSoup
import json
from typing import Dict, List, Optional
import logging
from dataclasses import dataclass
import re

@dataclass
class VideoData:
    url: str
    video_id: str
    title: str
    description: str
    transcript: str
    category: str
    priority: int
    language: str

class YouTubeProcessor:
    def __init__(self, config_path: str = "config/youtube_videos.json"):
        self.config_path = config_path
        self.session = requests.Session()
        self.formatter = TextFormatter()
        
    def extract_video_id(self, url: str) -> str:
        """Extract the video ID from a YouTube URL"""
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu.be\/)([\w-]+)',
            r'(?:youtube\.com\/embed\/)([\w-]+)',
            r'(?:youtube\.com\/v\/)([\w-]+)'
        ]
        
        for pattern in patterns:
            if match := re.search(pattern, url):
                return match.group(1)
        raise ValueError(f"Invalid YouTube URL: {url}")

    def get_video_info(self, url: str) -> Dict:
        """Get detailed video information using the oEmbed API"""
        video_id = self.extract_video_id(url)
        api_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        
        try:
            response = self.session.get(api_url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Error getting video info for {url}: {e}")
            return {}

    def get_video_description(self, video_id: str) -> str:
        """Get the complete video description"""
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            response = self.session.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            desc = None
            for selector in [
                'meta[name="description"]',
                'meta[property="og:description"]',
                '#description-text'
            ]:
                desc = soup.select_one(selector)
                if desc:
                    return desc.get('content', desc.text).strip()
            return ""
        except Exception as e:
            logging.error(f"Error getting video description: {e}")
            return ""

    def get_transcript(self, video_id: str) -> Optional[Dict[str, str]]:
        """Get the video transcript in multiple languages"""
        try:
            transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript_data = {}
            
            try:
                en_transcript = transcripts.find_transcript(['en'])
                transcript_data['en'] = self.formatter.format_transcript(en_transcript.fetch())
            except:
                pass
            
            try:
                es_transcript = transcripts.find_transcript(['es'])
                transcript_data['es'] = self.formatter.format_transcript(es_transcript.fetch())
            except:
                pass
            
            if not transcript_data:
                try:
                    transcript = transcripts.find_manually_created_transcript()
                    translated = transcript.translate('en').fetch()
                    transcript_data['en'] = self.formatter.format_transcript(translated)
                except:
                    pass
            
            return transcript_data if transcript_data else None
            
        except Exception as e:
            logging.error(f"Error getting transcript for video {video_id}: {e}")
            return None

    def process_videos(self) -> List[VideoData]:
        """Process all videos from the configuration file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8-sig') as f:
                config = json.load(f)
            
            videos = []
            processed_urls = set()
            
            def process_video_entry(entry: Dict, category: str):
                try:
                    url = entry['url']
                    if url in processed_urls:
                        return
                    processed_urls.add(url)
                    
                    video_id = self.extract_video_id(url)
                    logging.info(f"Processing video: {url}")
                    
                    info = self.get_video_info(url)
                    description = self.get_video_description(video_id)
                    transcripts = self.get_transcript(video_id)
                    
                    transcript = transcripts.get('en', transcripts.get('es', '')) if transcripts else ''
                    language = 'en' if transcripts and 'en' in transcripts else 'es'
                    
                    videos.append(VideoData(
                        url=url,
                        video_id=video_id,
                        title=entry.get('title', info.get('title', '')),
                        description=description,
                        transcript=transcript,
                        category=category,
                        priority=entry.get('priority', 1),
                        language=language
                    ))
                    logging.info(f"Successfully processed video: {url}")
                    
                except Exception as e:
                    logging.error(f"Error processing video {entry.get('url')}: {e}")
            
            if 'video_list' in config:
                for url in config['video_list']:
                    if isinstance(url, str):
                        process_video_entry({'url': url}, 'general')
            
            if 'tutorials' in config:
                def process_category(data, parent_category=''):
                    if isinstance(data, list):
                        for entry in data:
                            if isinstance(entry, dict) and 'url' in entry:
                                category = f"{parent_category}" if parent_category else entry.get('category', 'general')
                                process_video_entry(entry, category)
                    elif isinstance(data, dict):
                        for key, value in data.items():
                            new_category = f"{parent_category}/{key}" if parent_category else key
                            process_category(value, new_category)
                
                process_category(config['tutorials'])
            
            logging.info(f"Total videos processed: {len(videos)}")
            return videos
            
        except Exception as e:
            logging.error(f"Error processing videos: {e}")
            return []