import pandas as pd
import requests
import zipfile
import io
import os
from pathlib import Path
import xml.etree.ElementTree as ET
import logging

logger = logging.getLogger(__name__)

# --- 설정 ---
CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cache"
CACHE_FILE = CACHE_DIR / "dart_corp_code_map.csv"
DART_API_KEY = os.getenv("DART_API_KEY")
CORP_CODE_URL = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={DART_API_KEY}"

def _fetch_and_save_corp_code_map():
    """DART에서 전체 고유번호 XML을 다운로드하여 파싱 후 CSV로 저장합니다."""
    if not DART_API_KEY:
        logger.error("DART_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
        raise ValueError("DART_API_KEY is not set.")

    logger.info("DART에서 전체 법인 고유번호 맵을 다운로드합니다...")
    try:
        response = requests.get(CORP_CODE_URL)
        response.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            with z.open('CORPCODE.xml') as f:
                tree = ET.parse(f)
                root = tree.getroot()

        corp_list = []
        for item in root.findall('./list'):
            corp_code = item.find('corp_code').text
            corp_name = item.find('corp_name').text
            stock_code = item.find('stock_code').text
            modify_date = item.find('modify_date').text

            if stock_code and stock_code.strip():
                corp_list.append({
                    'corp_code': corp_code,
                    'corp_name': corp_name,
                    'stock_code': stock_code.strip(),
                    'modify_date': modify_date
                })

        df = pd.DataFrame(corp_list)

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(CACHE_FILE, index=False, encoding='utf-8-sig')
        logger.info(f"성공적으로 {len(df)}개의 상장 법인 정보를 '{CACHE_FILE}'에 저장했습니다.")
        return df

    except requests.exceptions.RequestException as e:
        logger.error(f"DART API 요청 실패: {e}")
        raise
    except Exception as e:
        logger.error(f"법인 고유번호 맵 처리 중 오류 발생: {e}")
        raise

def get_corp_code_map(force_update: bool = False) -> pd.DataFrame:
    """캐시된 DART 고유번호 맵을 DataFrame으로 로드합니다."""
    if not CACHE_FILE.exists() or force_update:
        return _fetch_and_save_corp_code_map()
    else:
        logger.info(f"캐시된 법인 고유번호 맵을 '{CACHE_FILE}'에서 로드합니다.")
        return pd.read_csv(CACHE_FILE, dtype={'stock_code': str})

def get_corp_code(stock_code: str, corp_map: pd.DataFrame) -> str | None:
    """DataFrame 맵에서 stock_code에 해당하는 corp_code를 조회합니다."""
    if corp_map.empty:
        return None
    # Normalize stock_code to 6-digit string (e.g., '20' -> '000020') to match CSV formatting
    stock_code_norm = str(stock_code).zfill(6)
    result = corp_map[corp_map['stock_code'] == stock_code_norm]

    if not result.empty:
        corp_code = result.iloc[0]['corp_code']
        # Ensure corp_code is always zero-padded to 8 characters for downstream callers
        corp_code_padded = str(corp_code).zfill(8)
        logger.debug(
            f"corp_map lookup: stock_code={stock_code} (normalized={stock_code_norm}) -> corp_code={corp_code} (padded={corp_code_padded})"
        )
        return corp_code_padded
    else:
        logger.debug(f"corp_map lookup: stock_code={stock_code} (normalized={stock_code_norm}) -> corp_code=None")
        return None


