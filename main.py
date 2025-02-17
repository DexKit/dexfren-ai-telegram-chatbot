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
from utils.logger import setup_logger

logger = setup_logger()

# Initialize Swarm and Knowledge Base
client = Swarm()
knowledge_base = DexKitKnowledgeBase()

# Store active conversations
active_conversations = {}

# Initialize documentation manager
docs_manager = DocumentationManager()

def load_agent_config():
    """Load agent configuration from JSON file"""
    try:
        config_path = os.path.join('config', 'agent_instructions.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
        # Convert config to formatted instruction string
        instructions = format_agent_instructions(config['instructions'])
        
        return {
            'name': config['name'],
            'model': config['model'],
            'instructions': instructions
        }
    except Exception as e:
        logging.error(f"Error loading agent config: {e}")
        sys.exit(1)

def format_agent_instructions(config):
    """Format the JSON config into a structured instruction string"""
    sections = []
    
    # Core behavior
    sections.append("CORE BEHAVIOR:")
    sections.extend([f"{i+1}. {rule}" for i, rule in enumerate(config['core_behavior'])])
    
    # URLs
    sections.append("\nURL RULES (MANDATORY):")
    sections.append("1. ONLY use URLs from this approved list:\n")
    for category, urls in config['approved_urls'].items():
        sections.append(f"\n{category.replace('_', ' ').title()}:")
        if isinstance(urls, dict):
            for name, url in urls.items():
                if isinstance(url, dict):
                    sections.append(f"• {name.replace('_', ' ').title()}:")
                    for sub_name, sub_url in url.items():
                        sections.append(f"  - {sub_name.replace('_', ' ').title()}: {sub_url}")
                else:
                    sections.append(f"• {name.replace('_', ' ').title()}: {url}")
        else:
            sections.append(f"• {urls}")
    
    # Networks
    sections.append("\nAvailable Networks:")
    sections.extend([f"• {network}" for network in config['available_networks']])
    
    # Token Creation Rules
    sections.append("\nCRITICAL RULES FOR TOKEN CREATION:")
    sections.extend([f"{i+1}. {rule}" for i, rule in enumerate(config['token_creation_rules'])])
    
    # Response Format
    sections.append("\nRESPONSE FORMAT:")
    sections.extend([f"{i+1}. {fmt}" for i, fmt in enumerate(config['response_format'])])
    
    # Formatting
    sections.append("\nFORMATTING:")
    for key, value in config['formatting'].items():
        sections.append(f"• {key.replace('_', ' ').title()}: {value}")
    
    # Prohibited
    sections.append("\nSTRICTLY PROHIBITED:")
    sections.extend([f"• {item}" for item in config['prohibited']])
    
    # Social Media Rules
    sections.append("\nSOCIAL MEDIA RULES:")
    sections.extend([f"{i+1}. {rule}" for i, rule in enumerate(config['social_media_rules'])])
    
    return "\n".join(sections)

# Initialize the agent with config
agent_config = load_agent_config()
dexkit_agent = Agent(
    name=agent_config['name'],
    instructions=agent_config['instructions'],
    model=agent_config['model']
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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages."""
    try:
        # Log incoming message
        logger.info(f"Message from {update.effective_user.username}: {update.message.text}")
        
        # Check if message is in private chat or for the bot in groups
        is_private = update.message.chat.type == 'private'
        is_bot_mentioned = bool(update.message.entities and 
            any(entity.type == 'mention' and 
                context.bot.username in update.message.text[entity.offset:entity.offset + entity.length] 
                for entity in update.message.entities))
        is_reply_to_bot = bool(update.message.reply_to_message and 
            update.message.reply_to_message.from_user.id == context.bot.id)
        
        # Process if private chat OR bot is mentioned/replied to in groups
        if not (is_private or is_bot_mentioned or is_reply_to_bot):
            return
            
        chat_id = update.message.chat_id
        message_text = update.message.text
        
        # Start typing only when we know we'll respond
        await context.bot.send_chat_action(
            chat_id=chat_id,
            action="typing"
        )
        
        if chat_id not in active_conversations:
            active_conversations[chat_id] = []
            
        active_conversations[chat_id].append({
            "role": "user",
            "content": message_text
        })
        
        relevant_info = knowledge_base.query_knowledge(message_text)
        context_text = "\n".join([doc.page_content for doc in relevant_info])
        
        # Improve conversation context
        conversation = [
            {"role": "system", "content": f"{dexkit_agent.instructions}\n\n{context_text}"},
            {"role": "system", "content": "Remember to be specific and provide actionable steps."}
        ]
        
        # Add context from last 3 interactions for better continuity
        if len(active_conversations[chat_id]) > 1:
            conversation.extend(active_conversations[chat_id][-6:])
        
        # Add current message
        conversation.append({
            "role": "user",
            "content": f"Question: {message_text}\nPlease provide a detailed and specific response."
        })
        
        typing_task = asyncio.create_task(keep_typing(context.bot, chat_id))
        
        try:
            response = client.run(
                agent=dexkit_agent,
                messages=conversation,
                stream=False
            )
            
            bot_response = response.messages[-1]["content"]
            active_conversations[chat_id].append({
                "role": "assistant",
                "content": bot_response
            })
            
        finally:
            # Cancel typing before sending message
            typing_task.cancel()
            await asyncio.sleep(0.1)  # Small delay to ensure typing is cancelled
        
        # Log outgoing message
        logger.info(f"Response to {update.effective_user.username}: {bot_response}")
        
        # Send message after typing is cancelled
        await update.message.reply_text(
            bot_response,
            reply_to_message_id=update.message.message_id,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        error_msg = f"Error processing message: {str(e)}"
        logger.error(error_msg)
        await update.message.reply_text("Lo siento, hubo un error procesando tu mensaje.")

async def keep_typing(bot, chat_id):
    try:
        while True:
            await bot.send_chat_action(
                chat_id=chat_id,
                action="typing"
            )
            # Reduced sleep time to keep typing indicator more consistent
            await asyncio.sleep(3)
    except asyncio.CancelledError:
        pass

def process_context(knowledge_base, message_text):
    relevant_info = knowledge_base.query_knowledge(message_text)
    
    # Improve content prioritization
    priority_keywords = [
        'contract', 'token', 'erc20', 'dapp', 'builder', 
        'template', 'swap', 'exchange', 'wallet', 'nft'
    ]
    
    # Classify documents by relevance
    priority_docs = []
    secondary_docs = []
    
    for doc in relevant_info:
        content_lower = doc.page_content.lower()
        # Calculate score based on keywords
        score = sum(2 for keyword in priority_keywords if keyword in content_lower)
        # Add score for exact match with query
        score += sum(3 for word in message_text.lower().split() if word in content_lower)
        
        if score > 2:
            priority_docs.append((score, doc))
        else:
            secondary_docs.append((score, doc))
    
    # Sort by score
    priority_docs.sort(reverse=True)
    secondary_docs.sort(reverse=True)
    
    # Combine prioritized documents (maximum 5 documents)
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
        # Initialize knowledge base
        knowledge_base.db = initialize_knowledge_base()
        if not knowledge_base.db:
            logging.error("Could not initialize knowledge base. Exiting...")
            sys.exit(1)
            
        # Initialize Telegram bot
        global app
        app = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()
        
        if not os.getenv('TELEGRAM_BOT_TOKEN'):
            logging.error("TELEGRAM_BOT_TOKEN not found in environment variables")
            sys.exit(1)
            
        # Add handlers
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
    main()