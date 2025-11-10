"""
InMemoryRedis 단위 테스트 (pytest 수집용)

conftest.py의 InMemoryRedis 헬퍼 클래스가 Redis와 100% 호환인지 검증합니다.
이 테스트는 향후 Redis hash 관련 코드를 InMemoryRedis에서도 안전하게 사용할 수 있음을
보장합니다.
"""

import pytest
from tests.conftest import InMemoryRedis


class TestInMemoryRedisHsetCompatibility:
    """InMemoryRedis.hset이 Redis 호환성을 갖는지 검증"""

    def test_hset_single_field_addition(self):
        """단일 필드 추가 시 정확한 반환값 확인"""
        redis = InMemoryRedis()

        # 테스트 1: 단일 필드 설정
        result = redis.hset("test_hash", "field1", "value1")
        assert result == 1, "단일 필드 추가 시 1 반환"
        assert redis.hget("test_hash", "field1") == "value1"

    def test_hset_field_update(self):
        """기존 필드 업데이트 시 0 반환"""
        redis = InMemoryRedis()

        # 테스트 2: 같은 필드 업데이트
        redis.hset("test_hash", "field1", "value1")
        result = redis.hset("test_hash", "field1", "updated_value")
        assert result == 0, "기존 필드 업데이트 시 0 반환"
        assert redis.hget("test_hash", "field1") == "updated_value"

    def test_hset_mapping_multiple_fields(self):
        """mapping으로 여러 필드를 동시에 설정"""
        redis = InMemoryRedis()

        # 테스트 3: mapping으로 여러 필드 설정
        result = redis.hset("test_hash", mapping={"field2": "value2", "field3": "value3"})
        assert result == 2, "mapping으로 2개 필드 추가 시 2 반환"
        assert redis.hget("test_hash", "field2") == "value2"
        assert redis.hget("test_hash", "field3") == "value3"

    def test_hset_combined_key_value_and_mapping(self):
        """key/value와 mapping을 동시에 설정"""
        redis = InMemoryRedis()

        # 테스트 4: key/value + mapping 동시 설정
        result = redis.hset(
            "test_hash",
            "field4",
            "value4",
            mapping={"field5": "value5"}
        )
        assert result == 2, "key/value + mapping으로 2개 필드 추가 시 2 반환"
        assert redis.hget("test_hash", "field4") == "value4"
        assert redis.hget("test_hash", "field5") == "value5"

    def test_hgetall_retrieves_all_fields(self):
        """hgetall로 모든 필드를 정확하게 조회"""
        redis = InMemoryRedis()

        # 테스트 5: hgetall로 전체 조회
        redis.hset("test_hash", "field1", "value1")
        redis.hset("test_hash", mapping={"field2": "value2", "field3": "value3"})
        redis.hset("test_hash", "field4", "value4", mapping={"field5": "value5"})

        all_data = redis.hgetall("test_hash")
        assert len(all_data) == 5
        assert all_data["field1"] == "value1"
        assert all_data["field2"] == "value2"
        assert all_data["field3"] == "value3"
        assert all_data["field4"] == "value4"
        assert all_data["field5"] == "value5"

    def test_hset_mixed_new_and_existing_fields(self):
        """새로운 필드와 기존 필드가 섞여 있을 때 처리"""
        redis = InMemoryRedis()

        # 초기 설정
        redis.hset("test_hash", "field1", "value1")

        # 기존 필드1 + 새로운 필드2, 필드3 업데이트
        result = redis.hset(
            "test_hash",
            "field1",
            "updated_value1",
            mapping={"field2": "value2", "field3": "value3"}
        )

        # 반환값: field2, field3는 새로운 필드이므로 2 (field1은 업데이트이므로 카운트 안 함)
        assert result == 2, "새로운 필드 2개만 카운트"
        assert redis.hget("test_hash", "field1") == "updated_value1"
        assert redis.hget("test_hash", "field2") == "value2"
        assert redis.hget("test_hash", "field3") == "value3"

    def test_string_operations(self):
        """set/get 기본 기능 확인"""
        redis = InMemoryRedis()

        # String 값 설정
        result = redis.set("key1", "value1")
        assert result is True

        # String 값 조회
        assert redis.get("key1") == "value1"
        assert redis.get("nonexistent") is None

    def test_empty_hash_operations(self):
        """빈 hash에 대한 작업"""
        redis = InMemoryRedis()

        # 빈 hash 조회
        assert redis.hgetall("nonexistent") == {}
        assert redis.hget("nonexistent", "field") is None

    def test_redis_compatibility_comprehensive(self):
        """전체적인 Redis 호환성 검증"""
        redis = InMemoryRedis()

        # 복합 시나리오: TaskManager.create_task와 유사한 사용 패턴
        task_key = "task:test-uuid-123"
        task_data = {
            "task_id": "test-uuid-123",
            "status": "queued",
            "created_at": "2025-11-08T18:30:00.000Z",
            "progress": "0.0"
        }

        # Redis처럼 mapping으로 전체 저장
        result = redis.hset(task_key, mapping=task_data)
        assert result == 4, "4개 필드 추가"

        # 전체 조회
        stored_data = redis.hgetall(task_key)
        assert stored_data == task_data

        # 상태 업데이트
        result = redis.hset(task_key, "status", "running")
        assert result == 0, "기존 필드 업데이트는 0 반환"

        # 진행률 업데이트
        result = redis.hset(task_key, "progress", "0.75")
        assert result == 0

        # 업데이트된 상태 확인
        assert redis.hget(task_key, "status") == "running"
        assert redis.hget(task_key, "progress") == "0.75"

        # 전체 데이터 확인
        final_data = redis.hgetall(task_key)
        assert final_data["status"] == "running"
        assert final_data["progress"] == "0.75"
        assert final_data["task_id"] == "test-uuid-123"


@pytest.mark.parametrize(
    "initial_fields,update_mapping,expected_count",
    [
        # (초기 필드, 업데이트 mapping, 예상 반환값)
        ({}, {"a": 1, "b": 2, "c": 3}, 3),  # 모두 새로운 필드
        ({"a": 1}, {"a": 2, "b": 3}, 1),    # a는 업데이트, b는 새로운 필드
        ({"a": 1, "b": 2}, {"a": 2, "b": 3, "c": 4}, 1),  # c만 새로운 필드
        ({"a": 1}, {"b": 2}, 1),  # 다른 필드 추가
    ],
    ids=[
        "all_new_fields",
        "mixed_update_and_new",
        "one_new_among_updates",
        "disjoint_fields",
    ]
)
def test_hset_mapping_field_count(initial_fields, update_mapping, expected_count):
    """다양한 상황에서 hset의 반환값이 정확한지 검증"""
    redis = InMemoryRedis()
    hash_key = "test_hash"

    # 초기 필드 설정
    if initial_fields:
        redis.hset(hash_key, mapping=initial_fields)

    # 업데이트/추가
    result = redis.hset(hash_key, mapping=update_mapping)

    assert result == expected_count, (
        f"초기: {initial_fields}, 업데이트: {update_mapping}, "
        f"예상: {expected_count}, 실제: {result}"
    )
