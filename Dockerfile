# Use Python 3.11 to match App Runner configuration
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port 8000
EXPOSE 8000

# Set environment variable for port
ENV PORT=8000

# Command to run the application (matches apprunner.yaml)
CMD ["uvicorn", "web_app:app", "--host", "0.0.0.0", "--port", "8000"]