"""Utility functions for video processing.

Provides helpers for probing, encoding, thumbnail generation,
and HLS manifest parsing used by the encoding pipeline.
"""

import os
import json
import logging
import subprocess

from django.conf import settings

logger = logging.getLogger(__name__)

RESOLUTIONS = [
    {'resolution': '1080p', 'width': 1920, 'height': 1080,
     'bitrate': 5000, 'maxrate': 5350, 'bufsize': 10000},
    {'resolution': '720p', 'width': 1280, 'height': 720,
     'bitrate': 2800, 'maxrate': 2996, 'bufsize': 5600},
    {'resolution': '480p', 'width': 854, 'height': 480,
     'bitrate': 1400, 'maxrate': 1498, 'bufsize': 2800},
]


def probe_video(video_path):
    """Extract duration and audio presence using ffprobe.

    Args:
        video_path: Absolute path to the video file.

    Returns:
        A tuple of (duration_seconds, has_audio_stream).
    """
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json',
             '-show_format', '-show_streams', video_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        data = json.loads(result.stdout)
        duration = float(data.get('format', {}).get('duration', 0))
        has_audio = any(
            s.get('codec_type') == 'audio' for s in data.get('streams', []))
        return duration, has_audio
    except Exception as exc:
        logger.warning('ffprobe failed: %s. Defaults used.', exc)
        return 0.0, False


def parse_m3u8_segments(m3u8_path):
    """Parse an HLS manifest to extract segment names and durations.

    Args:
        m3u8_path: Absolute path to the .m3u8 file.

    Returns:
        A list of dicts with 'name' and 'duration' keys.
    """
    segments = []
    current_duration = 0.0

    with open(m3u8_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#EXTINF:'):
                duration_str = line.split(':', 1)[1].rstrip(',')
                try:
                    current_duration = float(duration_str)
                except ValueError:
                    current_duration = 0.0
            elif line and not line.startswith('#'):
                segments.append({'name': line, 'duration': current_duration})
                current_duration = 0.0

    return segments


def generate_thumbnail(video_id, input_path):
    """Generate a JPEG thumbnail from the 1-second mark of a video.

    Args:
        video_id: Primary key of the Video.
        input_path: Absolute path to the source video file.

    Returns:
        Relative path from MEDIA_ROOT if successful, None otherwise.
    """
    thumbnail_dir = os.path.join(settings.MEDIA_ROOT, 'thumbnails')
    os.makedirs(thumbnail_dir, exist_ok=True)
    thumbnail_path = os.path.join(thumbnail_dir, '{}.jpg'.format(video_id))

    cmd = [
        'ffmpeg', '-y', '-ss', '1', '-i', input_path,
        '-frames:v', '1', '-q:v', '2', '-update', '1',
        thumbnail_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode == 0 and os.path.exists(thumbnail_path):
            rel_path = os.path.relpath(thumbnail_path, settings.MEDIA_ROOT)
            return rel_path.replace('\\', '/')
    except subprocess.TimeoutExpired:
        logger.warning('[VIDEO %s] Thumbnail generation timed out.', video_id)
    except Exception as exc:
        logger.warning('[VIDEO %s] Thumbnail generation failed: %s',
                       video_id, exc)

    return None


def encode_single_resolution(video_id, input_path, res, has_audio):
    """Encode a single resolution variant to HLS.

    Args:
        video_id: Primary key of the Video.
        input_path: Absolute path to the source video file.
        res: Resolution config dict with width, height, bitrate, etc.
        has_audio: Whether the source video contains an audio stream.

    Returns:
        A tuple of (success: bool, res_dir: str).
    """
    res_dir = os.path.join(
        settings.MEDIA_ROOT, 'hls', str(video_id), res['resolution'])
    os.makedirs(res_dir, exist_ok=True)

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', 'scale={}:{}'.format(res['width'], res['height']),
        '-c:v', 'libx264',
        '-b:v', '{}k'.format(res['bitrate']),
        '-maxrate', '{}k'.format(res['maxrate']),
        '-bufsize', '{}k'.format(res['bufsize']),
    ]

    if has_audio:
        cmd.extend(['-c:a', 'aac', '-b:a', '128k', '-ac', '2'])

    cmd.extend([
        '-f', 'hls',
        '-hls_time', '6',
        '-hls_playlist_type', 'vod',
        '-hls_segment_filename', '{}/segment_%05d.ts'.format(res_dir),
        '{}/index.m3u8'.format(res_dir),
    ])

    logger.info('[VIDEO %s] Encoding %s...', video_id, res['resolution'])

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=3600)
        if result.returncode != 0:
            logger.error('[VIDEO %s] %s encoding FAILED (exit code: %s).',
                         video_id, res['resolution'], result.returncode)
            return False, res_dir
        return True, res_dir
    except subprocess.TimeoutExpired:
        logger.error('[VIDEO %s] %s encoding TIMED OUT.',
                     video_id, res['resolution'])
        return False, res_dir
    except Exception as exc:
        logger.error('[VIDEO %s] %s encoding ERROR: %s',
                     video_id, res['resolution'], exc)
        return False, res_dir
