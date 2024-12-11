from collections import OrderedDict
from enum import Enum
from typing import List


class Token(Enum):
    INTEGER = b'i'
    LIST = b'l'
    DICT = b'd'
    END = b'e'
    STRING_SEPARATOR = b':'


class Decoder:
    def __init__(self, data: bytes):
        self._data = data
        self._index = 0

    def _peek(self) -> bytes | None:
        if self._index + 1 > len(self._data):
            return None
        return self._data[self._index:self._index+1]
    
    def _consume(self):
        self._index += 1

    def decode(self) -> int | str | List | OrderedDict:
        c = self._peek()
        if c is None:
            raise EOFError('unexpected end')
        elif c == Token.INTEGER.value:
            self._consume()
            return self._decode_integer()
        elif c in b'0123456789':
            return self._decode_string()
        elif c == Token.LIST.value:
            self._consume()
            return self._decode_list()
        elif c == Token.DICT.value:
            self._consume()
            return self._decode_dict()
        elif c == Token.END.value:
            return None
        else:
            raise RuntimeError(f'invalid token at {self._index}')

    def _read_until(self, token: bytes) -> bytes:
        try:
            occur = self._data.index(token, self._index)
            res = self._data[self._index:occur]
            self._index = occur + 1
            return res
        except ValueError:
            raise RuntimeError(f'unable to find token {str(token)}')
        
    def _read(self, length: int) -> bytes:
        if self._index + length > len(self._data):
            raise IndexError(f'cannot read {length} bytes from position {self._index}')
        res = self._data[self._index:self._index+length]
        self._index += length
        return res

    def _decode_integer(self):
        return int(self._read_until(Token.END.value))
         
    def _decode_string(self):
        str_len = int(self._read_until(Token.STRING_SEPARATOR.value))
        return self._read(str_len)
    
    def _decode_list(self):
        res = []
        while self._peek() != Token.END.value:
            res.append(self.decode())
        self._consume() # consume end

        return res
    
    def _decode_dict(self):
        res = OrderedDict()
        while self._peek() != Token.END.value:
            key = self.decode()
            value = self.decode()
            res[key] = value
        self._consume()

        return res
    

class Encoder:
    def __init__(self, data):
        self._data = data

    def encode(self) -> bytes:
        return self._encode_next(self._data)
    
    def _encode_next(self, data):
        if type(data) == str:
            return self._encode_string(data)
        elif type(data) == bytes:
            return self._encode_bytes(data)
        elif type(data) == int:
            return self._encode_integer(data)
        elif type(data) == list:
            return self._encode_list(data)
        elif type(data) == dict or type(data) == OrderedDict:
            return self._encode_dict(data)
        else:
            return None
        
    def _encode_string(self, val):
        return str.encode(str(len(val)) + ':' + val)
    
    def _encode_bytes(self, val):
        res = bytearray()
        res += str.encode(str(len(val)))
        res += b':'
        res += val
        return res
    
    def _encode_integer(self, val):
        return str.encode('i' + str(val) + 'e')
    
    def _encode_list(self, val: List) -> bytes:
        res = bytearray('l', 'utf-8')
        res += b''.join([self._encode_next(item) for item in val])
        res += b'e'
        return res

    def _encode_dict(self, val: dict) -> bytes:
        res = bytearray('d', 'utf-8')
        for k, v in val.items():
            key = self._encode_next(k)
            value = self._encode_next(v)

            if key and value:
                res += key
                res += value
            else:
                raise RuntimeError('bad dict')
        res += b'e'
        return res