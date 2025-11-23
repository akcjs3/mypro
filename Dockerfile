FROM python:3.11-slim

WORKDIR /app

# (opencv 같은 패키지 때문에 필요한 시스템 라이브러리)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
  && rm -rf /var/lib/apt/lists/*

# requirements 먼저 복사해서 설치
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# backend 전체 복사
COPY backend/ .

ENV PORT=8000
EXPOSE 8000

CMD gunicorn server:app --bind 0.0.0.0:${PORT}
