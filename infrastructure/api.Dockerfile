FROM python:3.12.14-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/backend
WORKDIR /app
COPY requirements.lock ./requirements.lock
RUN --mount=type=cache,target=/root/.cache/pip python -m pip install --timeout 120 --retries 5 --require-hashes -r requirements.lock \
    && groupadd --gid 10001 cloud \
    && useradd --uid 10001 --gid cloud --no-create-home cloud \
    && mkdir -p /srv/storage && chown cloud:cloud /srv/storage
RUN python -m pip uninstall --yes pip
COPY backend ./backend
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
