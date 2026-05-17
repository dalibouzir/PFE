# Storage Supabase Readiness

Date: 2026-05-17

## Scope
Pre-deploy storage readiness for WeeFarm uploads only.

Constraints respected:
- No deploy executed
- No Azure env var change executed
- No DB schema change
- No workflow/business logic change
- No Collecte/stock behavior change outside file storage URL path
- No fake business record insertion

## 1) Implementation Inspection

Inspected:
- `backend/app/services/uploads.py`
- `backend/app/core/config.py`
- `backend/.env.example`
- `backend/.env`
- `backend/app/api/routes/inputs.py`
- `app/(platform)/manager/inputs/page.tsx` (read-only verification of link rendering)

Findings:
- Backend expects these env vars for Supabase upload mode:
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
  - `SUPABASE_UPLOADS_BUCKET` (default fallback in code: `weefarm-uploads`)
- Upload behavior in `uploads.py`:
  - Supabase mode: enabled when URL + service role key are present and not placeholders.
  - Returns public URL shape:  
    `https://<project>.supabase.co/storage/v1/object/public/<bucket>/<path>`
  - Local fallback (dev-style): writes to local filesystem and returns `/uploads/<path>`.
- Collecte justificatif route uses this upload service:
  - `POST /inputs/{input_id}/justificatif`
- Frontend proof link handling:
  - Relative `/uploads/...` is prefixed with backend API base URL.
  - Absolute Supabase URL is used directly.

## 2) Supabase Bucket Verification

Target bucket:
- `weefarm-uploads`

Verification result:
- Bucket existed: **yes**
- Created in this pass: **no**
- Access mode: **public**
- Service role upload permission: **working**

## 3) Storage-Only Smoke Test (No Business Data)

Test path used:
- `health-check/storage-smoke-test.txt`

Operations:
1. Upload via Supabase Storage API with service-role key
2. Fetch via returned public URL
3. Delete test object

Result:
- Upload: `200`
- Fetch: `200`
- Delete: `200`

Returned URL shape:
- `https://gghsnrfvdthklpiopwys.supabase.co/storage/v1/object/public/weefarm-uploads/health-check/storage-smoke-test.txt`

## 4) Local Env Readiness

`.env.example`:
- `SUPABASE_URL` placeholder present: yes
- `SUPABASE_SERVICE_ROLE_KEY` placeholder present: yes
- `SUPABASE_UPLOADS_BUCKET=weefarm-uploads` present: yes

`.env` (local, gitignored):
- `SUPABASE_URL` present: yes
- `SUPABASE_SERVICE_ROLE_KEY` present: yes
- `SUPABASE_UPLOADS_BUCKET=weefarm-uploads` present: yes (added in this pass)

Secret handling:
- Service role key remains backend-only.
- No frontend env exposure introduced.

## 5) Fallback Behavior Check

Service-level check:
- With current Supabase vars: Supabase mode enabled (`True`)
- With vars absent: Supabase mode disabled (`False`) and local fallback path active

Interpretation:
- Local `/uploads` fallback remains available for development.
- With valid Supabase vars, production-intended path is Supabase URL output.

## 6) Azure / Deploy Readiness

Azure env vars still required to be present in deployed backend runtime:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_UPLOADS_BUCKET=weefarm-uploads`

Status now:
- Supabase storage side is ready.
- No Azure changes done in this task (as requested).
- No deploy done in this task (as requested).

## Final Status

- Bucket exists: **yes**
- Access mode matches code behavior (public URL): **yes**
- Env templates/local backend env ready: **yes**
- Storage smoke passed: **yes**
- Azure runtime update still needed: **yes**
- Deploy readiness: **ready after Azure env verification and deploy step**
