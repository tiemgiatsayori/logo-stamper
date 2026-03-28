FROM python:3.11-slim

WORKDIR /app

# Install system deps for Pillow and onnxruntime
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps first (for Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt

# Pre-download the U2-Net model so first run is instant
RUN python -c "from rembg import new_session; new_session('u2net')"

# Copy app files
COPY app.py .
COPY images/ images/

EXPOSE 7860

CMD ["python", "app.py"]
