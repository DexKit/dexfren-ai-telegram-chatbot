import os
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from youtube_transcript_api import YouTubeTranscriptApi
from langchain.schema import Document
from dotenv import load_dotenv
from typing import List
import re

load_dotenv()

class DexKitKnowledgeBase:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings()
        self.db = None
        
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
            
            # Try different language combinations
            for langs in [
                ['en'],
                ['pt'],
                ['es'],
                ['en', 'pt'],
                ['pt', 'en'],
                ['pt', 'es'],
                ['en', 'es'],
                ['pt', 'en', 'es']
            ]:
                try:
                    transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
                    print(f"Found subtitles in {langs} for video {video_url}")
                    break
                except Exception:
                    continue
                    
            if not transcript_list:
                print(f"Warning: No subtitles found for video {video_url}")
                return []
                
            full_transcript = ' '.join([entry['text'] for entry in transcript_list])
            
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )
            splits = text_splitter.split_text(full_transcript)
            
            detected_lang = transcript_list[0].get('language', 'unknown')
            
            return [
                Document(
                    page_content=split,
                    metadata={
                        'source': video_url,
                        'type': 'youtube',
                        'language': detected_lang
                    }
                ) for split in splits
            ]
            
        except Exception as e:
            print(f"Warning: Could not process video {video_url}: {str(e)}")
            return []

    def create_knowledge_base(self, pdf_directory: str = None, youtube_urls: List[str] = None):
        """Create the knowledge base from PDFs and YouTube videos"""
        documents = []
        
        # Process PDFs if directory exists
        if pdf_directory:
            print("Processing PDF documents...")
            documents.extend(self.process_pdf(pdf_directory))
        
        # Process YouTube videos
        if youtube_urls:
            print(f"Processing {len(youtube_urls)} videos...")
            for url in youtube_urls:
                print(f"Processing video: {url}")
                documents.extend(self.process_youtube(url))
        
        print(f"Creating vector knowledge base with {len(documents)} documents...")
        
        # Create new Chroma instance with documents
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