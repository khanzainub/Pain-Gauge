# AIIMS connected patient and admin extension

Only AIIMS/ is changed. Root index.html, original storage and original cloud backup are preserved.

## Google Cloud configuration

Keep the existing OAuth client/project in drive-config.json. The GitHub Pages origin remains https://khanzainub.github.io. Enable Google Drive API and configure the Google Auth consent screen for:

- openid, email, profile
- https://www.googleapis.com/auth/drive.appdata
- https://www.googleapis.com/auth/drive.file
- Admin only, incrementally: https://www.googleapis.com/auth/drive.readonly

Testing audiences require adding the actual patient and admin Google accounts as test users. Admin Drive read-only access is a restricted scope: follow Google's publishing/verification requirements before broad public use. Never put passwords, client secrets or tokens into GitHub.

## Behavior

Google's userinfo endpoint verifies email and subject. khanzainub@gmail.com opens the admin dashboard automatically; other verified users open the original patient diary. Admin grants the extra Drive reading permission once via Connect shared patient folders. Patient permission and admin permission are distinct.

Each patient owns a My Drive folder named Pain Gauge · PG-<stable ID>. The app creates/reuses that folder automatically after sign-in; patient-record.json contains the full diary. The current implementation creates its own folder rather than offering arbitrary folder selection. The patient can open it from the app. The patient must opt in to give the admin reader permission. No notification email is requested. Google ACLs protect access; the JavaScript admin-email check is navigation, not the data security boundary.

All Google tokens remain in memory. This static client does not sync in the background after the page closes and reconnect is required after reload/expiry. Saved updates are debounced; the admin refreshes every 30 seconds while open. No separate database is used.

The original private app-data backup file is read-only fallback for migration. AIIMS private backup is pain-gauge-aiims-backup.json. Restore from Drive reads the private AIIMS backup (with original legacy fallback), retaining confirmation and local recovery. Restore synced diary separately loads the active shared-folder diary. Restoring an older private backup archives a different active cloud diary before replacing it. Cloud conflict detection pauses autosync instead of silently replacing an existing diary. Explicit keep-local first archives the previous cloud data. Updates check Drive versions and use ETags when returned. As with any offline/multi-device client, avoid concurrent editing from multiple devices.

AIIMS per-account local keys use Google-subject-derived patient IDs. Anonymous AIIMS draft is separate. Importing the original device diary is explicit and copy-only. Account switching does not merge different users. Local storage is not encrypted; sign out is not secure deletion.

## Required live acceptance checks

Google OAuth needs the actual user's interactive consent. Automated tests use mocked Google API responses and cannot certify Cloud project configuration or real shared-folder behavior.

1. Sign in with a non-admin test account. Verify ID, name, original skeleton, fibromyalgia, sleep/mood, female-only optional period fields, exports and reload/reconnect.
2. Save entries on several locations. Confirm the folder/file appear in that patient's Drive and private Back up now / Restore function, including legacy backup fallback.
3. Enable sharing; sign in as the admin, grant read-only permission and confirm list/details, skeleton, all location scores, diet/medicines/sleep/mood/period, and 30-second refresh.
4. Revoke sharing and refresh admin. Confirm the patient disappears. A non-admin account cannot open another patient's data through Drive APIs.
5. Test restore-before-upload on a new device, account switching on a shared device, token expiry, denied grants, network errors and another-device conflict.

No real patient credentials or records are used by the included tests.
