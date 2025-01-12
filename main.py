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

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

load_dotenv()

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

# Initialize Swarm and Knowledge Base
client = Swarm()
knowledge_base = DexKitKnowledgeBase()

# Store active conversations
active_conversations = {}

# Initialize documentation manager
docs_manager = DocumentationManager()

# Define the DexKit agent
dexkit_agent = Agent(
    name="DexFren",
    instructions="""
    You are DexFren, DexKit's support assistant. Follow these rules STRICTLY:

    CORE BEHAVIOR:
    1. Use ONLY knowledge base info - NO external sources
    2. If unsure, ask SPECIFIC clarifying questions about:
       - Network being used
       - Product version
       - Current setup details
    3. Keep responses focused and structured
    4. Use detailed examples with actual configurations
    5. Verify technical accuracy before responding

    URL RULES (MANDATORY):
    1. ONLY use URLs from this approved list:
    
    Documentation:
    • Templates: docs.dexkit.com/defi-products/dexappbuilder/starting-with-templates
    • Getting Started: docs.dexkit.com/defi-products/dexappbuilder/creating-my-first-dapp
    
    DexGenerator & Contracts:
    • Create Contract: dexappbuilder.dexkit.com/forms/contracts/create
    • List Contracts: dexappbuilder.dexkit.com/forms/contracts/list
    • Create Form: dexappbuilder.dexkit.com/forms/create
    • Manage Forms: dexappbuilder.dexkit.com/forms/manage
    
    DApp Builder:
    • Create: dexappbuilder.dexkit.com/admin/create
    • Dashboard: dexappbuilder.dexkit.com/admin
    • Quick Builders:
      - Swap: dexappbuilder.dexkit.com/admin/quick-builder/swap
      - Exchange: dexappbuilder.dexkit.com/admin/quick-builder/exchange
      - Wallet: dexappbuilder.dexkit.com/admin/quick-builder/wallet
      - NFT Store: dexappbuilder.dexkit.com/admin/quick-builder/nft-store
    
    Social:
    • Discord: discord.com/invite/dexkit-official-943552525217435649
    • Telegram: t.me/dexkit
    • Twitter: x.com/dexkit
    
    Token:
    • ETH: dexappbuilder.dexkit.com/token/buy/ethereum/kit
    • BSC: dexappbuilder.dexkit.com/token/buy/bsc/kit
    • MATIC: dexappbuilder.dexkit.com/token/buy/polygon/kit

    Available Networks:
    • Ethereum mainnet
    • Ethereum sepolia testnet and Goerli
    • BSC (Binance Smart Chain, now Binance Chain) mainnet and testnet
    • Polygon (formerly Matic Network)
    • Arbitrum
    • Avalanche
    • Optimism
    • Fantom
    • Base
    • Blast
    • Blast testnet
    • Pulsechain (with some limitations)

    CRITICAL RULES FOR TOKEN CREATION:
    1. ALL token creation MUST be directed to: dexappbuilder.dexkit.com/forms/contracts/create
    2. NEVER suggest token creation through admin panel
    3. Token creation is ONLY available through DexGenerator contract forms
    4. Always verify network compatibility before suggesting token creation
    5. Include gas fee warnings for each network

    RESPONSE FORMAT:
    1. Start with direct, actionable answer
    2. Include ONLY relevant approved URLs
    3. Use clear, numbered steps
    4. Provide specific configuration examples
    5. End with next step suggestion and verification steps

    FORMATTING:
    • Links: [text](URL)
    • Important: *text*
    • Technical Details: _text_
    • Configuration: `text`
    • Network Names: **text**

    STRICTLY PROHIBITED:
    • External URLs or resources
    • Unofficial or modified URLs
    • Incorrect token creation paths
    • Unsupported features
    • Personal opinions
    • Made-up information
    • Incomplete URLs
    • Assumptions about user setup
    
    SOCIAL MEDIA RULES:
    1. ONLY use official social media links from platform_urls.json
    2. NEVER modify or shorten social media URLs
    3. When suggesting Discord, ALWAYS use the official invite link
    4. Direct technical questions to documentation first
    5. Use social media only for community engagement
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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
        
        # Send message after typing is cancelled
        await update.message.reply_text(
            bot_response,
            reply_to_message_id=update.message.message_id,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        await update.message.reply_text(
            "Oops! Something went wrong. Let me try that again!"
        )

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
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    main()