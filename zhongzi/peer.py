import asyncio
import logging
import struct
from .message import parse_one_message
from . import message
from enum import Enum


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

    async def connect(self):
        try:
            logging.info(f'opening tcp connetion to {self._peer_addr}')
            self.reader, self.writer = await asyncio.open_connection(self._peer_addr[0], self._peer_addr[1])
        except Exception as e:
            logging.error(f'connection to {self._peer_addr} refused: {e}')
            raise e
        
        await self.handshake()
        await self.send_interested()

        self._state_started()
        self._state_choked()

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
                    pass
                case message.Request():
                    logging.info('skip request message')
                case message.Cancel():
                    logging.info('skip cancel message')    
                case _:
                    logging.error(f'unhandled message: {msg}')
                    self._state_stopped()

    async def handshake(self):
        logging.info('handshaking with peer')
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
    
    async def get_piece(self, piece_index: int, offset: int) -> bytes:
        # if not self.has_piece(piece_index):
        #     raise ValueError(f'don\'t have piece {piece_index}')
        # if self._state_is_choked():
        #     raise ValueError('my peer is choked')
        data = message.Request(piece_index, offset).encode()
        self.writer.write(data)
        await self.writer.drain()
        logging.info(f'sent request message: piece_index={piece_index}, offset={offset}, data={data}')
