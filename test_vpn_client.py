import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath('.'))

from bot.services import vpn
from bot.database.crud import get_all_users

async def main():
    try:
        users = await get_all_users()
        u = next((x for x in users if x.vpn_name), None)
        if not u:
            print("No users with vpn_name")
            return
            
        print("Checking", u.vpn_name)
        res = await vpn.get_client(u.vpn_name)
        print("Success:")
        print(res)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
