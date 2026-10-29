# APEX AI Helper UI (React 19)

Component layout follows APEX MFE conventions (`src/components`, `src/api`, `src/types`, path alias `@/`).

| Stack | Version |
|-------|---------|
| React | 19.2.x (same pin as `axs-apex-home`) |
| Build | Vite 6 |
| Language | TypeScript |

## Scripts

```bash
npm install
npm run dev      # http://localhost:5173 — API proxied to :8080
npm run build    # output: ../apex_rag_demo/web/static/dist
npm run typecheck
```

Production: from repo root run `./scripts/build-frontend.sh`, then `./scripts/run-web.sh`.

Legacy vanilla UI remains at `apex_rag_demo/web/static/index.html` if `dist/` is not built.
