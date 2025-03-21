import os
import json
import requests
from bs4 import BeautifulSoup
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.schema import Document
from dotenv import load_dotenv
from typing import List, Dict
from .cache_manager import KnowledgeCache
from chromadb.config import Settings

load_dotenv()

class DexKitKnowledgeBase:
    def __init__(self, chunk_size: int = 300, chunk_overlap: int = 30):
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
        self.cache = KnowledgeCache(cache_size=100, cache_ttl=3600)
        
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
        """Process PDF documents with improved chunking"""
        documents = []
        for filename in os.listdir(pdf_directory):
            if filename.endswith('.pdf'):
                try:
                    pdf_path = os.path.join(pdf_directory, filename)
                    print(f"Processing PDF: {pdf_path}")
                    
                    loader = PyPDFLoader(pdf_path)
                    pages = loader.load()
                    
                    text_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=self.chunk_size,
                        chunk_overlap=self.chunk_overlap,
                        separators=["\n\n", "\n", ". ", " ", ""]
                    )
                    
                    for page in pages:
                        chunks = text_splitter.split_text(page.page_content)
                        for chunk in chunks:
                            if len(chunk.strip()) > 50:
                                doc = Document(
                                    page_content=chunk,
                                    metadata={
                                        'source': filename,
                                        'type': 'pdf',
                                        'page': page.metadata.get('page', 0)
                                    }
                                )
                                documents.append(doc)
                                print(f"Added chunk from page {page.metadata.get('page', 0)}")
                    
                    print(f"Successfully processed PDF: {filename} - Generated {len(documents)} chunks")
                except Exception as e:
                    print(f"Error processing PDF {filename}: {str(e)}")
                    import traceback
                    print(traceback.format_exc())
        
        return documents
        
    def process_youtube(self, video_url: str) -> List[Document]:
        """Process a YouTube video metadata without transcripts"""
        try:
            video_data = None
            for category, content in self.youtube_metadata.get('tutorials', {}).items():
                if isinstance(content, dict):
                    for subcategory, videos in content.items():
                        if isinstance(videos, list):
                            for video in videos:
                                if video.get('url') == video_url:
                                    video_data = video
                                    break
                elif isinstance(content, list):
                    for video in content:
                        if video.get('url') == video_url:
                            video_data = video
                            break

            if not video_data:
                print(f"Warning: No metadata found for video: {video_url}")
                return []

            metadata_content = f"""
            Title: {video_data.get('title', '')}
            Description: {video_data.get('description', '')}
            Category: {video_data.get('category', '')}
            Topics: {', '.join(video_data.get('topics', []))}
            Keywords: {', '.join(video_data.get('keywords', []))}
            Difficulty: {video_data.get('difficulty', '')}
            Language: {video_data.get('language', '')}
            Related Docs: {', '.join(video_data.get('related_docs', []))}
            """

            return [
                Document(
                    page_content=metadata_content.strip(),
                    metadata={
                        'source': video_url,
                        'type': 'youtube',
                        'title': video_data.get('title', ''),
                        'category': video_data.get('category', ''),
                        'priority': video_data.get('priority', 0),
                        'language': video_data.get('language', ''),
                        'difficulty': video_data.get('difficulty', ''),
                        'topics': video_data.get('topics', []),
                        'related_docs': video_data.get('related_docs', [])
                    }
                )
            ]

        except Exception as e:
            print(f"Warning: Could not process video metadata {video_url}: {str(e)}")
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
        """Create or load knowledge base"""
        if os.getenv('SKIP_DOC_PROCESSING'):
            self.db = Chroma(
                persist_directory="./knowledge_base",
                embedding_function=self.embeddings,
                client_settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                    is_persistent=True
                )
            )
            return
        
        documents = []
        
        print("\nProcessing documentation pages...")
        web_docs = self.process_web_docs()
        documents.extend(web_docs)
        print(f"✓ Processed {len(web_docs)} web documents")
        
        if pdf_directory and os.path.exists(pdf_directory):
            print("\nProcessing PDF documents...")
            pdf_docs = self.process_pdf(pdf_directory)
            documents.extend(pdf_docs)
            print(f"✓ Processed {len(pdf_docs)} PDF documents")
        
        if youtube_urls:
            print(f"\nProcessing {len(youtube_urls)} video metadata...")
            video_docs = []
            for url in youtube_urls:
                video_docs.extend(self.process_youtube(url))
            documents.extend(video_docs)
            print(f"✓ Processed metadata for {len(video_docs)} videos")
        
        print(f"\nCreating vector knowledge base with {len(documents)} total documents...")
        
        self.db = Chroma(
            persist_directory="./knowledge_base",
            embedding_function=self.embeddings,
            client_settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
                is_persistent=True
            )
        )
        
        self.db.add_documents(documents)
        
        print("✅ Knowledge base created successfully!")
        
        self.cache.set_query_function(self._raw_query_knowledge)

    def _raw_query_knowledge(self, query: str, k: int = 3):
        """Raw query function without cache"""
        if not self.db:
            raise ValueError("Knowledge base not initialized")
        return self.db.similarity_search(query, k=k)
        
    def query_knowledge(self, query: str, k: int = 3):
        """Query function with cache"""
        try:
            return self.cache.query(query, k)
        except Exception as e:
            print(f"Cache error, falling back to direct query: {str(e)}")
            return self._raw_query_knowledge(query, k)

    def process_new_pdfs(self, pdf_paths: List[str]) -> List[Document]:
        """Process new PDFs incrementally with batch processing"""
        BATCH_SIZE = 50
        documents = []
        current_batch = []
        
        for pdf_path in pdf_paths:
            if os.path.isfile(pdf_path) and pdf_path.endswith('.pdf'):
                try:
                    loader = PyPDFLoader(pdf_path)
                    pages = loader.load()
                    
                    text_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=self.chunk_size,
                        chunk_overlap=self.chunk_overlap,
                        separators=["\n\n", "\n", ". ", " ", ""]
                    )
                    
                    for page in pages:
                        chunks = text_splitter.split_text(page.page_content)
                        for chunk in chunks:
                            if len(chunk.strip()) > 50:
                                doc = Document(
                                    page_content=chunk,
                                    metadata={
                                        'source': os.path.basename(pdf_path),
                                        'type': 'pdf',
                                        'page': page.metadata.get('page', 0)
                                    }
                                )
                                current_batch.append(doc)
                                documents.append(doc)
                                print(f"Added chunk from {os.path.basename(pdf_path)} page {page.metadata.get('page', 0)}")
                                
                                if len(current_batch) >= BATCH_SIZE:
                                    if self.db:
                                        self.db.add_documents(current_batch)
                                        print(f"Processed batch of {len(current_batch)} chunks")
                                    current_batch = []
                
                except Exception as e:
                    print(f"Error processing PDF {pdf_path}: {str(e)}")
                
        if current_batch and self.db:
            try:
                self.db.add_documents(current_batch)
                print(f"Processed final batch of {len(current_batch)} chunks")
            except Exception as e:
                print(f"Error processing final batch: {str(e)}")
        
        return documents

    def process_new_videos(self, video_urls: List[str]) -> List[Document]:
        """Process new YouTube videos incrementally"""
        documents = []
        for url in video_urls:
            try:
                video_docs = self.process_youtube(url)
                documents.extend(video_docs)
            except Exception as e:
                print(f"Error processing video {url}: {str(e)}")
        
        if documents and self.db:
            self.db.add_documents(documents)
            print(f"Added {len(documents)} new video chunks to knowledge base")
        
        return documents