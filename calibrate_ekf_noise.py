"""
Estimate EKF noise variances from a static BLE capture and save them to JSON.

Usage:
    python calibrate_ekf_noise.py
    python calibrate_ekf_noise.py --duration 45 --output ekf_noise.json

Protocol:
    1. Keep the IMU completely still on a stable surface.
    2. Capture for 30-60 seconds.
    3. The script estimates var_gyr, var_acc, var_mag and saves them.
"""

import argparse
import json
from datetime import datetime

import numpy as np

from src.ble_stream import IMUStreamer
from src.config import (
    CHARACTERISTIC_UUID,
    DEVICE_ADDRESS,
    EKF_DEFAULT_NOISES,
    EKF_NOISE_FILE,
    PACKET_LENGTH,
    RAW_DATA_LENGTH,
    SAMPLE_FREC,
)


def _mean_axis_variance(data: np.ndarray) -> float:
    """Return average of per-axis sample variances with safe fallback."""
    if data.shape[0] < 2:
        return float('nan')
    axis_var = np.var(data, axis=0, ddof=1)
    return float(np.mean(axis_var))


def _normalize_rows(data: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(data, axis=1, keepdims=True)
    valid = (norms[:, 0] > 0.0)
    if not np.any(valid):
        return np.empty((0, data.shape[1]))
    return data[valid] / norms[valid]


def estimate_ekf_noises(df):
    """Estimate EKF variances from static samples if available."""
    if df.empty:
        raise ValueError("No samples collected; could not estimate EKF noises")

    if 'is_static_sample' in df.columns:
        static_df = df[df['is_static_sample'] == True]
    else:
        static_df = df.iloc[0:0]

    # Prefer static-only data. Fall back to full capture only if needed.
    source_df = static_df if len(static_df) >= 20 else df

    gyr = source_df[['gyro_x', 'gyro_y', 'gyro_z']].to_numpy(dtype=float)
    acc = source_df[['accel_x', 'accel_y', 'accel_z']].to_numpy(dtype=float)
    mag = source_df[['mag_x', 'mag_y', 'mag_z']].to_numpy(dtype=float)

    mag_unit = _normalize_rows(mag)

    var_gyr = _mean_axis_variance(gyr)
    var_acc = _mean_axis_variance(acc)
    var_mag = _mean_axis_variance(mag_unit)

    estimates = [var_gyr, var_acc, var_mag]
    sanitized = []
    for idx, value in enumerate(estimates):
        default = float(EKF_DEFAULT_NOISES[idx])
        if (not np.isfinite(value)) or value <= 0.0:
            sanitized.append(default)
        else:
            sanitized.append(float(value))

    return {
        'noises': sanitized,
        'var_gyr': sanitized[0],
        'var_acc': sanitized[1],
        'var_mag': sanitized[2],
        'sample_count_total': int(len(df)),
        'sample_count_used': int(len(source_df)),
        'sample_count_static': int(len(static_df)),
        'used_static_only': bool(source_df is static_df),
    }


def main():
    parser = argparse.ArgumentParser(description='Estimate EKF Q/R noise variances from static BLE capture')
    parser.add_argument('--duration', type=float, default=30.0, help='Capture duration in seconds (default: 30)')
    parser.add_argument('--output', type=str, default=EKF_NOISE_FILE, help='Output JSON path')
    parser.add_argument('--max-retries', type=int, default=10, help='Max BLE retry attempts')
    args = parser.parse_args()

    print('\n=== EKF Noise Calibration ===')
    print('Keep the IMU completely static during capture.')
    print(f'Capturing for {args.duration:.1f}s...')

    streamer = IMUStreamer(
        device_address=DEVICE_ADDRESS,
        characteristic_uuid=CHARACTERISTIC_UUID,
        sample_freq=SAMPLE_FREC,
        expected_packet_len=PACKET_LENGTH,
        raw_data_len=RAW_DATA_LENGTH,
    )

    df = streamer.run_stream_thread(duration=args.duration, max_retries=args.max_retries)
    result = estimate_ekf_noises(df)

    payload = {
        'created_at': datetime.utcnow().isoformat(timespec='seconds') + 'Z',
        'method': 'static covariance estimate from BLE capture',
        'units': {
            'var_gyr': '(rad/s)^2',
            'var_acc': '(m/s^2)^2',
            'var_mag': 'unitless^2 (normalized magnetometer)',
        },
        **result,
    }

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)

    print(f"Saved EKF noise calibration to: {args.output}")
    print(
        'Estimated variances: '
        f"var_gyr={payload['var_gyr']:.6e}, "
        f"var_acc={payload['var_acc']:.6e}, "
        f"var_mag={payload['var_mag']:.6e}"
    )


if __name__ == '__main__':
    main()
