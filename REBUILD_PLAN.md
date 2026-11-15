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


## Detailed original UI and route audit

### Original navigation found in web/index.html

- Global navigation: Home, All videos, creator list, New creator.
- Secondary areas: AI usage, Settings.
- Per-creator tabs: Clips, Setup, Activity.
- Settings tabs: Profile, Security, Apps.
- Admin dashboard is shown only to admin users.
- Home includes the original link/file composer and overview.
- All videos is the cross-creator library.
- Creator Clips contains live status/player, clip list and video composer.
- The original interface uses the orange (#FF8B33) and dark-brown frame palette, Geist/Inter/Archivo Black/Anton/Poppins fonts, a collapsible sidebar, responsive layout, and a no-build plain JavaScript frontend.

### Original HTTP/API surface

The baseline studio/server.py contains 80 route decorators. They cover:

- Public pages: landing, login, signup, password reset, privacy, terms, acceptable-use, robots, sitemap and health check.
- Authentication: signup, verification, resend, forgot/reset password, login/logout, current user, password change, Google sign-in.
- Video jobs: status, sync, list/detail, URL preview, create from link, upload (including chunked upload), re-render, delete, bulk delete, ZIP export and media delivery.
- Creator workflows: list/create/edit/delete creators, channel preview/avatar, start/stop live recording and clip-now.
- Account/settings: overview, settings read/write, profile photo, connected account list/removal, YouTube OAuth, Instagram connection, create/manage posts and test alerts.
- AI usage and notifications.
- Feedback and admin tools: feedback submission/review, email preview/test, admin overview, user detail/disable/delete.

The route inventory is based on the decorators in the original baseline server.py, not on a proposed redesign.

### Original AI and processing contracts

- studio/ai.py centralizes the provider adapters. The baseline supports Gemini, OpenAI, Grok/xAI, Groq, OpenRouter, Claude/Anthropic, Ollama and custom OpenAI-compatible endpoints.
- studio/brain.py defines the structured clip-selection schema and prompt logic. The returned clip metadata includes time range, score, category, hook, title, description, hashtags, highlight words and reason.
- studio/jobs.py orchestrates download/input, audio, transcript, AI selection, rendering, fair queueing and persisted job state.
- studio/live.py records live sessions into a rolling buffer, transcribes segments and asks the AI to select moments.
- studio/render.py outputs 1080x1920 at 30 fps and defines Bounce, Hype and Clean caption styles plus hook rendering.
- studio/transcribe.py uses Parakeet 0.6B through sherpa-onnx locally by default, with an optional remote ASR fallback.
- studio/config.py uses PEAKCUT_* environment names, defaults to local SQLite at data/peakcut.db, stores models under data/models, and reads Google OAuth credentials from environment variables or a configured client file.

## Audit status

- [x] Confirmed original PeakCut commit and README.
- [x] Inspected original contributor guide and project architecture.
- [x] Inspected original FastAPI server and enumerated its route decorators.
- [x] Inspected original signed-in app shell and navigation.
- [x] Inspected original landing and authentication pages.
- [x] Inspected original AI, clip-selection, jobs, live, media, transcription, rendering, creator, posting, accounts, database and auth modules.
- [x] Inspected original dependency list and disposable test runner.
- [x] Created isolated branch from the original commit and committed this rebuild plan.
- [ ] Run original tests locally with a disposable data directory and spare port.
- [ ] Verify the user's existing .env keys by checking names only (never print values).
- [ ] Compare existing local data/model paths to original config before selecting a non-destructive compatibility strategy.

No application implementation has been started. This branch currently contains the original PeakCut source plus this planning document.
