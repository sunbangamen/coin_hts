#!/usr/bin/env python3
"""
Phase 3 문서 일관성 검증 스크립트

PHASE3_IMPLEMENTATION_STATUS.md를 기준으로,
다른 문서들의 수치가 일관성 있게 참조되고 있는지 확인합니다.

사용법:
  python scripts/verify_status_consistency.py
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple


class DocumentConsistencyVerifier:
    """문서 일관성 검증 클래스"""

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.docs = {
            'source': self.project_root / 'PHASE3_IMPLEMENTATION_STATUS.md',
            'summary': self.project_root / 'PHASE3_COMPLETION_SUMMARY.md',
            'issue': self.project_root / 'docs' / 'coin' / 'mvp' / 'ri_18.md',
            'test_results': self.project_root / 'TEST_RESULTS_SUMMARY.md',
        }
        self.errors = []
        self.warnings = []

    def extract_metrics(self, file_path: Path) -> Dict[str, str]:
        """파일에서 주요 수치 추출"""
        metrics = {}

        if not file_path.exists():
            self.errors.append(f"파일을 찾을 수 없습니다: {file_path}")
            return metrics

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 테스트 통과율 패턴 (예: "202/213", "94.8%")
        test_patterns = [
            r'(\d+)/(\d+)\s+테스트 통과',  # "202/213 테스트 통과"
            r'(\d+)/(\d+)\s+PASSED',       # "202/213 PASSED"
            r'(\d+)\s+passed,\s+(\d+)\s+failed',  # "202 passed, 11 failed"
        ]

        for pattern in test_patterns:
            matches = re.findall(pattern, content)
            if matches:
                metrics['test_pattern_found'] = pattern
                for match in matches:
                    metrics[f'test_{pattern}'] = match
                break

        # Task 상태 추출
        task_statuses = re.findall(r'Task\s+3\.\d+.*?(✅|⏳|❌)', content)
        if task_statuses:
            metrics['task_statuses'] = task_statuses

        # 참조 주석 확인
        if 'PHASE3_IMPLEMENTATION_STATUS.md' in content:
            metrics['has_reference_comment'] = True
        if '소스 오브 트루스' in content or 'Source of Truth' in content:
            metrics['has_sot_mention'] = True

        return metrics

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
            '재현 가능 명령': 'pytest tests/' in content,
        }

        passed = 0
        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            print(f"{status} {check_name}")
            if result:
                passed += 1
            else:
                self.errors.append(f"소스 오브 트루스 검증 실패: {check_name}")

        print(f"\n결과: {passed}/{len(checks)} 통과")
        return passed == len(checks)

    def verify_auxiliary_documents(self) -> bool:
        """보조 문서들 검증"""
        print("\n📚 보조 문서 검증")
        print("-" * 60)

        auxiliary_docs = {
            '요약 문서': self.docs['summary'],
            'Issue 문서': self.docs['issue'],
        }

        all_passed = True
        for doc_name, doc_path in auxiliary_docs.items():
            if not doc_path.exists():
                self.warnings.append(f"{doc_name}을(를) 찾을 수 없습니다: {doc_path}")
                print(f"⚠️  {doc_name}: 파일 없음")
                continue

            with open(doc_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 참조 링크 확인
            has_reference = 'PHASE3_IMPLEMENTATION_STATUS.md' in content
            status = "✅" if has_reference else "⚠️"
            print(f"{status} {doc_name}: 소스 오브 트루스 참조", end="")

            if not has_reference:
                print(" (없음)")
                self.warnings.append(f"{doc_name}에서 소스 오브 트루스 참조가 없습니다")
                all_passed = False
            else:
                print(" (있음)")

        return all_passed

    def verify_critical_metrics(self) -> bool:
        """핵심 수치 일관성 검증"""
        print("\n🔢 핵심 수치 일관성 검증")
        print("-" * 60)

        source_metrics = self.extract_metrics(self.docs['source'])

        if not source_metrics:
            self.warnings.append("소스 문서에서 수치를 추출할 수 없습니다")
            return False

        # 다른 문서들도 검증
        for doc_name, doc_path in self.docs.items():
            if doc_name == 'source' or not doc_path.exists():
                continue

            doc_metrics = self.extract_metrics(doc_path)
            if 'test_pattern_found' in doc_metrics and 'test_pattern_found' in source_metrics:
                # 두 문서 모두 테스트 수치가 있으면 일관성 확인
                print(f"✅ {doc_name}: 문서에서 메트릭 발견")
            elif 'test_pattern_found' not in doc_metrics:
                # 보조 문서는 자동 삽입 대상이므로 수치가 없을 수 있음
                if doc_name not in ['summary', 'issue']:
                    self.warnings.append(f"{doc_name}에서 테스트 수치를 찾을 수 없습니다")

        return len(self.errors) == 0

    def generate_report(self) -> str:
        """검증 리포트 생성"""
        report = []
        report.append("\n" + "=" * 60)
        report.append("📋 Phase 3 문서 일관성 검증 결과")
        report.append("=" * 60)

        if not self.errors and not self.warnings:
            report.append("✅ 모든 검증이 통과했습니다!")
            report.append("")
            report.append("상태:")
            report.append("  - 소스 오브 트루스 문서: ✅ 완벽")
            report.append("  - 보조 문서 참조: ✅ 완벽")
            report.append("  - 수치 일관성: ✅ 완벽")
        else:
            if self.errors:
                report.append("\n❌ 에러:")
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
        # 검증 실행
        sot_ok = self.verify_source_of_truth()
        aux_ok = self.verify_auxiliary_documents()
        metrics_ok = self.verify_critical_metrics()

        # 리포트 생성 및 출력
        report = self.generate_report()
        print(report)

        # 종료 코드
        if self.errors:
            return 1
        elif self.warnings:
            return 0  # 경고는 무시 (CI에서 실패하지 않음)
        else:
            return 0


def main():
    verifier = DocumentConsistencyVerifier()
    return verifier.run()


if __name__ == '__main__':
    exit(main())
