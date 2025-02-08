import aiohttp
from . import bencode
from . import torrent
import random
import logging
from typing import List
import socket
from struct import unpack
from urllib.parse import urlencode


class TrackerResponse:
    def __init__(self, res: dict):
        self._res = res

    @property
    def interval(self) -> int:
        return self._res.get(b'interval', 0)
        
    @property
    def peers(self) -> List[tuple]:
        peers = self._res[b'peers']
        peers = [peers[i:i+6] for i in range(0, len(peers), 6)]

        return [(socket.inet_ntoa(p[:4]), unpack('>H',p[4:])[0]) for p in peers]

    def __str__(self):
        return f'interval: {self.interval}\n' \
            f'peers: {", ".join([x for (x, _) in self.peers])}'
    

class Tracker:
    def __init__(self, torrent: torrent.Torrent):
        self._torrent = torrent
        self.peer_id = _calculate_peer_id()

    async def connect(self, uploaded=0, downloaded=0) -> TrackerResponse:
        params = {
            'info_hash': self._torrent.info_hash,
            'peer_id': self.peer_id,
            'port': 6889,
            'uploaded': uploaded,
            'downloaded': downloaded,
            'compact': 1,
            'left': self._torrent.total_size - downloaded
        }

        url = self._torrent.announce + '?' + urlencode(params)
        logging.info(f'connecting to tracker {url}')
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as res:
                if not res.status == 200:
                    raise ConnectionError(f'unable to connect to tracker: status code {res.status}')
                
                data = await res.read()

                try:
                    message = data.decode('utf-8')
                    if 'failure' in message:
                        raise ConnectionError(f'unable to connect to tracker: {message}')
                except UnicodeDecodeError:
                    pass

                return TrackerResponse(bencode.Decoder(data).decode())


def _calculate_peer_id():
    return '-PC0001-' + ''.join(
        [str(random.randint(0, 9)) for _ in range(12)]) 