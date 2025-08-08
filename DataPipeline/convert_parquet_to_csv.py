#!/usr/bin/env python3
"""
DataPipeline/convert_parquet_to_csv.py

Parquet 파일을 CSV 파일로 변환하는 유틸리티 도구

사용법:
    # 단일 파일 변환
    python convert_parquet_to_csv.py --file data/simulation/005930_d_20250623.parquet
    
    # 폴더 내 모든 parquet 파일 일괄 변환
    python convert_parquet_to_csv.py --folder data/simulation
    
    # 특정 패턴의 파일만 변환
    python convert_parquet_to_csv.py --folder data/simulation --pattern "*_5m_*.parquet"
    
    # 출력 폴더 지정
    python convert_parquet_to_csv.py --folder data/simulation --output output/csv
"""

import os
import sys
import argparse
import glob
import pandas as pd
from pathlib import Path
from typing import List, Optional

def convert_single_parquet_to_csv(parquet_path: str, output_dir: Optional[str] = None, verbose: bool = True) -> bool:
    """
    단일 parquet 파일을 CSV로 변환
    
    Args:
        parquet_path: parquet 파일 경로
        output_dir: 출력 디렉토리 (None이면 원본 파일과 같은 폴더)
        verbose: 상세 로그 출력 여부
        
    Returns:
        bool: 성공 시 True, 실패 시 False
    """
    try:
        if not os.path.exists(parquet_path):
            print(f"❌ 파일이 존재하지 않습니다: {parquet_path}")
            return False
            
        if not parquet_path.lower().endswith('.parquet'):
            print(f"❌ parquet 파일이 아닙니다: {parquet_path}")
            return False
            
        # 출력 경로 설정
        parquet_file = Path(parquet_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            csv_path = os.path.join(output_dir, parquet_file.stem + '.csv')
        else:
            csv_path = parquet_file.with_suffix('.csv')
            
        if verbose:
            print(f"🔄 변환 중: {parquet_path} → {csv_path}")
            
        # parquet 파일 로드
        df = pd.read_parquet(parquet_path)
        
        if verbose:
            print(f"   📊 데이터 크기: {len(df)}행 x {len(df.columns)}열")
            print(f"   📋 컬럼: {list(df.columns)}")
            
        # CSV로 저장 (인덱스 포함, 한글 지원)
        df.to_csv(csv_path, index=True, encoding='utf-8-sig')
        
        if verbose:
            file_size = os.path.getsize(csv_path) / 1024  # KB
            print(f"   ✅ 변환 완료: {csv_path} ({file_size:.1f}KB)")
            
        return True
        
    except Exception as e:
        print(f"❌ 변환 실패: {parquet_path}")
        print(f"   오류: {e}")
        return False

def find_parquet_files(folder_path: str, pattern: str = "*.parquet") -> List[str]:
    """
    폴더에서 parquet 파일들을 찾기
    
    Args:
        folder_path: 검색할 폴더 경로
        pattern: 파일 패턴 (기본값: "*.parquet")
        
    Returns:
        List[str]: 찾은 parquet 파일 경로 리스트
    """
    if not os.path.exists(folder_path):
        print(f"❌ 폴더가 존재하지 않습니다: {folder_path}")
        return []
        
    search_pattern = os.path.join(folder_path, pattern)
    parquet_files = glob.glob(search_pattern)
    
    # .parquet 확장자만 필터링
    parquet_files = [f for f in parquet_files if f.lower().endswith('.parquet')]
    parquet_files.sort()  # 정렬
    
    return parquet_files

def convert_folder_parquet_to_csv(
    folder_path: str, 
    pattern: str = "*.parquet", 
    output_dir: Optional[str] = None,
    verbose: bool = True
) -> tuple[int, int]:
    """
    폴더 내 모든 parquet 파일을 CSV로 변환
    
    Args:
        folder_path: 검색할 폴더 경로
        pattern: 파일 패턴
        output_dir: 출력 디렉토리
        verbose: 상세 로그 출력 여부
        
    Returns:
        tuple[int, int]: (성공 개수, 전체 개수)
    """
    parquet_files = find_parquet_files(folder_path, pattern)
    
    if not parquet_files:
        print(f"❌ 변환할 parquet 파일을 찾을 수 없습니다: {folder_path}/{pattern}")
        return 0, 0
        
    if verbose:
        print(f"🔍 발견된 parquet 파일: {len(parquet_files)}개")
        for i, file_path in enumerate(parquet_files, 1):
            filename = os.path.basename(file_path)
            print(f"   {i:2d}. {filename}")
        print()
        
    success_count = 0
    total_count = len(parquet_files)
    
    for i, parquet_path in enumerate(parquet_files, 1):
        if verbose:
            print(f"[{i}/{total_count}]", end=" ")
            
        if convert_single_parquet_to_csv(parquet_path, output_dir, verbose):
            success_count += 1
            
        if verbose and i < total_count:
            print()  # 구분선
            
    return success_count, total_count

def main():
    """CLI 인터페이스"""
    parser = argparse.ArgumentParser(
        description='Parquet 파일을 CSV 파일로 변환하는 유틸리티',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 단일 파일 변환
  python convert_parquet_to_csv.py --file data/simulation/005930_d_20250623.parquet
  
  # 폴더 내 모든 parquet 파일 변환
  python convert_parquet_to_csv.py --folder data/simulation
  
  # 5분봉 파일만 변환
  python convert_parquet_to_csv.py --folder data/simulation --pattern "*_5m_*.parquet"
  
  # 출력 폴더 지정
  python convert_parquet_to_csv.py --folder data/simulation --output output/csv
        """
    )
    
    # 상호 배타적 그룹 (file 또는 folder 중 하나만 선택)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--file', '-f', help='변환할 단일 parquet 파일 경로')
    group.add_argument('--folder', '-d', help='변환할 parquet 파일들이 있는 폴더 경로')
    
    parser.add_argument('--pattern', '-p', default='*.parquet', 
                       help='파일 패턴 (폴더 모드에서만 사용, 기본값: *.parquet)')
    parser.add_argument('--output', '-o', 
                       help='출력 디렉토리 (지정하지 않으면 원본과 같은 폴더)')
    parser.add_argument('--quiet', '-q', action='store_true', 
                       help='상세 로그 출력 안함')
    
    args = parser.parse_args()
    
    verbose = not args.quiet
    
    if verbose:
        print("🔄 Parquet → CSV 변환 유틸리티")
        print("=" * 50)
    
    if args.file:
        # 단일 파일 변환
        success = convert_single_parquet_to_csv(args.file, args.output, verbose)
        if verbose:
            if success:
                print("\n✅ 변환 완료!")
            else:
                print("\n❌ 변환 실패!")
        sys.exit(0 if success else 1)
        
    elif args.folder:
        # 폴더 일괄 변환
        success_count, total_count = convert_folder_parquet_to_csv(
            args.folder, args.pattern, args.output, verbose
        )
        
        if verbose:
            print("\n" + "=" * 50)
            print(f"📊 변환 결과: {success_count}/{total_count} 성공")
            
            if success_count == total_count:
                print("✅ 모든 파일 변환 완료!")
            elif success_count > 0:
                print(f"⚠️  일부 파일 변환 완료 ({total_count - success_count}개 실패)")
            else:
                print("❌ 모든 파일 변환 실패!")
                
        sys.exit(0 if success_count == total_count else 1)

if __name__ == "__main__":
    main() 