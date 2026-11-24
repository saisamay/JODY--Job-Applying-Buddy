FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/apps/api
WORKDIR /app
COPY apps/api/requirements.txt requirements-dev.lock ./
RUN pip install --disable-pip-version-check --no-cache-dir -c requirements-dev.lock -r requirements.txt \
    && useradd --system --uid 10001 --no-create-home jody
COPY alembic.ini .
COPY apps/api /app/apps/api
USER 10001
EXPOSE 10000
CMD ["python", "-m", "jody.preview"]
