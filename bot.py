import os
import asyncio
import json
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import litellm

load_dotenv()

def log_llm_interaction(user_message: str, llm_response: str, model: str, telegram_update: dict = None, error: str = None):
    """Log LLM requests and responses to a file."""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "model": model,
        "user_message": user_message,
        "llm_response": llm_response,
        "telegram_update": telegram_update,
        "error": error
    }
    
    try:
        with open("llm_logs.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Failed to write log: {e}")

async def get_llm_response(user_message: str, telegram_update: dict = None) -> str:
    """Get response from LLM using LiteLLM."""
    try:
        # Get system prompt from environment or use default
        system_prompt = os.getenv('SYSTEM_PROMPT', 'You are a helpful assistant.')
        
        # Get model from environment or use default
        model = os.getenv('LITELLM_MODEL', 'gpt-4o')
        
        # Determine which API key to use based on model
        if model.startswith('claude'):
            api_key = os.getenv('ANTHROPIC_API_KEY')
        else:
            api_key = os.getenv('OPENAI_API_KEY')
            
        response = await litellm.acompletion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            api_key=api_key
        )
        
        llm_response = response.choices[0].message.content
        
        # Log successful interaction
        log_llm_interaction(user_message, llm_response, model, telegram_update)
        
        return llm_response
        
    except Exception as e:
        error_msg = str(e)
        print(f"LLM error: {error_msg}")
        fallback_response = "Sorry, I'm having trouble processing your message right now."
        
        # Log failed interaction
        log_llm_interaction(user_message, fallback_response, model, telegram_update, error_msg)
        
        return fallback_response

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle any incoming message and respond using LLM."""
    user_message = update.message.text
    
    # Convert Telegram update to dict for logging
    telegram_update_dict = update.to_dict()
    
    # Get LLM response
    llm_response = await get_llm_response(user_message, telegram_update_dict)
    
    # Split response into paragraphs and send each as separate message
    paragraphs = [p.strip() for p in llm_response.split('\n\n') if p.strip()]
    
    for paragraph in paragraphs:
        await update.message.reply_text(paragraph)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    await update.message.reply_text('Bot is running! Send me any message and I\'ll respond using AI.')

def create_bot_application():
    """Create and configure the Telegram bot application."""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
    
    application = Application.builder().token(token).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
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