import os
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

# Global dictionary to store conversation state per chat
# Structure: {chat_id: {"thread_id": "..."}}
conversation_state = {}

# Initialize OpenAI client
openai_client = None

# Global assistant ID - reused across all conversations
global_assistant_id = None

async def get_openai_client():
    """Get or create OpenAI client."""
    global openai_client
    if openai_client is None:
        openai_client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    return openai_client

async def get_or_create_global_assistant(system_prompt: str, model: str) -> str:
    """Get or create the global OpenAI assistant (reused across all conversations)."""
    global global_assistant_id
    
    if global_assistant_id is None:
        client = await get_openai_client()
        assistant = await client.beta.assistants.create(
            name="Telegram Bot Assistant",
            instructions=system_prompt,
            model=model
        )
        global_assistant_id = assistant.id
        print(f"Created new global assistant: {global_assistant_id}")
    
    return global_assistant_id

async def update_assistant_instructions(new_instructions: str, model: str) -> str:
    """Update the global assistant with new instructions."""
    global global_assistant_id
    client = await get_openai_client()
    
    if global_assistant_id is None:
        # Create new assistant if none exists
        return await get_or_create_global_assistant(new_instructions, model)
    else:
        # Update existing assistant
        updated_assistant = await client.beta.assistants.update(
            assistant_id=global_assistant_id,
            instructions=new_instructions
        )
        print(f"Updated assistant {global_assistant_id} with new instructions")
        return updated_assistant.id

async def get_openai_assistants_response(user_message: str, chat_id: int, model: str, system_prompt: str) -> tuple[str, str]:
    """Get response using OpenAI Assistants API with conversation state."""
    client = await get_openai_client()
    
    # Get or create the global assistant (reused across all chats)
    assistant_id = await get_or_create_global_assistant(system_prompt, model)
    
    # Get or create thread for this chat
    if chat_id not in conversation_state:
        thread = await client.beta.threads.create()
        conversation_state[chat_id] = {
            "thread_id": thread.id
        }
        print(f"Created new thread for chat {chat_id}: {thread.id}")
    
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
        assistant_id=assistant_id
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

async def clear_conversation_state(chat_id: int) -> bool:
    """Clear conversation state for a specific chat by creating a new thread."""
    client = await get_openai_client()
    
    if chat_id in conversation_state:
        # Create a new thread for this chat
        new_thread = await client.beta.threads.create()
        conversation_state[chat_id] = {
            "thread_id": new_thread.id
        }
        print(f"Created new thread for chat {chat_id}: {new_thread.id}")
        return True
    return False