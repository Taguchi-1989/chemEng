"""
Vercel Serverless Function Entry Point

既存のFastAPIアプリをVercelにデプロイするためのエントリーポイント
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any


# ==================== FastAPI App ====================

app = FastAPI(
    title="ChemEng API",
    description="化学工学計算API - 物性推算、物質収支、蒸留塔設計など",
    version="0.1.0",
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Models ====================

class PropertyRequest(BaseModel):
    substance: str = Field(..., description="物質名またはCAS番号")
    property: str = Field(..., description="物性名")
    temperature: float | None = Field(None, description="温度 (K)")
    pressure: float | None = Field(None, description="圧力 (Pa)")


class CalculationRequest(BaseModel):
    parameters: dict[str, Any] = Field(default_factory=dict)


# ==================== Endpoints ====================

@app.get("/")
def root():
    """API情報"""
    # Check for available engines
    try:
        from engines import get_available_engines
        engines = get_available_engines()
        engine_names = [e.name for e in engines]
    except Exception:
        engine_names = []

    return {
        "name": "ChemEng API",
        "version": "0.1.0",
        "description": "化学工学計算API",
        "mode": "full" if engine_names else "lightweight",
        "available_engines": engine_names,
        "note": None if engine_names else "Lightweight mode: heavy calculation libraries (thermo, chemicals) not installed. Install locally for full functionality.",
        "endpoints": {
            "/api/v1/engines": "利用可能なエンジン一覧",
            "/api/v1/skills": "利用可能なスキル一覧",
            "/api/v1/property": "物性値取得 (POST)",
            "/api/v1/calculate/{skill_id}": "計算実行 (POST)",
        },
    }


@app.get("/api/v1/engines")
def list_engines():
    """利用可能なエンジン一覧"""
    try:
        from engines import get_available_engines
        engines = get_available_engines()
        return {
            "engines": [
                {
                    "name": e.name,
                    "available": e.is_available(),
                    "property_types": e.capabilities.property_types,
                    "calculation_types": e.capabilities.calculation_types,
                }
                for e in engines
            ]
        }
    except Exception as e:
        return {"engines": [], "error": str(e)}


@app.get("/api/v1/skills")
def list_skills():
    """利用可能なスキル一覧"""
    try:
        from core import get_registry
        registry = get_registry()
        skills = registry.list_skills()
        return {
            "skills": [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "calculation_type": s.calculation_type,
                }
                for s in skills
            ]
        }
    except Exception as e:
        return {"skills": [], "error": str(e)}


@app.get("/api/v1/skills/{skill_id}")
def get_skill(skill_id: str):
    """スキル詳細"""
    try:
        from core import get_registry
        registry = get_registry()
        skill = registry.get_skill(skill_id)
        if skill is None:
            raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")
        return {
            "id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "calculation_type": skill.calculation_type,
            "input_schema": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                    "unit": p.unit,
                }
                for p in skill.input_schema
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/property")
def get_property(request: PropertyRequest):
    """物性値を取得"""
    try:
        from engines import select_engine

        engine = select_engine(substance=request.substance, property_name=request.property)
        if engine is None:
            raise HTTPException(
                status_code=503,
                detail="No calculation engine available. This API is running in lightweight mode. Install thermo/chemicals locally for full functionality."
            )

        conditions = {}
        if request.temperature:
            conditions["temperature"] = request.temperature
        if request.pressure:
            conditions["pressure"] = request.pressure

        value = engine.get_property(request.substance, request.property, conditions)

        return {
            "success": True,
            "substance": request.substance,
            "property": request.property,
            "value": value,
            "conditions": conditions,
            "engine": engine.name,
        }
    except Exception as e:
        return {
            "success": False,
            "substance": request.substance,
            "property": request.property,
            "error": str(e),
        }


@app.post("/api/v1/calculate/{skill_id}")
def calculate(skill_id: str, request: CalculationRequest):
    """計算を実行"""
    try:
        from core import get_registry
        registry = get_registry()
        result = registry.execute(skill_id, request.parameters)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Vercel用ハンドラー
handler = app
