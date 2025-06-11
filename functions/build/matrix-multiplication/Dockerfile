FROM ghcr.io/openfaas/classic-watchdog:0.3.3 AS watchdog

FROM python:3.9-slim

# 1. Create app folder
RUN mkdir -p /home/app

# 2. Add fwatchdog from stage 1
COPY --from=watchdog /fwatchdog /usr/bin/fwatchdog
RUN chmod +x /usr/bin/fwatchdog

# 3. Set working directory and copy code
WORKDIR /home/app
COPY handler.py .
COPY requirements.txt .

# 4. Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 5. Add non-root user and adjust permissions
RUN useradd -ms /bin/bash app && chown -R app /home/app
USER app

ENV fprocess="python3 handler.py"
ENV write_debug="true"

EXPOSE 8080
HEALTHCHECK --interval=3s CMD [ -e /tmp/.lock ] || exit 1

CMD ["fwatchdog"]
