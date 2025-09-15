#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
선정된 30개 종목의 종목코드를 찾는 스크립트
"""
import json
import os

def load_stock_data():
    """KOSPI와 KOSDAQ 종목 데이터 로드"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    kospi_path = os.path.join(current_dir, 'data', 'kospi_code.json')
    kosdaq_path = os.path.join(current_dir, 'data', 'kosdaq_code.json')
    
    with open(kospi_path, 'r', encoding='utf-8') as f:
        kospi_data = json.load(f)
    
    with open(kosdaq_path, 'r', encoding='utf-8') as f:
        kosdaq_data = json.load(f)
    
    return kospi_data, kosdaq_data

def find_stock_codes():
    """선정된 종목들의 종목코드 찾기"""
    
    # 선정된 종목 리스트
    selected_stocks = {
        'KOSPI': [
            '삼성전자', 'SK하이닉스', 'LG에너지솔루션', '현대차', '기아', 
            'NAVER', '카카오', '삼성바이오로직스', '셀트리온', 'POSCO홀딩스',
            'LG화학', 'KB금융', '신한지주', '삼성SDI', '현대모비스',
            '한국전력', 'SK이노베이션', '카카오뱅크', '삼성물산', 'KT&G'
        ],
        'KOSDAQ': [
            '에코프로비엠', 'HLB', '셀트리온헬스케어', '펄어비스', '카카오게임즈',
            '리노공업', '에스엠', 'JYP Ent.', '위메이드', '에이치엘비생명과학'
        ]
    }
    
    kospi_data, kosdaq_data = load_stock_data()
    
    found_codes = {}
    not_found = {}
    
    print("🔍 선정된 30개 종목의 종목코드 검색 중...\n")
    
    # KOSPI 종목 검색
    print("📈 KOSPI 20종목:")
    print("-" * 50)
    found_codes['KOSPI'] = []
    not_found['KOSPI'] = []
    
    for stock_name in selected_stocks['KOSPI']:
        found = False
        for code, info in kospi_data.items():
            if info['name'] == stock_name:
                found_codes['KOSPI'].append({
                    'code': code,
                    'name': stock_name,
                    'audit': info.get('auditInfo', 'N/A')
                })
                print(f"✅ {stock_name:<15} → {code} ({info.get('auditInfo', 'N/A')})")
                found = True
                break
        
        if not found:
            not_found['KOSPI'].append(stock_name)
            print(f"❌ {stock_name:<15} → 찾을 수 없음")
    
    print(f"\nKOSPI 찾은 종목: {len(found_codes['KOSPI'])}/20\n")
    
    # KOSDAQ 종목 검색
    print("📊 KOSDAQ 10종목:")
    print("-" * 50)
    found_codes['KOSDAQ'] = []
    not_found['KOSDAQ'] = []
    
    for stock_name in selected_stocks['KOSDAQ']:
        found = False
        for code, info in kosdaq_data.items():
            if info['name'] == stock_name:
                found_codes['KOSDAQ'].append({
                    'code': code,
                    'name': stock_name,
                    'audit': info.get('auditInfo', 'N/A')
                })
                print(f"✅ {stock_name:<15} → {code} ({info.get('auditInfo', 'N/A')})")
                found = True
                break
        
        if not found:
            not_found['KOSDAQ'].append(stock_name)
            print(f"❌ {stock_name:<15} → 찾을 수 없음")
    
    print(f"\nKOSDAQ 찾은 종목: {len(found_codes['KOSDAQ'])}/10\n")
    
    # 요약 정보
    total_found = len(found_codes['KOSPI']) + len(found_codes['KOSDAQ'])
    print("=" * 60)
    print(f"📋 검색 요약: {total_found}/30 종목 찾음")
    print("=" * 60)
    
    # 찾지 못한 종목들
    all_not_found = not_found['KOSPI'] + not_found['KOSDAQ']
    if all_not_found:
        print(f"⚠️  찾지 못한 종목 ({len(all_not_found)}개):")
        for stock in all_not_found:
            print(f"   - {stock}")
        print()
    
    return found_codes, not_found

def generate_selected_stocks_file(found_codes):
    """찾은 종목들로 selected_stocks.json 파일 생성"""
    
    # 모든 종목을 하나의 딕셔너리로 합치기
    selected_stocks = {}
    
    for kospi_stock in found_codes['KOSPI']:
        selected_stocks[kospi_stock['code']] = {
            'code': kospi_stock['code'],
            'name': kospi_stock['name'],
            'market': 'KOSPI',
            'auditInfo': kospi_stock['audit']
        }
    
    for kosdaq_stock in found_codes['KOSDAQ']:
        selected_stocks[kosdaq_stock['code']] = {
            'code': kosdaq_stock['code'],
            'name': kosdaq_stock['name'],
            'market': 'KOSDAQ',
            'auditInfo': kosdaq_stock['audit']
        }
    
    # 파일 저장
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'selected_stocks.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(selected_stocks, f, ensure_ascii=False, indent=2)
    
    print(f"💾 선정 종목 파일 생성: {output_path}")
    print(f"📊 총 {len(selected_stocks)}개 종목 저장됨\n")
    
    return selected_stocks

if __name__ == "__main__":
    try:
        found_codes, not_found = find_stock_codes()
        selected_stocks = generate_selected_stocks_file(found_codes)
        
        print("🎉 종목코드 검색 및 파일 생성 완료!")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
