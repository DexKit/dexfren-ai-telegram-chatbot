from knowledge.data_ingestion import DexKitKnowledgeBase
import json
import shutil
import os

def clean_previous_training():
    """Clean previous training data but preserve docs and config"""
    directories_to_clean = [
        './knowledge_base',  # Vector store
        './__pycache__',    # Python cache
        './knowledge/__pycache__'
    ]
    
    print("Cleaning previous training data...")
    
    for directory in directories_to_clean:
        if os.path.exists(directory):
            try:
                shutil.rmtree(directory)
                print(f"✓ Cleaned {directory}")
            except Exception as e:
                print(f"! Error cleaning {directory}: {str(e)}")

def load_youtube_urls():
    """Load YouTube URLs from config file"""
    with open('config/youtube_videos.json', 'r') as f:
        data = json.load(f)
        return data['video_list']

def main():
    print("\n=== Starting DexKit Knowledge Base Creation ===\n")
    
    # Clean previous training
    clean_previous_training()
    
    print("\n=== Initializing new training ===\n")
    
    knowledge_base = DexKitKnowledgeBase()
    youtube_urls = load_youtube_urls()
    
    print(f"\n=== Processing {len(youtube_urls)} videos ===")
    print("\n=== Processing documentation and platform pages ===")
    
    knowledge_base.create_knowledge_base(
        pdf_directory="./docs",
        youtube_urls=youtube_urls
    )
    
    print("\n=== Knowledge base created successfully! ===")
    print("\nReady to use with the Telegram bot.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n! Error: {str(e)}")
        exit(1) 