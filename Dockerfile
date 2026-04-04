# ChemEng Docker Image
# Python 3.10 + FastAPI

FROM python:3.10-slim

LABEL maintainer="ZEAL-BOOT-CAMP"
LABEL description="ChemEng - Chemical Engineering Calculation Module"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements_full.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements_full.txt

COPY . .

RUN pip install --no-cache-dir -e .

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD sh -c 'python -c "import os, urllib.request; urllib.request.urlopen(\"http://localhost:%s/api\" % os.environ.get(\"PORT\", \"8000\"))"' || exit 1

CMD ["sh", "-c", "uvicorn chemeng.interface.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
