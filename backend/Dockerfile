FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
RUN useradd --create-home --uid 10001 smartdb && mkdir -p /app/config && chown -R smartdb:smartdb /app
USER smartdb
EXPOSE 5687/udp
ENTRYPOINT ["smartdb-ingestion"]
