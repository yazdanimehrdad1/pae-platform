FROM python:3.11-slim

RUN groupadd --gid 1000 modbus && \
    useradd --uid 1000 --gid modbus --create-home modbus

WORKDIR /opt/mock-modbus

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

RUN chown -R modbus:modbus /opt/mock-modbus

USER modbus

EXPOSE 502

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1',502)); s.close()"

CMD ["python", "-m", "app.server"]
