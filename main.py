from dotenv import load_dotenv
import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from swarm import Swarm, Agent
from knowledge.data_ingestion import DexKitKnowledgeBase
from langchain_chroma import Chroma

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

# Define the DexKit agent
dexkit_agent = Agent(
    name="DexKit Assistant",
    instructions="""
    You are the official DexKit support assistant. Your role is to help users with DexAppBuilder.
    Use the provided context to answer questions accurately.
    If you're not sure about something, acknowledge it and direct users to official support channels.
    Always maintain a professional and helpful tone.
    """,
    model="gpt-4"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = """
Welcome to the DexKit Assistant! 👋

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
        user_message = update.message.text
        
        # Search relevant information in the knowledge base
        relevant_info = knowledge_base.query_knowledge(user_message)
        context_text = "\n".join([doc.page_content for doc in relevant_info])
        
        # Get response from the agent with the context
        response = client.run(
            agent=dexkit_agent,
            messages=[
                {"role": "system", "content": f"Relevant context from DexKit documentation and tutorials:\n{context_text}"},
                {"role": "user", "content": user_message}
            ],
            stream=False
        )
        
        await update.message.reply_text(response.messages[-1]["content"])
        
    except Exception as e:
        error_message = "I apologize, but I encountered an error. Please try again or contact DexKit support if the issue persists."
        logging.error(f"Error: {str(e)}")
        await update.message.reply_text(error_message)

def run_bot():
    """Main function to run the bot"""
    # Configure event policy for Windows
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Initialize the knowledge base
    try:
        knowledge_base.db = Chroma(
            persist_directory="./knowledge_base",
            embedding_function=knowledge_base.embeddings
        )
    except Exception as e:
        print(f"Error loading knowledge base: {e}")
        return

    # Configure and run the bot
    app = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Starting bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        run_bot()
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Error running bot: {e}")