# WBS private staging source â€” NOT DEPLOYED

Repository: baysidegraphics/writersblock-app
Branch: wbs-commercial-staging-release-py313
Streamlit app: NEW, separate from writersblock-studios.streamlit.app
Entrypoint: staging_app.py
Python: 3.13
Visibility: private; restrict access to owner/testers. Do not attach the existing live app.

Original 314-file archive is unchanged. Only app.py checkout/affiliate endpoint constants differ. Added staging_app.py validates synthetic configuration before executing the existing app; .gitignore excludes private configuration. No workflow is included, so source upload adds no Actions trigger. Existing protected functions are not rewritten.

## Configuration names only â€” never commit values
WBS_STAGING_ISOLATION_CONFIRMED = synthetic-only
WBS_STAGING_SUPABASE_PROJECT_REF = owner-verified isolated project reference
SUPABASE_URL = matching isolated endpoint
SUPABASE_KEY = that project's publishable/anon key

Do not copy production Streamlit secrets. No service-role key, Stripe key, webhook secret or Affitor program key belongs here. This source check cannot independently prove a database contains no customer data: verification of the selected project is a prerequisite. Existing Supabase projects remain prohibited. No new database or resource was created.

Initially omit GEMINI_API_KEY. Genuine Quill requires separately approved test-only configuration and live-call scope; if approved later, WBS_STAGING_AI_AUTHORIZED must equal explicit-owner-approval and the isolated key is supplied only through this new app's secret store. Kokoro uses original public checksum-verified assets; no paid speech provider. Missing service configuration stops safely before running the application.

## Owner authorization needed
Authorize pushing this exact local branch to the existing writersblock-app repository, NEW staging branch only and creating ONE separate private Streamlit Community Cloud staging app, selecting branch wbs-commercial-staging-release-py313 / staging_app.py / Python 3.13. Never point production at this branch. Creation must remain within available free hosting capacity; do not upgrade or attach billing. If no suitable synthetic Supabase project exists, login/save/reload remain blocked; authorize a separate isolated service route rather than use existing production projects.

No Actions test, model call, production schema change, payment cutover, regression rerun or live deployment is included. Existing accepted evidence is reused. First actual Community Cloud build/native/voice/PDF acceptance remains outstanding. Roll back this separate staging app by deleting it or selecting the previous staging commit; production is unchanged.

This branch is based on production repository main commit 8c9957129a364a18da6f0c8b3ab4a1233e11dd9f; main itself is unchanged. Keep production bound to main/app.py. Deploy a NEW app bound to this branch/staging_app.py. Existing Streamlit repository access is expected to cover branches of this already connected repository, but current account permission, private-app slot and new-app privacy must be confirmed in Streamlit before creation. No new OAuth access is needed solely to identify another branch. The existing token is restricted to the synthetic test repository and must NOT be reused or expanded silently.
