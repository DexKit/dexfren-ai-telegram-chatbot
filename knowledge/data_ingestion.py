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
        
    def process_youtube(self, video_url: str) -> List[Document]:
        """Process a YouTube video using youtube_transcript_api"""
        try:
            video_id = self.get_video_id(video_url)
            
            # Try first with English
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
            except:
                # If no English, try with Spanish
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['es'])
            
            # Combine the transcript text
            full_transcript = ' '.join([entry['text'] for entry in transcript_list])
            
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )
            splits = text_splitter.split_text(full_transcript)
            
            # Create documents in the correct format
            return [
                Document(
                    page_content=split,
                    metadata={'source': video_url, 'type': 'youtube'}
                ) for split in splits
            ]
            
        except Exception as e:
            print(f"Error processing video {video_url}: {str(e)}")
            return []

    def process_pdf(self, pdf_path) -> List[Document]:
        """Process a PDF file and add it to the knowledge base"""
        try:
            loader = PyPDFLoader(pdf_path)
            pages = loader.load()
            
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )
            splits = text_splitter.split_documents(pages)
            
            return splits
        except Exception as e:
            print(f"Error processing PDF {pdf_path}: {str(e)}")
            return []

    def create_knowledge_base(self, pdf_directory, youtube_urls):
        """Create a complete knowledge base"""
        print("Starting document processing...")
        all_documents = []
        
        # Process PDFs
        if os.path.exists(pdf_directory):
            for filename in os.listdir(pdf_directory):
                if filename.endswith(".pdf"):
                    pdf_path = os.path.join(pdf_directory, filename)
                    documents = self.process_pdf(pdf_path)
                    all_documents.extend(documents)
        
        # Process YouTube videos
        print(f"Processing {len(youtube_urls)} videos...")
        for url in youtube_urls:
            print(f"Processing video: {url}")
            documents = self.process_youtube(url)
            all_documents.extend(documents)
        
        if all_documents:
            print(f"Creating vector knowledge base with {len(all_documents)} documents...")
            self.db = Chroma.from_documents(
                all_documents,
                self.embeddings,
                persist_directory="./knowledge_base"
            )
            self.db.persist()
            print("Knowledge base created successfully!")
        else:
            print("Could not process any documents.")
        
    def query_knowledge(self, query, k=3):
        """Query the knowledge base"""
        if not self.db:
            raise ValueError("Knowledge base not initialized")
        
        results = self.db.similarity_search(query, k=k)
        return results