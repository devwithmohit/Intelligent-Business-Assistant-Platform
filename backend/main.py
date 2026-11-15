import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import agents as agents_router
from .api.v1 import analytics as analytics_router
from .api.v1 import auth as auth_router
from .api.v1 import chat as chat_router
from .api.v1 import integrations as integrations_router
from .api.v1 import tasks as tasks_router
from .api.v1 import users as users_router
from .api.v1 import workflows as workflows_router
from .api import websocket as websocket_router
from .core.config import settings, validate_security_settings
from .core.logging_config import configure_logging
from .middleware.logging_middleware import LoggingMiddleware
from .middleware.rate_limit import init_rate_limiter
from .middleware.security_headers import SecurityHeadersMiddleware

configure_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Validate security settings on import / module load
validate_security_settings(settings)

app = FastAPI(title=getattr(settings, "APP_NAME", "IBA Backend"), version="0.1.0")

# Security headers middleware
app.add_middleware(
    SecurityHeadersMiddleware,
    enable_hsts=settings.ENV.lower() in ("production", "prod", "staging"),
)

# CORS Hardening
raw_origins = getattr(settings, "ALLOWED_ORIGINS", [])
explicit_origins = [origin for origin in raw_origins if origin != "*"]
if not explicit_origins:
    explicit_origins = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]
if "*" in raw_origins:
    logger.warning(
        "Wildcard origin '*' cannot be combined with allow_credentials=True. "
        "Using explicit allowed origins: %s",
        explicit_origins,
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=explicit_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# Logging middleware (structured request logging)
app.add_middleware(LoggingMiddleware)


def _include_router(module) -> None:
    router = getattr(module, "router", None)
    if router is None:
        logger.warning(
            "router module has no router; skipping registration",
            extra={"module": getattr(module, "__name__", repr(module))},
        )
        return
    app.include_router(router)


def _build_default_rate_limit(requests: int, window_seconds: int) -> str:
    if window_seconds <= 1:
        return f"{requests}/second"
    if window_seconds == 60:
        return f"{requests}/minute"
    if window_seconds == 3600:
        return f"{requests}/hour"
    return f"{requests}/{window_seconds} seconds"


for router_module in (
    auth_router,
    users_router,
    agents_router,
    analytics_router,
    chat_router,
    integrations_router,
    tasks_router,
    workflows_router,
    websocket_router,
):
    _include_router(router_module)


@app.on_event("startup")
async def on_startup():
    # Fail fast and loudly if default/insecure environment secrets are detected in non-dev environment
    validate_security_settings(settings)

    # init rate limiter (slowapi) if available
    try:
        redis_url = getattr(settings, "REDIS_URL", None)
        default_limit = _build_default_rate_limit(
            getattr(settings, "RATE_LIMIT_REQUESTS", 100),
            getattr(settings, "RATE_LIMIT_WINDOW", 60),
        )
        init_rate_limiter(app, redis_url=redis_url, default_limits=[default_limit])
    except Exception:
        logger.exception("Failed to initialize rate limiter")

    # Explicit migration checks or warnings instead of blind Base.metadata.create_all
    env = (getattr(settings, "ENV", None) or "development").lower().strip()
    is_dev = env in ("development", "dev", "test", "testing", "local")

    if is_dev:
        logger.info(
            "Development environment ('%s') detected: Initializing development SQLite schema.",
            env,
        )
        try:
            from .core import database

            database.init_db(create_tables=True)
            logger.info("Development database initialized.")
        except Exception:
            logger.exception("Development database initialization failed")
    else:
        logger.warning(
            "Non-development environment ('%s') detected: Skipping blind Base.metadata.create_all. "
            "Database migrations must be applied explicitly using Alembic ('alembic upgrade head').",
            env,
        )
        try:
            from .core import database

            with database.engine.connect() as conn:
                pass
            logger.info("Database connectivity check succeeded.")
        except Exception:
            logger.critical("Database connectivity check failed on startup")
            raise RuntimeError("Database connectivity check failed on startup")


@app.get("/healthz", tags=["health"])
def healthz():
    return {"status": "ok"}
