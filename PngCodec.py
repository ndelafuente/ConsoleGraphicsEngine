import struct

from collections import Counter, defaultdict
from dataclasses import dataclass
from io import SEEK_CUR, SEEK_SET, BufferedReader
from typing import Self, Sequence


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

        # Read chunks
        self.chunks_read = []
        image_data = bytearray()
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
                    header = struct.unpack("!II5B", data)
                    (width, height, bit_depth, color_type,
                     compression_method, filter_method, interlace_method) = header
                case Iso.PALETTE:
                    palette = tuple(struct.iter_unpack("!3B", data))
                case Iso.IMAGE_DATA:
                    image_data.extend(data)
                case Iso.IMAGE_TRAILER:
                    pass
                case Iso.TRANSPARENCY:
                    match color_type:
                        case 0:
                            grey_sample, = struct.unpack("!H", data)
                        case 2:
                            rgb_sample = struct.unpack("!3H", data)
                        case 3:
                            alpha_samples = tuple(struct.iter_unpack("!B", data))
                        case 4 | 6:
                            pass  # full aplpha channel is already present
                case Iso.PRIMARY_CHROMATICITIES_AND_WHITE_POINT:
                    color_space_info = struct.unpack("!8I", data)
                case Iso.IMAGE_GAMMA:
                    image_gamma = struct.unpack("!I", data) * 100000
                case Iso.EMBEDDED_ICC_PROFILE:
                    # Compression method at compressed[0]
                    profile_name, _, compressed = data.partition(b'\0')
                case Iso.SIGNIFICANT_BITS:
                    # num_fields = (3 if color_type & 2 else 1) + (1 if color_type & 4 else 0)
                    match color_type:
                        case 0:
                            grey_sbits = struct.unpack("!B", data)
                        case 2 | 3:
                            rgb_sbits = struct.unpack("!3B", data)
                        case 4:
                            greya_sbits = struct.unpack("!2B", data)
                        case 6:
                            rgba_sbits = struct.unpack("!4B", data)
                case Iso.STANDARD_RGB_COLOUR_SPACE:
                    rendering_intent = struct.unpack("!B", data)
                case Iso.TEXTUAL_DATA:
                    keyword, _, text_string = data.partition(b'\0')
                case Iso.COMPRESSED_TEXTUAL_DATA:
                    keyword, _, compressed_text = data.partition(b'\0')
                case Iso.INTERNATIONAL_TEXTUAL_DATA:
                    pass  # TODO
                case Iso.BACKGROUND_COLOUR:
                    match color_type:
                        case 0 | 4:
                            bkgd = struct.unpack("!H", data)
                        case 2 | 6:
                            bkgd = struct.unpack("!3H", data)
                        case 3:
                            bkgd = palette[struct.unpack("!B", data)]
                case Iso.IMAGE_HISTOGRAM:
                    histogram = struct.unpack(f"!{len(palette)}H", data)
                case Iso.PHYSICAL_PIXEL_DIMENSIONS:
                    ppu_x, ppu_y, unit_spec = struct.unpack("!IIB", data)
                case Iso.SUGGESTED_PALETTE:
                    pass  # TODO
                case Iso.IMAGE_LAST_MODIFICATION_TIME:
                    from datetime import datetime
                    time_last_modified = datetime(*struct.unpack("!H5B", data))

            self.chunks_read.append(name)
            print(f"decoded chunk {name}")

        image_data = zlib_decompress(image_data)


def zlib_decompress(image_data):
    FCHECK, = struct.unpack_from(f'!H', image_data)
    assert FCHECK % 31 == 0
    ADLER32_S2, ADLER32_S1 = struct.unpack_from(f'!HH', image_data, -4)

    zlib_bitstream = BitBuffer(image_data[:2])
    CM = zlib_bitstream.read(4)
    assert CM == 8
    CINFO = zlib_bitstream.read(4)

    FDICT = zlib_bitstream.read(1, offset=5)
    FLEVEL = zlib_bitstream.read(2)
    if FDICT:
        raise NotImplementedError

    bitstream = BitBuffer(image_data[2:-4])
    decompressed = bytearray()
    last_block = False
    while not last_block:
        last_block = bitstream.read(1)  # bfinal
        block_type = bitstream.read(2)  # btype

        if (block_type == 0b00):  # no compression
            bitstream.align_to_next_byte()
            # TODO ensure correct bit order
            LEN = bitstream.read(16)
            NLEN = bitstream.read(16)
            assert LEN == ~NLEN
            literal_data = bitstream.read(LEN)  # TODO copy data into decompressed
        elif (block_type == 0b11):  # reserved (error)
            raise ValueError("invalid block type")
        else:
            if (block_type == 0b10):  # compressed with dynamic Huffman codes
                # Read representation of code trees
                HLIT = bitstream.read(5) + 257  # number of Literal/Length codes
                HDIST = bitstream.read(5) + 1  # number of Distance codes
                HCLEN = bitstream.read(4) + 4  # number of Code Length codes
                code_length_codes = tuple(bitstream.iter_read(HCLEN, 3))

                CLC_ORDER = (
                    16, 17, 18, 0, 8, 7, 9, 6, 10, 5,
                    11, 4, 12, 3, 13, 2, 14, 1, 15
                )

                # TODO read encoded HLIT code lengths for LL alphabet
                # TODO read encoded HDIST code lengths for distance alphabet
                breakpoint()
            while True:
                value = bitstream.read()  # FIXME
                if value == 256:  # end of block
                    break


@dataclass
class HuffmanCode:
    symbol: int
    length: int
    __code: int = None

    @property
    def code(self):
        if self.__code is None:
            raise AttributeError(f"attribute 'code' has not been set")

        return self.__code

    @code.setter
    def code(self, value):
        self.__code = value


@dataclass
class HuffmanNode:
    branch_0: Self | None = None
    branch_1: Self | None = None
    symbol: int | None = None


class HuffmanTree:
    def __init__(self, alphabet: Sequence[int], code_lengths: Sequence[int]):
        # 1) Count the number of codes for each code length
        bl_count = Counter(code_lengths)

        # 2) Find the numerical value of the smallest code for each code length
        code = 0
        bl_count[0] = 0
        next_code = {}
        for bits in range(MAX_BITS := max(bl_count)):
            code = (code + bl_count[bits]) << 1
            next_code[bits + 1] = code

        """
        3) Assign numerical values to all codes, using consecutive
        values for all codes of the same length with the base
        values determined at step 2. Codes that are never used
        (which have a bit length of zero) must not be assigned a
        value.
        """
        self._length_lookup = defaultdict(dict)  # mapping: {length: {code: symbol}}
        tree = [HuffmanCode(sym, len) for sym, len in zip(alphabet, code_lengths)]
        for node in tree:
            if (node.length != 0):
                node.code = next_code[node.length]
                next_code[node.length] += 1

                self._length_lookup[node.length][node.code] = node.symbol

        tree.sort(key=lambda node: node.length)

        # Build tree TODO evaluate for removal?
        self.lookup_dict = {}  # mapping:: code: symbol
        self.root = HuffmanNode()
        for node in tree:
            self.insert(node.symbol, node.code, node.length)

    def insert(self, symbol, code, length):
        if code in self.lookup_dict:
            raise ValueError("insertion clashes with existing symbol")
        self.lookup_dict[code] = symbol

        cur = self.root
        for _ in range(length):
            if (code & 0b1):
                if cur.branch_1 is None:
                    cur.branch_1 = HuffmanNode()
                cur = cur.branch_1
            else:
                if cur.branch_0 is None:
                    cur.branch_0 = HuffmanNode()
                cur = cur.branch_0
            code >>= 1
        if cur.symbol is not None:
            raise ValueError("insertion clashes with existing symbol")
        cur.symbol = symbol

    def __getitem__(self, code):
        if isinstance(code, int):
            return self.lookup_dict[code]
        raise NotImplementedError(
            f"{type(self).__name__} indices must be integers,"
            f" not {type(code).__name__}"
        )

    def print(self):
        self.print_recur(self.root)

    def print_recur(self, cur: HuffmanNode, pre=''):
        if cur.symbol:
            print(cur.symbol, pre)
        if cur.branch_0 is not None:
            self.print_recur(cur.branch_0, '0'+pre)
        if cur.branch_1 is not None:
            self.print_recur(cur.branch_1, '1'+pre)

    def of_length(self, length):
        if length in self._length_lookup:
            return self._length_lookup[length]
        else:
            return {}

    def __contains__(self, code) -> bool:
        return code in self.lookup_dict
        cur = self.root
        while True:
            nex = cur.branch_1 if item & 0b1 else cur.branch_0
            if nex is None:
                return cur.symbol is not None
            cur = nex
            item >>= 1


class BitBuffer:
    BYTE_LENGTH = 8
    BIT_MASKS = tuple((1 << i) - 1 for i in range(BYTE_LENGTH + 1))

    def __init__(self, buffer: bytes | bytearray) -> None:
        self.buffer = buffer
        self.index = 0
        self.len = len(self.buffer) * self.BYTE_LENGTH

    def read(self, n: int, offset: int = 0):
        data = self._get(n, self.index + offset)
        self.index += n + offset
        return data

    def read_bytes(self, n: int):
        if not self.is_byte_aligned():
            raise NotImplementedError
        byte_index = self.index % self.BYTE_LENGTH
        return self.buffer[byte_index: byte_index + n]

    def read_huffman_code(self, tree: HuffmanTree):

        initial_index = self.index  # save index for later

        bits_read = tree[0].length  # minimum code length
        value = self.read(bits_read)

        max_len = tree[-1].length
        while bits_read <= max_len:
            next_bit = self.read(1)

            for node in tree:
                if node.code & (next_bit << bits_read):
                    pass

            bits_read += 1

        # No match was found
        self.index = initial_index
        return None

    def iter_read(self, times: int, n: int, offset: int = 0):
        for _ in range(times):
            yield self.read(n, offset)

    def is_byte_aligned(self):
        return (self.index % self.BYTE_LENGTH) == 0

    def align_to_next_byte(self):
        byte_index = self.index // self.BYTE_LENGTH
        self.index = (byte_index + 1) * self.BYTE_LENGTH

    def __len__(self):
        return self.len

    def _get(self, n: int, index: int):
        if n < 0:
            raise ValueError("cannot read negative length")
        if index < 0 or (index + n) > self.len:
            raise IndexError

        # Calculate byte and bit indices
        byte_index, bit_offset = divmod(index, self.BYTE_LENGTH)

        # Read data from first byte
        bit_count = min(n, self.BYTE_LENGTH - bit_offset)
        data = (self.buffer[byte_index] >> bit_offset) & self.BIT_MASKS[bit_count]
        byte_index += 1

        # NOTE: Any further reads should be byte-aligned (bit offset == 0)

        # Read any full bytes
        num_bytes, final_bits = divmod(n - bit_count, self.BYTE_LENGTH)
        for _ in range(num_bytes):
            data |= self.buffer[byte_index] << bit_count
            bit_count += self.BYTE_LENGTH
            byte_index += 1

        # Read final bits if necessary
        if final_bits:
            data |= (self.buffer[byte_index] & self.BIT_MASKS[final_bits]) << bit_count

        return data

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._get(1, key)
        if isinstance(key, tuple):
            if len(key) != 2 and not all(isinstance(k, int) for k in key):
                class_name = type(self).__name__
                raise ValueError(
                    f"{class_name} tuple indices must contain exactly two"
                    f" integers, i.e. <{class_name} object>[int, int]"
                )
            # TODO define behavior?
        if isinstance(key, slice):
            start, stop, stride = key.indices(self.len)
            start = self.len + start if start < 0 else start
            stop = self.len + stop if stop < 0 else stop

            data = self._get(stop - start, start)
            if stride == 1:
                return data
            else:
                return int(format(data, 'b')[::stride], base=2)

        raise TypeError(
            f"{type(self).__name__} indices must be integers,"
            f" tuples, or slices, not {type(key).__name__}"
        )


def unpack(buffer: bytes, format: str):
    # TODO incorporate into BitBuffer or remove
    offset = 0
    ret = []
    ordering = '@'
    if format[0][0] in '@=<>!':
        ordering = format[0][0]
    parsed_format = []
    digits = None
    for c in format:
        match c:
            case '[':
                if digits is not None:
                    raise SyntaxError
                digits = c
            case ']':
                parsed_format.append(int(digits))
    for part in format:
        if isinstance(part, str):
            part = part.split('S')
            for sub_part in part:
                struct.calcsize(sub_part)

            for c in part:
                match c:
                    case '@' | '=' | '<' | '>' | '!':
                        pass
                    case 'S':
                        str_end = buffer.find(b'\0', offset)
                        ret.append(buffer[offset:str_end])
                        offset = str_end + 1
                    case _:
                        struct.unpack_from(c, buffer, offset)

            match part.count('S'):
                case 0:
                    pass
                case 1:
                    part.partition('S')

    return tuple(ret)


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
