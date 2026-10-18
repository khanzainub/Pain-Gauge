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


## Care-team dashboard and directory

`care-team.json` is the central registered-doctor directory (verified Google email plus display name). Maintainers add only authorized team members here through repository changes; no credentials belong in this file. `care-core.js` uses that directory for navigation. Actual data access is still enforced by Google Drive ACLs, not this public list.

A patient’s explicit team consent includes registered future doctors. On the next connected sync, the app reconciles reader permissions for all registered doctors. While the patient page is open and their token is valid, team changes are checked every minute. This cannot change Drive permissions while a patient is offline; immediate membership changes without a patient session require a separately configured Google Group or backend, neither of which is configured here. Google Group membership alone also needs a reliable folder-discovery strategy for new members.

Previous consent naming only the original doctor does not authorize a broader team. Those patients see the new team permission unchecked, with a separate option to remove earlier doctor access. No unrelated manual Drive shares are deleted by the app. Signing out does not revoke sharing.

The admin overview shows each patient’s brief summary, highest latest location rating, sleep/mood and report date, without miniature repeated charts. The patient detail has only two primary visuals: one combined pain trend with a separate line for every reported joint/location (including lower scores and zero), and a date/location heatmap (21 dates per page). Date-range and joint filters apply to both. Redundant comparison, daily bar, and small-multiple charts are removed. A trend point opens that date’s latest recorded entry for each relevant location; a heatmap rating opens the exact location/date context. The native accessible dialog shows pain notes, sleep, food/diet, mood, medicines, optional period information and other saved notes from those historical entry snapshots, never from the current profile. The complete diary and current health profile remain collapsed below the charts. Every chart uses latest entry per location/date; missing reports stay missing, not zero. Filters and selected patient are retained through refreshes, and unchanged details are not rebuilt.

Run `node --test AIIMS/tests/*.test.cjs` for the mocked OAuth/Drive, account isolation, consent, aggregation and chart tests. Real Google sign-in and multi-account sharing still require interactive acceptance testing; no browser visual QA was available in this environment.

The all-locations chart never truncates the location list or collapses it into a daily maximum. Joint labels focus an individual location; the dropdown restores All locations. Clicking a point always opens that joint/date’s historical entry. Patient overview cards and counts are hidden while viewing a patient, and Back to overview restores them. Repeated patient-detail stat cards are removed.


Patient overview summary: the newest recorded date is identified first, then the highest pain rating among all saved records on that date is shown with its location. A higher report earlier on that date is included; records from older dates are excluded. The label is “Highest pain in latest entry”. This summary is distinct from the chart’s latest rating per joint on each date. Edited-overwritten records cannot be reconstructed. Patient cards show identity, condition and pain only; sleep, mood and other context remain available inside the patient detail and entry notes. Admin labels use plain wording such as “Pain location”, “Pain by location”, “Food” and “Medicines”.


## Sign-in landing page

The AIIMS front page offers English and Hindi, the instruction “To use, continue with Google.”, and a Google-branded button with a locally embedded standard-color G mark. Diary, sharing controls, admin dashboard and app navigation are hidden in the initial HTML before JavaScript executes. Only a verified Google userinfo response unlocks the appropriate patient or care-team view. Sign-out, failed authentication and token expiry return to the closed gate. No data or backup is deleted by the gate. Google tokens remain memory-only, so reopening/reloading requires connecting again. This is an interface gate, not encryption of existing browser storage or a replacement for Drive ACLs.


## Overview and chart controls

The care-team landing view defaults to All patients. The single selection offers All patients (name order), Highest pain first (latest-day peak descending), and Latest reports first (report date descending). These reorder rather than hide shared patients.

The patient detail uses individual location checkboxes, Select all and Clear selection. Multiple locations can be shown together; selecting none shows an empty state rather than silently restoring all. Both the line chart and heatmap use that selection and the date range. Each line retains its location colour across selection changes. Entry-note clicks remain tied to the exact location and date.

The line chart has a grey grid, pain ticks at 0, 2, 4, 6, 8, 10, and the full ISO date rotated vertically at every recorded-date tick. Dates are positioned by elapsed time. The chart widens and scrolls horizontally to prevent labels from overlapping. The heatmap also has full vertical dates and a sequential light-to-dark blue score scale, with foreground contrast chosen for readable values. Missing entries remain visually distinct from zero pain.


### Patient fields and doctor display
All fields returned by the patient form's getProfile are covered by an automated doctor-profile rendering test. Food habit is an optional profile selection, independent of the existing dietPatterns checkbox categories. Existing checkbox values are retained. Each pain entry keeps its saved food habit, food categories, food notes, treatment text, medicine categories, doses taken or skipped, sleep, mood, menstrual context and pain notes. Doctor point notes use that entry snapshot only and omit empty fields. The complete diary retains recorded background details as well. Background and latest saved daily information are separate collapsed profile groups. Missing profile fields explicitly display Not recorded.
The versioned care-profile-v14.js deployment asset must match care.js; a test enforces equality.

Patient sharing UI is a single consent checkbox. Manual sync, folder and permission tools are not presented to patients. Sync is scheduled after saved changes, every 120 seconds while the signed-in patient page is visible, and when it becomes visible again. Automatic sync does not bypass conflict checks; recovery choices appear only when different diaries need a decision. Session invalidation clears the periodic timer. Versioned runtime asset is now care-profile-v15.js, tested against care.js.

Shared header now uses compact language choices and a Menu disclosure for navigation and account tools. Patient section headings are unnumbered. All current profile/routine form changes save locally and schedule sync; the existing getProfile/setProfile round trip retains medication, food categories and wellbeing until changed, including explicit clearing. JAK inhibitor remains an existing medication category. Current deployment runtime: care-profile-v16.js.

Patient form organization (v17): Profile, Food and diet, Medication, Sleep, Mood, and female-only Period information are separate collapsed cards. Each has Save and Clear all. Clearing a card changes only its current form fields and schedules normal sync; historical pain entries are never deleted. Patient ID remains read-only. Existing automatic carry-forward and automatic sync remain. Recovery decisions remain available only inside Menu under Backup recovery, with a short pause notice when needed; neither cloud nor phone records are silently discarded. Runtime: care-profile-v17.js.

Overlapping trend points: selecting any marker opens every currently selected location whose latest recorded rating has the same date and pain score. Each location retains its own saved notes. Hidden locations and other dates/scores are excluded. Keyboard activation behaves identically. Heatmap cells remain location-specific. Runtime: care-profile-v18.js.

Doctor CSV export: Download patient data is a collapsed overview panel with independent patient, profile-sex, and inclusive pain-entry date-range filters. Only currently accessible loaded patients are exported. All saved pain entries are retained, not only daily maxima or chart-visible locations. One row represents one saved pain-location entry. Profile-only patients receive a row only when no date filter is set. Missing historical values remain blank; current profile fields use separate profile_ columns. Sex filter uses current profile sex, falling back to the most recent recorded sex if absent. UTF-8 CSV includes BOM, quoted multiline notes, semicolon-separated checkbox values, and spreadsheet-formula neutralization for strings. Runtime: care-profile-v19.js; export helper: care-export.js. For statistical analysis, account for repeated joints, dates, and patients; row count is not participant count.

Cohort export (v20): choose All patients or Selected patients with individual checkboxes. Selection supports one or multiple patients, Select all, and Clear selection. Patient scope combines with current disease (including free-text other diagnosis), current-profile age bounds, sex and entry date bounds using AND. Multiple patient IDs within the scope use OR. Empty selected scope exports no records. Missing/blank age is excluded only when an age bound is set; zero age remains valid. Age limits are inclusive, validated from 0 to 120. Disease and patient selections remain stable across patient refresh; inaccessible/removed patients cannot be exported. Reset clears all filters. Runtime: care-profile-v20.js.

Matched filters (v21): export panel is below the patient overview/list. Export sex choices are the same Female/Male values as the patient form, with an additional missing-data filter rather than an invented patient sex category. Disease scope supports All diseases or individually checked diseases with Select all and Clear selection. The catalogue is read directly from the patient diagnosis dropdown and augmented only with actual saved diagnosis/free-text values; selected diseases use OR and combine with other filters using AND. All dropdown options have explicit stable values, preventing language translation from changing saved category codes. Patient-to-profile and export-column coverage checks remain active. Runtime: care-profile-v21.js.

Current-profile sex is now used exactly for sex filtering (no historical fallback), consistently with current age/disease filters. Historical patient ID/name are retained in entry_ columns alongside the current identity columns.

Sync and information update (v22): semantic backup comparison ignores property order and empty optional defaults, preventing schema-only differences from pausing sync. Active patient-record differences are reconciled after both versions are archived privately in Drive. The last successful sync snapshot is a three-way baseline: independent profile/entry edits merge and known unchanged deletions propagate. Conflicting entry revisions use saved timestamps; unknown versions remain preserved in the recovery files. A local profile change carries a profileUpdatedAt timestamp. Account and generation checks remain enforced; failed recovery uploads stop reconciliation before local replacement. Original/legacy private backups still require explicit restore. Drive requests bypass caches. Save feedback distinguishes local save from confirmed Drive upload/sharing.
About and Data/privacy are now shared role-visible sections, rather than duplicated patient-only notices. The standalone bilingual policy describes actual Google scopes, identifiable CSV exports, future care-team access, sign-out versus revocation, storage and recovery retention. Controls use a common navy/teal style. Runtime: care-profile-v22.js.

Sky-blue theme (v23): light blue surfaces, medium blue primary actions and dark blue active/selected controls are shared by both roles. Selected language, checked location controls and open menu state have clear dark/blue feedback. Body fonts, headings, labels, inputs, borders and card radius are aligned. Numbered patient headings 04 and 05 are removed; pain-axis numeric labels and data remain unchanged. White text contrast on primary/selected blue exceeds 4.5:1. Runtime: care-profile-v23.js, identical to care.js.

Mood characters (v24): six inline SVG stick figures, with short Happy, Calm, Low, Stressed, Anxious and Panic episode labels, replace the visible native mood dropdown. The original careMood select remains the storage/backup field and retains all legacy values. Selection updates aria-pressed, local saving, Drive sharing and exports through the existing field. Restore/account change and Clear all repaint selection; unmapped legacy values remain visible verbatim in the status line. Panic episode is a self-reported label, not a diagnosis. No external images or emoji fonts are used. Sleep controls remain unchanged. Runtime: care-profile-v24.js.

Independent language and quiet footer (v25): each patient's UI preference uses painGaugeAIIMS:<patientId>:language. The signed-out landing page has its own language key; a new patient can inherit that landing selection once. Existing global painGaugeLanguage values are not shared across patients. Registered doctors are always English and language buttons are hidden; forced doctor English never overwrites patient preferences. Language restoration runs on every verified account/context change. About and privacy are plain bottom links opening role-specific dialogs. Patient copy links to the full bilingual policy; doctor copy is brief. Footer identifies maintainer Zainab Khan and the explicitly supplied WhatsApp number, linking to wa.me/917455910098 without sending a message. Runtime: care-profile-v25.js.

The bottom About dropdown credits Zainab Khan and explains the pain-inspired development of the diary and care-team dashboard. Privacy opens as a separate page and describes care and research use limited to patient-shared records. Contact: WhatsApp 7455910098.
