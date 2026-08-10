"""
Custom Django storage backend that uploads files to ImageKit.io
and serves them from ImageKit's CDN.

Compatible with imagekitio Python SDK v5.x.
"""

import logging
import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible

try:
    from imagekitio import ImageKit
    from imagekitio._exceptions import APIStatusError
except ImportError:
    ImageKit = None
    APIStatusError = Exception

logger = logging.getLogger(__name__)


@deconstructible
class ImageKitStorage(Storage):
    """
    Django storage backend backed by ImageKit.io (SDK v5).

    Uploads go through the ImageKit Upload API; URLs are served
    from ImageKit's CDN (https://ik.imagekit.io/<id>/...).
    """

    def __init__(self):
        if ImageKit is None:
            raise ImportError(
                "Install the ImageKit SDK: pip install imagekitio"
            )
        private_key = settings.IMAGEKIT_PRIVATE_KEY
        if not private_key:
            raise ValueError("IMAGEKIT_PRIVATE_KEY is not set.")

        # SDK v5: only private_key is required for server-side uploads
        self.client = ImageKit(private_key=private_key)
        self.url_endpoint = settings.IMAGEKIT_URL_ENDPOINT.rstrip('/')
        self.folder = getattr(settings, 'IMAGEKIT_FOLDER', 'getmecare')
        logger.info("ImageKitStorage initialised — endpoint: %s  folder: %s",
                    self.url_endpoint, self.folder)

    # ── Required Storage interface ──────────────────────────────────────

    def _save(self, name, content):
        """Upload a file to ImageKit and return the stored file_path."""
        # Always read from the beginning
        if hasattr(content, 'seek'):
            content.seek(0)

        file_bytes = content.read() if hasattr(content, 'read') else bytes(content)

        if not file_bytes:
            raise ValueError("Cannot upload an empty file.")

        # Build a collision-safe filename while keeping the original extension
        ext = ''
        if '.' in name:
            ext = name[name.rfind('.'):]
        unique_name = f'{uuid.uuid4().hex[:16]}{ext}'

        folder = f'/{self.folder.strip("/")}'

        logger.info(
            "ImageKit upload — folder=%s  file_name=%s  size=%d bytes",
            folder, unique_name, len(file_bytes),
        )

        try:
            result = self.client.files.upload(
                file=file_bytes,
                file_name=unique_name,
                folder=folder,
                use_unique_file_name=False,  # we already made it unique
            )
        except APIStatusError as exc:
            logger.error("ImageKit API error during upload: %s", exc, exc_info=True)
            raise IOError(f"ImageKit upload failed (API error {exc.status_code}): {exc.message}") from exc
        except Exception as exc:
            logger.error("Unexpected error during ImageKit upload: %s", exc, exc_info=True)
            raise IOError(f"ImageKit upload failed: {exc}") from exc

        if result and result.file_path:
            # Strip leading '/' so Django doesn't treat it as absolute
            stored_path = result.file_path.lstrip('/')
            logger.info("ImageKit upload success — file_path=%s  url=%s",
                        stored_path, result.url)
            return stored_path

        raise IOError(f"ImageKit upload returned no file_path: {result}")

    def _open(self, name, mode='rb'):
        """Fetch a file from the CDN (used mainly for admin thumbnails)."""
        import httpx
        url = self.url(name)
        resp = httpx.get(url, timeout=30)
        resp.raise_for_status()
        return ContentFile(resp.content)

    def url(self, name):
        """Return the CDN URL for a stored file."""
        path = name.lstrip('/')
        return f'{self.url_endpoint}/{path}'

    def exists(self, name):
        """
        Always False — we use UUID-based filenames so collisions are
        astronomically unlikely, and skipping a round-trip API call
        is a big win.
        """
        return False

    def listdir(self, path):
        raise NotImplementedError("ImageKit storage does not support listdir.")

    def size(self, name):
        """Size is not readily available; return 0 to satisfy the interface."""
        return 0

    def get_modified_time(self, name):
        from django.utils import timezone
        return timezone.now()

    def delete(self, name):
        """Delete a file from ImageKit using its stored file_path."""
        path = '/' + name.lstrip('/')
        logger.info("Attempting to delete ImageKit asset at path: %s", path)
        try:
            # Search by path using the search_query parameter (SDK v5)
            results = self.client.assets.list(
                search_query=f'filePath = "{path}"',
                limit=5,
            )
            items = getattr(results, 'data', results) or []
            for asset in items:
                file_id = getattr(asset, 'file_id', None)
                if file_id:
                    self.client.files.delete(file_id)
                    logger.info("Deleted ImageKit asset — file_id=%s  path=%s",
                                file_id, path)
                    return
            logger.warning("ImageKit delete: no asset found for path %s", path)
        except Exception as exc:
            # Non-fatal — log and move on so Django doesn't break
            logger.warning("ImageKit delete failed for %s: %s", path, exc)
