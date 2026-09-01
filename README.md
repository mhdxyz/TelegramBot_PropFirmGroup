# Telegram AI Bot

A Telegram bot that receives updates via **webhook** (not polling), with an
**optional, pluggable AI feature** backed by Google Gemini. The AI feature
can be fully disabled via configuration — no Gemini key, client, or handler
is involved when it's off — and the normal bot keeps working either way.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# edit .env: set TELEGRAM_BOT_TOKEN and WEBHOOK_SECRET at minimum.
# To use the AI feature, also set AI_ENABLED=true and GEMINI_API_KEY.

python -m app.main
# or: uvicorn app.main:create_asgi_app --factory --host 0.0.0.0 --port 8000
```

Run tests:

```bash
pytest
```

## Architecture

```
Telegram
   │ HTTPS webhook
   ▼
app/webhook/routes.py        verifies secret token + payload size,
                              parses the update, hands off, returns fast
   │
   ▼
telegram.ext.Application      python-telegram-bot's own dispatcher
   │
   ├── app/bot/handlers/       normal bot: /start, /help, and (only when
   │                           AI is off) a fallback text handler
   │
   └── app/features/ai/        AI feature: handler → chat_service →
                                AIService → Gemini provider
                                (only wired up when AI_ENABLED=true)
```

`app/main.py` is the composition root — the only file that constructs
concrete classes and wires them together. Everything else receives its
dependencies through its constructor, which is what makes each layer
testable with fakes instead of a real Telegram/Gemini/HTTP/database
connection (see `tests/`).

### Why webhook, not polling

`app/webhook/app.py` builds a FastAPI app whose lifespan owns the async
startup/shutdown sequence: connect the database, `initialize()`/`start()`
the `telegram.ext.Application`, and — if `WEBHOOK_URL` is set — register
the webhook with Telegram automatically. The webhook route itself
(`app/webhook/routes.py`) does nothing except validate the request and
hand it to `Application.process_update()`; no AI logic, no database logic,
no business rules live in the HTTP layer. Deploy it behind any ASGI server
(uvicorn, hypercorn, gunicorn+uvicorn workers) on any HTTPS-capable host —
nothing in the app assumes a specific provider.

One implementation detail worth calling out: `aiosqlite` connections are
bound to the event loop they were opened on, so the database is connected
*inside* the FastAPI lifespan (the loop the ASGI server actually runs),
not eagerly at import/wiring time in `main.py`. `SQLiteUserRepository`
holds a reference to the `Database` wrapper rather than a raw connection so
it can be constructed before that connection exists.

### Why AI is a separable, optional feature

Everything AI-specific lives in `app/features/ai/`: the Telegram handler,
`ChatService` (orchestration), `AIService` (provider selection + fallback),
the `AIProvider` protocol, and the Gemini implementation. Nothing in
`app/bot/handlers/`, `app/core/`, `app/security/`, or `app/repositories/`
imports anything from `app/features/ai/`.

`AI_ENABLED` is read once, in `main.py::_build_telegram_application`:

```python
if config.ai.enabled:
    providers = build_all_available_providers(config.ai)
    ...
    application.add_handler(MessageHandler(..., ai_message_handler))
else:
    application.add_handler(MessageHandler(..., ai_disabled_handler))
```

When `AI_ENABLED=false`: `GEMINI_API_KEY` isn't required (config validation
doesn't even ask for it), no Gemini provider is constructed, no AI handler
is registered, and `dependencies.get(bot_data).ai` is `None`. The normal
bot (`/start`, `/help`, and a plain "AI is off" reply to text) runs
unaffected. Flip the flag and restart — no code changes needed.

### AI provider abstraction

`AIProvider` (`features/ai/provider.py`) is a `Protocol` with one method,
`generate_reply`. Only Gemini is implemented today, per project scope, but
`AIService` and `ChatService` depend on the protocol, not on
`google-generativeai` directly — adding a second provider later means one
new file implementing the protocol plus one branch in
`features/ai/factory.py`. `AIService` already supports trying a fallback
provider if the preferred one fails; with a single configured provider it
behaves like a direct call.

### Error handling

Unchanged from the original design: every application error derives from
`AppError` (`core/exceptions.py`) and carries a `user_message` safe to
show in Telegram, separate from the technical detail that gets logged.
Gemini SDK exceptions are caught and translated at the provider boundary
(`features/ai/gemini_provider.py`); nothing above it sees a raw SDK
exception. `bot/middleware/error_boundary.py` turns any uncaught `AppError`
(or anything else) into a safe reply plus a log entry. At the HTTP layer,
`webhook/app.py` has a catch-all exception handler as a last-resort safety
net so no unexpected exception can leak a stack trace to a caller.

### Security

- **Webhook**: `WEBHOOK_SECRET` is checked against Telegram's
  `X-Telegram-Bot-Api-Secret-Token` header using `hmac.compare_digest`
  (Telegram's own mechanism, not a bespoke one). Payload size is capped by
  `WEBHOOK_MAX_PAYLOAD_BYTES`. Malformed JSON and malformed update shapes
  return 400 without detail; wrong method returns 405 (FastAPI default);
  unauthorized requests return 401.
- **Authorization**: `security/authorization.py` — allow-list and
  admin-list, both optional. Empty allow-list means "everyone allowed".
- **Rate limiting**: `security/rate_limiter.py` — in-memory sliding
  window, per Telegram user ID.
- **Message length**: validated in `ChatService` before reaching Gemini.
- No secret is hard-coded; everything sensitive comes from environment
  variables, validated at startup (`core/config.py`).

## Extending the bot

**Add an AI provider:** implement the `AIProvider` protocol in a new
`app/features/ai/your_provider.py`, add it to `AIProviderName` in
`core/config.py`, and add a branch in `features/ai/factory.py::build_provider`.

**Add a normal-bot command:** write a handler in `app/bot/handlers/` and
register it in `main.py::_build_telegram_application`. It should have no
reason to import anything from `app/features/ai/`.

**Add a role/permission:** extend `security/authorization.py`; existing
call sites don't need to change.

**Swap SQLite for Postgres:** implement `UserRepository`
(`repositories/user_repository.py`) against Postgres and construct it
instead of `SQLiteUserRepository` in `main.py`. `ChatService` depends on
the `UserRepository` protocol, not SQLite, so it doesn't change.

**Change deployment target:** `create_asgi_app()` (or `uvicorn
app.main:create_asgi_app --factory`) is the entire HTTP contract. Point
whatever hosting platform you use at that ASGI callable; nothing in
`app/` assumes Cloud Run, a VPS, or any other specific environment.

## Environment variables

See `.env.example` for the full list with defaults. Required in all cases:
`TELEGRAM_BOT_TOKEN`, `WEBHOOK_SECRET`. Required only when `AI_ENABLED=true`:
`GEMINI_API_KEY`.

## Production webhook setup

1. Deploy the app behind HTTPS (a load balancer, Cloud Run, nginx+VPS, etc.).
2. Set `WEBHOOK_URL` to the public HTTPS base URL, and `WEBHOOK_SECRET` to a
   random value.
3. On startup, the app calls `bot.set_webhook(url, secret_token=...)`
   automatically. If you'd rather manage that outside the app (e.g. as a
   deploy-time step), leave `WEBHOOK_URL` unset and call Telegram's
   `setWebhook` API yourself with the same path and secret.

## Testing strategy

- `tests/unit/` — pure logic: `ChatService`, `AIService` (including
  provider fallback with generic provider identifiers, not just Gemini),
  the rate limiter, authorization, and webhook secret-token verification.
  No network calls, no real Telegram/Gemini/HTTP/database involved.
- `tests/integration/`
  - `test_webhook.py` — the HTTP endpoint over FastAPI's `TestClient`
    against a fake `Application` double: valid update, missing/wrong
    secret, malformed JSON, oversized payload, wrong HTTP method, health
    check.
  - `test_ai_toggle.py` — proves `AI_ENABLED` actually changes which
    handler gets registered and whether AI dependencies get built, for
    both states, plus the fail-fast case (`AI_ENABLED=true` without
    credentials).
- Failure paths are tested explicitly, not just the happy path.
