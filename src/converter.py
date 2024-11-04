import os
import ffmpeg
import pyaudio
import wave
import threading
import time
from subprocess import run as system
from src.utils import changefontsize
from src.utils.others import yt_download
from keyboard import add_hotkey, wait
import numpy as np
from rich.progress import Progress
from multiprocessing import Pool, Queue
from rich.progress import Progress, TextColumn, BarColumn, TimeRemainingColumn, SpinnerColumn
import io, tempfile

# from src.utils.file import tools

class TerminalPlayer:
    def __init__(self) -> None:
        self.BRIGHTNESS_LEVELS_LOW = "  .-+⠶⣶#Bg0MNWQ%&@⣿███████████████"
        self.BRIGHTNESS_LEVELS_HIGH = "          .-':_,^=;><+!rc*/z?sLTv)J7(|F{C}fI31tlu[neoZ5Yxya]2ESwqkP6h9d4VpOGbUAKXHm8RD#$Bg0MNWQ%&@██████████████"
        self.playing = False
        self.stop = False

    # def renderVideo(self, frames_ascii, dir_name, audio_bytes, frame_rate):
    #     with open(dir_name, 'wb') as file:
    #         tools.write_video(file, frames_ascii, frame_rate, self.crtBrightness - 1, audio_bytes)

    # def loadVideo(self, path):
    #     with open(path, 'rb') as file:
    #         return tools.read_video(file)

    def convert_to_ascii(self, image, brightnessLevels):
        rgb_pixels = np.array(image, dtype=np.int32)

        brightness = np.mean(rgb_pixels, axis=2) / 255.0
        ascii_indices = (brightness * (len(brightnessLevels) - 1)).astype(int)

        ascii_image = []

        height, width, _ = rgb_pixels.shape
        last_rgb = np.zeros((3,), dtype=np.int32)
        last_rgb_used = np.zeros((height, width), dtype=bool) 
        ascii_chars = np.array([brightnessLevels[idx] for idx in ascii_indices.flatten()]).reshape(height, width)

        ansi_colors = np.full((height, width), "\033[0m", dtype=object)
        color_changes = np.zeros((height, width), dtype=bool) 

        for y in range(height):
            for x in range(width):
                current_rgb = rgb_pixels[y, x]
                distance = 0
                for i in range(3):
                    distance += abs(current_rgb[i] - last_rgb[i]) # more detailed difference

                if distance > 100 or (y == 0 and x == 0):
                    ansi_colors[y, x] = f"\033[38;2;{current_rgb[0]};{current_rgb[1]};{current_rgb[2]}m"
                    color_changes[y, x] = True
                    last_rgb = current_rgb  # Update last RGB value
                else:
                    ansi_colors[y, x] = ansi_colors[y, x-1]  # Use the previous color if no change

        # Construct ASCII rows
        for y in range(height):
            ascii_row = []
            for x in range(width):
                if color_changes[y, x]:
                    ascii_row.append(ansi_colors[y, x] + ascii_chars[y, x])  # Use ANSI color
                else:
                    ascii_row.append(ascii_chars[y, x])  # Use the same character without color change
            ascii_image.append("".join(ascii_row))

        return ascii_image



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
            .filter('format', 'rgb24')  # Mude para 'rgb24' para saída em cores
            .output('pipe:', format='rawvideo', pix_fmt='rgb24', loglevel="quiet")  # Use 'rgb24' aqui também
            .run_async(pipe_stdout=True, pipe_stderr=True)
        )

        frame_size = target_frame_width * target_frame_height * 3  # Mude para 3 para RGB
        while True:
            in_bytes = process.stdout.read(frame_size)
            if not in_bytes:
                break
            frame = np.frombuffer(in_bytes, np.uint8).reshape((target_frame_height, target_frame_width, 3))  # Mude para incluir 3 canais

            frames.append(frame)  # Armazene o frame como um array numpy

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

    def start_hotkeyts(self):
        add_hotkey('q', self.escape)

        wait()

    # deactivated for now
    # def load_video(self):
    #     while True:
    #         target = input("\nEnter the path of the .ascv file: ")
    #         if not os.path.exists(target):
    #             print(f"Couldn't find the path of the file: {target}.")
    #             continue
    #         break

    #     print("Processing data...")
    #     frames_ascii, frame_rate, brightness, audio_bytes = self.loadVideo(target)
    #     print("Video loaded successfully.")

    #     return frames_ascii, frame_rate, target, audio_bytes
    
    def create_video(self):
        print("\nThe size of the window will change the video quality!")
        while True:
            try:
                choose = int(input("Choose the brightness quality (type the number):\n[1] Low/Medium (recommended)\n[2] High\nYour input: "))
                break
            except ValueError:
                print(f"The input has to be a number!")

        self.crtBrightness = choose

        chooseyt = input("Do you want to use an Youtube URL? [Y/N] ")

        if chooseyt.strip().lower() in ['y', 'yes', 'sim', 's']:
            while True:
                yt_url = input("Enter the video's URL: ")

                args = yt_download(yt_url)
                if not yt_url or not args:
                    print(f"The URL '{yt_url}' doesn't exist!")
                    continue
                print(f"Video downloaded successfully.")
                with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{args[2]}') as temp_file:
                    temp_file.write(args[3])
                    input_filename = temp_file.name
                break

        else:
            while True:
                input_filename = input("\nEnter the video's path (this requires the file extension): ")
                if not os.path.exists(input_filename):
                    print(f"The path '{input_filename}' doesn't exist!")
                    continue
                break
        
        while True:
            try:
                change_res = input("Enter the desired size of font (smaller fonts will increase resolution, but can make the process slower, recommended: 5-10, leave blank to skip): ").strip()
                if not change_res:
                    change_res = 10
                    break
                
                change_res = int(change_res)
                if change_res and int(change_res) > 1:
                    print(f"Capturing resolution...")
                    changefontsize.change_fz(change_res)
                    time.sleep(1)
                    terminal = os.get_terminal_size()
                    changefontsize.change_fz(10) # Return to normal size for better reading
                    break
                elif change_res > 20 or change_res < 1:
                    print("The font size has to be between 1 and 20!")
                    continue
            except ValueError:
                print(f"Please insert a valid value!")
                continue

        probe = ffmpeg.probe(input_filename)
        vid_info = next(stream for stream in probe['streams'] if stream['codec_type'] == 'video')
        vidW = int(vid_info['width'])
        vidH = int(vid_info['height'])

        target_frame_width = terminal.columns - 1
        target_frame_height = terminal.lines - 2

        ratio = vidW / vidH
        target_frame_width = int(round(target_frame_height * ratio * 2))

        print(f"\nVideo resolution: {vidW} X {vidH}")
        print(f"Terminal resolution: {target_frame_width} X {target_frame_height}")

        print(f"\nExtracting frames and audio...")

        frame_bytes, audio_bytes = self.extract_frames_and_audio(input_filename, target_frame_width, target_frame_height)

        print("Converting frames to ASCII...")

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

            with Pool(processes=8) as pool:
                for frame_ascii in pool.imap(self.process_frame, frame_bytes):
                    frames_ascii.append(frame_ascii)
                    queue.put(1) 

            progress_thread.join()

        frame_rate_str = vid_info['r_frame_rate']
        if '/' in frame_rate_str:
            num, denom = map(int, frame_rate_str.split('/'))
            frame_rate = round(num / denom)
        else:
            frame_rate = int(frame_rate_str)

        renderArgs = (frames_ascii, audio_bytes, frame_rate)

        return frames_ascii, frame_rate, audio_bytes, change_res, renderArgs
    
    def process_frame(self, byte_content):
        return "\n".join(self.convert_to_ascii(byte_content, self.BRIGHTNESS_LEVELS_HIGH if self.crtBrightness == 2 else self.BRIGHTNESS_LEVELS_LOW))

    def main(self):
        # deactivated for now
        # print("The imported frames will follow the resolution which the frames were processed!")
        # load_choice = input("Do you want to import frames? (Y/N): ")
        
        # if load_choice.lower() in ['y', 'yes', 'sim', 's']:
        #     frames_ascii, frame_rate, target, audio_bytes = self.load_video()
        # else:
        frames_ascii, frame_rate, audio_bytes, resolution, renderArgs  = self.create_video()

        input("\nPress enter to play (while playing, press Q to exit)... ")

        hk = threading.Thread(target=self.start_hotkeyts)
        hk.start()
        
        audio_thread = threading.Thread(target=self.play_audio, args=(audio_bytes,))
        audio_thread.start()

        while self.playing is not True:
            continue

        system("cls", shell=True)

        frame_duration = 1 / frame_rate
        start_time = time.time()

        from sys import stdout

        stdout.write('\033[?25l') # hides cursor

        try: # avoids error if load_video
            if resolution:
                changefontsize.change_fz(resolution)
        except:
            pass

        for i, frame in enumerate(frames_ascii):
            elapsed_time = time.time() - start_time
            expected_frame = int(elapsed_time / frame_duration)

            if i >= expected_frame:
                stdout.write('\033[H' + frame)
                stdout.flush()

            time_to_sleep = frame_duration - (time.time() - (start_time + i * frame_duration))
            time.sleep(max(0, time_to_sleep))
            if self.stop:
                break

        audio_thread.join()
        changefontsize.change_fz(10)
        print('\033[?25h') # show cursor
        print('\033[2J\033[H', end='', flush=True) # clears buffer

        # removed for now
        # try:
        #     from time import time as timestamp
        #     save = input("Do you want to save the video? (this might take some time) (Y/N): ")
        #     if save.strip().lower() in ['y', 'yes', 's', 'sim']:
        #         flag = timestamp()
        #         frames_ascii, audio_bytes, frame_rate = renderArgs
        #         while True:
        #             name = input("Enter a path/name to export the file: ")
        #             if not name:
        #                 print("Please insert a valid name!")
        #             elif name[5:] != '.ascv':
        #                 name += '.ascv'
        #             if os.path.exists(name):
        #                 print("The file already exists!")
        #                 continue
        #             break
        #         print(f"Saving video...")
        #         self.renderVideo(frames_ascii, name, audio_bytes, frame_rate)
        #         count = round(timestamp() - flag, 2)
        #         print(f"Video saved successfully in {count} seconds!")
        # except Exception as e:
        #     print(e)

        input("\033[0mPress enter to exit...")
        exit(0)
        
if __name__ == "__main__":
    changefontsize.change_fz(10) # default font size
    try:
        player = TerminalPlayer()
        player.main()
    except KeyboardInterrupt:
        exit(0)