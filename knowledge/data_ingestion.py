from .youtube_processor import YouTubeProcessor
from .documentation_manager import DocumentationManager
from .platform_processor import PlatformProcessor
from typing import List, Dict
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings
import logging
import os
from dotenv import load_dotenv

load_dotenv()

class DexKitKnowledgeBase:
    def __init__(self):
        self.youtube_processor = YouTubeProcessor()
        self.doc_manager = DocumentationManager()
        self.platform_processor = PlatformProcessor()
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=os.getenv('OPENAI_API_KEY')
        )
        self.docs: List[Document] = []
        
    def build_knowledge_base(self) -> List[Document]:
        """Builds the complete knowledge base"""
        logging.info("Processing YouTube videos...")
        videos = self.youtube_processor.process_videos()
        for video in videos:
            self.docs.append(Document(
                page_content=f"Title: {video.title}\n\nDescription: {video.description}",
                metadata={
                    'source': video.url,
                    'type': 'youtube_metadata',
                    'category': video.category,
                    'priority': video.priority,
                    'language': video.language,
                    'video_id': video.video_id
                }
            ))
            
            if video.transcript:
                chunks = [video.transcript[i:i+1000] for i in range(0, len(video.transcript), 800)]
                for i, chunk in enumerate(chunks):
                    self.docs.append(Document(
                        page_content=f"Transcript Part {i+1}: {chunk}",
                        metadata={
                            'source': video.url,
                            'type': 'youtube_transcript',
                            'category': video.category,
                            'priority': video.priority,
                            'language': video.language,
                            'video_id': video.video_id,
                            'chunk': i+1,
                            'total_chunks': len(chunks)
                        }
                    ))
        
        logging.info("Processing documentation...")
        for doc_ref in self.doc_manager.docs_map.values():
            content_chunks = [doc_ref.content[i:i+1000] for i in range(0, len(doc_ref.content), 800)]
            
            self.docs.append(Document(
                page_content=f"Title: {doc_ref.title}\n\nDescription: {doc_ref.description}",
                metadata={
                    'source': doc_ref.url,
                    'type': 'documentation_meta',
                    'category': doc_ref.category,
                    'last_updated': doc_ref.last_updated
                }
            ))
            
            for i, chunk in enumerate(content_chunks):
                self.docs.append(Document(
                    page_content=f"Content Part {i+1}: {chunk}",
                    metadata={
                        'source': doc_ref.url,
                        'type': 'documentation_content',
                        'category': doc_ref.category,
                        'last_updated': doc_ref.last_updated,
                        'chunk': i+1,
                        'total_chunks': len(content_chunks)
                    }
                ))
        
        logging.info("Processing platform URLs...")
        platform_data = self.platform_processor.process_platform_urls()
        for data in platform_data:
            self.docs.append(Document(
                page_content=f"Title: {data.title}\n\nDescription: {data.description}",
                metadata={
                    'source': data.url,
                    'type': f'platform_{data.type}',
                    'category': data.category,
                    'section': data.section
                }
            ))
            
            if data.content:
                content_chunks = [data.content[i:i+1000] for i in range(0, len(data.content), 800)]
                for i, chunk in enumerate(content_chunks):
                    self.docs.append(Document(
                        page_content=f"Content Part {i+1}: {chunk}",
                                metadata={
                            'source': data.url,
                            'type': f'platform_{data.type}_content',
                            'category': data.category,
                            'section': data.section,
                            'chunk': i+1,
                            'total_chunks': len(content_chunks)
                        }
                    ))
        
        logging.info(f"Total of documents processed: {len(self.docs)}")
        return self.docs

    def query_knowledge(self, query: str, k: int = 3) -> List[Document]:
        """Query the knowledge base"""
        if not hasattr(self, 'vectorstore'):
            raise ValueError("Knowledge base not initialized. Run build_knowledge_base() first.")
        return self.vectorstore.similarity_search(query, k=k)