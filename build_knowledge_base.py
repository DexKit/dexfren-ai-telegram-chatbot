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
    try:
        with open('config/youtube_videos.json', 'r', encoding='utf-8-sig') as f:
            content = f.read().strip()
            data = json.loads(content)
            urls = data.get('video_list', [])
            print(f"Successfully loaded {len(urls)} YouTube URLs")
            return urls
    except Exception as e:
        print(f"Error loading YouTube URLs: {str(e)}")
        return []

def main():
    print("\n=== Starting DexKit Knowledge Base Creation (GPT-3.5) ===\n")
    
    try:
        # Clean previous training
        clean_previous_training()
        
        print("\n=== Initializing new training ===\n")
        
        # Initialize knowledge base with specific parameters
        knowledge_base = DexKitKnowledgeBase(
            chunk_size=500,
            chunk_overlap=50
        )
        
        # Load YouTube URLs
        youtube_urls = load_youtube_urls()
        if not youtube_urls:
            print("Warning: No YouTube URLs loaded")
        
        print(f"\n=== Processing {len(youtube_urls)} videos ===")
        print("\n=== Processing documentation and platform pages ===")
        
        # Create knowledge base
        knowledge_base.create_knowledge_base(
            pdf_directory="./docs" if os.path.exists("./docs") else None,
            youtube_urls=youtube_urls
        )
        
        print("\n=== Knowledge base created successfully! ===")
        print("\nReady to use with the Telegram bot.")
        
    except Exception as e:
        print(f"\n! Error in main process: {str(e)}")
        print("Stack trace:")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        exit(exit_code)
    except Exception as e:
        print(f"\n! Critical Error: {str(e)}")
        exit(1) 