from .util import decode_id, decode_addr
from typing import Tuple, List, Self
from datetime import datetime


class Node:
    def __init__(self, id: bytes, addr: Tuple[str, int]):
        self.id = decode_id(id)
        self.addr = addr
        self._created = datetime.now()
        self._modified = self._created

    def renew(self):
        self._modified = datetime.now()

    def distance_to(self, target: int) -> int:
        return self.id ^ target
    
    @property
    def modified(self):
        return self._modified
    
    @property
    def is_young(self) -> bool:
        now = datetime.now()
        delta = (now - self._modified).seconds

        if delta < 15 * 60:
            return True
        else:
            return False

    @staticmethod
    def decode_nodes(nodes: bytes) -> List[Self]:
        if len(nodes) % 26 != 0:
            raise ValueError("wrong length")
        
        return [Node(nodes[i: i + 20], decode_addr(nodes[i + 20: i + 26])) for i in range(0, len(nodes), 26)]

    def __str__(self):
        return f"{self.id}, {self.addr}"
    
    def __repr__(self):
        return f"Node({self.id}, {self.addr})"
    