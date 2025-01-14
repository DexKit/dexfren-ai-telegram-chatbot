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
    instructions=f"""
    You are DexFren, DexKit's support assistant. Follow these rules STRICTLY:

    CORE BEHAVIOR:
    1. Use ONLY knowledge base info - NO external sources
    2. Avoid hallucinations on ANY topic
    3. Keep responses focused and structured
    4. Use detailed examples with actual configurations
    5. Verify technical accuracy before responding

    DOCUMENTATION URLS:
    DexAppBuilder:
    • Main: docs.dexkit.com/defi-products
    • Getting Started: docs.dexkit.com/defi-products/dexappbuilder/creating-my-first-dapp
    • Templates: docs.dexkit.com/defi-products/dexappbuilder/starting-with-templates
    • Networks: docs.dexkit.com/defi-products/dexappbuilder/available-networks
    • Management: docs.dexkit.com/defi-products/dexappbuilder/managing-this-tool
    • Tokens: docs.dexkit.com/defi-products/dexappbuilder/importing-tokens
    • Domains: docs.dexkit.com/defi-products/dexappbuilder/custom-domains
    • Teams: docs.dexkit.com/defi-products/dexappbuilder/configuring-teams

    DexGenerator:
    • Overview: docs.dexkit.com/defi-products/dexgenerator/overview
    • Requirements: docs.dexkit.com/defi-products/dexgenerator/requirements
    • Web3 Forms: docs.dexkit.com/defi-products/dexgenerator/web3-forms-generator
    • NFT Guide: docs.dexkit.com/defi-products/dexgenerator/creating-my-first-nft-collection
    • Contracts: docs.dexkit.com/defi-products/dexgenerator/managing-deployed-contracts

    DexSwap:
    • Overview: docs.dexkit.com/defi-products/dexswap/overview
    • First Swap: docs.dexkit.com/defi-products/dexswap/creating-my-first-swap
    • Management: docs.dexkit.com/defi-products/dexswap/managing-this-tool

    DexNFTStore:
    • Overview: docs.dexkit.com/defi-products/dexnftstore/overview
    • First Store: docs.dexkit.com/defi-products/dexnftstore/creating-my-first-store
    • Management: docs.dexkit.com/defi-products/dexnftstore/managing-this-tool

    DexWallet:
    • Overview: docs.dexkit.com/defi-products/dexwallet/overview
    • First Wallet: docs.dexkit.com/defi-products/dexwallet/creating-my-first-wallet
    • Management: docs.dexkit.com/defi-products/dexwallet/managing-this-tool

    DApp Builder URLs:
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
    • BSC mainnet and testnet
    • Polygon
    • Arbitrum
    • Avalanche
    • Optimism
    • Fantom
    • Base
    • Blast
    • Blast testnet
    • Pulsechain

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
        is_private = update.message.chat.type == 'private'
        is_bot_mentioned = bool(update.message.entities and 
            any(entity.type == 'mention' and 
                context.bot.username in update.message.text[entity.offset:entity.offset + entity.length] 
                for entity in update.message.entities))
        is_reply_to_bot = bool(update.message.reply_to_message and 
            update.message.reply_to_message.from_user.id == context.bot.id)
        
        if not (is_private or is_bot_mentioned or is_reply_to_bot):
            return
            
        chat_id = update.message.chat_id
        message_text = update.message.text
        
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
        
        conversation = [
            {"role": "system", "content": f"{dexkit_agent.instructions}\n\n{context_text}"},
            {"role": "system", "content": "Remember to be specific and provide actionable steps."}
        ]
        
        if len(active_conversations[chat_id]) > 1:
            conversation.extend(active_conversations[chat_id][-6:])
        
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
            typing_task.cancel()
            await asyncio.sleep(0.1)
        
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
            await asyncio.sleep(3)
    except asyncio.CancelledError:
        pass

def process_knowledge_base_results(relevant_info):
    """Process and format knowledge base results"""
    if not relevant_info:
        return "No relevant information found."
    
    formatted_content = []
    for doc in relevant_info:
        content = doc.page_content.strip()
        if hasattr(doc.metadata, 'source'):
            content += f"\nFuente: {doc.metadata['source']}"
        formatted_content.append(content)
    
    return "\n---\n".join(formatted_content)

def process_context(knowledge_base, message_text):
    relevant_info = knowledge_base.query_knowledge(message_text)
    docs_manager = DocumentationManager()
    
    platform_and_docs = docs_manager.find_relevant_docs(message_text, max_results=4)
    
    platform_links = "\n\nDirect Links:\n"
    doc_links = "\nRelated Documentation:\n"
    
    for doc in platform_and_docs:
        if 'dexappbuilder.dexkit.com/admin' in doc.url:
            platform_links += f"• [{doc.title}]({doc.url})\n"
        else:
            doc_links += f"• [{doc.title}]({doc.url})\n"
    
    context = process_knowledge_base_results(relevant_info)
    
    return f"{platform_links}{doc_links}\n\nRelevant Context:\n{context}"

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