# Temporary in-memory WBS staging preview

Repository: baysidegraphics/writersblock-app
Branch: wbs-commercial-staging-release-py313
Entrypoint: staging_app.py
Python: 3.13

This staging-only entrypoint runs the existing WBS Test synthetic fixture adapter and the actual modular stage workflows. No Supabase configuration is required or consumed. Do not supply production secrets, payment keys, customer records or manuscripts. Supabase and Gemini live client creation are blocked during the preview. AI generation and Quill replies are explicitly simulated; no real AI/service acceptance is claimed. Quill controls and original Kokoro speech code are unchanged. Original Kokoro assets may download from their checksum-verified public source on first voice use; no paid speech service is used.

Each browser session has an independent in-memory database and independent per-format synthetic V7 workspaces. Save checkpoint preserves the active revision; explicit revision creation/reloading uses the existing real save/load handlers. Format switching retains workspaces within that session. Nothing is durable: data resets on server restart, session loss or reconnect. Never enter valuable author content. The page displays this warning prominently.

The copied fixture helpers omit unittest classes and do not execute regression suites. Only the staging entrypoint, fixture adaptation and this staging guide change. app.py, core, formats, engine, Quill, Kokoro and protected Short Story modules are unchanged by this correction. Existing live checkout/affiliate disabling remains.

Deployment preparation is local until explicitly published. Push only this staging branch; never main. Because the separate staging app is already online and watches this branch, pushing the correction will automatically rebuild that STAGING app. No production deployment is authorized. The previous staging commit can be restored on this branch if required; do not modify production main or app settings.
