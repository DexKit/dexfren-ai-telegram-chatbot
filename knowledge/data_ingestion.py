import os
import json
import requests
from bs4 import BeautifulSoup
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.schema import Document
from dotenv import load_dotenv
from typing import List, Dict
from .cache_manager import KnowledgeCache
from chromadb.config import Settings
import logging

load_dotenv()

logger = logging.getLogger(__name__)

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
        
    def _load_youtube_metadata(self) -> List[Dict]:
        """Load YouTube metadata from config file"""
        try:
            config_path = 'config/youtube_videos.json'
            logger.debug(f"Loading YouTube metadata from: {os.path.abspath(config_path)}")
            
            if not os.path.exists(config_path):
                logger.error(f"Error: File not found at {config_path}")
                return []
            
            with open(config_path, 'rb') as f:
                content = f.read().decode('utf-8-sig').strip()
                data = json.loads(content)
                
                videos = {}
                paths = {}
                
                def extract_videos(obj, path=""):
                    if isinstance(obj, dict):
                        if 'url' in obj and 'title' in obj:
                            url = obj['url']
                            
                            if url not in paths:
                                paths[url] = path
                            
                            if url in videos:
                                merged = {**videos[url], **obj}
                                
                                for key in ['keywords', 'topics', 'related_docs']:
                                    if key in videos[url] and key in obj:
                                        merged[key] = list(set(videos[url][key] + obj[key]))
                                
                                videos[url] = merged
                            else:
                                videos[url] = obj.copy()
                                
                            videos[url]['_path'] = path
                        
                        for key, value in obj.items():
                            new_path = f"{path}/{key}" if path else key
                            extract_videos(value, new_path)
                    elif isinstance(obj, list):
                        for item in obj:
                            extract_videos(item, path)
                
                extract_videos(data)
                
                for url, video in videos.items():
                    path = video.get('_path', '')
                    categories = [p for p in path.split('/') if p]
                    
                    if 'categories' not in video:
                        video['categories'] = []
                    
                    video['categories'].extend(categories)
                    video['categories'] = list(set(video['categories']))
                    
                    if '_path' in video:
                        del video['_path']
                
                logger.debug(f"Found {len(videos)} unique videos in metadata")
                return list(videos.values())
                
        except Exception as e:
            logger.error(f"Warning: Could not load YouTube metadata: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
        
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
        """Process a YouTube video metadata"""
        try:
            with open('config/youtube_videos.json', 'r', encoding='utf-8-sig') as f:
                youtube_data = json.loads(f.read().strip())
            with open('config/keywords.json', 'r') as f:
                keywords_config = json.load(f)
            
            all_keywords = set()
            for category_data in keywords_config.values():
                all_keywords.update(category_data.get('keywords', []))
            
            all_videos = []
            
            def find_video_recursively(data, path=""):
                if isinstance(data, dict):
                    if 'url' in data and data.get('url') == video_url:
                        categories = [p for p in path.split('/') if p]
                        category_keywords = set()
                        
                        for category in categories:
                            if category in keywords_config:
                                category_keywords.update(keywords_config[category].get('keywords', []))
                        
                        metadata = {
                            'source': data.get('url'),
                            'type': 'youtube',
                            'title': data.get('title'),
                            'description': data.get('description', ''),
                            'duration': data.get('duration', 'N/A'),
                            'difficulty': data.get('difficulty', 'N/A'),
                            'topics': data.get('topics', []),
                            'keywords': list(set(data.get('keywords', [])) | category_keywords | all_keywords),
                            'related_docs': data.get('related_docs', []),
                            'categories': categories
                        }
                        
                        all_videos.append(Document(
                            page_content=data.get('description', ''),
                            metadata=metadata
                        ))
                    
                    for key, value in data.items():
                        new_path = f"{path}/{key}" if path else key
                        find_video_recursively(value, new_path)
                        
                elif isinstance(data, list):
                    for i, item in enumerate(data):
                        find_video_recursively(item, path)
            
            find_video_recursively(youtube_data)
            
            if not all_videos:
                with open('config/agent_instructions.json', 'r') as f:
                    agent_config = json.load(f)
                    content_map = agent_config.get('instructions', {}).get('content_mapping', {})
                    
                    for category, content in content_map.items():
                        category_keywords = set(keywords_config.get(category, {}).get('keywords', []))
                        
                        primary = content.get('primary_video', {})
                        if primary and primary.get('url') == video_url:
                            metadata = {
                                'source': primary.get('url'),
                                'type': 'youtube',
                                'title': primary.get('title'),
                                'description': primary.get('description', ''),
                                'duration': primary.get('duration', 'N/A'),
                                'difficulty': primary.get('difficulty', 'N/A'),
                                'topics': primary.get('topics', []),
                                'keywords': list(category_keywords | all_keywords),
                                'related_docs': primary.get('related_docs', []),
                                'categories': [category]
                            }
                            all_videos.append(Document(
                                page_content=primary.get('description', ''),
                                metadata=metadata
                            ))
                            
                        for secondary in content.get('secondary_videos', []):
                            if secondary.get('url') == video_url:
                                metadata = {
                                    'source': secondary.get('url'),
                                    'type': 'youtube',
                                    'title': secondary.get('title'),
                                    'description': secondary.get('description', ''),
                                    'duration': secondary.get('duration', 'N/A'),
                                    'difficulty': secondary.get('difficulty', 'N/A'),
                                    'topics': secondary.get('topics', []),
                                    'keywords': list(category_keywords | all_keywords),
                                    'related_docs': secondary.get('related_docs', []),
                                    'categories': [category]
                                }
                                all_videos.append(Document(
                                    page_content=secondary.get('description', ''),
                                    metadata=metadata
                                ))
            
            return all_videos

        except Exception as e:
            logger.error(f"Error processing video {video_url}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
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
        
    def query(self, query_text: str, filter_results: bool = True) -> list:
        """Query the knowledge base"""
        try:
            relevant_videos = self.find_videos_by_query(query_text)
            
            query_embedding = self.embeddings.embed_query(query_text)
            
            all_documents = []
            for namespace in self.namespaces:
                docs = self.db.similarity_search_by_vector_with_score(
                    query_embedding, 
                    k=5,
                    filter={"namespace": namespace}
                )
                all_documents.extend(docs)
            
            all_documents.sort(key=lambda x: x[1])
            
            documents = [doc for doc, _ in all_documents]
            
            if relevant_videos:
                logger.info(f"Adding {len(relevant_videos)} relevant videos to the context")
                documents = relevant_videos + documents
            
            return documents[:10]
        
        except Exception as e:
            logger.error(f"Error querying knowledge base: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []

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

    def _build_search_index(self):
        """Build the search index for all content"""
        try:
            logging.info("Cleaning existing database...")
            self.db.delete_collection()
            
            logging.info("Processing YouTube videos...")
            youtube_urls = self._load_youtube_urls()
            all_documents = []
            
            for url in youtube_urls:
                try:
                    video_docs = self.process_youtube(url)
                    if video_docs:
                        all_documents.extend(video_docs)
                        for doc in video_docs:
                            logger.debug(f"Processed video: {doc.metadata.get('title')}")
                            logger.debug(f"   URL: {doc.metadata.get('source')}")
                            logger.debug(f"   Keywords: {doc.metadata.get('keywords')}")
                except Exception as e:
                    logger.error(f"Error processing video {url}: {str(e)}")
            
            for i, doc in enumerate(all_documents):
                doc.metadata["id"] = f"doc_{i}_{hash(doc.page_content)}"
            
            logging.info(f"Adding {len(all_documents)} documents to the database...")
            if all_documents:
                self.db.add_documents(all_documents)
            
            self.cache = KnowledgeCache(self.db)
            return True
            
        except Exception as e:
            logging.error(f"Error building search index: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return False

    def get_topic_videos(self, topic_name):
        """Directly get videos for a specific topic bypassing the embedding search"""
        try:
            videos = []
            youtube_metadata = self._load_youtube_metadata()
            
            for url, video in youtube_metadata.items():
                categories = video.get('categories', [])
                keywords = video.get('keywords', [])
                
                if (topic_name.lower() in [c.lower() for c in categories]) or \
                   (topic_name.lower() in [k.lower() for k in keywords]):
                    doc = Document(
                        page_content=video.get('description', ''),
                        metadata={
                            'source': video.get('url', url),
                            'type': 'youtube',
                            'title': video.get('title', 'Tutorial Video'),
                            'description': video.get('description', ''),
                            'duration': video.get('duration', 'N/A'),
                            'difficulty': video.get('difficulty', 'Beginner'),
                            'topics': video.get('topics', []),
                            'keywords': video.get('keywords', []),
                            'related_docs': video.get('related_docs', []),
                            'categories': video.get('categories', [])
                        }
                    )
                    videos.append(doc)
            
            logger.info(f"Found {len(videos)} direct videos for topic '{topic_name}'")
            return videos
            
        except Exception as e:
            logger.error(f"Error getting videos by topic: {str(e)}")
            return []

    def process_youtube_content(self, topic_keywords):
        """Process YouTube content specifically for certain topics"""
        try:
            with open('config/youtube_videos.json', 'r', encoding='utf-8-sig') as f:
                content = f.read().strip()
                all_videos = json.loads(content)
                
            matched_videos = []
            
            def extract_matching_videos(data, topic_keywords):
                if isinstance(data, dict):
                    if 'url' in data and 'keywords' in data and 'title' in data:
                        video_keywords = [k.lower() for k in data.get('keywords', [])]
                        if any(kw.lower() in video_keywords for kw in topic_keywords):
                            matched_videos.append(data)
                        
                    for value in data.values():
                        if isinstance(value, (dict, list)):
                            extract_matching_videos(value, topic_keywords)
                
                elif isinstance(data, list):
                    for item in data:
                        extract_matching_videos(item, topic_keywords)
            
            extract_matching_videos(all_videos, topic_keywords)
            
            documents = []
            for video in matched_videos:
                doc = Document(
                    page_content=video.get('description', ''),
                    metadata={
                        'source': video.get('url', ''),
                        'type': 'youtube',
                        'title': video.get('title', ''),
                        'description': video.get('description', ''),
                        'duration': video.get('duration', 'N/A'),
                        'difficulty': video.get('difficulty', 'Beginner'),
                        'topics': video.get('topics', []),
                        'keywords': video.get('keywords', []),
                        'related_docs': video.get('related_docs', []),
                        'categories': [video.get('category', '')]
                    }
                )
                documents.append(doc)
            
            return documents
            
        except Exception as e:
            logger.error(f"Error processing YouTube content: {str(e)}")
            return []

    def get_platform_urls_for_context(self, query_text):
        """
        Gets platform URLs relevant to the user's query
        based on keywords.json and platform_urls.json
        """
        try:
            with open('config/keywords.json', 'r') as f:
                keywords_config = json.load(f)
            
            query_words = set(query_text.lower().replace('?', '').split())
            
            relevant_categories = []
            for category, data in keywords_config.items():
                category_keywords = [kw.lower() for kw in data.get('keywords', [])]
                if any(kw in query_words for kw in category_keywords) or any(kw in query_text.lower() for kw in category_keywords):
                    relevant_categories.append(category)
                    
            if "dapp_builder" in relevant_categories:
                builder_urls = self.platform_urls.get('dapp_builder', {})
                platform_info = "PLATFORM LINKS FOR DAPP CREATION:\n"
                
                if 'dashboard' in builder_urls:
                    platform_info += f"• Dashboard: {builder_urls['dashboard']}\n"
                if 'create' in builder_urls:
                    platform_info += f"• Create DApp: {builder_urls['create']}\n"
                    
                if 'quick_builders' in builder_urls:
                    platform_info += "\nQUICK BUILDERS:\n"
                    for key, url in builder_urls['quick_builders'].items():
                        platform_info += f"• {key.replace('_', ' ').title()}: {url}\n"
                        
                platform_info += "\nREMINDER: Users must CONNECT WALLET first (not login)"
                
                return platform_info
                
            elif "token_creation" in relevant_categories:
                contract_urls = self.platform_urls.get('dexgenerator_contracts', {})
                platform_info = "PLATFORM LINKS FOR TOKEN CREATION:\n"
                
                if 'create' in contract_urls:
                    platform_info += f"• Create Contract: {contract_urls['create']}\n"
                if 'list' in contract_urls:
                    platform_info += f"• List Contracts: {contract_urls['list']}\n"
                    
                platform_info += "\nREMINDER: Users must CONNECT WALLET first (not login)"
                
                return platform_info
                
            return None
            
        except Exception as e:
            logger.error(f"Error getting platform URLs for context: {str(e)}")
            return None

    def get_all_available_videos(self):
        """
        Fetch all available videos in the system.
        Useful for responding to queries about available tutorials.
        """
        try:
            videos_list = []
            
            youtube_metadata = self._load_youtube_metadata()
            if youtube_metadata:
                for video in youtube_metadata:
                    if 'url' in video and 'title' in video:
                        videos_list.append({
                            'title': video.get('title', ''),
                            'url': video.get('url', ''),
                            'duration': video.get('duration', 'N/A'),
                            'difficulty': video.get('difficulty', 'Beginner'),
                            'topics': video.get('topics', []),
                            'categories': video.get('categories', [])
                        })
            
            with open('config/agent_instructions.json', 'r') as f:
                agent_config = json.load(f)
                content_map = agent_config.get('instructions', {}).get('content_mapping', {})
                
                for category, content in content_map.items():
                    primary = content.get('primary_video', {})
                    if primary and 'url' in primary and 'title' in primary:
                        videos_list.append({
                            'title': primary.get('title', ''),
                            'url': primary.get('url', ''),
                            'duration': primary.get('duration', 'N/A'),
                            'difficulty': primary.get('difficulty', 'Beginner'),
                            'topics': primary.get('topics', []),
                            'categories': [category]
                        })
                    
                    for video in content.get('secondary_videos', []):
                        if 'url' in video and 'title' in video:
                            videos_list.append({
                                'title': video.get('title', ''),
                                'url': video.get('url', ''),
                                'duration': video.get('duration', 'N/A'),
                                'difficulty': video.get('difficulty', 'Beginner'),
                                'topics': video.get('topics', []),
                                'categories': [category]
                            })
            
            unique_videos = {}
            for video in videos_list:
                if video['url'] not in unique_videos:
                    unique_videos[video['url']] = video
            
            logger.info(f"Found {len(unique_videos)} unique videos in the knowledge base")
            return list(unique_videos.values())
            
        except Exception as e:
            logger.error(f"Error getting all available videos: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def find_videos_by_query(self, query_text):
        """
        Search for videos based on the query text and returns documents
        formatted to include them directly in the context
        """
        try:
            query_lower = query_text.lower().replace('?', '')
            query_words = set(query_lower.split())
            
            dapp_keywords = ["dapp", "app", "application", "create", "make", "build", "develop"]
            swap_keywords = ["swap", "exchange", "dex"]
            token_keywords = ["token", "erc20", "contract"]
            nft_keywords = ["nft", "collection", "marketplace"]
            
            is_dapp_query = any(kw in query_lower for kw in dapp_keywords)
            is_swap_query = any(kw in query_lower for kw in swap_keywords)
            is_token_query = any(kw in query_lower for kw in token_keywords)
            is_nft_query = any(kw in query_lower for kw in nft_keywords)
            
            all_videos = []
            with open('config/youtube_videos.json', 'r', encoding='utf-8-sig') as f:
                yt_data = json.loads(f.read().strip())
                
                def extract_videos(data, current_path=[]):
                    if isinstance(data, dict):
                        for key, value in data.items():
                            if isinstance(value, list) and all(isinstance(item, dict) for item in value):
                                for video in value:
                                    if 'url' in video and 'title' in video:
                                        if 'categories' not in video:
                                            video['categories'] = []
                                        video['categories'].extend(current_path + [key])
                                        all_videos.append(video)
                            elif isinstance(value, dict):
                                extract_videos(value, current_path + [key])
                            elif isinstance(value, list):
                                for item in value:
                                    if isinstance(item, dict):
                                        extract_videos(item, current_path + [key])
                
                extract_videos(yt_data)
            
            relevant_videos = []
            
            if "tutorial" in query_lower or "video" in query_lower or "lista" in query_lower:
                logger.info(f"Consulta general sobre videos detectada: '{query_text}'")
                for video in all_videos:
                    if 'url' in video and 'title' in video:
                        doc = Document(
                            page_content=video.get('description', ''),
                            metadata={
                                'source': video.get('url', ''),
                                'type': 'youtube',
                                'title': video.get('title', ''),
                                'duration': video.get('duration', 'N/A'),
                                'difficulty': video.get('difficulty', 'Beginner'),
                                'topics': video.get('topics', []),
                                'related_docs': video.get('related_docs', [])
                            }
                        )
                        relevant_videos.append(doc)
            
                logger.info(f"Devolviendo {len(relevant_videos)} videos para consulta general")
                return relevant_videos
            
            filtered_videos = []
            
            if is_dapp_query:
                for video in all_videos:
                    if 'dapp' in ' '.join(video.get('keywords', [])).lower() or 'dapp' in video.get('title', '').lower():
                        filtered_videos.append(video)
            
            if is_swap_query:
                for video in all_videos:
                    if any(kw in ' '.join(video.get('keywords', [])).lower() or kw in video.get('title', '').lower() 
                           for kw in ['swap', 'exchange', 'dex']):
                        filtered_videos.append(video)
            
            if is_token_query:
                for video in all_videos:
                    if any(kw in ' '.join(video.get('keywords', [])).lower() or kw in video.get('title', '').lower() 
                           for kw in ['token', 'erc20', 'contract']):
                        filtered_videos.append(video)
            
            if is_nft_query:
                for video in all_videos:
                    if any(kw in ' '.join(video.get('keywords', [])).lower() or kw in video.get('title', '').lower() 
                           for kw in ['nft', 'collection', 'marketplace']):
                        filtered_videos.append(video)
            
            unique_urls = set()
            unique_videos = []
            for video in filtered_videos:
                if video.get('url') not in unique_urls:
                    unique_urls.add(video.get('url'))
                    unique_videos.append(video)
            
            for video in unique_videos:
                if 'url' in video and 'title' in video:
                    doc = Document(
                        page_content=video.get('description', ''),
                        metadata={
                            'source': video.get('url', ''),
                            'type': 'youtube',
                            'title': video.get('title', ''),
                            'duration': video.get('duration', 'N/A'),
                            'difficulty': video.get('difficulty', 'Beginner'),
                            'topics': video.get('topics', []),
                            'related_docs': video.get('related_docs', [])
                        }
                    )
                    relevant_videos.append(doc)
            
            logger.info(f"Returning {len(relevant_videos)} relevant videos for the query")
            return relevant_videos
        
        except Exception as e:
            logger.error(f"Error finding videos by query: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []