"""
ChemEng REST API

FastAPIベースのWeb API

Usage:
    python -m chemeng.interface.api
    uvicorn chemeng.interface.api:app --reload

Endpoints:
    GET  /                          - API情報
    GET  /api/v1/engines            - エンジン一覧
    GET  /api/v1/skills             - スキル一覧
    GET  /api/v1/skills/{id}        - スキル詳細
    POST /api/v1/calculate/{id}     - 計算実行
    POST /api/v1/property           - 物性値取得
    POST /api/v1/equilibrium        - 相平衡計算
"""

from __future__ import annotations

import logging
import os
import time as _time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, Query, Request, Response
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, HTMLResponse  # noqa: F401
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field, field_validator
    from starlette.middleware.base import BaseHTTPMiddleware
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    # ダミー定義
    class BaseModel:
        pass
    def Field(*args, **kwargs):
        return None
    def Query(*args, **kwargs):
        return None
    def field_validator(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

try:
    from ..core.errors import safe_error_message
    from ..core.logging_config import setup_logging
except ImportError:
    from core.errors import safe_error_message
    from core.logging_config import setup_logging

setup_logging()
logger = logging.getLogger("chemeng")

# Web UIディレクトリ
WEB_DIR = Path(__file__).parent / "web"


def _parse_cors_origins(value: str | None) -> list[str]:
    if not value:
        return ["http://localhost:8000", "http://127.0.0.1:8000"]
    if value.strip() == "*":
        return ["*"]
    return [o.strip() for o in value.split(",") if o.strip()]


# ==================== リクエスト/レスポンスモデル ====================

class PropertyRequest(BaseModel):
    """Property lookup request."""

    substance: str = Field(..., description="Substance name or CAS number", max_length=200)
    property: str = Field(..., description="Property name", max_length=100, pattern=r"^[a-z_]+$")
    temperature: float | None = Field(None, description="Temperature (K)", ge=0, le=10000)
    pressure: float | None = Field(None, description="Pressure (Pa)", ge=0, le=1e9)
    quality: float | None = Field(None, description="Vapor quality (0-1)", ge=0, le=1)
    engine: str | None = Field(None, description="Requested engine", max_length=50)

    @field_validator("substance")
    @classmethod
    def validate_substance(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("substance must not be empty")
        return value


class PropertyResponse(BaseModel):
    """物性値レスポンス"""
    success: bool
    substance: str
    property: str
    value: float | None = None
    unit: str | None = None
    conditions: dict[str, float] = Field(default_factory=dict)
    engine: str | None = None
    error: str | None = None


class CalculationRequest(BaseModel):
    """計算リクエスト"""
    parameters: dict[str, Any] = Field(default_factory=dict)


class CalculationResponse(BaseModel):
    """計算レスポンス"""
    success: bool
    skill_id: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    execution_time_ms: int = 0
    engine: str | None = None
    timestamp: str | None = None


class BatchCaseRequest(BaseModel):
    """バッチ計算の1ケース"""
    skill_id: str = Field(..., max_length=100)
    case_name: str = Field("", max_length=200)
    parameters: dict[str, Any] = Field(default_factory=dict)


class BatchCalculationRequest(BaseModel):
    """バッチ計算リクエスト"""
    cases: list[BatchCaseRequest] = Field(..., min_length=1, max_length=50)


class EquilibriumRequest(BaseModel):
    """Equilibrium calculation request."""

    substances: list[str] = Field(..., description="Substance list", max_length=10)
    composition: dict[str, float] = Field(..., description="Mole fractions")
    temperature: float | None = Field(None, description="Temperature (K)", ge=0, le=10000)
    pressure: float | None = Field(None, description="Pressure (Pa)", ge=0, le=1e9)
    engine: str | None = Field(None, description="Requested engine", max_length=50)

    @field_validator("substances")
    @classmethod
    def validate_substances(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if len(cleaned) < 2:
            raise ValueError("at least two substances are required")
        return cleaned

    @field_validator("composition")
    @classmethod
    def validate_composition(cls, value: dict[str, float]) -> dict[str, float]:
        if not value:
            raise ValueError("composition must not be empty")
        total = sum(value.values())
        if abs(total - 1.0) > 0.05:
            raise ValueError("composition must sum to 1.0")
        return value


class EngineInfo(BaseModel):
    """エンジン情報"""
    name: str
    available: bool
    property_types: list[str]
    calculation_types: list[str]
    supported_substances: str


class SkillInfo(BaseModel):
    """スキル情報"""
    id: str
    name: str
    description: str
    calculation_type: str
    required_engines: list[str]
    tags: list[str] = Field(default_factory=list)


class SkillDetail(SkillInfo):
    """スキル詳細"""
    version: str
    input_schema: list[dict[str, Any]]
    output_schema: list[dict[str, Any]]
    defaults: dict[str, Any] = Field(default_factory=dict)


class FeedbackRequest(BaseModel):
    """User feedback request."""
    category: str = Field(..., description="Feedback category", max_length=50)
    message: str = Field(..., description="Feedback message", min_length=1, max_length=2000)
    name: str = Field("", description="Optional user name", max_length=100)


class ChatRequest(BaseModel):
    """AI chat request."""
    message: str = Field(..., description="User message", max_length=2000)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=20)
    context: dict[str, Any] | None = Field(None, description="Current UI context")


class SuggestRequest(BaseModel):
    """Parameter suggestion request."""
    skill_id: str = Field(..., description="Skill identifier", max_length=100)
    current_params: dict[str, Any] = Field(default_factory=dict)
    goal: str | None = Field(None, description="User's goal description", max_length=500)


class FlowsheetRequest(BaseModel):
    """Flowsheet calculation request."""
    id: str = Field("flowsheet-1", max_length=100)
    name: str = Field("Process Flowsheet", max_length=200)
    components: list[str] = Field(default_factory=list)
    blocks: dict[str, Any] = Field(default_factory=dict)
    streams: dict[str, Any] = Field(default_factory=dict)
    tear_streams: list[str] = Field(default_factory=list)
    convergence_config: dict[str, Any] = Field(default_factory=dict)


class GoalSeekRequest(BaseModel):
    """Goal seek request."""
    flowsheet: dict[str, Any] = Field(...)
    target_variable: str = Field(..., max_length=200)
    target_value: float = Field(...)
    manipulated_variable: str = Field(..., max_length=200)
    lower_bound: float = Field(...)
    upper_bound: float = Field(...)
    tolerance: float = Field(1e-6)
    max_iterations: int = Field(50, ge=1, le=500)


# ==================== アプリケーション ====================

def create_app() -> FastAPI:
    """FastAPIアプリケーションを作成"""
    if not FASTAPI_AVAILABLE:
        raise ImportError("FastAPI is not installed. Run: pip install fastapi uvicorn")

    def _result_timestamp(value: Any) -> str | None:
        return value.isoformat() if value is not None else None

    app = FastAPI(
        title="ChemEng API",
        description="化学工学計算モジュール REST API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # セキュリティヘッダー + リクエストトレーシング + CSRF ミドルウェア
    class SecurityHeadersMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            # CSRF protection: only enforce JSON content type when the request
            # actually sends a body. Some endpoints use POST with query params only.
            if request.method == "POST" and request.url.path.startswith("/api/"):
                ct = request.headers.get("content-type", "")
                content_length = request.headers.get("content-length", "0").strip() or "0"
                has_body = content_length not in ("0", "")
                if has_body and "application/json" not in ct:
                    return Response(
                        status_code=415,
                        content='{"detail":"Unsupported Media Type. Content-Type must be application/json."}',
                        media_type="application/json",
                    )

            request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
            start = _time.perf_counter()
            response: Response = await call_next(request)
            elapsed = _time.perf_counter() - start
            if request.url.path.startswith("/js/") or request.url.path.startswith("/css/"):
                response.headers["Cache-Control"] = "no-cache, must-revalidate"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
                "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
                "connect-src 'self'; "
                "img-src 'self' data:; "
                "frame-ancestors 'none';"
            )
            response.headers["X-Request-ID"] = request_id
            if request.url.path.startswith("/api/"):
                logger.info(
                    "req=%s method=%s path=%s status=%s time=%.3fs",
                    request_id, request.method, request.url.path,
                    response.status_code, elapsed,
                )
            return response

    app.add_middleware(SecurityHeadersMiddleware)

    # レートリミッター（インメモリ、60 req/min per IP）
    class RateLimitMiddleware(BaseHTTPMiddleware):
        def __init__(self, app_instance, max_requests: int = 60, window: int = 60):
            super().__init__(app_instance)
            self.max_requests = max_requests
            self.window = window
            self._requests: dict[str, list[float]] = defaultdict(list)
            self._last_cleanup: float = 0.0

        def _get_client_ip(self, request: Request) -> str:
            """Extract client IP, respecting X-Forwarded-For behind reverse proxies."""
            forwarded = request.headers.get("X-Forwarded-For", "")
            if forwarded:
                # First IP is the original client
                return forwarded.split(",")[0].strip()
            return request.client.host if request.client else "unknown"

        async def dispatch(self, request: Request, call_next):
            rate_limited_prefixes = ("/api/v1/calculate", "/api/v1/chat", "/api/v1/suggest", "/api/v1/feedback", "/api/v1/flowsheet")
            if not any(request.url.path.startswith(p) for p in rate_limited_prefixes):
                return await call_next(request)
            client_ip = self._get_client_ip(request)
            now = _time.time()

            # Periodic cleanup to prevent unbounded memory growth
            if now - self._last_cleanup > self.window * 2:
                cutoff = now - self.window
                self._requests = defaultdict(list, {
                    k: v for k, v in self._requests.items()
                    if v and v[-1] > cutoff
                })
                self._last_cleanup = now

            self._requests[client_ip] = [
                t for t in self._requests[client_ip] if now - t < self.window
            ]
            if len(self._requests[client_ip]) >= self.max_requests:
                return Response(
                    status_code=429,
                    content='{"detail":"Rate limit exceeded. Please wait. / レート制限超過。しばらくお待ちください。"}',
                    media_type="application/json",
                )
            self._requests[client_ip].append(now)
            return await call_next(request)

    app.add_middleware(RateLimitMiddleware, max_requests=60, window=60)

    # CORS設定
    cors_origins = _parse_cors_origins(os.environ.get("CHEMENG_CORS_ORIGINS"))
    allow_credentials_env = os.environ.get("CHEMENG_CORS_ALLOW_CREDENTIALS", "false").lower()
    allow_credentials = allow_credentials_env in ("1", "true", "yes") and "*" not in cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )

    # Static files for CSS, JS, slides
    css_dir = WEB_DIR / "css"
    if css_dir.exists():
        app.mount("/css", StaticFiles(directory=str(css_dir)), name="css")

    js_dir = WEB_DIR / "js"
    if js_dir.exists():
        app.mount("/js", StaticFiles(directory=str(js_dir)), name="js")

    slides_dir = WEB_DIR / "slides"
    if slides_dir.exists():
        app.mount("/slides", StaticFiles(directory=str(slides_dir)), name="slides")

    # ==================== エンドポイント ====================

    @app.get("/presentation.html", response_class=HTMLResponse)
    async def presentation():
        """Presentation slides"""
        html_file = WEB_DIR / "presentation.html"
        if html_file.exists():
            return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
        raise HTTPException(status_code=404, detail="Presentation not found")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Web UI"""
        html_file = WEB_DIR / "index.html"
        if html_file.exists():
            return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
        return HTMLResponse(content="""
            <html><body>
            <h1>ChemEng API</h1>
            <p>Web UI not found. API available at <a href="/docs">/docs</a></p>
            </body></html>
        """)

    @app.get("/api")
    async def api_info():
        """API情報"""
        return {
            "name": "ChemEng API",
            "version": "1.0.0",
            "description": "Chemical Engineering Calculation Module",
            "docs": "/docs",
            "ui": "/",
        }

    @app.get("/api/v1/engines", response_model=list[EngineInfo])
    async def list_engines():
        """利用可能なエンジン一覧"""
        from engines import get_available_engines

        engines = get_available_engines()
        return [
            EngineInfo(
                name=e.name,
                available=e.is_available(),
                property_types=e.capabilities.property_types,
                calculation_types=e.capabilities.calculation_types,
                supported_substances=e.capabilities.supported_substances,
            )
            for e in engines
        ]

    @app.get("/api/v1/skills", response_model=list[SkillInfo])
    async def list_skills():
        """スキル一覧"""
        from core import get_registry

        registry = get_registry()
        skills = registry.list_skills()
        return [
            SkillInfo(
                id=s.id,
                name=s.name,
                description=s.description,
                calculation_type=s.calculation_type,
                required_engines=s.required_engines,
                tags=s.tags,
            )
            for s in skills
        ]

    @app.get("/api/v1/skills/{skill_id}", response_model=SkillDetail)
    async def get_skill(skill_id: str):
        """スキル詳細"""
        from core import get_registry

        registry = get_registry()
        skill = registry.get_skill(skill_id)

        if skill is None:
            raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")

        return SkillDetail(
            id=skill.id,
            name=skill.name,
            description=skill.description,
            calculation_type=skill.calculation_type,
            required_engines=skill.required_engines,
            tags=skill.tags,
            version=skill.version,
            input_schema=[p.to_dict() for p in skill.input_schema],
            output_schema=[p.to_dict() for p in skill.output_schema],
            defaults=skill.defaults,
        )

    @app.post("/api/v1/calculate/batch")
    async def calculate_batch(request: BatchCalculationRequest):
        """バッチ計算実行 - 複数ケースを一括処理"""
        import time as _time

        from core import get_registry

        registry = get_registry()
        start = _time.perf_counter()
        results = []
        succeeded = 0
        failed = 0

        for case in request.cases:
            case_start = _time.perf_counter()
            try:
                result = registry.execute(case.skill_id, case.parameters)
                case_elapsed = int((_time.perf_counter() - case_start) * 1000)
                results.append({
                    "success": result.success,
                    "case_name": case.case_name,
                    "skill_id": result.skill_id,
                    "inputs": result.inputs,
                    "outputs": result.outputs,
                    "warnings": result.warnings,
                    "errors": result.errors,
                    "execution_time_ms": case_elapsed,
                    "engine": result.engine_used,
                    "timestamp": _result_timestamp(result.timestamp),
                })
                if result.success:
                    succeeded += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                case_elapsed = int((_time.perf_counter() - case_start) * 1000)
                results.append({
                    "success": False,
                    "case_name": case.case_name,
                    "skill_id": case.skill_id,
                    "inputs": case.parameters,
                    "outputs": {},
                    "warnings": [],
                    "errors": [safe_error_message(e)],
                    "execution_time_ms": case_elapsed,
                    "engine": None,
                    "timestamp": None,
                })

            # バッチ全体のタイムアウト（5分）
            if (_time.perf_counter() - start) > 300:
                remaining = len(request.cases) - len(results)
                failed += remaining
                logger.warning("Batch timeout: %d cases remaining", remaining)
                break

        elapsed = int((_time.perf_counter() - start) * 1000)
        return {
            "success": failed == 0,
            "total": len(request.cases),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
            "execution_time_ms": elapsed,
        }

    @app.post("/api/v1/calculate/{skill_id}", response_model=CalculationResponse)
    async def calculate(skill_id: str, request: CalculationRequest):
        """計算実行（30秒タイムアウト付き）"""
        import asyncio
        import concurrent.futures

        from core import get_registry

        registry = get_registry()

        def _run_calculation():
            return registry.execute(skill_id, request.parameters)

        try:
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = await asyncio.wait_for(
                    loop.run_in_executor(pool, _run_calculation),
                    timeout=30.0,
                )
        except asyncio.TimeoutError:
            logger.warning("Calculation timed out: skill=%s", skill_id)
            return CalculationResponse(
                success=False,
                skill_id=skill_id,
                inputs=request.parameters,
                errors=["Calculation timed out (30s). Try simpler parameters. / 計算がタイムアウトしました（30秒）。パラメータを簡素化してください。"],
            )
        except Exception as e:
            logger.error("Unhandled error in calculate(%s): %s", skill_id, e, exc_info=True)
            return CalculationResponse(
                success=False,
                skill_id=skill_id,
                inputs=request.parameters,
                errors=[safe_error_message(e)],
            )

        return CalculationResponse(
            success=result.success,
            skill_id=result.skill_id,
            inputs=result.inputs,
            outputs=result.outputs,
            warnings=result.warnings,
            errors=result.errors,
            execution_time_ms=result.execution_time_ms,
            engine=result.engine_used,
            timestamp=_result_timestamp(result.timestamp),
        )

    @app.post("/api/v1/property", response_model=PropertyResponse)
    async def get_property(request: PropertyRequest):
        """物性値取得"""
        from engines import get_engine, select_engine

        # エンジン選択
        if request.engine:
            engine = get_engine(request.engine)
            if not engine:
                raise HTTPException(
                    status_code=400,
                    detail=f"Engine not found: {request.engine}"
                )
        else:
            engine = select_engine(
                substance=request.substance,
                property_name=request.property,
            )

        if not engine:
            raise HTTPException(
                status_code=500,
                detail="No calculation engine available"
            )

        conditions = {}
        if request.temperature is not None:
            conditions["temperature"] = request.temperature
        if request.pressure is not None:
            conditions["pressure"] = request.pressure
        if request.quality is not None:
            conditions["quality"] = request.quality

        try:
            value = engine.get_property(
                request.substance,
                request.property,
                conditions,
            )

            return PropertyResponse(
                success=True,
                substance=request.substance,
                property=request.property,
                value=value,
                conditions=conditions,
                engine=engine.name,
            )

        except Exception as e:
            return PropertyResponse(
                success=False,
                substance=request.substance,
                property=request.property,
                error=safe_error_message(e),
                engine=engine.name,
            )

    @app.post("/api/v1/txy-diagram")
    async def get_txy_diagram(
        light_component: str = Query(..., max_length=200),
        heavy_component: str = Query(..., max_length=200),
        pressure: float = Query(101325.0, ge=0, le=1e9),
        points: int = Query(21, ge=2, le=200),
    ):
        """
        T-x-y相図データを生成

        Args:
            light_component: 軽沸成分（低沸点）
            heavy_component: 重沸成分（高沸点）
            pressure: 圧力 (Pa)
            points: データ点数
        """
        try:
            from core import get_registry

            registry = get_registry()
            result = registry.execute("txy_diagram", {
                "light_component": light_component,
                "heavy_component": heavy_component,
                "pressure": pressure,
                "points": points,
            })
            if result.success:
                return result.outputs
            return {
                "success": False,
                "error": "; ".join(result.errors),
            }
        except Exception as e:
            return {
                "success": False,
                "error": safe_error_message(e),
            }

    @app.post("/api/v1/equilibrium")
    async def calculate_equilibrium(request: EquilibriumRequest):
        """相平衡計算"""
        from engines import get_engine, select_engine

        # エンジン選択
        if request.engine:
            engine = get_engine(request.engine)
            if not engine:
                raise HTTPException(
                    status_code=400,
                    detail=f"Engine not found: {request.engine}"
                )
        else:
            engine = select_engine(
                substance=request.substances,
                calculation_type="vle",
            )

        if not engine:
            raise HTTPException(
                status_code=500,
                detail="No calculation engine available"
            )

        conditions = {}
        if request.temperature is not None:
            conditions["temperature"] = request.temperature
        if request.pressure is not None:
            conditions["pressure"] = request.pressure

        try:
            result = engine.calculate_equilibrium(
                request.substances,
                request.composition,
                conditions,
            )

            return {
                "success": True,
                "engine": engine.name,
                "result": result,
            }

        except Exception as e:
            return {
                "success": False,
                "engine": engine.name,
                "error": safe_error_message(e),
            }

    # 物質データのキャッシュ（起動時に1回だけ読み込み）
    _substances_cache: dict | None = None

    # ==================== AI Endpoints ====================

    # ==================== Feedback Endpoint ====================

    @app.post("/api/v1/feedback")
    async def submit_feedback(request: FeedbackRequest):
        """Submit user feedback to Discord via webhook."""
        from urllib.parse import urlparse

        import httpx

        webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
        if not webhook_url:
            logger.warning("DISCORD_WEBHOOK_URL not configured — feedback discarded")
            return {"success": False, "error": "Feedback system is not configured."}

        # SSRF protection: only allow Discord webhook URLs
        parsed = urlparse(webhook_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in ("discord.com", "discordapp.com")
            or not parsed.path.startswith("/api/webhooks/")
        ):
            logger.error("Invalid DISCORD_WEBHOOK_URL: not a valid Discord webhook")
            return {"success": False, "error": "Feedback system misconfigured."}

        category_labels = {
            "bug": "\U0001f41b Bug Report",
            "feature": "\u2728 Feature Request",
            "question": "\u2753 Question",
            "other": "\U0001f4ac Other",
        }
        cat_label = category_labels.get(request.category, request.category)

        embed = {
            "title": f"[Feedback] {cat_label}",
            "description": request.message,
            "color": 0x00D4FF,
            "fields": [],
            "footer": {"text": "ChemEng Feedback"},
        }
        if request.name.strip():
            embed["fields"].append({"name": "From", "value": request.name.strip(), "inline": True})
        embed["fields"].append({"name": "Category", "value": cat_label, "inline": True})

        payload = {
            "username": "ChemEng Feedback",
            "embeds": [embed],
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(webhook_url, json=payload)
            if resp.status_code in (200, 204):
                logger.info("Feedback sent to Discord: category=%s", request.category)
                return {"success": True}
            logger.error("Discord webhook error: status=%s body=%s", resp.status_code, resp.text[:200])
            return {"success": False, "error": "Failed to send feedback. Please try again later."}
        except Exception as e:
            logger.error("Discord webhook exception: %s", e)
            return {"success": False, "error": "Failed to send feedback. Please try again later."}

    # ==================== AI Endpoints ====================

    _assistant = None

    @app.post("/api/v1/chat")
    async def ai_chat(request: ChatRequest):
        """AI chat endpoint for the help panel."""
        nonlocal _assistant
        try:
            from ai.chat import ChemEngAssistant

            if _assistant is None:
                _assistant = ChemEngAssistant()
            reply = _assistant.chat(
                message=request.message,
                history=request.history,
                context=request.context,
            )
            return {"success": True, "reply": reply}
        except RuntimeError as e:
            error_msg = str(e)
            if "API_KEY" in error_msg or "not installed" in error_msg:
                return {
                    "success": False,
                    "reply": "AI機能は現在利用できません。ANTHROPIC_API_KEY環境変数を設定してください。\n\nAI feature is not available. Please set the ANTHROPIC_API_KEY environment variable.",
                    "error": error_msg,
                }
            raise HTTPException(status_code=500, detail=safe_error_message(e))
        except Exception as e:
            logger.error("AI chat error: %s", e, exc_info=True)
            return {
                "success": False,
                "reply": "エラーが発生しました。もう一度お試しください。\n\nAn error occurred. Please try again.",
                "error": safe_error_message(e),
            }

    @app.post("/api/v1/suggest")
    async def ai_suggest(request: SuggestRequest):
        """AI parameter suggestion endpoint."""
        try:
            from ai.suggest import suggest_parameters

            suggestions = suggest_parameters(
                skill_id=request.skill_id,
                current_params=request.current_params,
                goal=request.goal,
            )
            return {"success": True, "suggestions": suggestions}
        except RuntimeError as e:
            error_msg = str(e)
            if "API_KEY" in error_msg or "not installed" in error_msg:
                return {"success": False, "suggestions": [], "error": error_msg}
            raise HTTPException(status_code=500, detail=safe_error_message(e))
        except Exception as e:
            logger.error("AI suggest error: %s", e, exc_info=True)
            return {"success": False, "suggestions": [], "error": safe_error_message(e)}

    # ==================== Substance Endpoints ====================

    @app.get("/api/v1/substances")
    async def list_substances(query: str | None = None, category: str | None = None):
        """登録済み物質一覧を取得（検索可能）"""
        nonlocal _substances_cache
        import yaml

        substances_file = Path(__file__).parent.parent / "skills" / "defaults" / "common_substances.yaml"

        if not substances_file.exists():
            return {"success": True, "substances": []}

        try:
            if _substances_cache is None:
                with open(substances_file, encoding="utf-8") as f:
                    _substances_cache = yaml.safe_load(f)

            data = _substances_cache

            substances = data.get("substances", {})
            result = []

            for key, info in substances.items():
                name_ja = info.get("name_ja", "")
                name_en = info.get("name_en", key)
                aliases = info.get("aliases", [])
                cat = info.get("category", "")

                # フィルタリング
                if category and cat != category:
                    continue

                if query:
                    query_lower = query.lower()
                    searchable = [key.lower(), name_ja.lower(), name_en.lower()] + [a.lower() for a in aliases]
                    if not any(query_lower in s for s in searchable):
                        continue

                result.append({
                    "id": key,
                    "name_ja": name_ja,
                    "name_en": name_en,
                    "formula": info.get("formula", ""),
                    "cas": info.get("cas", ""),
                    "category": cat,
                    "aliases": aliases,
                    "molecular_weight": info.get("molecular_weight"),
                })

            return {"success": True, "substances": result}

        except Exception as e:
            return {"success": False, "error": safe_error_message(e), "substances": []}

    @app.get("/api/v1/substances/{substance}")
    async def get_substance_info(substance: str, engine: str | None = None):
        """物質情報取得"""
        from engines import get_engine, select_engine

        if engine:
            eng = get_engine(engine)
        else:
            eng = select_engine(substance=substance)

        if not eng:
            raise HTTPException(
                status_code=500,
                detail="No calculation engine available"
            )

        try:
            if hasattr(eng, "get_substance_info"):
                info = eng.get_substance_info(substance)
            elif hasattr(eng, "get_fluid_info"):
                info = eng.get_fluid_info(substance)
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Engine {eng.name} does not support substance info"
                )

            return {
                "success": True,
                "substance": substance,
                "engine": eng.name,
                "info": info,
            }

        except Exception as e:
            raise HTTPException(status_code=400, detail=safe_error_message(e))

    # ==================== Flowsheet Endpoints ====================

    @app.post("/api/v1/flowsheet/calculate")
    async def calculate_flowsheet(request: FlowsheetRequest):
        """フローシート全体を計算"""
        import asyncio
        import concurrent.futures

        def _run():
            from core.solver import SequentialModularSolver
            solver = SequentialModularSolver(request.model_dump())
            return solver.solve()

        try:
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = await asyncio.wait_for(
                    loop.run_in_executor(pool, _run),
                    timeout=60.0,
                )
            return result
        except asyncio.TimeoutError:
            return {"success": False, "error": "Flowsheet calculation timed out (60s)"}
        except Exception as e:
            logger.error("Flowsheet calculation error: %s", e, exc_info=True)
            return {"success": False, "error": safe_error_message(e)}

    @app.post("/api/v1/flowsheet/goal-seek")
    async def goal_seek(request: GoalSeekRequest):
        """ゴールシーク実行"""
        import asyncio
        import concurrent.futures

        def _run():
            from core.solver import GoalSeekSolver
            solver = GoalSeekSolver(request.flowsheet)
            return solver.solve(
                target_variable=request.target_variable,
                target_value=request.target_value,
                manipulated_variable=request.manipulated_variable,
                lower_bound=request.lower_bound,
                upper_bound=request.upper_bound,
                tolerance=request.tolerance,
                max_iterations=request.max_iterations,
            )

        try:
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = await asyncio.wait_for(
                    loop.run_in_executor(pool, _run),
                    timeout=120.0,
                )
            return result
        except asyncio.TimeoutError:
            return {"success": False, "error": "Goal seek timed out (120s)"}
        except Exception as e:
            logger.error("Goal seek error: %s", e, exc_info=True)
            return {"success": False, "error": safe_error_message(e)}

    @app.post("/api/v1/flowsheet/export-mermaid")
    async def export_mermaid(request: FlowsheetRequest):
        """フローシートからMermaidダイアグラムを生成"""
        try:
            from core.flowsheet import FlowsheetData, generate_mermaid
            flowsheet = FlowsheetData.from_dict(request.model_dump())
            mermaid_text = generate_mermaid(flowsheet)
            return {"success": True, "mermaid": mermaid_text}
        except Exception as e:
            logger.error("Mermaid export error: %s", e, exc_info=True)
            return {"success": False, "error": safe_error_message(e)}

    return app


# アプリケーションインスタンス
app = create_app() if FASTAPI_AVAILABLE else None


def start_server(host: str | None = None, port: int | None = None):
    """サーバー起動"""
    if not FASTAPI_AVAILABLE:
        print("Error: FastAPI is not installed")
        print("Run: pip install fastapi uvicorn")
        return

    import uvicorn
    resolved_host = host or os.environ.get("HOST", "0.0.0.0")
    resolved_port = port if port is not None else int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host=resolved_host, port=resolved_port)


if __name__ == "__main__":
    start_server()
