import asyncio, redis.asyncio as redis
async def main():
    r = redis.Redis(host="localhost", port=6379, db=0)
    print(await r.ping())
asyncio.run(main())