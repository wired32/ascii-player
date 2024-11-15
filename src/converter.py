import ffmpeg
import pyaudio
import wave
import threading
import time
from src.utils.others import yt_download
from keyboard import add_hotkey, wait
import numpy as np
from rich.progress import Progress
from multiprocessing import Pool, Queue
from rich.progress import Progress, TextColumn, BarColumn, TimeRemainingColumn, SpinnerColumn
import io, tempfile
import os
from subprocess import run as system
from sys import stdout

class TerminalPlayer:
    def __init__(self) -> None:
        self.playing = False
        self.stop = False
        self.windows = os.name == 'nt'

    def extract_frames_and_audio(self, input_filename, target_frame_width, target_frame_height):
        audio_data = (
            ffmpeg
            .input(input_filename)
            .output('pipe:', format='wav', loglevel="quiet")
            .run(capture_stdout=True, capture_stderr=True)
        )[0] 

        frames = []

        process = (
            ffmpeg
            .input(input_filename)
            .filter('scale', target_frame_width, target_frame_height)
            .filter('format', 'rgb24')
            .output('pipe:', format='rawvideo', pix_fmt='rgb24', loglevel="quiet")
            .run_async(pipe_stdout=True, pipe_stderr=True)
        )

        frame_size = target_frame_width * target_frame_height * 3 
        while True:
            in_bytes = process.stdout.read(frame_size)
            if not in_bytes:
                break
            frame = np.frombuffer(in_bytes, np.uint8).reshape((target_frame_height, target_frame_width, 3)) 

            frames.append(frame)

        process.stdout.close()
        process.wait()

        return frames, audio_data

    def play_audio(self, content):
        p = pyaudio.PyAudio()
        
        wf = wave.Wave_read(io.BytesIO(content))
        
        stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                        channels=wf.getnchannels(),
                        rate=wf.getframerate(),
                        output=True)

        data = wf.readframes(1024)
        self.playing = True
        self.stop = False
        while len(data) > 0 and not self.stop:
            stream.write(data)
            data = wf.readframes(1024)

        stream.stop_stream()
        stream.close()
        p.terminate()
        self.playing = False


    def escape(self):
        self.stop = True

    def start_hotkeys(self):
        add_hotkey('q', self.escape)

        wait()

    def batch(self, content: list, size: int) -> list[list]:
        return [content[i:i + size] for i in range(0, len(content), size)]
    
    def create_video(self):
        chooseyt = input("Do you want to use an Youtube URL? [Y/N] ")

        if chooseyt.strip().lower() in ['y', 'yes', 'sim', 's']:
            while True:
                yt_url = input("Enter the video's URL: ")

                args = yt_download(yt_url)
                if not yt_url or not args:
                    stdout.write(f"The URL '{yt_url}' doesn't exist!")
                    continue
                stdout.write(f"Video \033[48;5;7m{args[1]}\033[0m downloaded successfully.")
                with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{args[2]}') as temp_file:
                    temp_file.write(args[3])
                    input_filename = temp_file.name
                break

        else:
            while True:
                input_filename = input("\nEnter the video's path (this requires the file extension): ")
                if not os.path.exists(input_filename):
                    stdout.write(f"The path '{input_filename}' doesn't exist!")
                    continue
                break

        while True:
            input("Terminal size will be captured automatically\nIMPORTANT: If you want a better quality, reduce the font size now (3-5px is the recommended) and press enter to capture (you can resize after)... ")

            terminal = os.get_terminal_size()

            target_frame_width = terminal.columns - 1
            target_frame_height = terminal.lines - 2

            stdout.write(f"\033[48;5;28mTerminal resolution captured:\033[0m {target_frame_width} X {target_frame_height}")
            if input("Do you want to retake the resolution? (leave blank to continue) [Y/N] ").strip().lower() not in ['y', 'yes', 'sim', 's']:
                break


        probe = ffmpeg.probe(input_filename)
        vid_info = next(stream for stream in probe['streams'] if stream['codec_type'] == 'video')
        vidW = int(vid_info['width'])
        vidH = int(vid_info['height'])

        ratio = vidW / vidH
        target_frame_width = int(round(target_frame_height * ratio * 2))

        stdout.write(f"\nVideo resolution: {vidW} X {vidH}")
        stdout.write(f"Terminal resolution: {target_frame_width} X {target_frame_height}")

        stdout.write(f"\nExtracting frames and audio...")

        frame_bytes, audio_bytes = self.extract_frames_and_audio(input_filename, target_frame_width, target_frame_height)

        frame_chars = target_frame_width * target_frame_height
        video_lenght = len(frame_bytes)

        stdout.write(f"Extracted {video_lenght} frames from video")
        stdout.write(f"Approximate characters per frame: {frame_chars}")
        stdout.write(f"Approximated conversion time: {round((frame_chars * video_lenght * 5) / 1000000000, 4)} seconds (Based on 5 nanoseconds per character)")

        processes = 7

        frame_bytes = self.batch(frame_bytes, round(len(frame_bytes) / (processes * 2))) # batches frames to reduce function calling, increase multiplication to increase batches

        stdout.write("Converting frames to ASCII...")
        time_snapshot = time.time()

        frames_ascii = []
        queue = Queue()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task("[yellow]Converting frames...", total=len(frame_bytes))

            def monitor_progress(queue):
                while not progress.finished:
                    queue.get()
                    progress.update(task, advance=1)

            progress_thread = threading.Thread(target=monitor_progress, args=(queue,))
            progress_thread.start()

            with Pool(processes=processes) as pool:
                for frame_batch in pool.imap(self.process_frame, frame_bytes):
                    frames_ascii += frame_batch
                    queue.put(1)

            progress_thread.join()

        stdout.write(f"Frame conversion completed in {round(time.time() - time_snapshot, 4)} seconds.")

        frame_rate_str = vid_info['r_frame_rate']
        if '/' in frame_rate_str:
            num, denom = map(int, frame_rate_str.split('/'))
            frame_rate = round(num / denom)
        else:
            frame_rate = int(frame_rate_str)

        return frames_ascii, frame_rate, audio_bytes
    
    def process_frame(self, byte_content):
        batch = []

        for image in byte_content:
            rgb_pixels = np.array(image, dtype=np.int32)

            ascii_image = []

            height, width, _ = rgb_pixels.shape
            last_rgb = np.zeros((3,), dtype=np.int32)

            ansi_colors = np.full((height, width), "\033[0m", dtype=object)
            color_changes = np.zeros((height, width), dtype=bool) 

            for y in range(height):
                for x in range(width):
                    current_rgb = rgb_pixels[y, x]
                    # perceptual weights based on human vision (green is perceived more strongly)
                    weights = [0.299, 0.587, 0.114]

                    distance = 0
                    for i in range(3):
                        diff = current_rgb[i] - last_rgb[i]
                        distance += weights[i] * diff * diff  # apply weights

                    if distance > 15 or (y == 0 and x == 0):
                        ansi_colors[y, x] = f"\033[48;2;{current_rgb[0]};{current_rgb[1]};{current_rgb[2]}m"
                        color_changes[y, x] = True
                        last_rgb = current_rgb
                    else:
                        ansi_colors[y, x] = ansi_colors[y, x-1]  # use the previous color if no change

            # create the ANSI sequence directly without printing
            for y in range(height):
                ascii_row = []
                for x in range(width):
                    if color_changes[y, x]:
                        ascii_row.append(ansi_colors[y, x] + " ")  # use ANSI color
                    else:
                        ascii_row.append(" ")  # use the same character without color change
                ascii_image.append("".join(ascii_row))

            # append the final ANSI sequences image for this frame
            batch.append("\n".join(ascii_image))

        # return the batch containing the ANSI sequences for the images
        return batch


    def main(self):
        frames_ascii, frame_rate, audio_bytes  = self.create_video()

        input("\nPress enter to play (while playing, press Q to exit)... ")
        
        try:
            from colorama import init # type: ignore
            init()
        except ImportError:
            stdout.write("WARNING: Couldn't import colorama, color support might not be avaliable on your terminal.\n")

        def play_frames():
            hk = threading.Thread(target=self.start_hotkeys)
            hk.start()
            
            audio_thread = threading.Thread(target=self.play_audio, args=(audio_bytes,))
            audio_thread.start()

            while self.playing is not True:
                continue

            system("cls", shell=True)

            frame_duration = 1 / frame_rate
            start_time = time.time()

            stdout.write('\033[?25l') # hides cursor

            previous_frame = None

            for i, frame in enumerate(frames_ascii):
                if self.stop:
                    break
                elapsed_time = time.time() - start_time
                expected_frame = int(elapsed_time / frame_duration)

                if i >= expected_frame:
                    if previous_frame:
                        if previous_frame == frame:
                            # avoid draws if identic frame
                            time_to_sleep = frame_duration - (time.time() - (start_time + i * frame_duration))
                            time.sleep(max(0, time_to_sleep))
                            continue

                        changes = ""
                            
                        # only redraw lines that have changed compared to the previous frame
                        for line_index, (prev_line, new_line) in enumerate(zip(previous_frame.splitlines(), frame.splitlines())):
                            if prev_line != new_line:
                                changes += f'\033[{line_index + 1};0H{new_line}'
                        
                        if changes:
                            stdout.write(changes)
                    else:
                        stdout.write('\033[H' + frame)
                    stdout.flush()
                    previous_frame = frame

                time_to_sleep = frame_duration - (time.time() - (start_time + i * frame_duration))
                time.sleep(max(0, time_to_sleep))
                
            audio_thread.join()
            stdout.write('\033[?25h') # show cursor

            try:
                if self.windows:
                    system("cls", shell=True)
                else:
                    system("clear", shell=True)
            except Exception as e:
                stdout.write("Couldn't clear terminal: " + str(e))
                stdout.write("Skipping...")

        play_frames()
        if input("Do you want to play again? (Y/N): ").strip().lower() in ['y', 'yes', 'sim', 's']: 
            play_frames()
        exit(0)
        
if __name__ == "__main__":
    try:
        player = TerminalPlayer()
        player.main()
    except KeyboardInterrupt:
        exit(0)