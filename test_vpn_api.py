import asyncio
import sys
import os

# Add bot to path
sys.path.insert(0, os.path.abspath('.'))

from bot.services import vpn

async def main():
    try:
        res = await vpn.list_clients()
        print("Success:", type(res))
        if isinstance(res, dict):
            print(list(res.keys()))
        elif isinstance(res, list):
            print("List of length", len(res))
            if res: print(res[0])
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
