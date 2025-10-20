import os
import requests
from typing import Dict, List, Optional


class DartApiClient:
    BASE_URL = "https://opendart.fss.or.kr/api"

    def __init__(self):
        self.api_key = os.getenv("DART_API_KEY")
        if not self.api_key:
            raise ValueError("DART_API_KEY 환경 변수가 설정되지 않았습니다.")

    def _request_api(self, endpoint: str, params: Dict) -> Optional[List[Dict]]:
        url = f"{self.BASE_URL}/{endpoint}"
        final_params = {"crtfc_key": self.api_key, **params}
        try:
            response = requests.get(url, params=final_params)
            response.raise_for_status()
            data = response.json()
            if data.get("status") != "000":
                if data.get("status") != "013":  # '데이터 없음'은 오류가 아님
                    print(f"DART API Warning: {data.get('message')}")
                return None
            return data.get("list", [])
        except Exception as e:
            print(f"DART API Error: {e}")
            return None

    def get_financial_statements(self, corp_code: str, year: int, reprt_code: str) -> Optional[List[Dict]]:
        """연결재무제표(CFS)를 명시적으로 요청"""
        params = {"corp_code": corp_code, "bsns_year": str(year), "reprt_code": reprt_code, "fs_div": "CFS"}
        return self._request_api("fnlttSinglAcntAll.json", params)

    def get_annual_share_info(self, corp_code: str, year: int) -> Optional[List[Dict]]:
        """연간 사업보고서의 주식 총수 조회"""
        params = {"corp_code": corp_code, "bsns_year": str(year), "reprt_code": "11011"}
        return self._request_api("stockTotqySttus.json", params)


