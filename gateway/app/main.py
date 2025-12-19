"""
Lambda Gateway - API Gateway互換サーバー

AWS API GatewayとLambda Authorizerの挙動を再現し、
routing.ymlに基づいてリクエストをLambda RIEコンテナに転送します。
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse, Response
from typing import Optional
from pydantic import BaseModel
import json
import time
import os
import base64
from datetime import datetime, timedelta, timezone
import jwt
import requests

from .config import config

try:
    from .router import load_routing_config, match_route
except ImportError:
    from router import load_routing_config, match_route

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 起動時にルーティング設定を読み込み
    load_routing_config()
    yield

app = FastAPI(title="Lambda Gateway", version="2.0.0", lifespan=lifespan)

# JWT設定
# SECRET_KEY等はconfigから直接参照するためグローバル変数は削除
ALGORITHM = "HS256"

# API Key設定も削除しconfigから参照


# リクエスト/レスポンスモデル
class AuthParameters(BaseModel):
    USERNAME: str
    PASSWORD: str


class AuthRequest(BaseModel):
    AuthParameters: AuthParameters


class AuthenticationResult(BaseModel):
    IdToken: str


class AuthResponse(BaseModel):
    AuthenticationResult: AuthenticationResult


def create_access_token(username: str) -> str:
    """
    JWTトークンを生成
    """
    expire = datetime.now(timezone.utc) + timedelta(seconds=config.JWT_EXPIRES_DELTA)
    to_encode = {
        "sub": username,
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    encoded_jwt = jwt.encode(to_encode, config.JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(authorization: Optional[str] = Header(None)) -> str:
    """
    Lambda Authorizer互換：Authorizationヘッダーを検証してユーザー名を返す
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Unauthorized")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Unauthorized")
    except (jwt.exceptions.DecodeError, jwt.exceptions.PyJWTError):
        raise HTTPException(status_code=401, detail="Unauthorized")
    except ValueError:
        raise HTTPException(status_code=401, detail="Unauthorized")


def build_event(
    request: Request,
    body: bytes,
    user_id: str,
    path_params: dict,
    route_path: str
) -> dict:
    """
    API Gateway Lambda Proxy Integration互換のeventオブジェクトを構築
    """
    # gzip圧縮されているか確認
    is_base64 = "gzip" in request.headers.get("content-encoding", "").lower()
    
    # ボディの処理
    if is_base64:
        body_content = base64.b64encode(body).decode("utf-8")
    else:
        try:
            body_content = body.decode("utf-8")
        except UnicodeDecodeError:
            body_content = base64.b64encode(body).decode("utf-8")
            is_base64 = True
    
    # クエリパラメータ
    query_params = dict(request.query_params) if request.query_params else None
    
    # ヘッダー
    headers = {key: value for key, value in request.headers.items()}
    
    event = {
        "resource": route_path or str(request.url.path),
        "path": str(request.url.path),
        "httpMethod": request.method,
        "headers": headers,
        "queryStringParameters": query_params,
        "pathParameters": path_params if path_params else None,
        "requestContext": {
            "identity": {
                "sourceIp": request.client.host if request.client else "unknown"
            },
            "authorizer": {
                "claims": {
                    "cognito:username": user_id
                },
                "cognito:username": user_id
            },
            "requestId": f"req-{int(time.time() * 1000)}"
        },
        "body": body_content,
        "isBase64Encoded": is_base64
    }
    
    return event


import docker

# Dockerクライアント初期化
docker_client = None
try:
    docker_client = docker.from_env()
except Exception:
    print("Warning: Failed to initialize Docker client. Dynamic IP resolution will better disabled.")


def resolve_container_ip(container_name: str) -> str:
    """
    コンテナ名からIPアドレスを解決
    Gatewayがホストネットワークで動作している場合、
    Dockerネットワーク内のコンテナ名解決ができないため、直接IPを取得する
    """
    global docker_client
    
    # 既にIPアドレス形式の場合はそのまま返す
    if container_name.replace(".", "").isdigit():
        return container_name
        
    if not docker_client:
        try:
            docker_client = docker.from_env()
        except Exception:
            return container_name
            
    try:
        container = docker_client.containers.get(container_name)
        # ネットワーク設定からIPアドレスを取得（最初のネットワークを使用）
        networks = container.attrs["NetworkSettings"]["Networks"]
        for net_name, net_config in networks.items():
            ip = net_config.get("IPAddress")
            if ip:
                return ip
        return container_name
    except Exception as e:
        print(f"Failed to resolve IP for container {container_name}: {e}")
        return container_name


def proxy_to_lambda(target_container: str, event: dict) -> requests.Response:
    """
    Lambda RIEコンテナにリクエストを転送
    
    Args:
        target_container: routing.ymlで定義されたコンテナ名
        event: 構築されたeventオブジェクト
    
    Returns:
        Lambda RIEからのレスポンス
    """
    # コンテナ名からIPを解決
    host = resolve_container_ip(target_container)
    
    rie_url = f"http://{host}:8080/2015-03-31/functions/function/invocations"
    
    headers = {"Content-Type": "application/json"}
    
    response = requests.post(
        rie_url,
        data=json.dumps(event),
        headers=headers,
        timeout=30
    )
    
    return response


# ===========================================
# エンドポイント定義
# ===========================================

@app.post(config.AUTH_ENDPOINT_PATH, response_model=AuthResponse)
async def authenticate_user(
    request: AuthRequest,
    response: Response,
    x_api_key: Optional[str] = Header(None)
):
    """
    ユーザー認証エンドポイント（認証不要）
    """
    if not x_api_key or x_api_key != config.X_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    response.headers["PADMA_USER_AUTHORIZED"] = "true"
    
    username = request.AuthParameters.USERNAME
    password = request.AuthParameters.PASSWORD
    
    # DB照合ロジック (Configベースの簡易認証)
    if username == config.AUTH_USER and password == config.AUTH_PASS:
        id_token = create_access_token(username)
        return AuthResponse(
            AuthenticationResult=AuthenticationResult(IdToken=id_token)
        )
    
    return JSONResponse(
        status_code=401,
        content={"message": "Unauthorized"},
        headers={"PADMA_USER_AUTHORIZED": "true"}
    )


@app.get("/health")
async def health_check():
    """
    ヘルスチェックエンドポイント（認証不要）
    """
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def gateway_handler(request: Request, path: str):
    """
    キャッチオールルート：routing.ymlに基づいてLambda RIEに転送
    """
    request_path = f"/{path}"
    
    # ルーティングマッチング
    target_container, path_params, route_path = match_route(request_path, request.method)
    
    if not target_container:
        return JSONResponse(
            status_code=404,
            content={"message": "Not Found"}
        )
    
    # 認証検証
    authorization = request.headers.get("authorization")
    try:
        user_id = verify_token(authorization)
    except HTTPException:
        return JSONResponse(
            status_code=401,
            content={"message": "Unauthorized"}
        )
    
    # リクエストボディを取得
    body = await request.body()
    
    # eventオブジェクトを構築
    event = build_event(request, body, user_id, path_params, route_path)
    
    # Lambda RIEに転送
    try:
        lambda_response = proxy_to_lambda(target_container, event)
        
        # Lambdaからのレスポンスを返却
        try:
            response_data = lambda_response.json()
            
            # Lambda応答がAPI Gateway形式の場合
            if isinstance(response_data, dict) and "statusCode" in response_data:
                status_code = response_data.get("statusCode", 200)
                response_headers = response_data.get("headers", {})
                response_body = response_data.get("body", "")
                
                # bodyがJSON文字列の場合はパース
                if isinstance(response_body, str):
                    try:
                        response_body = json.loads(response_body)
                    except json.JSONDecodeError:
                        pass
                
                return JSONResponse(
                    status_code=status_code,
                    content=response_body,
                    headers=response_headers
                )
            else:
                return JSONResponse(content=response_data)
                
        except json.JSONDecodeError:
            return Response(
                content=lambda_response.content,
                status_code=lambda_response.status_code,
                headers=dict(lambda_response.headers)
            )
            
    except requests.exceptions.RequestException as e:
        return JSONResponse(
            status_code=502,
            content={"message": "Bad Gateway"}
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
