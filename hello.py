from zhongzi import torrent, tracker, client
import asyncio
import logging
import sys


logging.basicConfig(stream=sys.stdout, level=logging.DEBUG,
                    format="%(asctime)s - %(levelname)s - %(message)s",  # 添加 %(asctime)s 表示时间
                    datefmt="%Y-%m-%d %H:%M:%S",  # 定义时间格式
                    )


async def main():
    t = torrent.Torrent('ubuntu-14.04.6-server-amd64.iso.torrent')
    cli = client.TorrentClient(t)

    await cli.start()


asyncio.run(main())
