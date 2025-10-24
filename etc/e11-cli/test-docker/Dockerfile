# Use the official Ubuntu 22.04 base image
FROM ubuntu:22.04

# Install necessary packages for sudo
RUN apt-get update && \
    apt-get install -y sudo && \
    rm -rf /var/lib/apt/lists/*

# Create the 'ubuntu' user and add it to the sudo group
RUN useradd -m -s /bin/bash ubuntu && \
    echo "ubuntu:password" | chpasswd && \
    usermod -aG sudo ubuntu

# (Optional) Allow 'ubuntu' user to run sudo without a password
# This is generally not recommended for security reasons in production environments,
# but can be useful for development or specific testing scenarios.
# RUN echo 'ubuntu ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

# Set the default user for subsequent commands
USER ubuntu

# Set the working directory (optional)
WORKDIR /home/ubuntu

# Define the command to run when the container starts (optional)
CMD ["/bin/bash"]
