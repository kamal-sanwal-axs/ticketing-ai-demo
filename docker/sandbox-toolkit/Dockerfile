FROM node:20-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements.txt

WORKDIR /opt/react-shell
COPY react-shell/ ./
RUN npm install --no-audit --no-fund

COPY run_job.py /opt/run_job.py
RUN chmod +x /opt/run_job.py

RUN useradd -m -u 10001 sandbox
USER sandbox
ENTRYPOINT ["python3", "/opt/run_job.py"]
