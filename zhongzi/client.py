import asyncio
import logging
from .tracker import Tracker
from .torrent import Torrent
from .peer import Peer


class TorrentClient:
    def __init__(self, torrent: Torrent):
        self.tracker = Tracker(torrent)
        self.peer_id = self.tracker.peer_id
        self.info_hash = torrent.info_hash

    async def start(self):
        tracker_res = await self.tracker.connect()
        self.peers = tracker_res.peers

        logging.info(f'got {len(self.peers)} peers from tracker')

        
        for peer_info in self.peers:
            p = Peer(self.peer_id, self.info_hash, peer_info)
            await p.connect()
            
            asyncio.create_task(p.run())

            while not p.can_downlowd():
                logging.info('peer cannot download, waiting...')
                await asyncio.sleep(1)

            logging.info('peer can download, start downloading...')
            
            while len(p._remote_pieces) == 0:
                logging.info('peer has no pieces, waiting...')
                await asyncio.sleep(3)

            for piece_index in p._remote_pieces:
                await p.get_piece(piece_index, 0)
