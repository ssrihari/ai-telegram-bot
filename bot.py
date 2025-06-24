import os
import json
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from openai_client import get_openai_assistants_response, clear_conversation_state, update_assistant_instructions

load_dotenv()

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

def load_enhanced_system_prompt() -> str:
    """Load system prompt from environment and append how-to-talk-to-kids.md content."""
    base_prompt = os.getenv('SYSTEM_PROMPT', 'You are a helpful assistant.')
    
    try:
        with open('how-to-talk-to-kids.md', 'r', encoding='utf-8') as f:
            book_content = f.read()
        
        enhanced_prompt = f"{base_prompt}\n\n```\n{book_content}\n```"
        return enhanced_prompt
    except FileNotFoundError:
        print("Warning: how-to-talk-to-kids.md not found, using base prompt only")
        return base_prompt
    except Exception as e:
        print(f"Error loading how-to-talk-to-kids.md: {e}")
        return base_prompt

async def get_llm_response(user_message: str, telegram_update: dict = None, chat_id: int = None) -> str:
    """Get response from OpenAI using Assistants API."""
    try:
        # Get enhanced system prompt with book content
        system_prompt = load_enhanced_system_prompt()
        
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
    
    # Check if this is a reply to another message
    if update.message.reply_to_message:
        replied_text = update.message.reply_to_message.text or "[Non-text message]"
        # Format the message with the reply context
        user_message = f"[Replying to: \"{replied_text}\"]\n\n{user_message}"
    
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
    await update.message.reply_text('Bot is running! Send me any message and I\'ll respond using AI.\n\nCommands:\n/new - Start a fresh conversation\n/instruct <instructions> - Update bot instructions')

async def new_conversation_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /new command to start a fresh conversation."""
    chat_id = update.message.chat.id
    
    # Create new thread for this chat
    if await clear_conversation_state(chat_id):
        await update.message.reply_text('🔄 Started a new conversation! Previous context has been cleared.')
    else:
        await update.message.reply_text('🔄 Starting fresh! This is already a new conversation.')

async def instruct_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /instruct command to update assistant instructions."""
    # Get the instructions from the command arguments
    if not context.args:
        await update.message.reply_text('❗ Please provide instructions after the command.\n\nExample: /instruct You are a helpful cooking assistant that provides detailed recipes.')
        return
    
    new_instructions = ' '.join(context.args)
    
    try:
        # Get model from environment
        model = os.getenv('OPENAI_MODEL', 'gpt-4o')
        
        # Update the assistant instructions
        await update_assistant_instructions(new_instructions, model)
        
        await update.message.reply_text(f'✅ Assistant instructions updated!\n\nNew instructions: "{new_instructions}"')
        
    except Exception as e:
        await update.message.reply_text(f'❌ Failed to update instructions: {str(e)}')

def create_bot_application():
    """Create and configure the Telegram bot application."""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
    
    application = Application.builder().token(token).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("new", new_conversation_command))
    application.add_handler(CommandHandler("instruct", instruct_command))
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