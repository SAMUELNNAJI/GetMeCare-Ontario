"""
Custom Django storage backend that uploads files to ImageKit.io
and serves them from ImageKit's CDN.

Used as DEFAULT_FILE_STORAGE in production so user-uploaded media
(profile images, documents, etc.) persist across Render deploys.

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
except ImportError:
    ImageKit = None

logger = logging.getLogger(__name__)


@deconstructible
class ImageKitStorage(Storage):
    """
    Django storage backend backed by ImageKit.io.

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
        self.client = ImageKit(private_key=private_key)
        self.url_endpoint = settings.IMAGEKIT_URL_ENDPOINT.rstrip('/')
        self.folder = getattr(settings, 'IMAGEKIT_FOLDER', 'getmecare')
        logger.info("ImageKitStorage initialized for endpoint %s", self.url_endpoint)

    # ── Required Storage interface ──────────────────────────────────────

    def _save(self, name, content):
        """Upload a file to ImageKit and return the file path."""
        # Ensure the file pointer is at the start
        if hasattr(content, 'seek'):
            content.seek(0)

        # Read bytes
        if hasattr(content, 'read'):
            file_bytes = content.read()
        else:
            file_bytes = content

        # Generate a unique filename to avoid collisions
        ext = ''
        if '.' in name:
            ext = name[name.rfind('.'):]
        unique_name = f'{uuid.uuid4().hex[:16]}{ext}'

        folder = f'/{self.folder}'.rstrip('/')
        logger.info(
            "Uploading to ImageKit: folder=%s file_name=%s bytes=%d",
            folder, unique_name, len(file_bytes),
        )

        upload_result = self.client.files.upload(
            file=file_bytes,
            file_name=unique_name,
            folder=folder,
            use_unique_file_name=False,
        )

        logger.debug("ImageKit upload result: %s", upload_result)

        # The response is a Pydantic model — access fields as attributes
        if upload_result and upload_result.file_path:
            logger.info(
                "ImageKit upload success: file_path=%s url=%s",
                upload_result.file_path,
                getattr(upload_result, 'url', None),
            )
            return upload_result.file_path

        raise IOError(f'ImageKit upload failed: {upload_result}')

    def _open(self, name, mode='rb'):
        """Download a file from ImageKit (rare — mostly for admin thumbnails)."""
        url = self.url(name)
        import requests
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return ContentFile(resp.content)

    def url(self, name):
        """Return the CDN URL for a stored file."""
        # name is the filePath returned by _save (e.g. "/getmecare/abc123.jpg")
        path = name.lstrip('/')
        return f'{self.url_endpoint}/{path}'

    def exists(self, name):
        """Always return False so Django generates a fresh unique name."""
        return False

    def listdir(self, path):
        raise NotImplementedError('ImageKit storage does not support listdir')

    def size(self, name):
        return 0  # not easily available; not required for normal operation

    def get_modified_time(self, name):
        from django.utils import timezone
        return timezone.now()

    def delete(self, name):
        """Delete a file from ImageKit by looking up its file_id."""
        path = name.lstrip('/')
        logger.info("Attempting to delete ImageKit asset: %s", path)
        try:
            # List assets in the folder and find the one matching this path.
            folder = '/'.join(path.split('/')[:-1]) or self.folder
            search_path = f'/{folder}'.rstrip('/')
            assets = self.client.assets.list(
                path=search_path,
                type='file',
                limit=100,
            )
            for asset in assets:
                if getattr(asset, 'file_path', None) == path or getattr(asset, 'file_path', None) == f'/{path}':
                    file_id = getattr(asset, 'file_id', None)
                    if file_id:
                        self.client.files.delete(file_id)
                        logger.info("Deleted ImageKit asset: %s", file_id)
                        return
            logger.warning("Could not find ImageKit asset to delete: %s", path)
        except Exception as exc:
            logger.warning("ImageKit delete failed for %s: %s", path, exc)
