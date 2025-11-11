#!/usr/bin/env python3
"""
Test Counter Script

Task 3.5: 자동화된 테스트 수 계산

이 스크립트는 tests/ 디렉터리 하위의 모든 테스트 함수를 카운트하고
결과를 JSON 형식으로 출력합니다.

사용:
    python scripts/count_tests.py
    python scripts/count_tests.py --format json
    python scripts/count_tests.py --format markdown
"""

import subprocess
import json
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple

def get_test_files() -> List[Path]:
    """Find all test files in tests/ directory"""
    tests_dir = Path("tests")
    if not tests_dir.exists():
        return []

    # Find all Python files with "test_" in name
    test_files = list(tests_dir.glob("**/test_*.py"))
    return sorted(test_files)

def count_tests_in_file(file_path: Path) -> int:
    """Count test functions in a single file using ripgrep"""
    try:
        result = subprocess.run(
            ["rg", "-c", r"^\s*(async\s+)?def\s+test_", str(file_path)],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip())
        return 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        # Fallback: count manually
        with open(file_path) as f:
            content = f.read()
        count = 0
        for line in content.split('\n'):
            if 'def test_' in line and ('def test_' in line or 'async def test_' in line):
                count += 1
        return count

def categorize_tests(file_path: Path) -> str:
    """Categorize test file by location"""
    parts = file_path.parts
    if 'integration' in parts:
        return 'integration'
    elif 'unit' in parts:
        return 'unit'
    else:
        return 'unit'  # Default to unit if not explicitly categorized

def generate_report() -> Dict:
    """Generate comprehensive test report"""
    test_files = get_test_files()

    now = datetime.now()
    report = {
        'timestamp': now.isoformat() + 'Z',
        'date': now.strftime('%Y-%m-%d'),
        'files': [],
        'summary': {
            'total': 0,
            'by_category': defaultdict(int),
            'by_directory': defaultdict(int),
        }
    }

    for test_file in test_files:
        count = count_tests_in_file(test_file)
        category = categorize_tests(test_file)

        # Get relative path - handle both absolute and relative paths
        try:
            rel_path = test_file.relative_to(Path.cwd())
        except ValueError:
            rel_path = test_file

        directory = str(rel_path.parent)

        file_info = {
            'path': str(rel_path),
            'directory': directory,
            'category': category,
            'count': count,
        }

        report['files'].append(file_info)
        report['summary']['total'] += count
        report['summary']['by_category'][category] += count
        report['summary']['by_directory'][directory] += count

    # Convert defaultdicts to regular dicts
    report['summary']['by_category'] = dict(report['summary']['by_category'])
    report['summary']['by_directory'] = dict(report['summary']['by_directory'])

    return report

def print_json(report: Dict):
    """Print report in JSON format"""
    print(json.dumps(report, indent=2, ensure_ascii=False))

def print_markdown(report: Dict):
    """Print report in Markdown table format"""
    print("# Test Count Report\n")
    print(f"**Generated**: {report['date']}\n")

    print("## Summary\n")
    print(f"- **Total Tests**: {report['summary']['total']}")
    print(f"- **Test Files**: {len(report['files'])}\n")

    if report['summary']['by_category']:
        print("### By Category\n")
        for category, count in sorted(report['summary']['by_category'].items()):
            print(f"- {category.capitalize()}: {count}")
        print()

    if report['summary']['by_directory']:
        print("### By Directory\n")
        for directory, count in sorted(report['summary']['by_directory'].items()):
            print(f"- `{directory}`: {count}")
        print()

    print("## Test Files\n")
    print("| File | Category | Count |")
    print("|------|----------|-------|")

    for file_info in sorted(report['files'], key=lambda x: x['path']):
        path = file_info['path']
        category = file_info['category']
        count = file_info['count']
        print(f"| `{path}` | {category} | {count} |")

    print()
    print(f"**Total**: {report['summary']['total']} tests")

def print_text(report: Dict):
    """Print report in plain text format"""
    print(f"Test Count Report ({report['date']})")
    print("=" * 60)
    print(f"Total Tests: {report['summary']['total']}")
    print(f"Test Files: {len(report['files'])}")
    print()

    if report['summary']['by_category']:
        print("By Category:")
        for category, count in sorted(report['summary']['by_category'].items()):
            print(f"  {category.capitalize()}: {count}")
        print()

    print("Test Files:")
    for file_info in sorted(report['files'], key=lambda x: x['path']):
        path = file_info['path']
        count = file_info['count']
        print(f"  {path}: {count}")

    print()
    print(f"Total: {report['summary']['total']} tests ({report['date']})")

def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Count test functions in the tests/ directory'
    )

    parser.add_argument(
        '--format',
        choices=['json', 'markdown', 'text'],
        default='text',
        help='Output format (default: text)'
    )

    parser.add_argument(
        '--save',
        type=str,
        help='Save report to file (append to existing if .md file)'
    )

    args = parser.parse_args()

    # Generate report
    report = generate_report()

    # Print report
    if args.format == 'json':
        output = json.dumps(report, indent=2, ensure_ascii=False)
        print_json(report)
    elif args.format == 'markdown':
        print_markdown(report)
    else:
        print_text(report)

    # Save if requested
    if args.save:
        output_path = Path(args.save)
        with open(output_path, 'w', encoding='utf-8') as f:
            if args.format == 'json':
                f.write(json.dumps(report, indent=2, ensure_ascii=False))
            elif args.format == 'markdown':
                # Capture markdown output
                import io
                from contextlib import redirect_stdout

                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    print_markdown(report)
                f.write(buffer.getvalue())
            else:
                import io
                from contextlib import redirect_stdout

                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    print_text(report)
                f.write(buffer.getvalue())

        print(f"\n✓ Report saved to {output_path}", file=sys.stderr)

if __name__ == '__main__':
    main()
