# AI Curriculum Assistant

Open **Designer → AI Curriculum Assistant → Set up a video call**. Choose a curriculum or search all of your curricula, then choose English (India), Hindi, or Gujarati as the opening language. The existing text assistant is also available on the page.

## Setup

1. **Designer identity.** Set `ENABLE_VERIFIED_DESIGNER_AUTH=true` for MongoDB-backed sign-in. From `Assist`, enroll an approved Designer using the immutable owner ID already attached to their curricula:
   ```powershell
   python -m backend.enroll_designer --email designer@example.edu --owner-id EXISTING_OWNER_ID --name "Designer Name"
   ```
   The terminal prompts for a password without echo. Choose **Verified Designer sign-in** on the portal login page. Accounts, hashed password credentials, and expiring opaque sessions live in dedicated Designer database collections. Password resets require the matching email and owner ID plus `--reset`. When verified mode is enabled, demo Designer headers cannot access private Designer routes. Other demo roles still use the existing demo flow. Set `ENABLE_DEMO_IDENTITY_ADAPTER=false` on a deployment with real data. An existing verified identity middleware can also supply the role and owner ID through `request.state.authenticated_user`.
2. **Tavus.** Store the API key from [PAL Maker](https://maker.tavus.io/) and a random signing secret of at least 32 characters in `Assist/.env` as `TAVUS_API_KEY` and `TAVUS_TOOL_SECRET`. The [developer tier](https://www.tavus.io/pricing) offers free development minutes. The app reuses the existing `GROQ_API_KEY` and `GROQ_MODEL`. Tavus provides speech recognition, synthesis, and stock avatars.
3. **Public callback.** For development, start a dedicated callback listener and expose only that listener with a [Cloudflare Quick Tunnel](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/):
   ```powershell
   python -m uvicorn backend.tavus_callback:app --host 127.0.0.1 --port 8013
   cloudflared tunnel --no-autoupdate --protocol http2 --url http://127.0.0.1:8013
   ```
   Use a separate terminal for each process. To configure a new PAL, provide the public HTTPS origin and a completed [stock face](https://docs.tavus.io/sections/faces/stock-faces) ID:
   ```powershell
   python -m backend.setup_live_assistant --origin https://example.trycloudflare.com --face-id STOCK_FACE_ID
   ```
   Save the printed ID as `TAVUS_PAL_ID`, then restart FastAPI and the callback listener. For a new tunnel hostname, reuse the PAL and tool IDs to update the endpoint in place:
   ```powershell
   python -m backend.setup_live_assistant --origin https://example.trycloudflare.com --pal-id PAL_ID --tool-id TOOL_ID
   ```
   A Quick Tunnel is temporary. Use a stable HTTPS origin for a shared deployment. Pass the original request body and `X-Tavus-Signature` through the proxy. Avoid logging room-token URLs or callback bodies. Verify Tavus retention settings before using real curriculum information. Groq receives the spoken question and supporting evidence. Tavus receives the answer to speak.
4. **Atlas.** Keep the existing AICTE and Designer MongoDB settings. With index and collection permissions, run `python -m backend.setup_live_indexes`. It copies the existing embedding definition to an isolated supplemental reference index and adds an owner-filtered index on the existing Designer vector collection. Wait for both indexes to reach `READY`. The API creates two ordinary indexes for the `live_curriculum_sessions` collection, including expiry cleanup. The Analyzer stores a compact report summary in the existing owner-scoped metadata record once the PAL is configured. Run the Analyzer for reports created before configuration.
5. **Archive.** Extract the supplied `SIH.rar` into a temporary directory and point the importer at the inner `SIH` folder. The default command inventories the expected 24 PDFs without connecting to MongoDB. Add `--apply` to index missing documents:
   ```powershell
   python -m backend.import_live_references "C:/path/to/extracted/SIH"
   python -m backend.import_live_references "C:/path/to/extracted/SIH" --apply
   ```
   The importer compares content hashes against the original AICTE reference records. It skips legacy filename matches and flags same-name editions with different hashes for review. The existing CSE reference already matches the supplied archive. The supplementary collection retains branch, year, document type and PDF page metadata. It includes model curricula, drafts and suggested reading. Use applicable official notices or approval handbooks when a question requires authority beyond this archive. Scanned or image-only pages require OCR before their contents can be retrieved.

The live tool refreshes the registered document scope on every question, so a new upload can enter the conversation as soon as Atlas can retrieve it. When the Designer explicitly selects a curriculum, the session stays scoped to that selection. The Reviewer screen currently uses demo data, so the live assistant reports Reviewer feedback as unavailable.

## Live acceptance check

With a verified Designer and synthetic curriculum, start a call and ask for an AICTE model curriculum comparison and an explanation of a saved Analyzer finding. Follow up in Hindi or Gujarati, check the displayed source pages, and upload another curriculum from a second tab during a call configured to search all owned curricula. Verify a different Designer cannot select the document or access the citation endpoint, then end the call and verify the room closes.
