import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath('.'))

from bot.services import vpn

async def main():
    try:
        res = await vpn.create_client("test_client_expiry", 3, 0)
        print("Create response:")
        print(res)
        
        info = await vpn.get_client("test_client_expiry")
        print("Info response:")
        print(info)
        
        await vpn.delete_client("test_client_expiry")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
