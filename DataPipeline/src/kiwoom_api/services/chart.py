from ..core.client import client
from ..models.chart_data import ChartData
import datetime
import time as time_module
import json

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

                # [디버깅] 원본 응답을 파일로 저장
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
            
            RESPONSE_KEY_MAP = {
                'ka10081': 'stk_dt_pole_chart_qry',
                'ka10082': 'stk_stk_pole_chart_qry',
                'ka10083': 'stk_mth_pole_chart_qry',
                'ka10080': 'stk_min_pole_chart_qry',
                'ka20008': 'inds_mth_pole_qry',
            }
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

def get_monthly_inds_chart(inds_code, base_date=None, num_candles=120, auto_pagination=True, output_dir=None):
    params = {'inds_cd': inds_code, 'base_dt': base_date or datetime.datetime.now().strftime('%Y%m%d')}
    return _get_chart_data('monthly', 'ka20008', params, auto_pagination, num_candles=num_candles, base_date=params['base_dt'], output_dir=output_dir)

def get_minute_chart(stock_code, interval, base_date=None, num_candles=77, modified_price_type='1', auto_pagination=True, output_dir=None):
    params = {'stk_cd': stock_code, 'tic_scope': str(interval) if interval else '1', 'upd_stkpc_tp': modified_price_type}
    return _get_chart_data('minute', 'ka10080', params, auto_pagination, num_candles=num_candles, base_date=base_date, output_dir=output_dir)
