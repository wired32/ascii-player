import requests
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from io import BytesIO

class muteLogger:
    def error(self, msg=None):
        pass
    def warning(self, msg=None):
        pass
    def debug(self, msg=None):
        pass

def yt_download(link, custom_name=None):
    # set up options for yt-dlp
    ydl_opts = {
        'format': 'best',  # choose the best quality available
        'noplaylist': True,  # do not download playlists
        'logger': muteLogger,
    }

    with YoutubeDL(ydl_opts) as ydl:
        try:
            print(f"Downloading video...")
            info = ydl.extract_info(link, download=False)  # set download=False to get info without downloading
            
            # get the download URL
            video_url = info['url']

            # create a BytesIO buffer to hold the video data
            video_buffer = BytesIO()

            response = requests.get(video_url, stream=True)
            response.raise_for_status()  # Raise an error for bad responses

            # write the response content to the BytesIO buffer
            for chunk in response.iter_content(chunk_size=8192):
                video_buffer.write(chunk)

            # seek to the beginning of the buffer for reading
            video_buffer.seek(0)

            return True, info['title'], info['ext'], video_buffer.getvalue()  # return the video bytes
        except DownloadError as e:
            if "is not a valid URL" in str(e):
                return False
        except Exception as e:
            raise Exception(f'An unexpected error occurred: {e}')