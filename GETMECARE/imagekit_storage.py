"""
Custom Django storage backend that uploads files to ImageKit.io
and serves them from ImageKit's CDN.

Used as DEFAULT_FILE_STORAGE in production so user-uploaded media
(profile images, documents, etc.) persist across Render deploys.
"""

import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible

try:
    from imagekitio import ImageKit
except ImportError:
    ImageKit = None


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
        self.client = ImageKit(
            private_key=settings.IMAGEKIT_PRIVATE_KEY,
            public_key=settings.IMAGEKIT_PUBLIC_KEY,
            url_endpoint=settings.IMAGEKIT_URL_ENDPOINT,
        )
        self.url_endpoint = settings.IMAGEKIT_URL_ENDPOINT.rstrip('/')
        self.folder = getattr(settings, 'IMAGEKIT_FOLDER', 'getmecare')

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

        upload_result = self.client.files.upload(
            file=file_bytes,
            file_name=unique_name,
            folder=f'/{self.folder}',
            use_unique_file_name=False,
        )

        # The response is a Pydantic model — access fields as attributes
        if upload_result and upload_result.file_path:
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
        try:
            # List files matching the path and delete by ID
            path = name.lstrip('/')
            files = self.client.files.list(
                path=f'/{path}',
                limit=1,
            )
            if files and len(files) > 0:
                self.client.files.delete(files[0].file_id)
        except Exception:
            pass  # best-effort deletion
