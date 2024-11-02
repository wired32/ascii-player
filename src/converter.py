import os
import ffmpeg
from PIL import Image
import pyaudio
import wave
import threading
import time
from rich.console import Console
from subprocess import run as system
from src.utils import changefontsize
from src.utils.others import yt_download
from keyboard import add_hotkey, wait
import numpy as np
from rich.progress import Progress
from multiprocessing import Pool, Queue
from rich.progress import Progress, TextColumn, BarColumn, TimeRemainingColumn, SpinnerColumn
import io, tempfile

from src.utils.file import tools

console = Console()

class TerminalPlayer:
    def __init__(self) -> None:
        self.BRIGHTNESS_LEVELS_LOW = " .-+*wGHM#&%@"
        self.BRIGHTNESS_LEVELS_HIGH = "          .-':_,^=;><+!rc*/z?sLTv)J7(|F{C}fI31tlu[neoZ5Yxya]2ESwqkP6h9d4VpOGbUAKXHm8RD#$Bg0MNWQ%&@██████████████"
        self.playing = False
        self.stop = False

    def renderVideo(self, frames_ascii, dir_name, audio_bytes, frame_rate):
        with open(dir_name, 'wb') as file:
            tools.write_video(file, frames_ascii, frame_rate, self.crtBrightness - 1, audio_bytes)

    def loadVideo(self, path):
        with open(path, 'rb') as file:
            return tools.read_video(file)

    def move_cursor_to_top(self):
        print('\033[H', end='')

    def convert_to_ascii(self, image, brightnessLevels):
        grayscale_image = image.convert("L")

        pixels = np.array(grayscale_image)
        normalized_pixels = pixels / 255.0

        ascii_indices = (normalized_pixels * (len(brightnessLevels) - 1)).astype(int)

        ascii_image = np.array([[brightnessLevels[idx] for idx in row] for row in ascii_indices])

        return "\n".join("".join(row) for row in ascii_image)

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
            .filter('format', 'gray')
            .output('pipe:', format='rawvideo', pix_fmt='gray', loglevel="quiet")
            .run_async(pipe_stdout=True, pipe_stderr=True)
        )

        frame_size = target_frame_width * target_frame_height
        while True:
            in_bytes = process.stdout.read(frame_size)
            if not in_bytes:
                break
            frame = np.frombuffer(in_bytes, np.uint8).reshape((target_frame_height, target_frame_width))

            pil_image = Image.fromarray(frame) 
            byte_io = io.BytesIO()
            pil_image.save(byte_io, format='PNG') 
            byte_content = byte_io.getvalue() 

            frames.append(byte_content) 

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

    def load_video(self):
        while True:
            target = console.input("\n[yellow][INPUT][/] [bold white]Enter the path of the .ascv file: ")
            if not os.path.exists(target):
                console.print(f"[bold red][ERROR][/] [bold white]Couldn't find the path of the file: {target}.")
                continue
            break

        console.print("[bold yellow][INFO][/] Processing data...")
        frames_ascii, frame_rate, brightness, audio_bytes = self.loadVideo(target)
        console.print("[bold green][SUCCESS][/] Video loaded successfully.")

        return frames_ascii, frame_rate, target, audio_bytes
    
    def create_video(self):
        console.print("\n[bold yellow][INFO][/] [bold white]The size of the window will change the video quality!")
        while True:
            try:
                choose = int(console.input("[bold green][OPTIONS][/] [bold white]Choose the brightness quality (type the number):\n[green][1][/] Low/Medium (recommended)\n[green][2][/] High\nYour input: "))
                break
            except ValueError:
                console.print(f"[bold red][ERROR][/] The input has to be a number!")

        brightnessLevels = self.BRIGHTNESS_LEVELS_LOW if choose == 1 else self.BRIGHTNESS_LEVELS_HIGH
        self.crtBrightness = choose

        chooseyt = console.input("[bold green][OPTION][/] Do you want to use an Youtube URL? [Y/N] ")

        if chooseyt.strip().lower() in ['y', 'yes', 'sim', 's']:
            while True:
                yt_url = console.input("[bold red][YOUTUBE][/] Enter the video's URL: ")

                response, info, ext, content = yt_download(yt_url)
                if not yt_url and not response:
                    console.print(f"[bold red][ERROR][/] The URL '{yt_url}' doesn't exist!")
                    continue
                console.print(f"[bold green][SUCCESS][/] Video downloaded successfully.")
                with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}') as temp_file:
                    temp_file.write(content)
                    input_filename = temp_file.name
                break

        else:
            while True:
                input_filename = console.input("\n[bold yellow][INPUT][bold white] Enter the video's path (this requires the file extension): ")
                if not os.path.exists(input_filename):
                    console.print(f"[bold red][ERROR][/] The path '{input_filename}' doesn't exist!")
                    continue
                break
        
        while True:
            try:
                change_res = console.input("[bold yellow][INPUT][/] Enter the desired size of font (smaller fonts will increase resolution, but can make the process slower, recommended: 5-10, leave blank to skip): ").strip()
                if not change_res:
                    change_res = 10
                    break
                
                change_res = int(change_res)
                if change_res and int(change_res) > 1:
                    console.print(f"[cyan][PROCESS][/] [bold white]Capturing resolution...")
                    changefontsize.change_fz(change_res)
                    time.sleep(1)
                    break
                elif change_res > 20 or change_res < 1:
                    console.print("[bold red][ERROR][/] [bold white]The font size has to be between 1 and 20!")
                    continue
            except ValueError:
                console.print(f"[bold red][ERROR][/] [bold white]Please insert a valid value!")
                continue

        probe = ffmpeg.probe(input_filename)
        vid_info = next(stream for stream in probe['streams'] if stream['codec_type'] == 'video')
        vidW = int(vid_info['width'])
        vidH = int(vid_info['height'])

        terminal = os.get_terminal_size()

        changefontsize.change_fz(10) # Return to normal size for better reading

        target_frame_width = terminal.columns - 1
        target_frame_height = terminal.lines - 2

        ratio = vidW / vidH
        target_frame_width = int(round(target_frame_height * ratio * 2))

        console.print(f"[bold yellow][INFO][/] [bold white]Video resolution: {vidW} X {vidH}")
        console.print(f"[bold yellow][INFO][/] [bold white]Terminal resolution: {target_frame_width} X {target_frame_height}")

        frame_bytes, audio_bytes = self.extract_frames_and_audio(input_filename, target_frame_width, target_frame_height)

        console.print("[bold yellow][INFO][/] [bold white]Converting frames to ASCII...")

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
        with Image.open(io.BytesIO(byte_content)) as image:
            return self.convert_to_ascii(image, self.BRIGHTNESS_LEVELS_HIGH if self.crtBrightness == 2 else self.BRIGHTNESS_LEVELS_LOW)

    def main(self):
        console.print("[bold yellow][INFO][/] The imported frames will follow the resolution which the frames were processed!")
        load_choice = console.input("[bold green][OPTIONS][/] [bold white]Do you want to import frames? (Y/N): ")
        
        if load_choice.lower() in ['y', 'yes', 'sim', 's']:
            frames_ascii, frame_rate, target, audio_bytes = self.load_video()
        else:
            frames_ascii, frame_rate, audio_bytes, resolution, renderArgs  = self.create_video()

        console.input("\n[bold white]Press enter to play (while playing, press Q to exit)... ")

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
        flush_rate = 5

        stdout.write('\033[?25l') # Hides cursor

        try: # avoids error if load_video
            if resolution:
                changefontsize.change_fz(resolution)
        except:
            pass

        for i, frame in enumerate(frames_ascii):
            elapsed_time = time.time() - start_time
            expected_frame = int(elapsed_time / frame_duration)

            if i >= expected_frame:
                self.move_cursor_to_top()
                stdout.write(frame)
                if i + 1 % flush_rate == 0:
                    stdout.flush()

            time_to_sleep = frame_duration - (time.time() - (start_time + i * frame_duration))
            time.sleep(max(0, time_to_sleep))
            if self.stop:
                break

        audio_thread.join()
        changefontsize.change_fz(10)
        print('\033[?25h') # Show cursor
        print('\033[2J\033[H', end='', flush=True) # Clears buffer

        try:
            from time import time as timestamp
            save = console.input("[bold white]Do you want to save the video? (this might take some time) (Y/N): ")
            if save.strip().lower() in ['y', 'yes', 's', 'sim']:
                flag = timestamp()
                frames_ascii, audio_bytes, frame_rate = renderArgs
                while True:
                    name = console.input("[bold yellow][INPUT][bold white] Enter a path/name to export the file: ")
                    if not name:
                        console.print("[bold red][ERROR][/] [bold white]Please insert a valid name![/]")
                    elif name[5:] != '.ascv':
                        name += '.ascv'
                    if os.path.exists(name):
                        console.print("[bold red][ERROR][/] [bold white]The file already exists![/]")
                        continue
                    break
                console.print(f"[bold yellow][INFO][/] Saving video...")
                self.renderVideo(frames_ascii, name, audio_bytes, frame_rate)
                count = round(timestamp() - flag, 2)
                console.print(f"[bold green][SUCCESS][/] Video saved successfully in {count} seconds!")
        except Exception as e:
            print(e)

        console.input("[bold white]Press enter to exit...")
        exit(0)
        
if __name__ == "__main__":
    changefontsize.change_fz(10) # default font size
    try:
        player = TerminalPlayer()
        player.main()
    except KeyboardInterrupt:
        exit(0)