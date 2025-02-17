import os
import json
import requests
from bs4 import BeautifulSoup
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from youtube_transcript_api import YouTubeTranscriptApi
from langchain.schema import Document
from dotenv import load_dotenv
from typing import List, Dict

load_dotenv()

class DexKitKnowledgeBase:
    def __init__(self, chunk_size=500, chunk_overlap=50):
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=os.getenv('OPENAI_API_KEY')
        )
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.db = None
        self.youtube_metadata = self._load_youtube_metadata()
        self.docs_metadata = self._load_docs_metadata()
        self.platform_urls = self._load_platform_urls()
        
    def _load_youtube_metadata(self) -> Dict:
        """Load YouTube metadata from config file"""
        try:
            config_path = 'config/youtube_videos.json'
            print(f"Loading YouTube metadata from: {os.path.abspath(config_path)}")
            
            if not os.path.exists(config_path):
                print(f"Error: File not found at {config_path}")
                return {}
            
            with open(config_path, 'rb') as f:
                content = f.read().decode('utf-8-sig').strip()
                if content.startswith(u'\ufeff'):
                    content = content[1:]
                print(f"First 100 characters of file: {content[:100]}")
                
                try:
                    data = json.loads(content)
                    print("JSON loaded successfully")
                    return data.get('tutorials', {})
                except json.JSONDecodeError as je:
                    print(f"JSON Error at position {je.pos}: {je.msg}")
                    print(f"Near text: {content[max(0, je.pos-20):je.pos+20]}")
                    return {}
                
        except Exception as e:
            print(f"Warning: Could not load YouTube metadata: {str(e)}")
            print(f"Exception type: {type(e)}")
            return {}
        
    def _load_docs_metadata(self) -> Dict:
        """Load documentation URLs from config file"""
        try:
            with open('config/documentation_urls.json', 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load documentation metadata: {str(e)}")
            return {}
            
    def _load_platform_urls(self) -> Dict:
        """Load platform URLs from config file"""
        try:
            with open('config/platform_urls.json', 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load platform URLs: {str(e)}")
            return {}
        
    def get_video_id(self, url: str) -> str:
        """Extract the video ID from a YouTube URL"""
        video_id = url.split('/')[-1]
        if 'watch?v=' in video_id:
            video_id = video_id.split('watch?v=')[-1]
        return video_id
        
    def process_pdf(self, pdf_directory: str) -> List[Document]:
        """Process PDF files from a directory"""
        documents = []
        
        if not os.path.exists(pdf_directory):
            print(f"Warning: PDF directory {pdf_directory} does not exist")
            return documents
            
        for file in os.listdir(pdf_directory):
            if file.endswith('.pdf'):
                try:
                    pdf_path = os.path.join(pdf_directory, file)
                    loader = PyPDFLoader(pdf_path)
                    documents.extend(loader.load())
                    print(f"Processed PDF: {file}")
                except Exception as e:
                    print(f"Warning: Could not process PDF {file}: {str(e)}")
                    
        return documents
        
    def process_youtube(self, video_url: str) -> List[Document]:
        """Process a YouTube video using youtube_transcript_api"""
        try:
            video_id = self.get_video_id(video_url)
            transcript_list = None
            
            video_metadata = self.youtube_metadata.get(video_url, {})
            
            for langs in [['en'], ['es']]:
                try:
                    transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
                    break
                except Exception:
                    continue
                    
            if not transcript_list:
                print(f"Warning: No subtitles found for video: {video_metadata.get('title', video_url)}")
                return []
                
            full_transcript = ' '.join([entry['text'] for entry in transcript_list])
            
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap
            )
            splits = text_splitter.split_text(full_transcript)
            
            splits = splits[:5]
            
            return [
                Document(
                    page_content=split,
                    metadata={
                        'source': video_url,
                        'type': 'youtube',
                        'title': video_metadata.get('title', 'Unknown'),
                        'category': video_metadata.get('category', 'General')
                    }
                ) for split in splits
            ]
            
        except Exception as e:
            print(f"Warning: Could not process video {video_url}: {str(e)}")
            return []

    def process_web_docs(self) -> List[Document]:
        """Process web documentation and platform pages"""
        documents = []
        
        def extract_content(url: str, section: str, category: str) -> Dict:
            try:
                response = requests.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                
                for element in soup.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                    element.decompose()
                
                main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
                if main_content:
                    text = main_content.get_text(separator='\n', strip=True)
                else:
                    text = soup.get_text(separator='\n', strip=True)
                
                text = text[:5000]
                
                return {
                    'content': text,
                    'url': url,
                    'section': section,
                    'category': category
                }
            except Exception as e:
                print(f"Warning: Could not process URL {url}: {str(e)}")
                return None
        
        def process_urls_recursively(data: Dict, category: str = "", section: str = ""):
            for key, value in data.items():
                if isinstance(value, str) and value.startswith('http'):
                    content = extract_content(value, section or key, category)
                    if content:
                        text_splitter = RecursiveCharacterTextSplitter(
                            chunk_size=1000,
                            chunk_overlap=200
                        )
                        splits = text_splitter.split_text(content['content'])
                        
                        for split in splits:
                            documents.append(Document(
                                page_content=split,
                                metadata={
                                    'source': content['url'],
                                    'type': 'web_page',
                                    'section': content['section'],
                                    'category': content['category']
                                }
                            ))
                        print(f"Successfully processed: {value}")
                elif isinstance(value, dict):
                    process_urls_recursively(value, category or key, section or key)
        
        print("\nProcessing documentation pages...")
        process_urls_recursively(self.docs_metadata)
        
        print("\nProcessing platform pages...")
        process_urls_recursively(self.platform_urls)
        
        return documents

    def create_knowledge_base(self, pdf_directory: str = None, youtube_urls: List[str] = None):
        """Create the knowledge base from PDFs, web docs and YouTube videos"""
        documents = []
        
        documents.extend(self.process_web_docs())
        
        if pdf_directory:
            print("\nProcessing PDF documents...")
            documents.extend(self.process_pdf(pdf_directory))
        
        if youtube_urls:
            print(f"\nProcessing {len(youtube_urls)} videos...")
            for url in youtube_urls:
                print(f"Processing video: {url}")
                documents.extend(self.process_youtube(url))
        
        print(f"\nCreating vector knowledge base with {len(documents)} documents...")
        
        self.db = Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings,
            persist_directory="./knowledge_base"
        )
        
        print("Knowledge base created successfully!")

    def query_knowledge(self, query: str, k: int = 3) -> List[Document]:
        """Query the knowledge base"""
        if not self.db:
            raise ValueError("Knowledge base not initialized")
        
        results = self.db.similarity_search(query, k=k)
        return results