import asyncio
import logging
from typing import Dict, List
from ..bencode import Encoder, Decoder
from .util import decode_addr
from .node import Node


class KRPCProtocol(asyncio.DatagramProtocol):
    def __init__(self, node_id: bytes=None):
        self.futures: Dict[bytes, asyncio.Future] = {}
        self.transaction_id = 1

        if node_id is None:
            node_id = bytes.fromhex("8df9e68813c4232db0506c897ae4c210daa98250")
        self.node_id = node_id

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        msg = Decoder(data).decode()

        if b't' not in msg:
            logging.warning(f'msg do not contain transaction id: {msg}')
            return
        
        tid: bytes = msg[b't']
        
        if tid not in self.futures:
            logging.warning(f'invalid tansaction id: {tid}')
            return

        future = self.futures.pop(tid)
        if future and not future.done():
            future.set_result(msg)
             
    async def find_node(self, addr, target: bytes=None, timeout=5) -> List[Node]:
        future = asyncio.Future()
        tid = self._get_transaction_id()

        self.futures[tid] = future

        if target is None:
            target = self.node_id

        msg = {
            b"t" : tid,
            b"y" : b"q",
            b"q" : b"find_node",
            b"a" : {
                b"id" : self.node_id,
                b"target" : target
            }
        }

        self.transport.sendto(Encoder(msg).encode(), addr)

        try:
            res = await asyncio.wait_for(future, timeout=timeout)
            return Node.decode_nodes( res[b'r'][b'nodes'] )
        except asyncio.TimeoutError:
            self.futures.pop(tid, None)
            raise TimeoutError(f"krpc find_node timeout after {timeout} seconds for {addr}")
        except Exception as e:
            self.futures.pop(tid, None)
            logging.error(f"find_node error: {e}, res: {res}")

    async def get_peers(self, addr, info_hash: bytes, timeout=5) -> List[Node]:
        future = asyncio.Future()
        tid = self._get_transaction_id()

        self.futures[tid] = future

        msg = {
            b"t" : tid,
            b"y" : b"q",
            b"q" : b"get_peers",
            b"a" : {
                b"id" : self.node_id,
                b"info_hash" : info_hash,
            }
        }

        self.transport.sendto(Encoder(msg).encode(), addr)

        try:
            res = await asyncio.wait_for(future, timeout=timeout)
            r = res.get(b'r')
            if b'values' in r:
                peers = []
                for value in r[b'values']:
                    peers.append(decode_addr(value))
                return peers
            if b'nodes' in r:
                return Node.decode_nodes( r[b'nodes'] )
        except asyncio.TimeoutError:
            self.futures.pop(tid, None)
            raise TimeoutError(f"krpc get_peers timeout after {timeout} seconds for {addr}")
        except Exception as e:
            self.futures.pop(tid, None)
            logging.error(f"get_peers error: {e}, res: {res}")        

        return []

    def _get_transaction_id(self) -> bytes:
        self.transaction_id = (self.transaction_id + 1) % 0x10000
        return self.transaction_id.to_bytes(2, "big")