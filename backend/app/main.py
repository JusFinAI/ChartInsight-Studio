"""ChartInsight API 백엔드 메인 모듈"""

import time
import uuid
import logging
from datetime import datetime
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# === 로깅 시스템 초기화 (앱 시작 시 가장 먼저 실행) ===
from app.utils.logger_config import setup_logging

# 로깅 시스템 설정 (전체 앱에서 한 번만 실행)
setup_logging(log_level="INFO")

# 이후 모든 모듈에서 표준 방식으로 로거 사용
logger = logging.getLogger(__name__)

# 라우터 임포트
from app.routers import pattern_analysis

# FastAPI 앱 인스턴스 생성
app = FastAPI(title="ChartInsight API")

# CORS 설정 - 개발 중에는 모든 도메인에서 접근 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# 요청 로깅 미들웨어
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    # 요청 정보 로깅
    logger.info(f"Request {request_id} started: {request.method} {request.url.path}?{request.url.query}")
    
    # 다음 미들웨어 또는 엔드포인트 호출
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # 응답 정보 로깅
        logger.info(f"Request {request_id} completed: {response.status_code} - {process_time:.3f} sec")
        
        # 응답 헤더에 처리 시간 추가
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as e:
        process_time = time.time() - start_time
        # 예외 발생 시 전체 스택 트레이스를 로그에 자동 기록
        logger.exception(f"Request {request_id} failed - {process_time:.3f} sec")
        return JSONResponse(
            status_code=500,
            content={"message": "Internal server error"}
        )

# 라우터 등록
app.include_router(pattern_analysis.router, prefix="/api/v1")

# 새로운 엔드포인트 등록 (프론트엔드 호환)
from app.routers.pattern_analysis import (
    get_chart_data, 
    get_js_points, 
    get_patterns, 
    get_price_levels, 
    get_market_data,
    get_trading_radar_data
)

# 프론트엔드 호환 라우트 등록
app.add_api_route("/chart-data", get_chart_data, methods=["GET"])
app.add_api_route("/js-points", get_js_points, methods=["GET"])
app.add_api_route("/patterns", get_patterns, methods=["GET"])
app.add_api_route("/price-levels", get_price_levels, methods=["GET"])
app.add_api_route("/market-data", get_market_data, methods=["GET"])
app.add_api_route("/trading-radar-data", get_trading_radar_data, methods=["GET"])

# 루트 엔드포인트
@app.get("/")
def read_root():
    """API 루트 엔드포인트"""
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to ChartInsight API"}

# 상태 확인 엔드포인트
@app.get("/health")
def health_check():
    """API 상태 확인 엔드포인트"""
    logger.info("Health check performed")
    return {"status": "healthy", "version": "1.0.0"}

# 앱이 직접 실행되는 경우
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting ChartInsight API server")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)