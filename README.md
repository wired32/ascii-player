# 📼 Terminal Video Player

**Overview**  
This project is a fun experiment aimed at breaking away from the limitations of ASCII art when it comes to displaying anything graphical in the terminal. It allows you to play videos in the terminal using ANSI codes and custom rendering techniques.

**Features**  
- Convert and play videos inside the terminal.
- Uses ANSI codes for video frame rendering.
- Supports audio extraction alongside video conversion.

## How to Run

### 1. Clone the Repository
```bash
git clone https://github.com/wired32/ascii-player.git
```

### 2. Install Dependencies
Navigate to the project folder and install the required packages:
```bash
cd ascii-player
pip install -r requirements.txt
```

### 3. Run the Converter Script
To convert a video, run the `converter.py` script inside the `src` folder:
```bash
python -m src.converter
```

## How It Works

1. **Input File**  
   Start by providing the path to a video file or by downloading a video from YouTube.

2. **Frame Processing**  
   The script processes the video by extracting frames and audio. It converts both the video frames and audio into byte format.

3. **Font Size Adjustment**  
   You will be prompted to reduce or maintain the terminal font size.  

   **Why is this important?**  
   The terminal is a grid-based system, so using a smaller font size increases the number of cells available for rendering, leading to better video quality. The terminal window size and line height also influence the resolution.

   **How small should my font be?**  
    The ideal font size depends on your preferences and system capabilities. Font sizes are typically measured in pixels (px). A smaller font size, like 3px, means that each video "pixel" will occupy 3px in the terminal window.

    However, keep in mind that terminals are not designed for graphical content, so using very small font sizes can cause performance issues or throttling, depending on your machine and rendering engine.

    For casual testing, I recommend using a font size of 3px or larger. If you have a better machine, you can experiment with 2px or even 1px for higher resolution, but be aware that this may impact performance.

4. **Frame Conversion**  
   After gathering all the necessary information, the script uses **6 processes** to convert all frames into ANSI sequences. Each process handles **2 batches** of frames. You can tweak these values in `src/converter.py` (line 150) for performance adjustments.

5. **Video Playback**  
   Once the frames are processed, the playback begins. The first frame is displayed, and subsequent frames are refreshed line-by-line, updating only the parts that have changed. This minimizes unnecessary redraws for smoother playback.

## Customization

- **Adjusting Process Numbers and Batch Sizes:**  
  You can customize the number of processes and the batch size in the `src/converter.py` file to optimize performance for your system. Modify the parameters at line 150 to suit your needs.

## Why ANSI Codes?

Using ANSI codes allows for efficient frame rendering directly in the terminal without relying on external graphical libraries. This approach offers a unique way to experience video playback in an environment where graphical output is usually limited to text-based rendering.