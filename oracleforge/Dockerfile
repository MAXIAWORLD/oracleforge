FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

ENV ENV=dev
ENV DB_PATH=/tmp/oracle.sqlite
ENV API_KEY_PEPPER=glama-test-pepper

EXPOSE 8003

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
