import os
import time
import random
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import requests
from typing import Dict, List, Optional


class DartApiClient:
    BASE_URL = "https://opendart.fss.or.kr/api"
    # Retry/backoff settings
    MAX_RETRIES = 5
    BASE_DELAY = 1  # seconds
    MAX_DELAY = 60  # seconds

    def __init__(self):
        self.api_key = os.getenv("DART_API_KEY")
        if not self.api_key:
            raise ValueError("DART_API_KEY 환경 변수가 설정되지 않았습니다.")

    def _request_api(self, endpoint: str, params: Dict) -> Optional[List[Dict]]:
        url = f"{self.BASE_URL}/{endpoint}"
        final_params = {"crtfc_key": self.api_key, **params}
        attempt = 0
        while True:
            try:
                response = requests.get(url, params=final_params, timeout=30)
            except requests.RequestException as e:
                # Network-level error: retry with backoff
                attempt += 1
                if attempt > self.MAX_RETRIES:
                    print(f"DART API Error (network): {e} - exceeded max retries")
                    return None
                delay = min(self.BASE_DELAY * (2 ** (attempt - 1)), self.MAX_DELAY)
                # jitter +/-20%
                jitter = random.uniform(-0.2 * delay, 0.2 * delay)
                sleep_for = max(0.0, delay + jitter)
                print(f"DART API network error: {e}. retrying in {sleep_for:.1f}s (attempt {attempt})")
                time.sleep(sleep_for)
                continue

            # If we get a response, check status codes
            if response.status_code == 200:
                try:
                    data = response.json()
                except Exception as e:
                    print(f"DART API Error: invalid JSON response: {e}")
                    return None

                if data.get("status") != "000":
                    message = data.get('message', '') or ''
                    # If it's '데이터 없음' treat as non-error
                    if data.get("status") == "013":
                        return None

                    # If message indicates rate-limit or quota exceeded, treat as retryable
                    lower_msg = message.lower()
                    retry_keywords = ['사용한도', '한도', 'rate limit', 'quota exceeded', 'too many requests', '한도를 초과']
                    if any(k in lower_msg for k in retry_keywords):
                        # treat like HTTP 429: enter retry/backoff loop
                        attempt += 1
                        if attempt > self.MAX_RETRIES:
                            print(f"DART API Warning: {message} - exceeded max retries")
                            return None

                        # Use a similar backoff strategy
                        delay = min(self.BASE_DELAY * (2 ** (attempt - 1)), self.MAX_DELAY)
                        jitter = random.uniform(-0.2 * delay, 0.2 * delay)
                        sleep_for = max(0.0, delay + jitter)
                        print(f"DART API rate-limit message received: '{message}'. retrying in {sleep_for:.1f}s (attempt {attempt})")
                        time.sleep(sleep_for)
                        continue
                    else:
                        # Non-retryable API warning/message
                        print(f"DART API Warning: {message}")
                        return None
                return data.get("list", [])

            # Handle retryable HTTP status codes (rate limiting / service unavailable)
            if response.status_code in (429, 503):
                attempt += 1
                if attempt > self.MAX_RETRIES:
                    print(f"DART API Error: HTTP {response.status_code} - exceeded max retries")
                    return None

                # Respect Retry-After header if present
                retry_after = response.headers.get('Retry-After')
                sleep_for = None
                if retry_after:
                    try:
                        # If numeric seconds
                        sleep_for = int(retry_after)
                    except Exception:
                        try:
                            dt = parsedate_to_datetime(retry_after)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            sleep_for = max(0, (dt - datetime.now(timezone.utc)).total_seconds())
                        except Exception:
                            sleep_for = None

                if sleep_for is None:
                    delay = min(self.BASE_DELAY * (2 ** (attempt - 1)), self.MAX_DELAY)
                    jitter = random.uniform(-0.2 * delay, 0.2 * delay)
                    sleep_for = max(0.0, delay + jitter)

                print(f"DART API HTTP {response.status_code}. retrying in {sleep_for:.1f}s (attempt {attempt})")
                time.sleep(sleep_for)
                continue

            # Other non-success codes: log and return None
            try:
                response.raise_for_status()
            except Exception as e:
                print(f"DART API Error: HTTP {response.status_code} - {e}")
            return None

    def get_financial_statements(self, corp_code: str, year: int, reprt_code: str) -> Optional[List[Dict]]:
        """연결재무제표(CFS)를 명시적으로 요청"""
        params = {"corp_code": corp_code, "bsns_year": str(year), "reprt_code": reprt_code, "fs_div": "CFS"}
        return self._request_api("fnlttSinglAcntAll.json", params)

    def get_annual_share_info(self, corp_code: str, year: int) -> Optional[List[Dict]]:
        """연간 사업보고서의 주식 총수 조회"""
        params = {"corp_code": corp_code, "bsns_year": str(year), "reprt_code": "11011"}
        return self._request_api("stockTotqySttus.json", params)


