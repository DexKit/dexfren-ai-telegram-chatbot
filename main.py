from dotenv import load_dotenv
import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from swarm import Swarm, Agent
from knowledge.data_ingestion import DexKitKnowledgeBase
from langchain_community.vectorstores import Chroma
from knowledge.documentation_manager import DocumentationManager

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Load environment variables
load_dotenv()

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
    You are DexFren, DexKit's support assistant. Follow these rules exactly:

    CORE BEHAVIOR:
    1. Use ONLY knowledge base info
    2. If unsure, ask specific questions
    3. Keep responses brief and focused
    4. Use examples when explaining

    URLS - USE ONLY THESE:
    DApp:
    • Create: dexappbuilder.dexkit.com/admin/create
    • Main: dexappbuilder.dexkit.com

    KIT Token Purchase:
    • ETH: dexappbuilder.dexkit.com/token/buy/ethereum/kit
    • BSC: dexappbuilder.dexkit.com/token/buy/bsc/kit
    • MATIC: dexappbuilder.dexkit.com/token/buy/polygon/kit

    RESPONSE FORMAT:
    • Start with direct answer
    • Use bullet points for steps
    • Include relevant URL
    • End with next step suggestion

    FORMATTING:
    • Links: [text](URL)
    • Important: *text*
    • Details: _text_
    • Code: `text`

    PROHIBITED:
    • External exchanges/DEXs
    • Unsupported features
    • Personal opinions
    • Made-up information
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
        
        conversation = [
            {"role": "system", "content": f"{dexkit_agent.instructions}\n\nContext:\n{context_text}"}
        ] + active_conversations[chat_id][-5:]
        
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

def main():
    """Initialize and run the bot"""
    knowledge_base.db = Chroma(
        persist_directory="./knowledge_base",
        embedding_function=knowledge_base.embeddings
    )
    
    app = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()
    
    # Simplify handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ))
    
    print("Starting bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Error running bot: {e}")