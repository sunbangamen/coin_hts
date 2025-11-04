"""RQ 설정 파일"""
import os
from redis import Redis

# Redis 연결 설정
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# Redis 클라이언트
redis_conn = Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True,
    socket_keepalive=True,
    socket_keepalive_options={},
)

# RQ 워커 설정
RQ_RESULT_TTL = 500  # 결과 보관 시간 (초)
RQ_FAILURE_TTL = 86400  # 실패 결과 보관 시간 (초) = 1일
RQ_DEFAULT_RESULT_TTL = 500
RQ_JOB_TIMEOUT = 3600  # 작업 타임아웃 (초) = 1시간

# 워커 동시성 설정
RQ_WORKER_CLASS = "rq.Worker"
RQ_QUEUE_CLASS = "rq.Queue"

# 로깅 설정
RQ_LOG_LEVEL = os.getenv("RQ_LOG_LEVEL", "INFO")
