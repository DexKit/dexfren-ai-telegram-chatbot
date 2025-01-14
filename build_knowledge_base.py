from knowledge.data_ingestion import DexKitKnowledgeBase
from langchain_community.vectorstores import Chroma
import json
import shutil
import os
import logging

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

def main():
    print("\n=== Starting DexKit Knowledge Base Creation (GPT-3.5) ===\n")
    
    try:
        clean_previous_training()
        
        print("\n=== Initializing new training ===\n")
        
        knowledge_base = DexKitKnowledgeBase()
        
        documents = knowledge_base.build_knowledge_base()
        
        print(f"\nProcessing {len(documents)} documents...")
        
        vectorstore = Chroma.from_documents(
            documents=documents,
            embedding=knowledge_base.embeddings,
            persist_directory="./knowledge_base"
        )
        vectorstore.persist()
        
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
        logging.basicConfig(level=logging.INFO)
        exit_code = main()
        exit(exit_code)
    except Exception as e:
        print(f"\n! Critical Error: {str(e)}")
        exit(1) 