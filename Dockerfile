FROM python:3.11-slim

# 작업 디렉터리
WORKDIR /app

# 환경 변수 설정
ENV DATA_ROOT=/data \
    TZ=Asia/Seoul \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 데이터 디렉터리 생성
RUN mkdir -p /data

# 기본 명령
CMD ["python", "-m", "pytest", "tests/", "-v"]
