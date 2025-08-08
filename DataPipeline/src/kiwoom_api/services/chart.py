from ..core.client import client
from ..models.chart_data import ChartData
# from ..utils import get_today # 이 라인을 삭제하거나 주석 처리합니다.
import datetime
import re
import pandas as pd
import time as time_module  # time 모듈과 변수명 충돌 방지
import json  # 응답 구조 출력을 위한 json 모듈 추가


class ChartService:
    """차트 데이터 서비스"""
    
    def __init__(self):
        self.endpoint = '/api/dostk/chart'
    
    def get_daily_chart(self, stock_code, base_date=None, num_candles=252, 
                        modified_price_type='1', auto_pagination=True, output_dir=None):
        """
        일봉 차트 데이터를 조회합니다.
        
        Args:
            stock_code (str): 종목 코드
            base_date (str, optional): 기준 일자(YYYYMMDD). 기본값은 오늘.
            num_candles (int, optional): 조회할 캔들 개수. 기본값은 252개(약 1년).
            modified_price_type (str, optional): 수정주가구분(0: 원주가, 1: 수정주가). 기본값은 '1'.
            auto_pagination (bool, optional): 연속 조회 자동 처리 여부. 기본값은 True.
            output_dir (str, optional): CSV 파일 저장 경로. 기본값은 None.
            
        Returns:
            ChartData: 일봉 차트 데이터
        """
        # 현재 날짜 (오늘)
        today = datetime.datetime.now().strftime('%Y%m%d')  # 시스템 날짜 직접 사용
        
        # 기준일 설정 (기본값: 오늘)
        if base_date is None:
            base_date = today
        else:
            base_date = self._format_date(base_date)
            
        # 기준일이 미래인 경우 오늘로 조정
        if base_date > today:
            print(f"기준일({base_date})이 미래입니다. 오늘({today})로 조정합니다.")
            base_date = today
            
        print(f"일봉 차트 조회: {stock_code}, 기준일: {base_date}, 캔들 개수: {num_candles}")
        
        # 요청 데이터 구성
        params = {
            'stk_cd': stock_code,
            'base_dt': base_date,       # 기준일자
            'upd_stkpc_tp': modified_price_type,
        }
        
        # API ID 설정
        api_id = 'ka10081'
        
        return self._get_chart_data('daily', api_id, params, auto_pagination, 
                                    num_candles=num_candles, base_date=base_date, output_dir=output_dir)
    
    def get_minute_chart(self, stock_code, base_date=None, time_interval='1', 
                         num_candles=77, market_time='N', modified_price_type='1', 
                         auto_pagination=True, output_dir=None):
        """
        분봉 차트 데이터를 조회합니다.
        
        Args:
            stock_code (str): 종목 코드
            base_date (str, optional): 기준 일자(YYYYMMDD). 기본값은 오늘.
            time_interval (str, optional): 시간간격(1: 1분, 3: 3분, 5: 5분, 10: 10분, 30: 30분, 60: 60분). 기본값은 '1'.
            num_candles (int, optional): 조회할 캔들 개수. 기본값은 77개.
            market_time (str, optional): 장구분(N: 전체, 1: 장중, 2: 시간외). 기본값은 'N'.
            modified_price_type (str, optional): 수정주가구분(0: 원주가, 1: 수정주가). 기본값은 '1'.
            auto_pagination (bool, optional): 연속 조회 자동 처리 여부. 기본값은 True.
            output_dir (str, optional): CSV 파일 저장 경로. 기본값은 None.
            
        Returns:
            ChartData: 분봉 차트 데이터
        """
        # 현재 날짜 (오늘) - 시스템 시간 직접 사용
        today = datetime.datetime.now().strftime('%Y%m%d')
        now_time = datetime.datetime.now().strftime('%H%M%S')
        
        print(f"시스템 현재 날짜: {today}, 현재 시간: {now_time}")
        
        # 기준일자 설정 (기본값: 오늘)
        if base_date is None:
            base_date = today
        else:
            base_date = self._format_date(base_date)
        
        # 기준일이 미래인 경우 오늘로 조정
        if base_date > today:
            print(f"기준일({base_date})이 미래입니다. 오늘({today})로 조정합니다.")
            base_date = today
            
        print(f"분봉 차트 조회: {stock_code}, 기준일: {base_date}, 시간간격: {time_interval}분, 캔들 개수: {num_candles}")
        
        # 요청 데이터 구성 - ka10080 API 형식 사용
        params = {
            'stk_cd': stock_code,          # 종목코드
            'tic_scope': time_interval,    # 틱범위 (분봉 간격)
            'upd_stkpc_tp': modified_price_type, # 수정주가구분
        }
        
        # API ID 설정
        api_id = 'ka10080'
        
        print(f"API ID: {api_id}, 파라미터: {params}")
        
        result = self._get_chart_data('minute', api_id, params, auto_pagination, 
                                     num_candles=num_candles, base_date=base_date, 
                                     output_dir=output_dir)
        
        # 추가 전처리 설정
        result.preprocessing_required = True
        
        # 시간 필드 처리 (시간 필드가 없는 경우 추가)
        if result.data:
            for item in result.data:
                # cntr_tm 필드 처리 (reference code 방식)
                if 'cntr_tm' in item:
                    timestamp = item['cntr_tm']
                    if len(timestamp) == 14:  # YYYYMMDDHHMMSS 형식인 경우
                        item['date'] = timestamp[:8]      # YYYYMMDD
                        item['time'] = timestamp[8:14]    # HHMMSS
                    else:
                        print(f"cntr_tm 필드 형식 오류: {timestamp}")
                
                # 날짜 필드 확인
                elif 'stck_bsop_date' in item:
                    item['date'] = item['stck_bsop_date']
                elif 'dt' in item:
                    item['date'] = item['dt']
                    
                # 시간 필드 확인
                if 'stck_cntg_hour' in item:
                    item['time'] = item['stck_cntg_hour']
                elif 'tm' in item:
                    item['time'] = item['tm']
                elif 'time' not in item:
                    # 시간 정보가 없는 경우 빈 값 설정
                    item['time'] = '000000'
        
        return result
    
    def get_weekly_chart(self, stock_code, base_date=None, num_candles=52, 
                        modified_price_type='1', auto_pagination=True, output_dir=None):
        """
        주봉 차트 데이터를 조회합니다.
        
        Args:
            stock_code (str): 종목 코드
            base_date (str, optional): 기준 일자(YYYYMMDD). 기본값은 오늘.
            num_candles (int, optional): 조회할 캔들 개수. 기본값은 52개(약 1년).
            modified_price_type (str, optional): 수정주가구분(0: 원주가, 1: 수정주가). 기본값은 '1'.
            auto_pagination (bool, optional): 연속 조회 자동 처리 여부. 기본값은 True.
            output_dir (str, optional): CSV 파일 저장 경로. 기본값은 None.
            
        Returns:
            ChartData: 주봉 차트 데이터
        """
        # 현재 날짜 (오늘)
        today = datetime.datetime.now().strftime('%Y%m%d')  # 시스템 날짜 직접 사용
        
        # 기준일 설정 (기본값: 오늘)
        if base_date is None:
            base_date = today
        else:
            base_date = self._format_date(base_date)
            
        # 기준일이 미래인 경우 오늘로 조정
        if base_date > today:
            print(f"기준일({base_date})이 미래입니다. 오늘({today})로 조정합니다.")
            base_date = today
            
        print(f"주봉 차트 조회: {stock_code}, 기준일: {base_date}, 캔들 개수: {num_candles}")
        
        # 요청 데이터 구성
        params = {
            'stk_cd': stock_code,      # 종목코드
            'base_dt': base_date,       # 기준일자
            'upd_stkpc_tp': modified_price_type,  # 수정주가구분
        }
        
        # API ID 설정
        api_id = 'ka10082'
        
        return self._get_chart_data('weekly', api_id, params, auto_pagination, 
                                    num_candles=num_candles, base_date=base_date, output_dir=output_dir)
    
    def _get_chart_data(self, chart_type, api_id, params, auto_pagination=True, num_candles=None, output_dir=None, base_date=None):
        """
        차트 데이터를 조회하는 내부 메서드
        
        Args:
            chart_type (str): 차트 유형 ('daily', 'minute', 'weekly')
            api_id (str): API ID
            params (dict): 요청 파라미터
            auto_pagination (bool): 연속 조회 자동 처리 여부
            num_candles (int, optional): 조회할 캔들 개수. None이면 모든 데이터 조회.
            output_dir (str, optional): CSV 파일 저장 경로. ChartData 객체로 전달.
            base_date (str, optional): 기준일자 (YYYYMMDD)
            
        Returns:
            ChartData: 차트 데이터
        """
        result = ChartData(chart_type, output_dir=output_dir)
        cont_yn = 'N'
        next_key = ''
        page_count = 0
        max_pages = 50  # 최대 요청 페이지 수 제한
        today = datetime.datetime.now().strftime('%Y%m%d')  # 시스템 날짜 직접 사용
        target_reached = False  # 목표 캔들 개수 도달 플래그
        
        try:
            while True:
                page_count += 1
                print(f"차트 데이터 요청 중: {chart_type}, 페이지: {page_count}")
                
                # API 요청
                try:
                    print(f"API 요청: {api_id}, 데이터: {params}")
                    response = client.request(
                        endpoint=self.endpoint,
                        api_id=api_id,
                        data=params,
                        cont_yn=cont_yn,
                        next_key=next_key
                    )
                    
                    # 응답 데이터 가져오기
                    data = response['data']
                    headers = response['headers']
                    
                    # 응답 헤더 확인
                    print(f"응답 헤더: {json.dumps({key: headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=2, ensure_ascii=False)}")
                    
                except Exception as e:
                    print(f"API 요청 중 오류 발생: {e}")
                    if page_count == 1:  # 첫 번째 요청이 실패한 경우
                        return result
                    break  # 이후 요청 실패는 지금까지 수집된 데이터로 계속 진행
                
                # 데이터 키 찾기
                data_key = None
                possible_keys = ['stk_dt_pole_chart_qry', 'stk_min_pole_chart_qry', 'stk_stk_pole_chart_qry']
                
                if api_id == 'ka10080':  # 틱 범위 기준 분봉 API
                    print(f"ka10080 API 응답 구조 확인: {list(data.keys())}")
                elif api_id == 'ka10082':  # 주봉 API
                    print(f"ka10082 API 응답 구조 확인: {list(data.keys())}")
                    if 'stk_stk_pole_chart_qry' in data:
                        data_key = 'stk_stk_pole_chart_qry'
                        print(f"주봉 데이터 키 찾음: {data_key}")
                        if data[data_key] and len(data[data_key]) > 0:
                            print(f"주봉 첫 항목: {json.dumps(data[data_key][0], indent=2, ensure_ascii=False)}")
                
                for key in possible_keys:
                    if key in data and isinstance(data[key], list) and len(data[key]) > 0:
                        data_key = key
                        print(f"데이터 키 찾음: {key}")
                        break
                
                # 응답 결과가 비어있으면 종료
                if not data_key or not data[data_key]:
                    print(f"응답에 데이터가 없습니다. 가능한 키: {', '.join(possible_keys)}")
                    print(f"응답 구조: {list(data.keys())}")
                    
                    # 첫 번째 페이지에서 데이터가 없으면 응답 전체 구조 출력
                    if page_count == 1:
                        print(f"첫 페이지 응답 구조: {json.dumps(data, indent=2, ensure_ascii=False)[:1000]}")  # 처음 1000자만 출력
                    break
                
                # 데이터 처리
                filtered_data = []
                
                if data[data_key] and len(data[data_key]) > 0:
                    first_item = data[data_key][0]
                    last_item = data[data_key][-1]
                    print(f"첫 번째 항목 구조: {json.dumps(first_item, indent=2, ensure_ascii=False)}")
                    print(f"마지막 항목 구조: {json.dumps(last_item, indent=2, ensure_ascii=False)}")
                    
                    # cntr_tm 필드 확인 (분봉용)
                    if 'cntr_tm' in first_item:
                        print("cntr_tm 필드 발견, timestamp 형식 사용")
                        
                        for item in data[data_key]:
                            if 'cntr_tm' in item:
                                timestamp = item['cntr_tm']
                                
                                # 14자리인 경우 (YYYYMMDDHHMMSS)
                                if len(timestamp) == 14:
                                    date = timestamp[:8]      # YYYYMMDD
                                    time_str = timestamp[8:14]    # HHMMSS
                                    
                                    # 미래 데이터 필터링
                                    if date > today:
                                        continue
                                    
                                    # 전처리용 필드 추가
                                    item_copy = item.copy()
                                    item_copy['date'] = date
                                    item_copy['time'] = time_str
                                    filtered_data.append(item_copy)
                        
                        if filtered_data:
                            print(f"{len(filtered_data)}개 데이터가 cntr_tm 필드로 처리됨")
                    else:
                        # 기존 방식 (개별 필드 확인)
                        date_field = None
                        time_field = None
                        
                        if 'dt' in first_item:
                            date_field = 'dt'
                        elif 'stck_bsop_date' in first_item:
                            date_field = 'stck_bsop_date'
                        elif 'cntg_date' in first_item:
                            date_field = 'cntg_date'
                        
                        if 'tm' in first_item:
                            time_field = 'tm'
                        elif 'stck_cntg_hour' in first_item:
                            time_field = 'stck_cntg_hour'
                        elif 'cntg_time' in first_item:
                            time_field = 'cntg_time'
                        
                        print(f"날짜 필드: {date_field}, 시간 필드: {time_field}")
                        
                        for item in data[data_key]:
                            if date_field and date_field not in item:
                                continue
                                
                            # 날짜 필드가 있는 경우 필터링
                            if date_field:
                                date = item[date_field]
                                
                                # 미래 데이터 필터링
                                if date > today:
                                    continue
                            
                            filtered_data.append(item)
                
                # 데이터 추가
                result.append(filtered_data)
                
                print(f"페이지 {page_count}: {len(filtered_data)}개 데이터 추가 (전체: {len(result.data)}개)")
                
                # base_date 필터링 및 num_candles 처리 (일괄 처리)
                if base_date and result.data:
                    # base_date 필터링: API는 최신→과거 순이므로 base_date에 해당하는 첫 번째 데이터부터 과거로 필터링
                    filtered_by_base_date = []
                    base_date_found = False
                    
                    print(f"base_date 필터링 시작: {base_date}")
                    
                    for item in result.data:
                        item_date = None
                        
                        # 날짜 추출
                        if 'cntr_tm' in item:
                            item_date = item['cntr_tm'][:8]  # YYYYMMDD 부분만
                        elif 'date' in item:
                            item_date = item['date']
                        elif 'dt' in item:
                            item_date = item['dt']
                        elif 'stck_bsop_date' in item:
                            item_date = item['stck_bsop_date']
                        
                        # base_date와 일치하는 첫 번째 데이터를 찾으면 그때부터 수집 시작
                        if item_date == base_date:
                            base_date_found = True
                        
                        # base_date 이후의 모든 데이터 포함 (base_date부터 과거로)
                        if base_date_found:
                            filtered_by_base_date.append(item)
                    
                    if base_date_found:
                        result.data = filtered_by_base_date
                        print(f"base_date({base_date}) 필터링 후: {len(result.data)}개 데이터")
                    else:
                        print(f"base_date({base_date})에 해당하는 데이터를 찾지 못했습니다. 원본 데이터 유지.")
                elif base_date is None and result.data:
                    # base_date가 None이면 가장 최신 캔들로 자동 설정 (첫 번째 데이터가 최신)
                    first_item = result.data[0]
                    if 'cntr_tm' in first_item:
                        latest_timestamp = first_item['cntr_tm']
                        print(f"base_date가 None이므로 최신 캔들로 자동 설정: {latest_timestamp}")
                    elif 'date' in first_item and 'time' in first_item:
                        latest_timestamp = first_item['date'] + first_item['time'].zfill(6)
                        print(f"base_date가 None이므로 최신 캔들로 자동 설정: {latest_timestamp}")
                
                # num_candles 처리 (일괄 처리)
                if num_candles and len(result.data) >= num_candles:
                    result.data = result.data[:num_candles]
                    target_reached = True
                    print(f"목표 캔들 개수({num_candles})에 도달. 수집 완료: {len(result.data)}개")
                
                # 목표 도달 플래그 체크 - while 루프 중단
                if target_reached:
                    break
                
                # 연속 조회 정보 업데이트
                cont_yn = headers.get('cont-yn', 'N')
                next_key = headers.get('next-key', '')
                
                print(f"연속 조회 정보: cont_yn={cont_yn}, next_key={next_key}")
                
                # 연속 조회가 아니거나 자동 페이징이 아니면 종료
                if cont_yn != 'Y' or not auto_pagination:
                    break
                
                # API 요청 제한을 위한 지연 (연속 조회 시에만)
                time_module.sleep(0.3)
                    
                # 페이지 제한 도달 체크
                if page_count >= max_pages:
                    print(f"최대 페이지 수({max_pages}) 도달: {chart_type}")
                    break
        
        except Exception as e:
            print(f"{chart_type} 차트 데이터 수집 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            
        print(f"차트 데이터 조회 완료: {chart_type}, 페이지: {page_count}, 항목 수: {len(result.data)}")
        
        # 데이터 정렬 (날짜 기준)
        if result.data and len(result.data) > 0:
            try:
                # 날짜 필드 찾기 (차트 타입별로 다름)
                first_item = result.data[0]
                last_item = result.data[-1]
                
                if 'cntr_tm' in first_item:
                    # 분봉: cntr_tm에서 날짜와 시간 정보 모두 추출
                    first_timestamp = first_item['cntr_tm']  # YYYYMMDDHHMMSS
                    last_timestamp = last_item['cntr_tm']
                    
                    if len(first_timestamp) == 14 and len(last_timestamp) == 14:
                        first_datetime = f"{first_timestamp[:4]}-{first_timestamp[4:6]}-{first_timestamp[6:8]} {first_timestamp[8:10]}:{first_timestamp[10:12]}:{first_timestamp[12:14]}"
                        last_datetime = f"{last_timestamp[:4]}-{last_timestamp[4:6]}-{last_timestamp[6:8]} {last_timestamp[8:10]}:{last_timestamp[10:12]}:{last_timestamp[12:14]}"
                        print(f"실제 조회된 기간: {first_datetime} ~ {last_datetime} (총 {len(result.data)}개)")
                    else:
                        first_date = first_timestamp[:8]
                        last_date = last_timestamp[:8]
                        print(f"실제 조회된 기간: {first_date} ~ {last_date} (총 {len(result.data)}개)")
                elif 'dt' in first_item:
                    # 일봉: dt 필드
                    first_date = first_item['dt']
                    last_date = last_item['dt']
                    print(f"실제 조회된 기간: {first_date} ~ {last_date} (총 {len(result.data)}개)")
                elif 'stck_bsop_date' in first_item:
                    # 일봉: stck_bsop_date 필드
                    first_date = first_item['stck_bsop_date']
                    last_date = last_item['stck_bsop_date']
                    print(f"실제 조회된 기간: {first_date} ~ {last_date} (총 {len(result.data)}개)")
                    
            except Exception as e:
                print(f"날짜 범위 출력 중 오류 발생: {e}")
        
        return result
    
    def _filter_chart_data(self, data_list, start_date=None, end_date=None):
        """
        차트 데이터를 날짜 범위에 맞게 필터링합니다.
        
        Args:
            data_list (list): 차트 데이터 리스트
            start_date (str, optional): 시작일(YYYYMMDD)
            end_date (str, optional): 종료일(YYYYMMDD)
            
        Returns:
            list: 필터링된 차트 데이터
        """
        if not data_list:
            return []
        
        filtered_data = []
        today = datetime.datetime.now().strftime('%Y%m%d')
        
        # 날짜 필드 이름 찾기
        date_field = 'dt' if 'dt' in data_list[0] else 'stck_bsop_date'
        
        for item in data_list:
            if date_field not in item:
                continue
                
            date = item[date_field]
            
            # 미래 데이터 필터링
            if date > today:
                continue
                
            # 시작일 필터링
            if start_date and date < start_date:
                continue
                
            # 종료일 필터링
            if end_date and date > end_date:
                continue
                
            filtered_data.append(item)
        
        return filtered_data
    
    def _parse_period(self, period_str, trading_days=True):
        """
        기간 문자열을 파싱하여 일수로 변환
        
        Args:
            period_str: 기간 문자열 ('2y', '3m', '40d' 등)
            trading_days: True면 거래일 기준, False면 달력일 기준으로 계산
            
        Returns:
            int: 일수
        """
        if not period_str:
            return 252 if trading_days else 365  # 기본값 1년
            
        # 복합 기간 처리 (예: '1y6m')
        total_days = 0
        
        # 년(y) 매칭
        year_match = re.search(r'(\d+)y', period_str)
        if year_match:
            years = int(year_match.group(1))
            total_days += years * (252 if trading_days else 365)
        
        # 월(m) 매칭
        month_match = re.search(r'(\d+)m', period_str)
        if month_match:
            months = int(month_match.group(1))
            total_days += months * (21 if trading_days else 30)
        
        # 주(w) 매칭
        week_match = re.search(r'(\d+)w', period_str)
        if week_match:
            weeks = int(week_match.group(1))
            total_days += weeks * (5 if trading_days else 7)
        
        # 일(d) 매칭
        day_match = re.search(r'(\d+)d', period_str)
        if day_match:
            days = int(day_match.group(1))
            total_days += days
        
        # 숫자만 있는 경우 일수로 취급
        if total_days == 0 and period_str.isdigit():
            total_days = int(period_str)
        
        # 최소 1일
        return max(1, total_days)
    
    def _calculate_start_date(self, end_date, period, trading_days=True):
        """
        종료일과 기간을 기반으로 시작일 계산
        
        Args:
            end_date: 종료일 (YYYYMMDD 문자열)
            period: 기간 문자열 ('2y', '3m', '40d' 등)
            trading_days: True면 거래일 기준, False면 달력일 기준으로 계산
            
        Returns:
            str: YYYYMMDD 형식의 시작일 문자열
        """
        # 기간을 일수로 변환
        days = self._parse_period(period, trading_days)
        
        # 종료일 파싱
        end_date_obj = datetime.datetime.strptime(end_date, '%Y%m%d')
        
        # 거래일 기준인 경우 보정값 적용
        if trading_days:
            calendar_days = int(days * 1.4)  # 거래일을 달력일로 대략 변환
        else:
            calendar_days = days
        
        # 시작일 계산 (종료일 - 일수)
        start_date_obj = end_date_obj - datetime.timedelta(days=calendar_days)
        
        # YYYYMMDD 형식으로 반환
        return start_date_obj.strftime('%Y%m%d')
    
    def _validate_date_range(self, start_date, end_date):
        """
        시작일과 종료일의 유효성을 검사
        
        Args:
            start_date: 시작일 (YYYYMMDD 형식)
            end_date: 종료일 (YYYYMMDD 형식)
            
        Returns:
            tuple: (시작일, 종료일, 오류 메시지)
        """
        try:
            # 날짜 변환
            start_dt = datetime.datetime.strptime(start_date, '%Y%m%d')
            end_dt = datetime.datetime.strptime(end_date, '%Y%m%d')
            today = datetime.datetime.now()
            
            error_msg = None
            
            # 종료일이 오늘보다 미래인 경우
            if end_dt > today:
                end_dt = today
                end_date = today.strftime('%Y%m%d')
                error_msg = f"종료일이 미래 날짜입니다. 오늘({end_date})로 조정합니다."
            
            # 시작일이 종료일보다 미래인 경우
            if start_dt > end_dt:
                start_dt = end_dt - datetime.timedelta(days=365)  # 기본값 1년
                start_date = start_dt.strftime('%Y%m%d')
                error_msg = f"시작일이 종료일보다 미래입니다. 종료일 1년 전({start_date})으로 조정합니다."
            
            # 시작일이 너무 과거인 경우 (예: 20년 이상)
            max_years_back = 20
            min_date = end_dt - datetime.timedelta(days=365 * max_years_back)
            if start_dt < min_date:
                start_dt = min_date
                start_date = start_dt.strftime('%Y%m%d')
                error_msg = f"시작일이 너무 과거입니다. {max_years_back}년 전({start_date})으로 조정합니다."
            
            return start_date, end_date, error_msg
        
        except ValueError as e:
            # 날짜 형식이 잘못된 경우
            today_str = datetime.datetime.now().strftime('%Y%m%d')
            last_year = (datetime.datetime.now() - datetime.timedelta(days=365)).strftime('%Y%m%d')
            return last_year, today_str, f"날짜 형식이 잘못되었습니다: {e}. 기본값으로 설정합니다."
    
    def _format_date(self, date_str):
        """
        다양한 형식의 날짜 문자열을 YYYYMMDD 형식으로 변환
        
        Args:
            date_str: 날짜 문자열
            
        Returns:
            str: YYYYMMDD 형식의 날짜 문자열
        """
        if isinstance(date_str, datetime.datetime):
            return date_str.strftime('%Y%m%d')
        
        if len(date_str) == 8 and date_str.isdigit():
            return date_str
        
        try:
            # 하이픈이나 슬래시 포함된 날짜를 파싱
            if '-' in date_str or '/' in date_str:
                date_obj = datetime.datetime.strptime(
                    date_str.replace('/', '-'), 
                    '%Y-%m-%d' if len(date_str.split('-')[0]) == 4 else '%d-%m-%Y'
                )
            else:
                # 다른 형식 시도
                formats = ['%Y%m%d', '%d%m%Y', '%m%d%Y']
                for fmt in formats:
                    try:
                        date_obj = datetime.datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    raise ValueError(f"인식할 수 없는 날짜 형식: {date_str}")
            
            return date_obj.strftime('%Y%m%d')
        except Exception as e:
            print(f"날짜 변환 오류: {e}, 기본값 사용")
            return datetime.datetime.now().strftime('%Y%m%d')
    
    def _parse_minute_period(self, period_str):
        """
        기간 문자열을 파싱하여 분 단위로 변환
        
        Args:
            period_str: 기간 문자열 ('1d', '4h', '30m' 등)
            - 'd': 일 (하루 = 390분, 6시간 30분 거래 시간 기준)
            - 'h': 시간
            - 'm': 분
        
        Returns:
            int: 분 단위 기간
        """
        if not period_str:
            return 390  # 기본값 1일 (거래시간 6시간 30분 = 390분)
            
        # 일(d) 매칭
        day_match = re.search(r'(\d+)d', period_str)
        if day_match:
            days = int(day_match.group(1))
            return days * 390  # 하루 거래시간 6시간 30분 = 390분
        
        # 시간(h) 매칭
        hour_match = re.search(r'(\d+)h', period_str)
        if hour_match:
            hours = int(hour_match.group(1))
            return hours * 60  # 1시간 = 60분
        
        # 분(m) 매칭
        minute_match = re.search(r'(\d+)m', period_str)
        if minute_match:
            minutes = int(minute_match.group(1))
            return minutes
        
        # 숫자만 있는 경우 분으로 취급
        if period_str.isdigit():
            return int(period_str)
        
        # 기본값
        return 390  # 1일 (거래시간 6시간 30분)
    
    def _find_previous_trading_day(self, date_str):
        """
        주어진 날짜의 이전 거래일을 찾음
        
        Args:
            date_str: YYYYMMDD 형식의 날짜 문자열
            
        Returns:
            str: 이전 거래일 (YYYYMMDD 형식)
        """
        date_obj = datetime.datetime.strptime(date_str, '%Y%m%d')
        while True:
            date_obj -= datetime.timedelta(days=1)
            if date_obj.weekday() < 5:  # 주말이 아닌 경우
                return date_obj.strftime('%Y%m%d')


# 싱글톤 인스턴스 생성
chart_service = ChartService()

# 싱글톤 인스턴스를 통한 래퍼 함수들
def get_daily_chart(stock_code, base_date=None, num_candles=252, 
                    modified_price_type='1', auto_pagination=True, output_dir=None):
    return chart_service.get_daily_chart(stock_code, base_date=base_date, num_candles=num_candles,
                                           modified_price_type=modified_price_type, auto_pagination=auto_pagination,
                                           output_dir=output_dir)

def get_weekly_chart(stock_code, base_date=None, num_candles=52, 
                     modified_price_type='1', auto_pagination=True, output_dir=None):
    return chart_service.get_weekly_chart(stock_code, base_date=base_date, num_candles=num_candles,
                                            modified_price_type=modified_price_type, auto_pagination=auto_pagination,
                                            output_dir=output_dir)

def get_minute_chart(stock_code, interval, base_date=None, num_candles=77, 
                     market_time='N', modified_price_type='1', auto_pagination=True, output_dir=None):
    return chart_service.get_minute_chart(stock_code, base_date=base_date, 
                                            time_interval=str(interval) if interval else '1',
                                            num_candles=num_candles, market_time=market_time, 
                                            modified_price_type=modified_price_type, 
                                            auto_pagination=auto_pagination, output_dir=output_dir)

# 기존의 싱글톤 인스턴스 (필요하다면 유지, 아니면 위의 _service_instance로 통일)
# chart_service = ChartService() 