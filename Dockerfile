# Copyright (c) 2021 Intel Corporation.

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Dockerfile for EII Web UI Deplyment Tool Backend

ARG EII_VERSION
ARG UBUNTU_IMAGE_VERSION
FROM ia_eiibase:$EII_VERSION as builder
LABEL description="EII Web UI Deployment Tool Backend Image"
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --user -r requirements.txt
FROM ubuntu:$UBUNTU_IMAGE_VERSION as runtime
USER root

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive \
    apt-get install -y --no-install-recommends \
    python3-distutils \
    python3-minimal \
    libopencv-dev \
    python3-opencv \
    v4l-utils \
    ssh \
    rsync \
    sshpass && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
ARG CMAKE_INSTALL_PREFIX
ENV PYTHONPATH=$PYTHONPATH:/app/.local/lib/python3.8/site-packages:/app \
    LD_LIBRARY_PATH=$LD_LIBRARY_PATH:${CMAKE_INSTALL_PREFIX}/lib \
    PATH=$PATH:/app/.local/bin
COPY --from=builder /root/.local/lib .local/lib
COPY --from=builder /app .
COPY ./eii_deployment_tool_backend.py /app/
COPY ./libs /app/libs

HEALTHCHECK NONE
ENTRYPOINT python3 eii_deployment_tool_backend.py $DEPLOYMENT_TOOL_BACKEND_PORT
