from dotenv import load_dotenv
import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ChatAction
from swarm import Swarm, Agent
from knowledge.data_ingestion import DexKitKnowledgeBase
from langchain_chroma import Chroma
from knowledge.documentation_manager import DocumentationManager
from chromadb.config import Settings
import sys
from typing import Optional
import json
import re

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

def load_all_configs():
    """Load all configuration files"""
    base_config_path = 'config'
    config_files = {
        'agent': 'agent_instructions.json',
        'documentation': 'documentation_urls.json',
        'platform': 'platform_urls.json',
        'youtube': 'youtube_videos.json',
        'messages': 'bot_messages.json',
        'settings': 'bot_settings.json'
    }
    
    configs = {}
    logger = logging.getLogger('main')
    logger.info("Loading configuration files...")
    
    for key, filename in config_files.items():
        path = os.path.join(base_config_path, filename)
        logger.info(f"Loading {path}...")
        
        if not os.path.exists(path):
            logger.error(f"Configuration file not found: {path}")
            configs[key] = {}
            continue
            
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                configs[key] = json.load(f)
                logger.info(f"Successfully loaded {filename}")
                
                if key == 'youtube':
                    logger.info(f"Loaded {len(configs[key])} YouTube videos")
                elif key == 'documentation':
                    logger.info(f"Loaded {len(configs[key])} documentation sections")
                elif key == 'platform':
                    logger.info(f"Loaded {len(configs[key].get('products', {}))} platform products")
                
        except UnicodeError:
            with open(path, 'r', encoding='utf-8') as f:
                configs[key] = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error in {path}: {str(e)}")
            configs[key] = {}
        except Exception as e:
            logger.error(f"Error loading {path}: {str(e)}")
            configs[key] = {}
    
    return configs

def generate_documentation_urls(docs_config):
    """Generate documentation URLs section from config"""
    urls = []
    
    for product, data in docs_config.items():
        if 'base_url' in data and 'sections' in data:
            urls.append(f"{product.upper()}:")
            for section_name, section_data in data['sections'].items():
                if isinstance(section_data, str):
                    url = f"{data['base_url']}{section_data}"
                    urls.append(f"• {section_name.replace('_', ' ').title()}: {url}")
                elif isinstance(section_data, dict) and 'url' in section_data:
                    url = data['base_url'] + section_data['url'] if section_data['url'].startswith('/') else section_data['url']
                    urls.append(f"• {section_data.get('title', section_name.replace('_', ' ').title())}: {url}")
    
    return "\n".join(urls)

def generate_platform_urls(platform_config):
    """Generate platform URLs section from config"""
    urls = ["DApp Builder URLs:"]
    
    admin_urls = platform_config.get('products', {}).get('dexappbuilder', {}).get('dexkit-dexappbuilder-admin', {})
    if admin_urls:
        for key, url in admin_urls.items():
            if isinstance(url, str):
                urls.append(f"• {key.replace('dexkit-dexappbuilder-admin-', '').replace('-', ' ').title()}: {url}")
            elif isinstance(url, dict) and key == 'dexkit-dexappbuilder-admin-quick-builders':
                urls.append("• Quick Builders:")
                for qb_key, qb_url in url.items():
                    builder_name = qb_key.replace('dexkit-dexappbuilder-admin-quick-builder-', '').title()
                    urls.append(f"  - {builder_name}: {qb_url}")
    
    return "\n".join(urls)

def generate_social_urls(platform_config):
    """Generate social URLs section from config"""
    social_urls = ["Social:"]
    social_data = platform_config.get('social', {})
    
    for key, url in social_data.items():
        platform = key.replace('dexkit-', '').title()
        social_urls.append(f"• {platform}: {url}")
    
    return "\n".join(social_urls)

def generate_token_urls(platform_config):
    """Generate token URLs section from config"""
    token_urls = ["Token:"]
    token_data = platform_config.get('token', {}).get('buy', {})
    
    for key, url in token_data.items():
        network = key.replace('dexkit-buy-', '').upper()
        token_urls.append(f"• {network}: {url}")
    
    return "\n".join(token_urls)

def load_agent_instructions(configs):
    """Generate agent instructions from config files"""
    agent_config = configs.get('agent', {})
    
    if not agent_config:
        print("[X] Error: Agent configuration is empty")
        return "Default instructions for DexFren"
        
    try:
        instructions = [
            f"You are {agent_config['name']}, DexKit's support assistant. Follow these rules STRICTLY:\n",
            "\nCORE BEHAVIOR:",
            *[f"{i+1}. {rule}" for i, rule in enumerate(agent_config['core_behavior'])],
            
            f"\n{generate_documentation_urls(configs['documentation'])}",
            f"\n{generate_platform_urls(configs['platform'])}",
            f"\n{generate_social_urls(configs['platform'])}",
            f"\n{generate_token_urls(configs['platform'])}",
            
            "\nAvailable Networks:",
            "Mainnets:",
            *[f"• {network}" for network in agent_config['networks']['mainnets']],
            "\nTestnets:",
            *[f"• {network}" for network in agent_config['networks']['testnets']],
            
            "\nCRITICAL RULES FOR TOKEN CREATION:",
            *[f"{i+1}. {rule}" for i, rule in enumerate(agent_config['token_creation_rules'])],
            
            "\nRESPONSE FORMAT:",
            *[f"{i+1}. {fmt}" for i, fmt in enumerate(agent_config['response_format'])],
            
            "\nFORMATTING:",
            *[f"• {key}: {value}" for key, value in agent_config['formatting'].items()],
            
            "\nSTRICTLY PROHIBITED:",
            *[f"• {item}" for item in agent_config['prohibited']]
        ]
        
        return "\n".join(instructions)
    except Exception as e:
        print(f"[X] Error generating agent instructions: {str(e)}")
        return "Default instructions for DexFren"

configs = load_all_configs()
agent_instructions = load_agent_instructions(configs)

dexkit_agent = Agent(
    name="DexFren",
    instructions=agent_instructions,
    model="gpt-3.5-turbo"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(configs['messages']['welcome']['message'])

def initialize_logging(config):
    log_config = config.get('logging', {})
    log_format = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    log_level = getattr(logging, log_config.get('level', 'INFO'))
    
    # Limpiar handlers existentes
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Configurar el logger principal
    logging.basicConfig(
        format=log_format,
        level=log_level,
        handlers=[
            logging.FileHandler('bot.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)  # Usar stdout en lugar de stderr
        ]
    )
    
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.INFO)

async def keep_typing(bot, chat_id):
    """Keep typing indicator active"""
    try:
        while True:
            await bot.send_chat_action(
                chat_id=chat_id,
                action=ChatAction.TYPING
            )
            await asyncio.sleep(3)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Error in keep_typing: {str(e)}")

def format_telegram_message(text: str) -> str:
    """Format text for Telegram MarkdownV2"""
    special_chars = '_*[]()~`>#+-=|{}.!'
    
    url_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
    urls = re.findall(url_pattern, text)
    
    for title, url in urls:
        old = f'[{title}]({url})'
        escaped_url = url.replace('.', r'\.')
        new = f'[{title}]({escaped_url})'
        text = text.replace(old, new)
    
    result = ""
    in_url = False
    for char in text:
        if char == '[':
            in_url = True
            result += char
        elif char == ']':
            in_url = False
            result += char
        elif char in special_chars and not in_url:
            result += f'\\{char}'
        else:
            result += char
            
    return result

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.message.chat_id
        message_text = update.message.text
        logger = logging.getLogger('telegram.bot')
        
        typing_task = asyncio.create_task(keep_typing(context.bot, chat_id))
        
        try:
            configs = load_all_configs()
            platform_urls = configs.get('platform', {})
            
            format_instructions = """
            Answer in a concise and direct manner.
            Use this format:
            *bold* for important titles and concepts
            _italic_ for emphasis
            [text](URL) for links
            `code` for configurations
            

            DO NOT include HTML code or iframes.
            DO NOT include long answers.
            ALWAYS include the relevant platform links.
            """
            
            messages = [
                {"role": "system", "content": format_instructions},
                {"role": "system", "content": f"URLs disponibles: {json.dumps(platform_urls, indent=2)}"},
                {"role": "user", "content": message_text}
            ]
            
            response = client.run(
                agent=dexkit_agent,
                messages=messages,
                stream=False
            )
            
            bot_response = response.messages[-1]["content"]
            
        finally:
            typing_task.cancel()
            await asyncio.sleep(0.1)
        
        await update.message.reply_text(
            bot_response,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in handle_message: {e}", exc_info=True)
        await update.message.reply_text(
            "Sorry, an error occurred. Please try again."
        )

def process_knowledge_base_results(relevant_info):
    """Process and format knowledge base results"""
    if not relevant_info:
        return None
    
    formatted_content = []
    for doc in relevant_info:
        content = doc.page_content.strip()
        source = doc.metadata.get('source', 'Unknown source')
        formatted_content.append(f"From {source}:\n{content}")
    
    return "\n\n".join(formatted_content)

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

def initialize_knowledge_base() -> Optional[Chroma]:
    try:
        kb_dir = configs['settings']['knowledge_base']['directory']
        if not os.path.exists(kb_dir):
            os.makedirs(kb_dir)
        
        return Chroma(
            persist_directory=kb_dir,
            embedding_function=knowledge_base.embeddings,
            client_settings=Settings(**configs['settings']['knowledge_base']['chroma_settings'])
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
    try:
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO,
            handlers=[
                logging.FileHandler('bot.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        logger = logging.getLogger('main')
        logger.info("Configuration loaded")
        
        logger.info("Starting bot...")
        logger.info("Initializing knowledge base...")
        if not knowledge_base.create_knowledge_base():
            logger.error("Could not initialize knowledge base")
            return

        global app
        logger.info("Building Telegram application...")
        app = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()
        
        logger.info("Adding handlers...")
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        logger.info("Starting polling...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logging.error(f"Critical error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    
    print("Starting configuration...")
    configs = load_all_configs()
    
    initialize_logging(configs['settings'])
    logger = logging.getLogger('main')
    
    logger.info("Configuration loaded")
    logger.info("Starting bot...")
    main()