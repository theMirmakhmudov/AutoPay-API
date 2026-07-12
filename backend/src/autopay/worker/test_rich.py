import asyncio

import httpx

from autopay.core.config import settings


async def test():
    # We will send a message to the admin chat (6716993468)
    url = f"https://api.telegram.org/bot{settings.MANAGEMENT_BOT_TOKEN}/sendRichMessage"
    payload = {
        "chat_id": 6716993468,
        "rich_message": {
            "html": "<table bordered striped><caption><b>Test Rich Table</b></caption><tr><th>Column 1</th><th>Column 2</th></tr><tr><td>Hello</td><td>World</td></tr></table>"
        }
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=payload)
        print(r.status_code)
        print(r.text)

if __name__ == "__main__":
    asyncio.run(test())
