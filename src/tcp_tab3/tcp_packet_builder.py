"""Packet builder for the Tab3 TCP client."""

from __future__ import annotations

import math
import struct

import numpy as np

from .tcp_types import AcquisitionContext, CommSettings, OutgoingPacket


class TCPPacketBuildError(ValueError):
    """Raised when one acquisition block cannot be converted into a TCP packet."""


class TCPPacketBuilder:
    """Convert one phase acquisition block into the wb-monitor DAS packet format."""

    HEADER_STRUCT = struct.Struct(">IIIId")

    @classmethod
    def build_packet(
        cls,
        phase_data: np.ndarray,
        context: AcquisitionContext,
        settings: CommSettings,
        comm_count: int,
    ) -> OutgoingPacket:
        """Serialize one acquisition block into bytes."""
        time_downsample = int(settings.time_downsample)
        space_downsample = int(settings.space_downsample)
        if time_downsample <= 0 or space_downsample <= 0:
            raise TCPPacketBuildError("Downsample factors must be positive integers.")
        if context.scan_rate_hz % time_downsample != 0:
            raise TCPPacketBuildError(
                f"time_downsample={time_downsample} must divide scan_rate={context.scan_rate_hz}."
            )

        matrix = cls._reshape_phase_data(phase_data, context)
        channel_start = max(0, int(settings.channel_start))
        channel_end = min(context.point_num_after_merge - 1, int(settings.channel_end))
        if channel_end < channel_start:
            raise TCPPacketBuildError(
                f"Invalid channel range: start={channel_start}, end={channel_end}."
            )

        selected = matrix[:, channel_start : channel_end + 1]
        selected = selected[:, ::space_downsample]
        if selected.size == 0:
            raise TCPPacketBuildError("Selected channel range produced an empty packet.")

        send_matrix = selected.T
        send_matrix = send_matrix[:, ::time_downsample]
        if send_matrix.size == 0:
            raise TCPPacketBuildError("Time downsampling produced an empty packet.")

        sample_rate_hz = context.scan_rate_hz // time_downsample
        samples_per_channel = int(send_matrix.shape[1])
        channel_count = int(send_matrix.shape[0])
        packet_duration_seconds = samples_per_channel / float(sample_rate_hz)
        data_bytes = channel_count * samples_per_channel * 8

        payload_array = np.asarray(send_matrix, dtype=">f8")
        payload_bytes = payload_array.reshape(-1, order="C").tobytes()
        if len(payload_bytes) != data_bytes:
            raise TCPPacketBuildError(
                f"Serialized payload size mismatch: expected={data_bytes}, actual={len(payload_bytes)}."
            )

        header_bytes = cls.HEADER_STRUCT.pack(
            int(comm_count),
            int(sample_rate_hz),
            int(channel_count),
            int(data_bytes),
            float(packet_duration_seconds),
        )

        return OutgoingPacket(
            comm_count=int(comm_count),
            header_bytes=header_bytes,
            payload_bytes=payload_bytes,
            channel_count=channel_count,
            sample_rate_hz=sample_rate_hz,
            samples_per_channel=samples_per_channel,
            packet_duration_seconds=float(packet_duration_seconds),
            data_bytes=data_bytes,
        )

    @staticmethod
    def _reshape_phase_data(phase_data: np.ndarray, context: AcquisitionContext) -> np.ndarray:
        """Convert the acquisition callback payload into a time x space matrix in radians."""
        expected_points = context.frame_num * context.point_num_after_merge
        flat = np.asarray(phase_data)
        if flat.ndim > 1:
            flat = flat.reshape(-1)
        if flat.size != expected_points:
            raise TCPPacketBuildError(
                f"Unexpected phase data size: expected={expected_points}, actual={flat.size}."
            )

        # Reuse the existing GUI conversion rule so display and communication stay consistent.
        rad_data = flat.astype(np.float64, copy=False) / 32767.0 * math.pi
        return rad_data.reshape(context.frame_num, context.point_num_after_merge)
