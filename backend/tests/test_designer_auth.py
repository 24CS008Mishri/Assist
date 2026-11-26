from unittest import TestCase
from unittest.mock import MagicMock, patch

from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from backend.core import designer_sessions as identity
from backend.core.auth import require_authenticated_user
from backend.routers import demo, designer_auth
from backend.tavus_callback import app as callback_app


class VerifiedDesignerTests(TestCase):
    def test_normal_login_can_start_a_loopback_only_session_for_existing_owner(self):
        app = FastAPI()
        app.include_router(demo.router)

        @app.get("/private")
        def private(user=Depends(require_authenticated_user)):
            return {"owner": user.user_id}

        user = next(user for user in demo.USERS if user["role"] == "designer")
        payload = {"email": user["email"], "password": user["password"]}
        session = MagicMock()
        session.find_one.return_value = {"local_owner_id": user["id"]}
        with (
            patch.dict("os.environ", {
                "ENABLE_VERIFIED_DESIGNER_AUTH": "false",
                "ENABLE_LOCAL_DESIGNER_VIDEO_LOGIN": "true",
                "ENABLE_DEMO_IDENTITY_ADAPTER": "true",
            }),
            patch.object(identity, "_sessions", return_value=session),
            TestClient(app, base_url="https://localhost", client=("127.0.0.1", 50000)) as client,
        ):
            self.assertEqual(client.get("/private", headers={"X-Demo-User-Id": user["id"]}).status_code, 401)
            denied = client.post("/api/login", json=payload, headers={"Origin": "https://example.org"})
            self.assertNotIn(identity.COOKIE, denied.cookies)
            remote = client.post("/api/login", json=payload, headers={
                "Origin": "http://localhost:5173", "CF-Connecting-IP": "203.0.113.1",
            })
            self.assertNotIn(identity.COOKIE, remote.cookies)
            trusted = client.post("/api/login", json=payload, headers={"Origin": "http://localhost:5173"})
            self.assertEqual(trusted.json()["id"], user["id"])
            self.assertIn(identity.COOKIE, trusted.cookies)
            self.assertEqual(client.get("/private").json(), {"owner": user["id"]})

    def test_password_cookie_session_and_logout(self):
        app = FastAPI()
        app.include_router(designer_auth.router)

        @app.get("/private")
        def private(user=Depends(require_authenticated_user)):
            return {"owner": user.user_id}

        salt = "f0" * 16
        account = {
            "_id": "owner@example.invalid", "name": "Example", "organization": "Test", "owner_id": "bound-owner",
            "salt": salt, "password_digest": identity.password_digest("test-private-passphrase", salt),
            "revision": "current", "active": True,
        }
        directory = MagicMock()
        directory.find_one.return_value = account
        sessions = MagicMock()
        sessions.find_one.return_value = {"account": account["_id"], "revision": "current"}

        with (
            patch.dict("os.environ", {"ENABLE_VERIFIED_DESIGNER_AUTH": "true", "ENABLE_DEMO_IDENTITY_ADAPTER": "true"}),
            patch.object(identity, "accounts", return_value=directory),
            patch.object(identity, "_sessions", return_value=sessions),
            patch.object(identity, "_limit_attempts"),
            patch.object(designer_auth, "close_designer_consultation") as close,
            TestClient(app, base_url="https://testserver") as client,
        ):
            self.assertEqual(client.get("/private", headers={"X-Demo-User-Id": "u3"}).status_code, 401)
            self.assertEqual(client.post("/api/designer-auth/login", json={
                "email": account["_id"], "password": "not-the-password",
            }).status_code, 401)
            response = client.post("/api/designer-auth/login", json={
                "email": account["_id"], "password": "test-private-passphrase",
            })
            self.assertEqual(response.status_code, 200)
            cookie = response.headers.get_list("set-cookie")[-1]
            self.assertIn("HttpOnly", cookie)
            self.assertIn("Secure", cookie)
            self.assertIn("SameSite=strict", cookie)
            self.assertEqual(client.get("/private", headers={"X-Demo-User-Id": "u3"}).json(), {"owner": "bound-owner"})
            self.assertEqual(client.post("/api/designer-auth/logout").status_code, 204)
            close.assert_called_once_with("bound-owner")
            self.assertEqual(client.get("/private").status_code, 401)

    def test_public_tavus_listener_excludes_internal_routes(self):
        with TestClient(callback_app) as client:
            self.assertEqual(client.get("/docs").status_code, 404)
            self.assertEqual(client.get("/api/documents").status_code, 404)
            self.assertEqual(client.post("/api/designer-auth/login", json={}).status_code, 404)
