FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create upload directory
RUN mkdir -p uploads

# Streamlit configuration
RUN mkdir -p /root/.streamlit
RUN echo '\
[general]\n\
email = ""\n\
\n\
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

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app/ui/streamlit_app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]
