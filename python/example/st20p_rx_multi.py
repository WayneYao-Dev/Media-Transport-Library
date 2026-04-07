# SPDX-License-Identifier: BSD-3-Clause
# Copyright 2026 Intel Corporation

"""Module of MTL st20p multi-stream rx python example."""

import argparse
import ctypes
import sys

import cv2
import misc_util
import pymtl as mtl


def parse_csv_list(value):
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_int_csv_list(value):
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def parse_args():
    parser = argparse.ArgumentParser(
        description="MTL ST20P multi-stream rx python example"
    )
    parser.add_argument("--p_port", type=str, required=True, help="primary port name")
    parser.add_argument("--p_sip", type=str, required=True, help="primary local IP")
    parser.add_argument(
        "--p_rx_ips",
        type=parse_csv_list,
        required=True,
        help="rx multicast/source IP list, separated by comma",
    )
    parser.add_argument(
        "--udp_ports",
        type=parse_int_csv_list,
        required=True,
        help="rx udp port list, separated by comma",
    )
    parser.add_argument(
        "--payload_types",
        type=parse_int_csv_list,
        default=None,
        help="payload type list, separated by comma, default all 112",
    )
    parser.add_argument(
        "--pipeline_fmt",
        type=misc_util.parse_pipeline_fmt,
        default=mtl.ST_FRAME_FMT_YUV422PLANAR10LE,
        help="pipeline_fmt",
    )
    parser.add_argument(
        "--transport_fmt",
        type=misc_util.parse_transport_fmt,
        default=mtl.ST20_FMT_YUV_422_10BIT,
        help="transport_fmt",
    )
    parser.add_argument("--width", type=int, default=1920, help="width")
    parser.add_argument("--height", type=int, default=1080, help="height")
    parser.add_argument(
        "--fps",
        type=misc_util.parse_fps,
        default=mtl.ST_FPS_P59_94,
        help="fps",
    )
    parser.add_argument(
        "--interlaced", action="store_true", help="Enable interlaced option"
    )
    parser.add_argument("--ptp", action="store_true", help="Enable built-in PTP")
    parser.add_argument(
        "--display", action="store_true", help="display all streams in separate windows"
    )
    parser.add_argument(
        "--display_scale_factor", type=int, default=2, help="display scale factor"
    )
    parser.add_argument(
        "--rss_mode",
        type=misc_util.parse_rss_mode,
        default=mtl.MTL_RSS_MODE_NONE,
        help="rss_mode",
    )
    parser.add_argument(
        "--pacing_way",
        type=misc_util.parse_pacing_way,
        default=mtl.ST21_TX_PACING_WAY_AUTO,
        help="pacing_way",
    )
    parser.add_argument("--nb_tx_desc", type=int, default=0, help="nb_tx_desc")
    parser.add_argument("--nb_rx_desc", type=int, default=0, help="nb_rx_desc")
    parser.add_argument("--lcores", type=str, default="", help="lcores")
    return parser.parse_args()


def validate_args(args):
    session_cnt = len(args.p_rx_ips)
    if session_cnt == 0:
        raise ValueError("at least one rx stream is required")
    if len(args.udp_ports) == 0:
        raise ValueError("at least one udp_port is required")
    if args.payload_types is None:
        args.payload_types = [112] * session_cnt
    elif len(args.payload_types) == 0:
        raise ValueError("at least one payload_type is required")
    return session_cnt


def get_value(values, index):
    if len(values) == 1:
        return values[0]
    if index < len(values):
        return values[index]
    return values[-1]


def frame_to_bgr(frame, display_scale_factor):
    width = frame.width
    height = frame.height

    if frame.fmt == mtl.ST_FRAME_FMT_YUV422PLANAR10LE:
        ptr = (ctypes.c_ubyte * frame.data_size).from_address(
            mtl.st_frame_addr_cpuva(frame, 0)
        )
        y, u, v = misc_util.yuv422p10le_to_yuv422(ptr, width, height)
        y, u, v = misc_util.downscale_yuv422(y, u, v, display_scale_factor)
        u = cv2.resize(u, (y.shape[1], y.shape[0]), interpolation=cv2.INTER_LINEAR)
        v = cv2.resize(v, (y.shape[1], y.shape[0]), interpolation=cv2.INTER_LINEAR)
        return cv2.cvtColor(cv2.merge([y, u, v]), cv2.COLOR_YUV2BGR)

    if frame.fmt == mtl.ST_FRAME_FMT_YUV422PLANAR8:
        ptr = (ctypes.c_ubyte * frame.data_size).from_address(
            mtl.st_frame_addr_cpuva(frame, 0)
        )
        y, u, v = misc_util.ptr_to_yuv422p8(ptr, width, height)
        y, u, v = misc_util.downscale_yuv422(y, u, v, display_scale_factor)
        u = cv2.resize(u, (y.shape[1], y.shape[0]), interpolation=cv2.INTER_LINEAR)
        v = cv2.resize(v, (y.shape[1], y.shape[0]), interpolation=cv2.INTER_LINEAR)
        return cv2.cvtColor(cv2.merge([y, u, v]), cv2.COLOR_YUV2BGR)

    return None


def display_frame(frame, stream_idx, display_scale_factor):
    bgr = frame_to_bgr(frame, display_scale_factor)
    if bgr is None:
        return
    cv2.imshow(f"st20p_rx_multi_{stream_idx}", bgr)
    cv2.waitKey(1)


def interlaced_display(first, second, stream_idx, display_scale_factor):
    frame = mtl.st_frame_create_by_malloc(
        first.fmt,
        first.width,
        first.height,
        False,
    )
    if frame:
        mtl.st_field_merge(first, second, frame)
        display_frame(frame, stream_idx, display_scale_factor)
        mtl.st_frame_free(frame)


def build_init_params(args, session_cnt):
    init_para = mtl.mtl_init_params()
    mtl.mtl_para_port_set(init_para, mtl.MTL_PORT_P, args.p_port)
    mtl.mtl_para_pmd_set(
        init_para, mtl.MTL_PORT_P, mtl.mtl_pmd_by_port_name(args.p_port)
    )
    init_para.num_ports = 1
    mtl.mtl_para_sip_set(init_para, mtl.MTL_PORT_P, args.p_sip)
    init_para.flags = mtl.MTL_FLAG_BIND_NUMA | mtl.MTL_FLAG_DEV_AUTO_START_STOP
    if args.ptp:
        init_para.flags |= mtl.MTL_FLAG_PTP_ENABLE
    mtl.mtl_para_tx_queues_cnt_set(init_para, mtl.MTL_PORT_P, 0)
    mtl.mtl_para_rx_queues_cnt_set(init_para, mtl.MTL_PORT_P, session_cnt)
    init_para.rss_mode = args.rss_mode
    init_para.pacing = args.pacing_way
    init_para.nb_tx_desc = args.nb_tx_desc
    init_para.nb_rx_desc = args.nb_rx_desc
    if args.lcores:
        init_para.lcores = args.lcores
    return init_para


def create_rx_session(mtl_handle, init_para, args, stream_idx):
    rx_para = mtl.st20p_rx_ops()
    rx_para.name = f"st20p_rx_python_{stream_idx}"
    rx_para.width = args.width
    rx_para.height = args.height
    rx_para.fps = args.fps
    rx_para.interlaced = args.interlaced
    rx_para.framebuff_cnt = 3
    rx_para.transport_fmt = args.transport_fmt
    rx_para.output_fmt = args.pipeline_fmt

    rx_port = mtl.st_rx_port()
    mtl.st_rxp_para_port_set(
        rx_port,
        mtl.MTL_SESSION_PORT_P,
        mtl.mtl_para_port_get(init_para, mtl.MTL_SESSION_PORT_P),
    )
    rx_port.num_port = 1
    mtl.st_rxp_para_ip_set(rx_port, mtl.MTL_SESSION_PORT_P, args.p_rx_ips[stream_idx])
    mtl.st_rxp_para_udp_port_set(
        rx_port, mtl.MTL_SESSION_PORT_P, get_value(args.udp_ports, stream_idx)
    )
    rx_port.payload_type = get_value(args.payload_types, stream_idx)
    rx_para.port = rx_port

    return mtl.st20p_rx_create(mtl_handle, rx_para)


def run_interlaced_loop(streams, display, display_scale_factor):
    first_fields = [None] * len(streams)
    try:
        while True:
            any_progress = False
            for idx, stream in enumerate(streams):
                field = mtl.st20p_rx_get_frame(stream)
                if not field:
                    continue
                any_progress = True
                if field.second_field:
                    if first_fields[idx]:
                        if display:
                            interlaced_display(
                                first_fields[idx], field, idx, display_scale_factor
                            )
                        mtl.st20p_rx_put_frame(stream, first_fields[idx])
                        first_fields[idx] = None
                    mtl.st20p_rx_put_frame(stream, field)
                else:
                    if first_fields[idx]:
                        mtl.st20p_rx_put_frame(stream, first_fields[idx])
                    first_fields[idx] = field
            if not any_progress:
                cv2.waitKey(1)
    except KeyboardInterrupt:
        print("KeyboardInterrupt")
    finally:
        for idx, stream in enumerate(streams):
            if first_fields[idx]:
                mtl.st20p_rx_put_frame(stream, first_fields[idx])


def run_frame_loop(streams, display, display_scale_factor):
    try:
        while True:
            any_progress = False
            for idx, stream in enumerate(streams):
                frame = mtl.st20p_rx_get_frame(stream)
                if not frame:
                    continue
                any_progress = True
                if display:
                    display_frame(frame, idx, display_scale_factor)
                mtl.st20p_rx_put_frame(stream, frame)
            if not any_progress:
                cv2.waitKey(1)
    except KeyboardInterrupt:
        print("KeyboardInterrupt")


def main():
    args = parse_args()

    try:
        session_cnt = validate_args(args)
    except ValueError as exc:
        print(exc)
        sys.exit(1)

    init_para = build_init_params(args, session_cnt)
    mtl_handle = mtl.mtl_init(init_para)
    if not mtl_handle:
        print("mtl_init fail")
        sys.exit(1)

    streams = []
    try:
        for idx in range(session_cnt):
            stream = create_rx_session(mtl_handle, init_para, args, idx)
            if not stream:
                print(f"st20p_rx_create fail for stream {idx}")
                sys.exit(1)
            streams.append(stream)
            print(
                "created rx session: "
                f"ip={args.p_rx_ips[idx]} "
                f"udp_port={get_value(args.udp_ports, idx)} "
                f"payload_type={get_value(args.payload_types, idx)}"
            )

        if args.interlaced:
            run_interlaced_loop(streams, args.display, args.display_scale_factor)
        else:
            run_frame_loop(streams, args.display, args.display_scale_factor)
    finally:
        misc_util.destroy()
        for stream in streams:
            mtl.st20p_rx_free(stream)
        mtl.mtl_uninit(mtl_handle)

    print("Everything fine, bye")


if __name__ == "__main__":
    main()
