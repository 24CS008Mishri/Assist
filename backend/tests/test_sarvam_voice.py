import base64
import io
import wave
from unittest import TestCase
from unittest.mock import MagicMock, patch

from backend.services import live_curriculum_knowledge as knowledge
from backend.services import sarvam_voice


class SarvamTests(TestCase):
    def test_bulbul_wav_is_converted_to_echo_pcm(self):
        buffer = io.BytesIO()
        samples = b"\x00\x01" * 16
        with wave.open(buffer, "wb") as wav:
            wav.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
            wav.writeframes(samples)
        with patch.dict("os.environ", {"SARVAM_API_KEY": "fake"}), patch.object(sarvam_voice, "_client") as factory:
            client = factory.return_value
            client.post.return_value.json.return_value = {"audios": [base64.b64encode(buffer.getvalue()).decode()]}
            self.assertEqual(base64.b64decode(sarvam_voice.synthesize("नमस्ते", "hi-IN")), samples)
            self.assertEqual(client.post.call_args.kwargs["json"]["speaker"], "kavya")

    def test_saaras_uses_code_mixed_auto_detection(self):
        with patch.dict("os.environ", {"SARVAM_API_KEY": "fake"}), patch.object(sarvam_voice, "_client") as factory:
            client = factory.return_value
            client.post.return_value.json.return_value = {"transcript": "semester के credits", "language_code": "hi-IN"}
            self.assertEqual(sarvam_voice.transcribe(b"audio", "audio/wav"), ("semester के credits", "hi-IN"))
            self.assertEqual(client.post.call_args.kwargs["data"]["mode"], "codemix")

    def test_pdf_check_scopes_reads_and_does_not_reject_a_partial_syllabus(self):
        collection = MagicMock()
        first_pages = collection.find.return_value.sort.return_value.limit
        doc = {"filename": "document.pdf", "document_id": "id", "curriculum_id": "curr"}
        with patch.object(knowledge, "get_designer_collection", return_value=collection):
            first_pages.return_value = [{"text": "Page 1\nTax Invoice\nPayment reference"}]
            wrong = knowledge._document_check("designer", doc)
            first_pages.return_value = [{"text": "Semester II\nCourse credits"}]
            partial = knowledge._document_check("designer", doc)
        self.assertEqual(wrong["likely_non_curriculum_type"], "Tax Invoice")
        self.assertEqual(wrong["opening_excerpt"], "")
        self.assertIsNone(partial["likely_non_curriculum_type"])
        self.assertEqual(collection.find.call_args.args[0]["owner_id"], "designer")

    def test_wrong_pdf_warning_does_not_call_groq_or_embeddings(self):
        record = {"filename": "document.pdf", "document_id": "owned", "curriculum_id": "curr"}
        with (
            patch.object(knowledge, "_owned_documents", return_value=[record]),
            patch.object(knowledge, "_document_check", return_value={"likely_non_curriculum_type": "Tax Invoice"}),
            patch.object(knowledge, "get_live_llm") as model,
            patch.object(knowledge, "get_embeddings") as embeddings,
        ):
            response, evidence = knowledge.answer_live_question(
                "designer", "owned", "Review this PDF", "curriculum review", "en-in",
                curriculum_id="curr",
            )
        self.assertIn("wrong PDF", response)
        self.assertEqual(evidence, [])
        model.assert_not_called()
        embeddings.assert_not_called()
