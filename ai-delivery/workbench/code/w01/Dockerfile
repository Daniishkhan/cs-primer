# Build on an Apple-silicon Mac with:
#   docker build --platform linux/amd64 -t YOU/zts-worker:v1 .
# RunPod's machines are x86-64 Linux; the flag stops an ARM image that
# would start and then fail.
FROM python:3.11-slim

WORKDIR /
# Dependencies first, so the layer is reused when only handler.py changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the weights into the image: no download at cold start.
ARG MODEL=HuggingFaceTB/SmolLM2-135M-Instruct
ENV MODEL=${MODEL}
RUN python -c "from huggingface_hub import snapshot_download; \
snapshot_download('${MODEL}')"

COPY handler.py .
# -u: unbuffered, so the logs show up in the RunPod console at once.
CMD ["python", "-u", "/handler.py"]
