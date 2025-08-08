"""데이터 캐싱 유틸리티"""

import time
from typing import Dict, Any, Tuple, Optional
import logging

# 로거 설정
logger = logging.getLogger("chartinsight-api.cache")

class SimpleCache:
    """간단한 메모리 기반 캐시 클래스"""
    
    def __init__(self, expire_seconds=300):  # 기본 5분 캐싱
        """
        SimpleCache 초기화
        
        Args:
            expire_seconds (int): 캐시 만료 시간(초)
        """
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.expire_seconds = expire_seconds
        logger.info(f"SimpleCache 초기화 완료 (만료 시간: {expire_seconds}초)")
    
    def get(self, key: str) -> Optional[Any]:
        """
        캐시에서 값 조회
        
        Args:
            key (str): 캐시 키
            
        Returns:
            Optional[Any]: 캐시된 값 또는 None (캐시 미스 시)
        """
        if key not in self.cache:
            logger.debug(f"캐시 미스: {key}")
            return None
        
        value, timestamp = self.cache[key]
        # 만료 시간 확인
        if time.time() - timestamp > self.expire_seconds:
            del self.cache[key]
            logger.debug(f"캐시 만료: {key}")
            return None
        
        logger.debug(f"캐시 히트: {key}")
        return value
    
    def set(self, key: str, value: Any) -> None:
        """
        캐시에 값 저장
        
        Args:
            key (str): 캐시 키
            value (Any): 저장할 값
        """
        self.cache[key] = (value, time.time())
        logger.debug(f"캐시 저장: {key}")
    
    def clear(self) -> None:
        """캐시 전체 삭제"""
        count = len(self.cache)
        self.cache.clear()
        logger.info(f"캐시 전체 삭제 ({count}개 항목)")
        
    def get_stats(self) -> Dict[str, Any]:
        """
        캐시 통계 정보 반환
        
        Returns:
            Dict[str, Any]: 캐시 통계 정보
        """
        current_time = time.time()
        active_items = 0
        expired_items = 0
        
        for _, (_, timestamp) in self.cache.items():
            if current_time - timestamp <= self.expire_seconds:
                active_items += 1
            else:
                expired_items += 1
                
        return {
            "total_items": len(self.cache),
            "active_items": active_items,
            "expired_items": expired_items,
            "expire_seconds": self.expire_seconds
        }

# 싱글톤 인스턴스 생성
data_cache = SimpleCache() 