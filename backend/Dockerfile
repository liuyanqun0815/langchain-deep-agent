FROM python:3.11-slim

WORKDIR /app

# 系统依赖：build-essential（pdf 等）、git（从 GitHub 添加技能）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# skills 由 volume 挂载，镜像中仅创建空目录占位
RUN mkdir -p data skills

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# 生产环境不使用 reload
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
