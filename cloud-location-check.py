#!/usr/bin/env python3
"""Read-only service checks for Codex Cloud; never submit attendance."""

import argparse
import http.client
import json
import os
import urllib.error
import urllib.request


ORIGIN = "https://www.dongxiangsz.cn"
MAX_RESPONSE_BYTES = 2_000_000
TARGET = {
    "latitude": 36.1704810,
    "longitude": 116.7546120,
    "coordinate_system": "WGS84",
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward a session credential to a redirected destination.
        return None


def get_json(path, token=None):
    headers = {"Content-Type": "application/json", "Form-type": "routine"}
    if token is not None:
        headers["Authori-zation"] = (
            token if token.startswith("Bearer ") else "Bearer " + token
        )
    try:
        request = urllib.request.Request(
            ORIGIN + path, headers=headers, method="GET"
        )
        opener = urllib.request.build_opener(NoRedirect())
        try:
            response = opener.open(request, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            http_status = response.getcode()
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException):
        return {
            "reachable": False,
            "error": "connection_failed",
            "hint": "Check the cloud network policy, HTTPS proxy, and service availability.",
        }, None

    metadata = {"reachable": True, "http_status": http_status, "success": False}
    if len(payload) > MAX_RESPONSE_BYTES:
        return dict(metadata, error="response_too_large"), None
    try:
        body = json.loads(payload.decode("utf-8-sig"))
    except (ValueError, UnicodeError):
        return dict(metadata, error="invalid_json"), None
    if not isinstance(body, dict) or type(body.get("status")) is not int:
        return dict(metadata, error="unexpected_response_shape"), None

    metadata["service_status"] = body["status"]
    metadata["success"] = http_status == 200 and body["status"] == 200
    return metadata, body


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read-only connectivity and optional session checks. No attendance submission."
    )
    parser.add_argument(
        "--check-session",
        action="store_true",
        help="Also GET /api/user using DONGXIANG_TOKEN; never print account data.",
    )
    args = parser.parse_args(argv)
    result = {"mode": "read_only", "reference_location_wgs84": TARGET}
    public_status, public_body = get_json("/api/fitness/venues")
    result["public_service"] = public_status
    if public_status.get("success"):
        venues = public_body.get("data")
        if isinstance(venues, list) and all(isinstance(v, dict) for v in venues):
            result["venues"] = [
                {key: venue.get(key) for key in
                 ("id", "name", "latitude", "longitude", "radius")}
                for venue in venues
            ]
        else:
            public_status.update(success=False, error="unexpected_venue_data")

    if args.check_session:
        raw_token = os.environ.get("DONGXIANG_TOKEN", "")
        token = raw_token.strip()
        if not token or any(ord(char) < 32 or ord(char) > 126 for char in raw_token):
            result["session"] = {
                "checked": False,
                "reason": "missing_or_invalid_DONGXIANG_TOKEN",
            }
        else:
            session_status, session_body = get_json("/api/user", token)
            session_status["checked"] = True
            if session_body is not None:
                session_status["has_data"] = session_body.get("data") is not None
                session_status["session_expired"] = session_body["status"] in (
                    110002, 110003, 110004
                )
            # Do not copy profile fields or service messages into the output.
            result["session"] = session_status

    print(json.dumps(result, ensure_ascii=False, indent=2))
    public_ok = public_status.get("success", False)
    session_ok = not args.check_session or result["session"].get("success", False)
    return 0 if public_ok and session_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
