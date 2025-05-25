import asyncio
import logging
import struct
from .message import parse_one_message
from . import message
from enum import Enum
from .torrent import Piece
import hashlib
from typing import Dict


class PeerState(Enum):
    Running = 1 << 1
    Choked = 1 << 2


class Peer:
    def __init__(self, my_peer_id: str, info_hash: bytes, peer_addr: tuple):
        self._peer_addr = peer_addr
        self._my_peer_id = my_peer_id.encode('utf-8')
        self._info_hash = info_hash
        self._state_stopped()
        self._remote_pieces = {}

        self.futures: Dict[str, asyncio.Future] = {}

    async def connect(self):
        try:
            logging.info(f'opening tcp connetion to {self._peer_addr}')
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self._peer_addr[0], self._peer_addr[1]),
                timeout=2
            )
        except Exception as e:
            logging.error(f'connection to {self._peer_addr} refused: {e}')
            raise
        
        await self.handshake()
        await self.send_interested()

        self._state_started()
        self._state_choked()

        asyncio.create_task(self.heartbeat())

    async def run(self):
        async for msg in message.PeerMessageIterator(self.reader):
            if not self._state_is_running():
                break

            match msg:
                case message.Unchoke():
                    self._state_unchoked()
                case message.Choke():
                    self._state_choked()
                case message.Interested():
                    logging.info('skip interested message')
                case message.NotInterested():
                    logging.info('skip not interested message')
                case message.Have():
                    self._remote_pieces[msg.piece_index] = True
                case message.KeepAlive():
                    logging.info('skip keep alive message')
                case message.Piece():
                    index = msg.index
                    offset = msg.begin
                    key = f'{index}-{offset}'
                    if key not in self.futures:
                        logging.warning(f'the piece message is not the one we want: {key}')
                        continue
                    future = self.futures.pop(key)
                    if future and not future.done():
                        future.set_result(msg.block)

                case message.Bitfield():
                    bitfield = msg.bitfield
                    piece_index = 0
                    for byte in bitfield:
                        for i in range(7, -1, -1):
                            bit = (byte >> i) & 1
                            if bit == 1:
                                self._remote_pieces[piece_index] = True
                            piece_index += 1

                case message.Request():
                    logging.info('skip request message')
                case message.Cancel():
                    logging.info('skip cancel message')    
                case _:
                    logging.error(f'unhandled message: {msg}')
                    self._state_stopped()

    async def handshake(self):
        logging.info(f'handshaking with peer {self._peer_addr}')
        self.writer.write(struct.pack(
            '>B19s8x20s20s',
            19,                         # Single byte (B)
            b'BitTorrent protocol',     # String 19s
                                        # Reserved 8x (pad byte, no value)
            self._info_hash,            # String 20s
            self._my_peer_id) 
        )
        await self.writer.drain()

        data = await self.reader.read(68)
        logging.debug(f'received handshake: {data}')

        parts = struct.unpack('>B19s8x20s20s', data)
        # check info hash
        if parts[2] != self._info_hash:
            logging.error('info hash mismatch')
            raise ValueError('info hash mismatch')

    async def heartbeat(self):
        while True:
            if not self._state_is_running():
                await asyncio.sleep(10)
                continue
            try:
                await self.keep_alive()
                logging.debug(f'heartbeat to peer {self._peer_addr}')
                await asyncio.sleep(60)
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
                logging.error(f'heartbeat loop, peer {self._peer_addr} disconnected: {e}')
                return
            except Exception as e:
                logging.warning(f'heartbeat loop error: {e}')
                continue

    async def keep_alive(self):
        self.writer.write(message.KeepAlive().encode())
        await self.writer.drain()
        logging.info(f'sent keep alive message to peer {self._peer_addr}')
        
    def _state_stopped(self):
        self._state = 0

    def _state_started(self):
        self._state = PeerState.Running.value

    def _state_is_running(self):
        return self._state & PeerState.Running.value

    def _state_choked(self):
        self._state |= PeerState.Choked.value

    def _state_unchoked(self):
        self._state &= ~PeerState.Choked.value

    def _state_is_choked(self):
        return self._state & PeerState.Choked.value
    
    def can_downlowd(self):
        return self._state_is_running() and not self._state_is_choked()

    async def send_interested(self):
        self.writer.write(message.Interested().decode())
        await self.writer.drain()
        logging.info('sent interested message')

    def has_piece(self, piece_index: int) -> bool:
        return piece_index in self._remote_pieces
    
    async def get_piece(self, piece_index: int, offset: int, length: int=2**14) -> bytes:
        data = message.Request(piece_index, offset, length).encode()
        self.writer.write(data)
        await self.writer.drain()
        logging.debug(f'sent request message: piece_index={piece_index}, offset={offset}, length={length}')

        future = asyncio.Future()
        self.futures[f'{piece_index}-{offset}'] = future
        try:
            res = await asyncio.wait_for(future, timeout=60)
            return res
        except TimeoutError as e:
            logging.error(f'timeout while waiting for piece {piece_index}-{offset}')
            self.futures.pop(f'{piece_index}-{offset}', None)
            raise

    async def send_have(self, piece_index: int):
        self.writer.write(message.Have(piece_index=piece_index).encode())
        await self.writer.drain()
        logging.info(f'sent have message: piece_index={piece_index}')

    async def download_piece(self, piece: Piece) -> bytes:
        buf = bytearray()
        for block in piece.blocks:
            block_data = await self.get_piece(piece.index, block.offset, block.length)
            buf.extend(block_data)

        piece_data = bytes(buf)
        checksum = hashlib.sha1(piece_data)
        if checksum.digest() != piece.checksum:
            raise ValueError(f'piece checksum mismatch: {checksum.hexdigest()} != {piece.checksum.hex()}')
        
        await self.send_have(piece.index)

        logging.info(f'downloaded piece {piece.index} from {self._peer_addr}')

        return piece_data