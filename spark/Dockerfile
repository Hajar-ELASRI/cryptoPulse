FROM apache/spark:3.5.9-scala2.12-java17-python3-ubuntu
USER root
RUN pip3 install --no-cache-dir "pymongo>=4.8,<5" \
    && mkdir -p /tmp/ivy /opt/spark/checkpoints
COPY cryptopulse_spark /opt/cryptopulse/cryptopulse_spark
ENV PYTHONPATH=/opt/cryptopulse:/opt/spark/python:/opt/spark/python/lib/py4j-0.10.9.7-src.zip \
    PYTHONUNBUFFERED=1 \
    TZ=UTC
WORKDIR /opt/cryptopulse
