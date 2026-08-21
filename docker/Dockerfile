# AutoMark AI — unified image (CRM + Campaigns + Analytics)
#
# Build context is the repo root:
#     docker build -f docker/Dockerfile -t automark .
# or via docker/docker-compose.yml, which sets the context for you.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# psycopg2-binary needs libpq; sentence-transformers needs build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies before copying source (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Single shared upload directory — every module writes here.
RUN mkdir -p /app/uploads

# Streamlit config, for the optional analytics admin UI service.
RUN mkdir -p /root/.streamlit && printf '\
[server]\n\
headless = true\n\
enableCORS = false\n\
enableXsrfProtection = false\n\
port = 8501\n\
address = "0.0.0.0"\n\
maxUploadSize = 200\n\
\n\
[theme]\n\
base = "dark"\n\
backgroundColor = "#0A0805"\n\
secondaryBackgroundColor = "#1C1610"\n\
textColor = "#e8eaf5"\n\
font = "sans serif"\n\
' > /root/.streamlit/config.toml

EXPOSE 8000 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# One app, one entry point. Compose overrides this for the analytics UI service.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
