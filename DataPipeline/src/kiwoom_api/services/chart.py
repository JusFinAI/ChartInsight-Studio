from ..core.client import client
from ..models.chart_data import ChartData
import datetime
import time as time_module
import json
import os

# [개선] 1. 디버깅 플래그 및 RESPONSE_KEY_MAP을 전역 상수로 분리
DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() in ('true', '1', 't')

RESPONSE_KEY_MAP = {
    'ka10081': 'stk_dt_pole_chart_qry',
    'ka10082': 'stk_stk_pole_chart_qry',
    'ka10083': 'stk_mth_pole_chart_qry',
    'ka10080': 'stk_min_pole_chart_qry',
    'ka20006': 'inds_dt_pole_qry',
    'ka20007': 'inds_stk_pole_qry',
    'ka20008': 'inds_mth_pole_qry',
}


def _get_chart_data(chart_type, api_id, params, auto_pagination=True, num_candles=None, output_dir=None, base_date=None):
    result = ChartData(chart_type, output_dir=output_dir)
    cont_yn = 'N'
    next_key = ''
    page_count = 0
    max_pages = 50

    try:
        while True:
            page_count += 1
            print(f"차트 데이터 요청 중: {chart_type}, 페이지: {page_count}")

            try:
                print(f"API 요청: {api_id}, 데이터: {params}")
                response = client.request(
                    endpoint='/api/dostk/chart',
                    api_id=api_id,
                    data=params,
                    cont_yn=cont_yn,
                    next_key=next_key
                )

                # [개선] 2. 디버깅 코드를 조건부로 실행
                if DEBUG_MODE:
                    debug_filename = f'{params.get("inds_cd") or params.get("stk_cd")}-{api_id}.json'
                    with open(debug_filename, 'w', encoding='utf-8') as f:
                        json.dump(response['data'], f, ensure_ascii=False, indent=4)
                    print(f"[디버깅] API 원본 응답을 '{debug_filename}'에 저장했습니다.")

                data = response['data']
                headers = response['headers']

                normalized_cont_yn = headers.get('cont_yn', 'N')
                normalized_next_key = headers.get('next_key', '')

            except Exception as e:
                print(f"API 요청 중 오류 발생: {e}")
                break

            data_key = RESPONSE_KEY_MAP.get(api_id)

            if not data_key or data_key not in data or not data[data_key]:
                print(f"응답에 데이터가 없습니다. 응답 키: {data_key}, API ID: {api_id}")
                break

            result.append(data[data_key])

            if num_candles and len(result.data) >= num_candles:
                result.data = result.data[:num_candles]
                if len(result.data) >= num_candles:
                    break

            if normalized_cont_yn != 'Y' or not auto_pagination or page_count >= max_pages:
                break

            cont_yn = normalized_cont_yn
            next_key = normalized_next_key
            time_module.sleep(0.3)

    except Exception as e:
        print(f"{chart_type} 차트 데이터 수집 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    print(f"차트 데이터 조회 완료: {chart_type}, 페이지: {page_count}, 항목 수: {len(result.data)}")
    return result


def get_daily_stock_chart(stock_code, base_date=None, num_candles=252, modified_price_type='1', auto_pagination=True, output_dir=None):
    params = {'stk_cd': stock_code, 'base_dt': base_date or datetime.datetime.now().strftime('%Y%m%d'), 'upd_stkpc_tp': modified_price_type}
    return _get_chart_data('daily', 'ka10081', params, auto_pagination, num_candles=num_candles, base_date=params['base_dt'], output_dir=output_dir)


def get_weekly_stock_chart(stock_code, base_date=None, num_candles=52, modified_price_type='1', auto_pagination=True, output_dir=None):
    params = {'stk_cd': stock_code, 'base_dt': base_date or datetime.datetime.now().strftime('%Y%m%d'), 'upd_stkpc_tp': modified_price_type}
    return _get_chart_data('weekly', 'ka10082', params, auto_pagination, num_candles=num_candles, base_date=params['base_dt'], output_dir=output_dir)


def get_monthly_stock_chart(stock_code, base_date=None, num_candles=120, modified_price_type='1', auto_pagination=True, output_dir=None):
    params = {'stk_cd': stock_code, 'base_dt': base_date or datetime.datetime.now().strftime('%Y%m%d'), 'upd_stkpc_tp': modified_price_type}
    return _get_chart_data('monthly', 'ka10083', params, auto_pagination, num_candles=num_candles, base_date=params['base_dt'], output_dir=output_dir)


def get_daily_inds_chart(inds_code, base_date=None, num_candles=252, auto_pagination=True, output_dir=None):
    """
    업종/지수 일봉 차트 데이터를 조회합니다. (API ID: ka20006)

    Note: 업종/지수 API는 수정주가 파라미터를 지원하지 않습니다.
    """
    params = {'inds_cd': inds_code, 'base_dt': base_date or datetime.datetime.now().strftime('%Y%m%d')}
    return _get_chart_data('daily', 'ka20006', params, auto_pagination, num_candles=num_candles, base_date=params['base_dt'], output_dir=output_dir)


def get_weekly_inds_chart(inds_code, base_date=None, num_candles=52, auto_pagination=True, output_dir=None):
    """
    업종/지수 주봉 차트 데이터를 조회합니다. (API ID: ka20007)

    Note: 업종/지수 API는 수정주가 파라미터를 지원하지 않습니다.
    """
    params = {'inds_cd': inds_code, 'base_dt': base_date or datetime.datetime.now().strftime('%Y%m%d')}
    return _get_chart_data('weekly', 'ka20007', params, auto_pagination, num_candles=num_candles, base_date=params['base_dt'], output_dir=output_dir)


def get_monthly_inds_chart(inds_code, base_date=None, num_candles=120, auto_pagination=True, output_dir=None):
    """
    업종/지수 월봉 차트 데이터를 조회합니다. (API ID: ka20008)

    Note: 업종/지수 API는 수정주가 파라미터를 지원하지 않습니다.
    """
    params = {'inds_cd': inds_code, 'base_dt': base_date or datetime.datetime.now().strftime('%Y%m%d')}
    return _get_chart_data('monthly', 'ka20008', params, auto_pagination, num_candles=num_candles, base_date=params['base_dt'], output_dir=output_dir)


def get_minute_chart(stock_code, interval, base_date=None, num_candles=77, modified_price_type='1', auto_pagination=True, output_dir=None):
    params = {'stk_cd': stock_code, 'tic_scope': str(interval) if interval else '1', 'upd_stkpc_tp': modified_price_type}
    return _get_chart_data('minute', 'ka10080', params, auto_pagination, num_candles=num_candles, base_date=base_date, output_dir=output_dir)


def get_chart(code: str, timeframe: str, **kwargs):
    """
    코드를 분석하여 적절한 차트 API를 자동으로 호출하는 통합 라우팅 함수.

    Args:
        code (str): 종목코드(6자리) 또는 업종/지수코드(3자리)
        timeframe (str): 'd', 'w', 'mon' 등 시간 주기
        **kwargs: 각 차트 조회 함수에 전달될 추가 파라미터
                 (예: num_candles, base_date 등)

    Returns:
        ChartData: 조회된 차트 데이터 객체
    """
    # 코드 길이가 3이면 업종/지수로 간주
    is_index_or_sector = isinstance(code, str) and len(code) == 3

    if timeframe == 'd':
        return get_daily_inds_chart(inds_code=code, **kwargs) if is_index_or_sector else get_daily_stock_chart(stock_code=code, **kwargs)

    elif timeframe == 'w':
        return get_weekly_inds_chart(inds_code=code, **kwargs) if is_index_or_sector else get_weekly_stock_chart(stock_code=code, **kwargs)

    elif timeframe == 'mon':
        return get_monthly_inds_chart(inds_code=code, **kwargs) if is_index_or_sector else get_monthly_stock_chart(stock_code=code, **kwargs)

    else:
        # 분봉(예: '5m','30m','1h')은 종목 전용이므로 별도 처리 권장
        raise ValueError(f"지원하지 않는 타임프레임: {timeframe}")
