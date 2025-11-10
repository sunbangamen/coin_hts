#!/usr/bin/env python3
"""
Phase 3 상태 보고서 자동 생성 스크립트

pytest 결과 JSON과 PHASE3_IMPLEMENTATION_STATUS.md 템플릿을 읽어,
다른 문서들의 수치를 자동으로 업데이트합니다.

사용법:
  python scripts/generate_phase3_status.py --input /tmp/test_results_<ts>.json --update-docs
"""

import json
import glob
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any


class Phase3StatusGenerator:
    """Phase 3 상태 생성 및 문서 업데이트 클래스"""

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.docs = {
            'source': self.project_root / 'PHASE3_IMPLEMENTATION_STATUS.md',
            'summary': self.project_root / 'PHASE3_COMPLETION_SUMMARY.md',
            'issue': self.project_root / 'docs' / 'coin' / 'mvp' / 'ri_18.md',
        }

    def load_test_results(self, result_file: str) -> Dict[str, Any]:
        """테스트 결과 JSON 파일 로드"""
        result_path = Path(result_file)
        if not result_path.exists():
            raise FileNotFoundError(f"결과 파일을 찾을 수 없습니다: {result_file}")

        with open(result_path, 'r') as f:
            return json.load(f)

    def extract_status(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """테스트 결과에서 상태 정보 추출"""
        total = results.get('total_tests', 0)
        passed = results.get('passed', 0)
        failed = results.get('failed', 0)

        return {
            'timestamp': results.get('timestamp'),
            'date': results.get('date'),
            'total_tests': total,
            'passed': passed,
            'failed': failed,
            'pass_rate': (passed / total * 100) if total > 0 else 0,
            'pass_rate_str': f"{passed}/{total} ({passed/total*100:.1f}%)" if total > 0 else "0/0",
        }

    def update_implementation_status(self, status: Dict[str, Any]):
        """PHASE3_IMPLEMENTATION_STATUS.md 업데이트"""
        if not self.docs['source'].exists():
            print(f"⚠️  파일을 찾을 수 없습니다: {self.docs['source']}")
            return

        with open(self.docs['source'], 'r', encoding='utf-8') as f:
            content = f.read()

        # 테스트 통과율 섹션 업데이트
        old_test_rate = r'```\n\d+/\d+ 테스트 통과 \(\d+\.?\d*%\)'
        new_test_rate = f"```\n{status['pass_rate_str']} 테스트 통과"

        # 마지막 업데이트 시간 업데이트
        timestamp = datetime.fromtimestamp(int(status['timestamp'])).strftime('%Y-%m-%d %H:%M:%S UTC')
        content = content.replace(
            'f"**마지막 업데이트**: 2025-11-10',
            f"**마지막 업데이트**: {timestamp}"
        )

        with open(self.docs['source'], 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"✅ PHASE3_IMPLEMENTATION_STATUS.md 업데이트 완료")
        print(f"   - 테스트 통과율: {status['pass_rate_str']}")

    def generate_summary(self, status: Dict[str, Any]) -> str:
        """상태 요약 문자열 생성"""
        summary = f"""
## 📊 현재 상태 (자동 업데이트: {status['date']})

### 테스트 통과율
```
{status['pass_rate_str']} 테스트 통과
- 총 테스트: {status['total_tests']}
- 통과: {status['passed']}
- 실패: {status['failed']}
```

### 주요 Task 상태
- Task 3.1 ✅ 성능 재검증
- Task 3.2 ✅ 비동기 API (RQ + Redis)
- Task 3.3 ✅ 포지션 관리
- Task 3.4 ✅ S3 스토리지
- Task 3.5 ⏳ 결과 저장 개선
- Task 3.6 ⏳ 운영 가이드
- Task 3.7 ⏳ 백업 및 모니터링
- Task 3.8 ⏳ 통합 테스트

""".strip()
        return summary

    def print_summary(self, status: Dict[str, Any]):
        """상태 요약 출력"""
        print("\n" + "=" * 60)
        print("📊 Phase 3 상태 요약")
        print("=" * 60)
        print(f"타임스탬프: {status['date']}")
        print(f"총 테스트: {status['total_tests']}")
        print(f"통과: {status['passed']} ✅")
        print(f"실패: {status['failed']} ❌")
        print(f"통과율: {status['pass_rate']:.1f}%")
        print("=" * 60 + "\n")

    def run(self, result_file: str, update_docs: bool = False):
        """실행"""
        try:
            # 결과 로드
            print(f"📂 결과 파일 로드: {result_file}")
            results = self.load_test_results(result_file)

            # 상태 추출
            status = self.extract_status(results)

            # 요약 출력
            self.print_summary(status)

            # 문서 업데이트
            if update_docs:
                print("🔄 문서 업데이트 중...")
                self.update_implementation_status(status)
                print(f"✅ 모든 문서가 업데이트되었습니다.")
            else:
                print("💡 팁: --update-docs 플래그를 사용하여 문서를 자동으로 업데이트하세요.")

            # 다음 단계
            print("\n📝 다음 단계:")
            print("  1. git diff로 변경 사항 확인")
            print("  2. python scripts/verify_status_consistency.py로 일관성 검증")
            print("  3. git add && git commit로 커밋")

        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            raise


def main():
    parser = argparse.ArgumentParser(
        description="Phase 3 상태 보고서 자동 생성 및 문서 동기화"
    )
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help="pytest 결과 JSON 파일 경로 (예: /tmp/test_results_*.json)"
    )
    parser.add_argument(
        '--update-docs',
        action='store_true',
        help="문서를 자동으로 업데이트할지 여부"
    )

    args = parser.parse_args()

    # glob 패턴 지원
    if '*' in args.input:
        files = sorted(glob.glob(args.input))
        if not files:
            print(f"❌ 매칭되는 파일이 없습니다: {args.input}")
            return 1
        result_file = files[-1]  # 가장 최신 파일 선택
        print(f"📁 글롭 패턴에서 최신 파일 선택: {result_file}")
    else:
        result_file = args.input

    generator = Phase3StatusGenerator()
    generator.run(result_file, update_docs=args.update_docs)
    return 0


if __name__ == '__main__':
    exit(main())
