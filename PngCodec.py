from dataclasses import dataclass
from io import SEEK_CUR, SEEK_SET, BufferedReader
from typing import Sequence


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


class PngDecodeError(UnicodeDecodeError):
    def __init__(self, file: BufferedReader, start: int, end: int, reason: str) -> None:
        file.seek(0, SEEK_SET)
        super().__init__("PNG", file.read(end), start, end, reason)


class PngDecoder:
    def __init__(self, filename, check_crc=True) -> None:

        file = StrictBufferedReader(filename)
        signature = file.read(len(Iso.SIGNATURE))
        if signature != Iso.SIGNATURE:
            raise PngDecodeError(file, 0, len(Iso.SIGNATURE), "invalid signature")

        if check_crc:
            crc = Crc()

        self.chunks_read = []
        self.image_data = bytearray()
        # Read chunks
        while file.readable():
            chunk_start = file.tell()
            length = int.from_bytes(file.read(Iso.SUB_CHUNK_SIZE))
            name = file.read(Iso.SUB_CHUNK_SIZE).decode(Iso.CHUNK_NAME_ENCODING)
            if not Iso.can_parse_chunk(name, self.chunks_read):
                if Iso.chunk_is_critical(name):
                    error_message = f"unrecognized critical chunk: {name}"
                    raise PngDecodeError(file, chunk_start, file.tell(), error_message)
                else:
                    # Ignore unrecognized non-critical chunks
                    file.seek(length + Iso.SUB_CHUNK_SIZE, SEEK_CUR)
                    print(f"ignoring chunk {name}")
                    continue

            # Read chunk data
            data = file.read(length)
            crc_code = int.from_bytes(file.read(Iso.SUB_CHUNK_SIZE))
            if check_crc and crc_code != crc.calculate(name.encode() + data):
                error_message = f"chunk {name} failed CRC"
                raise PngDecodeError(file, chunk_start, file.tell(), error_message)

            match name:
                case Iso.IMAGE_HEADER:
                    pass
                case Iso.IMAGE_DATA:
                    self.image_data.extend(data)
                case Iso.IMAGE_TRAILER:
                    pass

            self.chunks_read.append(name)
            print(f"decoded chunk {name}")


@dataclass(frozen=True)
class PngChunk:
    name: str
    required: bool = False
    multiple: bool = False
    consecutive: bool = False
    first: bool = False
    last: bool = False
    before: str | Sequence[str] = ()
    after: str | Sequence[str] = ()
    conflicts: str | Sequence[str] = ()
    dependencies: str | Sequence[str] = ()

    def __eq__(self, obj: object) -> bool:
        if isinstance(obj, str):
            return self.name == obj
        if isinstance(obj, (bytes, bytearray)):
            try:
                return self.name == obj.decode(Iso.CHUNK_NAME_ENCODING)
            except UnicodeDecodeError:
                return NotImplemented
        if isinstance(obj, type(self)):
            return vars(self) == vars(obj)
        return NotImplemented

    def __str__(self) -> str:
        return self.name


class Iso:

    # See http://www.libpng.org/pub/png/spec/iso/index-object.html#5PNG-file-signature
    SIGNATURE = b'\x89PNG\r\n\x1a\n'
    SUB_CHUNK_SIZE = 4
    CHUNK_NAME_ENCODING = 'ASCII'

    # ISO Defined Chunks
    IMAGE_HEADER = 'IHDR'
    PALETTE = 'PLTE'
    IMAGE_DATA = 'IDAT'
    IMAGE_TRAILER = 'IEND'
    TRANSPARENCY = 'tRNS'
    PRIMARY_CHROMATICITIES_AND_WHITE_POINT = 'cHRM'
    IMAGE_GAMMA = 'gAMA'
    EMBEDDED_ICC_PROFILE = 'iCCP'
    SIGNIFICANT_BITS = 'sBIT'
    STANDARD_RGB_COLOUR_SPACE = 'sRGB'
    TEXTUAL_DATA = 'tEXt'
    COMPRESSED_TEXTUAL_DATA = 'zTXt'
    INTERNATIONAL_TEXTUAL_DATA = 'iTXt'
    BACKGROUND_COLOUR = 'bKGD'
    IMAGE_HISTOGRAM = 'hIST'
    PHYSICAL_PIXEL_DIMENSIONS = 'pHYs'
    SUGGESTED_PALETTE = 'sPLT'
    IMAGE_LAST_MODIFICATION_TIME = 'tIME'

    # See http://www.libpng.org/pub/png/spec/iso/index-object.html#5ChunkOrdering
    _DEFINED_CHUNKS = (
        PngChunk('IHDR', required=True, first=True),
        PngChunk('PLTE', before="IDAT"),
        PngChunk('IDAT', required=True, multiple=True, consecutive=True),
        PngChunk('IEND', required=True, last=True),
        PngChunk('cHRM', before=("PLTE", "IDAT")),
        PngChunk('gAMA', before=("PLTE", "IDAT")),
        PngChunk('iCCP', before=("PLTE", "IDAT"), conflicts="sRGB"),
        PngChunk('sBIT', before=("PLTE", "IDAT")),
        PngChunk('sRGB', before=("PLTE", "IDAT"), conflicts="iCCP"),
        PngChunk('bKGD', after="PLTE", before="IDAT"),
        PngChunk('hIST', after="PLTE", before="IDAT", dependencies="PLTE"),
        PngChunk('tRNS', after="PLTE", before="IDAT"),
        PngChunk('pHYs', before="IDAT"),
        PngChunk('sPLT', multiple=True, before="IDAT"),
        PngChunk('tIME'),
        PngChunk('iTXt', multiple=True),
        PngChunk('tEXt', multiple=True),
        PngChunk('zTXt', multiple=True),
    )
    _REQUIRED_CHUNKS = set(pc.name for pc in _DEFINED_CHUNKS if pc.required)
    _CHUNK_MAP = {pc.name: pc for pc in _DEFINED_CHUNKS}

    class ChunkError(ValueError):
        pass

    @classmethod
    def can_parse_chunk(cls, name: str, chunks_read: list[str], suppress=True) -> bool:
        try:
            cls._check_chunk_ordering(name, chunks_read)
            return True
        except cls.ChunkError as e:
            if suppress:
                return False
            else:
                raise e

    @classmethod
    def _check_chunk_ordering(cls, name: str, chunks_read: list[str]) -> None:
        if name not in cls._CHUNK_MAP:
            if not name.isprintable():
                name = name.encode()
            raise cls.ChunkError(f"chunk {name} not recognized")

        new_chunk = cls._CHUNK_MAP[name]

        if new_chunk.first:
            if chunks_read:
                raise cls.ChunkError(f"chunk {name} is not first")
            return

        dependencies = list(new_chunk.dependencies)
        prev_i = None
        for i, chunk in enumerate(chunks_read):
            chunk_spec = cls._CHUNK_MAP[chunk]
            if chunk_spec.last:
                raise cls.ChunkError(f"last chunk was already read")
            if new_chunk.name in chunk_spec.after:
                raise cls.ChunkError(f"chunk {chunk} should come after {new_chunk}")
            if chunk_spec.name in new_chunk.before:
                raise cls.ChunkError(f"chunk {new_chunk} should come before {chunk}")
            if chunk_spec == new_chunk:
                if not new_chunk.multiple:
                    raise cls.ChunkError(f"multiple {new_chunk} chunks not allowed")
                if new_chunk.consecutive and prev_i is not None and prev_i != i - 1:
                    raise cls.ChunkError(f"{new_chunk} chunks must be consecutive")
                prev_i = i
            if chunk_spec.name in new_chunk.conflicts:
                raise cls.ChunkError(f"chunk {new_chunk} conflicts with {chunk}")
            if new_chunk.name in chunk_spec.conflicts:
                raise cls.ChunkError(f"chunk {chunk} conflicts with {new_chunk}")

            if chunk_spec.name in dependencies:
                dependencies.remove(chunk_spec)

        if dependencies:
            raise cls.ChunkError(f"{dependencies} must be read before chunk {new_chunk}")

        if new_chunk.last:
            required = set(c for c in (*chunks_read, name) if c in cls._REQUIRED_CHUNKS)
            if required != cls._REQUIRED_CHUNKS:
                raise cls.ChunkError(f"required chunks were not read before last chunk")

    @classmethod
    def chunk_is_critical(cls, name: str | bytes | bytearray) -> bool:
        """
        Test if the chunk is critical: the 5th bit of the first byte of
        the name is not set (i.e. the first character is uppercase)
        """
        if isinstance(name, str):
            name = name.encode(cls.CHUNK_NAME_ENCODING)
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


if __name__ == "__main__":
    from sys import argv
    if len(argv) == 2:
        _, filename = argv
        PngDecoder(filename)
    else:
        print(f"usage: python {argv[0]} <filename>")
        exit(1)
