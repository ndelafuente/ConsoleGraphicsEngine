import struct

from collections import Counter, defaultdict
from dataclasses import dataclass
from io import SEEK_CUR, SEEK_SET, BufferedReader
from typing import Sequence

INFGEN = False


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
                    if not INFGEN:
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
                            alpha_samples = tuple(s[0] for s in alpha_samples)
                            missing_samples = len(palette) - len(alpha_samples)
                            if missing_samples > 0:
                                alpha_samples += tuple([255] * missing_samples)
                            elif missing_samples < 0:
                                raise PngDecodeError("too many alpha samples provided")
                        case 4 | 6:
                            pass  # full aplpha channel is already present
                case Iso.PRIMARY_CHROMATICITIES_AND_WHITE_POINT:
                    color_space_info = struct.unpack("!8I", data)
                case Iso.IMAGE_GAMMA:
                    image_gamma, = struct.unpack("!I", data)
                    image_gamma *= 100000
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
            if not INFGEN:
                print(f"decoded chunk {name}")

        image_data = zlib_decompress(image_data)
        assert len(image_data) % height == 0
        bb = BitBuffer(image_data)
        image = []
        for _ in range(height):
            filter_type = bb.read(8)
            if filter_type != 0:
                raise NotImplementedError("unsupported filter method")
            for pixel in bb.iter_read(width, bit_depth):
                r, g, b = palette[pixel]
                a = alpha_samples[pixel]
                image.append((r, g, b, a))

        self.image = image


def zlib_decompress(image_data):
    if INFGEN:
        print('! infgen 3.0 output', '!', 'zlib', sep='\n')
    FCHECK, = struct.unpack_from('!H', image_data)
    assert FCHECK % 31 == 0
    ADLER32_S2, ADLER32_S1 = struct.unpack_from('!HH', image_data, -4)

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

        if INFGEN:
            print("!")
            if last_block:
                print("last")

        if (block_type == 0b00):  # no compression
            bitstream.align_to_next_byte()
            LEN = bitstream.read(16)
            NLEN = bitstream.read(16)
            assert LEN == ~NLEN
            literal_data = bitstream.read_bytes(LEN)
            decompressed.extend(literal_data)
        elif (block_type == 0b11):  # reserved (error)
            raise ValueError("invalid block type")
        else:
            if (block_type == 0b10):  # compressed with dynamic Huffman codes
                # Read representation of code trees
                HLIT = bitstream.read(5) + 257  # number of Literal/Length codes
                HDIST = bitstream.read(5) + 1  # number of Distance codes
                HCLEN = bitstream.read(4) + 4  # number of Code Length codes

                CLEN_ORDER = (
                    16, 17, 18, 0, 8, 7, 9, 6, 10, 5,
                    11, 4, 12, 3, 13, 2, 14, 1, 15
                )
                clen_lengths = [0] * len(CLEN_ORDER)
                for i in range(HCLEN):
                    clen_lengths[CLEN_ORDER[i]] = bitstream.read(3)
                cl = HuffmanTree(sorted(CLEN_ORDER), clen_lengths)

                # TODO refactor?
                lit_code_lengths = bitstream.read_code_lengths(HLIT,  cl)
                dist_code_lengths = bitstream.read_code_lengths(HDIST, cl)
                LITERAL_ALPHABET = tuple(range(256))  # 0..255 inclusive
                LENGTH_ALPHABET = tuple(range(257, 285 + 1))  # 257..285 inclusive
                lit_len_tree = HuffmanTree(tuple(range(HLIT)), lit_code_lengths)
                dist_tree = HuffmanTree(tuple(range(HDIST)), dist_code_lengths)

                if INFGEN:
                    print("dynamic")
                    print("count", HLIT, HDIST, HCLEN)
                    for v, l in lit_len_tree.pairs():
                        print('! litlen', v, l)
                    for v, l in dist_tree.pairs():
                        print('! dist', v, l)
            else:
                raise NotImplementedError("have not yet implemented block type 0b01")

            while True:
                code = bitstream.read_huffman_code(lit_len_tree)
                if code == 256:  # end of block
                    if INFGEN:
                        print("end")
                    break
                elif code < 256:  # literal
                    decompressed.append(code)
                    if INFGEN:
                        if 32 <= code < 127:
                            print(f"literal '{chr(code)}")
                        else:
                            print('literal', code)
                else:  # length
                    LENGTH_EXTRA_BITS = {
                        257: (0, 3), 258: (0, 4), 259: (0, 5),
                        260: (0, 6), 261: (0, 7), 262: (0, 8),
                        263: (0, 9), 264: (0, 10), 265: (1, 11),
                        266: (1, 13), 267: (1, 15), 268: (1, 17),
                        269: (2, 19), 270: (2, 23), 271: (2, 27),
                        272: (2, 31), 273: (3, 35), 274: (3, 43),
                        275: (3, 51), 276: (3, 59), 277: (4, 67),
                        278: (4, 83), 279: (4, 99), 280: (4, 115),
                        281: (5, 131), 282: (5, 163), 283: (5, 195),
                        284: (5, 227), 285: (0, 258)
                    }
                    DIST_EXTRA_BITS = {
                        0: (0, 1), 1: (0, 2), 2: (0, 3), 3: (0, 4),
                        4: (1, 5), 5: (1, 7), 6: (2, 9), 7: (2, 13),
                        8: (3, 17), 9: (3, 25), 10: (4, 33), 11: (4, 49),
                        12: (5, 65), 13: (5, 97), 14: (6, 129), 15: (6, 193),
                        16: (7, 257), 17: (7, 385), 18: (8, 513), 19: (8, 769),
                        20: (9, 1025), 21: (9, 1537), 22: (10, 2049), 23: (10, 3073),
                        24: (11, 4097), 25: (11, 6145), 26: (12, 8193), 27: (12, 12289),
                        28: (13, 16385), 29: (13, 24577)
                    }
                    extra_bits, base_length = LENGTH_EXTRA_BITS[code]
                    length = bitstream.read(extra_bits) + base_length

                    dist_code = bitstream.read_huffman_code(dist_tree)

                    extra_bits, base_dist = DIST_EXTRA_BITS[dist_code]
                    dist = bitstream.read(extra_bits) + base_dist

                    initial_length = len(decompressed)
                    for i in range(length):
                        decompressed.append(decompressed[initial_length - dist + i])

                    if INFGEN:
                        print("match", length, dist)
    s1 = 1
    s2 = 0
    for byte in decompressed:
        s1 += byte
        s2 += s1
    s1 %= 65521
    s2 %= 65521

    assert ADLER32_S1 == s1
    assert ADLER32_S2 == s2

    if INFGEN:
        print("\n!\nadler")

    return decompressed


class HuffmanTree:
    def __init__(self, alphabet: Sequence[int], code_lengths: Sequence[int]):
        if len(alphabet) != len(code_lengths):
            raise ValueError("alphabet and code lengths do not match up")

        # 1) Count the number of codes for each code length
        bl_count = Counter(code_lengths)

        # 2) Find the numerical value of the smallest code for each code length
        code = 0
        bl_count[0] = 0
        next_code = {}
        for bits in range(max(bl_count)):
            code = (code + bl_count[bits]) << 1
            next_code[bits + 1] = code

        """
        3) Assign numerical values to all codes, using consecutive
        values for all codes of the same length with the base
        values determined at step 2. Codes that are never used
        (which have a bit length of zero) must not be assigned a
        value.
        """
        non_zero_code_lengths = [l for l in code_lengths if l != 0]
        self.min_length = min(non_zero_code_lengths)
        self.max_length = max(non_zero_code_lengths)

        self._codes_by_length = defaultdict(dict)  # mapping: {length: {code: symbol}}
        for symbol, length in zip(alphabet, code_lengths):
            if (length != 0):
                code = next_code[length]
                self._codes_by_length[length][code] = symbol
                next_code[length] += 1

    def contains(self, code: int, length: int) -> bool:
        return code in self._codes_by_length[length]

    def get(self, code: int, length: int) -> int:
        return self._codes_by_length[length][code]

    def __repr__(self) -> str:
        return str({
            format(code, 'b').zfill(code_len): val
            for code_len, codes in sorted(self._codes_by_length.items())
            for code, val in codes.items()
        })

    def pairs(self):
        return sorted([
            (v, l)
            for l, d in self._codes_by_length.items()
            for _, v in d.items()
        ])


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
        for read_length in range(tree.min_length, tree.max_length + 1):
            code = self._get(read_length, self.index)
            code = int(format(code, 'b').zfill(read_length)[::-1], 2)
            if tree.contains(code, read_length):
                self.index += read_length
                return tree.get(code, read_length)

        raise KeyError("no matching huffman code could be found")

    def read_code_lengths(self, num_codes: int, tree: HuffmanTree):
        lengths = []
        while len(lengths) < num_codes:
            code = self.read_huffman_code(tree)

            match code:
                case 16:
                    prev_code = lengths[-1]
                    rep_len = self.read(2) + 3
                    lengths.extend([prev_code] * rep_len)
                    if INFGEN:
                        print("repeat", rep_len)
                case 17:
                    rep_len = self.read(3) + 3
                    lengths.extend([0] * rep_len)
                    if INFGEN:
                        print("zeros", rep_len)
                case 18:
                    rep_len = self.read(7) + 11
                    lengths.extend([0] * rep_len)
                    if INFGEN:
                        print("zeros", rep_len)
                case _:
                    lengths.append(code)
                    if INFGEN:
                        print("lens", code)
        return lengths

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

        # NOTE: Any further reads will be byte-aligned (bit offset == 0)

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
            match key:
                case offset, length:
                    return self._get(length, self.index + offset)
                case offset, :
                    return self[self.index + offset:]

            raise ValueError(
                f"{type(self).__name__} tuple indices must contain 1-2 items"
            )
        if isinstance(key, slice):
            start, stop, stride = key.indices(self.len)
            start = self.len + start if start < 0 else start
            stop = self.len + stop if stop < 0 else stop
            length = stop - start
            data = self._get(length, start)
            if stride != 1:
                data = int(format(data, 'b').zfill(length)[::stride], base=2)
            return data

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
