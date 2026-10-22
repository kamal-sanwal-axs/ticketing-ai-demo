# APEX dev API links

Gateway host: **https://api.apex-dev.axsdevops.io**

Sign in to the B2B shell: [apex-dev.axsdevops.io](https://apex-dev.axsdevops.io/login)

Use the same **Bearer JWT** in this demo (web UI or `APEX_BEARER_TOKEN` for CLI).

## OpenAPI specifications (swagger.json)

| Service | Base path | OpenAPI JSON |
|---------|-----------|--------------|
| Admin | `/admin` | [admin/swagger/v1/swagger.json](https://api.apex-dev.axsdevops.io/admin/swagger/v1/swagger.json) |
| Search | `/search` | [search/swagger/v1/swagger.json](https://api.apex-dev.axsdevops.io/search/swagger/v1/swagger.json) |
| Events | `/events` | [events/swagger/v1/swagger.json](https://api.apex-dev.axsdevops.io/events/swagger/v1/swagger.json) |
| Inventory | `/inventory` | [inventory/swagger/v1/swagger.json](https://api.apex-dev.axsdevops.io/inventory/swagger/v1/swagger.json) |
| Marketing | `/marketing` | [marketing/swagger/v1/swagger.json](https://api.apex-dev.axsdevops.io/marketing/swagger/v1/swagger.json) |

## Interactive Swagger UI

| Service | UI (may require VPN / auth) |
|---------|-----------------------------|
| Search | [search/swagger/index.html](https://api.apex-dev.axsdevops.io/search/swagger/index.html) |
| Admin, Events, Inventory, Marketing | Use OpenAPI JSON above or run the service locally with Swagger enabled |

## Endpoints used by this demo

| Demo intent | Method | URL (under gateway) |
|-------------|--------|---------------------|
| `search_events` | POST | `/search/v1/events/suggest` |
| `create_organization` | POST | `/admin/v1/organizations` |
| `create_client_venue` | POST | `/admin/v1/client-venues` |
| `get_event` | GET | `/events/{eventId}` |
| `inventory_zones` | GET | `/inventory/events/{eventId}/zones/primary` |
| `marketing_events` | GET | `/marketing/v1/events` |
| Token validation | GET | `/admin/v1/users/me/workflows` |

## Source repos (local monorepo)

If you have the APEX codebase checked out:

| API | Typical repo path |
|-----|-------------------|
| apex-admin-api | `Documents/axs/apex/apex-admin-api` |
| apex-search-api | `Documents/axs/apex/apex-search-api` |
| apex-events-api | `Documents/axs/apex/apex-events-api` (events service) |
| apex-inventory-api | `Documents/axs/apex/apex-inventory-api` |

## Environment variables

See [`.env.example`](../.env.example). Each service has `APEX_<SERVICE>_BASE_URL` and `APEX_<SERVICE>_SWAGGER_URL` overrides.

Machine-readable catalog: [`data/apex_services.json`](../data/apex_services.json)

```bash
python -m apex_rag_demo.main --list-services
```
