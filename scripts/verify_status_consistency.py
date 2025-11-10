#!/usr/bin/env python3
"""
Phase 3 문서 일관성 검증 스크립트 (개선판)

PHASE3_IMPLEMENTATION_STATUS.md를 기준으로,
다른 문서들의 수치가 일관성 있게 참조되고 있는지 확인합니다.

사용법:
  python scripts/verify_status_consistency.py                # 경고 수준 검증
  python scripts/verify_status_consistency.py --strict      # 에러 수준 검증 (CI/CD용)
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional


class DocumentConsistencyVerifier:
    """문서 일관성 검증 클래스"""

    def __init__(self, project_root: Path = None, strict: bool = False):
        self.project_root = project_root or Path(__file__).parent.parent
        self.strict = strict
        self.docs = {
            'source': self.project_root / 'PHASE3_IMPLEMENTATION_STATUS.md',
            'summary': self.project_root / 'PHASE3_COMPLETION_SUMMARY.md',
            'issue': self.project_root / 'docs' / 'coin' / 'mvp' / 'ri_18.md',
            'test_results': self.project_root / 'TEST_RESULTS_SUMMARY.md',
        }
        # 문서별 필수 AUTO 블록
        self.required_auto_blocks = {
            'source': ['AUTO-BEGIN: TEST_STATISTICS', 'AUTO-BEGIN: TASK_STATUS'],
            'summary': ['AUTO-BEGIN: COMPLETION_SUMMARY_STATISTICS'],
            'issue': ['AUTO-BEGIN: ISSUE_29_METRICS'],
        }
        self.errors = []
        self.warnings = []
        self.source_metrics = {}
        self._missing_docs = []

    def parse_test_metrics(self, content: str) -> Optional[Dict[str, int]]:
        """문서에서 테스트 수치 파싱"""
        # 패턴: "192/203 (94.5%) 테스트 통과" 등
        pattern = r'(\d+)/(\d+)\s*\(([0-9.]+)%\)\s*테스트 통과'
        match = re.search(pattern, content)

        if match:
            return {
                'passed': int(match.group(1)),
                'total': int(match.group(2)),
                'pass_rate': float(match.group(3)),
                'failed': int(match.group(2)) - int(match.group(1)),
            }
        return None

    def extract_metrics_from_source(self) -> bool:
        """소스 오브 트루스 문서에서 메트릭 추출"""
        source_file = self.docs['source']
        if not source_file.exists():
            self.errors.append(f"소스 오브 트루스 파일을 찾을 수 없습니다: {source_file}")
            return False

        with open(source_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 테스트 메트릭 파싱
        metrics = self.parse_test_metrics(content)
        if not metrics:
            self.errors.append("소스 문서에서 테스트 수치를 파싱할 수 없습니다")
            return False

        self.source_metrics = metrics
        return True

    def verify_source_of_truth(self) -> bool:
        """소스 오브 트루스 문서 검증"""
        print("\n📌 소스 오브 트루스 문서 검증")
        print("-" * 60)

        source_file = self.docs['source']
        if not source_file.exists():
            self.errors.append(f"소스 오브 트루스 파일을 찾을 수 없습니다: {source_file}")
            return False

        with open(source_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 필수 섹션 확인
        checks = {
            '소스 오브 트루스 표시': '🔴 소스 오브 트루스' in content,
            '마지막 업데이트 시간': '**마지막 업데이트**' in content,
            '업데이트 명령': 'scripts/generate_phase3_status.py' in content,
            '상태 검증 명령': '--strict' in content,
            'AUTO 블록 (TEST_STATISTICS)': 'AUTO-BEGIN: TEST_STATISTICS' in content,
            'AUTO 블록 (TASK_STATUS)': 'AUTO-BEGIN: TASK_STATUS' in content,
            '재현 가능 명령': 'pytest' in content,
        }

        passed = 0
        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            print(f"{status} {check_name}")
            if result:
                passed += 1
            else:
                if self.strict:
                    self.errors.append(f"SOT 검증 실패: {check_name}")
                else:
                    self.warnings.append(f"SOT 검증 실패: {check_name}")

        print(f"\n결과: {passed}/{len(checks)} 통과")
        return passed == len(checks)

    def verify_metrics_consistency(self) -> bool:
        """다중 문서 간 수치 일관성 검증"""
        print("\n📊 수치 일관성 검증")
        print("-" * 60)

        if not self.source_metrics:
            print("⚠️  소스 문서의 메트릭이 없습니다")
            return False

        source_str = f"{self.source_metrics['passed']}/{self.source_metrics['total']}"
        print(f"📌 기준값 (SOT): {source_str} ({self.source_metrics['pass_rate']:.1f}%)")

        all_consistent = True
        for doc_name, doc_path in self.docs.items():
            if doc_name == 'source' or not doc_path.exists():
                continue

            with open(doc_path, 'r', encoding='utf-8') as f:
                content = f.read()

            metrics = self.parse_test_metrics(content)
            if not metrics:
                status = "⚠️"
                result = "(수치 없음)"
                if self.strict and doc_name in ['summary', 'issue']:
                    # 보조 문서에서 수치가 없으면 경고
                    self.warnings.append(f"{doc_name}에서 테스트 수치를 찾을 수 없습니다")
            else:
                # 수치 일치 확인
                match = (metrics['passed'] == self.source_metrics['passed'] and
                         metrics['total'] == self.source_metrics['total'])
                status = "✅" if match else "❌"
                result = f"{metrics['passed']}/{metrics['total']} ({metrics['pass_rate']:.1f}%)"

                if not match:
                    all_consistent = False
                    error_msg = f"{doc_name}: {result} (기준값과 불일치)"
                    if self.strict:
                        self.errors.append(error_msg)
                    else:
                        self.warnings.append(error_msg)

            print(f"{status} {doc_name}: {result}")

        return all_consistent

    def verify_auto_blocks(self) -> bool:
        """AUTO 블록 존재 및 내용 검증"""
        print("\n🔲 AUTO 블록 검증 (모든 문서)")
        print("-" * 60)

        all_present = True

        for doc_name, doc_path in self.docs.items():
            if doc_name == 'test_results':
                continue

            if not doc_path.exists():
                status = "❌"
                print(f"{status} {doc_name}: 파일을 찾을 수 없습니다")
                self._missing_docs.append(doc_name)
                all_present = False
                if self.strict:
                    self.errors.append(f"문서를 찾을 수 없습니다: {doc_path}")
                continue

            with open(doc_path, 'r', encoding='utf-8') as f:
                content = f.read()

            required_blocks = self.required_auto_blocks.get(doc_name, [])
            if not required_blocks:
                continue

            # 각 문서의 필수 AUTO 블록 확인
            doc_blocks_present = True
            for block in required_blocks:
                if block not in content:
                    doc_blocks_present = False
                    all_present = False
                    if self.strict:
                        self.errors.append(f"{doc_name}에서 필수 AUTO 블록을 찾을 수 없습니다: {block}")
                    else:
                        self.warnings.append(f"{doc_name}에서 필수 AUTO 블록을 찾을 수 없습니다: {block}")

            status = "✅" if doc_blocks_present else "❌"
            blocks_desc = f"({len(required_blocks)}개)" if required_blocks else ""
            print(f"{status} {doc_name}: {blocks_desc}")

        return all_present

    def generate_report(self) -> str:
        """검증 리포트 생성"""
        report = []
        report.append("\n" + "=" * 60)
        report.append("📋 Phase 3 문서 일관성 검증 결과")
        report.append("=" * 60)

        if not self.errors and not self.warnings:
            report.append("✅ 모든 검증이 통과했습니다! (Strict 모드)" if self.strict else "✅ 모든 검증이 통과했습니다!")
            report.append("")
            report.append("상태:")
            report.append("  - 소스 오브 트루스 문서: ✅ 완벽")
            report.append("  - 수치 일관성: ✅ 완벽")
            report.append("  - AUTO 블록: ✅ 완벽")
        else:
            if self.errors:
                report.append("\n❌ 에러 (Strict 모드):" if self.strict else "\n❌ 에러:")
                for error in self.errors:
                    report.append(f"  - {error}")

            if self.warnings:
                report.append("\n⚠️  경고:")
                for warning in self.warnings:
                    report.append(f"  - {warning}")

        report.append("")
        report.append("=" * 60)

        return "\n".join(report)

    def run(self) -> int:
        """실행"""
        print("🔍 Phase 3 문서 일관성 검증 시작")
        print(f"엄격 모드: {'✅ 활성화' if self.strict else '⚠️ 비활성화'}")

        # 1. 소스 메트릭 추출
        if not self.extract_metrics_from_source():
            report = self.generate_report()
            print(report)
            return 1 if self.strict else 0

        # 2. 검증 실행
        sot_ok = self.verify_source_of_truth()
        metrics_ok = self.verify_metrics_consistency()
        blocks_ok = self.verify_auto_blocks()

        # 3. 리포트 생성 및 출력
        report = self.generate_report()
        print(report)

        # 4. 종료 코드 결정
        if self.strict:
            # Strict 모드: 에러가 있으면 실패
            if self.errors:
                return 1
        else:
            # 일반 모드: 에러만 체크
            if self.errors:
                return 1

        return 0


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Phase 3 문서 일관성 검증"
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help="strict 모드 활성화 (모든 불일치를 에러로 취급)"
    )

    args = parser.parse_args()

    verifier = DocumentConsistencyVerifier(strict=args.strict)
    return verifier.run()


if __name__ == '__main__':
    exit(main())
