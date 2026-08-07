"""Signals for the videos_app module.

Provides automatic triggers for background tasks when Video
instances are created or modified.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from videos_app.models import Video

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Video)
def trigger_video_encoding(sender, instance, created, **kwargs):
    """Queue HLS encoding when a new Video is created with a file.

    Args:
        sender: The model class that sent the signal.
        instance: The actual Video instance being saved.
        created: True if this is a new instance, False otherwise.
        **kwargs: Additional signal arguments (raw, using, update_fields).

    Returns:
        None
    """
    if not created:
        logger.debug(
            '[VIDEO %s] Save triggered but not a creation. Skipping.', instance.id)
        return

    if not instance.original_video_file:
        logger.warning(
            '[VIDEO %s] No original_video_file attached. Skipping.', instance.id)
        return

    from videos_app.tasks import encode_video_to_hls

    logger.info(
        '[VIDEO %s] New video created. Queuing encoding task.', instance.id)

    try:
        result = encode_video_to_hls.delay(instance.id)
        logger.info('[VIDEO %s] Encoding task queued (job_id: %s).',
                    instance.id, result.id)
    except Exception as exc:
        logger.error(
            '[VIDEO %s] Failed to queue encoding task: %s', instance.id, exc)
