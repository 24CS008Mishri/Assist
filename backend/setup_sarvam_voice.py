"""Check Sarvam and create a separate Echo PAL using the existing Vaani face."""
import argparse
import os

from dotenv import load_dotenv
import httpx

from backend.services import sarvam_voice


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create-pal", action="store_true", help="Create the Echo PAL after a successful speech check")
    args = parser.parse_args()
    load_dotenv()
    key = os.getenv("TAVUS_API_KEY")
    existing = os.getenv("TAVUS_PAL_ID")
    if not os.getenv("SARVAM_API_KEY"):
        parser.exit(1, "Set SARVAM_API_KEY in Assist/.env.\n")
    try:
        sarvam_voice.synthesize("Hello, I am Vaani. How could I help you?", "en-IN")
    except httpx.HTTPStatusError as exc:
        parser.exit(1, f"Sarvam returned HTTP {exc.response.status_code}. Check the key in the Sarvam dashboard.\n")
    except (httpx.RequestError, ValueError, KeyError):
        parser.exit(1, "Could not validate Sarvam audio.\n")
    print("Sarvam Bulbul speech check passed.")
    if not args.create_pal:
        return
    if os.getenv("TAVUS_SARVAM_PAL_ID"):
        parser.exit(1, "TAVUS_SARVAM_PAL_ID is already configured.\n")
    if not key or not existing:
        parser.exit(1, "Set the existing Tavus API key and PAL ID first.\n")
    try:
        with httpx.Client(base_url="https://tavusapi.com", headers={"x-api-key": key}, timeout=12) as client:
            original = client.get(f"/v2/pals/{existing}")
            original.raise_for_status()
            pal = original.json()
            face = pal.get("default_face_id") or pal.get("default_replica_id")
            if not face:
                parser.exit(1, "Could not identify the existing PAL face.\n")
            echo = client.post("/v2/pals", json={
                "pal_name": "Vaani · Sarvam Voice", "pipeline_mode": "echo",
                "default_face_id": face, "disclosure_type": "off",
            })
            echo.raise_for_status()
            print(f"Set TAVUS_SARVAM_PAL_ID={echo.json()['pal_id']} in Assist/.env and restart FastAPI.")
    except httpx.HTTPStatusError as exc:
        parser.exit(1, f"Tavus returned HTTP {exc.response.status_code} while configuring the Echo PAL.\n")
    except (httpx.RequestError, ValueError, KeyError):
        parser.exit(1, "Could not configure the Echo PAL.\n")


if __name__ == "__main__":
    main()
