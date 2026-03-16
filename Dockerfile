FROM python:3.11-slim

LABEL org.opencontainers.image.description="strands-multi-engineer-agent"

# Runtime container for the agent CLI.
# For local development use a .venv instead (see scripts/bootstrap.sh).

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Create the non-root user before copying files so --chown on COPY sets
# ownership directly, avoiding an expensive post-copy chown -R over /app.
RUN useradd --create-home --no-log-init appuser

# Copy only the package source needed at runtime.
# See .dockerignore for what is excluded from the build context.
COPY --chown=appuser:appuser pyproject.toml ./
COPY --chown=appuser:appuser agent/       ./agent/
COPY --chown=appuser:appuser providers/   ./providers/
COPY --chown=appuser:appuser tools/       ./tools/
COPY --chown=appuser:appuser tasks/       ./tasks/
COPY --chown=appuser:appuser eval/        ./eval/
COPY --chown=appuser:appuser sample_repos/ ./sample_repos/

# Non-editable production install.
# Dev extras (pytest, mypy, ruff) are not needed at runtime.
# This layer is invalidated when pyproject.toml or source files change.
RUN pip install --no-cache-dir .

USER appuser

ENTRYPOINT ["agent"]
CMD ["--help"]
