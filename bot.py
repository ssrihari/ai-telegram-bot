import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import litellm

load_dotenv()

async def get_llm_response(user_message: str) -> str:
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
        
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"LLM error: {e}")
        return "Sorry, I'm having trouble processing your message right now."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle any incoming message and respond using LLM."""
    user_message = update.message.text
    
    # Get LLM response
    llm_response = await get_llm_response(user_message)
    
    # Send response back to user
    await update.message.reply_text(llm_response)

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