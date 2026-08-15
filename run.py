# github.com/MrAbhi2k3

import asyncio
from app.main import start_app

if __name__ == "__main__":
    try:
        asyncio.run(start_app())
    except (KeyboardInterrupt, SystemExit):
        pass
