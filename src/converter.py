import os
import ffmpeg
from PIL import Image
import pyaudio
import wave
import threading
import time
from rich.console import Console
from rich.panel import Panel
import json
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from shutil import rmtree, copyfileobj
from gzip import open as g_open
from subprocess import run as system
import src.utils.changefontsize
from keyboard import add_hotkey, wait
import numpy as np

class muteLogger:
    def error(msg):
        pass
    def warning(msg):
        pass
    def debug(msg):
        pass

def delete_folder(dir):
    try:
        if os.path.exists(dir):
            os.rmdir(dir)
    except:
        pass

def compact_file(file_name):
    with open(file_name, 'rb') as f_in:
        with g_open(file_name[:-4] + '.gz', 'wb') as f_out:
            copyfileobj(f_in, f_out)

def unzip(file_name):
    with g_open(f"{file_name}.gz", 'rb') as f_in:
        with open(f"{file_name}.txt", 'wb') as f_out:
            copyfileobj(f_in, f_out)

def yt_download(link, dir, custom_name=None):
    outtmpl = f'{dir}/{"%(title)s" if not custom_name else custom_name}.%(ext)s'
    
    ydl_opts = {
        'outtmpl': outtmpl, 
        'logger': muteLogger
    }
    
    with YoutubeDL(ydl_opts) as ydl:
        try:
            console.print(f"[bold yellow][INFO][/] Downloading video...")
            info = ydl.extract_info(link, download=True)
            return True, info['title'], info['ext']
        except DownloadError as e:
            if "is not a valid URL" in str(e):
                return False
        except Exception as e:
            raise Exception(f'An unexpected error occurred: {e}')

console = Console()

class TerminalPlayer:
    def __init__(self, path) -> None:
        self.BRIGHTNESS_LEVELS_LOW = " .-+*wGHM#&%@"
        self.BRIGHTNESS_LEVELS_HIGH = "          .-':_,^=;><+!rc*/z?sLTv)J7(|F{C}fI31tlu[neoZ5Yxya]2ESwqkP6h9d4VpOGbUAKXHm8RD#$Bg0MNWQ%&@██████████████"
        self.playing = False
        self.path = path
        self.stop = False

    def ensure_tmp_directory(self, dir_name):
        """Certifica-se de que o diretório temporário existe."""
        tmp_path = os.path.join(self.path, "tmp", dir_name)
        os.makedirs(tmp_path, exist_ok=True)
        return tmp_path

    def save_configs(self, config: dict, dir_name):
        tmp_path = self.ensure_tmp_directory(dir_name)
        while True:
            try:
                with open(os.path.join(tmp_path, "config.json"), 'w') as f:
                    json.dump(config, f, indent=4)
                break
            except Exception as e:
                raise Exception(f"Unexpected error: {e}")

    def load_configs(self, dir_name):
        tmp_path = self.ensure_tmp_directory(dir_name)
        while True:
            try:
                with open(os.path.join(tmp_path, "config.json"), 'r') as f:
                    return json.load(f)
                break
            except FileNotFoundError:
                raise FileNotFoundError("Config file not found.")
            except Exception as e:
                raise Exception(f"Unexpected error: {e}")

    def save_frames_to_txt(self, frames_ascii, dir_name):
        tmp_path = self.ensure_tmp_directory(dir_name)
        while True:
            try:
                with open(os.path.join(tmp_path, "frames_ascii.txt"), "w", encoding="utf-8") as f:
                    for frame in frames_ascii:
                        f.write(frame + "\n\n")
                break
            except Exception as e:
                raise Exception(f"Unexpected error: {e}")

    def load_frames_from_txt(self, dir_name):
        tmp_path = self.ensure_tmp_directory(dir_name)
        while True:
            try:
                frames_ascii = []
                with open(os.path.join(tmp_path, "frames_ascii.txt"), "r", encoding="utf-8") as f:
                    content = f.read().strip().split("\n\n")
                    frames_ascii = [frame for frame in content if frame]
                return frames_ascii
            except FileNotFoundError:
                raise FileNotFoundError(f"Frames file not found. {dir_name}")
            except Exception as e:
                raise Exception(f"Unexpected error: {e}")

    def move_cursor_to_top(self):
        print('\033[H', end='')

    def convert_to_ascii(self, image, brightnessLevels):
        grayscale_image = image.convert("L")

        pixels = np.array(grayscale_image)
        normalized_pixels = pixels / 255.0

        ascii_indices = (normalized_pixels * (len(brightnessLevels) - 1)).astype(int)

        ascii_image = np.array([[brightnessLevels[idx] for idx in row] for row in ascii_indices])

        return "\n".join("".join(row) for row in ascii_image)

    def extract_frames_and_audio(self, input_filename, target_frame_width, target_frame_height, dir_name):
        tmp_path = self.ensure_tmp_directory(dir_name)
        os.makedirs(os.path.join(tmp_path, "frames"), exist_ok=True)
        (
            ffmpeg
            .input(input_filename)
            .filter('scale', target_frame_width, target_frame_height)
            .filter('format', 'gray')
            .output(os.path.join(tmp_path, "frames", '%d.bmp'))
            .run(overwrite_output=True)
        )
        
        ffmpeg.input(input_filename).output(os.path.join(tmp_path, "audio.wav")).run(overwrite_output=True)

    def play_audio(self, dir_name):
        tmp_path = self.ensure_tmp_directory(dir_name)
        wf = wave.open(os.path.join(tmp_path, "audio.wav"), 'rb')
        p = pyaudio.PyAudio()
        stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                        channels=wf.getnchannels(),
                        rate=wf.getframerate(),
                        output=True)

        data = wf.readframes(1024)
        self.playing = True
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
        os.makedirs(os.path.join(self.path, "tmp"), exist_ok=True)
        avaliable = os.listdir(os.path.join(self.path, "tmp"))
        avlist = "[bold yellow]Avaliable projects:[/]\n"

        for index, item in enumerate(avaliable):
            if not os.path.isdir(os.path.join(self.path, "tmp", item)):
                avaliable.pop(index)

        if avaliable:
            for dir in avaliable:
                avlist += f"\n[bold white]- {dir}"
        else:
            avlist += f"\n[bold white]- No projects avaliable."

        console.print(Panel(avlist))

        while True:
            dir_name = console.input("\n[yellow][INPUT][/] [bold white]Enter the name used to save the project: ")
            target = os.path.join(self.path, "tmp", dir_name, "frames_ascii")
            if not os.path.exists(os.path.join(self.path, "tmp", dir_name)):
                console.print(f"[bold red][ERROR][/] [bold white]This name is not avaliable in the tmp directory!")
                continue
            break
        unzip(target)
        console.print("[bold yellow][INFO][/] Processing data...")
        frames_ascii = self.load_frames_from_txt(dir_name)
        console.print("[bold yellow][INFO][/] Loading configs...")
        vid_info = self.load_configs(dir_name)['metadata']
        console.print("[bold green][SUCCESS][/] Video loaded successfully.")

        return frames_ascii, vid_info, dir_name
    
    def create_video(self):
        console.print("\n[bold yellow][INFO][/] [bold white]The size of the window will change the video quality!")
        while True:
            try:
                choose = int(console.input("[bold green][OPTIONS][/] [bold white]Choose the brightness quality (type the number):\n[green][1][/] Low/Medium (recommended)\n[green][2][/] High\nYour input: "))
                break
            except ValueError:
                console.print(f"[bold red][ERROR][/] The input has to be a number!")

        brightnessLevels = self.BRIGHTNESS_LEVELS_LOW if choose == 1 else self.BRIGHTNESS_LEVELS_HIGH

        while True:
            dir_name = console.input("[bold yellow][INPUT][bold white] Enter a name to the exported files directory: ")
            if dir_name:
                break
            console.print("[bold red][ERROR][/] [bold white]Please insert a valid name![/]")

        chooseyt = console.input("[bold green][OPTION][/] Do you want to use an Youtube URL? [Y/N] ")

        if chooseyt in ['y', 'yes', 'sim', 's']:
            while True:
                yt_url = console.input("[bold red][YOUTUBE][/] Enter the video's URL: ")
                target = self.path + f"\\tmp\\{dir_name}"

                os.makedirs(target)
                response, info, ext = yt_download(yt_url, target, dir_name)
                if not yt_url and not response:
                    console.print(f"[bold red][ERROR][/] The URL '{yt_url}' doesn't exist!")
                    continue
                console.print(f"[bold green][SUCCESS][/] Video downloaded successfully.")
                input_filename = target + f"\\{dir_name}.{ext}"
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
                    break
                
                change_res = int(change_res)
                if change_res and int(change_res) > 1:
                    changefontsize.change_fz(change_res)
                    console.print(f"[bold green][SUCCESS][/] [bold white]Font size changed to {change_res} successfully.")
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
        self.save_configs({'metadata': vid_info}, dir_name)
        vidW = int(vid_info['width'])
        vidH = int(vid_info['height'])

        target_frame_width = os.get_terminal_size().columns - 1
        target_frame_height = os.get_terminal_size().lines - 2

        ratio = vidW / vidH
        target_frame_width = int(round(target_frame_height * ratio * 2))

        console.print(f"[bold yellow][INFO][/] [bold white]Video resolution: {vidW} X {vidH}")
        console.print(f"[bold yellow][INFO][/] [bold white]Terminal resolution: {target_frame_width} X {target_frame_height}")

        self.extract_frames_and_audio(input_filename, target_frame_width, target_frame_height, dir_name)

        frame_files = sorted(os.listdir(os.path.join(self.path, "tmp", dir_name, "frames")), key=lambda f: int(f.split('.')[0]))
        frames_ascii = []

        console.print("[bold yellow][INFO][/] [bold white]Converting frames to ASCII...")
        for frame_file in frame_files:
            frame_path = os.path.join(self.path, "tmp", dir_name, "frames", frame_file)
            with Image.open(frame_path) as image:
                ascii_frame = self.convert_to_ascii(image, brightnessLevels)
                frames_ascii.append(ascii_frame)

        self.save_frames_to_txt(frames_ascii, dir_name)

        console.print("\n[bold yellow][INFO][/] Compacting frames...")
        compact_file(os.path.join(self.path, "tmp", dir_name, "frames_ascii.txt"))

        try: 
            os.remove(os.path.join(self.path, 'tmp', dir_name, "frames_ascii.txt"))
        except FileNotFoundError: 
            pass

        return frames_ascii, vid_info, dir_name

    def main(self):
        console.print("[bold yellow][INFO][/] The imported frames will follow the resolution which the frames were processed!")
        load_choice = console.input("[bold green][OPTIONS][/] [bold white]Do you want to import frames? (Y/N): ")
        
        if load_choice.lower() in ['y', 'yes', 'sim', 's']:
            frames_ascii, vid_info, dir_name = self.load_video()
        else:
            frames_ascii, vid_info, dir_name  = self.create_video()

        console.input("\n[bold white]Press enter to play (while playing, press Q to exit)... ")

        hk = threading.Thread(target=self.start_hotkeyts)
        hk.start()
        
        audio_thread = threading.Thread(target=self.play_audio, args=(dir_name,))
        audio_thread.start()

        while self.playing is not True:
            continue

        system("cls", shell=True)

        frame_rate_str = vid_info['r_frame_rate']
        if '/' in frame_rate_str:
            num, denom = map(int, frame_rate_str.split('/'))
            frame_rate = num / denom
        else:
            frame_rate = float(frame_rate_str)

        frame_duration = 1 / frame_rate
        start_time = time.time()

        for i, frame in enumerate(frames_ascii):
            elapsed_time = time.time() - start_time
            expected_frame = int(elapsed_time / frame_duration)

            if i >= expected_frame:
                self.move_cursor_to_top()
                print(frame)

            time_to_sleep = frame_duration - (time.time() - (start_time + i * frame_duration))
            time.sleep(max(0, time_to_sleep))
            if self.stop:
                break

        audio_thread.join()
        console.print("[bold yellow][INFO][/] Deleting temporary frames...")
        time.sleep(1)
        delete_folder(os.path.join(self.path, "tmp", dir_name, "frames"))
        try: 
            os.remove(os.path.join(self.path, 'tmp', dir_name, "frames_ascii.txt"))
        except FileNotFoundError: 
            pass
        changefontsize.change_fz(10)

if __name__ == "__main__":
    player = TerminalPlayer(path=os.getcwd())
    player.main()