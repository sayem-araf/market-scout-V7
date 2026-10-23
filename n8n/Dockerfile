FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY market_scout.py scout_agent.py inventory_review.py automation_api.py ./
COPY data/demo ./data/demo
RUN useradd --uid 10001 --create-home scout
USER scout
CMD ["python", "automation_api.py", "--host", "0.0.0.0"]
