FROM python:3.9-slim

WORKDIR /app

COPY ./ /app/agent

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "agent/core/app.py", "--config", "agent/arch/architecture.yaml"]
