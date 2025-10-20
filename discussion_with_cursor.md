나 : 한가지 너의 의견을 물어 보고 싶은게 . dag_initial_loader의 _run_stock_info_load_task 에서는 모든 종목을 조회한 뒤에 live.stocks' 테이블에는 제로 필터링을 통과한 즉 is_active 가 True인 종목만을 db에 자장하고 있니 ?  그리고 너가 설계자라면 그렇게하는게 좋니 아니면 is_active가 False인 종목도 live.stocks' 테이블에 기록 해 두는 것이 맞니? @dag_initial_loader.py @data_collector.py 


짧히 결론부터: 현재 `_run_stock_info_load_task`는 “필터 제로를 통과한 종목만” `live.stocks`에 업서트하고 있습니다. 설계자 관점에서는 **원장(마스터)**으로는 API에서 받은 모든 종목(활성/비활성 구분 포함)을 보관하고, 분석용 필터는 별도 단계에서 적용하는 것이 더 안전·명확합니다. 아래에 근거, 위험, 권장안(구체적)과 질문을 정리합니다.

근거(코드 참조)
```59:76:DataPipeline/dags/dag_initial_loader.py
all_stocks = sync_stock_master_data()
filtered_stocks = apply_filter_zero(all_stocks)
logger.info(f"📊 외부 API로부터 로드된 종목 수: {len(all_stocks)}개")
logger.info(f"🔎 필터 제로 통과 종목 수: {len(filtered_stocks)}개")
```

```89:100:DataPipeline/dags/dag_initial_loader.py
records_to_upsert = [
    {
        "stock_code": s['code'],
        ...
        "is_active": True,
        "backfill_needed": True
    } for s in filtered_stocks
]
```

현재 동작 요약
- 전체 API 결과(`all_stocks`)는 읽지만, DB에 업서트하는 대상은 `apply_filter_zero`를 통과한 `filtered_stocks` 뿐입니다.
- 업서트 시 `is_active=True`로 설정(즉 DB에는 필터 통과 종목만 ‘활성’으로 들어감).

이 방식의 문제점 / 리스크
- 필터는 분석용 제외 기준이지 공식 마스터(원장)를 변경할 근거가 아닙니다. 필터 정책이 바뀌면(강화되면) 실제로 상장·거래중인 종목을 DB에서 비활성화하거나 누락시킬 위험이 있습니다(데이터 오염).
- 원본 API와 분석필터를 동일 기준으로 처리하면 “분석 제외 = 상장폐지” 같은 논리적 혼선이 생깁니다.
- 운영/감사 관점에서 “한 번이라도 API에 존재했던 종목”의 기록을 남기지 않으면 추후 원인분석(예: 왜 이 종목이 분석에서 빠졌는가)을 못하게 됩니다.

권장 설계 (우선순위·구체안)
1. (권장) 마스터 원장 보관: `live.stocks`에는 API 원본(또는 API→매핑 결과) 전체를 업서트.  
   - 필드 `is_active`는 API의 실제 상장/거래 상태에 따라 설정(또는 기본 True)하되, **apply_filter_zero는 적용하지 않음**.
   - 이렇게 하면 DB가 canonical ledger 역할을 하므로 오염 위험 감소.
2. 분석 대상 선별은 별도 단계에서 수행:  
   - 분석 파이프라인(예: `get_managed_stocks_from_db` 또는 sync 직후의 XCom 반환)에서 `apply_filter_zero`를 사용해 *분석 대상 리스트*를 만들고 XCom으로 전달.  
   - 즉, "분석 필터 = 파이프라인 입력"으로 분리.
3. 점진적 보수안(코드 최소변경)
   - 변경 A: `_run_stock_info_load_task`에서 `filtered_stocks` 대신 `all_stocks`로 업서트하되, 레코드에 `is_active` 값을 (필터 통과 여부가 아니라) API에서 얻은 상태로 채우거나 기본값 True로 둠.  
   - 변경 B(권장): `sync_stock_master_to_db`를 이용해 마스터 동기화 로직을 통일시키고, 필터는 `get_managed_stocks_from_db` 이후에 적용.
4. 데이터 보존·감사
   - 삭제(또는 is_active=False)하는 경우, 언제/무엇이 변경했는지 기록(이력 테이블 또는 audit_info 확장)을 권장.

운영상 기대 이득
- 필터 정책 변경 시에도 마스터 데이터 무결성 보장
- 분석 파이프라인의 의존성·데이터 흐름 명확화 (XCom 사용 권장)
- 문제 발생 시 원인 추적(언제 종목이 비활성화 되었는지 등)이 쉬움

질문(결정 포인트)
1. `live.stocks`를 canonical ledger로 바꾸는 쪽으로 진행할까요? (즉, apply_filter_zero 제거 → all_stocks 업서트)  
2. 동작 변경 시 `get_managed_stocks_from_db`를 `sync_stock_master_task`가 XCom으로 활성/분석 대상 리스트를 반환하도록 바꾸길 원하나요?  
3. 즉시 코드 변경(풀 리퀘스트)으로 적용해 드릴까요, 아니면 우선 디자인 문서(작업 계획 + 테스트 시나리오)를 만들까요?
