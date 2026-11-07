import contextlib
import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock
import urllib.error


SCRIPT = Path(__file__).resolve().parents[1] / "cloud-location-check.py"
SPEC = importlib.util.spec_from_file_location("cloud_location_check", SCRIPT)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)

PRIVATE_MARKER = "fixture-private-value-never-output"


class Handler(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, *args):
        pass

    def send_payload(self, payload, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        Handler.requests.append((self.path, self.headers.get("Authori-zation")))
        if self.path == "/api/fitness/venues":
            self.send_payload(json.dumps({
                "status": 200,
                "msg": PRIVATE_MARKER,
                "data": [{"id": 1, "name": "fixture-venue", "latitude": "1.0",
                          "longitude": "2.0", "radius": 600,
                          "private_field": PRIVATE_MARKER}],
            }).encode())
        elif self.path == "/api/user":
            valid = self.headers.get("Authori-zation") == "Bearer fixture-token"
            self.send_payload(json.dumps({
                "status": 200 if valid else 110003,
                "msg": PRIVATE_MARKER,
                "data": {"private_profile": PRIVATE_MARKER} if valid else None,
            }).encode())
        elif self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/leak")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif self.path == "/leak":
            self.send_payload(b'{"status": 200}')
        elif self.path == "/forbidden":
            self.send_payload(b'{"status": 200}', status=403)
        elif self.path == "/malformed":
            self.send_payload(PRIVATE_MARKER.encode(), content_type="text/plain")
        elif self.path == "/oversized":
            self.send_payload(b"x" * 128)
        else:
            self.send_payload(b'{"status": 404}', status=404)


class CloudCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin_patch = mock.patch.object(
            checker, "ORIGIN", "http://127.0.0.1:%d" % cls.server.server_port
        )
        cls.proxy_patch = mock.patch.object(checker.urllib.request, "getproxies", return_value={})
        cls.origin_patch.start()
        cls.proxy_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.proxy_patch.stop()
        cls.origin_patch.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def setUp(self):
        Handler.requests = []

    def run_cli(self, argv, token=""):
        output = io.StringIO()
        with mock.patch.dict(os.environ, {"DONGXIANG_TOKEN": token}):
            with contextlib.redirect_stdout(output):
                code = checker.main(argv)
        text = output.getvalue()
        self.assertNotIn(PRIVATE_MARKER, text)
        self.assertNotIn("fixture-token", text)
        return code, json.loads(text)

    def test_default_mode_ignores_session_and_filters_public_fields(self):
        code, result = self.run_cli([], token="fixture-token")
        self.assertEqual(code, 0)
        self.assertTrue(result["public_service"]["success"])
        self.assertEqual(Handler.requests, [("/api/fitness/venues", None)])
        self.assertEqual(set(result["venues"][0]),
                         {"id", "name", "latitude", "longitude", "radius"})
        self.assertNotIn("session", result)

    def test_explicit_valid_session_reports_only_status(self):
        code, result = self.run_cli(["--check-session"], token="fixture-token")
        self.assertEqual(code, 0)
        self.assertTrue(result["session"]["success"])
        self.assertTrue(result["session"]["has_data"])
        self.assertFalse(result["session"]["session_expired"])
        self.assertIn(("/api/user", "Bearer fixture-token"), Handler.requests)

    def test_expired_session_fails_without_exposing_message(self):
        code, result = self.run_cli(["--check-session"], token="expired-fixture")
        self.assertEqual(code, 1)
        self.assertTrue(result["session"]["session_expired"])
        self.assertFalse(result["session"]["success"])

    def test_invalid_or_missing_session_is_not_sent(self):
        for token in ("", "\nfixture-token", "fixture\ttoken", "fixture\u2603token"):
            with self.subTest(token_type=repr(token)):
                Handler.requests = []
                code, result = self.run_cli(["--check-session"], token=token)
                self.assertEqual(code, 1)
                self.assertFalse(result["session"]["checked"])
                self.assertEqual(Handler.requests, [("/api/fitness/venues", None)])

    def test_redirect_never_reaches_destination_with_credentials(self):
        metadata, _ = checker.get_json("/redirect", "fixture-token")
        self.assertEqual(metadata["http_status"], 302)
        self.assertFalse(metadata["success"])
        self.assertEqual(Handler.requests, [("/redirect", "Bearer fixture-token")])

    def test_http_failure_cannot_be_overridden_by_json_status(self):
        metadata, _ = checker.get_json("/forbidden")
        self.assertEqual(metadata["http_status"], 403)
        self.assertFalse(metadata["success"])

    def test_non_json_response_is_not_printed(self):
        metadata, body = checker.get_json("/malformed")
        self.assertEqual(metadata["error"], "invalid_json")
        self.assertIsNone(body)
        self.assertNotIn(PRIVATE_MARKER, json.dumps(metadata))

    def test_response_size_limit(self):
        with mock.patch.object(checker, "MAX_RESPONSE_BYTES", 32):
            metadata, body = checker.get_json("/oversized")
        self.assertEqual(metadata["error"], "response_too_large")
        self.assertIsNone(body)

    def test_network_exception_does_not_expose_details(self):
        errors = (urllib.error.URLError(PRIVATE_MARKER),
                  TimeoutError(PRIVATE_MARKER),
                  http.client.HTTPException(PRIVATE_MARKER))
        for error in errors:
            with self.subTest(error_type=type(error).__name__):
                opener = mock.Mock()
                opener.open.side_effect = error
                with mock.patch.object(checker.urllib.request, "build_opener", return_value=opener):
                    metadata, body = checker.get_json("/api/user", "fixture-token")
                self.assertFalse(metadata["reachable"])
                self.assertEqual(metadata["error"], "connection_failed")
                self.assertNotIn(PRIVATE_MARKER, json.dumps(metadata))
                self.assertIsNone(body)

    def test_invalid_success_payload_does_not_report_success(self):
        with mock.patch.object(checker, "get_json", return_value=(
            {"reachable": True, "http_status": 200, "success": True},
            {"status": 200, "data": {"private": PRIVATE_MARKER}},
        )):
            code, result = self.run_cli([])
        self.assertEqual(code, 1)
        self.assertEqual(result["public_service"]["error"], "unexpected_venue_data")


if __name__ == "__main__":
    unittest.main()
