FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCP_TRANSPORT=streamable-http \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --system studio \
    && useradd --system --gid studio --no-create-home studio

COPY main.py .
COPY studio/ ./studio/

USER studio
EXPOSE 8000

CMD ["python", "main.py"]
