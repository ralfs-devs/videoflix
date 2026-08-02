"""
Views for the videos_app API module.

Implements three endpoints for video listing and HLS streaming:
    - GET /api/video/ → List all available videos
    - GET /api/video/<id>/<resolution>/index.m3u8 → HLS manifest file
    - GET /api/video/<id>/<resolution>/<segment>/ → Individual .ts segment files

All endpoints require JWT authentication. Files are served from local
storage mounted at /app/media via Docker volume videoflix_media.
"""

from django.http import HttpResponse, Http404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from videos_app.models import Video, VideoResolution, VideoSegment
from videos_app.api.serializers import VideoListSerializer


class VideoListView(APIView):
    """
    API View for listing all available videos.

    Endpoint: GET /api/video/

    Returns metadata for all active videos with 'ready' status.
    Videos are ordered by created_at DESC (newest first).

    Success Response: 200 OK with list of video metadata
    Errors: 401 Unauthorized (if not authenticated), 500 Server Error
    Rate Limits: No limit

    Example Response:
    [
        {
            "id": 1,
            "created_at": "2023-01-01T12:00:00Z",
            "title": "Movie Title",
            "description": "Movie Description",
            "thumbnail_url": "http://example.com/media/thumbnail/image.jpg",
            "category": "Drama"
        }
    ]
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Retrieve list of all active, ready videos.
        """
        videos = Video.objects.filter(
            is_active=True,
            status="ready"
        ).prefetch_related("categories")

        serializer = VideoListSerializer(
            videos, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class VideoManifestView(APIView):
    """
    API View for serving HLS manifest files (.m3u8).

    Endpoint: GET /api/video/<int:movie_id>/<str:resolution>/index.m3u8

    Returns the HLS master playlist for a specific video and resolution.
    The manifest is read from disk and served with correct MIME type.

    URL Parameters:
        - movie_id: ID of the video
        - resolution: Target resolution (480p, 720p, 1080p)

    Success Response: 200 OK with M3U8 content (application/vnd.apple.mpegurl)
    Errors: 404 Not Found (video/resolution not found), 401 Unauthorized

    Note: This endpoint bypasses DRF serialization for raw file delivery.
    The manifest file is served directly from /app/media/hls/{video_id}/{resolution}/index.m3u8
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, movie_id, resolution):
        """
        Retrieve and serve HLS manifest file for given video and resolution.
        """
        try:
            video = Video.objects.get(
                id=movie_id, is_active=True, status="ready")
        except Video.DoesNotExist:
            raise Http404("Video not found")

        try:
            video_resolution = video.resolutions.get(resolution=resolution)
        except VideoResolution.DoesNotExist:
            raise Http404("Video or manifest not found")

        # Get the manifest file path
        if not video_resolution.hls_manifest:
            raise Http404("Video or manifest not found")

        manifest_path = video_resolution.hls_manifest.path

        try:
            with open(manifest_path, "r", encoding="utf-8") as manifest_file:
                manifest_content = manifest_file.read()
        except FileNotFoundError:
            raise Http404("Video or manifest not found")
        except PermissionError:
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return HttpResponse(
            manifest_content,
            content_type="application/vnd.apple.mpegurl"
        )


class VideoSegmentView(APIView):
    """
    API View for serving HLS video segments (.ts files).

    Endpoint: GET /api/video/<int:movie_id>/<str:resolution>/<str:segment>/

    Returns an individual video segment for playback. The segment file
    is served directly with correct MIME type for HLS streaming.

    URL Parameters:
        - movie_id: ID of the video
        - resolution: Target resolution (480p, 720p, 1080p)
        - segment: Segment filename (e.g., '000.ts', '001.ts')

    Success Response: 200 OK with binary .ts content (video/MP2T)
    Errors: 404 Not Found (video/segment not found), 401 Unauthorized

    Note: This endpoint bypasses DRF serialization for raw file delivery.
    The segment file is served directly from /app/media/hls/{video_id}/{resolution}/segments/{segment}
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, movie_id, resolution, segment):
        """
        Retrieve and serve video segment file for given video, resolution, and segment name.
        """
        try:
            video = Video.objects.get(
                id=movie_id, is_active=True, status="ready")
        except Video.DoesNotExist:
            raise Http404("Video not found")

        try:
            video_resolution = video.resolutions.get(resolution=resolution)
        except VideoResolution.DoesNotExist:
            raise Http404("Video or segment not found")

        try:
            video_segment = video_resolution.segments.get(segment_name=segment)
        except VideoSegment.DoesNotExist:
            raise Http404("Video or segment not found")

        if not video_segment.segment_file:
            raise Http404("Video or segment not found")

        segment_path = video_segment.segment_file.path

        try:
            with open(segment_path, "rb") as segment_file:
                segment_content = segment_file.read()
        except FileNotFoundError:
            raise Http404("Video or segment not found")
        except PermissionError:
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return HttpResponse(
            segment_content,
            content_type="video/MP2T"
        )
