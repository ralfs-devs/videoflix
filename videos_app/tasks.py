"""Background tasks for video processing.

Provides asynchronous jobs for:
    - HLS encoding with per-resolution outputs
    - Thumbnail generation
    - VideoSegment and VideoResolution metadata creation

All tasks are registered with django-rq on the 'default' queue.
"""

import os
import re
import logging
import subprocess
import json

from django.conf import settings
from django_rq import job

from videos_app.models import Video, VideoResolution, VideoSegment

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
                segments.append({
                    'name': line,
                    'duration': current_duration,
                })
                current_duration = 0.0

    return segments


@job('default')
def encode_video_to_hls(video_id):
    """Encode a video into per-resolution HLS streams.

    For each resolution (1080p, 720p, 480p), this task:
        1. Runs ffmpeg to produce index.m3u8 + segment .ts files.
        2. Creates a VideoResolution record with the manifest path.
        3. Parses the manifest and creates VideoSegment records.

    Also generates a thumbnail and sets the video duration.

    Args:
        video_id: Primary key of the Video to encode.

    Returns:
        A dict containing 'video_id', 'status',
        'thumbnail_saved' and 'encoding_success'.
    """
    result = {
        'video_id': video_id,
        'status': None,
        'thumbnail_saved': False,
        'encoding_success': False,
    }

    try:
        video = Video.objects.get(id=video_id)
    except Video.DoesNotExist:
        logger.error('[VIDEO %s] Video does not exist.', video_id)
        result['status'] = 'failed'
        return result

    if not video.original_video_file:
        logger.warning(
            '[VIDEO %s] No original_video_file attached. Skipping.',
            video_id)
        video.status = 'failed'
        video.save(update_fields=['status'])
        result['status'] = 'failed'
        return result

    video.status = 'processing'
    video.save(update_fields=['status'])
    logger.info('[VIDEO %s] Starting encoding pipeline.', video_id)

    input_path = video.original_video_file.path

    duration, has_audio = probe_video(input_path)
    if duration > 0:
        video.duration = int(duration)
        video.save(update_fields=['duration'])
    logger.info('[VIDEO %s] Duration: %ss, Audio: %s',
                video_id, int(duration), has_audio)

    thumbnail_dir = os.path.join(settings.MEDIA_ROOT, 'thumbnails')
    os.makedirs(thumbnail_dir, exist_ok=True)
    thumbnail_path = os.path.join(thumbnail_dir, '{}.jpg'.format(video.id))

    thumbnail_cmd = (
        'ffmpeg -y -ss 1 -i "{}" '
        '-frames:v 1 -q:v 2 -update 1 '
        '"{}"'
    ).format(input_path, thumbnail_path)

    logger.info('[VIDEO %s] Generating thumbnail...', video_id)
    thumb_exit_code = os.system(thumbnail_cmd)

    if thumb_exit_code == 0 and os.path.exists(thumbnail_path):
        rel_thumb = os.path.relpath(thumbnail_path, settings.MEDIA_ROOT)
        rel_thumb = rel_thumb.replace('\\', '/')
        video.thumbnail = rel_thumb
        video.save(update_fields=['thumbnail'])
        logger.info('[VIDEO %s] Thumbnail saved: %s', video_id, rel_thumb)
        result['thumbnail_saved'] = True
    else:
        logger.warning(
            '[VIDEO %s] Thumbnail generation failed (exit code: %s).',
            video_id, thumb_exit_code)

    VideoResolution.objects.filter(video=video).delete()

    for res in RESOLUTIONS:
        res_dir = os.path.join(
            settings.MEDIA_ROOT, 'hls', str(video.id), res['resolution'])
        os.makedirs(res_dir, exist_ok=True)

        cmd = (
            'ffmpeg -y -i "{}" '
            '-vf "scale={}:{}" '
            '-c:v libx264 -b:v {}k -maxrate {}k -bufsize {}k '
        ).format(
            input_path,
            res['width'], res['height'],
            res['bitrate'], res['maxrate'], res['bufsize'],
        )

        if has_audio:
            cmd += '-c:a aac -b:a 128k -ac 2 '

        cmd += (
            '-f hls -hls_time 6 -hls_playlist_type vod '
            '-hls_segment_filename "{}/segment_%05d.ts" '
            '"{}/index.m3u8"'
        ).format(res_dir, res_dir)

        logger.info('[VIDEO %s] Encoding %s...',
                    video_id, res['resolution'])
        exit_code = os.system(cmd)

        if exit_code != 0:
            logger.error('[VIDEO %s] %s encoding FAILED (exit code: %s).',
                         video_id, res['resolution'], exit_code)
            video.status = 'failed'
            video.save(update_fields=['status'])
            result['status'] = 'failed'
            return result

        m3u8_rel = 'hls/{}/{}'.format(video.id, res['resolution'])
        m3u8_abs = os.path.join(res_dir, 'index.m3u8')

        if not os.path.exists(m3u8_abs):
            logger.error('[VIDEO %s] %s manifest not found at %s.',
                         video_id, res['resolution'], m3u8_abs)
            video.status = 'failed'
            video.save(update_fields=['status'])
            result['status'] = 'failed'
            return result

        vr = VideoResolution.objects.create(
            video=video,
            resolution=res['resolution'],
            hls_manifest='{}/index.m3u8'.format(m3u8_rel),
            width=res['width'],
            height=res['height'],
            bitrate=res['bitrate'],
        )

        segments = parse_m3u8_segments(m3u8_abs)
        for idx, seg in enumerate(segments):
            VideoSegment.objects.create(
                resolution=vr,
                segment_name=seg['name'],
                segment_file='{}/{}'.format(m3u8_rel, seg['name']),
                sequence_index=idx,
                duration=seg['duration'],
            )

        logger.info('[VIDEO %s] %s done: %d segments.',
                    video_id, res['resolution'], len(segments))

    video.status = 'ready'
    video.save(update_fields=['status'])
    result['status'] = 'ready'
    result['encoding_success'] = True
    logger.info('[VIDEO %s] Encoding pipeline completed.', video_id)

    return result
