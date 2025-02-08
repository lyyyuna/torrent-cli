import bitstring
import struct
import asyncio
from enum import Enum
import logging


class PeerMessage(Enum):
    '''
    https://wiki.theory.org/BitTorrentSpecification#Messages
    '''
    Choke = 0
    Unchoke = 1
    Interested = 2
    NotInterested = 3
    Have = 4
    Bitfield = 5
    Request = 6
    Piece = 7
    Cancel = 8


class KeepAlive:
    '''
    ||
    '''
    def __str__(self):
        return 'KeepAlive'
    

class Choke:
    '''
    |len=1|id=0|
    '''
    def __str__(self):
        return 'Choke'


class Unchoke:
    '''
    |len=1|id=1|
    '''
    def __str__(self):
        return 'Unchoke'
    

class Interested:
    '''
    |len=1|id=2|
    '''
    def __str__(self):
        return 'Interested'

    def decode(self) -> bytes:
        return struct.pack('>Ib', 1, PeerMessage.Interested.value)


class NotInterested:
    '''
    |len=1|id=3|
    '''
    def __str__(self):
        return 'NotInterested'
    

class Have:
    '''
    |len=5|id=4|piece_index|
    '''
    def __init__(self, piece_index: int):
        self.piece_index = piece_index

    def __str__(self):
        return f'Have'
    
    @classmethod
    def decode(cls, data: bytes):
        piece_index = struct.unpack('>I', data)[0]
        return Have(piece_index)


class Bitfield:
    '''
    |len=1+X|id=5|bitfield|
    '''
    def __init__(self, bitfield: bitstring.BitArray):
        self.bitfield = bitfield

    def __str__(self):
        return 'Bitfield'
    
    @classmethod
    def decode(cls, data: bytes):
        parts = struct.unpack('>' + str(len(data)) + 's', data)
        return cls(parts[0])


class Request:
    '''
    |len=13|id=6|index|begin|length|
    '''
    def __init__(self, index = 0, begin = 0, length: int = 2**14):
        self.index = index
        self.begin = begin
        self.length = length

    def encode(self) -> bytes:
        return struct.pack('>IbIII',
                           13,
                           PeerMessage.Request.value,
                           self.index,
                           self.begin,
                           self.length)

    def __str__(self):
        return 'Request'
    

class Piece:
    '''
    |len=9+X|id=7|index|begin|block|
    '''
    def __init__(self, index: int, begin: int, block: bytes):
        self.index = index
        self.begin = begin
        self.block = block

    def __str__(self):
        return 'Piece'

    @classmethod
    def decode(cls, data: bytes):
        parts = struct.unpack('>II'+str(len(data)-8)+'s', data)
        return cls(parts[0], parts[1], parts[2])
    

class Cancel:
    '''
    |len=13|id=8|index|begin|length|
    '''
    def __init__(self, index = 0, begin = 0, length: int = 2**14):
        self.index = index
        self.begin = begin
        self.length = length

    @classmethod
    def decode(cls, data: bytes):
        parts = struct.unpack('>III', data)
        return cls(parts[0], parts[1], parts[2])

    def __str__(self):
        return 'Cancel'


async def parse_one_message(reader: asyncio.StreamReader) -> KeepAlive | Choke:
    length_bytes = await reader.readexactly(4)
    length = struct.unpack('>I', length_bytes)[0]
    if length == 0:
        return KeepAlive()
    
    id_bytes = await reader.readexactly(1)
    id = struct.unpack('>b', id_bytes)[0]

    data = b''
    if length > 1:
        data = await reader.readexactly(length - 1)

    match id:
        case PeerMessage.Choke.value:
            logging.info('received choke message')
            return Choke()
        case PeerMessage.Unchoke.value:
            logging.info('received unchoke message')
            return Unchoke()
        case PeerMessage.Interested.value:
            logging.info('received interested message')
            return Interested()
        case PeerMessage.NotInterested.value:
            logging.info('received not interested message')
            return NotInterested()
        case PeerMessage.Have.value:
            h = Have.decode(data)
            logging.info(f'received have message: {h.piece_index}')
            return h
        case PeerMessage.Bitfield.value:
            b = Bitfield.decode(data)
            logging.info(f'received bitfield message: {b.bitfield}')
            return b
        case PeerMessage.Request.value:
            logging.info('received request message')
            return Request()
        case PeerMessage.Piece.value:
            p = Piece.decode(data)
            logging.info('received piece message')
            return p
        case PeerMessage.Cancel.value:
            c = Cancel.decode(data)
            logging.info('received cancel message')
            return c
        case _:
            logging.error(f'unknown message id: {id}')
            raise ValueError(f'unknown message id: {id}')


class PeerMessageIterator:
    def __init__(self, reader: asyncio.StreamReader):
        self.reader = reader

    def __aiter__(self):
        return self
    
    async def __anext__(self):
        try:
            return await parse_one_message(self.reader)
        except Exception as e:
            logging.info(f'peer message iterator stopped: {e}')
            raise StopAsyncIteration()