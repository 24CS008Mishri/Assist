import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.services.resource_discovery_service import save_designer_resource


class ResourceOwnershipTests(unittest.TestCase):
    def test_resource_cannot_be_linked_to_another_or_unknown_curriculum(self):
        metadata = Mock()
        metadata.find_one.return_value = None
        db = SimpleNamespace(users=Mock())
        resource = {
            "resource_id": "openalex:W123", "title": "A real paper", "url": "https://openalex.org/W123",
            "source": "OpenAlex", "subject": "Machine Learning", "curriculum_id": "invented-id",
        }
        with patch("backend.services.resource_discovery_service.get_designer_metadata_collection", return_value=metadata), patch(
            "backend.services.resource_discovery_service.get_workflow_database", return_value=db
        ):
            with self.assertRaisesRegex(LookupError, "not available to this Designer"):
                save_designer_resource("designer-a", resource)
        metadata.find_one.assert_called_once_with({
            "source_type": "submitted_curriculum", "owner_id": "designer-a",
            "curriculum_id": "invented-id", "status": "Active",
        }, {"_id": 1})
        db.users.find_one.assert_not_called()
        db.users.update_one.assert_not_called()

    def test_resource_can_be_saved_to_the_designers_existing_curriculum(self):
        metadata = Mock()
        metadata.find_one.return_value = {"_id": "metadata-1"}
        users = Mock()
        users.find_one.return_value = {"user_id": "designer-a", "saved_resources": []}
        db = SimpleNamespace(users=users)
        resource = {
            "resource_id": "openalex:W123", "title": "A real paper", "url": "https://openalex.org/W123",
            "source": "OpenAlex", "subject": "Machine Learning", "curriculum_id": "ml-curriculum",
        }
        with patch("backend.services.resource_discovery_service.get_designer_metadata_collection", return_value=metadata), patch(
            "backend.services.resource_discovery_service.get_workflow_database", return_value=db
        ):
            saved = save_designer_resource("designer-a", resource)
        self.assertEqual(saved["curriculum_id"], "ml-curriculum")
        users.update_one.assert_called_once()


if __name__ == "__main__":
    unittest.main()
