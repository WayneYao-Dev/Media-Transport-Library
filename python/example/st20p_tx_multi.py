# SPDX-License-Identifier: BSD-3-Clause
# Copyright 2026 Intel Corporation

"""Module of MTL st20p multi-stream tx python example."""

import argparse
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
        description="MTL ST20P multi-stream tx python example"
    )
    parser.add_argument("--p_port", type=str, required=True, help="primary port name")
    parser.add_argument("--p_sip", type=str, required=True, help="primary local IP")
    parser.add_argument(
        "--p_tx_ips",
        type=parse_csv_list,
        required=True,
        help="tx destination IP list, separated by comma",
    )
    parser.add_argument(
        "--udp_ports",
        type=parse_int_csv_list,
        required=True,
        help="tx udp port list, separated by comma",
    )
    parser.add_argument(
        "--payload_types",
        type=parse_int_csv_list,
        default=None,
        help="payload type list, separated by comma, default all 112",
    )
    parser.add_argument(
        "--tx_urls",
        type=parse_csv_list,
        required=True,
        help="tx yuv file list, separated by comma",
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
    parser.add_argument(
        "--packing",
        type=misc_util.parse_packing,
        default=mtl.ST20_PACKING_BPM,
        help="packing",
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
    parser.add_argument("--display", action="store_true", help="display input frames")
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
    session_cnt = len(args.p_tx_ips)
    if session_cnt == 0:
        raise ValueError("at least one tx stream is required")
    if len(args.udp_ports) == 0:
        raise ValueError("at least one udp_port is required")
    if len(args.tx_urls) == 0:
        raise ValueError("at least one tx_url is required")
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
    mtl.mtl_para_tx_queues_cnt_set(init_para, mtl.MTL_PORT_P, session_cnt)
    mtl.mtl_para_rx_queues_cnt_set(init_para, mtl.MTL_PORT_P, 0)
    init_para.rss_mode = args.rss_mode
    init_para.pacing = args.pacing_way
    init_para.nb_tx_desc = args.nb_tx_desc
    init_para.nb_rx_desc = args.nb_rx_desc
    if args.lcores:
        init_para.lcores = args.lcores
    return init_para


def create_tx_session(mtl_handle, init_para, args, stream_idx):
    tx_para = mtl.st20p_tx_ops()
    tx_para.name = f"st20p_tx_python_{stream_idx}"
    tx_para.width = args.width
    tx_para.height = args.height
    tx_para.fps = args.fps
    tx_para.interlaced = args.interlaced
    tx_para.framebuff_cnt = 3
    tx_para.transport_fmt = args.transport_fmt
    tx_para.transport_packing = args.packing
    tx_para.input_fmt = args.pipeline_fmt

    tx_port = mtl.st_tx_port()
    mtl.st_txp_para_port_set(
        tx_port,
        mtl.MTL_SESSION_PORT_P,
        mtl.mtl_para_port_get(init_para, mtl.MTL_SESSION_PORT_P),
    )
    tx_port.num_port = 1
    mtl.st_txp_para_dip_set(tx_port, mtl.MTL_SESSION_PORT_P, args.p_tx_ips[stream_idx])
    mtl.st_txp_para_udp_port_set(
        tx_port, mtl.MTL_SESSION_PORT_P, get_value(args.udp_ports, stream_idx)
    )
    tx_port.payload_type = get_value(args.payload_types, stream_idx)
    tx_para.port = tx_port

    return mtl.st20p_tx_create(mtl_handle, tx_para)


def main():
    args = parse_args()

    try:
        session_cnt = validate_args(args)
    except ValueError as exc:
        print(exc)
        sys.exit(1)

    files = []
    for idx in range(session_cnt):
        tx_url = get_value(args.tx_urls, idx)
        try:
            files.append(open(tx_url, "rb"))
        except OSError:
            print(f"Open {tx_url} fail")
            for handle in files:
                handle.close()
            sys.exit(1)

    init_para = build_init_params(args, session_cnt)
    mtl_handle = mtl.mtl_init(init_para)
    if not mtl_handle:
        print("mtl_init fail")
        for handle in files:
            handle.close()
        sys.exit(1)

    streams = []
    frame_sizes = []
    try:
        for idx in range(session_cnt):
            stream = create_tx_session(mtl_handle, init_para, args, idx)
            if not stream:
                print(f"st20p_tx_create fail for stream {idx}")
                sys.exit(1)
            streams.append(stream)
            frame_sz = mtl.st20p_tx_frame_size(stream)
            frame_sizes.append(frame_sz)
            print(
                "created tx session: "
                f"ip={args.p_tx_ips[idx]} "
                f"udp_port={get_value(args.udp_ports, idx)} "
                f"payload_type={get_value(args.payload_types, idx)} "
                f"tx_url={get_value(args.tx_urls, idx)} "
                f"frame_sz={hex(frame_sz)}"
            )

        try:
            while True:
                any_progress = False
                for idx, stream in enumerate(streams):
                    frame = mtl.st20p_tx_get_frame(stream)
                    if not frame:
                        continue
                    any_progress = True
                    yuv_frame = files[idx].read(frame_sizes[idx])
                    if not yuv_frame:
                        files[idx].seek(0)
                        yuv_frame = files[idx].read(frame_sizes[idx])
                    if not yuv_frame:
                        print(
                            f"Fail to read {hex(frame_sizes[idx])} from "
                            f"{get_value(args.tx_urls, idx)}"
                        )
                        mtl.st20p_tx_put_frame(stream, frame)
                        continue

                    misc_util.copy_to_st_frame(yuv_frame, frame)
                    if args.display:
                        misc_util.frame_display(frame, args.display_scale_factor)
                    mtl.st20p_tx_put_frame(stream, frame)

                if not any_progress:
                    cv2.waitKey(1)
        except KeyboardInterrupt:
            print("KeyboardInterrupt")
    finally:
        misc_util.destroy()
        for stream in streams:
            mtl.st20p_tx_free(stream)
        mtl.mtl_uninit(mtl_handle)
        for handle in files:
            handle.close()

    print("Everything fine, bye")


if __name__ == "__main__":
    main()
