"""
Lambda Gateway - API Gateway互換サーバー

AWS API GatewayとLambda Authorizerの挙動を再現し、
routing.ymlに基づいてリクエストをLambda RIEコンテナに転送します。
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse, Response
from typing import Optional
from datetime import datetime, timezone
import requests

from .config import config
from .core.security import create_access_token, verify_token
from .core.proxy import build_event, proxy_to_lambda, parse_lambda_response
from .models.schemas import AuthRequest, AuthResponse, AuthenticationResult
from .services.route_matcher import load_routing_config, match_route
from .services.container import get_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフサイクル管理"""
    load_routing_config()
    yield


app = FastAPI(
    title="Lambda Gateway", version="2.0.0", lifespan=lifespan, root_path=config.root_path
)


# ===========================================
# エンドポイント定義
# ===========================================


@app.post(config.AUTH_ENDPOINT_PATH, response_model=AuthResponse)
async def authenticate_user(
    request: AuthRequest, response: Response, x_api_key: Optional[str] = Header(None)
):
    """ユーザー認証エンドポイント"""
    if not x_api_key or x_api_key != config.X_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    response.headers["PADMA_USER_AUTHORIZED"] = "true"

    username = request.AuthParameters.USERNAME
    password = request.AuthParameters.PASSWORD

    if username == config.AUTH_USER and password == config.AUTH_PASS:
        id_token = create_access_token(
            username=username,
            secret_key=config.JWT_SECRET_KEY,
            expires_delta=config.JWT_EXPIRES_DELTA,
        )
        return AuthResponse(AuthenticationResult=AuthenticationResult(IdToken=id_token))

    return JSONResponse(
        status_code=401,
        content={"message": "Unauthorized"},
        headers={"PADMA_USER_AUTHORIZED": "true"},
    )


@app.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def gateway_handler(request: Request, path: str):
    """キャッチオールルート：routing.ymlに基づいてLambda RIEに転送"""
    request_path = f"/{path}"

    # ルーティングマッチング
    target_container, path_params, route_path, function_config = match_route(
        request_path, request.method
    )

    if not target_container:
        return JSONResponse(status_code=404, content={"message": "Not Found"})

    # 認証検証
    authorization = request.headers.get("authorization")
    if not authorization:
        return JSONResponse(status_code=401, content={"message": "Unauthorized"})

    user_id = verify_token(authorization, config.JWT_SECRET_KEY)
    if not user_id:
        return JSONResponse(status_code=401, content={"message": "Unauthorized"})

    # オンデマンドコンテナ起動
    try:
        container_host = get_manager().ensure_container_running(
            name=target_container,
            image=function_config.get("image"),
            env=function_config.get("environment", {}),
        )
    except Exception as e:
        print(f"Container start failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"message": "Service Unavailable", "detail": "Cold start failed"},
        )

    # Lambda RIEに転送
    try:
        body = await request.body()
        event = build_event(request, body, user_id, path_params, route_path)
        lambda_response = proxy_to_lambda(container_host, event)

        # レスポンス変換
        result = parse_lambda_response(lambda_response)
        if "raw_content" in result:
            return Response(
                content=result["raw_content"],
                status_code=result["status_code"],
                headers=result["headers"],
            )
        return JSONResponse(
            status_code=result["status_code"], content=result["content"], headers=result["headers"]
        )

    except requests.exceptions.RequestException:
        return JSONResponse(status_code=502, content={"message": "Bad Gateway"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
