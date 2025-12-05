import os
import sys
import platform
import random
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import urllib.request
from moviepy import VideoFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips, vfx, ColorClip, AudioFileClip

# Font download URLs (Google Fonts - Noto Sans SC / Ma Shan Zheng)
# We try multiple URLs because GitHub raw paths can be tricky or change.
FONT_URLS = [
    # NotoSansSC variable font
    ("NotoSansSC-Regular.ttf", "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf"),
    # Ma Shan Zheng (Calligraphic)
    ("MaShanZheng-Regular.ttf", "https://raw.githubusercontent.com/google/fonts/main/ofl/mashanzheng/MaShanZheng-Regular.ttf"),
]

def get_font(font_size, font_path=None):
    """
    Returns a PIL ImageFont object.
    If font_path is provided, tries to use it.
    Otherwise, tries to find a local font, downloads one if missing, or falls back to default.
    """
    try:
        if font_path and os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, font_size)
            except Exception as e:
                print(f"Error loading provided font path {font_path}: {e}")

        # 1. Check if we have any of the downloaded fonts
        for filename, url in FONT_URLS:
            if os.path.exists(filename):
                return ImageFont.truetype(filename, font_size)

        # 2. Try to download
        for filename, url in FONT_URLS:
            print(f"Attempting to download font from {url}...")
            try:
                urllib.request.urlretrieve(url, filename)
                if os.path.exists(filename):
                    print(f"Successfully downloaded {filename}")
                    return ImageFont.truetype(filename, font_size)
            except Exception as e:
                print(f"Failed to download from {url}: {e}")

        # 3. Fallback to system fonts (prioritize CJK)
        system = platform.system()
        if system == "Linux":
            # Common Linux CJK fonts
            paths = [
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                "/usr/share/fonts/truetype/arphic/uming.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
            ]
            for p in paths:
                if os.path.exists(p):
                    print(f"Using system font: {p}")
                    return ImageFont.truetype(p, font_size)
        elif system == "Windows":
             try:
                 return ImageFont.truetype("msyh.ttc", font_size) # Microsoft YaHei
             except:
                 try:
                     return ImageFont.truetype("simhei.ttf", font_size) # SimHei
                 except:
                     return ImageFont.truetype("arial.ttf", font_size)
        elif system == "Darwin": # MacOS
             try:
                 return ImageFont.truetype("PingFang.ttc", font_size)
             except:
                 return ImageFont.truetype("Arial.ttf", font_size)

    except Exception as e:
        print(f"Font loading error: {e}")

    print("Warning: Using default PIL font (may be small/pixelated).")
    return ImageFont.load_default()

def create_text_image(text, font_size, video_width, font_path=None):
    """
    Creates a PIL Image containing the text on a transparent background.
    The image width depends on the text length.
    """
    try:
        font = get_font(font_size, font_path)

        # Calculate text size using bbox (left, top, right, bottom)
        bbox = font.getbbox(text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1] # Approximate height

        if text_width == 0:
            # Handle empty text case
            return None, 0, 0

        # Height of the image should accommodate the font
        image_height = int(font_size * 1.5)

        # Add padding for shadow
        shadow_offset = 3

        img = Image.new('RGBA', (text_width + shadow_offset, image_height), (0, 0, 0, 0)) # Transparent
        draw = ImageDraw.Draw(img)

        # Draw text centered vertically
        y_pos = (image_height - font_size) // 2

        # Shadow (Black)
        draw.text((shadow_offset, y_pos + shadow_offset), text, font=font, fill='black')

        # Main Text (White)
        draw.text((0, y_pos), text, font=font, fill='white')

        return img, text_width, image_height
    except Exception as e:
        print(f"Error creating text image: {e}")
        return None, 0

def resize_with_padding(image_path, target_size, bg_color=(255, 255, 255)):
    """
    Resizes an image to fit within target_size while maintaining aspect ratio,
    and pads with bg_color to fill the target size.
    """
    pil_img = Image.open(image_path)
    pil_img = pil_img.convert('RGB')

    target_w, target_h = target_size
    orig_w, orig_h = pil_img.size

    ratio = min(target_w / orig_w, target_h / orig_h)
    new_w = int(orig_w * ratio)
    new_h = int(orig_h * ratio)

    resized_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Create background
    new_img = Image.new('RGB', target_size, bg_color)
    paste_x = (target_w - new_w) // 2
    paste_y = (target_h - new_h) // 2

    new_img.paste(resized_img, (paste_x, paste_y))

    return np.array(new_img)

def apply_zoom_effect(clip, zoom_ratio=0.1):
    """
    Applies a gradual zoom effect (Ken Burns).
    Zooms from 1.0 to 1.0 + zoom_ratio over the clip's duration.
    Center-anchored zoom is achieved by resizing while the clip is centered in the composition.
    """
    def resize_func(t):
        return 1 + zoom_ratio * (t / clip.duration)
    return clip.with_effects([vfx.Resize(resize_func)])

def generate_slideshow(image_paths, text, output_path="output.mp4", duration=30, resolution=(1000, 1000), font_size=40, font_path=None, bottom_margin=50, zoom_factor=1.2, transition_effect="random", audio_path=None, bg_color=(255, 255, 255), progress_callback=None):
    """
    Generates a slideshow video from images with scrolling text.
    - Applies dynamic zoom (Ken Burns) to images (center-based).
    - Applies transitions between images based on transition_effect.
    transition_effect: "random", "crossfade", "slide_left", "slide_right", "slide_top", "slide_bottom"
    audio_path: Path to background audio/dubbing file.
    bg_color: Tuple (r, g, b) for background color.
    progress_callback: A function that takes a string message.
    """
    def log(msg):
        print(msg)
        if progress_callback:
            progress_callback(msg)

    if not image_paths:
        log("No images provided.")
        return

    # 1. Prepare Image Clips with Zoom and Transitions

    num_images = len(image_paths)
    transition_duration = 1.0

    # Calculate clip duration to satisfy the total duration requested
    # Total duration = (Clip1) + (Clip2 - trans) + ...
    # Approximately: Total = Clip * N - Trans * (N-1)
    # Clip * N = Total + Trans * (N-1)
    # Clip = (Total + Trans * (N-1)) / N

    if num_images > 1:
        raw_duration_needed = duration + (num_images - 1) * transition_duration
    else:
        raw_duration_needed = duration

    clip_duration = raw_duration_needed / num_images

    # Ensure transition isn't longer than half the clip
    if transition_duration > clip_duration / 2:
        transition_duration = clip_duration / 2

    log(f"Processing {len(image_paths)} images with transitions ({transition_effect})...")

    final_clips = []

    # Add a background clip as the base layer to prevent black edges
    base_bg = ColorClip(size=resolution, color=bg_color).with_duration(duration)
    final_clips.append(base_bg)

    current_start = 0.0

    valid_transitions = ["crossfade", "slide_left", "slide_right", "slide_top", "slide_bottom"]

    for i, img_path in enumerate(image_paths):
        # Resize and pad
        img_array = resize_with_padding(img_path, resolution, bg_color=bg_color)

        # Create ImageClip
        # Explicitly center the clip. While CompositeVideoClip defaults to center,
        # vfx.Resize changes the size. If we don't anchor it, it might behave unexpectedly
        # relative to the canvas. But usually with_position("center") ensures
        # the center of the clip remains at the center of the canvas.
        clip = ImageClip(img_array).with_duration(clip_duration).with_position("center")

        # Apply Zoom
        # zoom_factor 1.2 means zoom_ratio 0.2
        zoom_ratio = max(0.0, zoom_factor - 1.0)
        clip = apply_zoom_effect(clip, zoom_ratio=zoom_ratio)

        # Set start time
        if i == 0:
            clip = clip.with_start(0)
            current_start += clip_duration
        else:
            # Overlap with previous
            start_time = current_start - transition_duration
            clip = clip.with_start(start_time)

            # Determine transition type
            if transition_effect == "random":
                trans_type = random.choice(valid_transitions)
            elif transition_effect in valid_transitions:
                trans_type = transition_effect
            else:
                 trans_type = "random"

            if trans_type == "crossfade":
                clip = clip.with_effects([vfx.CrossFadeIn(transition_duration)])
            elif trans_type == "slide_left":
                clip = clip.with_effects([vfx.SlideIn(transition_duration, side="right")])
            elif trans_type == "slide_right":
                 clip = clip.with_effects([vfx.SlideIn(transition_duration, side="left")])
            elif trans_type == "slide_top":
                 clip = clip.with_effects([vfx.SlideIn(transition_duration, side="bottom")])
            elif trans_type == "slide_bottom":
                 clip = clip.with_effects([vfx.SlideIn(transition_duration, side="top")])

            current_start = start_time + clip_duration

        final_clips.append(clip)

    # Composite clips
    background_video = CompositeVideoClip(final_clips, size=resolution).with_duration(duration)

    # 2. Prepare Scrolling Text
    text_result = create_text_image(text, font_size, resolution[0], font_path)

    if text_result and text_result[0] is not None:
        text_img_pil, text_width, image_height = text_result
        text_img_array = np.array(text_img_pil)
        text_clip = ImageClip(text_img_array).with_duration(duration)

        # Initial position: Just off the right edge
        start_x = resolution[0]
        # Final position: Just off the left edge (text fully scrolled out)
        end_x = -text_width

        # Define position function
        def scroll_func(t):
            if duration == 0: return (0,0)
            x = start_x + (end_x - start_x) * (t / duration)
            # Use bottom_margin
            y = resolution[1] - image_height - bottom_margin
            return (int(x), int(y))

        text_clip = text_clip.with_position(scroll_func)

        # Composite
        final_video = CompositeVideoClip([background_video, text_clip], size=resolution)
    else:
        final_video = background_video

    # 3. Add Audio if provided
    if audio_path and os.path.exists(audio_path):
        log(f"Adding audio from {audio_path}...")
        try:
            audio_clip = AudioFileClip(audio_path)
            # Handle duration mismatch:
            # If audio is longer than video, cut it.
            # If audio is shorter than video, loop it? Or just let it end?
            # Usually for dubbing, we want it to play once.
            if audio_clip.duration > final_video.duration:
                audio_clip = audio_clip.with_duration(final_video.duration)

            final_video = final_video.with_audio(audio_clip)
        except Exception as e:
            log(f"Error adding audio: {e}")

    # 4. Write Output
    log(f"Writing video to {output_path}...")
    # MoviePy's write_videofile prints its own progress to stdout/stderr.
    # Capturing that is complex, so we just log the start and end.
    # Set audio=True (default) but explicit if we added audio, or audio=False if not?
    # write_videofile checks if clip has audio.
    final_video.write_videofile(output_path, fps=24, codec='libx264')
    log("Done.")

if __name__ == "__main__":
    # Test execution
    test_images = ["img1.jpg", "img2.jpg", "img3.jpg", "img4.jpg"]
    test_text = "This is a scrolling text example. It moves from right to left across the screen over the duration of the video. Enjoy the slideshow!"

    # Verify images exist
    valid_images = [img for img in test_images if os.path.exists(img)]

    if valid_images:
        generate_slideshow(valid_images, test_text, "test_output.mp4")
    else:
        print("Test images not found. Run create_dummy_images.py first.")
