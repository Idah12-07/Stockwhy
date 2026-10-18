FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Offline mode needs no keys. Override the command to run any input.
CMD ["python", "run.py", "--input", "input_examples/case1.json"]
