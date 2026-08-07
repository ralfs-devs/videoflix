"""Application configuration for videos_app.

Ensures signals are registered when Django starts.
"""

import logging
from django.apps import AppConfig


class VideosAppConfig(AppConfig):
    """Configuration for the videos_app application.

    Attributes:
        default_auto_field: The type of auto field for primary keys.
        name: The full Python path to the application.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'videos_app'

    @staticmethod
    def _register_signals():
        """Import signal modules to register receivers.

        The import itself is the side effect that triggers the
        @receiver decorators in signals.py. The assert statement
        references the module so that Pylance recognises it as used.
        """
        from videos_app import signals
        assert signals

    def ready(self):
        """Register signal handlers when the application is ready.

        Called once during startup after all models and apps have
        been fully loaded. The local import avoids circular
        dependencies and ensures model classes are available.
        """
        self._register_signals()
        logger = logging.getLogger(__name__)
        logger.info('videos_app signals registered successfully.')
