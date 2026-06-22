"""
Match Video Recorder - Subprocess-based approach (v4).

Uses a separate Python process for recording so it works with
Celery's prefork pool (where in-memory state doesn't persist between tasks).

The recorder subprocess handles:
- Segmented HLS recording (full match duration)
- Winner screen detection + smart screenshot
- Match number OCR verification

The recorder process runs independently and is managed via PID files + signals.
"""
import logging
import os
import signal
import subprocess
import time

logger = logging.getLogger(__name__)

RECORDING_DIR = '/server/media/match_recordings'
PID_DIR = '/tmp/match_recorders'
RECORDER_SCRIPT = '/server/cockfightManager/recorder_process.py'


def _pid_file(match_pk):
    return os.path.join(PID_DIR, f'recorder_{match_pk}.pid')


def _is_process_alive(pid):
    """Check if a process with given PID is running."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def start_recording(match_pk, match_number, reference_id, live_url=None):
    """
    Start recording a match in a subprocess.
    Returns dict with 'video_filename' on success, None on failure.
    """
    os.makedirs(RECORDING_DIR, exist_ok=True)
    os.makedirs(PID_DIR, exist_ok=True)

    video_filename = f'match_{match_pk}_{reference_id}.mp4'
    output_path = os.path.join(RECORDING_DIR, video_filename)

    # Check if already recording this match
    pid_file = _pid_file(match_pk)
    if os.path.exists(pid_file):
        try:
            pid = int(open(pid_file).read().strip())
            if _is_process_alive(pid):
                logger.info(f"Match {match_pk}: Already recording (PID {pid})")
                return {'video_filename': video_filename}
        except (ValueError, IOError):
            pass
        os.remove(pid_file)

    # Launch recorder subprocess
    try:
        proc = subprocess.Popen(
            ['python3', RECORDER_SCRIPT, str(match_pk), str(reference_id), output_path],
            stdout=open("/server/media/match_recordings/recorder.log", "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        # Save PID
        with open(pid_file, 'w') as f:
            f.write(str(proc.pid))

        logger.info(f"Match {match_pk}: Recorder started (PID {proc.pid})")
        return {'video_filename': video_filename}
    except Exception as e:
        logger.error(f"Match {match_pk}: Failed to start recorder: {e}")
        return None


def stop_recording(match_pk):
    """
    Stop recording a match by sending SIGTERM to the recorder process.
    The recorder will record an extra ~15 seconds to capture the winner screen,
    then save the video + winner screenshot automatically.
    Returns video_filename on success, None on failure.
    """
    pid_file = _pid_file(match_pk)
    if not os.path.exists(pid_file):
        logger.warning(f"Match {match_pk}: No PID file found")
        return None

    try:
        pid = int(open(pid_file).read().strip())
    except (ValueError, IOError):
        os.remove(pid_file)
        return None

    # Send SIGTERM to gracefully stop recording
    # The recorder will continue ~15s extra for winner screen capture
    if _is_process_alive(pid):
        try:
            os.kill(pid, signal.SIGTERM)
            logger.info(f"Match {match_pk}: Stop signal sent (PID {pid}), waiting for recorder to finish...")
            # Wait for process to finish (max 45s = 15s extra recording + 30s processing)
            for _ in range(45):
                time.sleep(1)
                if not _is_process_alive(pid):
                    break
            else:
                # Force kill if still running
                logger.warning(f"Match {match_pk}: Recorder still running after 45s, force killing")
                os.kill(pid, signal.SIGKILL)
                time.sleep(1)
        except (OSError, ProcessLookupError):
            pass

    # Clean up PID file
    try:
        os.remove(pid_file)
    except OSError:
        pass

    # Check if video file was created
    for f in os.listdir(RECORDING_DIR):
        if f.startswith(f'match_{match_pk}_') and f.endswith('.mp4'):
            filepath = os.path.join(RECORDING_DIR, f)
            if os.path.getsize(filepath) > 1000:
                logger.info(f"Match {match_pk}: Recording saved ({os.path.getsize(filepath)} bytes)")
                return f
            else:
                logger.warning(f"Match {match_pk}: Recording too small ({os.path.getsize(filepath)} bytes)")
                return None

    logger.warning(f"Match {match_pk}: No recording file found")
    return None


def get_screenshot(match_pk):
    """
    Get the winner screenshot file created by the recorder process.
    The recorder saves it as match_XX_YYYYY_win.png alongside the video.
    Returns screenshot filename on success, None if not found.
    """
    for f in os.listdir(RECORDING_DIR):
        if f.startswith(f'match_{match_pk}_') and f.endswith('_win.png'):
            filepath = os.path.join(RECORDING_DIR, f)
            if os.path.getsize(filepath) > 100:
                return f
    return None


def stop_match_recording_helper(match):
    """Stop video recording and retrieve winning screenshot. Called from tasks.py."""
    # Stop the recording (recorder will capture extra 15s + detect winner)
    video_filename = stop_recording(match.pk)

    if video_filename:
        match.recordingFile = f'match_recordings/{video_filename}'
        match.recordingStatus = 'completed'
    else:
        match.recordingStatus = 'failed'

    # Get the winner screenshot (recorder creates it, or fallback extraction)
    screenshot_file = capture_screenshot(match.pk)
    if screenshot_file:
        match.screenshotFile = f'match_recordings/{screenshot_file}'

    update_fields = ['recordingFile', 'recordingStatus', 'screenshotFile']
    match.save(update_fields=update_fields)


def capture_screenshot(match_pk, suffix='win'):
    """
    Capture a screenshot from the recorded video.
    First checks for the winner screenshot created by the recorder.
    Falls back to extracting a frame near the end of the video.
    """
    # Check if recorder already created the screenshot
    screenshot = get_screenshot(match_pk)
    if screenshot:
        return screenshot
    # Fallback to frame extraction
    return _capture_screenshot_fallback(match_pk, suffix)


def _capture_screenshot_fallback(match_pk, suffix='win'):
    """
    Fallback screenshot extraction from video file.
    Used only if the recorder process didn't save a screenshot.
    Extracts a frame from near the end of the video.
    """
    video_path = None
    for f in os.listdir(RECORDING_DIR):
        if f.startswith(f'match_{match_pk}_') and f.endswith('.mp4'):
            video_path = os.path.join(RECORDING_DIR, f)
            break

    if not video_path or not os.path.exists(video_path):
        return None

    if os.path.getsize(video_path) < 1000:
        return None

    base_name = os.path.splitext(os.path.basename(video_path))[0]
    screenshot_filename = f'{base_name}_{suffix}.png'
    screenshot_path = os.path.join(RECORDING_DIR, screenshot_filename)

    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', video_path],
            capture_output=True, text=True, timeout=10
        )
        duration = float(result.stdout.strip()) if result.stdout.strip() else 0

        if duration > 0.5:
            # Extract frame from last 2 seconds
            seek_time = max(0, duration - 2)
            subprocess.run(
                ['ffmpeg', '-y', '-ss', str(seek_time), '-i', video_path,
                 '-frames:v', '1', '-q:v', '2', screenshot_path],
                capture_output=True, timeout=15
            )
            if os.path.exists(screenshot_path) and os.path.getsize(screenshot_path) > 100:
                logger.info(f"Match {match_pk}: Fallback screenshot captured")
                return screenshot_filename
    except Exception as e:
        logger.error(f"Match {match_pk}: Fallback screenshot failed: {e}")

    return None
