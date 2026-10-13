# Pain Gauge

**[Open Pain Gauge](https://khanzainub.github.io/Pain-Gauge/)**

Pain Gauge was created by [Zainab Khan](https://khanzainub.github.io/Portfolio-/). Living with long-term pain and repeatedly trying to explain it inspired her to create a practical symptom diary.

## Open for use and improvement

Everyone is welcome to use, study, adapt and improve Pain Gauge. Contributions, bug reports, accessibility improvements and translations are welcome through GitHub issues and pull requests. The code is released under the [MIT License](LICENSE). Keep the copyright and license notice when redistributing it.

## Using the app

1. Open the link in Chrome, Firefox, Safari or another modern browser and bookmark it.
2. Choose English or Hindi and save the one-time health profile; a name is not required.
3. Update medication and diet, select a pain point on the skeleton, and save its date, intensity and notes.
4. Review charts and download or share charts and CSV records.

The skeleton indicates reported pain location; it does not identify its medical cause. Pain Gauge does not diagnose conditions or replace clinical advice.

## Privacy and backups

Records remain in browser storage on your device unless you explicitly export, share or back them up. Clearing browser data, private browsing or switching devices can lose local records. Export regularly. Share health information only with people you choose.

Google Drive backup is optional. Browser backups use the app-specific private data folder and request only the `drive.appdata` scope. No access token is stored in localStorage. Connecting does not upload records; **Back up now** does. Restore asks before replacing local records. The Android bridge is retained for compatible Android wrappers. Browser backups and existing Android backups may be separate if they use different OAuth projects or storage locations.

### One-time setup for the site owner

Browser Google Drive authorization needs your own Google Cloud OAuth client; this repository currently has no configured client ID.

1. Enable **Google Drive API** in your Google Cloud project.
2. Configure the Google Auth Platform consent screen and audience. While in testing, add your test users; before general public use, configure publishing and any Google requirements.
3. Create an OAuth client with type **Web application**.
4. Add this exact **Authorized JavaScript origin**: `https://khanzainub.github.io` (no path).
5. Set `googleClientId` in [drive-config.json](drive-config.json) to the public client ID ending in `.apps.googleusercontent.com`.
6. Open the deployed page in a full browser, allow the Google sign-in popup, connect and test a backup/restore with sample records.

A client ID is public configuration. **Never put a client secret, access token, API credentials or patient records in this repository.** The GitHub connection is separate from this website's Google OAuth configuration.

## Development and deployment

The app is a standalone `index.html`; skeleton images, styles and application code are embedded. `drive-config.json` contains only the public OAuth client ID. GitHub Actions deploys the repository to GitHub Pages when `main` changes. `test-refined/index.html` is now only a compatibility redirect for existing bookmarks; the duplicate app was removed.

Preserve anatomical point IDs and stored record keys when improving the app. Test both languages, mobile and desktop layouts, exports, storage and backup/restore before submitting a pull request.

## License

Copyright © 2026 Zainab Khan. MIT License; see [LICENSE](LICENSE).

## Data continuity when updating

Keep the published origin, localStorage keys, anatomical IDs, record schema and OAuth client/project unchanged for routine updates. Never clear patient storage during startup or deployment. If a schema change is necessary, make a backward-compatible migration and keep a recoverable copy before writing. Changing the Google Cloud project can change access to the app-data backups; do not do this as a routine upgrade. Before release, verify existing sample records survive a reload and update, and that existing backups still restore.

Google permission and an active browser token are different. Tokens are temporary and intentionally held only in page memory. Reopening the page or token expiry can require connecting again; it does not erase Drive backups. Cloud backups occur only when the user chooses Back up now. Reconnect and restore an existing backup before backing up from a new or empty device, because a backup updates the saved cloud file. Keep CSV exports as independent copies. Data retention is not guaranteed; users are responsible for keeping copies, and the maintainer does not accept responsibility for data loss.
