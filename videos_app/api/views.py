"""Views for the videos_app API module.

Implements three endpoints for video listing and HLS streaming:
    - GET /api/video/ → List all available videos
    - GET /api/video/<id>/<resolution>/index.m3u8 → HLS manifest file
    - GET /api/video/<id>/<resolution>/<segment>/ → Individual .ts segment files

All endpoints require JWT authentication. Files are served from local
storage mounted at /app/media via Docker volume videoflix_media.
"""

import os

from django.conf import settings
from django.http import HttpResponse, Http404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from videos_app.models import Video, VideoResolution, VideoSegment
from videos_app.api.serializers import VideoListSerializer


class VideoListView(APIView):
    """API View for listing all available videos.

    Endpoint: GET /api/video/

    Returns metadata for all active videos with 'ready' status.
    Videos are ordered by created_at DESC (newest first).

    Attributes:
        permission_classes: Requires JWT authentication.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Retrieve list of all active, ready videos.

        Args:
            request: The HTTP request object.

        Returns:
            Response with serialized video data (200 OK).
        """
        videos = Video.objects.filter(
            is_active=True,
            status="ready"
        ).prefetch_related("categories")

        serializer = VideoListSerializer(
            videos, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class VideoManifestView(APIView):
    """API View for serving HLS manifest files (.m3u8).

    Endpoint: GET /api/video/<int:movie_id>/<str:resolution>/index.m3u8

    Returns the HLS playlist for a specific video and resolution.
    The manifest is read from disk and served with correct MIME type.

    Attributes:
        permission_classes: Requires JWT authentication.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, movie_id, resolution):
        """Retrieve and serve HLS manifest file.

        Args:
            request: The HTTP request object.
            movie_id: ID of the video.
            resolution: Target resolution (480p, 720p, 1080p).

        Returns:
            HttpResponse with m3u8 content (200 OK) or 404.
        """
        try:
            video = Video.objects.get(
                id=movie_id, is_active=True, status="ready")
        except Video.DoesNotExist:
            raise Http404("Video not found")

        try:
            video_resolution = video.resolutions.get(resolution=resolution)
        except VideoResolution.DoesNotExist:
            raise Http404("Resolution not found")

        if not video_resolution.hls_manifest:
            raise Http404("Manifest not found")

        manifest_path = os.path.join(
            settings.MEDIA_ROOT, video_resolution.hls_manifest)

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_content = f.read()
        except FileNotFoundError:
            raise Http404("Manifest file not found on disk")

        return HttpResponse(
            manifest_content,
            content_type="application/vnd.apple.mpegurl"
        )


class VideoSegmentView(APIView):
    """API View for serving HLS video segments (.ts files).

    Endpoint: GET /api/video/<int:movie_id>/<str:resolution>/<str:segment>/

    Returns an individual video segment for playback.

    Attributes:
        permission_classes: Requires JWT authentication.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, movie_id, resolution, segment):
        """Retrieve and serve video segment file.

        Args:
            request: The HTTP request object.
            movie_id: ID of the video.
            resolution: Target resolution (480p, 720p, 1080p).
            segment: Segment filename (e.g., 'segment_00000.ts').

        Returns:
            HttpResponse with binary .ts content (200 OK) or 404.
        """
        try:
            video = Video.objects.get(
                id=movie_id, is_active=True, status="ready")
        except Video.DoesNotExist:
            raise Http404("Video not found")

        try:
            video_resolution = video.resolutions.get(resolution=resolution)
        except VideoResolution.DoesNotExist:
            raise Http404("Resolution not found")

        try:
            video_segment = video_resolution.segments.get(segment_name=segment)
        except VideoSegment.DoesNotExist:
            raise Http404("Segment not found")

        if not video_segment.segment_path:
            raise Http404("Segment path not found")

        segment_path = os.path.join(
            settings.MEDIA_ROOT, video_segment.segment_path)

        try:
            with open(segment_path, "rb") as f:
                segment_content = f.read()
        except FileNotFoundError:
            raise Http404("Segment file not found on disk")

        return HttpResponse(
            segment_content,
            content_type="video/MP2T"
        )
