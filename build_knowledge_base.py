from knowledge.data_ingestion import DexKitKnowledgeBase
import json
import shutil
import os
from typing import Optional, List, Callable, Dict, Tuple
from tqdm import tqdm
from datetime import datetime
import hashlib
import logging

logger = logging.getLogger(__name__)

knowledge_base = DexKitKnowledgeBase(
    chunk_size=500,
    chunk_overlap=50
)

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
    """Load YouTube URLs from both config files"""
    try:
        urls = set()
        
        with open('config/youtube_videos.json', 'r', encoding='utf-8-sig') as f:
            content = f.read().strip()
            data = json.loads(content)
            
            def extract_urls(obj):
                if isinstance(obj, dict):
                    if 'url' in obj:
                        urls.add(obj['url'])
                    for value in obj.values():
                        extract_urls(value)
                elif isinstance(obj, list):
                    for item in obj:
                        extract_urls(item)
            
            extract_urls(data)
        
        with open('config/agent_instructions.json', 'r') as f:
            agent_config = json.load(f)
            content_mapping = agent_config['instructions'].get('content_mapping', {})
            
            for category in content_mapping.values():
                if 'primary_video' in category:
                    urls.add(category['primary_video']['url'])
                for video in category.get('secondary_videos', []):
                    urls.add(video['url'])
        
        print(f"Successfully loaded {len(urls)} YouTube URLs")
        return list(urls)
    except Exception as e:
        print(f"Error loading YouTube URLs: {str(e)}")
        return []

def calculate_file_hash(filepath: str) -> str:
    """Calculate SHA-256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def calculate_json_hash(json_data: dict) -> str:
    """Calculate hash of JSON data"""
    json_str = json.dumps(json_data, sort_keys=True)
    return hashlib.sha256(json_str.encode()).hexdigest()

def load_training_hashes() -> Dict:
    """Load saved hashes from knowledge base"""
    hash_file = './knowledge_base/.training_hashes.json'
    if os.path.exists(hash_file):
        with open(hash_file, 'r') as f:
            return json.load(f)
    return {}

def save_training_hashes(hashes: Dict):
    """Save current hashes to knowledge base"""
    hash_file = './knowledge_base/.training_hashes.json'
    os.makedirs('./knowledge_base', exist_ok=True)
    with open(hash_file, 'w') as f:
        json.dump(hashes, f, indent=2)

def check_critical_files_changed() -> Tuple[bool, List[str]]:
    """
    Check if any critical files have changed
    Returns: (has_changes, changed_files)
    """
    critical_files = {
        'docs': './docs',
        'platform_urls': './config/platform_urls.json',
        'documentation_urls': './config/documentation_urls.json',
        'youtube_videos': './config/youtube_videos.json',
        'agent_instructions': './config/agent_instructions.json'
    }
    
    previous_hashes = load_training_hashes()
    current_hashes = {}
    changed_files = []
    
    if os.path.exists(critical_files['docs']):
        pdf_hashes = {}
        for filename in os.listdir(critical_files['docs']):
            if filename.endswith('.pdf'):
                filepath = os.path.join(critical_files['docs'], filename)
                pdf_hashes[filename] = calculate_file_hash(filepath)
        current_hashes['docs'] = pdf_hashes
        
        if 'docs' not in previous_hashes or previous_hashes['docs'] != pdf_hashes:
            changed_files.append('PDF documents')
    
    for key, filepath in critical_files.items():
        if key == 'docs':
            continue
            
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
                    current_hashes[key] = calculate_json_hash(data)
                    
                if (key not in previous_hashes or 
                    previous_hashes[key] != current_hashes[key]):
                    changed_files.append(filepath)
            except Exception as e:
                print(f"Error checking {filepath}: {str(e)}")
                current_hashes[key] = None
    
    has_changes = bool(changed_files)
    
    if not has_changes:
        print("\n=== No changes detected in critical files ===")
        print("✓ PDFs: No changes")
        print("✓ Platform URLs: No changes")
        print("✓ Documentation URLs: No changes")
        print("✓ YouTube Videos: No changes")
        print("\nSkipping training process...")
    else:
        print("\n=== Changes detected in: ===")
        for file in changed_files:
            print(f"• {file}")
        save_training_hashes(current_hashes)
    
    return has_changes, changed_files

def get_file_hash(filepath: str) -> str:
    """Get a unique hash of the file based on its content and modification date"""
    return f"{os.path.getmtime(filepath)}_{os.path.getsize(filepath)}"

def load_processed_files() -> Dict:
    """Load the processed files registry"""
    processed_files_path = './knowledge_base/.processed_files.json'
    if os.path.exists(processed_files_path):
        with open(processed_files_path, 'r') as f:
            return json.load(f)
    return {}

def save_processed_files(processed_files: Dict):
    """Save the processed files registry"""
    processed_files_path = './knowledge_base/.processed_files.json'
    os.makedirs('./knowledge_base', exist_ok=True)
    with open(processed_files_path, 'w') as f:
        json.dump(processed_files, f, indent=2)

def check_for_updates() -> tuple[List[str], List[str]]:
    """
    Check for new files or changes
    Returns: (new_pdfs, new_videos)
    """
    processed_files = load_processed_files()
    new_pdfs = []
    new_videos = []

    if os.path.exists('./docs'):
        for filename in os.listdir('./docs'):
            if filename.endswith('.pdf'):
                filepath = os.path.join('./docs', filename)
                file_hash = get_file_hash(filepath)
                
                if (filename not in processed_files.get('pdfs', {}) or 
                    processed_files['pdfs'][filename]['hash'] != file_hash):
                    new_pdfs.append(filepath)
                else:
                    print(f"Skipping unchanged PDF: {filename}")

    if 'youtube_urls' in processed_files:
        current_urls = set(load_youtube_urls())
        processed_urls = set(processed_files['youtube_urls'])
        new_videos = list(current_urls - processed_urls)
        if not new_videos:
            print("No new YouTube videos to process")

    return new_pdfs, new_videos

def update_knowledge_base(new_pdfs: Optional[List[str]] = None, 
                        new_youtube_urls: Optional[List[str]] = None,
                        callback: Optional[Callable] = None) -> bool:
    """
    Update the knowledge base incrementally
    """
    try:
        if callback:
            callback("Starting incremental update...")

        if new_pdfs:
            if callback:
                callback(f"Processing {len(new_pdfs)} new PDFs...")
            knowledge_base.process_new_pdfs(new_pdfs)

        if new_youtube_urls:
            if callback:
                callback(f"Processing {len(new_youtube_urls)} new videos...")
            knowledge_base.process_new_videos(new_youtube_urls)

        return True

    except Exception as e:
        if callback:
            callback(f"Error in incremental update: {str(e)}")
        print(f"Error in incremental update: {str(e)}")
        return False

def main(callback=None):
    print("\n=== Starting DexKit Knowledge Base Creation (GPT-3.5) ===\n")
    
    try:
        has_changes, changed_files = check_critical_files_changed()
        
        if not has_changes:
            return 0
            
        if not knowledge_base.db:
            knowledge_base.create_knowledge_base()
        
        new_pdfs, new_videos = check_for_updates()
        
        if not new_pdfs and not new_videos:
            print("No changes detected.")
            print("✓ PDFs: No changes")
            print("✓ Videos: No changes")
            return 0

        print("\n=== Detected Updates ===")
        if new_pdfs:
            print(f"• New or modified PDFs: {len(new_pdfs)}")
            for pdf in new_pdfs:
                print(f"  - {os.path.basename(pdf)}")
        
        if new_videos:
            print(f"• Nuevos videos: {len(new_videos)}")
            for video in new_videos:
                print(f"  - {video}")

        if callback:
            callback("Starting update processing...")

        if new_pdfs:
            print("\n=== Processing PDFs ===")
            for pdf_path in tqdm(new_pdfs, desc="Processing PDFs"):
                try:
                    knowledge_base.process_new_pdfs([pdf_path])
                    processed_files = load_processed_files()
                    processed_files[os.path.basename(pdf_path)] = {
                        'hash': get_file_hash(pdf_path),
                        'last_processed': datetime.now().isoformat()
                    }
                    save_processed_files(processed_files)
                except Exception as e:
                    print(f"Error processing {pdf_path}: {str(e)}")

        if new_videos:
            print("\n=== Processing Videos ===")
            for video_url in tqdm(new_videos, desc="Processing Videos"):
                try:
                    knowledge_base.process_new_videos([video_url])
                    processed_files = load_processed_files()
                    if 'youtube_urls' not in processed_files:
                        processed_files['youtube_urls'] = []
                    processed_files['youtube_urls'].append(video_url)
                    save_processed_files(processed_files)
                except Exception as e:
                    print(f"Error processing {video_url}: {str(e)}")

        print("\n=== Knowledge base updated successfully! ===")
        if callback:
            callback("Knowledge base updated successfully!")
        
        return 0
        
    except Exception as e:
        error_msg = f"\n! Error in main process: {str(e)}"
        print(error_msg)
        if callback:
            callback(error_msg)
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