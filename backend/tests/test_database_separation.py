import unittest
from unittest.mock import Mock, patch

from fastapi import Request
from fastapi.testclient import TestClient

import main
from backend.core.auth import AuthenticatedUser, require_authenticated_user
from backend.models.analyzer_schemas import StructuredCurriculum
from backend.models.analyzer_scoring_schemas import (
    AnalyzerScore,
    CheckStatus,
    CriterionScore,
    DocumentScope,
    RuleType,
    ScoringCheck,
)
from backend.services.curriculum_extraction_service import (
    CurriculumNotFoundError,
    extract_structured_curriculum,
)
from backend.services.pdf_service import PdfPage


DESIGNER_A = AuthenticatedUser(user_id="designer-a", role="designer")
DESIGNER_B = AuthenticatedUser(user_id="designer-b", role="designer")
AICTE_ADMIN = AuthenticatedUser(user_id="admin-a", role="admin")


class DatabaseConfigurationTests(unittest.TestCase):
    @patch("backend.data.database._connect")
    @patch("backend.data.database.get_settings")
    def test_clients_use_curriculum_and_aicte_connections(
        self, settings_mock, connect_mock
    ):
        from backend.data import database

        settings_mock.return_value = Mock(
            curriculum_mongodb_uri="mongodb://curriculum-store",
            aicte_mongodb_uri="mongodb://aicte-store",
        )
        connect_mock.side_effect = ["designer-client", "aicte-client"]
        database.get_designer_client.cache_clear()
        database.get_aicte_client.cache_clear()
        try:
            self.assertEqual(database.get_designer_client(), "designer-client")
            self.assertEqual(database.get_aicte_client(), "aicte-client")
            self.assertEqual(
                connect_mock.call_args_list,
                [
                    unittest.mock.call(
                        "mongodb://curriculum-store", "CURRICULUM_MONGODB_URI"
                    ),
                    unittest.mock.call("mongodb://aicte-store", "AICTE_MONGODB_URI"),
                ],
            )
        finally:
            database.get_designer_client.cache_clear()
            database.get_aicte_client.cache_clear()

    @patch("backend.services.rag_service._make_vectorstore")
    @patch("backend.services.rag_service.get_designer_collection")
    @patch("backend.services.rag_service.get_settings")
    def test_designer_vectorstore_uses_curriculum_index(
        self, settings_mock, collection_mock, make_vectorstore_mock
    ):
        from backend.services.rag_service import get_designer_vectorstore

        settings_mock.return_value = Mock(
            curriculum_mongodb_vector_index="curriculum_vector_index"
        )
        collection_mock.return_value = "curricula-collection"
        get_designer_vectorstore()
        make_vectorstore_mock.assert_called_once_with(
            "curricula-collection", "curriculum_vector_index"
        )


class OwnerFilteringCollection:
    def __init__(self, records):
        self.records = records
        self.queries = []

    def find(self, query, projection):
        self.queries.append(query)
        return [
            record
            for record in self.records
            if all(record.get(key) == value for key, value in query.items())
        ]


class EvidenceCollection:
    def __init__(self, records):
        self.records = records
        self.queries = []

    def find(self, query, projection):
        self.queries.append(query)
        cursor = Mock()
        cursor.limit.return_value = self.records
        return cursor


class PassthroughSplitter:
    def split_documents(self, documents):
        return documents


class FakeVectorStore:
    def __init__(self):
        self.documents = []
        self.retriever = None

    def add_documents(self, documents):
        self.documents.extend(documents)

    def as_retriever(self, search_kwargs):
        self.retriever = Mock()
        self.retriever.invoke.return_value = []
        return self.retriever

    def similarity_search_with_score(self, query, k):
        return []

    def max_marginal_relevance_search(
        self, query, *, k, fetch_k, lambda_mult
    ):
        return []


def curriculum_chunk(owner_id="designer-a", curriculum_id="shared-curriculum"):
    return {
        "source_type": "submitted_curriculum",
        "owner_id": owner_id,
        "curriculum_id": curriculum_id,
        "document_id": f"doc-{owner_id}",
        "programme": "B.Tech",
        "branch": "CSE",
        "page_number": 1,
        "chunk_index": 0,
        "text": "Semester I",
    }


def score_with_reference_check():
    return AnalyzerScore(
        curriculum_id="shared-curriculum",
        document_id="doc-designer-a",
        scoring_version="cse_v1",
        document_scope=DocumentScope.PARTIAL_CURRICULUM,
        scope_reason="One semester supplied",
        overall_score=100,
        evaluable_weight=10,
        overall_evaluation_coverage=10,
        low_coverage=True,
        criteria=[
            CriterionScore(
                criterion="structure",
                label="Structure",
                score=100,
                weight=10,
                obtained_marks=10,
                evaluable_maximum_marks=10,
                configured_maximum_marks=100,
                evaluation_coverage=10,
                low_coverage=True,
                checks=[
                    ScoringCheck(
                        check_id="structure.total_credits",
                        criterion="structure",
                        title="Total credits",
                        rule_type=RuleType.AICTE_MODEL_REFERENCE,
                        status=CheckStatus.PASS,
                        obtained_marks=10,
                        maximum_marks=10,
                        expected=163,
                        actual=163,
                        deduction_reason="",
                    )
                ],
            )
        ],
    )


class UploadRoutingTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def tearDown(self):
        main.app.dependency_overrides.pop(require_authenticated_user, None)

    def authenticate(self, user):
        main.app.dependency_overrides[require_authenticated_user] = lambda: user

    @patch("backend.routers.rag.process_and_store_pdf", return_value=(2, False))
    @patch(
        "backend.routers.rag.extract_pages_from_pdf",
        return_value=[PdfPage(page_number=1, text="Official reference")],
    )
    def test_aicte_reference_upload_routes_without_owner(
        self, extract_mock, process_mock
    ):
        self.authenticate(AICTE_ADMIN)
        response = self.client.post(
            "/api/documents/upload",
            data={"source_type": "aicte_reference"},
            files={"file": ("official.pdf", b"pdf", "application/pdf")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(process_mock.call_args.kwargs["source_type"], "aicte_reference")
        self.assertIsNone(process_mock.call_args.kwargs["owner_id"])
        extract_mock.assert_called_once()

    @patch("backend.routers.rag.process_and_store_pdf", return_value=(3, False))
    @patch(
        "backend.routers.rag.extract_pages_from_pdf",
        return_value=[PdfPage(page_number=1, text="Designer curriculum")],
    )
    def test_submitted_upload_routes_with_authenticated_owner(
        self, extract_mock, process_mock
    ):
        self.authenticate(DESIGNER_A)
        response = self.client.post(
            "/api/documents/upload",
            data={
                "source_type": "submitted_curriculum",
                "curriculum_id": "shared-curriculum",
            },
            files={"file": ("curriculum.pdf", b"pdf", "application/pdf")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            process_mock.call_args.kwargs["source_type"], "submitted_curriculum"
        )
        self.assertEqual(process_mock.call_args.kwargs["owner_id"], "designer-a")
        self.assertNotIn("owner_id", response.json())
        extract_mock.assert_called_once()

    @patch("backend.routers.rag.process_and_store_pdf")
    def test_role_and_authentication_checks_are_fail_closed(self, process_mock):
        unauthenticated = self.client.post(
            "/api/documents/upload",
            data={"source_type": "aicte_reference"},
            files={"file": ("official.pdf", b"pdf", "application/pdf")},
        )
        self.assertEqual(unauthenticated.status_code, 401)

        self.authenticate(DESIGNER_A)
        wrong_role = self.client.post(
            "/api/documents/upload",
            data={"source_type": "aicte_reference"},
            files={"file": ("official.pdf", b"pdf", "application/pdf")},
        )
        self.assertEqual(wrong_role.status_code, 403)
        process_mock.assert_not_called()

    @patch("backend.routers.rag.get_all_documents", return_value=[])
    def test_document_listing_selects_role_specific_scope(self, list_mock):
        self.authenticate(DESIGNER_A)
        designer_response = self.client.get("/api/documents")
        self.assertEqual(designer_response.status_code, 200)
        list_mock.assert_called_with(
            source_type="submitted_curriculum", owner_id="designer-a"
        )

        list_mock.reset_mock()
        self.authenticate(AICTE_ADMIN)
        admin_response = self.client.get("/api/documents")
        self.assertEqual(admin_response.status_code, 200)
        list_mock.assert_called_with(source_type="aicte_reference", owner_id=None)

    @patch(
        "backend.routers.rag.get_all_documents",
        side_effect=RuntimeError(
            "Unable to connect using CURRICULUM_MONGODB_URI. Verify Atlas access."
        ),
    )
    def test_document_listing_returns_actionable_database_error(self, list_mock):
        self.authenticate(DESIGNER_A)
        response = self.client.get("/api/documents")
        self.assertEqual(response.status_code, 503)
        self.assertIn("CURRICULUM_MONGODB_URI", response.json()["detail"])

    @patch(
        "backend.routers.rag.process_and_store_pdf",
        side_effect=RuntimeError(
            "Unable to connect using CURRICULUM_MONGODB_URI. Verify Atlas access."
        ),
    )
    @patch(
        "backend.routers.rag.extract_pages_from_pdf",
        return_value=[PdfPage(page_number=1, text="Designer curriculum")],
    )
    def test_upload_returns_actionable_database_error(
        self, extract_mock, process_mock
    ):
        self.authenticate(DESIGNER_A)
        response = self.client.post(
            "/api/documents/upload",
            data={
                "source_type": "submitted_curriculum",
                "curriculum_id": "shared-curriculum",
            },
            files={"file": ("curriculum.pdf", b"pdf", "application/pdf")},
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("CURRICULUM_MONGODB_URI", response.json()["detail"])

    @patch.dict("os.environ", {"ENABLE_DEMO_IDENTITY_ADAPTER": "true"})
    @patch("backend.routers.rag.get_all_documents", return_value=[])
    def test_demo_designer_header_resolves_existing_u3_context(self, list_mock):
        response = self.client.get(
            "/api/documents",
            headers={"X-Demo-User-Id": "u3"},
        )
        self.assertEqual(response.status_code, 200)
        list_mock.assert_called_once_with(
            source_type="submitted_curriculum", owner_id="u3"
        )

    @patch.dict("os.environ", {"ENABLE_DEMO_IDENTITY_ADAPTER": "true"})
    @patch("backend.routers.rag.get_all_documents", return_value=[])
    def test_demo_admin_header_resolves_existing_u1_context(self, list_mock):
        response = self.client.get(
            "/api/documents",
            headers={"X-Demo-User-Id": "u1"},
        )
        self.assertEqual(response.status_code, 200)
        list_mock.assert_called_once_with(source_type="aicte_reference", owner_id=None)


class StoreSeparationTests(unittest.TestCase):
    @patch("backend.services.document_service.get_aicte_metadata_collection")
    @patch("backend.services.document_service.get_aicte_collection")
    def test_admin_listing_includes_legacy_unclassified_aicte_uploads(
        self, vector_collection_mock, metadata_collection_mock
    ):
        from backend.services.document_service import get_all_documents

        cursor = Mock()
        cursor.sort.return_value = []
        metadata_collection_mock.return_value.find.return_value = cursor
        self.assertEqual(
            get_all_documents(source_type="aicte_reference", owner_id=None),
            [],
        )
        query = metadata_collection_mock.return_value.find.call_args.args[0]
        self.assertIn({"source_type": "aicte_reference"}, query["$or"])
        self.assertIn({"source_type": {"$exists": False}}, query["$or"])

    @patch("backend.services.document_service.get_aicte_metadata_collection")
    @patch("backend.services.document_service.get_aicte_collection")
    def test_admin_delete_removes_aicte_metadata_and_all_chunk_shapes(
        self, vector_collection_mock, metadata_collection_mock
    ):
        from backend.services.document_service import delete_document

        metadata_collection_mock.return_value.delete_one.return_value.deleted_count = 1
        deleted = delete_document(
            "official.pdf",
            source_type="aicte_reference",
            owner_id=None,
        )
        self.assertTrue(deleted)
        self.assertEqual(vector_collection_mock.return_value.delete_many.call_count, 2)
        vector_collection_mock.return_value.delete_many.assert_any_call(
            {
                "metadata.source": "official.pdf",
                "$or": [
                    {"metadata.source_type": "aicte_reference"},
                    {"metadata.source_type": {"$exists": False}},
                ],
            }
        )
        vector_collection_mock.return_value.delete_many.assert_any_call(
            {
                "source": "official.pdf",
                "$or": [
                    {"source_type": "aicte_reference"},
                    {"source_type": {"$exists": False}},
                ],
            }
        )
        metadata_collection_mock.return_value.delete_one.assert_called_once_with(
            {
                "filename": "official.pdf",
                "$or": [
                    {"source_type": "aicte_reference"},
                    {"source_type": {"$exists": False}},
                ],
            }
        )

    @patch("backend.services.document_service.get_designer_metadata_collection")
    @patch("backend.services.document_service.get_designer_collection")
    @patch("backend.services.document_service.get_aicte_metadata_collection")
    @patch("backend.services.document_service.get_aicte_collection")
    def test_metadata_registration_uses_matching_database(
        self,
        aicte_vector_mock,
        aicte_metadata_mock,
        designer_vector_mock,
        designer_metadata_mock,
    ):
        from backend.services.document_service import register_document

        register_document(
            "official.pdf",
            2,
            document_id="doc-official",
            source_type="aicte_reference",
            programme="B.Tech",
            branch="CSE",
        )
        aicte_metadata_mock.return_value.update_one.assert_called_once()
        designer_metadata_mock.return_value.update_one.assert_not_called()

        register_document(
            "curriculum.pdf",
            3,
            document_id="doc-curriculum",
            source_type="submitted_curriculum",
            programme="B.Tech",
            branch="CSE",
            curriculum_id="shared-curriculum",
            owner_id="designer-a",
        )
        designer_metadata_mock.return_value.update_one.assert_called_once()
        designer_record = designer_metadata_mock.return_value.update_one.call_args.args[1]
        self.assertEqual(designer_record["$set"]["owner_id"], "designer-a")
        self.assertEqual(designer_record["$set"]["source_type"], "submitted_curriculum")
    def test_designer_a_can_extract_own_curriculum_but_designer_b_cannot(self):
        collection = OwnerFilteringCollection([curriculum_chunk()])
        extracted = extract_structured_curriculum(
            "shared-curriculum",
            owner_id="designer-a",
            collection=collection,
        )
        self.assertEqual(extracted.document_id, "doc-designer-a")
        self.assertEqual(collection.queries[-1]["owner_id"], "designer-a")

        with self.assertRaises(CurriculumNotFoundError):
            extract_structured_curriculum(
                "shared-curriculum",
                owner_id="designer-b",
                collection=collection,
            )
        self.assertEqual(collection.queries[-1]["owner_id"], "designer-b")

    @patch("backend.services.curriculum_extraction_service.get_designer_collection")
    def test_extraction_uses_only_designer_database(self, designer_collection_mock):
        collection = OwnerFilteringCollection([curriculum_chunk()])
        designer_collection_mock.return_value = collection
        result = extract_structured_curriculum(
            "shared-curriculum", owner_id="designer-a"
        )
        self.assertEqual(result.curriculum_id, "shared-curriculum")
        designer_collection_mock.assert_called_once_with()

    @patch("backend.services.aicte_evidence_service.get_aicte_collection")
    def test_evidence_uses_only_aicte_database(self, aicte_collection_mock):
        from backend.services.aicte_evidence_service import (
            enrich_score_with_aicte_evidence,
        )

        collection = EvidenceCollection(
            [
                {
                    "text": "The model curriculum specifies 163 credits.",
                    "source": "official.pdf",
                    "source_type": "aicte_reference",
                    "programme": "B.Tech",
                    "branch": "CSE",
                    "page_number": 4,
                    "chunk_index": 2,
                }
            ]
        )
        aicte_collection_mock.return_value = collection
        enriched = enrich_score_with_aicte_evidence(score_with_reference_check())
        evidence = enriched.criteria[0].checks[0].aicte_evidence
        self.assertEqual(evidence[0].source, "official.pdf")
        aicte_collection_mock.assert_called_once_with()
        self.assertTrue(collection.queries[0].get("$or"))

    @patch("backend.services.rag_service.get_designer_vectorstore")
    @patch("backend.services.rag_service.get_aicte_vectorstore")
    def test_assistant_never_searches_designer_vectors(
        self, aicte_vector_mock, designer_vector_mock
    ):
        from backend.services.rag_service import retrieve_context

        vectorstore = FakeVectorStore()
        aicte_vector_mock.return_value = vectorstore
        self.assertEqual(retrieve_context("credit requirements"), [])
        aicte_vector_mock.assert_called_once_with()
        designer_vector_mock.assert_not_called()

    @patch("backend.services.rag_service.register_document")
    @patch("backend.services.rag_service.is_document_indexed", return_value=None)
    @patch(
        "backend.services.rag_service.get_text_splitter",
        return_value=PassthroughSplitter(),
    )
    @patch("backend.services.rag_service.get_aicte_vectorstore")
    @patch("backend.services.rag_service.get_designer_vectorstore")
    def test_submitted_ingestion_never_writes_aicte_vectors(
        self,
        designer_vector_mock,
        aicte_vector_mock,
        splitter_mock,
        indexed_mock,
        register_mock,
    ):
        from backend.services.rag_service import process_and_store_pdf

        vectorstore = FakeVectorStore()
        designer_vector_mock.return_value = vectorstore
        process_and_store_pdf(
            "Semester I",
            "curriculum.pdf",
            pages=[PdfPage(page_number=1, text="Semester I")],
            source_type="submitted_curriculum",
            curriculum_id="shared-curriculum",
            owner_id="designer-a",
        )
        designer_vector_mock.assert_called_once_with()
        aicte_vector_mock.assert_not_called()
        self.assertEqual(vectorstore.documents[0].metadata["owner_id"], "designer-a")
        self.assertEqual(vectorstore.documents[0].metadata["page_number"], 1)
        self.assertEqual(vectorstore.documents[0].metadata["chunk_index"], 0)
        self.assertEqual(register_mock.call_args.kwargs["owner_id"], "designer-a")

    @patch("backend.services.rag_service.register_document")
    @patch("backend.services.rag_service.is_document_indexed", return_value=None)
    @patch(
        "backend.services.rag_service.get_text_splitter",
        return_value=PassthroughSplitter(),
    )
    @patch("backend.services.rag_service.get_designer_vectorstore")
    @patch("backend.services.rag_service.get_aicte_vectorstore")
    def test_aicte_ingestion_never_writes_designer_vectors(
        self,
        aicte_vector_mock,
        designer_vector_mock,
        splitter_mock,
        indexed_mock,
        register_mock,
    ):
        from backend.services.rag_service import process_and_store_pdf

        vectorstore = FakeVectorStore()
        aicte_vector_mock.return_value = vectorstore
        process_and_store_pdf(
            "Official reference",
            "official.pdf",
            pages=[PdfPage(page_number=1, text="Official reference")],
            source_type="aicte_reference",
        )
        aicte_vector_mock.assert_called_once_with()
        designer_vector_mock.assert_not_called()
        self.assertNotIn("owner_id", vectorstore.documents[0].metadata)
        self.assertIsNone(register_mock.call_args.kwargs["owner_id"])


class AnalyzerAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def tearDown(self):
        main.app.dependency_overrides.pop(require_authenticated_user, None)

    @patch("backend.services.curriculum_extraction_service.get_designer_collection")
    def test_cross_designer_analyzer_request_returns_not_found(
        self, designer_collection_mock
    ):
        designer_collection_mock.return_value = OwnerFilteringCollection(
            [curriculum_chunk(owner_id="designer-a", curriculum_id="private-a")]
        )
        main.app.dependency_overrides[require_authenticated_user] = lambda: DESIGNER_B
        for operation in ("extract", "score", "analyze"):
            with self.subTest(operation=operation):
                response = self.client.post(f"/api/analyzer/{operation}/private-a")
                self.assertEqual(response.status_code, 404)
                self.assertNotIn("designer-a", response.text)

    @patch.dict("os.environ", {"ENABLE_DEMO_IDENTITY_ADAPTER": ""})
    def test_analyzer_requires_server_authenticated_identity(self):
        response = self.client.post("/api/analyzer/score/private-a")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Authentication required"})

    @patch.dict("os.environ", {"ENABLE_DEMO_IDENTITY_ADAPTER": "true"})
    @patch("backend.routers.analyzer.extract_structured_curriculum")
    def test_demo_designer_identity_is_used_by_analyzer(self, extract_mock):
        extract_mock.return_value = StructuredCurriculum(
            curriculum_id="private-a",
            document_id="doc-u3",
            programme="B.Tech",
            branch="CSE",
        )
        response = self.client.post(
            "/api/analyzer/extract/private-a",
            headers={"X-Demo-User-Id": "u3"},
        )
        self.assertEqual(response.status_code, 200)
        extract_mock.assert_called_once_with(
            curriculum_id="private-a",
            document_id=None,
            owner_id="u3",
        )

    def test_auth_adapter_reads_teammate_server_identity_contract(self):
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/analyzer/extract/private-a",
                "headers": [],
                "query_string": b"",
                "scheme": "http",
                "server": ("testserver", 80),
                "client": ("testclient", 50000),
            }
        )
        request.state.authenticated_user = {
            "user_id": "designer-a",
            "role": "designer",
        }
        current_user = require_authenticated_user(request)
        self.assertEqual(current_user, DESIGNER_A)


if __name__ == "__main__":
    unittest.main()
