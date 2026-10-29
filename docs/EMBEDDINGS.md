# Embeddings, similarity, and chat (Qwen 3B)

## Two different models

| Role | What you run | Typical config | Vector size |
|------|----------------|----------------|-------------|
| **Chat / classify / orchestrator** | `llama_cpp.server` + **Qwen2.5-3B-Instruct** GGUF | `CHAT_BASE_URL`, `CHAT_MODEL` | Hidden size **inside** llama (e.g. ~2048) — **not used by Chroma** |
| **RAG + routing embeddings** | sentence-transformers or `:8081` embed server | `SENTENCE_TRANSFORMERS_MODEL`, `EMBED_MODEL` | **384** (`BAAI/bge-small-en-v1.5` default) |

Upgrading chat to **qwen2.5-3b-instruct-q5_k_m.gguf** does **not** require matching embedding dimensions to the 3B model. They are **separate pipelines**:

- Embeddings → fixed-length vectors for **Chroma / cosine routing**
- Chat model → reads **text** (snippets, API JSON, prompts), not embedding tensors from the same stack

There is **no** shared “transformer layer” between MiniLM and Qwen; better chat quality comes from a larger **instruct** GGUF, not from retuning embed dim to 3B.

## Similarity metric (no extra library)

The stack already uses:

- **L2-normalized** vectors from sentence-transformers (`normalize_embeddings=True`)
- **NumPy dot product** for in-process routing (`intent_semantic`, `capability_routing`, `dynamic_tools`) → equivalent to **cosine similarity**
- **Chroma HNSW** for ANN search

Configure Chroma space via `.env`:

```bash
CHROMA_HNSW_SPACE=cosine   # recommended with normalized ST vectors (default)
# CHROMA_HNSW_SPACE=l2     # ok for normalized vectors; ranking similar to cosine
# CHROMA_HNSW_SPACE=ip     # inner product (same ranking as cosine when normalized)
```

Implementation: `apex_rag_demo/rag/chroma_metrics.py` (`chroma_collection_metadata`, `distance_to_similarity`).

**After changing `CHROMA_HNSW_SPACE`**, delete and re-sync collections (metadata is fixed at create time):

```bash
python -m apex_rag_demo.rag.sync_index
```

You do **not** need a new library for cosine/dot/L2; Chroma + NumPy cover it.

## Should you change the embedding model?

**Not required** when moving to Qwen 3B chat. Optional upgrades for **retrieval / intent routing** quality:

| Model | Dim | Notes |
|-------|-----|--------|
| **`BAAI/bge-small-en-v1.5`** | 384 | **Default**; strong retrieval vs MiniLM |
| `sentence-transformers/all-MiniLM-L6-v2` | 384 | Legacy; faster/smaller |
| `intfloat/e5-small-v2` | 384 | Prefix queries with `query: ` per model card |
| Qwen / other large embedders | 768+ | **Different dim** → set `EMBEDDING_EXPECTED_DIMENSION`, **full Chroma re-sync** |

### Reranker (cross-encoder, KB retrieve path only)

Used after bi-encoder fetch in `retrieve_bi_encoder` → `rerank_cross_encoder` (not for Chroma intent routes).

| Model | Notes |
|-------|--------|
| **`BAAI/bge-reranker-base`** | **Default**; pairs with bge-small embed |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | Legacy; faster/lighter |

Set `RAG_RERANK_MODEL` in `.env`. Download via `python -m apex_rag_demo.download_models --rerank-only`. Restart web app after change (CrossEncoder is cached in-process).

### Vector top-k (env)

| Stage | Variable | Default |
|-------|----------|---------|
| Chroma fetch (KB) | `RAG_RETRIEVE_K` | `10` |
| After rerank | `RAG_TOP_K` | `2` |
| Intent routes | `CHROMA_INTENT_ROUTE_TOP_K` | `3` |
| Agent Chroma enrich | `CHROMA_SYSTEM_ENRICH_TOP_K` | `3` |
| Session memory | `SESSION_MEMORY_TOP_K` | `3` |

`CHAT_TOP_K` is **llama.cpp sampling**, not Chroma. Full list: [CONFIG.md](./CONFIG.md).

Steps to swap embed model:

1. Set `SENTENCE_TRANSFORMERS_MODEL` (and `EMBED_MODEL` if using HTTP backend)
2. Set `EMBEDDING_EXPECTED_DIMENSION` to the new model’s output size
3. `python scripts/download_embedding_model.py` or `python -m apex_rag_demo.download_models`
4. Restart embed server (if used)
5. `python -m apex_rag_demo.rag.sync_index` (rebuild all collections)

Keep **`CHROMA_HNSW_SPACE=cosine`** with normalized embeddings.

## Switch to BGE-small-en-v1.5 (checklist)

1. **`.env`** (project root) — set or confirm:
   ```bash
   SENTENCE_TRANSFORMERS_MODEL=BAAI/bge-small-en-v1.5
   EMBED_MODEL=BAAI/bge-small-en-v1.5
   EMBEDDING_EXPECTED_DIMENSION=384
   RAG_RERANK_MODEL=BAAI/bge-reranker-base
   RAG_RETRIEVE_K=10
   RAG_TOP_K=2
   CHROMA_HNSW_SPACE=cosine
   ```
2. **Download weights** (project `.venv`):
   ```bash
   cd ticketing-ai-demo && source .venv/bin/activate
   python scripts/download_embedding_model.py
   ```
   (Downloads **bge-small** embedder + **bge-reranker-base**; or `python -m apex_rag_demo.download_models --rerank-only`.)
3. **Restart embed server** (if `RAG_EMBEDDING_BACKEND=http`):
   ```bash
   ./scripts/run-embed-server.sh
   ```
   Or set `RAG_EMBEDDING_BACKEND=sentence-transformers` and skip `:8081` (restart web app only).
4. **Chroma must be re-embedded** (vectors from MiniLM are incompatible with BGE even at same 384-d):
   ```bash
   docker compose up -d chroma
   python -m apex_rag_demo.rag.sync_index
   ```
5. **Restart web app** so config and in-process caches reload.

Chat llama (Qwen 3B on `:8000`) is unchanged.

## Chunking (KB text)

Embedding models work best on **short** chunks (~350–500 chars). See architecture notes in the repo; splitting KB/OpenAPI text before `sync_index` improves recall regardless of chat model size.

## Related

- [KG_NEO4J.md](./KG_NEO4J.md) — ontology, Neo4j sync, runtime enrichment
- [CONFIG.md](./CONFIG.md) — all `.env` variables
- [CHAT_MODEL.md](./CHAT_MODEL.md) — llama.cpp / Qwen GGUF only
- [RAG_STACK.md](./RAG_STACK.md) — ports, sync, Chroma
