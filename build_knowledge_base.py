from knowledge.data_ingestion import DexKitKnowledgeBase
import json
import shutil
import os

def clean_previous_training():
    """Clean previous training data but preserve docs and config"""
    directories_to_clean = [
        './knowledge_base',
        './__pycache__',
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

def validate_training_progress(progress_data):
    """Validates training quality in real-time"""
    if progress_data['document_count'] < 10:
        print("Warning: Low document count for training")
        
    if progress_data['average_chunk_size'] < 200:
        print("Warning: Chunks too small")
        
    return True

def main():
    print("\n=== Starting DexKit Knowledge Base Creation (GPT-3.5) ===\n")
    
    try:
        clean_previous_training()
        
        print("\n=== Initializing new training ===\n")
        
        knowledge_base = DexKitKnowledgeBase(
            chunk_size=750,
            chunk_overlap=150
        )
        
        youtube_urls = load_youtube_urls()
        if not youtube_urls:
            print("Warning: No YouTube URLs loaded")
        
        print(f"\n=== Processing {len(youtube_urls)} videos ===")
        
        success = knowledge_base.create_knowledge_base(
            pdf_directory="./docs" if os.path.exists("./docs") else None,
            youtube_urls=youtube_urls,
            validation_callback=validate_training_progress
        )
        
        if success:
            print("\nKnowledge base created successfully!")
            print("\nReady to use with the Telegram bot.")
            return 0
        else:
            print("\nError: Knowledge base creation was not successful")
            return 1
            
    except Exception as e:
        print(f"\n! Error in main process: {str(e)}")
        print("Stack trace:")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        exit(exit_code)
    except Exception as e:
        print(f"\n! Critical Error: {str(e)}")
        exit(1) 