from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai


ROOT_DIR = Path(__file__).resolve().parents[1]
KNOWLEDGE_FILE = ROOT_DIR / "knowledge" / "propfirmmeeting.md"

load_dotenv(ROOT_DIR / ".env")


def main() -> None:
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    if not KNOWLEDGE_FILE.exists():
        raise FileNotFoundError(
            f"Knowledge file not found: {KNOWLEDGE_FILE}"
        )

    client = genai.Client(api_key=api_key)

    print("Creating Gemini File Search Store...")

    store = client.file_search_stores.create(
        config={
            "display_name": "PropFirmMeeting Knowledge Base",
            "embedding_model": "models/gemini-embedding-2",
        }
    )

    print(f"Store created: {store.name}")
    print(f"Uploading: {KNOWLEDGE_FILE}")

    operation = client.file_search_stores.upload_to_file_search_store(
        file=str(KNOWLEDGE_FILE),
        file_search_store_name=store.name,
        config={
            "display_name": "PropFirmMeeting Knowledge",
        },
    )

    print("Indexing knowledge...")

    while not operation.done:
        time.sleep(3)
        operation = client.operations.get(operation)

    print()
    print("Knowledge indexing completed.")
    print()
    print(f"GEMINI_FILE_SEARCH_STORE_NAME={store.name}")
    print()

    print(
        "Add the value above to your .env file."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise