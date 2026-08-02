"""
Serializers for the videos_app API module.

Provides serialization for video listings, categories, and resolution
metadata. Designed to match the API specification:
    - GET /api/video/ → VideoListSerializer
    - GET /api/video/<id>/<resolution>/index.m3u8 → served via views
    - GET /api/video/<id>/<resolution>/<segment>/ → served via views
"""

from rest_framework import serializers
from videos_app.models import Category, Video, VideoResolution


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for Category model.

    Used as nested representation in VideoListSerializer.
    Returns the category name as a plain string (matches API spec
    where 'category' is a string like 'Drama').
    """

    class Meta:
        model = Category
        fields = ["name"]


class VideoListSerializer(serializers.ModelSerializer):
    """
    Serializer for the video listing endpoint (GET /api/video/).

    Returns metadata for all available videos, matching the API spec:
    {
        "id": 1,
        "created_at": "2023-01-01T12:00:00Z",
        "title": "Movie Title",
        "description": "Movie Description",
        "thumbnail_url": "http://example.com/media/thumbnail/image.jpg",
        "category": "Drama"
    }

    Note: Only videos with is_active=True and status='ready' should
    be returned by the view.
    """

    thumbnail_url = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()

    class Meta:
        model = Video
        fields = [
            "id",
            "created_at",
            "title",
            "description",
            "thumbnail_url",
            "category",
        ]

    def get_thumbnail_url(self, obj: Video) -> str | None:
        """
        Return the absolute URL for the video thumbnail.

        Returns None if no thumbnail is set.
        """
        if obj.thumbnail:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
            return obj.thumbnail.url
        return None

    def get_category(self, obj: Video) -> str | None:
        """
        Return the first category name for this video.

        Returns None if the video has no categories assigned.
        """
        first_category = obj.categories.first()
        return first_category.name if first_category else None


class VideoResolutionSerializer(serializers.ModelSerializer):
    """
    Serializer for VideoResolution model.

    Used for nested representation of available quality levels
    (480p, 720p, 1080p) in the VideoDetailSerializer.
    """

    class Meta:
        model = VideoResolution
        fields = [
            "resolution",
            "width",
            "height",
            "bitrate",
        ]


class VideoDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for individual video detail views.

    Includes all metadata plus nested resolution information.
    Useful for future detail endpoints or admin queries.

    Not directly tied to the current API spec, but prepared for
    potential extensions (e.g., GET /api/video/<id>/).
    """

    categories = CategorySerializer(many=True)
    resolutions = VideoResolutionSerializer(many=True)
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Video
        fields = [
            "id",
            "title",
            "description",
            "thumbnail_url",
            "categories",
            "duration",
            "status",
            "resolutions",
            "created_at",
        ]

    def get_thumbnail_url(self, obj: Video) -> str | None:
        """
        Return the absolute URL for the video thumbnail.

        Returns None if no thumbnail is set.
        """
        if obj.thumbnail:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
            return obj.thumbnail.url
        return None
