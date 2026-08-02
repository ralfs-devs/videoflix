"""
URL configuration for videos_app API.

Routes:
    - /api/video/ → VideoListView (list all videos)
    - /api/video/<id>/<resolution>/index.m3u8 → VideoManifestView (HLS manifest)
    - /api/video/<id>/<resolution>/<segment>/ → VideoSegmentView (video segments)
"""

from django.urls import path
from .views import VideoListView, VideoManifestView, VideoSegmentView

app_name = "videos_app"

urlpatterns = [
    path(
        "video/",
        VideoListView.as_view(),
        name="video-list"
    ),
    path(
        "video/<int:movie_id>/<str:resolution>/index.m3u8",
        VideoManifestView.as_view(),
        name="video-manifest"
    ),
    path(
        "video/<int:movie_id>/<str:resolution>/<str:segment>/",
        VideoSegmentView.as_view(),
        name="video-segment"
    ),
]
