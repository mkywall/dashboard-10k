FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install additional dependencies not in requirements.txt
RUN pip install --no-cache-dir pycrucible python-dotenv

# Copy application code
COPY dashboard_app.py .
COPY templates/ templates/

# Set environment variables
ENV FLASK_APP=dashboard_app.py
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8080

# Run the application
CMD ["python", "dashboard_app.py"]
