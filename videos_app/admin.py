from django.contrib import admin
from videos_app.models import Category, Video, VideoResolution, VideoSegment


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "video_count"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}

    def video_count(self, obj):
        return obj.videos.count()

    video_count.short_description = "Videos"


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ["title", "status", "duration", "created_at", "is_active"]
    list_filter = ["status", "is_active", "categories", "created_at"]
    search_fields = ["title", "description"]
    readonly_fields = ["thumbnail", "duration", "created_at", "updated_at"]
    date_hierarchy = "created_at"

    fieldsets = (
        ("Metadata", {
            "fields": ("title", "description", "categories", "thumbnail")
        }),
        ("Source File", {
            "fields": ("original_video_file",),
            "description": "Upload original video file for transcoding"
        }),
        ("Status & Info", {
            "fields": ("status", "duration", "is_active"),
            "classes": ("collapse",),
            "description": "Status managed by RQ worker"
        }),
    )


@admin.register(VideoResolution)
class VideoResolutionAdmin(admin.ModelAdmin):
    list_display = ["video", "resolution", "width",
                    "height", "bitrate", "processed_at"]
    list_filter = ["resolution", "processed_at"]
    search_fields = ["video__title"]
    readonly_fields = ["hls_manifest", "width",
                       "height", "bitrate", "processed_at"]


@admin.register(VideoSegment)
class VideoSegmentAdmin(admin.ModelAdmin):
    list_display = ["resolution", "segment_name",
                    "sequence_index", "duration"]
    list_filter = ["resolution__resolution", "resolution__video"]
    search_fields = ["segment_path", "resolution__video__title"]
    readonly_fields = ["segment_path",
                       "sequence_index", "duration"]
