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

from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse
    from pydantic import BaseModel, Field
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    # ダミー定義
    class BaseModel:
        pass
    def Field(*args, **kwargs):
        return None

# Web UIディレクトリ
WEB_DIR = Path(__file__).parent / "web"


# ==================== リクエスト/レスポンスモデル ====================

class PropertyRequest(BaseModel):
    """物性値取得リクエスト"""
    substance: str = Field(..., description="物質名またはCAS番号")
    property: str = Field(..., description="物性名")
    temperature: float | None = Field(None, description="温度 (K)")
    pressure: float | None = Field(None, description="圧力 (Pa)")
    quality: float | None = Field(None, description="乾き度 (0-1)")
    engine: str | None = Field(None, description="使用するエンジン名")


class PropertyResponse(BaseModel):
    """物性値レスポンス"""
    success: bool
    substance: str
    property: str
    value: float | None = None
    unit: str | None = None
    conditions: dict[str, float] = {}
    engine: str | None = None
    error: str | None = None


class CalculationRequest(BaseModel):
    """計算リクエスト"""
    parameters: dict[str, Any] = Field(default_factory=dict)


class CalculationResponse(BaseModel):
    """計算レスポンス"""
    success: bool
    skill_id: str
    inputs: dict[str, Any] = {}
    outputs: dict[str, Any] = {}
    warnings: list[str] = []
    errors: list[str] = []
    execution_time_ms: int = 0
    engine: str | None = None
    timestamp: str | None = None


class EquilibriumRequest(BaseModel):
    """相平衡計算リクエスト"""
    substances: list[str] = Field(..., description="物質リスト")
    composition: dict[str, float] = Field(..., description="組成（モル分率）")
    temperature: float | None = Field(None, description="温度 (K)")
    pressure: float | None = Field(None, description="圧力 (Pa)")
    engine: str | None = Field(None, description="使用するエンジン名")


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
    tags: list[str] = []


class SkillDetail(SkillInfo):
    """スキル詳細"""
    version: str
    input_schema: list[dict[str, Any]]
    output_schema: list[dict[str, Any]]
    defaults: dict[str, Any] = {}


# ==================== アプリケーション ====================

def create_app() -> "FastAPI":
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ==================== エンドポイント ====================

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
                error=str(e),
                engine=engine.name,
            )

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
                "error": str(e),
            }

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
            raise HTTPException(status_code=400, detail=str(e))

    return app


# アプリケーションインスタンス
app = create_app() if FASTAPI_AVAILABLE else None


def start_server(host: str = "0.0.0.0", port: int = 8000):
    """サーバー起動"""
    if not FASTAPI_AVAILABLE:
        print("Error: FastAPI is not installed")
        print("Run: pip install fastapi uvicorn")
        return

    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
