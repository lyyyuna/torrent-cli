from .bucket import Bucket
from .node import Node
from .util import decode_id
from typing import List


class RoutingTable:
    def __init__(self, local_id):
        self._local_id = local_id
        self._buckets = {Bucket(0, 2**160)}

    def add(self, node: Node):
        for bucket in self._buckets:
            if bucket.id_in_range(node.id):
                added = bucket.add(node)

                if not added and self._split(bucket):
                    return self.add(node)   

    def _split(self, bucket) -> bool:
        if bucket.range_max - bucket.range_min < Bucket.max_capacity:
            return False
        
        self._buckets.remove(bucket)

        mid = (bucket.range_min + bucket.range_max) >> 1

        for new_bucket in (Bucket(bucket.range_min, mid), Bucket(mid, bucket.range_max)):
            self._buckets.add(new_bucket)

            for node in bucket.good_nodes:
                if new_bucket.id_in_range(node.id):
                    new_bucket.add(node)

        return True
    
    def _get_closest(self, target_id: int) -> List[Node]:
        all_nodes = [node for bucket in self._buckets for node in bucket.good_nodes]
        return sorted(all_nodes, key=lambda node: node.distance_to(target_id))[:20]

    def __getitem__(self, item: int) -> List[Node]:
        return self._get_closest(item)
    
    def get_closest(self, target_id: bytes) -> List[Node]:
        return self._get_closest(decode_id(target_id))
    
    @staticmethod
    def get_closest_from_list(target_id: bytes, iterable):
        return sorted(iterable, key=lambda node: node.distance_to(decode_id(target_id)))[:20]