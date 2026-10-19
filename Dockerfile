# Python for the app, plus Node.js because Meterless H-MEM (memory) runs on Node.
FROM node:22-slim AS nodebase

FROM python:3.12-slim
COPY --from=nodebase /usr/local/bin/node /usr/local/bin/node
COPY --from=nodebase /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN cd meterless && (npm install --no-audit --no-fund || echo "Meterless bridge install skipped")
EXPOSE 8000
# Default: print one report. For the web UI run:
#   docker run -p 8000:8000 stockwhy python run.py --serve --host 0.0.0.0
CMD ["python", "run.py", "--input", "input_examples/case1.json"]
