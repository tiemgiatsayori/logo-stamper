FROM python:3.11-slim

WORKDIR /app

# Install system deps for Pillow and onnxruntime
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps first (for Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY app.py .
COPY index.html .
COPY images/ images/

EXPOSE 7860

CMD ["python", "app.py"]
