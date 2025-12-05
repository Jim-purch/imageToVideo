import os
import sys
import platform
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import urllib.request
from moviepy import VideoFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips

# Font download URL (Google Fonts - Roboto Regular)
FONT_URL = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Regular.ttf"
LOCAL_FONT_PATH = "Roboto-Regular.ttf"

def get_font(font_size):
    """
    Returns a PIL ImageFont object.
    Tries to find a local font, downloads one if missing, or falls back to default.
    """
    try:
        # 1. Check if we have the downloaded font
        if not os.path.exists(LOCAL_FONT_PATH):
            print(f"Downloading font from {FONT_URL}...")
            try:
                urllib.request.urlretrieve(FONT_URL, LOCAL_FONT_PATH)
            except Exception as e:
                print(f"Failed to download font: {e}")

        if os.path.exists(LOCAL_FONT_PATH):
            return ImageFont.truetype(LOCAL_FONT_PATH, font_size)

        # 2. Fallback to system fonts (simple check)
        system = platform.system()
        if system == "Linux":
            paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                     "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]
            for p in paths:
                if os.path.exists(p):
                    return ImageFont.truetype(p, font_size)
        elif system == "Windows":
             return ImageFont.truetype("arial.ttf", font_size)
        elif system == "Darwin": # MacOS
             return ImageFont.truetype("Arial.ttf", font_size)

    except Exception as e:
        print(f"Font loading error: {e}")

    print("Warning: Using default PIL font (may be small/pixelated).")
    return ImageFont.load_default()

def create_text_image(text, height, video_width):
    """
    Creates a PIL Image containing the text on a transparent background.
    The image width depends on the text length.
    """
    try:
        font_size = int(height * 0.8)
        font = get_font(font_size)

        # Calculate text size using bbox (left, top, right, bottom)
        bbox = font.getbbox(text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1] # Approximate height

        if text_width == 0:
            # Handle empty text case
            return None, 0

        img = Image.new('RGBA', (text_width, height), (0, 0, 0, 0)) # Transparent
        draw = ImageDraw.Draw(img)

        # Draw text centered vertically
        # text_height is height of glyphs, bbox[1] usually negative or 0.
        # Simple centering:
        draw.text((0, (height - font_size) // 2), text, font=font, fill='white')

        return img, text_width
    except Exception as e:
        print(f"Error creating text image: {e}")
        return None, 0

def resize_with_padding(image_path, target_size):
    """
    Resizes an image to fit within target_size while maintaining aspect ratio,
    and pads with black to fill the target size.
    """
    pil_img = Image.open(image_path)
    pil_img = pil_img.convert('RGB')

    target_w, target_h = target_size
    orig_w, orig_h = pil_img.size

    ratio = min(target_w / orig_w, target_h / orig_h)
    new_w = int(orig_w * ratio)
    new_h = int(orig_h * ratio)

    resized_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Create black background
    new_img = Image.new('RGB', target_size, (0, 0, 0))
    paste_x = (target_w - new_w) // 2
    paste_y = (target_h - new_h) // 2

    new_img.paste(resized_img, (paste_x, paste_y))

    return np.array(new_img)

def generate_slideshow(image_paths, text, output_path="output.mp4", duration=30, resolution=(1280, 720)):
    """
    Generates a slideshow video from images with scrolling text.
    """
    if not image_paths:
        print("No images provided.")
        return

    # 1. Prepare Image Clips
    clips = []
    clip_duration = duration / len(image_paths)

    print(f"Processing {len(image_paths)} images...")

    for img_path in image_paths:
        # Resize and pad
        img_array = resize_with_padding(img_path, resolution)
        # Create ImageClip
        clip = ImageClip(img_array).with_duration(clip_duration)
        clips.append(clip)

    # Concatenate clips
    background_video = concatenate_videoclips(clips, method="compose")

    # 2. Prepare Scrolling Text
    banner_height = int(resolution[1] * 0.1) # 10% of height
    text_img_pil, text_width = create_text_image(text, banner_height, resolution[0])

    if text_img_pil:
        text_img_array = np.array(text_img_pil)
        text_clip = ImageClip(text_img_array).with_duration(duration)

        # Initial position: Just off the right edge
        start_x = resolution[0]
        # Final position: Just off the left edge (text fully scrolled out)
        end_x = -text_width

        # Define position function
        def scroll_func(t):
            # Linear interpolation
            if duration == 0: return (0,0)
            x = start_x + (end_x - start_x) * (t / duration)
            y = resolution[1] - banner_height - 10 # 10px padding from bottom
            return (int(x), int(y))

        text_clip = text_clip.with_position(scroll_func)

        # Composite
        final_video = CompositeVideoClip([background_video, text_clip], size=resolution)
    else:
        final_video = background_video

    # 3. Write Output
    print(f"Writing video to {output_path}...")
    final_video.write_videofile(output_path, fps=24, codec='libx264', audio=False)
    print("Done.")

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
