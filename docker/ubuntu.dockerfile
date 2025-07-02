# syntax=docker/dockerfile:1

# Copyright (c) 2025 Intel Corporation.
# SPDX-License-Identifier: BSD-3-Clause

# Ubuntu 22.04, builder stage
ARG IMAGE_CACHE_REGISTRY=docker.io
FROM "${IMAGE_CACHE_REGISTRY}/library/ubuntu:22.04@sha256:149d67e29f765f4db62aa52161009e99e389544e25a8f43c8c89d4a445a7ca37" AS builder

LABEL maintainer="andrzej.wilczynski@intel.com,dawid.wesierski@intel.com,marek.kasiewicz@intel.com"

ENV MTL_REPO=Media-Transport-Library
ENV DPDK_VER=25.03
ENV PKG_CONFIG_PATH=/usr/local/lib/pkgconfig:/usr/lib64/pkgconfig
ENV DEBIAN_FRONTEND="noninteractive"
ENV TZ="Europe/Warsaw"

SHELL ["/bin/bash", "-ex", "-o", "pipefail", "-c"]

# Install build dependencies and debug tools
RUN apt-get clean && rm -rf /var/lib/apt/lists/* && \
    apt-get update -y && \
    apt-get install -y --no-install-recommends ca-certificates sudo curl unzip
    apt-get install -y --no-install-recommends git build-essential meson python3 python3-pyelftools pkg-config libnuma-dev libjson-c-dev libpcap-dev libgtest-dev libsdl2-dev libsdl2-ttf-dev libssl-dev ca-certificates && \
    apt-get install -y --no-install-recommends m4 clang llvm zlib1g-dev libelf-dev libcap-ng-dev libcap2-bin gcc-multilib; \
    apt-get install -y --no-install-recommends systemtap-sdt-dev || true; \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY . $MTL_REPO

# Clone DPDK and xdp-tools repo
RUN git clone https://github.com/DPDK/dpdk.git && \
    git clone --recurse-submodules https://github.com/xdp-project/xdp-tools.git

# Build DPDK with Media-Transport-Library patches
WORKDIR /dpdk
RUN git checkout v$DPDK_VER && \
    git switch -c v$DPDK_VER && \
    git config --global user.email "you@example.com" && \
    git config --global user.name "Your Name" && \
    git am ../$MTL_REPO/patches/dpdk/$DPDK_VER/*.patch && \
    meson setup build && \
    meson install -C build && \
    DESTDIR=/install meson install -C build

# Build the xdp-tools project
WORKDIR /xdp-tools
RUN ./configure && make &&\
    make install && \
    DESTDIR=/install make install
WORKDIR /xdp-tools/lib/libbpf/src
RUN make install && \
    DESTDIR=/install make install

# Build MTL
WORKDIR /$MTL_REPO
RUN ./build.sh && \
    DESTDIR=/install meson install -C build && \
    setcap 'cap_net_raw+ep' ./tests/tools/RxTxApp/build/RxTxApp

# Ubuntu 22.04, runtime/final stage
ARG IMAGE_CACHE_REGISTRY
FROM "${IMAGE_CACHE_REGISTRY}/library/ubuntu:22.04@sha256:149d67e29f765f4db62aa52161009e99e389544e25a8f43c8c89d4a445a7ca37" AS final

LABEL org.opencontainers.image.authors="andrzej.wilczynski@intel.com,dawid.wesierski@intel.com,marek.kasiewicz@intel.com"
LABEL org.opencontainers.image.url="https://github.com/OpenVisualCloud/Media-Transport-Library"
LABEL org.opencontainers.image.title="Intel® Media Transport Library"
LABEL org.opencontainers.image.description="Intel® Media Transport Library (MTL), a real-time media transport(DPDK, AF_XDP, RDMA) stack for both raw and compressed video based on COTS hardware"
LABEL org.opencontainers.image.documentation="https://openvisualcloud.github.io/Media-Transport-Library/README.html"
LABEL org.opencontainers.image.version="1.26.0"
LABEL org.opencontainers.image.vendor="Intel® Corporation"
LABEL org.opencontainers.image.licenses="BSD 3-Clause License"

ENV DEBIAN_FRONTEND="noninteractive"
ENV TZ="Europe/Warsaw"
SHELL ["/bin/bash", "-ex", "-o", "pipefail", "-c"]

# Install runtime dependencies
WORKDIR /home/imtl/
RUN apt-get clean -y && rm -rf /var/lib/apt/lists/* && \
    apt-get update -y && \
    apt-get install -y --no-install-recommends ca-certificates sudo curl unzip && \
    apt-get install -y --no-install-recommends libnuma1 libjson-c5 libpcap0.8 libsdl2-2.0-0 libsdl2-ttf-2.0-0 libssl3 zlib1g libelf1 libcap-ng0 libatomic1 && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    echo "Add user: imtl(20001) with group vfio(2110)" && \
    groupadd -g 2110 vfio && \
    useradd -m -G vfio,root,sudo -u 20001 imtl

# Copy libraries and binaries
COPY --chown=imtl --from=builder /install /
COPY --chown=imtl --from=builder /Media-Transport-Library/build /home/imtl
COPY --chown=imtl --from=builder /Media-Transport-Library/tests/tools/RxTxApp/build/RxTxApp /home/imtl/RxTxApp
COPY --chown=imtl --from=builder /Media-Transport-Library/tests/tools/RxTxApp/script /home/imtl/scripts

RUN ldconfig
SHELL ["/bin/bash", "-c"]

USER imtl
HEALTHCHECK --interval=30s --timeout=5s CMD true || exit 1
CMD ["/bin/bash"]
