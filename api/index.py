"""
Vercel Serverless Function Entry Point

フロントエンドUI + バックエンドAPIへのプロキシ
計算処理はローカルサーバー（BACKEND_URL）に転送される

環境変数:
    BACKEND_URL: ローカルサーバーのURL（例: https://xxxx.ngrok-free.app）
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Any

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

# バックエンドURL（環境変数から取得）
BACKEND_URL = os.environ.get("BACKEND_URL", "")


# ==================== FastAPI App ====================

app = FastAPI(
    title="ChemEng API",
    description="化学工学計算API - 物性推算、物質収支、蒸留塔設計など",
    version="0.2.0",
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


# ==================== Proxy Helper ====================

async def proxy_request(request: Request, path: str):
    """リクエストをバックエンドサーバーに転送"""
    if not BACKEND_URL:
        raise HTTPException(
            status_code=503,
            detail="Backend server not configured. Set BACKEND_URL environment variable."
        )

    if not HTTPX_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="httpx not installed. Cannot proxy requests."
        )

    url = f"{BACKEND_URL.rstrip('/')}/{path.lstrip('/')}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            body = await request.body()
            headers = {
                k: v for k, v in request.headers.items()
                if k.lower() not in ("host", "content-length")
            }

            response = await client.request(
                method=request.method,
                url=url,
                content=body,
                headers=headers,
            )

            return JSONResponse(
                content=response.json(),
                status_code=response.status_code,
            )
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Backend server timeout")
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Cannot connect to backend server")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Backend error: {str(e)}")


# ==================== Endpoints ====================

@app.get("/")
def root():
    """API情報"""
    engine_names = []
    try:
        from engines import get_available_engines
        engines = get_available_engines()
        engine_names = [e.name for e in engines]
    except Exception:
        pass

    if BACKEND_URL:
        mode = "proxy"
        backend_status = "configured"
    elif engine_names:
        mode = "full"
        backend_status = "not configured (using local engines)"
    else:
        mode = "lightweight"
        backend_status = "not configured"

    return {
        "name": "ChemEng API",
        "version": "0.2.0",
        "description": "化学工学計算API",
        "mode": mode,
        "backend_url": BACKEND_URL or None,
        "backend_status": backend_status,
        "available_engines": engine_names if engine_names else None,
        "endpoints": {
            "/api/v1/engines": "利用可能なエンジン一覧",
            "/api/v1/skills": "利用可能なスキル一覧",
            "/api/v1/property": "物性値取得 (POST)",
            "/api/v1/calculate/{skill_id}": "計算実行 (POST)",
        },
    }


@app.get("/api/v1/engines")
async def list_engines(request: Request):
    """利用可能なエンジン一覧"""
    if BACKEND_URL and HTTPX_AVAILABLE:
        return await proxy_request(request, "/api/v1/engines")

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
async def list_skills(request: Request):
    """利用可能なスキル一覧"""
    if BACKEND_URL and HTTPX_AVAILABLE:
        return await proxy_request(request, "/api/v1/skills")

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
async def get_skill(skill_id: str, request: Request):
    """スキル詳細"""
    if BACKEND_URL and HTTPX_AVAILABLE:
        return await proxy_request(request, f"/api/v1/skills/{skill_id}")

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
async def get_property(request: Request):
    """物性値を取得"""
    if BACKEND_URL and HTTPX_AVAILABLE:
        return await proxy_request(request, "/api/v1/property")

    body = await request.json()
    prop_request = PropertyRequest(**body)

    try:
        from engines import select_engine

        engine = select_engine(substance=prop_request.substance, property_name=prop_request.property)
        if engine is None:
            raise HTTPException(
                status_code=503,
                detail="No calculation engine available."
            )

        conditions = {}
        if prop_request.temperature:
            conditions["temperature"] = prop_request.temperature
        if prop_request.pressure:
            conditions["pressure"] = prop_request.pressure

        value = engine.get_property(prop_request.substance, prop_request.property, conditions)

        return {
            "success": True,
            "substance": prop_request.substance,
            "property": prop_request.property,
            "value": value,
            "conditions": conditions,
            "engine": engine.name,
        }
    except Exception as e:
        return {
            "success": False,
            "substance": prop_request.substance,
            "property": prop_request.property,
            "error": str(e),
        }


@app.post("/api/v1/calculate/{skill_id}")
async def calculate(skill_id: str, request: Request):
    """計算を実行"""
    if BACKEND_URL and HTTPX_AVAILABLE:
        return await proxy_request(request, f"/api/v1/calculate/{skill_id}")

    body = await request.json()
    calc_request = CalculationRequest(**body)

    try:
        from core import get_registry
        registry = get_registry()
        result = registry.execute(skill_id, calc_request.parameters)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Vercel用ハンドラー
handler = app
