import os
from ollama import Client


def main():
    host = os.getenv(
        "OLLAMA_HOST",
        "http://host.docker.internal:11434"
    )

    model = os.getenv(
        "OLLAMA_MODEL",
        "qwen3-vl:4b"
    )

    client = Client(host=host)

    print("Connecting to Ollama...")

    response = client.chat(
        model=model,
        messages=[
            {
                "role": "user",
                "content": (
                    "Reply with exactly: "
                    "Computer-use automation ready"
                ),
            }
        ],
    )

    print("Model response:")
    print(response.message.content)


if __name__ == "__main__":
    main()