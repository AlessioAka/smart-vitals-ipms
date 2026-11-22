# The simulator image (build context = repository root). numpy only: small image.
FROM python:3.12-slim

WORKDIR /service

COPY simulator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/config.py src/rules.py src/__init__.py src/
COPY simulator/ simulator/
COPY data/patients.json data/patients.json

ENV PATIENTS_PATH=/service/data/patients.json \
    PYTHONUNBUFFERED=1

RUN useradd --create-home appuser
USER appuser

CMD ["python", "-m", "simulator.run_simulator"]
