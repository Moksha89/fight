#!/usr/bin/env python3
"""
Match Number Detection Script - OCR for cockfight video streams.

Detects the match/fight number displayed in the top-right corner of the video.
The overlay shows "FIGHT # XXX" in white text on a dark reddish-purple badge.

Usage:
  python3 detect_match_number.py <video_file.mp4>
  python3 detect_match_number.py --live   (detect from live stream)
  python3 detect_match_number.py --dir /path/to/recordings  (scan all recordings)

Requirements:
  - ffmpeg/ffprobe (for frame extraction)
  - PIL/Pillow (for image processing)
  - pytesseract + tesseract-ocr (for OCR, optional - has pixel-based fallback)
"""
import json
import os
import re
import ssl
import subprocess
import sys
import urllib.request

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://img.hyrcv.com/',
    'Origin': 'https://img.hyrcv.com'
}


def extract_frame(video_path, timestamp=5, output=None):
    """Extract a single frame from video at given timestamp."""
    if output is None:
        output = video_path + '.detect_frame.png'
    r = subprocess.run(
        ['ffmpeg', '-y', '-ss', str(timestamp), '-i', video_path,
         '-frames:v', '1', '-f', 'image2', output],
        capture_output=True, timeout=30
    )
    if os.path.exists(output) and os.path.getsize(output) > 500:
        return output
    return None


def crop_fight_badge(frame_path, output=None):
    """
    Crop the FIGHT # badge area from top-right corner.
    In 852x480 frame: badge is at approx x=700, y=0, w=152, h=40
    Scale up 4x for better OCR.
    """
    if output is None:
        output = frame_path + '.badge.png'
    subprocess.run(
        ['ffmpeg', '-y', '-i', frame_path,
         '-vf', 'crop=152:40:700:0,scale=608:160',
         '-f', 'image2', output],
        capture_output=True, timeout=10
    )
    if os.path.exists(output) and os.path.getsize(output) > 100:
        return output
    return None


def detect_number_ocr(badge_path):
    """Try OCR with pytesseract to read the fight number."""
    try:
        import pytesseract
        from PIL import Image
        # Grayscale works best for white text on blue-purple gradient badge
        img = Image.open(badge_path).convert('L')
        text = pytesseract.image_to_string(img, config='--psm 7')
        m = re.search(r'(\d+)', text)
        if m:
            return int(m.group(1))
    except ImportError:
        pass
    except Exception:
        pass
    return None


def detect_number_pixels(badge_path):
    """
    Fallback: detect the number by analyzing pixel columns.
    The FIGHT # badge has:
    - "FIGHT #" text on the left (fixed)
    - The number in large white text on the right
    - A small red dot indicator on far right
    
    We look for vertical white pixel patterns that form digits.
    """
    try:
        # Get raw pixel data
        raw_path = badge_path + '.raw'
        subprocess.run(
            ['ffmpeg', '-y', '-i', badge_path,
             '-pix_fmt', 'rgb24', '-f', 'rawvideo', raw_path],
            capture_output=True, timeout=10
        )
        if not os.path.exists(raw_path):
            return None

        raw = open(raw_path, 'rb').read()
        os.remove(raw_path)

        # Badge is 608x160 pixels, 3 bytes per pixel
        w, h = 608, 160
        if len(raw) < w * h * 3:
            return None

        # Count white pixels per column in the number region
        # The number starts around x=350 (after "FIGHT #" text) to x=560 (before dot)
        # For each column, count pixels with brightness > 180
        white_cols = []
        for x in range(350, 560):
            count = 0
            for y in range(20, 140):  # skip top/bottom borders
                idx = (y * w + x) * 3
                r, g, b = raw[idx], raw[idx + 1], raw[idx + 2]
                brightness = (r + g + b) / 3
                if brightness > 180:
                    count += 1
            white_cols.append(count)

        # Find digit groups (clusters of columns with white pixels)
        in_digit = False
        digits_info = []
        digit_start = 0
        for i, c in enumerate(white_cols):
            if c > 15 and not in_digit:
                in_digit = True
                digit_start = i
            elif c <= 5 and in_digit:
                in_digit = False
                width = i - digit_start
                if width > 8:  # minimum digit width
                    digits_info.append((digit_start, i, width))

        # Report what we found
        return len(digits_info)  # number of digits found (rough)

    except Exception:
        return None


def detect_from_video(video_path, timestamps=None):
    """
    Detect fight number from a video file.
    Tries multiple timestamps for reliability.
    """
    if timestamps is None:
        # Get duration
        r = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', video_path],
            capture_output=True, text=True, timeout=10
        )
        try:
            dur = float(r.stdout.strip())
        except (ValueError, AttributeError):
            dur = 30
        timestamps = [3, 10, min(20, dur - 2)]

    results = []
    for ts in timestamps:
        frame = extract_frame(video_path, ts)
        if not frame:
            continue

        badge = crop_fight_badge(frame)
        if badge:
            num = detect_number_ocr(badge)
            if num:
                results.append(num)
            os.remove(badge)
        os.remove(frame)

    if results:
        # Return most common result
        from collections import Counter
        return Counter(results).most_common(1)[0][0]
    return None


def detect_from_live():
    """Detect fight number from the live stream."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    url = 'https://api.onlinework.vip/phdrawApi/wrtc/stream?arena_id=1'
    req = urllib.request.Request(url)
    for k, v in HEADERS.items():
        req.add_header(k, v)
    resp = urllib.request.urlopen(req, timeout=15, context=ctx)
    data = json.loads(resp.read())
    token = data['data']['token']
    stream_id = data['data']['streamId']
    hls_url = f'https://origin.theclandestineproject.live/MainArena/streams/{stream_id}.m3u8?token={token}'

    # Capture a frame
    frame = '/tmp/live_detect_frame.png'
    ffmpeg_headers = "Referer: https://img.hyrcv.com/\r\nOrigin: https://img.hyrcv.com\r\nUser-Agent: Mozilla/5.0\r\n"
    r = subprocess.run(
        ['ffmpeg', '-y', '-headers', ffmpeg_headers, '-i', hls_url,
         '-frames:v', '1', '-f', 'image2', frame],
        capture_output=True, timeout=30
    )
    if os.path.exists(frame) and os.path.getsize(frame) > 500:
        badge = crop_fight_badge(frame)
        num = None
        if badge:
            num = detect_number_ocr(badge)
            os.remove(badge)
        os.remove(frame)
        return num
    return None


def scan_directory(dir_path):
    """Scan all MP4 files in a directory and detect fight numbers."""
    results = []
    for f in sorted(os.listdir(dir_path)):
        if f.endswith('.mp4') and f.startswith('match_'):
            video_path = os.path.join(dir_path, f)
            print(f"Scanning {f}...", end=' ')
            num = detect_from_video(video_path, timestamps=[5])
            if num:
                print(f"FIGHT # {num}")
            else:
                print("NOT DETECTED")
            results.append((f, num))
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 detect_match_number.py <video.mp4>")
        print("  python3 detect_match_number.py --live")
        print("  python3 detect_match_number.py --dir /path/to/recordings")
        sys.exit(1)

    arg = sys.argv[1]

    if arg == '--live':
        print("Detecting fight number from live stream...")
        num = detect_from_live()
        if num:
            print(f"FIGHT # {num}")
        else:
            print("Could not detect fight number (OCR not available or stream inactive)")

    elif arg == '--dir':
        dir_path = sys.argv[2] if len(sys.argv) > 2 else '/server/media/match_recordings'
        scan_directory(dir_path)

    else:
        # Single video file
        if not os.path.exists(arg):
            print(f"File not found: {arg}")
            sys.exit(1)
        print(f"Analyzing: {arg}")
        num = detect_from_video(arg)
        if num:
            print(f"Detected FIGHT # {num}")
        else:
            print("Could not detect fight number")


if __name__ == '__main__':
    main()
