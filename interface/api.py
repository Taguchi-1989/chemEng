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
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, HTMLResponse  # noqa: F401
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field
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

from core.logging_config import setup_logging
from core.errors import safe_error_message

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
    """物性値取得リクエスト"""
    substance: str = Field(..., description="物質名またはCAS番号", max_length=200)
    property: str = Field(..., description="物性名", max_length=100, pattern=r"^[a-z_]+$")
    temperature: float | None = Field(None, description="温度 (K)", ge=0, le=10000)
    pressure: float | None = Field(None, description="圧力 (Pa)", ge=0, le=1e9)
    quality: float | None = Field(None, description="乾き度 (0-1)", ge=0, le=1)
    engine: str | None = Field(None, description="使用するエンジン名", max_length=50)


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


class EquilibriumRequest(BaseModel):
    """相平衡計算リクエスト"""
    substances: list[str] = Field(..., description="物質リスト", max_length=10)
    composition: dict[str, float] = Field(..., description="組成（モル分率）")
    temperature: float | None = Field(None, description="温度 (K)", ge=0, le=10000)
    pressure: float | None = Field(None, description="圧力 (Pa)", ge=0, le=1e9)
    engine: str | None = Field(None, description="使用するエンジン名", max_length=50)


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


# ==================== アプリケーション ====================

def create_app() -> FastAPI:
    """FastAPIアプリケーションを作成"""
    if not FASTAPI_AVAILABLE:
        raise ImportError("FastAPI is not installed. Run: pip install fastapi uvicorn")

    app = FastAPI(
        title="ChemEng API",
        description="化学工学計算モジュール REST API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS設定
    cors_origins = _parse_cors_origins(os.environ.get("CHEMENG_CORS_ORIGINS"))
    allow_credentials_env = os.environ.get("CHEMENG_CORS_ALLOW_CREDENTIALS", "false").lower()
    allow_credentials = allow_credentials_env in ("1", "true", "yes") and "*" not in cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "OPTIONS"],
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

    @app.post("/api/v1/calculate/{skill_id}", response_model=CalculationResponse)
    async def calculate(skill_id: str, request: CalculationRequest):
        """計算実行"""
        from core import get_registry

        registry = get_registry()
        result = registry.execute(skill_id, request.parameters)

        return CalculationResponse(
            success=result.success,
            skill_id=result.skill_id,
            inputs=result.inputs,
            outputs=result.outputs,
            warnings=result.warnings,
            errors=result.errors,
            execution_time_ms=result.execution_time_ms,
            engine=result.engine_used,
            timestamp=result.timestamp.isoformat(),
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

    @app.get("/api/v1/substances")
    async def list_substances(query: str | None = None, category: str | None = None):
        """登録済み物質一覧を取得（検索可能）"""
        import yaml

        substances_file = Path(__file__).parent.parent / "skills" / "defaults" / "common_substances.yaml"

        if not substances_file.exists():
            return {"success": True, "substances": []}

        try:
            with open(substances_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)

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

    return app


# アプリケーションインスタンス
app = create_app() if FASTAPI_AVAILABLE else None


def start_server(host: str = "127.0.0.1", port: int = 8000):
    """サーバー起動"""
    if not FASTAPI_AVAILABLE:
        print("Error: FastAPI is not installed")
        print("Run: pip install fastapi uvicorn")
        return

    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
