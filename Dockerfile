FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

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

# Copy entire monorepo
COPY . .

# Ensure upload directories exist
RUN mkdir -p CRM/uploads data-analytics-assistant/uploads

# Streamlit configuration for the analytics service
RUN mkdir -p /root/.streamlit && printf '\
[server]\n\
headless = true\n\
enableCORS = false\n\
enableXsrfProtection = false\n\
port = 8501\n\
address = "0.0.0.0"\n\
maxUploadSize = 50\n\
\n\
[theme]\n\
base = "dark"\n\
backgroundColor = "#0f1117"\n\
secondaryBackgroundColor = "#161b27"\n\
textColor = "#e8eaf0"\n\
font = "sans serif"\n\
' > /root/.streamlit/config.toml

EXPOSE 8000 8501

# No default CMD — each docker-compose service sets its own command + working_dir
