from zhongzi import torrent, tracker, client
import asyncio
import logging
import sys


logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


async def main():
    t = torrent.Torrent('ubuntu-24.10-live-server-amd64.iso.torrent')
    cli = client.TorrentClient(t)

    asyncio.create_task( cli.start() )
    asyncio.create_task( cli.start() )
    asyncio.create_task( cli.start() )

    await asyncio.sleep(1000)


asyncio.run(main())
