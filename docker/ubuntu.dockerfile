# syntax=docker/dockerfile:1

# Copyright (c) 2025 Intel Corporation.
# SPDX-License-Identifier: BSD-3-Clause

# Ubuntu 22.04, builder stage
ARG IMAGE_CACHE_REGISTRY=docker.io
FROM "${IMAGE_CACHE_REGISTRY}/library/ubuntu:22.04@sha256:149d67e29f765f4db62aa52161009e99e389544e25a8f43c8c89d4a445a7ca37" AS builder

LABEL maintainer="andrzej.wilczynski@intel.com,dawid.wesierski@intel.com,marek.kasiewicz@intel.com"

ARG NPROC=20
ARG DPDK_VER=25.03
ENV PREFIX_PATH=/opt/intel
ENV MTL_REPO=${PREFIX_PATH}/mtl
ENV XDP_REPO=${PREFIX_PATH}/xdp
ENV DPDK_REPO=${PREFIX_PATH}/dpdk
ENV PKG_CONFIG_PATH=/usr/local/lib/pkgconfig:/usr/lib64/pkgconfig
ENV DEBIAN_FRONTEND="noninteractive"
ENV TZ="Europe/Warsaw"

SHELL ["/bin/bash", "-ex", "-o", "pipefail", "-c"]

# Install build dependencies and debug tools
WORKDIR "${DPDK_REPO}"
RUN apt-get update -y && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends ca-certificates sudo curl unzip apt-transport-https apt-utils python3-dev && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* && \
    curl -fsSL https://bootstrap.pypa.io/get-pip.py | python3 && \
    python3 -m pip --no-cache-dir install --upgrade pip setuptools

WORKDIR "${MTL_REPO}"
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends git build-essential python3-pyelftools pkg-config libnuma-dev libjson-c-dev libpcap-dev libgtest-dev libsdl2-dev libsdl2-ttf-dev libssl-dev && \
    apt-get install -y --no-install-recommends m4 clang llvm zlib1g-dev libelf-dev libcap-ng-dev libcap2-bin gcc-multilib; \
    apt-get install -y --no-install-recommends systemtap-sdt-dev || true; \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    python3 -m pip --no-cache-dir install meson ninja

COPY . "${MTL_REPO}"

# Clone DPDK and xdp-tools repo
WORKDIR "${XDP_REPO}"
RUN git clone https://github.com/DPDK/dpdk.git "${DPDK_REPO}" && \
    git clone --recurse-submodules https://github.com/xdp-project/xdp-tools.git "${XDP_REPO}"

# Build DPDK with Media-Transport-Library patches
WORKDIR "${DPDK_REPO}"
RUN git checkout v$DPDK_VER && \
    git switch -c v$DPDK_VER && \
    git config --global user.email "you@example.com" && \
    git config --global user.name "Your Name" && \
    git am "${MTL_REPO}/patches/dpdk/${DPDK_VER}/"*.patch && \
    meson setup build && \
    ninja -C build && \
    ninja -C build install && \
    DESTDIR=/install ninja -C build install

# Build the xdp-tools project
WORKDIR "${XDP_REPO}"
RUN ./configure && \
    make -j${NPROC:-$(nproc)} && \
    make -j${NPROC:-8} install && \
    DESTDIR=/install make -j${NPROC:-8} install && \
    mkdir -p /xdp-tools/lib/libbpf/src && \
    make -C "/xdp-tools/lib/libbpf/src" -j${NPROC:-$(nproc)} && \
    make -C "/xdp-tools/lib/libbpf/src" -j${NPROC:-8} install && \
    DESTDIR=/install make -C "/xdp-tools/lib/libbpf/src" -j${NPROC:-8} install

# Build MTL
WORKDIR /$MTL_REPO
RUN ./build.sh && \
    ninja -C build && \
    ninja -C build install && \
    DESTDIR=/install ninja -C build install && \
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
