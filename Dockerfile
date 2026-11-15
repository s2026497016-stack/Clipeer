# Clipeer: one image with the web server, the clip pipeline and ffmpeg.
FROM python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg ca-certificates bzip2 \
 && rm -rf /var/lib/apt/lists/*
# yt-dlp needs a JavaScript runtime for YouTube
COPY --from=denoland/deno:bin@sha256:b507583d3c68ba69f3ed2ce5969ae5b8b70f43421c781279c7aea06435263543 /deno /usr/local/bin/deno

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY studio studio
COPY web web
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin clipeer \
 && mkdir -p /data \
 && chown -R clipeer:clipeer /app /data

ENV CLIPEER_DATA=/data \
    CLIPEER_HOST=0.0.0.0 \
    CLIPEER_PORT=8765 \
    CLIPEER_TRUST_PROXY=1 \
    PYTHONUNBUFFERED=1
VOLUME /data
USER clipeer
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/healthz', timeout=4)"
# the first start downloads the speech model into /data/models (about 480 MB)
CMD ["sh", "-c", "python -m studio.fetch_model && python -m studio.server"]
