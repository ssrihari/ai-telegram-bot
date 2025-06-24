import os
import asyncio
import json
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

# Global dictionary to store conversation state per chat
# Structure: {chat_id: {"assistant_id": "...", "thread_id": "..."}}
conversation_state = {}

# Initialize OpenAI client
openai_client = None

def log_llm_interaction(user_message: str, llm_response: str, model: str, telegram_update: dict = None, error: str = None, response_id: str = None):
    """Log LLM requests and responses to a file."""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "model": model,
        "user_message": user_message,
        "llm_response": llm_response,
        "telegram_update": telegram_update,
        "response_id": response_id,
        "error": error
    }
    
    try:
        with open("llm_logs.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Failed to write log: {e}")

async def get_openai_client():
    """Get or create OpenAI client."""
    global openai_client
    if openai_client is None:
        openai_client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    return openai_client

async def get_or_create_assistant(system_prompt: str, model: str) -> str:
    """Get or create an OpenAI assistant."""
    client = await get_openai_client()
    
    # For simplicity, create a new assistant each time
    # In production, you might want to cache/reuse assistants
    assistant = await client.beta.assistants.create(
        name="Telegram Bot Assistant",
        instructions=system_prompt,
        model=model
    )
    return assistant.id

async def get_openai_assistants_response(user_message: str, chat_id: int, model: str, system_prompt: str) -> tuple[str, str]:
    """Get response using OpenAI Assistants API with conversation state."""
    client = await get_openai_client()
    
    # Get or create conversation state for this chat
    if chat_id not in conversation_state:
        assistant_id = await get_or_create_assistant(system_prompt, model)
        thread = await client.beta.threads.create()
        conversation_state[chat_id] = {
            "assistant_id": assistant_id,
            "thread_id": thread.id
        }
    
    chat_state = conversation_state[chat_id]
    
    # Add message to thread
    await client.beta.threads.messages.create(
        thread_id=chat_state["thread_id"],
        role="user",
        content=user_message
    )
    
    # Run the assistant
    run = await client.beta.threads.runs.create(
        thread_id=chat_state["thread_id"],
        assistant_id=chat_state["assistant_id"]
    )
    
    # Wait for completion
    while run.status in ['queued', 'in_progress']:
        await asyncio.sleep(1)
        run = await client.beta.threads.runs.retrieve(
            thread_id=chat_state["thread_id"],
            run_id=run.id
        )
    
    if run.status == 'completed':
        # Get the assistant's response
        messages = await client.beta.threads.messages.list(
            thread_id=chat_state["thread_id"],
            order="desc",
            limit=1
        )
        
        response_content = messages.data[0].content[0].text.value
        return response_content, run.id
    else:
        raise Exception(f"Assistant run failed with status: {run.status}")

async def get_llm_response(user_message: str, telegram_update: dict = None, chat_id: int = None) -> str:
    """Get response from OpenAI using Assistants API."""
    try:
        # Get system prompt from environment or use default
        system_prompt = os.getenv('SYSTEM_PROMPT', 'You are a helpful assistant.')
        
        # Get model from environment or use default
        model = os.getenv('OPENAI_MODEL', 'gpt-4o')
        
        # Use OpenAI Assistants API for conversation state
        llm_response, response_id = await get_openai_assistants_response(
            user_message, chat_id, model, system_prompt
        )
        
        # Log successful interaction
        log_llm_interaction(user_message, llm_response, model, telegram_update, response_id=response_id)
        
        return llm_response
        
    except Exception as e:
        error_msg = str(e)
        print(f"OpenAI error: {error_msg}")
        fallback_response = "Sorry, I'm having trouble processing your message right now."
        
        # Log failed interaction
        log_llm_interaction(user_message, fallback_response, model or "gpt-4o", telegram_update, error_msg)
        
        return fallback_response

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle any incoming message and respond using LLM."""
    user_message = update.message.text
    chat_id = update.message.chat.id
    
    # Convert Telegram update to dict for logging
    telegram_update_dict = update.to_dict()
    
    # Get LLM response with chat context
    llm_response = await get_llm_response(user_message, telegram_update_dict, chat_id)
    
    # Split response into paragraphs and send each as separate message
    paragraphs = [p.strip() for p in llm_response.split('\n\n') if p.strip()]
    
    for paragraph in paragraphs:
        await update.message.reply_text(paragraph)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    await update.message.reply_text('Bot is running! Send me any message and I\'ll respond using AI.\n\nUse /new to start a fresh conversation with no previous context.')

async def new_conversation_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /new command to start a fresh conversation."""
    chat_id = update.message.chat.id
    
    # Remove conversation state for this chat
    if chat_id in conversation_state:
        del conversation_state[chat_id]
        await update.message.reply_text('🔄 Started a new conversation! Previous context has been cleared.')
    else:
        await update.message.reply_text('🔄 Starting fresh! This is already a new conversation.')

def create_bot_application():
    """Create and configure the Telegram bot application."""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
    
    application = Application.builder().token(token).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("new", new_conversation_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    return application

async def run_bot():
    """Run the Telegram bot."""
    application = create_bot_application()
    
    print("Starting Telegram bot...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    try:
        # Keep the bot running
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("Stopping bot...")
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

if __name__ == "__main__":
    asyncio.run(run_bot())