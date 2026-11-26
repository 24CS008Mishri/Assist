import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from langchain_core.documents import Document

from backend.routers import live_assistant as live
from backend.services import live_curriculum_knowledge as knowledge


class LiveAssistantTests(TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(live.router)

        @app.middleware("http")
        async def trusted_identity(request: Request, call_next):
            # Simulates the upstream identity middleware without demo headers.
            if request.headers.get("test-user"):
                request.state.authenticated_user = {
                    "id": request.headers["test-user"],
                    "role": request.headers.get("test-role", "designer"),
                }
            return await call_next(request)

        self.client = TestClient(app)
        self.secret = "fixture-signing-key-for-callbacks-only"
        config = patch.object(live, "_configuration", return_value=("key", "pal", self.secret))
        config.start()
        self.addCleanup(config.stop)

    def test_demo_header_cannot_create_paid_room(self):
        with patch.dict("os.environ", {"ENABLE_DEMO_IDENTITY_ADAPTER": "true"}):
            result = self.client.post("/api/live-assistant/sessions", json={}, headers={"X-Demo-User-Id": "u3"})
        self.assertEqual(result.status_code, 401)
        result = self.client.post("/api/live-assistant/sessions", json={}, headers={
            "test-user": "reviewer", "test-role": "reviewer",
        })
        self.assertEqual(result.status_code, 403)

    def test_owner_scope_applied_before_creating_private_room(self):
        store = MagicMock()
        store.find_one.return_value = None
        with patch.object(live, "get_designer_metadata_collection", return_value=store), patch.object(live, "_tavus_post") as provider:
            result = self.client.post("/api/live-assistant/sessions", json={"document_id": "other", "curriculum_id": "cse"},
                                      headers={"test-user": "designer-1"})
        self.assertEqual(result.status_code, 404)
        self.assertEqual(store.find_one.call_args.args[0]["owner_id"], "designer-1")
        provider.assert_not_called()

    def test_private_room_is_created_with_all_three_languages_and_no_key_in_response(self):
        sessions = MagicMock()
        sessions.update_one.return_value.matched_count = 1
        with patch.object(live, "_sessions", return_value=sessions), patch.object(
            live, "_tavus_post", return_value={
                "conversation_id": "call1", "conversation_url": "https://tavus.daily.co/call1",
                "meeting_token": "private-token",
            },
        ) as provider, patch.object(live.live_transcripts, "new_transcript", return_value="saved-history") as new_history:
            result = self.client.post("/api/live-assistant/sessions", json={"language": "gu"},
                                      headers={"test-user": "designer-1"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.headers["cache-control"], "no-store")
        self.assertEqual(result.json()["embed_url"], "https://tavus.daily.co/call1?t=private-token")
        self.assertEqual(set(result.json()), {"id", "embed_url", "expires_at", "transcript_id"})
        self.assertEqual(result.json()["transcript_id"], "saved-history")
        new_history.assert_called_once_with("designer-1", None, None, "General consultation", "gu")
        body = provider.call_args.kwargs["body"]
        self.assertTrue(body["require_auth"])
        self.assertEqual(body["custom_greeting"], live.GREETINGS["gu"])
        self.assertEqual(body["properties"]["participant_left_timeout"], 90)
        self.assertEqual(body["properties"]["languages"], ["gu", "en-in", "hi"])

    def test_replacement_room_reuses_the_same_transcript(self):
        history_id = UUID(int=1)
        sessions = MagicMock()
        sessions.update_one.return_value.matched_count = 1
        with patch.object(live, "_sessions", return_value=sessions), patch.object(live, "_tavus_post", return_value={
            "conversation_id": "replacement", "conversation_url": "https://tavus.daily.co/replacement", "meeting_token": "private-token",
        }), patch.object(live.live_transcripts, "continue_transcript", return_value=str(history_id)) as resume, patch.object(
            live.live_transcripts, "new_transcript",
        ) as new_history:
            result = self.client.post("/api/live-assistant/sessions", json={"transcript_id": str(history_id)},
                                      headers={"test-user": "designer-1"})
        self.assertEqual(result.json()["transcript_id"], str(history_id))
        resume.assert_called_once_with("designer-1", history_id, None, None)
        new_history.assert_not_called()

    def test_transcript_read_and_write_require_ownership(self):
        history_id = str(UUID(int=1))
        history = MagicMock()
        history.find_one.return_value = None
        with patch.object(live.live_transcripts, "_history", return_value=history), patch.object(
            live.live_transcripts, "_turns",
        ) as turns:
            headers = {"test-user": "unrelated-designer"}
            self.assertEqual(self.client.get(f"/api/live-assistant/transcripts/{history_id}", headers=headers).status_code, 404)
            saved = self.client.post(f"/api/live-assistant/transcripts/{history_id}/turns", headers=headers, json={
                "id": str(UUID(int=2)), "sequence": 1, "role": "user", "text": "Test question",
            })
            self.assertEqual(saved.status_code, 404)
            self.assertEqual(history.find_one.call_args.args[0], {"_id": history_id, "owner_id": "unrelated-designer"})
            turns.assert_not_called()

    def test_source_poll_detects_ended_provider_room_for_the_owner(self):
        sessions = MagicMock()
        sessions.find_one.return_value = {"sources": []}
        ended = SimpleNamespace(is_success=True, json=lambda: {"status": "ended"})
        with patch.object(live, "_sessions", return_value=sessions), patch.object(live.httpx, "get", return_value=ended) as provider:
            result = self.client.get("/api/live-assistant/sessions/call1/sources?check_provider=true",
                                     headers={"test-user": "designer-1"})
            self.assertEqual(result.status_code, 404)
            self.assertEqual(sessions.find_one.call_args.args[0]["_id"], "designer-1")
            provider.assert_called_once()

    def test_callback_rejects_invalid_hmac_and_resolves_owner_from_session(self):
        event = {
            "name": "answer_curriculum_question",
            "conversation_id": "call1",
            "tool_call_id": "turn-1",
            "arguments": json.dumps({
                "question": "Explain credit gaps", "search_query": "CSE credit gaps",
                "language": "en-in", "owner_id": "another-designer",
            }),
        }
        raw = json.dumps(event).encode()
        sig = hmac.new(self.secret.encode(), raw, hashlib.sha256).hexdigest()
        sessions = MagicMock()
        sessions.find_one.return_value = {"_id": "verified-owner", "document_id": "selected"}
        sessions.update_one.return_value.matched_count = 1
        with patch.object(live, "_sessions", return_value=sessions), patch.object(
            live, "answer_live_question", return_value=("Spoken answer", [])
        ) as answer:
            rejected = self.client.post("/api/live-assistant/tavus-tool", content=raw,
                                        headers={"X-Tavus-Signature": "0" * 64})
            self.assertEqual(rejected.status_code, 401)
            answer.assert_not_called()
            approved = self.client.post("/api/live-assistant/tavus-tool", content=raw,
                                        headers={"X-Tavus-Signature": sig})
        self.assertEqual(approved.text, "Spoken answer")
        answer.assert_called_once_with("verified-owner", "selected", "Explain credit gaps", "CSE credit gaps", "en-in",
                                       curriculum_id=None, review_curriculum=False)
        self.assertEqual(sessions.find_one.call_args.args[0]["state"], "active")

    def test_evidence_deadline_returns_spoken_fallback(self):
        raw = json.dumps({
            "name": "answer_curriculum_question", "conversation_id": "call1", "tool_call_id": "turn-2",
            "arguments": json.dumps({"question": "Review this", "search_query": "review", "language": "en-in"}),
        }).encode()
        signature = hmac.new(self.secret.encode(), raw, hashlib.sha256).hexdigest()
        from time import sleep
        with patch.object(live, "EVIDENCE_SECONDS", .01), patch.object(
            live, "_answer_tool", side_effect=lambda *_: sleep(.08),
        ):
            response = self.client.post("/api/live-assistant/tavus-tool", content=raw,
                                        headers={"X-Tavus-Signature": signature})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, live.EVIDENCE_UNAVAILABLE["en-in"])

    def test_citations_and_end_are_scoped_to_verified_owner(self):
        sessions = MagicMock()
        sessions.find_one.return_value = None
        sessions.update_one.return_value.matched_count = 0
        with patch.object(live, "_sessions", return_value=sessions), patch.object(live, "_tavus_post") as provider:
            headers = {"test-user": "unrelated-designer"}
            self.assertEqual(self.client.get("/api/live-assistant/sessions/call1/sources", headers=headers).status_code, 404)
            self.assertEqual(self.client.delete("/api/live-assistant/sessions/call1", headers=headers).status_code, 204)
        self.assertEqual(sessions.find_one.call_args.args[0]["_id"], "unrelated-designer")
        self.assertEqual(sessions.update_one.call_args.args[0]["_id"], "unrelated-designer")
        provider.assert_not_called()


class LiveKnowledgeTests(TestCase):
    def test_private_retrieval_excludes_unregistered_and_cross_owner_chunks(self):
        def document(owner, identifier):
            return Document(page_content=identifier, metadata={
                "source_type": "submitted_curriculum", "owner_id": owner,
                "document_id": identifier, "source": identifier, "page_number": 2,
            })

        store = MagicMock()
        store.similarity_search_by_vector.return_value = [
            document("me", "approved"), document("someone-else", "approved"),
            document("me", "deleted"),
        ]
        model = MagicMock()
        model.invoke.return_value = SimpleNamespace(content="Grounded reply")
        with patch.object(knowledge, "_owned_documents", return_value=[
            {"document_id": "approved", "filename": "mine.pdf", "programme": "B.Tech", "branch": "CSE"},
        ]), patch.object(knowledge, "get_embeddings"), patch.object(
            knowledge, "get_aicte_vectorstore", return_value=SimpleNamespace(similarity_search_by_vector=lambda *_a, **_k: [])
        ), patch.object(
            knowledge, "retrieve_supplement", return_value=[]
        ), patch.object(knowledge, "get_designer_vectorstore", return_value=store), patch.object(
            knowledge, "get_live_llm", return_value=model
        ), patch.object(knowledge, "_document_check", return_value=None), patch.object(
            knowledge, "curriculum_facts", return_value=({"sum_of_extracted_programme_credits": 42}, [3])
        ) as review:
            answer, sources = knowledge.answer_live_question("me", None, "What are the credit gaps?", "credits", "en-in")
        self.assertEqual(answer, "Grounded reply")
        self.assertEqual(sources, [{"title": "approved", "page": 2, "kind": "Your curriculum"},
                                   {"title": "mine.pdf", "page": 3, "kind": "Your curriculum"}])
        self.assertEqual(review.call_args.args[0], "me")
        self.assertEqual(store.similarity_search_by_vector.call_args.kwargs["pre_filter"], {
            "owner_id": {"$eq": "me"}, "document_id": {"$in": ["approved"]},
        })
        prompt = model.invoke.call_args.args[0][1].content
        self.assertIn('"sum_of_extracted_programme_credits": 42', prompt)
        self.assertNotIn("deleted", prompt)
        self.assertNotIn("someone-else", prompt)
