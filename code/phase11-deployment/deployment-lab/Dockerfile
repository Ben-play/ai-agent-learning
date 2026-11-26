# Synthetic classroom image. This mutable base tag and unlocked dependencies are not release evidence.
FROM python:3.11-slim
WORKDIR /course
COPY code/phase11-deployment/deployment-lab/pyproject.toml /tmp/course-http/pyproject.toml
RUN python -m pip install --no-cache-dir /tmp/course-http \
    && mkdir /state && chown 10001:10001 /state
COPY code/phase4-prompt-context/main.py code/phase4-prompt-context/main.py
COPY code/phase5-agent-harness/harness-lab/main.py code/phase5-agent-harness/harness-lab/main.py
COPY code/phase7-data-rag/rag-lab/lab.py code/phase7-data-rag/rag-lab/lab.py
COPY code/phase7-data-rag/rag-lab/assessment/checks.py code/phase7-data-rag/rag-lab/assessment/checks.py
COPY code/phase8-agent-engineering/engineering-lab/observations.py code/phase8-agent-engineering/engineering-lab/observations.py
COPY code/phase11-deployment/deployment-lab/host.py code/phase11-deployment/deployment-lab/host.py
COPY code/phase11-deployment/deployment-lab/http_app.py code/phase11-deployment/deployment-lab/http_app.py
WORKDIR /course/code/phase11-deployment/deployment-lab
USER 10001:10001
CMD ["python", "-B", "-m", "uvicorn", "http_app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers", "--no-access-log"]
