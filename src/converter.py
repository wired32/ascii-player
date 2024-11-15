# external libraries
import ffmpeg, pyaudio, numpy as np
from keyboard import add_hotkey, wait

from rich.progress import Progress
from rich.progress import Progress, TextColumn, BarColumn, TimeRemainingColumn, SpinnerColumn

# internal libraries
from multiprocessing import Pool, Queue
import threading

import io, tempfile, time
import wave
import os
from os import system
from sys import stdout

# modules
from src.utils.others import yt_download

class TerminalPlayer:
    def __init__(self) -> None:
        self.playing = False
        self.stop = False
        self.windows = os.name == 'nt'
        stdout.write('\033[?1049h') # initializes alternate buffer

    def extract_frames_and_audio(self, input_filename, target_frame_width, target_frame_height):
        """
        Extracts frames and audio from a video file.

        This function reads a video file, extracts its audio in WAV format, and
        converts its frames to a specified width and height in RGB format. The
        extracted frames are stored as numpy arrays and returned along with the
        audio data.

        Args:
            input_filename (str): The path to the video file.
            target_frame_width (int): The desired width of the output frames.
            target_frame_height (int): The desired height of the output frames.

        Returns:
            tuple: A tuple containing:
                - list: A list of numpy arrays representing the video frames.
                - bytes: The audio data in WAV format.
        """
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
        """
        Plays the given audio content using PyAudio.

        Args:
            content (bytes): The audio data in WAV format.

        """
        
        p = pyaudio.PyAudio()
        
        wf = wave.Wave_read(io.BytesIO(content))
        
        stream = p.open(
            format=p.get_format_from_width(wf.getsampwidth()),
            channels=wf.getnchannels(),
            rate=wf.getframerate(),
            output=True
        )

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


    def escape(self): # Function to be called by hotkey
        self.stop = True

    def start_hotkeys(self):
        # initialize and wait for hotkey in thread

        add_hotkey('q', self.escape)
        wait()

    def batch(self, content: list, size: int) -> list[list]:
        """
        Split a list into a list of lists of a given size.

        Args:
            content (list): The list to be split.
            size (int): The size of each sublist.

        Returns:
            list[list]: A list of lists of the given size.
        """
        return [content[i:i + size] for i in range(0, len(content), size)]
    
    def create_video(self):
        """
        Starts the video creation process.

        This function asks the user if they want to use a YouTube URL or a local video file. If the user chooses a YouTube URL, they will be asked to input the URL. If the user chooses a local video file, they will be asked to input the path to the file.

        The function then captures the terminal size and asks the user if they want to retake the resolution. If the user chooses to retake the resolution, the function will capture the terminal size again.

        The function then extracts the frames and audio from the video and converts the frames to ASCII art. The function then returns the ASCII art frames, the frame rate of the video, and the audio bytes of the video.

        Args:

            None

        Returns:

            list: A list of strings, where each string is an ASCII art frame of the video.
            int: The frame rate of the video.
            bytes: The audio bytes of the video.
        """
        chooseyt = input("Do you want to use an Youtube URL? [Y/N] ")

        if chooseyt.strip().lower() in ['y', 'yes', 'sim', 's']:
            while True:
                yt_url = input("Enter the video's URL: ")

                args = yt_download(yt_url)
                if not yt_url or not args:
                    stdout.write(f"The URL '{yt_url}' doesn't exist!")
                    continue
                stdout.write(f"Video {args[1]} downloaded successfully.")
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

            stdout.write(f"Terminal resolution captured: \033[48;5;28m{target_frame_width} X {target_frame_height}\033[0m\n")
            if input("Do you want to retake the resolution? (leave blank to continue) [Y/N] ").strip().lower() not in ['y', 'yes', 'sim', 's']:
                break


        probe = ffmpeg.probe(input_filename)
        vid_info = next(stream for stream in probe['streams'] if stream['codec_type'] == 'video')
        vidW = int(vid_info['width'])
        vidH = int(vid_info['height'])

        ratio = vidW / vidH
        target_frame_width = int(round(target_frame_height * ratio * 2))

        stdout.write(f"\nVideo resolution: {vidW} X {vidH}\n")

        stdout.write(f"\nExtracting frames and audio...")

        frame_bytes, audio_bytes = self.extract_frames_and_audio(input_filename, target_frame_width, target_frame_height)

        frame_chars = target_frame_width * target_frame_height
        video_lenght = len(frame_bytes)

        stdout.write(f" Extracted {video_lenght} frames from video\n")
        stdout.write(f"Approximate characters per frame: {frame_chars}\n")

        processes = 7

        frame_bytes = self.batch(frame_bytes, round(len(frame_bytes) / (processes * 2))) # batches frames to reduce function calling, increase multiplication to increase batches

        stdout.write("Converting frames to ASCII...\n")
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
        """
        Converts a batch of raw video frames into ANSI color-coded ASCII art frames.

        This function processes each image in the batch, computes color changes for
        each pixel, and generates a corresponding ANSI color-coded ASCII art frame.
        It uses vectorized operations to efficiently determine significant color
        changes and update ANSI color codes accordingly.

        Args:
            byte_content (list): A list of raw video frames, where each frame is
                                represented as a NumPy array of RGB pixel values.

        Returns:
            list: A list of strings, where each string is an ASCII art representation
                of a video frame with ANSI color codes.
        """
        batch = []

        for image in byte_content:
            rgb_pixels = np.array(image, dtype=np.int32)
            height, width, _ = rgb_pixels.shape
            last_rgb = np.zeros((3,), dtype=np.int32)
            
            # vectorized distance computation
            distance = np.sum(np.abs(rgb_pixels - last_rgb), axis=-1)
            
            # create a mask where the color changes are significant
            color_changes = distance > 1
            ansi_colors = np.full((height, width), "\033[0m", dtype=object)
            
            # update ANSI color codes where changes occur
            ansi_colors[color_changes] = np.array(
                [f"\033[48;2;{rgb[0]};{rgb[1]};{rgb[2]}m" for rgb in rgb_pixels[color_changes]],
                dtype=object
            )
            
            # create the ASCII image directly
            ascii_image = [
                "".join(
                    [f"{ansi_colors[y, x]} " if color_changes[y, x] else " " for x in range(width)]
                )
                for y in range(height)
            ]

            batch.append("\n".join(ascii_image))
        
        return batch

    def main(self):
        """
        Main entry point of the application. This method is responsible for playing
        the video in the terminal.

        It first creates the video frames and audio using the `create_video`
        method. Then, it starts a thread to capture hotkeys and another thread
        to play the audio. After that, it enters a loop where it displays the
        frames one by one using ANSI escape codes. The loop is stopped when the
        user presses 'Q' and the thread is joined to ensure the audio is finished
        playing. Finally, it clears the terminal and waits for user input to
        play again or exit.
        """
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
                stdout.write("\nSkipping...\n")

        play_frames()
        while True:
            if input("Do you want to play again? (Y/N): ").strip().lower() in ['y', 'yes', 'sim', 's']: 
                play_frames()
            if input("Are you sure? (Y/N): ").strip().lower() in ['y', 'yes', 'sim', 's']: 
                stdout.write('\033[?1049l') # return to main buffer
                exit(0)
        
if __name__ == "__main__":
    try:
        player = TerminalPlayer()
        player.main()
    except KeyboardInterrupt:
        stdout.write('\033[?1049l') # return to main buffer
        exit(0)