import sys
import os
import asyncio
import selectors
import uvicorn
from app.main import app

def main():
    config = uvicorn.Config(app, host=os.getenv("BILLING_HOST", "127.0.0.1"), port=int(os.getenv("BILLING_PORT", "8000")), log_level="info")
    server = uvicorn.Server(config)
    
    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop(selectors.SelectSelector())
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(server.serve())
        finally:
            loop.close()
    else:
        server.run()

if __name__ == "__main__":
    main()
