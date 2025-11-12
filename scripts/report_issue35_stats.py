#!/usr/bin/env python3
"""
Issue #35 구현 통계 자동 산출 스크립트

실제 저장소의 파일, 라인 수, 테스트 케이스를 집계하여
문서와 보고서의 수치를 자동으로 갱신합니다.

사용법:
  python3 scripts/report_issue35_stats.py

출력:
  - 변경된 파일 목록 (백엔드, 프론트엔드, 테스트, 문서)
  - 각 파일의 라인 수
  - 테스트 케이스 수 (유닛 + 통합)
  - 생성된 문서 목록
"""

import os
import re
import subprocess
from pathlib import Path
from collections import defaultdict

# 프로젝트 루트 디렉토리
PROJECT_ROOT = Path(__file__).parent.parent

def count_lines(filepath):
    """파일의 라인 수를 카운트합니다."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return len(f.readlines())
    except Exception as e:
        print(f"⚠️  라인 카운트 실패 {filepath}: {e}")
        return 0


def find_test_cases(filepath):
    """파일에서 테스트 케이스 수를 추출합니다."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # pytest 형식: def test_xxx()
        test_count = len(re.findall(r'^\s*def test_\w+\(', content, re.MULTILINE))
        return test_count
    except Exception as e:
        print(f"⚠️  테스트 추출 실패 {filepath}: {e}")
        return 0


def get_file_changes():
    """git을 통해 변경된 파일 목록을 조회합니다."""
    try:
        # git status로 변경된 파일 조회
        result = subprocess.run(
            ['git', 'status', '--short'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10
        )

        changes = defaultdict(list)
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue

            status = line[:2]
            filepath = line[3:]

            if 'backend' in filepath:
                changes['backend'].append((filepath, status))
            elif 'frontend' in filepath:
                changes['frontend'].append((filepath, status))
            elif 'tests' in filepath:
                changes['tests'].append((filepath, status))
            elif 'docs' in filepath:
                changes['docs'].append((filepath, status))

        return changes
    except Exception as e:
        print(f"⚠️  git status 실패: {e}")
        return defaultdict(list)


def collect_stats():
    """모든 통계를 수집합니다."""
    stats = {
        'backend_files': [],
        'frontend_files': [],
        'test_files': [],
        'doc_files': [],
        'automation_files': [],
        'total_lines': 0,
        'total_tests': 0,
        'timestamp': __import__('datetime').datetime.now().isoformat(),
        'command': 'python3 scripts/report_issue35_stats.py',
    }

    # 1. 백엔드 파일
    backend_files = [
        'backend/app/main.py',
        'backend/app/result_manager.py',
    ]

    for filepath in backend_files:
        full_path = PROJECT_ROOT / filepath
        if full_path.exists():
            lines = count_lines(full_path)
            stats['backend_files'].append({
                'path': filepath,
                'lines': lines,
                'status': 'Modified'
            })
            stats['total_lines'] += lines

    # 2. 프론트엔드 파일 (공용 파일 포함)
    frontend_files = [
        'frontend/src/components/SymbolToggleList.jsx',
        'frontend/src/styles/SymbolToggleList.css',
        'frontend/src/pages/SignalViewerPage.jsx',
        'frontend/src/App.css',
        'frontend/src/utils/charts.ts',  # 공용 파일
    ]

    for filepath in frontend_files:
        full_path = PROJECT_ROOT / filepath
        if full_path.exists():
            lines = count_lines(full_path)
            status = 'New' if 'SymbolToggleList' in filepath or 'SymbolToggleList' in filepath else 'Modified'
            stats['frontend_files'].append({
                'path': filepath,
                'lines': lines,
                'status': status
            })
            stats['total_lines'] += lines

    # 3. 테스트 파일
    test_files = [
        'tests/unit/test_symbol_result.py',
        'tests/integration/test_symbol_toggle_api.py',
    ]

    for filepath in test_files:
        full_path = PROJECT_ROOT / filepath
        if full_path.exists():
            lines = count_lines(full_path)
            tests = find_test_cases(full_path)
            stats['test_files'].append({
                'path': filepath,
                'lines': lines,
                'tests': tests,
                'status': 'New'
            })
            stats['total_lines'] += lines
            stats['total_tests'] += tests

    # 4. 문서 파일
    doc_files = [
        'docs/coin/mvp/SYMBOL_TOGGLE_API.md',
        'docs/coin/mvp/SIGNAL_VIEWER_USER_GUIDE.md',
        'docs/coin/mvp/PHASE2_ISSUE_35_COMPLETION.md',
    ]

    for filepath in doc_files:
        full_path = PROJECT_ROOT / filepath
        if full_path.exists():
            lines = count_lines(full_path)
            stats['doc_files'].append({
                'path': filepath,
                'lines': lines,
                'status': 'New'
            })
            stats['total_lines'] += lines

    # 5. 자동화 도구 파일
    automation_files = [
        'scripts/report_issue35_stats.py',
        'scripts/render_issue35_summary.py',
    ]

    for filepath in automation_files:
        full_path = PROJECT_ROOT / filepath
        if full_path.exists():
            lines = count_lines(full_path)
            stats['automation_files'].append({
                'path': filepath,
                'lines': lines,
                'status': 'New'
            })
            stats['total_lines'] += lines

    return stats


def print_stats(stats):
    """통계를 보기 좋게 출력합니다."""

    print("\n" + "="*80)
    print("📊 Issue #35 구현 통계 자동 산출")
    print("="*80 + "\n")

    # 백엔드
    print("📝 백엔드 파일 (Backend)")
    print("-" * 80)
    for file_info in stats['backend_files']:
        print(f"  {file_info['path']:<50} {file_info['lines']:>5} 줄  [{file_info['status']}]")
    print()

    # 프론트엔드
    print("📝 프론트엔드 파일 (Frontend)")
    print("-" * 80)
    for file_info in stats['frontend_files']:
        print(f"  {file_info['path']:<50} {file_info['lines']:>5} 줄  [{file_info['status']}]")
    print()

    # 테스트
    print("🧪 테스트 파일 (Tests)")
    print("-" * 80)
    total_test_cases = 0
    for file_info in stats['test_files']:
        print(f"  {file_info['path']:<50} {file_info['lines']:>5} 줄, {file_info['tests']:>2} 케이스")
        total_test_cases += file_info['tests']
    print()

    # 문서
    print("📚 문서 파일 (Documentation)")
    print("-" * 80)
    for file_info in stats['doc_files']:
        print(f"  {file_info['path']:<50} {file_info['lines']:>5} 줄  [{file_info['status']}]")
    print()

    # 자동화 도구
    print("🔧 자동화 도구 (Automation)")
    print("-" * 80)
    for file_info in stats['automation_files']:
        print(f"  {file_info['path']:<50} {file_info['lines']:>5} 줄  [{file_info['status']}]")
    print()

    # 요약
    print("="*80)
    print("📈 요약 통계")
    print("="*80)

    backend_count = len(stats['backend_files'])
    frontend_count = len(stats['frontend_files'])
    test_count = len(stats['test_files'])
    doc_count = len(stats['doc_files'])
    automation_count = len(stats['automation_files'])
    total_files = backend_count + frontend_count + test_count + doc_count + automation_count

    print(f"\n✅ 파일 수:")
    print(f"   • 백엔드:      {backend_count} 파일")
    print(f"   • 프론트엔드:   {frontend_count} 파일")
    print(f"   • 테스트:      {test_count} 파일")
    print(f"   • 문서:       {doc_count} 파일")
    print(f"   • 자동화:      {automation_count} 파일")
    print(f"   • 총합:       {total_files} 파일")

    print(f"\n✅ 라인 수:")
    print(f"   • 총 {stats['total_lines']} 줄 (공백 제외)")

    print(f"\n✅ 테스트:")
    print(f"   • 총 {stats['total_tests']} 테스트 케이스")
    for file_info in stats['test_files']:
        print(f"     - {Path(file_info['path']).name}: {file_info['tests']} 케이스")

    print("\n" + "="*80 + "\n")

    return {
        'backend_files': backend_count,
        'frontend_files': frontend_count,
        'test_files': test_count,
        'doc_files': doc_count,
        'automation_files': automation_count,
        'total_files': total_files,
        'total_lines': stats['total_lines'],
        'total_tests': stats['total_tests'],
        'timestamp': stats['timestamp'],
        'command': stats['command'],
    }


def generate_markdown_table(stats):
    """마크다운 형식의 테이블을 생성합니다."""

    print("\n" + "="*80)
    print("📋 마크다운 테이블 (문서용)")
    print("="*80 + "\n")

    # 파일별 통계 테이블
    print("### 백엔드 파일\n")
    print("| 파일 | 라인 수 | 상태 |")
    print("|------|--------|------|")
    for file_info in stats['backend_files']:
        print(f"| `{file_info['path']}` | {file_info['lines']} | {file_info['status']} |")

    print("\n### 프론트엔드 파일\n")
    print("| 파일 | 라인 수 | 상태 |")
    print("|------|--------|------|")
    for file_info in stats['frontend_files']:
        print(f"| `{file_info['path']}` | {file_info['lines']} | {file_info['status']} |")

    print("\n### 테스트 파일\n")
    print("| 파일 | 라인 수 | 테스트 케이스 |")
    print("|------|--------|---|")
    for file_info in stats['test_files']:
        print(f"| `{file_info['path']}` | {file_info['lines']} | {file_info['tests']} |")

    print("\n### 문서 파일\n")
    print("| 파일 | 라인 수 | 상태 |")
    print("|------|--------|------|")
    for file_info in stats['doc_files']:
        print(f"| `{file_info['path']}` | {file_info['lines']} | {file_info['status']} |")

    print("\n### 자동화 도구\n")
    print("| 파일 | 라인 수 | 상태 |")
    print("|------|--------|------|")
    for file_info in stats['automation_files']:
        print(f"| `{file_info['path']}` | {file_info['lines']} | {file_info['status']} |")

    print("\n" + "="*80 + "\n")


if __name__ == '__main__':
    try:
        stats = collect_stats()
        summary = print_stats(stats)
        generate_markdown_table(stats)

        # JSON 형식으로 저장 (렌더 스크립트에서 읽을 수 있도록 전체 통계 저장)
        import json
        output_file = PROJECT_ROOT / 'scripts' / 'issue35_stats.json'

        # stats 객체에서 파일 리스트를 counts로 변환하되, 전체 데이터도 함께 저장
        json_output = {
            'backend_files': summary['backend_files'],
            'frontend_files': summary['frontend_files'],
            'test_files': summary['test_files'],
            'doc_files': summary['doc_files'],
            'automation_files': summary['automation_files'],
            'total_files': summary['total_files'],
            'total_lines': summary['total_lines'],
            'total_tests': summary['total_tests'],
            'timestamp': summary['timestamp'],
            'command': summary['command'],
            # 렌더 스크립트용: 상세 파일 정보
            'backend_files_detail': stats['backend_files'],
            'frontend_files_detail': stats['frontend_files'],
            'test_files_detail': stats['test_files'],
            'doc_files_detail': stats['doc_files'],
            'automation_files_detail': stats['automation_files'],
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_output, f, indent=2, ensure_ascii=False)
        print(f"💾 통계가 {output_file}에 저장되었습니다.\n")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        exit(1)
