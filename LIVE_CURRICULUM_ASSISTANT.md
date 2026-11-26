# AI Curriculum Assistant

Open **Designer → Virtual Assistant** and select a curriculum or choose it during the call. Choose an opening language and start the consultation. The separate **AI Assistant** page is the existing text chat.

Vaani acknowledges a curriculum question aloud before checking the evidence. The backend gives the evidence task 20 seconds and returns a spoken retry message if it cannot finish. Tavus may cap an individual room according to the account plan. If a room closes while the page is open, the portal attempts to reconnect, retaining the transcript and the last spoken topic. **End call** stops the consultation and cancels automatic reconnection. A failed reconnection can be retried from the call controls.

Open **Transcript history** to reopen a past consultation. The portal saves completed text turns to the Designer database as they arrive, using the same entry across replacement rooms. Access is limited to the Designer who started the consultation. The history contains text only and begins with new consultations.

## Sarvam voice

Set a valid `SARVAM_API_KEY` in `Assist/.env`. From `Assist`, run `python -m backend.setup_sarvam_voice --create-pal` to check Bulbul and create an Echo PAL using Vaani’s existing face. Set the returned `TAVUS_SARVAM_PAL_ID` and restart FastAPI. Choose **Sarvam · Kavya** before starting a consultation. **Tavus** remains available from the same selector.

The browser detects speech pauses and sends one audio turn at a time to the authenticated backend. Saaras v4 transcribes code-mixed speech, Groq and Atlas answer, and Bulbul v3 sends audio through Tavus Echo for lip synchronization. This path sends microphone audio to Sarvam and requires browser AudioWorklet support. Languages are limited to the shared Saaras and Bulbul coverage. The portal stores transcript text.

## Setup

1. **Local Designer sign-in.** With the portal and API bound to loopback, set `ENABLE_LOCAL_DESIGNER_VIDEO_LOGIN=true` and open `http://127.0.0.1:5173/login`. Use the existing Designer email and password in the normal sign-in form. The server issues a short-lived session for the same curriculum owner ID after a successful local login. No account enrollment is needed. This switch is off by default and intended only for the loopback development portal. A shared deployment should keep it off and supply verified identity through its authentication middleware. When either authenticated mode is enabled, demo Designer headers cannot access private Designer routes. Other demo roles continue through the existing login.
2. **Tavus.** Store the API key from [PAL Maker](https://maker.tavus.io/) and a random signing secret of at least 32 characters in `Assist/.env` as `TAVUS_API_KEY` and `TAVUS_TOOL_SECRET`. The [developer tier](https://www.tavus.io/pricing) offers free development minutes. The app reuses the existing `GROQ_API_KEY` and `GROQ_MODEL`. Tavus provides speech recognition, synthesis, and stock avatars. Maya uses `TAVUS_AVATAR_GENDER=feminine` by default. Set it to `masculine` if you switch to a male avatar, then rerun PAL configuration and restart the callback service.
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
4. **Atlas.** Keep the existing AICTE and Designer MongoDB settings. With index and collection permissions, run `python -m backend.setup_live_indexes`. It copies the existing embedding definition to an isolated supplemental reference index and adds an owner-filtered index on the existing Designer vector collection. Wait for both indexes to reach `READY`. The API creates two ordinary indexes for the `live_curriculum_sessions` collection, including expiry cleanup.
5. **Archive.** Extract the supplied `SIH.rar` into a temporary directory and point the importer at the inner `SIH` folder. The default command inventories the expected 24 PDFs without connecting to MongoDB. Add `--apply` to index missing documents:
   ```powershell
   python -m backend.import_live_references "C:/path/to/extracted/SIH"
   python -m backend.import_live_references "C:/path/to/extracted/SIH" --apply
   ```
   The importer compares content hashes against the original AICTE reference records. It skips legacy filename matches and flags same-name editions with different hashes for review. The existing CSE reference already matches the supplied archive. The supplementary collection retains branch, year, document type and PDF page metadata. It includes model curricula, drafts and suggested reading. Use applicable official notices or approval handbooks when a question requires authority beyond this archive. Scanned or image-only pages require OCR before their contents can be retrieved.

The live tool refreshes the registered document scope on every question, so a new upload can enter the conversation as soon as Atlas can retrieve it. When the Designer explicitly selects a curriculum, the session stays scoped to that selection. The Virtual Assistant builds course and credit facts directly from owner-scoped indexed PDFs. The structured table parser supports B.Tech CSE. Other formats use retrieved PDF passages for comparisons. The assistant distinguishes model guidance from explicit requirements and states when evidence is insufficient.

## Live acceptance check

With a verified Designer and synthetic curriculum, start a call and ask for an AICTE model curriculum comparison and ask why parsed semester totals differ from the reference. Follow up in Hindi or Gujarati, check the displayed source pages, and upload another curriculum from a second tab during a call configured to search all owned curricula. Verify a different Designer cannot select the document or access the citation endpoint, then end the call and verify the room closes.
