import asyncio
from typing import Tuple, List, Set
from .krpc import KRPCProtocol
from .node import Node
import logging
from .routing_table import RoutingTable
from .util import decode_id


class DHTServer:
    def __init__(self, bind: Tuple[str, int], ids: bytes):
        self._ids = ids
        self.id = decode_id(self._ids)
        self.bind = bind
        self._bootstrap_nodes = [
            ("67.215.246.10", 6881),  # router.bittorrent.com
            ("87.98.162.88", 6881),  # dht.transmissionbt.com
            ("82.221.103.244", 6881)  # router.utorrent.com
        ]
        self.routing_table = RoutingTable(self.id)

    async def run(self):
        loop = asyncio.get_event_loop()
        _, protocol = await loop.create_datagram_endpoint(
            lambda: KRPCProtocol(self._ids),
            local_addr=self.bind
        )
        self.protocol = protocol

    async def bootstrap(self, max_nodes: int | None):
        async def _find_node_with_catch(node: Node):
            try:
                return await self.protocol.find_node(node.addr)
            except TimeoutError:
                logging.warning(f'find_node timeout, ignore node {node}')

        known = set()
        peers: List[Node] = []
        for addr in self._bootstrap_nodes:
            peers.append(Node(self._ids, addr))

        while True:
            tasks : List[asyncio.Task[Node]] = []
            async with asyncio.TaskGroup() as tg:
                for node in peers:
                    task = tg.create_task(_find_node_with_catch(node))
                    tasks.append(task)

            candidates = set()
            for task in tasks:
                nodes = task.result() or []
                candidates.update(nodes)

                for node in nodes:
                    self.routing_table.add(node)

            closest = RoutingTable.get_closest_from_list(self._ids, candidates-known)

            if closest:
                known.update(closest)
                peers = closest
            else:
                break

            logging.debug(f'bootstrap: {len(known)} known nodes, {len(peers)} peers')

            if max_nodes:
                if len(known) > max_nodes:
                    break
            await asyncio.sleep(0.1)

    async def get_peers(self, info_hash: bytes) -> Set[Tuple[str, int]]:
        async def _get_peers_with_catch(node: Node):
            try:
                return await self.protocol.get_peers(node.addr, info_hash, timeout=2)
            except TimeoutError:
                logging.warning(f'get_peers timeout, ignore node {node}')

        known = set()
        result = set()

        peers: List[Node] = self.routing_table.get_closest(info_hash)
        
        while True:
            tasks = []
            async with asyncio.TaskGroup() as tg:
                for node in peers:
                    task = tg.create_task(_get_peers_with_catch(node))
                    tasks.append(task)

            candidates = set()
            for task in tasks:
                nodes = task.result() or []

                if len(nodes) == 0:
                    continue
                if isinstance(nodes[0], Node):
                    candidates.update(nodes)

                    for node in nodes:
                        self.routing_table.add(node)
                else:
                    result.update(nodes)
                    
            closest = RoutingTable.get_closest_from_list(info_hash, candidates-known)
            if closest:
                known.update(closest)
                peers = closest
            else:
                return result
            
            logging.debug(f'get_peers: {len(known)} known nodes, {len(peers)} peers')