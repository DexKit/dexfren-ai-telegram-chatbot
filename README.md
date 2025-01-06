# DexFren AI Telegram chatbot Bot Documentation

## Overview

DexFren AI chatbot is a Telegram bot powered by GPT-4 that helps users understand and use the DexAppBuilder platform. The bot uses a knowledge base built from DexKit's documentation and YouTube tutorials.

## Setup Requirements

### Dependencies

`pip install python-telegram-bot`
`pip install langchain-chroma`
`pip install python-dotenv`
`pip install swarm`
`pip install youtube-transcript-api`

### Environment Variables

`TELEGRAM_BOT_TOKEN`
`OPENAI_API_KEY`

## Project Structure

    project/
    ├── docs/                   # PDF documentation (if any)
    ├── knowledge/             
    │   ├── __init__.py
    │   └── data_ingestion.py  # Knowledge base processing
    ├── knowledge_base/         # Vector store data
    ├── .env                   # Environment variables
    ├── .gitignore            
    ├── README.md              # Simplified documentation
    ├── main.py                # Bot implementation
    └── build_knowledge_base.py # Knowledge base builder

## Features

- Natural language processing for DexKit-related queries
- Context-aware responses based on documentation and tutorials
- Support for both English and Spanish video transcripts
- Real-time responses using GPT-4
- Persistent knowledge base using Chroma vector store

## Usage

### Building the Knowledge Base

1. Place any PDF documentation in the `docs/` directory
2. Update YouTube URLs in `build_knowledge_base.py`
3. Run the knowledge base builder:

```bash
python build_knowledge_base.py
```

### Running the Bot

```bash
python main.py
```

### Interacting with the Bot

1. Find the bot on Telegram using the bot username
2. Start a conversation with `/start`
3. Ask questions about:
   - DexAppBuilder usage
   - Platform features
   - Technical guidance
   - Best practices

## Architecture

### Components

- **Telegram Bot**: Handles user interactions
- **Swarm Agent**: Processes queries using GPT-4
- **Knowledge Base**: Stores and retrieves relevant context
- **Vector Store**: Manages embeddings for efficient searching

### Data Flow

1. User sends message via Telegram
2. Bot queries knowledge base for relevant context
3. Context is sent to Swarm Agent with user query
4. GPT-4 generates response using context
5. Response is sent back to user