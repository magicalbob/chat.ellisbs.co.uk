# Use a lightweight version of the official Python image
FROM docker.ellisbs.co.uk:5190/python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Copy the rest of the application code to the working directory
COPY . .
COPY src src

# Install the application dependencies
RUN pip install --no-cache-dir -e .

# Create the database and run the application on startup
CMD ["python", "src/chat/app.py"]

# Expose the port the app runs on
EXPOSE 48080
