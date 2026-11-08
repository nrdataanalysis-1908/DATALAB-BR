FROM python:3.12-slim

WORKDIR /app

COPY apps/analytics/requirements.txt ./apps/analytics/requirements.txt
RUN python -m pip install --no-cache-dir -r apps/analytics/requirements.txt

COPY apps/analytics/app.py ./apps/analytics/app.py
COPY apps/analytics/catalog_data.py ./apps/analytics/catalog_data.py
COPY apps/analytics/generate_report.py ./apps/analytics/generate_report.py
COPY catalog ./catalog

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

CMD ["streamlit", "run", "apps/analytics/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
