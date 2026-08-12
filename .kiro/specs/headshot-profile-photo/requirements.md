# Requirements Document

## Introduction

Caregivers on GetMeCare currently can upload any image as their profile photo with no crop or framing
constraint. This feature adds a client-side image-cropping step that intercepts the file selection,
presents a modal powered by Cropper.js (loaded via CDN, no npm), enforces a 1:1 square aspect ratio
suitable for headshot/portrait photos, and only sends the confirmed crop to the server as a JPEG Blob.
All existing server-side validation in `ProfileImageForm` (magic-byte check, 5 MB size limit,
extension check) remains intact. The cropped Blob is submitted through the existing AJAX/XHR path
to `Account:edit_profile` with `action=image`.

---

## Glossary

- **Cropper**: The client-side Cropper.js widget that renders inside the Modal and controls the crop
  region.
- **CropModal**: The full-screen overlay `<dialog>` element that houses the Cropper and its
  confirm/cancel controls.
- **CropBlob**: The JPEG `Blob` produced by `canvas.toBlob()` after the user confirms the crop
  selection; this Blob is what gets uploaded to the server.
- **FileInput**: The `<input type="file" id="avatar-file-input">` element already present in
  `edit-profile.html`.
- **UploadXHR**: The existing `XMLHttpRequest` that posts form data to `Account:edit_profile` with
  `action=image`.
- **ProfileImageForm**: The Django form class in `Account/forms.py` that validates the uploaded
  image server-side (magic bytes, extension, size).
- **PreviewAvatar**: The `<img id="ep-av-img">` element in the avatar card that shows the current
  profile photo.
- **ProgressIndicator**: The existing `#avatar-progress` progress bar and percentage text already
  present in `edit-profile.html`.

---

## Requirements

### Requirement 1: Intercept file selection with a crop modal

**User Story:** As a caregiver, I want a guided cropping step after I select a photo, so that my
profile photo is always a well-framed headshot rather than an uncropped image.

#### Acceptance Criteria

1. WHEN a user selects a file via the FileInput, THE CropModal SHALL open and display the selected
   image inside the Cropper before any upload is attempted.
2. WHEN the CropModal is open, THE Cropper SHALL enforce a fixed 1:1 aspect ratio that the user
   cannot change.
3. WHEN the CropModal is open, THE Cropper SHALL display a circular preview pane so the user can
   see how the headshot will appear in the round avatar element.
4. WHEN a user cancels the CropModal, THE FileInput SHALL be reset and no upload SHALL be initiated.
5. WHEN the CropModal opens, THE Cropper SHALL load the Cropper.js library from the CDN URL
   `https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.2/cropper.min.js` without any npm or
   build-tool dependency.

### Requirement 2: Produce and validate the cropped output

**User Story:** As a caregiver, I want the cropped image sent to the server in the correct format
and within the size limit, so that my profile photo is saved reliably.

#### Acceptance Criteria

1. WHEN a user confirms the crop, THE Cropper SHALL export the crop region as a JPEG Blob with
   quality 0.92 using `HTMLCanvasElement.toBlob`.
2. WHEN the crop export produces a Blob larger than 5,242,880 bytes (5 MB), THE CropModal SHALL
   display an error message and SHALL NOT submit the Blob to the server.
3. WHEN the crop export produces a Blob of 5,242,880 bytes or fewer, THE Cropper SHALL close the
   CropModal and pass the Blob to the UploadXHR.
4. WHEN the CropBlob is submitted, THE UploadXHR SHALL append the CropBlob to a `FormData` object
   with the field name `profile_image` and filename `headshot.jpg`.
5. WHEN the CropBlob is submitted, THE UploadXHR SHALL include the `csrfmiddlewaretoken` field and
   the `action=image` field so that the server-side `edit_profile` view processes it correctly.

### Requirement 3: Preserve server-side validation

**User Story:** As a system operator, I want the server to continue validating all uploads
independently of the client crop step, so that no malformed or oversized image can reach the
database.

#### Acceptance Criteria

1. THE ProfileImageForm SHALL validate that the uploaded file does not exceed 5,242,880 bytes
   regardless of whether the file originated from the crop modal or a direct POST.
2. THE ProfileImageForm SHALL validate the magic bytes of the uploaded file against the JPEG, PNG,
   and WebP signatures regardless of the claimed file extension.
3. THE ProfileImageForm SHALL reject any file whose extension is not one of `jpg`, `jpeg`, `png`,
   or `webp`.
4. WHEN the `edit_profile` view receives a POST with `action=image` and no `profile_image` file,
   THE view SHALL return a 400 JSON response with `{"ok": false, "error": "..."}` for AJAX
   requests.

### Requirement 4: Progress feedback and avatar preview

**User Story:** As a caregiver, I want to see upload progress and an immediate preview of my new
headshot, so that I know the upload succeeded.

#### Acceptance Criteria

1. WHEN the UploadXHR is in progress, THE ProgressIndicator SHALL display the upload percentage
   updated on each XHR `progress` event.
2. WHEN the server returns `{"ok": true, "url": "..."}`, THE PreviewAvatar SHALL update its `src`
   attribute to the returned URL with a cache-busting query parameter.
3. WHEN the server returns `{"ok": true, "url": "..."}`, THE ProgressIndicator SHALL display
   "Photo updated!" for 2,200 ms and then hide.
4. WHEN the server returns `{"ok": false, ...}` or a network error occurs, THE ProgressIndicator
   SHALL hide and THE client SHALL display an alert with the error message.
5. WHILE an upload is in progress, THE FileInput trigger area SHALL be non-interactive so that a
   second file selection cannot be started.

### Requirement 5: Mobile-friendly modal layout

**User Story:** As a caregiver using a mobile device, I want the crop modal to be usable on a small
screen, so that I can upload a headshot from my phone.

#### Acceptance Criteria

1. THE CropModal SHALL use `position: fixed` with `inset: 0` so that it covers the full viewport
   on all screen sizes.
2. WHEN the viewport width is 600 px or less, THE CropModal SHALL size the Cropper container to
   90 vw × 90 vw so the crop area fills most of the screen without overflowing.
3. WHEN the viewport width is greater than 600 px, THE CropModal SHALL constrain the Cropper
   container to a maximum of 480 px × 480 px.
4. THE CropModal SHALL be dismissible by pressing the Escape key, with the same effect as clicking
   Cancel (FileInput reset, no upload).
