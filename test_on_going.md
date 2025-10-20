source /home/jscho/ChartInsight-Studio/backend/venv/bin/activate
jscho@DESKTOP-46EMA48:~/ChartInsight-Studio$ source /home/jscho/ChartInsight-Studio/backend/venv/bin/activate
(venv) jscho@DESKTOP-46EMA48:~/ChartInsight-Studio$ /home/jscho/ChartInsight-Studio/backend/venv/bin/python3 /home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py
설정 로드 완료: 환경=real, 호스트=https://api.kiwoom.com
📡 DART API(corpCode.xml)로 기업 목록 직접 조회 시도 중...
✅ 매핑 정보를 '/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/dart_corp_list_from_xml.csv'에 저장했습니다.
✅ DART API(XML)를 통해 3901개 유효 상장사 매핑 정보 획득.
================================================================================
🚀 전체 상장 기업 CAN SLIM 재무 분석 시작
================================================================================
Kiwoom API: 전체 종목 정보 수집 중...
토큰을 새로 발급받습니다
🔍 토큰 발급 응답: {'expires_dt': '20251018174749', 'return_msg': '정상적으로 처리되었습니다', 'token_type': 'Bearer', 'return_code': 0, 'token': '2xGhUxzAC7GRkBNpix4QuEQlEj5U6lqRF3HkhedYDTZwHQOUxbHgdlG54teJtKZO8Mx71MrDlhndkFD0Up6GpA'}
✅ 토큰 발견 (키: token)
✅ 토큰이 발급되었습니다. 만료 시간: 2025-10-18 17:43:41.986540
✅ Kiwoom API를 통해 4191개 종목 정보 획득.

--- [Filter Zero] 필터링 시작 ---
필터 제로 적용 중: 100%|███| 4191/4191 [00:00<00:00, 587766.34it/s]
✅ 필터링 완료: 4191개 종목 -> 1348개 종목 (2843개 제외)

--- 총 1348개 필터링된 종목 DART 분석 시작 ---
필터링된 종목 EPS 분석 중:   0%|          | 0/1348 [00:00<?, ?it/s]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   0%|  | 1/1348 [00:01<43:25,  1.93s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   0%|  | 2/1348 [00:03<43:57,  1.96s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   0%|  | 3/1348 [00:05<44:01,  1.96s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   0%|  | 4/1348 [00:07<44:15,  1.98s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   0%|  | 6/1348 [00:10<38:44,  1.73s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   1%|  | 8/1348 [00:12<30:56,  1.39s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   1%| | 10/1348 [00:16<35:55,  1.61s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   1%| | 12/1348 [00:18<30:47,  1.38s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   1%| | 13/1348 [00:21<38:33,  1.73s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   1%| | 14/1348 [00:23<41:40,  1.87s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   1%| | 15/1348 [00:24<34:50,  1.57s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   1%| | 16/1348 [00:26<36:00,  1.62s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   1%| | 17/1348 [00:28<38:51,  1.75s/it]❌ DART API 재무 데이터 수집 실패: corp_code=00113562, stock_code=000400, name=롯데손해보험
필터링된 종목 EPS 분석 중:   1%| | 18/1348 [00:30<41:31,  1.87s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   1%| | 19/1348 [00:32<42:43,  1.93s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   1%| | 20/1348 [00:35<49:34,  2.24s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   2%| | 21/1348 [00:37<48:54,  2.21s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   2%| | 22/1348 [00:40<48:50,  2.21s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   2%| | 23/1348 [00:42<49:51,  2.26s/it]❌ DART API 재무 데이터 수집 실패: corp_code=00103176, stock_code=000540, name=흥국화재
필터링된 종목 EPS 분석 중:   2%| | 24/1348 [00:44<49:48,  2.26s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   2%| | 25/1348 [00:47<50:39,  2.30s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   2%| | 26/1348 [00:48<48:01,  2.18s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   2%| | 27/1348 [00:50<45:52,  2.08s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   2%| | 28/1348 [00:52<40:23,  1.84s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   2%| | 29/1348 [00:54<42:19,  1.93s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   2%| | 30/1348 [00:56<42:04,  1.92s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   2%| | 31/1348 [00:57<39:51,  1.82s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   3%| | 34/1348 [01:01<34:57,  1.60s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   3%| | 37/1348 [01:04<27:13,  1.25s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   3%| | 38/1348 [01:06<29:46,  1.36s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   3%| | 39/1348 [01:08<32:57,  1.51s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   3%| | 42/1348 [01:10<23:29,  1.08s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   3%| | 43/1348 [01:12<27:09,  1.25s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   3%| | 44/1348 [01:15<34:50,  1.60s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   3%| | 45/1348 [01:16<34:16,  1.58s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   3%| | 46/1348 [01:18<35:39,  1.64s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   4%| | 49/1348 [01:22<32:35,  1.51s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   4%| | 50/1348 [01:25<42:56,  1.98s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   4%| | 51/1348 [01:28<44:35,  2.06s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   4%| | 52/1348 [01:30<45:25,  2.10s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   4%| | 53/1348 [01:31<42:36,  1.97s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   4%| | 54/1348 [01:33<39:49,  1.85s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   4%| | 55/1348 [01:36<44:11,  2.05s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   4%| | 56/1348 [01:37<43:04,  2.00s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   4%| | 57/1348 [01:40<44:56,  2.09s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   4%| | 58/1348 [01:42<43:30,  2.02s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   4%| | 60/1348 [01:43<32:26,  1.51s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   5%| | 61/1348 [01:46<40:36,  1.89s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   5%| | 62/1348 [01:48<36:54,  1.72s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   5%| | 63/1348 [01:48<29:13,  1.36s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   5%| | 64/1348 [01:50<31:09,  1.46s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   5%| | 65/1348 [01:52<34:27,  1.61s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   5%| | 66/1348 [01:55<41:58,  1.96s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   5%| | 67/1348 [01:56<40:49,  1.91s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   5%| | 68/1348 [01:58<41:29,  1.94s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   5%| | 69/1348 [02:00<40:29,  1.90s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   5%| | 70/1348 [02:02<39:49,  1.87s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   5%| | 71/1348 [02:04<40:53,  1.92s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   5%| | 72/1348 [02:07<48:35,  2.29s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   5%| | 74/1348 [02:11<42:47,  2.02s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   6%| | 75/1348 [02:13<41:37,  1.96s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   6%| | 76/1348 [02:14<41:05,  1.94s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   6%| | 78/1348 [02:19<42:22,  2.00s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   6%| | 79/1348 [02:21<47:58,  2.27s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   6%| | 81/1348 [02:25<43:11,  2.05s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   6%| | 83/1348 [02:27<32:50,  1.56s/it]❌ DART API 재무 데이터 수집 실패: corp_code=00150828, stock_code=002780, name=진흥기업
필터링된 종목 EPS 분석 중:   6%| | 84/1348 [02:28<30:54,  1.47s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   6%| | 85/1348 [02:30<33:33,  1.59s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   6%| | 87/1348 [02:33<33:12,  1.58s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   7%| | 88/1348 [02:36<38:13,  1.82s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   7%| | 89/1348 [02:38<38:46,  1.85s/it]❌ DART API 재무 데이터 수집 실패: corp_code=00158149, stock_code=002960, name=한국쉘석유
필터링된 종목 EPS 분석 중:   7%| | 90/1348 [02:39<35:33,  1.70s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   7%| | 91/1348 [02:42<39:10,  1.87s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   7%| | 92/1348 [02:44<41:47,  2.00s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   7%| | 93/1348 [02:46<41:53,  2.00s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   7%| | 94/1348 [02:47<38:48,  1.86s/it]❌ DART API 재무 데이터 수집 실패: corp_code=00146214, stock_code=003120, name=일성아이에스
필터링된 종목 EPS 분석 중:   7%| | 95/1348 [02:49<34:33,  1.65s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   7%| | 96/1348 [02:51<37:23,  1.79s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   7%| | 97/1348 [02:54<46:44,  2.24s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   7%| | 98/1348 [02:56<45:31,  2.19s/it]/home/jscho/ChartInsight-Studio/backend/_temp_integration/chart_pattern_analyzer_kiwoom/test_dartapi_financials_xml_all.py:252: FutureWarning: Series.fillna with 'method' is deprecated and will raise in a future version. Use obj.ffill() or obj.bfill() instead.
  pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
필터링된 종목 EPS 분석 중:   7%| | 99/1348 [02:58<43:05,  2.07s/it]