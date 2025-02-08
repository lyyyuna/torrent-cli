from . import bencode
from hashlib import sha1
from dataclasses import dataclass
from typing import List


@dataclass
class TorrentFile:
    name: str
    length: int


class Torrent:
    def __init__(self, filename):
        self._filename = filename
        self.files: List[TorrentFile] = []
        self._is_multi_files = False

        with open(self._filename, 'rb') as f:
            meta = f.read()
            self.meta_info = bencode.Decoder(meta).decode()
            info = bencode.Encoder(self.meta_info[b'info']).encode()
            self._info_hash = sha1(info).digest()
            self._name = self.meta_info[b'info'][b'name'].decode('utf-8')
            self._piece_length = self.meta_info[b'info'][b'piece length']
            self._pieces = self.meta_info[b'info'][b'pieces']

            if b'files' in self.meta_info[b'info']:
                self._is_multi_files = True

                for file in self.meta_info[b'info'][b'files']:
                    paths: list = file[b'path']
                    name = b'/'.join(paths)
                    name = name.decode('utf-8')
                    self.files.append(TorrentFile(name, file[b'length']))
            else:
                self._is_multi_files = False
                length = self.meta_info[b'info'][b'length']
                self.files.append(TorrentFile(self._name, length))

    @property
    def announce(self) -> str:
        return self.meta_info[b'announce'].decode('utf-8')
    
    @property
    def info_hash(self) -> bytes:
        return self._info_hash

    @property
    def is_multi_files(self) -> bool:
        return self._is_multi_files
    
    @property
    def piece_length(self) -> int:
        return self._piece_length
    
    @property
    def total_size(self) -> int:
        if self.is_multi_files is True:
            total = 0
            for file in self.files:
                total += file.length
            return total
        else:
            return self.files[0].length

    @property
    def pieces(self):
        pieces: List[bytes] = []
        data = self.meta_info[b'info'][b'pieces']

        offset = 0
        while offset < len(data):
            pieces.append(data[offset:offset+20])
            offset += 20

        return pieces
    
    @property
    def name(self):
        return self._name
    
    def __str__(self):
        return f'name: {self.name}\n' \
            f'total length: {self.total_size}\n' \
            f'announce url: {self.announce}\n' \
            f'hash: {self.info_hash}'