# Purpose
I wanted a bot that will join me in a telegram group chat, and give me advice to talking to my son. This bot is powered by an LLM, with a pre-defined system prompt. It will respond to messages that are posted in the chat like a normal person.

- The bot behaves as a human participant in a Telegram group chat.
- It is actively helpful, but responds only when directly mentioned.
- It takes on the identity of a persona defined by a static system prompt.

# Tech choices
- Python as the primary language
- Makefile as the interface to build, run, and run any scripts
- use requirements.txt to manage python deps
- Makefile has a setup target that installs all pre-requisites for development, both cli utils like fly, and pip install
- Telegram Bot API
- Switchable model backend via litellm, but initially open AI's 4o
- FastAPI via uvicorn
- Use .env for secrets

## Hosting & Ops
- Target host is Fly.io for v0.
- Simple deployment, via make

## Prompt / Persona
- The system prompt is written in a single static Markdown file (e.g., persona.md).
- It is set as a secret in Fly.io via the fly command line options

## Update / Mutation
The prompt is not dynamically editable in v0, but future versions should support prompt editing via the Telegram client, ideally without requiring message-based commands.

Anyone in the chat may be allowed to update the prompt once that feature exists.

## Future Work (Explicitly Not In v0)
- No annoyance filtering, rate limiting, or moderation logic.
- No memory of prior messages beyond LLM context window.
- No administrative commands or access control.
- No message history storage or analytics.
- No dynamic role/persona switching.
