FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir websocket-client>=1.4.0

COPY . /app

EXPOSE 8501

CMD ["streamlit", "run", "app.py"]