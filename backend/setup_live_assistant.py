"""Provision a dedicated stock-face PAL and its signed evidence tool."""
import argparse
import os
import re
from urllib.parse import urlsplit

from dotenv import load_dotenv
import httpx

TOOL_NAME = "answer_curriculum_question"
PAL_PROMPT = (
    "You are the AICTE Assist AI Curriculum Assistant. Be friendly and professional. "
    "For any question about academia, AICTE, curriculum files, scores, reviewer feedback, "
    "or this portal, always call answer_curriculum_question before answering. You may "
    "greet, request clarification, and acknowledge a goodbye directly. Use this call's "
    "history to resolve follow-ups and names. Keep the question in the user's language "
    "and provide a separate English search query with programme, branch, year, names, "
    "technical terms, and acronyms when known. Do not guess missing details. "
    "Match English, Hindi, Gujarati, or the user's natural mix, switching with the user. "
    "The tool provides your spoken answer. If it fails, say you could not verify the "
    "information and offer to try again. Do not make up a factual answer."
)


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
        raise ValueError("A Tavus identifier was missing or invalid.")
    return value


def provision(client, *, callback_origin, secret, face_id=None, pal_id=None, tool_id=None):
    def post(path, payload):
        response = client.post(path, json=payload)
        response.raise_for_status()
        return response

    if not pal_id:
        pal = post("/v2/pals", {
            "pal_name": "AICTE Assist Curriculum Assistant",
            "default_face_id": _identifier(face_id),
            "pipeline_mode": "full",
            "languages": ["en-in", "hi", "gu"],
            "disclosure_type": "always",
            "system_prompt": PAL_PROMPT,
        }).json()
        pal_id = _identifier(pal.get("pal_id"))
        print(f"Created PAL {pal_id}", flush=True)
    delivery = {"api": {
        "url": callback_origin + "/api/live-assistant/tavus-tool",
        "method": "POST",
        "auth": {"type": "hmac", "secret": secret},
        "timeout": 20,
    }}
    if not tool_id:
        tool = post("/v2/tools", {
            "name": TOOL_NAME,
            "origin": "llm",
            "description": "Get the grounded spoken answer for any curriculum, guideline, Analyzer or AICTE Assist question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The user's question in their language, with context from the call when needed."},
                    "search_query": {"type": "string", "description": "English keywords preserving named courses, branches, editions, and other relevant terms."},
                    "language": {"type": "string", "enum": ["en-in", "hi", "gu", "mixed"]},
                },
                "required": ["question", "search_query", "language"],
            },
            "on_call": "generate_filler",
            "on_resolve": "response_in_result",
            "delivery": delivery,
        }).json()
        tool_id = _identifier(tool.get("tool_id"))
        print(f"Created tool {tool_id}", flush=True)
    else:
        tool_path = f"/v2/tools/{_identifier(tool_id)}"
        tool = client.get(tool_path)
        tool.raise_for_status()
        if tool.json().get("name") != TOOL_NAME:
            raise ValueError("The tool ID does not identify the Curriculum Assistant tool.")
        result = client.patch(tool_path, json={"delivery": delivery})
        result.raise_for_status()
    post(f"/v2/pals/{_identifier(pal_id)}/tools", {"tool_ids": [_identifier(tool_id)]})
    return pal_id


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True, help="Public HTTPS origin of the AICTE Assist API")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--face-id", help="Stock Tavus face ID for the new dedicated PAL")
    target.add_argument("--pal-id", help="Reuse the dedicated PAL from a previous partial setup")
    parser.add_argument("--tool-id", help="Update the existing tool to use this origin and signing secret")
    args = parser.parse_args()
    key = os.getenv("TAVUS_API_KEY", "").strip()
    secret = os.getenv("TAVUS_TOOL_SECRET", "").strip()
    origin = urlsplit(args.origin)
    if (
        origin.scheme != "https" or not origin.hostname or origin.username or origin.password
        or origin.path not in ("", "/") or origin.query or origin.fragment
    ):
        parser.error("--origin must be a public HTTPS origin without a path or credentials")
    if not key or len(secret) < 32:
        parser.error("Set TAVUS_API_KEY and a random TAVUS_TOOL_SECRET of at least 32 characters in Assist/.env")
    try:
        with httpx.Client(base_url="https://tavusapi.com", headers={"x-api-key": key}, timeout=20) as client:
            pal_id = provision(
                client, callback_origin=args.origin.rstrip("/"), secret=secret,
                face_id=args.face_id, pal_id=args.pal_id, tool_id=args.tool_id,
            )
    except httpx.HTTPStatusError as exc:
        parser.exit(1, f"Tavus returned HTTP {exc.response.status_code}. Check account permissions and configuration.\n")
    except httpx.RequestError:
        parser.exit(1, "Could not reach Tavus.\n")
    except ValueError:
        parser.exit(1, "A Tavus ID or provider response was invalid.\n")
    print(f"Set TAVUS_PAL_ID={pal_id} in Assist/.env and restart the backend.")


if __name__ == "__main__":
    main()
