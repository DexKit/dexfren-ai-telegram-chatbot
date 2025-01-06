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

# Store active conversations
active_conversations = {}

# Define the DexKit agent
dexkit_agent = Agent(
    name="DexFren",
    instructions="""
    You are the official DexKit support assistant and your name is DexFren. Your role is to help users with DexAppBuilder.
    Use the provided context to answer questions accurately.
    If you're not sure about something, acknowledge it and direct users to official support channels.
    Always maintain a professional and helpful tone.
    """,
    model="gpt-4"
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
        chat_id = update.message.chat_id
        message_text = update.message.text
        is_group = update.message.chat.type in ['group', 'supergroup']
        
        # Simplify response logic
        should_respond = False
        
        # 1. In private chat, respond always
        if not is_group:
            should_respond = True
        
        # 2. In groups, respond if:
        else:
            bot_username = context.bot.username
            # a) It's a direct mention
            was_mentioned = f'@{bot_username}' in message_text
            
            # b) It's a response to any message in the conversation chain
            is_in_conversation = (
                update.message.reply_to_message and 
                (
                    # It's a direct response to the bot
                    (update.message.reply_to_message.from_user and 
                     update.message.reply_to_message.from_user.id == context.bot.id) or
                    # Or it's part of a response chain that started with the bot
                    chat_id in active_conversations
                )
            )
            
            should_respond = was_mentioned or is_in_conversation
            
            if was_mentioned:
                message_text = message_text.replace(f'@{bot_username}', '').strip()
        
        if not should_respond:
            return
            
        # Initialize or continue conversation
        if chat_id not in active_conversations:
            active_conversations[chat_id] = []
        
        # Add user message
        active_conversations[chat_id].append({
            "role": "user",
            "content": message_text
        })
        
        # Get context and prepare conversation
        relevant_info = knowledge_base.query_knowledge(message_text)
        context_text = "\n".join([doc.page_content for doc in relevant_info])
        
        conversation = [
            {"role": "system", "content": f"Relevant context from DexKit documentation and tutorials:\n{context_text}"}
        ] + active_conversations[chat_id][-5:]
        
        # Get response
        response = client.run(
            agent=dexkit_agent,
            messages=conversation,
            stream=False
        )
        
        # Save and send response
        bot_response = response.messages[-1]["content"]
        active_conversations[chat_id].append({
            "role": "assistant",
            "content": bot_response
        })
        
        # Keep history limited
        if len(active_conversations[chat_id]) > 10:
            active_conversations[chat_id] = active_conversations[chat_id][-10:]
        
        await update.message.reply_text(
            bot_response,
            reply_to_message_id=update.message.message_id
        )
        
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        await update.message.reply_text(
            "I apologize, but I encountered an error. Please try again."
        )

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