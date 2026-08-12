# Implementation Plan: Headshot-Only Profile Photo Upload

## Overview

Implement the client-side Cropper.js modal and preserve all server-side validation. Changes are
confined to `templates/Account/edit-profile.html` (CDN tags, modal HTML, CSS, JS) and
`Account/tests.py` (property-based and example tests for `ProfileImageForm`). No changes to
`views.py` or `forms.py` are needed.

---

## Tasks

- [x] 1. Add Cropper.js CDN dependencies to the template
  - [x] 1.1 Insert Cropper.js CSS `<link>` and JS `<script defer>` CDN tags into the
    `{% block extra_head %}` section of `templates/Account/edit-profile.html`
    - CDN CSS: `https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.2/cropper.min.css`
    - CDN JS: `https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.2/cropper.min.js`
    - Both tags must carry `crossorigin="anonymous"`
    - Verify the tags are placed before the `</style>` block closes and before `{% endblock %}`
    - _Requirements: 1.5_

- [x] 2. Add CropModal HTML structure and CSS to the template
  - [x] 2.1 Insert the `<dialog id="crop-modal">` element with all inner elements (`#crop-container`,
    `#crop-image`, `#crop-preview-wrap`, `#crop-preview`, `#crop-modal-footer`,
    `#crop-size-error`, `#crop-confirm-btn`, `#crop-cancel-btn`) just before
    `{% endblock content %}` in `edit-profile.html`
    - Follow the HTML structure in the design document exactly
    - `#crop-size-error` must have `hidden` and `role="alert"` attributes
    - _Requirements: 1.1, 1.3, 2.2, 5.1_
  - [x] 2.2 Add all CropModal CSS rules to the `<style>` block in `{% block extra_head %}`
    - `#crop-modal` must use `position: fixed; inset: 0`
    - `#crop-preview` must use `border-radius: 50%`
    - Include the `@media (max-width: 600px)` responsive rules that set `#crop-container`
      to `max-height: min(90vw, 360px)` and constrain modal width to `96vw`
    - Desktop: modal `width: min(520px, 96vw)`, `#crop-container max-height: 400px`
    - _Requirements: 1.3, 5.1, 5.2, 5.3_

- [x] 3. Implement the CropController JavaScript
  - [x] 3.1 In the `{% block extra_scripts %}` of `edit-profile.html`, replace the existing IIFE
    with an expanded IIFE that adds the `openCropModal`, `closeCropModal`, `confirmCrop`,
    `onBlob`, and `doUpload` functions
    - `openCropModal(file)`: uses `FileReader` to read file as DataURL, sets `#crop-image` src,
      calls `cropModal.showModal()`, initialises `new Cropper(cropImageEl, {aspectRatio: 1,
      viewMode: 1, preview: '#crop-preview'})`
    - `closeCropModal()`: calls `cropper.destroy()`, `cropModal.close()`, resets
      `fileInput.value = ''`, hides `#crop-size-error`
    - `confirmCrop()`: disables `#crop-confirm-btn`, calls
      `cropper.getCroppedCanvas().toBlob(onBlob, 'image/jpeg', 0.92)`
    - `onBlob(blob)`: if `!blob`, shows an error alert and re-enables confirm; if
      `blob.size > 5 * 1024 * 1024`, shows `#crop-size-error` and re-enables confirm; otherwise
      calls `closeCropModal()` then `doUpload(blob)`
    - `doUpload(blob)`: builds `FormData` with `csrfmiddlewaretoken`, `action=image`, and
      `profile_image` as a `File(blob, 'headshot.jpg', {type:'image/jpeg'})`; wires to the
      existing `setUploading`, `progressFill`, `progressText`, `showDone`, `showError`,
      `imgEl`, `initials` variables already present in the outer IIFE; sends via XHR
    - Bind `fileInput.addEventListener('change', ...)` to call `openCropModal` instead of
      the old direct-upload path
    - Bind `#crop-cancel-btn click` → `closeCropModal()`
    - Bind `#crop-confirm-btn click` → `confirmCrop()`
    - Bind `#crop-modal cancel` (Escape) → `closeCropModal()`
    - _Requirements: 1.1, 1.2, 1.4, 2.1, 2.2, 2.3, 2.4, 2.5, 4.1, 4.2, 4.3, 4.4, 4.5, 5.4_

- [x] 4. Checkpoint — manual smoke test
  - Open the edit-profile page in a browser, click the avatar, select a photo, verify the crop
    modal appears with a 1:1 crop box and a circular preview pane.
  - Confirm a crop and verify the progress bar advances, the avatar preview updates, and "Photo
    updated!" appears.
  - Press Escape and verify the modal closes with no upload.
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Write server-side tests for ProfileImageForm
  - [x] 5.1 Write example-based unit tests in `Account/tests.py` for `ProfileImageForm`
    - Valid JPEG (with correct magic bytes and extension) is accepted
    - Valid PNG accepted
    - Valid WebP accepted
    - File with `.gif` extension is rejected with a `ValidationError`
    - File whose magic bytes do not match any allowed type is rejected
    - File of exactly 5,242,880 bytes is accepted
    - File of 5,242,881 bytes is rejected
    - AJAX POST to `edit_profile` with `action=image` and no file returns status 400 with
      `{"ok": false, "error": "..."}` (uses Django `TestClient`)
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ]* 5.2 Write property-based tests using Hypothesis in `Account/tests.py`
    - Install `hypothesis` as a dev dependency (`pip install hypothesis`)
    - **Feature: headshot-profile-photo, Property 3: ProfileImageForm rejects any file exceeding 5 MB**
      - `@given(st.integers(min_value=5*1024*1024+1, max_value=10*1024*1024))` — generate size,
        create `SimpleUploadedFile` of that size filled with JPEG magic bytes, assert
        `ValidationError` is raised
    - **Feature: headshot-profile-photo, Property 4: ProfileImageForm rejects files with invalid magic bytes**
      - `@given(st.binary(min_size=12, max_size=24))` filtered to exclude valid magic prefixes —
        create `SimpleUploadedFile` named `test.jpg`, assert `ValidationError` is raised
    - **Feature: headshot-profile-photo, Property 5: ProfileImageForm rejects files with disallowed extensions**
      - `@given(st.text(alphabet='abcdefghijklmnopqrstuvwxyz', min_size=1, max_size=8))` filtered
        to exclude `{'jpg','jpeg','png','webp'}` — create `SimpleUploadedFile` with that extension
        and valid JPEG magic bytes, assert `ValidationError` is raised
    - Set `@settings(max_examples=100)` on each test
    - _Requirements: 3.1, 3.2, 3.3_

- [x] 6. Final checkpoint — ensure all tests pass
  - Run `python manage.py test Account` and confirm all tests pass, ask the user if questions
    arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP; the core crop modal
  functionality does not depend on them
- No changes to `views.py`, `forms.py`, or any model are required
- Hypothesis must be installed only as a **development** dependency; it must not be added to
  production requirements
- The existing `setUploading`, `showDone`, `showError` functions in the IIFE must be preserved
  unchanged so the progress indicator behavior (Requirements 4.1–4.5) continues to work
- Cropper.js `preview` option requires the preview element to exist in the DOM before
  `new Cropper(...)` is called — the `#crop-preview` div must be present in the HTML before the
  script runs

---

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1", "2.2"] },
    { "id": 2, "tasks": ["3.1"] },
    { "id": 3, "tasks": ["5.1"] },
    { "id": 4, "tasks": ["5.2"] }
  ]
}
```
