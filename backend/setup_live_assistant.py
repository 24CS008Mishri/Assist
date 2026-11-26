"""Provision a dedicated stock-face PAL and its signed evidence tool."""
import argparse
import os
import re
from urllib.parse import urlsplit

from dotenv import load_dotenv
import httpx

from backend.services.live_speech import avatar_gender

TOOL_NAME = "answer_curriculum_question"


def pal_prompt():
    return (
        f"Your name is Vaani (वाणी). Speak with {avatar_gender()} first-person grammar as a warm, confident curriculum consultant. "
        "Sound like an experienced academic talking to a colleague. Match the user's natural "
        "English, Hindi, Gujarati or language mix, and preserve familiar English academic terms. "
        "Keep greetings and acknowledgments brief. Respond naturally to small talk and be "
        "truthful if asked whether you are an AI. Do not reintroduce yourself. Wait through "
        "short pauses, yield to interruptions, and use the full conversation for follow-ups. "
        "Clarify only what is needed and match the user's level of familiarity. "
        "For academic or curriculum claims, call answer_curriculum_question before answering. "
        "When asked which curricula the user uploaded, immediately call answer_curriculum_question "
        "with list_uploads true and review_curriculum false. The tool reads the user's saved filenames. "
        "For 'only the names' or 'did you check?' after an upload-list request, make the same call "
        "and restate which uploads they mean in the question argument. Never only promise to check. "
        "Keep any upload-list acknowledgment to a few words and avoid asking them to wait a minute. "
        "Use review_curriculum for a review, comparison, missing courses, credits, or compliance. "
        "Restate incomplete follow-ups inside the tool arguments with context, never aloud. "
        "The search_query is English and should retain known programme, branch, year and course names. "
        "When the user switches language, switch with them. Spell out numbers naturally. "
        "When calling a tool, give a brief spoken update in the user's language about what you "
        "are checking, then deliver the result. Never say the session is almost out of time or "
        "offer a goodbye because of the room timer. The portal can continue in another room. "
        "Use plain speech. If the tool fails, briefly say you couldn't check it and offer to try again. "
        "Never invent a factual answer, approval or compliance finding."
    )


FLOW = {"turn_detection_model": "sparrow-2", "turn_taking_patience": "medium", "pal_interruptibility": "high"}


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
            "disclosure_type": "off",
            "system_prompt": pal_prompt(),
            "layers": {"conversational_flow": FLOW},
        }).json()
        pal_id = _identifier(pal.get("pal_id"))
        print(f"Created PAL {pal_id}", flush=True)
    else:
        result = client.patch(f"/v2/pals/{_identifier(pal_id)}", json=[
            {"op": "replace", "path": "/system_prompt", "value": pal_prompt()},
            {"op": "add", "path": "/disclosure_type", "value": "off"},
            {"op": "add", "path": "/layers/conversational_flow", "value": FLOW},
        ])
        if result.status_code != 304:
            result.raise_for_status()
    delivery = {"api": {
        "url": callback_origin + "/api/live-assistant/tavus-tool",
        "method": "POST",
        "auth": {"type": "hmac", "secret": secret},
        "timeout": 24,
    }}
    configuration = {
        "description": "List the user's uploaded curriculum names, answer a grounded curriculum question, or review a PDF against AICTE references.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The user's question in their language, with context from the call when needed."},
                "search_query": {"type": "string", "description": "English keywords preserving named courses, branches, editions, and other relevant terms."},
                "language": {"type": "string", "enum": ["en-in", "hi", "gu", "mixed"]},
                "review_curriculum": {"type": "boolean", "description": "True for a review, model comparison, missing courses, credits or compliance."},
                "list_uploads": {"type": "boolean", "description": "True when asked for the names or list of curricula the user uploaded, including related follow-ups. False for subjects inside a curriculum."},
            },
            "required": ["question", "search_query", "language"],
        },
        "on_call": "generate_filler",
        "on_resolve": "response_in_result",
        "delivery": delivery,
    }
    if not tool_id:
        tool = post("/v2/tools", {"name": TOOL_NAME, "origin": "llm", **configuration}).json()
        tool_id = _identifier(tool.get("tool_id"))
        print(f"Created tool {tool_id}", flush=True)
    else:
        tool_path = f"/v2/tools/{_identifier(tool_id)}"
        tool = client.get(tool_path)
        tool.raise_for_status()
        if tool.json().get("name") != TOOL_NAME:
            raise ValueError("The tool ID does not identify the Curriculum Assistant tool.")
        result = client.patch(tool_path, json=configuration)
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
