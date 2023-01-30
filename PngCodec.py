
from io import SEEK_CUR, SEEK_SET, BufferedReader


class StrictBufferedReader(BufferedReader):
    def __init__(self, filename: str) -> None:
        self.buffer = open(filename, 'rb')
        super().__init__(self.buffer)

    def read(self, size: int = None) -> bytes:
        data = self.buffer.read(size)
        if size is not None and (len_read := len(data)) != size:
            raise IOError(f"tried to read {size} bytes from buffer, recieved {len_read}")
        return data

    def readable(self) -> bool:
        bytes_read = len(self.buffer.read(n := 1))
        self.buffer.seek(-n, SEEK_CUR)
        return bytes_read == n


class PngDecodeError(ValueError):
    def __init__(self, file: BufferedReader, start: int, end: int, reason: str) -> None:
        file.seek(0, SEEK_SET)
        message = str(UnicodeDecodeError("PNG", file.read(), start, end, reason))
        super().__init__(message)


class PngDecoder:
    def __init__(self, filename, check_crc=True) -> None:
        PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
        SUB_CHUNK_SIZE = 4

        file = StrictBufferedReader(filename)
        signature = file.read(len(PNG_SIGNATURE))
        if signature != PNG_SIGNATURE:
            raise PngDecodeError(signature, 0, len(
                PNG_SIGNATURE), "invalid signature")

        if check_crc:
            crc = Crc()

        representation = {}

        # Read chunks
        while file.readable():
            chunk_start = file.tell()
            length = int.from_bytes(file.read(SUB_CHUNK_SIZE))
            name = file.read(SUB_CHUNK_SIZE)
            data = file.read(length)
            crc_code = int.from_bytes(file.read(SUB_CHUNK_SIZE))
            if check_crc and crc_code != crc.calculate(name + data):
                error_message = f"chunk {name} failed CRC"
                raise PngDecodeError(file, chunk_start, file.tell(), error_message)

            if self._chunk_is_critical(name):
                # Critical chunk
                pass
            else:
                # Ancillary chunk
                pass

            print(f"successfully parsed chunk {name}")

            representation[name] = data

    @staticmethod
    def _chunk_is_critical(name: bytes) -> bool:
        """
        Test if the chunk is critical: the 5th bit of the first byte of
        the name is not set (i.e. the first character is uppercase)
        """
        return not (name[0] & 0x20)


class Crc:
    """
    Cyclic Redundancy Check (CRC) algorithm
    Adapted from: http://libpng.org/pub/png/spec/iso/index-object.html#D-CRCAppendix
    """

    def __init__(self) -> None:
        # Table of CRCs of all 8-bit messages
        self.crc_table = [0] * 256

        for c in range(256):
            n = c
            for _ in range(8):
                if (c & 1):
                    c = 0xedb88320 ^ (c >> 1)
                else:
                    c = c >> 1
            self.crc_table[n] = c

    def _update_crc(self, crc: int, buf: bytes) -> int:
        """
        Update a running CRC with the bytes buf[0..len-1]--the CRC
        should be initialized to all 1's, and the transmitted value
        is the 1's complement of the final running CRC (see the
        routine below).
        """
        for byte in buf:
            crc = self.crc_table[(crc ^ byte) & 0xff] ^ (crc >> 8)
        return crc

    def calculate(self, buf: bytes) -> int:
        """
        Return the CRC of the bytes buf[0..len-1].
        """
        return self._update_crc(0xffffffff, buf) ^ 0xffffffff
