"""
Models for the videos_app module with local storage and HLS streaming.

Videos are uploaded locally, transcoded by RQ workers into 3 quality levels
(480p, 720p, 1080p), and served via HLS protocol. All files stored in Docker
persistent volumes (/app/media mounted as videoflix_media).

Architecture:
    Upload → /app/media/original_videos/ → RQ Worker (ffmpeg) → 
    → /app/media/hls/{video_id}/{resolution}/ → API serves streams

Note: No external CDN/S3. All media stored locally in persistent Docker volumes.
"""

from django.db import models
from django.conf import settings


class Category(models.Model):
    """
    Represents a video genre/category.

    Used for grouping videos in the dashboard view (User Story 5).
    Videos can belong to multiple categories via ManyToMany relationship.

    Attributes:
        name: Display name for the category
        slug: URL-friendly identifier
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Category name (e.g., Drama, Comedy, Action)"
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        blank=True,
        help_text="URL-friendly identifier"
    )

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Video(models.Model):
    """
    Main video content model with local file storage.

    Stores metadata and the original uploaded video file. After upload,
    an RQ worker transcodes the video into 3 quality levels (480p, 720p, 1080p),
    creating corresponding VideoResolution and VideoSegment records.

    The status field tracks processing state for the RQ worker pipeline.

    Attributes:
        title: Display title of the video
        description: Detailed description of the content
        categories: Many-to-many relationship with Category model
        thumbnail: Preview image extracted from video for dashboard display
        original_video_file: Uploaded source video file (local storage)
        status: Processing state (uploaded, processing, ready, failed)
        duration: Video length in seconds (populated after transcoding)
        created_at: Record creation timestamp (for dashboard ordering DESC)
        updated_at: Last modification timestamp
        is_active: Soft-delete flag for frontend filtering

    Note: Files stored in Docker volume videoflix_media mapped to /app/media.
    Original video: /app/media/original_videos/YYYY/MM/DD/{filename}
    Thumbnails: /app/media/thumbnails/YYYY/MM/DD/{filename}
    """

    STATUS_CHOICES = [
        ("uploaded", "Uploaded"),
        ("processing", "Processing"),
        ("ready", "Ready"),
        ("failed", "Failed"),
    ]

    title = models.CharField(
        max_length=255,
        help_text="Display title of the video"
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed description of the video content"
    )
    categories = models.ManyToManyField(
        Category,
        related_name="videos",
        help_text="Genres this video belongs to"
    )
    thumbnail = models.ImageField(
        upload_to="thumbnails/%Y/%m/%d/",
        blank=True,
        null=True,
        help_text="Preview image extracted from video for dashboard display"
    )
    original_video_file = models.FileField(
        upload_to="original_videos/%Y/%m/%d/",
        help_text="Source video file (will be transcoded to 3 qualities by RQ worker)"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="uploaded",
        help_text="Processing status for RQ worker tracking"
    )
    duration = models.PositiveIntegerField(
        default=0,
        help_text="Video duration in seconds (populated after transcoding)"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Creation timestamp for dashboard ordering (DESC)"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last update timestamp"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Soft-delete flag; inactive videos hidden from API"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["is_active", "-created_at"]),
        ]

    def __str__(self) -> str:
        return self.title


class VideoResolution(models.Model):
    """
    Represents a specific resolution version of a transcoded video.

    Each video is transcoded into 3 quality levels by the RQ worker:
    480p (SD), 720p (HD), and 1080p (Full HD). Each resolution has its own
    HLS manifest (.m3u8) and associated video segments (.ts files).

    Note: Files stored in Docker volume videoflix_media mapped to /app/media.
    Manifests: /app/media/hls/{video_id}/{resolution}/index.m3u8
    """

    RESOLUTION_CHOICES = [
        ("480p", "480p (SD)"),
        ("720p", "720p (HD)"),
        ("1080p", "1080p (Full HD)"),
    ]

    video = models.ForeignKey(
        Video,
        on_delete=models.CASCADE,
        related_name="resolutions",
        help_text="Parent video this resolution belongs to"
    )
    resolution = models.CharField(
        max_length=10,
        choices=RESOLUTION_CHOICES,
        help_text="Target resolution for transcoded output (480p, 720p, 1080p)"
    )
    hls_manifest = models.FileField(
        upload_to="hls/%Y/%m/%d/manifests/",
        help_text="HLS master playlist file (.m3u8) for this resolution"
    )
    width = models.PositiveSmallIntegerField(
        help_text="Frame width in pixels"
    )
    height = models.PositiveSmallIntegerField(
        help_text="Frame height in pixels"
    )
    bitrate = models.PositiveIntegerField(
        help_text="Encoding bitrate in kbps"
    )
    processed_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Transcoding completion timestamp"
    )

    class Meta:
        unique_together = ["video", "resolution"]
        ordering = ["-height"]

    def __str__(self) -> str:
        return f"{self.video.title} - {self.resolution}"


class VideoSegment(models.Model):
    """
    Represents an individual HLS video segment (.ts file).

    During transcoding, the RQ worker splits each resolution into small
    video segments (typically 4-10 seconds each). These segments are served
    via the /api/video/<id>/<resolution>/<segment>/ endpoint.

    Note: Files stored in Docker volume videoflix_media mapped to /app/media.
    Segments: /app/media/hls/{video_id}/{resolution}/segments/{sequence_index}.ts
    """

    resolution = models.ForeignKey(
        VideoResolution,
        on_delete=models.CASCADE,
        related_name="segments",
        help_text="Resolution variant this segment belongs to"
    )
    segment_name = models.CharField(
        max_length=50,
        help_text="Segment filename (e.g., '000.ts', '001.ts')"
    )
    segment_file = models.FileField(
        upload_to="hls/%Y/%m/%d/segments/",
        help_text="Actual .ts video segment file"
    )
    sequence_index = models.PositiveIntegerField(
        help_text="Sequential order for HLS playback"
    )
    duration = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        help_text="Segment duration in seconds (typically 4-10 seconds)"
    )

    class Meta:
        ordering = ["resolution", "sequence_index"]
        unique_together = ["resolution", "segment_name"]
        indexes = [
            models.Index(fields=["resolution", "sequence_index"]),
        ]

    def __str__(self) -> str:
        return f"{self.resolution} - {self.segment_name}"
