from __future__ import annotations

from openai import OpenAI

from apex_rag_demo.config import CHAT_BASE_URL, CHAT_MODEL, EMBED_BASE_URL, EMBED_MODEL


def chat_client() -> OpenAI:
    return OpenAI(base_url=CHAT_BASE_URL, api_key="local")


def embed_client() -> OpenAI:
    return OpenAI(base_url=EMBED_BASE_URL, api_key="local")


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    client = embed_client()
    response = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [item.embedding for item in response.data]


def chat_completion(system: str, user: str, temperature: float = 0.2) -> str:
    client = chat_client()
    kwargs: dict = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }
    if CHAT_MODEL:
        kwargs["model"] = CHAT_MODEL
    response = client.chat.completions.create(**kwargs)
    return (response.choices[0].message.content or "").strip()
