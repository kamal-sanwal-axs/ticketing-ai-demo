FROM python:3.12-slim-bookworm

# quickjs builds a native extension
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir \
    "quickjs>=1.19.0" \
    "RestrictedPython>=8.0"

COPY apex_rag_demo/__init__.py /app/apex_rag_demo/__init__.py
COPY apex_rag_demo/config.py /app/apex_rag_demo/config.py
COPY apex_rag_demo/plugins/__init__.py /app/apex_rag_demo/plugins/__init__.py
COPY apex_rag_demo/plugins/worker_runner.py /app/apex_rag_demo/plugins/worker_runner.py

ENV PYTHONPATH=/app
USER nobody
ENTRYPOINT ["python", "-m", "apex_rag_demo.plugins.worker_runner"]
