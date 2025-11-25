FROM python:3.11-slim

WORKDIR /app

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ src/

# Install dependencies
RUN pip install --no-cache-dir .

# Run the backend service
CMD ["python", "-m", "src.backend.app"]
