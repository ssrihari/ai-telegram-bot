import os
import json
import asyncio
import time
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from openai_client import get_openai_responses_response, stream_openai_responses, clear_conversation_state, update_system_instructions

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

async def stream_llm_response(user_message: str, telegram_update: dict, chat_id: int, update: Update):
    """Stream response from OpenAI and send paragraphs to Telegram as they arrive."""
    try:
        # Get enhanced system prompt with book content
        system_prompt = load_enhanced_system_prompt()
        
        # Get model from environment or use default
        model = os.getenv('OPENAI_MODEL', 'gpt-4o')
        
        print(f"[TIMING] Starting streaming request at: {datetime.now().isoformat()}")
        stream_start = time.time()
        
        # Get streaming response from OpenAI
        stream = stream_openai_responses(user_message, chat_id, model, system_prompt)
        
        # Buffer for accumulating text
        current_text = ""
        sent_paragraphs = []
        response_id = None
        first_chunk_time = None
        
        for chunk in stream:
            if first_chunk_time is None:
                first_chunk_time = time.time()
                print(f"[TIMING] First chunk received at: {datetime.now().isoformat()} (after {(first_chunk_time - stream_start)*1000:.1f}ms)")
            
            # Handle different types of streaming events
            if hasattr(chunk, 'type'):
                if chunk.type == 'content.delta':
                    # Accumulate text content
                    if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'text'):
                        current_text += chunk.delta.text
                        
                        # Check for complete paragraphs (double newline)
                        while '\n\n' in current_text:
                            paragraph_end = current_text.find('\n\n')
                            paragraph = current_text[:paragraph_end].strip()
                            current_text = current_text[paragraph_end + 2:]
                            
                            if paragraph and paragraph not in sent_paragraphs:
                                paragraph_send_start = time.time()
                                await update.message.reply_text(paragraph)
                                paragraph_send_end = time.time()
                                sent_paragraphs.append(paragraph)
                                print(f"[TIMING] Paragraph sent in {(paragraph_send_end - paragraph_send_start)*1000:.1f}ms: {paragraph[:50]}...")
                
                elif chunk.type == 'response.done':
                    # Stream completed, get response ID
                    if hasattr(chunk, 'response'):
                        response_id = chunk.response.id
                        print(f"[TIMING] Stream completed at: {datetime.now().isoformat()}")
                        
                        # Update conversation state
                        from openai_client import conversation_state
                        conversation_state[chat_id] = {
                            "previous_response_id": response_id
                        }
        
        # Send any remaining text as final paragraph
        if current_text.strip() and current_text.strip() not in sent_paragraphs:
            await update.message.reply_text(current_text.strip())
            sent_paragraphs.append(current_text.strip())
            print(f"[TIMING] Final paragraph sent: {current_text.strip()[:50]}...")
        
        # Combine all paragraphs for logging
        full_response = '\n\n'.join(sent_paragraphs)
        
        # Log successful interaction
        log_llm_interaction(user_message, full_response, model, telegram_update, response_id=response_id)
        
        stream_end = time.time()
        total_time = stream_end - stream_start
        print(f"[TIMING SUMMARY] Total streaming time: {total_time*1000:.1f}ms | Paragraphs sent: {len(sent_paragraphs)}")
        
        return full_response
        
    except Exception as e:
        error_msg = str(e)
        print(f"OpenAI streaming error: {error_msg}")
        fallback_response = "Sorry, I'm having trouble processing your message right now."
        
        # Send fallback response
        await update.message.reply_text(fallback_response)
        
        # Log failed interaction
        log_llm_interaction(user_message, fallback_response, model or "gpt-4o", telegram_update, error_msg)
        
        return fallback_response

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle any incoming message and respond using streaming LLM."""
    request_start = time.time()
    print(f"[TIMING] Request received at: {datetime.now().isoformat()}")
    
    user_message = update.message.text
    chat_id = update.message.chat.id
    
    # Check if this is a reply to another message
    if update.message.reply_to_message:
        replied_text = update.message.reply_to_message.text or "[Non-text message]"
        # Format the message with the reply context
        user_message = f"[Replying to: \"{replied_text}\"]\n\n{user_message}"
    
    # Convert Telegram update to dict for logging
    telegram_update_dict = update.to_dict()
    
    # Stream LLM response and send paragraphs as they arrive
    await stream_llm_response(user_message, telegram_update_dict, chat_id, update)
    
    request_end = time.time()
    total_time = request_end - request_start
    print(f"[TIMING] Total request time: {total_time*1000:.1f}ms")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    await update.message.reply_text('Bot is running! Send me any message and I\'ll respond using AI.\n\nCommands:\n/new - Start a fresh conversation\n/instruct <instructions> - Update bot instructions')

async def new_conversation_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /new command to start a fresh conversation."""
    chat_id = update.message.chat.id
    
    # Clear conversation state for this chat
    if clear_conversation_state(chat_id):
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
        
        # Update system instructions by clearing conversation state
        update_system_instructions(new_instructions, update.message.chat.id)
        
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