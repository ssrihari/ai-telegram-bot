import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Global dictionary to store conversation state per chat
# Structure: {chat_id: {"previous_response_id": "..."}}
conversation_state = {}

# Initialize OpenAI client
openai_client = None

def get_openai_client():
    """Get or create OpenAI client."""
    global openai_client
    if openai_client is None:
        openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    return openai_client

def get_responses_input(user_message: str, system_prompt: str, previous_response_id: str = None) -> list:
    """Format input for Responses API."""
    input_messages = []
    
    # Add system instructions as developer message if no previous response
    if previous_response_id is None:
        input_messages.append({
            "role": "developer",
            "content": system_prompt
        })
    
    # Add user message
    input_messages.append({
        "role": "user", 
        "content": user_message
    })
    
    return input_messages

def update_system_instructions(new_instructions: str, chat_id: int) -> bool:
    """Update system instructions by clearing conversation state."""
    # In Responses API, we need to start fresh to change instructions
    if chat_id in conversation_state:
        del conversation_state[chat_id]
        print(f"Cleared conversation state for chat {chat_id} to update instructions")
        return True
    return False

def stream_openai_responses(user_message: str, chat_id: int, model: str, system_prompt: str):
    """Stream response using OpenAI Responses API with conversation state."""
    client = get_openai_client()
    
    # Get previous response ID if exists
    previous_response_id = None
    if chat_id in conversation_state:
        previous_response_id = conversation_state[chat_id]["previous_response_id"]
    
    # Format input messages
    input_messages = get_responses_input(user_message, system_prompt, previous_response_id)
    
    # Create streaming response
    response_params = {
        "model": model,
        "input": input_messages,
        "stream": True
    }
    
    if previous_response_id:
        response_params["previous_response_id"] = previous_response_id
    
    print(f"Starting streaming response for chat {chat_id}")
    return client.responses.create(**response_params)

def get_openai_responses_response(user_message: str, chat_id: int, model: str, system_prompt: str) -> tuple[str, str]:
    """Get response using OpenAI Responses API with conversation state (non-streaming fallback)."""
    client = get_openai_client()
    
    # Get previous response ID if exists
    previous_response_id = None
    if chat_id in conversation_state:
        previous_response_id = conversation_state[chat_id]["previous_response_id"]
    
    # Format input messages
    input_messages = get_responses_input(user_message, system_prompt, previous_response_id)
    
    # Create response
    response_params = {
        "model": model,
        "input": input_messages
    }
    
    if previous_response_id:
        response_params["previous_response_id"] = previous_response_id
    
    response = client.responses.create(**response_params)
    
    # Store response ID for future conversations
    conversation_state[chat_id] = {
        "previous_response_id": response.id
    }
    
    # Extract response text
    response_content = response.output[0].content[0].text
    
    print(f"Response created for chat {chat_id}: {response.id}")
    return response_content, response.id

def clear_conversation_state(chat_id: int) -> bool:
    """Clear conversation state for a specific chat."""
    if chat_id in conversation_state:
        del conversation_state[chat_id]
        print(f"Cleared conversation state for chat {chat_id}")
        return True
    return False