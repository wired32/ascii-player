import struct
import mmap
import zlib
from multiprocessing import Pool, cpu_count

# Adjusted brightness levels and encoding maps for both ASCII and color encoding preparation
BRIGHTNESS_LEVELS_LOW = " .-+*wGHM#&%@\n"
BRIGHTNESS_LEVELS_HIGH = "          .-':_,^=;><+!rc*/z?sLTv)J7(|F{C}fI31tlu[neoZ5Yxya]2ESwqkP6h9d4VpOGbUAKXHm8RD#$Bg0MNWQ%&@██████████████\n"

LOW_ENCODING = {char: idx for idx, char in enumerate(BRIGHTNESS_LEVELS_LOW)}
HIGH_ENCODING = {char: idx for idx, char in enumerate(BRIGHTNESS_LEVELS_HIGH)}

# Utility to pack frames in batches
def pack_frame_batch(frames, brightness_level):
    pack_func = pack_high if brightness_level == 1.0 else pack_low
    return [pack_func(frame) for frame in frames]

# Adjusted functions to handle color data if needed
def pack_low(frame):
    packed_bytes = bytearray()
    bit_buffer = 0
    bit_count = 0

    for char in frame:
        value = LOW_ENCODING.get(char, 0)
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
        value = HIGH_ENCODING.get(char, 0)
        bit_buffer = (bit_buffer << 7) | value
        bit_count += 7
        while bit_count >= 8:
            bit_count -= 8
            packed_bytes.append((bit_buffer >> bit_count) & 0xFF)

    if bit_count > 0:
        packed_bytes.append((bit_buffer << (8 - bit_count)) & 0xFF)
    return packed_bytes

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

# Optimized parallel frame packing in batches
def pack_frames_parallel(frames, brightness):
    batch_size = 50  # batch size can be adjusted based on testing
    with Pool(cpu_count()) as pool:
        packed_batches = pool.starmap(pack_frame_batch, [(frames[i:i + batch_size], brightness) for i in range(0, len(frames), batch_size)])
    return [frame for batch in packed_batches for frame in batch]

# Optimized write_video function with mmap for writing, less frequent flushes, and zlib compression at level 2 // changed it back to 1 for faster writing
def write_video(file, frames, frame_rate, brightness, audio_bytes):
    # Use memory-mapped file for write efficiency
    with mmap.mmap(file.fileno(), 0) as mmapped_file:
        mmapped_file.write(b'VIDE')
        mmapped_file.write(struct.pack('I', frame_rate))
        mmapped_file.write(struct.pack('f', brightness))

        # Parallel pack frames in batches
        packed_frames = pack_frames_parallel(frames, brightness)

        # Aggregate frame data with length headers
        frame_data = bytearray()
        for packed_frame in packed_frames:
            frame_data.extend(struct.pack('I', len(packed_frame)))
            frame_data.extend(packed_frame)

        # Compress frame data with optimized level for color storage
        compressed_frames = zlib.compress(frame_data, level=1)
        mmapped_file.write(struct.pack('I', len(compressed_frames)))
        mmapped_file.write(compressed_frames)

        # Compress audio data at optimized compression level
        compressed_audio = zlib.compress(audio_bytes, level=1)
        mmapped_file.write(b'AUDI')
        mmapped_file.write(struct.pack('I', len(compressed_audio)))
        mmapped_file.write(compressed_audio)

        mmapped_file.flush()  # Flush once after all writes

# Optimized read_video function
def read_video(file):
    with mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as mmapped_file:
        if mmapped_file.read(4) != b'VIDE':
            raise ValueError("Invalid file format")

        frame_rate = struct.unpack('I', mmapped_file.read(4))[0]
        brightness = struct.unpack('f', mmapped_file.read(4))[0]
        unpack_func = unpack_high if brightness == 1.0 else unpack_low

        # Read and decompress frame data
        frame_data_length = struct.unpack('I', mmapped_file.read(4))[0]
        compressed_frames = mmapped_file.read(frame_data_length)
        decompressed_frames = zlib.decompress(compressed_frames)

        # Decode frames from packed format
        frames = []
        offset = 0
        while offset < len(decompressed_frames):
            frame_length = struct.unpack_from('I', decompressed_frames, offset)[0]
            offset += 4
            packed_frame = decompressed_frames[offset:offset + frame_length]
            frames.append(unpack_func(packed_frame))
            offset += frame_length

        # Read and decompress audio data
        if mmapped_file.read(4) != b'AUDI':
            raise ValueError("Missing audio data")

        audio_length = struct.unpack('I', mmapped_file.read(4))[0]
        compressed_audio = mmapped_file.read(audio_length)
        audio_bytes = zlib.decompress(compressed_audio)

    return frames, frame_rate, brightness, audio_bytes