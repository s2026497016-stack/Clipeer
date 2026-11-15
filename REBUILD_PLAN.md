# PeakCut Fresh Rebuild Plan

## Purpose

Rebuild the application from the original PeakCut source and interface, on an isolated branch. Do not start from the newer Clipeer UI or copy later changes by default. The original PeakCut commit is the source of truth for the first working version.

## Source baseline

- Repository: s2026497016-stack/Clipeer
- Baseline commit: 795a4e385380d0735fa302995abb18f0a3a17d73
- Branch: rebuild/peakcut-original
- Baseline README title: PeakCut
- Baseline stack: Python 3.10+, FastAPI, plain HTML/CSS/JavaScript, SQLAlchemy, SQLite by default, FFmpeg, yt-dlp, sherpa-onnx / Parakeet.
- Original UI files include web/landing.html, web/auth.html, web/index.html, and related static assets.
- No frontend build step is required by the original architecture.

## Preservation rules

1. Never force-push or rewrite main.
2. Never delete, move, overwrite, or reset the user's existing data directory, SQLite database, .env, Google OAuth credentials, API keys, downloaded Parakeet model, fonts, or backups.
3. Do not commit secrets, .env, personal paths, tokens, or user data.
4. Use a separate temporary data directory and spare port for tests and risky manual checks.
5. Before any schema migration or data-format conversion, make a verified backup and test against a copy.
6. Keep the user's existing local project and current backup branches intact.

## Original architecture inspected

- studio/server.py: FastAPI app, HTTP routes, session gate, static page delivery, OAuth/API endpoints.
- studio/config.py: environment configuration, .env loading, data/model/database paths, AI and Google credentials, host/port and processing limits.
- studio/ai.py: provider adapter layer (Gemini and other providers); one interface for AI services.
- studio/brain.py: transcript-to-clip selection and AI prompts/schema, hooks, titles, descriptions and metadata.
- studio/jobs.py: video-processing pipeline and fair job queue.
- studio/live.py: live stream recording, rolling buffer, transcript and AI clip selection.
- studio/media.py: video download, probing, audio extraction and loudness analysis.
- studio/transcribe.py: Parakeet / sherpa-onnx speech-to-text, with optional remote ASR fallback.
- studio/render.py: 9:16 output, caption rendering, hooks and visual styles.
- studio/creators.py and studio/profiles.py: creator workspaces and channel profiles.
- studio/posting.py and studio/accounts.py: connected social accounts, post queue and publishing.
- studio/auth.py, studio/db.py, studio/admin.py: authentication, database tables and administration.
- web/index.html: signed-in application UI.
- web/landing.html and web/auth.html: public landing and authentication pages.
- tests/run.py: disposable test server and isolated test data. Individual tests include permissions, abuse/limits, queue, delete, uploads and AI service behavior.

## Functional baseline (restore in this order)

### Phase 0 — Audit and baseline verification
- Inspect the full baseline tree, routes, frontend navigation, configuration, dependency versions, assets/fonts and tests.
- Record exact baseline files and checksums/commit references.
- Identify which existing local files/data are user-owned and which are tracked source.
- Run the original tests using temporary data and a spare port.
- No product feature implementation in this phase.

### Phase 1 — Original PeakCut experience
- Restore the original PeakCut public landing page, sign-in/sign-up pages and signed-in app shell.
- Preserve the original orange/dark visual system, navigation, spacing, responsive behavior and page interactions.
- Verify every visible navigation item maps to a working original route/view.
- No redesign or new features until visual parity is confirmed.

### Phase 2 — Core video-to-clip pipeline
- Accept supported YouTube/Twitch/Kick URLs and local uploads.
- Download/probe media, extract audio, transcribe, identify clip ranges, render 9:16 clips and produce word-synced captions.
- Verify Bounce, Hype and Clean caption styles and hook/title/description generation.
- Verify queue status, retries, errors and clip downloads.

### Phase 3 — AI and speech
- Gemini is the preferred configured AI provider; retain provider abstraction.
- Preserve existing key/model configuration without exposing credentials.
- Verify no-key loudness fallback.
- Verify Parakeet local ASR and YouTube transcript behavior.
- Keep AI prompts and transcript handling safe against untrusted video content.

### Phase 4 — Creator and live workflows
- Creator workspaces, channel/profile lookup, per-creator settings and activity logs.
- Live recording with rolling buffer, transcription and AI selection.
- Test offline/unsupported stream handling and reconnection safely.

### Phase 5 — Accounts and publishing
- Email/Google sign-in and admin controls.
- YouTube and Instagram connection/posting as supported by the original baseline.
- Posting queue, spacing, daily caps and status reporting.
- Do not assume later TikTok or advanced monitoring features belong in the baseline.

### Phase 6 — Quality and release
- Run tests with disposable data.
- Perform manual smoke tests for landing, auth, upload, URL input, transcription, clip generation, rendering, downloads, creator workspaces and live workflow.
- Confirm local setup uses the intended existing .env without printing secrets.
- Confirm all user data and backups remain untouched.
- Only after acceptance, open a pull request from rebuild/peakcut-original. Do not merge automatically.

## Explicitly out of scope for the first baseline

- Newer Clipeer visual redesign.
- PR #2 metadata-review workflow.
- Later experimental gameplay/vision detection.
- Railway/Docker deployment changes unless required to run the original baseline.
- TikTok integration and other post-baseline features.
- Any new feature not present in the original PeakCut baseline.

## Acceptance criteria

- Branch starts at the exact original PeakCut baseline commit.
- Original PeakCut landing, auth and app shell are restored.
- Core original workflows pass tests and manual smoke tests.
- Gemini and Parakeet work with the user's existing local configuration, without disclosing or replacing secrets.
- Existing database, .env, model files and backups are preserved.
- No changes are made to main until the user reviews and approves the rebuild.
