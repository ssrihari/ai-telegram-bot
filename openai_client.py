import os
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

# Global dictionary to store conversation state per chat
# Structure: {chat_id: {"assistant_id": "...", "thread_id": "..."}}
conversation_state = {}

# Initialize OpenAI client
openai_client = None

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

def clear_conversation_state(chat_id: int) -> bool:
    """Clear conversation state for a specific chat."""
    if chat_id in conversation_state:
        del conversation_state[chat_id]
        return True
    return False