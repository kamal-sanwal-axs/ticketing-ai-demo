# Upgrading the local chat model (llama.cpp)

The demo only needs an **OpenAI-compatible** server at `CHAT_BASE_URL` (default `http://localhost:8000/v1`). Any **GGUF** instruct model that runs in **llama-cpp-python** works; you do not change LangGraph or API code.

**Default for this repo:** **Qwen2.5-3B-Instruct** — `qwen2.5-3b-instruct-q5_k_m.gguf` (quality vs laptop RAM). Embeddings and Chroma are unchanged when you swap chat GGUF.

## Steps

1. **Download a GGUF** (see [Hugging Face download](#hugging-face-download-hf) below).

2. **Start the server** (use your **llama-cpp venv**, not `ticketing-ai-demo/.venv`):

```bash
python3 -m llama_cpp.server \
  --model ~/models/qwen2.5-3b-instruct-q5_k_m.gguf \
  --n_gpu_layers -1 \
  --port 8000 \
  --n_ctx 4096
```

3. **Point the app** (`.env`):

```bash
CHAT_BASE_URL=http://localhost:8000/v1
CHAT_MODEL=qwen2.5-3b-instruct-q5_k_m.gguf
```

4. **Restart** the web app (`./scripts/run-web.sh` or uvicorn).

Embeddings (Chroma / `:8081`) and Neo4j are **unchanged** — only chat on `:8000` swaps models.  
Embedding vectors are **not** tied to Qwen hidden size; see **[EMBEDDINGS.md](./EMBEDDINGS.md)**.

## Smaller models (optional)

```bash
# Example: Qwen2.5-1.5B — faster, weaker JSON routing than 3B
python3 -m llama_cpp.server \
  --model ~/models/Qwen2.5-1.5B-Instruct-GGUF/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  --n_gpu_layers -1 \
  --port 8000 \
  --n_ctx 4096
```

## Hugging Face download (`hf`)

Official Qwen GGUF repos use **`coder-3b`** in the filename, not `3b-coder`. Copy names from the [Files](https://huggingface.co) tab if a command 404s.

**Qwen2.5-3B-Instruct** (recommended for this demo):

```bash
mkdir -p ~/models/Qwen2.5-3B-Instruct-GGUF
cd ~/models/Qwen2.5-3B-Instruct-GGUF
hf download Qwen/Qwen2.5-3B-Instruct-GGUF qwen2.5-3b-instruct-q4_k_m.gguf --local-dir .
# or q5: qwen2.5-3b-instruct-q5_k_m.gguf
```

**Qwen2.5-Coder-3B-Instruct** (code-oriented; optional):

```bash
mkdir -p ~/models/Qwen2.5-Coder-3B-Instruct-GGUF
cd ~/models/Qwen2.5-Coder-3B-Instruct-GGUF
hf download Qwen/Qwen2.5-Coder-3B-Instruct-GGUF qwen2.5-coder-3b-instruct-q5_k_m.gguf --local-dir .
```

Wrong (file not found): `qwen2.5-3b-coder-instruct-q5_k_m.gguf`  
Right: **`qwen2.5-coder-3b-instruct-q5_k_m.gguf`**

List all `.gguf` names without downloading:

```bash
curl -s https://huggingface.co/api/models/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF/tree/main \
  | python3 -c "import json,sys; [print(x['path']) for x in json.load(sys.stdin) if x['path'].endswith('.gguf')]"
```

## Suggested models (local Mac)

| Model (GGUF) | Rough size (Q5) | Why |
|--------------|-----------------|-----|
| **Qwen2.5-3B-Instruct** | ~2.2 GB | **Recommended default** — orchestrator + classify JSON |
| Qwen2.5-1.5B-Instruct | ~1 GB | Faster; weaker multi-step routing |
| Qwen2.5-0.5B-Instruct | ~400 MB | Smoke tests only |
| Qwen2.5-7B-Instruct | ~4–5 GB | Best quality; tune `--n_gpu_layers` |

Use **`q4_K_M`** or **`q5_K_M`** quantizations for quality vs speed.

## If you hit OOM or slow responses

- Reduce GPU offload: `--n_gpu_layers 20` (or `0` for CPU-only).
- Use a smaller quant (`q4_0`) or smaller model (1.5B instead of 7B).
- Lower concurrent load (one chat tab).

## Context window

The app trims prompts for ~**2048** tokens by default (see `CHAT_CONTEXT_MAX_TOKENS*` in `.env.example`). If you start the server with **`--n_ctx 4096`**, you can raise:

```bash
CHAT_CONTEXT_MAX_TOKENS=3200
CHAT_CONTEXT_MAX_TOKENS_ROUTING=2800
```

If you see truncated JSON or empty classify responses, increase `n_ctx` on the server first, then these env vars.

## What improves with a bigger model

- **Classify / orchestrator / plan** JSON (fewer wrong intents, better `tool_id` picks).
- **Synthesis** prose when the formatter does not cover the answer.

**Not** improved by chat model: live API data, RAG retrieval, dynamic OpenAPI tools, UI tables — those stay deterministic.

## Verify

```bash
curl -s http://localhost:8000/v1/models | head
curl -s http://localhost:8080/api/chat -H 'Authorization: Bearer …' -H 'Content-Type: application/json' \
  -d '{"message":"hello","region":"US-West"}' | jq .answer
```

Check the llama.cpp terminal for load errors (unsupported arch, OOM).

## Related

- [CONFIG.md](./CONFIG.md) — all `CHAT_*` and sampling env vars
- [EMBEDDINGS.md](./EMBEDDINGS.md) — BGE embed + rerank on `:8081`
- [KG_NEO4J.md](./KG_NEO4J.md) — Neo4j / ontology (independent of chat GGUF)
