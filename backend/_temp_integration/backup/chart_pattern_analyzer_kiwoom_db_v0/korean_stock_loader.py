# Minimal shim for korean_stock_loader used by main_dashboard
from typing import List, Dict, Any, Tuple

def get_category_options():
    return [
        {'label': 'KOSPI', 'value': 'KOSPI'},
        {'label': 'KOSDAQ', 'value': 'KOSDAQ'}
    ]


def get_symbols_by_category():
    # Provide minimal sample options; real implementation will be used in production
    kospi = [{'label': '삼성전자', 'value': '005930'}, {'label': '현대차', 'value': '005380'}]
    kosdaq = [{'label': '카카오', 'value': '035720'}]
    return {'KOSPI': kospi, 'KOSDAQ': kosdaq}


def get_interval_options():
    return [
        {'label': '5분봉', 'value': '5m'},
        {'label': '30분봉', 'value': '30m'},
        {'label': '1시간봉', 'value': '1h'},
        {'label': '일봉', 'value': '1d'},
        {'label': '주봉', 'value': '1wk'}
    ]


def get_default_values():
    return ('KOSPI', '005930', '1d')
