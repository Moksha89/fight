#!/usr/bin/env python3
"""
Match video recorder v4 - Segmented HLS recording with OCR + winner detection.

Records full match by restarting ffmpeg every 50s with fresh HLS token.
Detects match number via OCR on FIGHT # overlay.
Detects winner screen for smart screenshot capture.

Usage: python3 recorder_process.py <match_pk> <reference_id> <output_path>
"""
import json
import logging
import os
import signal
import ssl
import struct
import subprocess
import sys
import time
import urllib.request

# Only use FileHandler to avoid duplicate lines (stdout also goes to recorder.log)
log_handler = logging.FileHandler('/server/media/match_recordings/recorder.log')
log_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger = logging.getLogger('match_recorder')
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)

API_BASE = 'https://api.onlinework.vip/phdrawApi/wrtc'
HLS_BASE = 'https://origin.theclandestineproject.live/MainArena/streams'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://img.hyrcv.com/',
    'Origin': 'https://img.hyrcv.com'
}
FFMPEG_HEADERS = "Referer: https://img.hyrcv.com/\r\nOrigin: https://img.hyrcv.com\r\nUser-Agent: Mozilla/5.0\r\n"

# Segment recording config
SEGMENT_DURATION = 50  # seconds per segment (HLS allows ~70, use 50 for safety)
STALL_TIMEOUT = 12     # restart if no growth for this many seconds
EXTRA_RECORD_SECS = 15 # keep recording after stop signal for winner screen

ffmpeg_proc = None
stop_requested = False
stop_time = None  # when stop was first requested


def signal_handler(signum, frame):
    global stop_requested, stop_time
    if not stop_requested:
        logger.info("Stop signal received - will record %ds extra for winner screen" % EXTRA_RECORD_SECS)
        stop_requested = True
        stop_time = time.time()


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


def fetch_json(url):
    req = urllib.request.Request(url)
    for k, v in HEADERS.items():
        req.add_header(k, v)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    resp = urllib.request.urlopen(req, timeout=15, context=ctx)
    return json.loads(resp.read())


def get_hls_url():
    try:
        data = fetch_json(f'{API_BASE}/stream?arena_id=1')
        if data.get('success') and data.get('data'):
            stream_id = data['data']['streamId']
            token = data['data']['token']
            return f'{HLS_BASE}/{stream_id}.m3u8?token={token}', stream_id
    except Exception as e:
        logger.warning(f"Failed to get HLS URL: {e}")
    return None, None


def start_ffmpeg_segment(hls_url, segment_path):
    """Start ffmpeg to record one segment."""
    cmd = [
        'ffmpeg', '-y',
        '-headers', FFMPEG_HEADERS,
        '-i', hls_url,
        '-c', 'copy',
        '-f', 'mpegts',
        segment_path
    ]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return proc


def stop_ffmpeg(proc):
    """Gracefully stop an ffmpeg process."""
    if proc and proc.poll() is None:
        try:
            proc.stdin.write(b'q')
            proc.stdin.flush()
        except Exception:
            pass
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def detect_fight_number(video_path):
    """
    Extract fight number from video by analyzing the FIGHT # overlay
    at top-right corner of the frame.
    
    Tries multiple timestamps since early frames may show ads/splash screens
    instead of the arena with the FIGHT # badge.
    
    Returns detected number as string, or None.
    """
    try:
        # Get video duration for picking timestamps
        dur_r = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', video_path],
            capture_output=True, text=True, timeout=10
        )
        try:
            duration = float(dur_r.stdout.strip())
        except (ValueError, AttributeError):
            duration = 60

        # Try multiple timestamps (ads usually appear in first few seconds)
        timestamps = [5, 30, 60, 120, min(180, duration - 10)]
        timestamps = [t for t in timestamps if t > 0 and t < duration]

        for ts in timestamps:
            frame_path = video_path + '.ocr_frame.png'
            r = subprocess.run(
                ['ffmpeg', '-y', '-ss', str(ts), '-i', video_path,
                 '-frames:v', '1', '-f', 'image2', frame_path],
                capture_output=True, timeout=30
            )
            if not os.path.exists(frame_path) or os.path.getsize(frame_path) < 1000:
                continue

            fight_num = _read_fight_number_from_png(frame_path)
            os.remove(frame_path)
            if fight_num:
                logger.info(f"Fight number detected at t={ts}s: #{fight_num}")
                return fight_num

        return None
    except Exception as e:
        logger.warning(f"Fight number detection failed: {e}")
        return None


def _read_fight_number_from_png(png_path):
    """
    Read the FIGHT # number from the top-right corner of a PNG frame.
    Uses pixel analysis on the badge area. The number is white text on
    a dark reddish-purple background.
    """
    try:
        # Use ffmpeg to crop just the fight number region and make it larger
        crop_path = png_path + '.crop.png'
        # Crop the top-right area: x=700, y=0, w=152, h=40 (in 852x480 frame)
        subprocess.run(
            ['ffmpeg', '-y', '-i', png_path,
             '-vf', 'crop=152:40:700:0,scale=608:160',
             '-f', 'image2', crop_path],
            capture_output=True, timeout=10
        )
        if not os.path.exists(crop_path):
            return None

        # Use pytesseract with grayscale (works best for white text on gradient)
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(crop_path).convert('L')
            text = pytesseract.image_to_string(img, config='--psm 7')
            os.remove(crop_path)
            import re
            m = re.search(r'(\d+)', text)
            if m:
                return m.group(1)
        except ImportError:
            pass
        except Exception:
            pass

        if os.path.exists(crop_path):
            os.remove(crop_path)
        return None
    except Exception as e:
        logger.warning(f"OCR failed: {e}")
        return None


def detect_winner_frame(video_path, output_screenshot):
    """
    Find the best winner declaration frame from the last ~15 seconds of video.
    
    The recorder captures 15 extra seconds after the stop signal (when winner is declared).
    During those extra seconds, the LED display in the arena shows "MERON WINS" or "WALA WINS".
    
    Strategy:
    1. Extract multiple candidate frames from the last 15 seconds
    2. Score each frame by analyzing the center LED area for red/blue color dominance
    3. Also try OCR for "MERON" or "WALA" text in the center
    4. Pick the frame with the best winner signal
    5. Fallback: use the frame from 8 seconds before end
    
    Returns: 'meron', 'wala', or None
    """
    try:
        r = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', video_path],
            capture_output=True, text=True, timeout=10
        )
        duration = float(r.stdout.strip())
        logger.info(f"Video duration: {duration:.1f}s, scanning last 15s for winner frame")

        # Extract candidate frames every 2 seconds from last 15 seconds
        best_frame = None
        best_score = 0
        best_winner = None
        candidates = []

        start_scan = max(0, duration - 15)
        for t_offset in range(0, 15, 2):
            t = start_scan + t_offset
            if t >= duration:
                break
            frame_path = video_path + f'.wc_{int(t)}.png'
            subprocess.run(
                ['ffmpeg', '-y', '-ss', str(t), '-i', video_path,
                 '-frames:v', '1', '-f', 'image2', frame_path],
                capture_output=True, timeout=30
            )
            if not os.path.exists(frame_path) or os.path.getsize(frame_path) < 1000:
                continue
            candidates.append((t, frame_path))

        # Analyze each candidate
        for t, frame_path in candidates:
            winner, score = _analyze_winner_frame(frame_path)
            logger.info(f"  t={t:.0f}s: winner={winner}, score={score:.3f}")
            if score > best_score:
                best_score = score
                if best_frame and best_frame != frame_path:
                    os.remove(best_frame)
                best_frame = frame_path
                best_winner = winner
            elif frame_path != best_frame:
                os.remove(frame_path)

        if best_frame and best_score > 0.05:
            os.rename(best_frame, output_screenshot)
            logger.info(f"Winner frame saved: {best_winner} (score={best_score:.3f})")
            _cleanup_winner_frames(video_path)
            return best_winner
        else:
            # Fallback: use frame from ~8 seconds before end (middle of extra recording)
            _cleanup_winner_frames(video_path)
            fallback_time = max(0, duration - 8)
            subprocess.run(
                ['ffmpeg', '-y', '-ss', str(fallback_time), '-i', video_path,
                 '-frames:v', '1', '-f', 'image2', output_screenshot],
                capture_output=True, timeout=30
            )
            logger.info(f"Fallback screenshot at t={fallback_time:.0f}s")
            return None

    except Exception as e:
        logger.warning(f"Winner detection failed: {e}")
        return None


def _cleanup_winner_frames(video_path):
    """Remove temporary winner check frames."""
    import glob
    for f in glob.glob(video_path + '.wc_*.png'):
        try:
            os.remove(f)
        except OSError:
            pass


def _analyze_winner_frame(frame_path):
    """
    Analyze a frame to detect if it shows a winner announcement on the center LED.
    
    The center LED display (x=260-590, y=90-180 in 852x480) shows:
    - "MERON WINS" with reddish background when Meron wins
    - "WALA WINS" with bluish background when Wala wins
    
    Also tries OCR on the center area for direct text detection.
    
    Returns: (winner_str, confidence_score)
    """
    try:
        # Method 1: Color analysis on center LED area
        raw_path = frame_path + '.raw'
        subprocess.run(
            ['ffmpeg', '-y', '-i', frame_path,
             '-vf', 'crop=330:90:260:90',
             '-pix_fmt', 'rgb24', '-f', 'rawvideo', raw_path],
            capture_output=True, timeout=10
        )

        color_winner = None
        color_score = 0

        if os.path.exists(raw_path):
            raw_data = open(raw_path, 'rb').read()
            os.remove(raw_path)
            num_pixels = len(raw_data) // 3
            if num_pixels > 0:
                red_count = blue_count = white_count = 0
                for i in range(0, min(len(raw_data) - 2, num_pixels * 3), 3):
                    r, g, b = raw_data[i], raw_data[i + 1], raw_data[i + 2]
                    if r > 120 and r > g * 1.4 and r > b * 1.3:
                        red_count += 1
                    if b > 100 and b > r * 1.2:
                        blue_count += 1
                    if r > 200 and g > 200 and b > 200:
                        white_count += 1

                red_pct = red_count / num_pixels
                blue_pct = blue_count / num_pixels
                white_pct = white_count / num_pixels

                if red_pct > 0.08 and red_pct > blue_pct:
                    color_winner = 'meron'
                    color_score = red_pct + white_pct * 0.5
                elif blue_pct > 0.08 and blue_pct > red_pct:
                    color_winner = 'wala'
                    color_score = blue_pct + white_pct * 0.5

        # Method 2: OCR on center banner area (try to detect "MERON"/"WALA"/"WINS")
        ocr_winner = None
        ocr_score = 0
        try:
            import pytesseract
            from PIL import Image
            # Crop and enlarge center banner for OCR
            banner_path = frame_path + '.banner.png'
            subprocess.run(
                ['ffmpeg', '-y', '-i', frame_path,
                 '-vf', 'crop=330:90:260:90,scale=990:270',
                 '-f', 'image2', banner_path],
                capture_output=True, timeout=10
            )
            if os.path.exists(banner_path):
                img = Image.open(banner_path).convert('L')
                text = pytesseract.image_to_string(img, config='--psm 6').upper()
                os.remove(banner_path)
                if 'MERON' in text:
                    ocr_winner = 'meron'
                    ocr_score = 0.5
                    if 'WIN' in text:
                        ocr_score = 1.0
                elif 'WALA' in text:
                    ocr_winner = 'wala'
                    ocr_score = 0.5
                    if 'WIN' in text:
                        ocr_score = 1.0
        except ImportError:
            pass
        except Exception:
            pass

        # Combine results
        if ocr_score > 0:
            return ocr_winner, ocr_score
        if color_score > 0:
            return color_winner, color_score
        return None, 0

    except Exception:
        return None, 0


def record(match_pk, reference_id, output_path):
    global ffmpeg_proc, stop_requested, stop_time

    recording_dir = os.path.dirname(output_path)
    os.makedirs(recording_dir, exist_ok=True)
    
    segment_dir = os.path.join(recording_dir, f'.segments_{match_pk}')
    os.makedirs(segment_dir, exist_ok=True)

    # Wait for stream to be available
    hls_url = None
    stream_id = None
    max_wait = 180
    start_time = time.time()

    while time.time() - start_time < max_wait:
        if stop_requested and stop_time and (time.time() - stop_time > EXTRA_RECORD_SECS):
            return

        hls_url, stream_id = get_hls_url()
        if not hls_url:
            time.sleep(5)
            continue

        try:
            req = urllib.request.Request(hls_url)
            for k, v in HEADERS.items():
                req.add_header(k, v)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            resp = urllib.request.urlopen(req, timeout=10, context=ctx)
            content = resp.read(500).decode()
            if '#EXTINF' in content:
                logger.info(f"HLS stream available: {stream_id}")
                break
        except urllib.error.HTTPError as e:
            if e.code == 403:
                logger.info("403 - refreshing token...")
            else:
                logger.info(f"HTTP {e.code}")
        except Exception as e:
            logger.warning(f"Stream check failed: {e}")

        time.sleep(3)
    else:
        logger.error("Stream not available after max wait")
        return

    # --- Segmented recording loop ---
    logger.info(f"Starting segmented recording: {output_path}")
    segment_num = 0
    segments = []  # list of segment file paths
    recording_start = time.time()
    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 15  # slow down after this many consecutive failures

    while True:
        # Check if we should stop (after extra recording time)
        if stop_requested and stop_time and (time.time() - stop_time > EXTRA_RECORD_SECS):
            logger.info("Extra recording time elapsed, stopping")
            break

        # Get fresh token for this segment
        new_url, new_sid = get_hls_url()
        if new_url:
            hls_url = new_url
        elif not hls_url:
            time.sleep(3)
            continue

        # Start new segment
        segment_num += 1
        seg_path = os.path.join(segment_dir, f'seg_{segment_num:04d}.ts')
        
        ffmpeg_proc = start_ffmpeg_segment(hls_url, seg_path)
        if not ffmpeg_proc:
            time.sleep(3)
            continue

        seg_start = time.time()
        last_size = 0
        stall_start = None
        got_data = False

        # Wait up to 8 seconds for ffmpeg to start producing data
        for _ in range(16):  # 16 * 0.5s = 8s
            time.sleep(0.5)
            if ffmpeg_proc.poll() is not None:
                break  # ffmpeg exited early
            if os.path.exists(seg_path) and os.path.getsize(seg_path) > 0:
                got_data = True
                break

        if not got_data:
            # Segment failed to start - clean up and retry
            stop_ffmpeg(ffmpeg_proc)
            ffmpeg_proc = None
            if os.path.exists(seg_path):
                os.remove(seg_path)
            consecutive_failures += 1
            if consecutive_failures <= 3:
                logger.info(f"Segment {segment_num} failed to start, retrying...")
                time.sleep(2)
            elif consecutive_failures <= MAX_CONSECUTIVE_FAILURES:
                # Log less frequently during retry storms
                if consecutive_failures % 5 == 0:
                    logger.info(f"Stream down, {consecutive_failures} consecutive failures, backing off 10s...")
                time.sleep(10)
            else:
                # Extended outage - slow down to 30s between retries
                if consecutive_failures % 20 == 0:
                    logger.info(f"Extended stream outage ({consecutive_failures} failures), retrying every 30s")
                time.sleep(30)
            continue

        consecutive_failures = 0  # reset on successful start
        logger.info(f"Segment {segment_num} recording (PID {ffmpeg_proc.pid})")

        # Monitor this segment until duration reached or stalled
        while True:
            time.sleep(2)

            # Check stop with extra time
            if stop_requested and stop_time and (time.time() - stop_time > EXTRA_RECORD_SECS):
                break

            # Check if ffmpeg died
            if ffmpeg_proc.poll() is not None:
                logger.info(f"Segment {segment_num} ffmpeg exited")
                break

            # Check segment duration
            elapsed = time.time() - seg_start
            if elapsed >= SEGMENT_DURATION:
                logger.info(f"Segment {segment_num} duration reached ({int(elapsed)}s)")
                break

            # Check file growth stall
            if os.path.exists(seg_path):
                cur_size = os.path.getsize(seg_path)
                if cur_size > last_size:
                    last_size = cur_size
                    stall_start = None
                elif cur_size > 0:
                    if stall_start is None:
                        stall_start = time.time()
                    elif time.time() - stall_start > STALL_TIMEOUT:
                        logger.info(f"Segment {segment_num} stalled at {cur_size} bytes")
                        break

        # Stop this segment's ffmpeg
        stop_ffmpeg(ffmpeg_proc)
        ffmpeg_proc = None

        # Record segment if it has useful data
        if os.path.exists(seg_path) and os.path.getsize(seg_path) > 10000:
            segments.append(seg_path)
            logger.info(f"Segment {segment_num}: {os.path.getsize(seg_path)} bytes")
        else:
            if os.path.exists(seg_path):
                os.remove(seg_path)

        # Brief gap between segments
        time.sleep(1)

    total_duration = time.time() - recording_start
    logger.info(f"Recording stopped after {int(total_duration)}s, {len(segments)} segments")

    if not segments:
        logger.error("No segments recorded")
        _cleanup_segments(segment_dir)
        return

    # --- Concatenate segments into final video ---
    logger.info("Concatenating %d segments..." % len(segments))
    
    if len(segments) == 1:
        # Single segment - just convert to MP4
        ts_path = segments[0]
    else:
        # Multiple segments - concatenate using concat protocol
        # MPEG-TS files can be concatenated by simple binary concatenation
        ts_path = output_path + '.combined.ts'
        with open(ts_path, 'wb') as outf:
            for seg in segments:
                with open(seg, 'rb') as inf:
                    while True:
                        chunk = inf.read(1024 * 1024)
                        if not chunk:
                            break
                        outf.write(chunk)
        logger.info(f"Combined TS: {os.path.getsize(ts_path)} bytes")

    # Convert to MP4
    result = subprocess.run(
        ['ffmpeg', '-y', '-i', ts_path, '-c', 'copy', '-movflags', '+faststart', output_path],
        capture_output=True, timeout=120
    )

    if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
        final_size = os.path.getsize(output_path)
        
        # Get duration
        dur_result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', output_path],
            capture_output=True, text=True, timeout=10
        )
        duration_str = dur_result.stdout.strip() if dur_result.returncode == 0 else '?'
        
        logger.info(f"Recording complete: {output_path} ({final_size} bytes, {duration_str}s)")
    else:
        # Fallback: rename TS
        logger.warning("MP4 conversion failed, using TS file")
        if len(segments) == 1:
            os.rename(ts_path, output_path)
        elif os.path.exists(ts_path):
            os.rename(ts_path, output_path)

    # --- Detect fight number ---
    fight_num = detect_fight_number(output_path)
    if fight_num:
        logger.info(f"Detected FIGHT # {fight_num} in video")
    else:
        logger.info("Could not detect fight number from video")

    # --- Detect winner frame and save screenshot ---
    screenshot_path = output_path.replace('.mp4', '_win.png')
    winner = detect_winner_frame(output_path, screenshot_path)
    if winner:
        logger.info(f"Winner screenshot saved: {winner}")
    elif os.path.exists(screenshot_path):
        logger.info("Fallback screenshot saved (no winner frame detected)")

    # Cleanup
    if ts_path != segments[0] and os.path.exists(ts_path):
        os.remove(ts_path)
    _cleanup_segments(segment_dir)


def _cleanup_segments(segment_dir):
    """Remove segment files and directory."""
    try:
        import shutil
        shutil.rmtree(segment_dir, ignore_errors=True)
    except Exception:
        pass


def main():
    if len(sys.argv) < 4:
        print("Usage: recorder_process.py <match_pk> <reference_id> <output_path>")
        sys.exit(1)

    match_pk = sys.argv[1]
    reference_id = sys.argv[2]
    output_path = sys.argv[3]

    logger.info(f"Recorder started: match={match_pk} ref={reference_id}")

    try:
        record(match_pk, reference_id, output_path)
    except Exception as e:
        logger.error(f"Recorder error: {e}")

    logger.info("Recorder process exiting")


if __name__ == '__main__':
    main()
