from .node import Node
from datetime import datetime
from typing import Dict, Generator, List


class Bucket:
    max_capacity = 8

    def __init__(self, range_min: int, range_max: int):
        self._range_min = range_min
        self._range_max = range_max
        self._nodes: Dict[int, Node] = {}

    def id_in_range(self, node_id: int) -> bool:
        return self._range_min <= node_id < self._range_max
    
    def add(self, node: Node) -> bool:
        if not self.id_in_range(node.id):
            raise ValueError(f"Node {node} is out of range [{self._range_min}, {self._range_max})")
        
        if node.id in self._nodes:
            self._nodes[node.id].renew()
            return True
        elif len(self._nodes) < Bucket.max_capacity:
            self._nodes[node.id] = node
            return True
        else:
            nodes_to_delete = self.bad_nodes
            if nodes_to_delete:
                for node in nodes_to_delete:
                    self._nodes.pop(node.id)

                return self.add(node)
            else:
                return False

    def _enum_nodes(self) -> Generator[Node]:
        for id, node in self._nodes.items():
            yield node

    @property
    def bad_nodes(self) -> List[Node]:
        return list(filter(lambda n: n.is_young is False, self._enum_nodes()))
    
    @property
    def good_nodes(self) -> List[Node]:
        return list(filter(lambda n: n.is_young is True, self._enum_nodes()))

    @property
    def range_min(self) -> int:
        return self._range_min
    
    @property
    def range_max(self) -> int:
        return self._range_max