import asyncio
from zhongzi.dht import DHTServer
import logging
import sys


async def main():
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

    s = DHTServer(('0.0.0.0', 9999), ids=bytes.fromhex("8df9e68813c4232db0506c897ae4c210daa98250"))

    await s.run()

    await s.bootstrap()

    results = await s.get_peers(bytes.fromhex("8df9e68813c4232db0506c897ae4c210daa98250"))

    logging.info(f"get_peers: {results}")


asyncio.run(main())