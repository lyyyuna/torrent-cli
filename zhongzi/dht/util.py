from socket import inet_aton, inet_ntoa


def encode_id(id: int) -> bytes:
    return id.to_bytes(20, "big")


def decode_id(id: bytes) -> int:
    if len(id) != 20:
        raise ValueError("invalid length")
    
    return int.from_bytes(id, "big")


def decode_info_hash(info_hash: bytes) -> int:
    return decode_id(info_hash)


def encode_info_hash(info_hash: int) -> bytes:
    return info_hash.to_bytes(20, "big")


def decode_addr(addr):
    host, port = addr[:4], addr[4:6]
    return (inet_ntoa(host), int.from_bytes(port, "big"))
