# EduCloud LMS — Upload Trace
Source: apps/files/views.py, apps/files/serializers.py, apps/files/models.py, config/settings/base.py
READ-ONLY — real HTTP trace cannot be captured (PostgreSQL not running in this container)
All traces below are code-derived.

---

## COULD NOT EXERCISE: Database not running in handoff container.

---

## Upload flow

The backend implements a **presign → direct-to-storage → poll** flow.
The client never sends file bytes to Django — only JSON metadata to obtain a presigned URL.

---

## Step 1: Request presigned upload URL

```
POST /api/v1/files/upload/
Host: myschool.educloud.app
Cookie: sessionid=<session-key>
Content-Type: application/json
X-CSRFToken: <csrf-token>

{
  "filename": "lecture01.mp4",
  "content_type": "video/mp4",
  "category": "LESSON_VIDEO",
  "size_bytes": 157286400
}
```

UploadRequestSerializer validates: filename, content_type, category, size_bytes (min_value=1).

**Response 201:** (shape from `apps/files/services/upload.py` — service file NOT read)
```json
UNKNOWN — the exact shape of the presign response is in apps/files/services/upload.py which was not read.
Expected fields: upload_url (PUT target), file_id (StoredFile.id), possibly fields/headers for the PUT.
```

**Errors:**
- HTTP 403 if not workspace member
- HTTP 422 if invalid category, content_type not in allowed list, or size > limit

---

## Step 2: PUT bytes directly to storage

The client PUTs the file bytes to the `upload_url` from Step 1.

```
PUT <presigned-upload-url>
Content-Type: video/mp4
Content-Length: 157286400

<file bytes>
```

**For R2 (production):**
- URL is a Cloudflare R2 presigned PUT URL
- Required headers: `Content-Type` matching the declared MIME type
- CORS from R2: UNKNOWN — R2 must be configured to allow browser PUTs from the frontend origin. This is infrastructure config, not code.

**For local backend (`STORAGE_BACKEND=local`):**
- Presigned URL would be a local endpoint or mock
- UNKNOWN exact behavior of local storage for presigned PUT

---

## Step 3: Completion / scan callback

After the PUT completes:
- If `SCANNER_BACKEND != "null"`: scanner is triggered server-side; client should poll `scan_status`
- If `SCANNER_BACKEND = "null"` (default dev): scan is skipped; file is immediately usable

The scanner calls back via:
```
POST /api/v1/files/{id}/scan-callback/
X-Scanner-Secret: <shared-secret>
Content-Type: application/json

{"status": "CLEAN", "details": {}}
```
This is a server-to-server call, not a client call.

---

## Step 4: Poll scan status

```
GET /api/v1/files/{id}/
Host: myschool.educloud.app
Cookie: sessionid=<session-key>
```

**Response 200:**
```json
{
  "id": 101,
  "key": "workspaces/42/videos/lecture01.mp4",
  "original_name": "lecture01.mp4",
  "content_type": "video/mp4",
  "size_bytes": 157286400,
  "category": "LESSON_VIDEO",
  "scan_status": "PENDING",
  "is_public": false,
  "created_at": "2026-01-01T10:00:00Z",
  "url": "<presigned-download-url or null>"
}
```

`scan_status` values: `PENDING`, `CLEAN`, `INFECTED`, `ERROR`, `SKIPPED`

Poll until `scan_status != "PENDING"`.
No server-sent polling interval is defined. Suggested: 2-5 second intervals.

**If INFECTED:**
The file is quarantined. The `url` field returns null. Attempting to use the file returns:
```json
{"error": {"code": "FILE_QUARANTINED", "detail": "File is quarantined."}}
```

---

## Step 5: Get download URL

The `url` field in the GET /files/{id}/ response is already a fresh presigned download URL.
TTL depends on category:
- Most content: `SIGNED_URL_TTL_CONTENT = 7200 seconds (2 hours)`
- Payment proofs: `SIGNED_URL_TTL_PROOF = 900 seconds (15 minutes)`

The URL is generated freshly on each GET /files/{id}/ call.
**Frontend should not cache the URL beyond its TTL.**

---

## Upload validation summary

| Rule | Value |
|---|---|
| Max size | 500 MB |
| Video MIME types | video/mp4, video/webm, video/quicktime |
| Document MIME type | application/pdf only |
| Image MIME types | image/jpeg, image/png, image/gif, image/webp |
| SVG | Rejected (DR-041) |
| Attachment MIME types | pdf + images + zip + msword + docx |

---

## PARTIAL note

The exact presigned URL response shape (Step 1) is UNKNOWN — requires reading `apps/files/services/upload.py` which was not read. The frontend will discover the actual shape at integration time.
