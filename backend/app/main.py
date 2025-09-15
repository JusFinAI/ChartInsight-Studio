"""ChartInsight API 백엔드 메인 모듈"""

import time
import uuid
import os
from datetime import datetime
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import sys
from logging.handlers import RotatingFileHandler
# 라우터 임포트
from app.routers import pattern_analysis

# 중앙 로깅 설정 사용
from app.utils.logger_config import get_logger

# 로거 설정
logger = get_logger("chartinsight-api", "api")

# 기존 로그 파일 정리 (30일 이상 지난 로그 파일 삭제)
def cleanup_old_logs(logs_directory, days_to_keep=30):
    """오래된 로그 파일을 삭제합니다"""
    current_time = time.time()
    max_age = days_to_keep * 86400  # 일 -> 초 변환
    
    for filename in os.listdir(logs_directory):
        if filename.startswith("api_") and filename.endswith(".log"):
            file_path = os.path.join(logs_directory, filename)
            file_age = current_time - os.path.getmtime(file_path)
            
            if file_age > max_age:
                try:
                    os.remove(file_path)
                    logger.info(f"오래된 로그 파일 삭제: {filename}")
                except Exception as e:
                    logger.error(f"로그 파일 삭제 실패: {filename}, 에러: {str(e)}")

# 오래된 로그 파일 정리
cleanup_old_logs("logs")

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
        logger.error(f"Request {request_id} failed: {str(e)} - {process_time:.3f} sec")
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