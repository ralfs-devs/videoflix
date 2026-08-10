"""Background tasks for video processing.

Provides the main encoding orchestration job. Individual steps
(probing, thumbnail, per-resolution encoding, manifest parsing)
are delegated to videos_app.utils.

All tasks are registered with django-rq on the 'default' queue.
"""

import os
import logging

from django_rq import job

from videos_app.models import Video, VideoResolution, VideoSegment
from videos_app.utils import (
    RESOLUTIONS,
    probe_video,
    generate_thumbnail,
    encode_single_resolution,
    parse_m3u8_segments,
)

logger = logging.getLogger(__name__)


@job('default')
def encode_video_to_hls(video_id):
    """Encode a video into per-resolution HLS streams.

    Orchestrates the full pipeline:
        1. Probe source video for duration and audio.
        2. Generate a thumbnail.
        3. Encode 1080p, 720p, and 480p variants.
        4. Create VideoResolution and VideoSegment records.
        5. Set status to 'ready' on success, 'failed' on error.

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

    video = _fetch_video(video_id, result)
    if video is None:
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
                video.id, int(duration), has_audio)

    rel_thumb = generate_thumbnail(video.id, input_path)
    if rel_thumb:
        video.thumbnail = rel_thumb
        video.save(update_fields=['thumbnail'])
        logger.info('[VIDEO %s] Thumbnail saved: %s', video.id, rel_thumb)
        result['thumbnail_saved'] = True
    else:
        logger.warning('[VIDEO %s] Thumbnail generation failed.', video.id)

    VideoResolution.objects.filter(video=video).delete()

    for res in RESOLUTIONS:
        success, res_dir = encode_single_resolution(
            video.id, input_path, res, has_audio)

        if not success:
            _mark_failed(video, result)
            return result

        m3u8_abs = os.path.join(res_dir, 'index.m3u8')
        if not os.path.exists(m3u8_abs):
            _mark_failed(video, result)
            return result

        m3u8_rel = 'hls/{}/{}'.format(video.id, res['resolution'])

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
                segment_path='{}/{}'.format(m3u8_rel, seg['name']),
                sequence_index=idx,
                duration=seg['duration'],
            )

        logger.info('[VIDEO %s] %s done: %d segments.',
                    video.id, res['resolution'], len(segments))

    video.status = 'ready'
    video.save(update_fields=['status'])
    result['status'] = 'ready'
    result['encoding_success'] = True
    logger.info('[VIDEO %s] Encoding pipeline completed.', video_id)

    return result


def _fetch_video(video_id, result):
    """Fetch the Video and validate it has a source file.

    Args:
        video_id: Primary key of the Video.
        result: The result dict to update on failure.

    Returns:
        The Video instance or None if not found / no file.
    """
    try:
        video = Video.objects.get(id=video_id)
    except Video.DoesNotExist:
        logger.error('[VIDEO %s] Video does not exist.', video_id)
        result['status'] = 'failed'
        return None

    if not video.original_video_file:
        logger.warning('[VIDEO %s] No original_video_file attached. Skipping.',
                       video_id)
        _mark_failed(video, result)
        return None

    return video


def _mark_failed(video, result):
    """Set video status to 'failed' and update result dict.

    Args:
        video: The Video instance to update.
        result: The result dict to update.
    """
    video.status = 'failed'
    video.save(update_fields=['status'])
    result['status'] = 'failed'
