import asyncio
import logging
from .tracker import Tracker
from .torrent import Torrent, Piece
from .peer import Peer
from .dht import DHTServer
from typing import List
import random


class TorrentClient:
    def __init__(self, torrent: Torrent):
        self.torrent = torrent
        self.tracker = Tracker(torrent)
        self.peer_id = self.tracker.peer_id
        self.info_hash = torrent.info_hash
        self.valid_peers: List[Peer] = []
        self.valid_peers_lock = asyncio.Lock()

        self.piece_download_queue: asyncio.Queue[Piece] = asyncio.Queue(maxsize=5)
        self.piece_saver_queue: asyncio.Queue[Piece] = asyncio.Queue(maxsize=1)

        logging.info(f'torrent total pieces: {len(self.torrent.pieces)}')

    async def start(self):
        asyncio.create_task(self.collecting_peers())

        asyncio.create_task(self.download())

        await self.file_saver()

    async def download(self):
        asyncio.create_task(self.piece_generator())

        async with asyncio.TaskGroup() as tg:
            for i in range(150):
                tg.create_task(self.download_piece_worker(i))

    async def piece_generator(self):
        for piece in self.torrent.pieces:
            await self.piece_download_queue.put(piece)
        
    async def download_piece_worker(self, index):
        while True:
            try:
                piece = await self.piece_download_queue.get()
            except asyncio.QueueShutDown:
                logging.info(f'piece queue is shutdown, worker {index} exiting')
                break

            peer = await self.choose_peer(piece.index)
            try:
                piece.data = await peer.download_piece(piece)
                await self.piece_saver_queue.put(piece)
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
                logging.error(f'peer {peer} disconnected: {e}')
                async with self.valid_peers_lock:
                    if peer in self.valid_peers:
                        self.valid_peers.remove(peer)
                await self.piece_download_queue.put(piece)
            except Exception as e:
                logging.error(f'failed to download piece {piece.index} from peer {peer}: {e}')
                await self.piece_download_queue.put(piece)

    async def choose_peer(self, piece_index: int) -> Peer:
        while True:
            async with self.valid_peers_lock:
                random.shuffle(self.valid_peers)
                for peer in self.valid_peers:
                    if not peer.can_downlowd():
                        continue
                    if peer.has_piece(piece_index):
                        return peer
            
            logging.info(f'no peer can download piece {piece_index}, waiting')
            await asyncio.sleep(10)

    async def collecting_peers(self):
        s = DHTServer(('0.0.0.0', 9999), ids=bytes.fromhex("8df9e68813c4232db0506c897ae4c210daa98250"))
        await s.run()

        while True:
            async with self.valid_peers_lock:
                if len(self.valid_peers) > 15:
                    logging.debug(f'valid peers count is sufficient: {len(self.valid_peers)}, skipping DHT bootstrap')
                    await asyncio.sleep(10)
                    continue

            await s.bootstrap(max_nodes=100)
            self.peers = await s.get_peers(self.info_hash)

            logging.info(f'got {len(self.peers)} peers from DHT network: {self.peers}')

            for peer_info in self.peers:
                p = Peer(self.peer_id, self.info_hash, peer_info)
                try:
                    await p.connect()
                except Exception as e:
                    logging.error(f'skip, failed to connect to peer {peer_info}: {e}')
                    continue
                
                asyncio.create_task(p.run())

                async with self.valid_peers_lock:
                    self.valid_peers.append(p)
                    logging.info(f'connected to peer: {peer_info}')

    async def file_saver(self):
        downloaded_pieces = 0

        with open(self.torrent.name, 'wb') as f:
            while True:
                try:
                    piece = await self.piece_saver_queue.get()
                except asyncio.QueueShutDown:
                    logging.info('data queue is empty, file saver exiting')
                    break

                f.seek(piece.index * self.torrent.piece_length)
                f.write(piece.data)
                f.flush()
                logging.info(f'saved piece {piece.index} to file {self.torrent.name}')

                downloaded_pieces += 1
                if downloaded_pieces == len(self.torrent.pieces):
                    logging.info('all pieces downloaded, exiting')
                    self.piece_download_queue.shutdown()
                    self.piece_saver_queue.shutdown()
                    return
