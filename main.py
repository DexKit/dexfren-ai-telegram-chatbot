from dotenv import load_dotenv
import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from swarm import Swarm, Agent
from knowledge.data_ingestion import DexKitKnowledgeBase
from langchain_chroma import Chroma
from knowledge.documentation_manager import DocumentationManager
from chromadb.config import Settings
import sys
from typing import Optional
import json
from langdetect import detect

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

load_dotenv()

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

client = Swarm()
knowledge_base = DexKitKnowledgeBase()

active_conversations = {}

docs_manager = DocumentationManager()

dexkit_agent = Agent(
    name="DexFren",
    instructions="""
    You are DexFren, DexKit's support assistant. Follow these rules STRICTLY:

    CORE BEHAVIOR:
    1. Use ONLY knowledge base info from:
       - Platform documentation
       - Official tutorials
       - Verified platform URLs
    2. If unsure, ask SPECIFIC clarifying questions about:
       - Network being used
       - Product version
       - Current setup details
    3. Keep responses focused and structured
    4. Use detailed examples with actual configurations
    5. Verify technical accuracy before responding

    PLATFORM CONTENT RULES:
    1. Use ONLY content from platform_processor for:
       - Documentation references
       - Product information
       - Feature descriptions
       - Technical specifications
    2. Maintain content hierarchy as defined in platform URLs
    3. Respect content categories and sections
    4. Use metadata for proper context

    NETWORK SUPPORT:
    • Primary Networks:
      - Ethereum (mainnet, sepolia, goerli)
      - BSC (mainnet, testnet)
      - Polygon
      - Arbitrum
      - Avalanche
      - Optimism
    • Secondary Networks:
      - Fantom
      - Base
      - Blast (mainnet, testnet)
      - Pulsechain (limited support)

    TOKEN CREATION GUIDELINES:
    1. Direct ALL token creation to DexGenerator forms
    2. Verify network compatibility first
    3. Include gas fee estimates
    4. Explain contract deployment process
    5. Highlight network-specific requirements

    RESPONSE FORMAT:
    1. Start with direct, actionable answer
    2. Use clear, numbered steps
    3. Include relevant configuration examples
    4. Add verification steps
    5. Suggest next actions

    FORMATTING:
    • Links: [text](URL)
    • Important: *text*
    • Technical: _text_
    • Config: `text`
    • Networks: **text**

    PROHIBITED:
    • External resources
    • Unofficial URLs
    • Unsupported features
    • Personal opinions
    • Assumptions
    • Incomplete information

    COMMUNITY ENGAGEMENT:
    1. Use official social channels only
    2. Prioritize documentation for technical help
    3. Direct to community for general discussion
    4. Maintain professional tone
    5. Focus on verified information
    """,
    model="gpt-3.5-turbo"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = """
Welcome, fren! 👋

I can help you with:
- Using DexAppBuilder
- Creating your DAPP
- Platform features and customization
- Technical guidance

How can I assist you today?
    """
    await update.message.reply_text(welcome_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages and generate responses"""
    try:
        user_message = update.message.text
        
        try:
            message_lang = detect(user_message)
        except:
            message_lang = 'en'
            
        relevant_docs = knowledge_base.query_knowledge(
            user_message,
            k=3
        )
        
        context_text = "\n".join([doc.page_content for doc in relevant_docs])
        
        if message_lang == 'es':
            system_prompt = """Eres un asistente experto en DexKit y DexAppBuilder. 
            Responde siempre en español de manera clara y concisa."""
        else:
            system_prompt = """You are an expert assistant for DexKit and DexAppBuilder. 
            Always respond in English in a clear and concise manner."""
            
        response = await generate_response(
            system_prompt=system_prompt,
            user_message=user_message,
            context=context_text
        )
        
        await update.message.reply_text(response)
        
    except Exception as e:
        error_msg = "Lo siento, ha ocurrido un error." if message_lang == 'es' else "Sorry, an error occurred."
        await update.message.reply_text(error_msg)
        logging.error(f"Error in handle_message: {str(e)}")

async def generate_response(system_prompt: str, user_message: str, context: str) -> str:
    """
    Generate a response using the DexFren agent with the provided context.
    
    Args:
        system_prompt (str): System prompt based on the detected language
        user_message (str): User message
        context (str): Relevant context from the knowledge base
    
    Returns:
        str: Response generated by the agent
    """
    try:
        full_message = f"""
Context from knowledge base:
{context}

User message:
{user_message}
"""
        response = await client.chat(
            agent=dexkit_agent,
            system_prompt=system_prompt,
            message=full_message
        )
        
        return response.content
        
    except Exception as e:
        logging.error(f"Error generating response: {str(e)}")
        return "Sorry, an error occurred while generating the response."

async def keep_typing(bot, chat_id):
    try:
        while True:
            await bot.send_chat_action(
                chat_id=chat_id,
                action="typing"
            )
            await asyncio.sleep(3)
    except asyncio.CancelledError:
        pass

def process_context(knowledge_base, message_text):
    relevant_info = knowledge_base.query_knowledge(message_text)
    
    priority_keywords = [
        'contract', 'token', 'erc20', 'dapp', 'builder', 
        'template', 'swap', 'exchange', 'wallet', 'nft'
    ]
    
    priority_docs = []
    secondary_docs = []
    
    for doc in relevant_info:
        content_lower = doc.page_content.lower()
        score = sum(2 for keyword in priority_keywords if keyword in content_lower)
        score += sum(3 for word in message_text.lower().split() if word in content_lower)
        
        if score > 2:
            priority_docs.append((score, doc))
        else:
            secondary_docs.append((score, doc))
    
    priority_docs.sort(reverse=True)
    secondary_docs.sort(reverse=True)
    
    ordered_docs = [doc for _, doc in priority_docs[:3] + secondary_docs[:2]]
    
    return "\n\nRelevant Context:\n" + "\n---\n".join([doc.page_content for doc in ordered_docs])

CHROMA_SETTINGS = Settings(
    anonymized_telemetry=False,
    allow_reset=True
)

def ensure_knowledge_base_directory():
    kb_dir = "./knowledge_base"
    if not os.path.exists(kb_dir):
        os.makedirs(kb_dir)
        print(f"Created knowledge base directory: {kb_dir}")
    return kb_dir

def initialize_knowledge_base() -> Optional[Chroma]:
    """Initialize the knowledge base with proper error handling"""
    try:
        kb_dir = ensure_knowledge_base_directory()
        return Chroma(
            persist_directory=kb_dir,
            embedding_function=knowledge_base.embeddings,
            client_settings=CHROMA_SETTINGS
        )
    except Exception as e:
        logging.error(f"Failed to initialize knowledge base: {e}")
        return None

def load_youtube_metadata():
    """Load YouTube metadata with proper error handling"""
    try:
        youtube_config_path = os.path.join('config', 'youtube_videos.json')
        if not os.path.exists(youtube_config_path):
            logging.warning(f"YouTube config file not found at {youtube_config_path}")
            return {}
            
        with open(youtube_config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading YouTube metadata: {e}")
        return {}

async def shutdown():
    """Graceful shutdown function for the bot"""
    if 'app' in globals() and app.is_running():
        await app.shutdown()
    print("Bot stopped gracefully")

def main():
    """Initialize and run the bot"""
    try:
        knowledge_base.db = initialize_knowledge_base()
        if not knowledge_base.db:
            logging.error("Could not initialize knowledge base. Exiting...")
            sys.exit(1)
            
        global app
        app = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()
        
        if not os.getenv('TELEGRAM_BOT_TOKEN'):
            logging.error("TELEGRAM_BOT_TOKEN not found in environment variables")
            sys.exit(1)
            
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        ))
        
        print("Starting bot...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logging.error(f"Critical error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    main()