# The Smart Vitals API image (build context = repository root)
FROM python:3.12-slim

WORKDIR /service

# 1. Libraries first: this layer is reused until requirements change
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Then the code, the model and the patient register
COPY src/ src/
COPY app/ app/
COPY dashboard/ dashboard/
COPY models/ models/
COPY data/patients.json data/patients.json

# Settings come from the environment, not the code
ENV MODEL_PATH=/service/models/smart_vitals_model.joblib \
    PATIENTS_PATH=/service/data/patients.json \
    DB_PATH=/data/smart_vitals.db \
    HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1

# Do not run as root inside the container
RUN useradd --create-home appuser && mkdir /data && chown appuser /data
USER appuser

EXPOSE 8000
CMD ["python", "-m", "app.main"]
