import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv
from bot import create_bot_application

load_dotenv()

# Global bot application
bot_app = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage bot lifecycle with FastAPI."""
    global bot_app
    
    # Start bot on startup
    try:
        bot_app = create_bot_application()
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling()
        print("Telegram bot started successfully")
    except Exception as e:
        print(f"Failed to start Telegram bot: {e}")
    
    yield
    
    # Stop bot on shutdown
    if bot_app:
        try:
            await bot_app.updater.stop()
            await bot_app.stop()
            await bot_app.shutdown()
            print("Telegram bot stopped")
        except Exception as e:
            print(f"Error stopping bot: {e}")

app = FastAPI(title="Telegram Bot Maker", version="0.1.0", lifespan=lifespan)

@app.get("/ping")
async def ping():
    return {"message": "pong"}

@app.get("/bot/status")
async def bot_status():
    """Check if the bot is running."""
    global bot_app
    is_running = bot_app is not None and bot_app.updater.running
    return {"bot_running": is_running}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)