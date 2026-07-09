import asyncio
import httpx
from core.config import settings

async def test():
    chat_id = 6716993468
    message_id = 61 # We got this from previous output!
    url = f"https://api.telegram.org/bot{settings.MANAGEMENT_BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "rich_message": {
            "html": "<table bordered striped><caption><b>Edited Rich Table</b></caption><tr><th>Column 1</th><th>Column 2</th></tr><tr><td>Hello</td><td>Edit!</td></tr></table>"
        }
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=payload)
        print(r.status_code)
        print(r.text)

if __name__ == "__main__":
    asyncio.run(test())
