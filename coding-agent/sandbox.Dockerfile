# Custom sandbox image with common test tools pre-installed.
# Built once, reused for every sandbox run — no network needed at run time,
# so DockerRunner can keep network_disabled=True for safety.
FROM python:3.11-slim

RUN pip install --no-cache-dir pytest

WORKDIR /workspace
