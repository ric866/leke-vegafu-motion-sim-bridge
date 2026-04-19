FROM mcr.microsoft.com/devcontainers/python:3.11

# Install system dependencies for GUI and USB support
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
    python3-tk \
    usbutils \
    libusb-1.0-0-dev

# Set the working directory
WORKDIR /workspaces/Leke-Vegafu-Motion-Sim-Bridge

# Pre-install our requirements
COPY requirements.txt .
RUN pip install -r requirements.txt
