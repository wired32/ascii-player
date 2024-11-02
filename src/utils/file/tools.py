import struct
import mmap
import zlib
from multiprocessing import Pool, cpu_count
from io import BufferedWriter

# define brightness levels and encoding maps
BRIGHTNESS_LEVELS_LOW = " .-+*wGHM#&%@\n"
BRIGHTNESS_LEVELS_HIGH = "          .-':_,^=;><+!rc*/z?sLTv)J7(|F{C}fI31tlu[neoZ5Yxya]2ESwqkP6h9d4VpOGbUAKXHm8RD#$Bg0MNWQ%&@██████████████\n"

LOW_ENCODING = {char: idx for idx, char in enumerate(BRIGHTNESS_LEVELS_LOW)}
HIGH_ENCODING = {char: idx for idx, char in enumerate(BRIGHTNESS_LEVELS_HIGH)}

# packing functions for low and high brightness frames
def pack_low(frame):
    packed_bytes = bytearray()
    bit_buffer = 0
    bit_count = 0

    for char in frame:
        value = LOW_ENCODING.get(char)
        if value is None:
            continue

        bit_buffer = (bit_buffer << 4) | value
        bit_count += 4

        while bit_count >= 8:
            bit_count -= 8
            packed_bytes.append((bit_buffer >> bit_count) & 0xFF)

    if bit_count > 0:
        packed_bytes.append((bit_buffer << (8 - bit_count)) & 0xFF)

    return packed_bytes

def pack_high(frame):
    packed_bytes = bytearray()
    bit_buffer = 0
    bit_count = 0

    for char in frame:
        value = HIGH_ENCODING.get(char)
        if value is None:
            continue

        bit_buffer = (bit_buffer << 7) | value
        bit_count += 7

        while bit_count >= 8:
            bit_count -= 8
            packed_bytes.append((bit_buffer >> bit_count) & 0xFF)

    if bit_count > 0:
        packed_bytes.append((bit_buffer << (8 - bit_count)) & 0xFF)

    return packed_bytes

# unpacking functions for low and high brightness frames
def unpack_low(packed_bytes):
    bit_buffer = 0
    bit_count = 0
    result = []

    for byte in packed_bytes:
        bit_buffer = (bit_buffer << 8) | byte 
        bit_count += 8

        while bit_count >= 4:
            bit_count -= 4
            value = (bit_buffer >> bit_count) & 0x0F
            if value < len(BRIGHTNESS_LEVELS_LOW): 
                result.append(BRIGHTNESS_LEVELS_LOW[value]) 

    return ''.join(result)

def unpack_high(packed_bytes):
    bit_buffer = 0
    bit_count = 0
    result = []

    for byte in packed_bytes:
        bit_buffer = (bit_buffer << 8) | byte
        bit_count += 8

        while bit_count >= 7: 
            bit_count -= 7
            value = (bit_buffer >> bit_count) & 0x7F
            if value < len(BRIGHTNESS_LEVELS_HIGH): 
                result.append(BRIGHTNESS_LEVELS_HIGH[value]) 

    return ''.join(result)

# Parallel frame packing using multiprocessing
def pack_frames_parallel(frames, brightness):
    pack_func = pack_high if brightness == 1.0 else pack_low
    with Pool(cpu_count()) as pool:
        packed_frames = pool.map(pack_func, frames)
    return packed_frames

# write video to file with optimized I/O and compression
def write_video(file, frames, frame_rate, brightness, audio_bytes):
    # use a BufferedWriter for efficient file I/O
    buffered_file = BufferedWriter(file)

    # write header
    buffered_file.write(b'VIDE')
    buffered_file.write(struct.pack('I', frame_rate))
    buffered_file.write(struct.pack('f', brightness))

    # pack frames with parallel processing
    packed_frames = pack_frames_parallel(frames, brightness)

    # structure packed frames with length headers
    frame_data = bytearray()
    for packed_frame in packed_frames:
        frame_data.extend(struct.pack('I', len(packed_frame)))
        frame_data.extend(packed_frame)

    # compress frame data with a lower compression level for faster writes
    compressed_frames = zlib.compress(frame_data, level=1)
    buffered_file.write(struct.pack('I', len(compressed_frames)))
    buffered_file.write(compressed_frames)

    # compress audio data
    compressed_audio = zlib.compress(audio_bytes, level=1)
    buffered_file.write(b'AUDI')
    buffered_file.write(struct.pack('I', len(compressed_audio)))
    buffered_file.write(compressed_audio)

    # ensure all data is written to the file
    buffered_file.flush()

# read video from file with mmap for efficient access
def read_video(file):
    with mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as mmapped_file:
        if mmapped_file.read(4) != b'VIDE':
            raise ValueError("Invalid file format")

        frame_rate = struct.unpack('I', mmapped_file.read(4))[0]
        brightness = struct.unpack('f', mmapped_file.read(4))[0]
        unpack_func = unpack_high if brightness == 1.0 else unpack_low

        # read and decompress frame data
        frame_data_length = struct.unpack('I', mmapped_file.read(4))[0]
        compressed_frames = mmapped_file.read(frame_data_length)
        decompressed_frames = zlib.decompress(compressed_frames)

        frames = []
        offset = 0
        while offset < len(decompressed_frames):
            frame_length = struct.unpack_from('I', decompressed_frames, offset)[0]
            offset += 4
            packed_frame = decompressed_frames[offset:offset + frame_length]
            frames.append(unpack_func(packed_frame))
            offset += frame_length

        # read and decompress audio data
        if mmapped_file.read(4) != b'AUDI':
            raise ValueError("Missing audio data")

        audio_length = struct.unpack('I', mmapped_file.read(4))[0]
        compressed_audio = mmapped_file.read(audio_length)
        audio_bytes = zlib.decompress(compressed_audio)

    return frames, frame_rate, brightness, audio_bytes
