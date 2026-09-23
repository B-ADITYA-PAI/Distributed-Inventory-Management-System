import json
from urllib import error, request

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3:1.7b"


def main() -> None:
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": "Reply with exactly the word READY."}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "seed": 42},
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        OLLAMA_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.URLError as exc:
        raise SystemExit(
            "Cannot reach Ollama. Start Ollama and run: ollama pull qwen3:1.7b"
        ) from exc

    print("Ollama connection: OK")
    print(f"Model: {MODEL_NAME}")
    print(f"Response: {data.get('message', {}).get('content', '').strip()}")


if __name__ == "__main__":
    main()
