import argparse
import json
import os
import threading
import time
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.ble_stream import IMUStreamer
from src.config import (
    DEVICE_ADDRESS,
    CHARACTERISTIC_UUID,
    SAMPLE_FREC,
    PACKET_LENGTH,
    RAW_DATA_LENGTH,
)


def _normalize_quaternion(q):
    q = np.array(q, dtype=float)
    norm = np.linalg.norm(q)
    if norm <= 0.0:
        return np.array([1.0, 0.0, 0.0, 0.0])
    return q / norm


def _mean_quaternion(quats):
    if len(quats) == 0:
        return np.array([1.0, 0.0, 0.0, 0.0])

    ref = _normalize_quaternion(quats[0])
    aligned = []
    for q in quats:
        qn = _normalize_quaternion(q)
        if np.dot(qn, ref) < 0.0:
            qn = -qn
        aligned.append(qn)

    q_mean = np.mean(np.array(aligned), axis=0)
    return _normalize_quaternion(q_mean)


def _closure_angle_deg(q_start, q_end):
    dot = float(np.dot(_normalize_quaternion(q_start), _normalize_quaternion(q_end)))
    dot = abs(max(min(dot, 1.0), -1.0))
    angle_rad = 2.0 * np.arccos(dot)
    return float(np.degrees(angle_rad))


def _quaternion_to_euler_deg(q):
    """Convert quaternion [w, x, y, z] to roll/pitch/yaw in degrees."""
    w, x, y, z = _normalize_quaternion(q)

    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = np.arctan2(sinr_cosp, cosr_cosp)

    sinp = 2.0 * (w * y - z * x)
    sinp = np.clip(sinp, -1.0, 1.0)
    pitch = np.arcsin(sinp)

    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = np.arctan2(siny_cosp, cosy_cosp)

    return {
        'roll_deg': float(np.degrees(roll)),
        'pitch_deg': float(np.degrees(pitch)),
        'yaw_deg': float(np.degrees(yaw)),
    }


def _save_start_end_angle_plot(loop_closure_metrics, plot_path):
    """Save grouped bar plot comparing start and end Euler angles."""
    start = loop_closure_metrics.get('start_euler_deg')
    end = loop_closure_metrics.get('end_euler_deg')
    if not start or not end:
        return False

    labels = ['Roll', 'Pitch', 'Yaw']
    start_vals = [start['roll_deg'], start['pitch_deg'], start['yaw_deg']]
    end_vals = [end['roll_deg'], end['pitch_deg'], end['yaw_deg']]
    x = np.arange(len(labels))
    width = 0.36

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - width / 2.0, start_vals, width=width, label='Start', color='#1f77b4')
    ax.bar(x + width / 2.0, end_vals, width=width, label='End', color='#ff7f0e')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel('Angle (deg)')

    closure_angle = loop_closure_metrics.get('closure_angle_deg')
    if closure_angle is not None:
        ax.set_title(f'Start vs End Orientation Angles (Closure: {closure_angle:.2f} deg)')
    else:
        ax.set_title('Start vs End Orientation Angles')

    ax.grid(True, axis='y', alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    return True


def _compute_loop_closure_metrics(df, hold_seconds):
    if df.empty:
        return {'closure_angle_deg': None, 'error': 'No samples captured'}

    if 'timestamp' not in df.columns:
        return {'closure_angle_deg': None, 'error': 'Missing timestamp column'}

    required_q = ['quat_w', 'quat_x', 'quat_y', 'quat_z']
    for col in required_q:
        if col not in df.columns:
            return {'closure_angle_deg': None, 'error': f'Missing quaternion column: {col}'}

    ts = pd.to_datetime(df['timestamp'])
    t0 = ts.iloc[0]
    t1 = ts.iloc[-1]

    start_mask = ts <= (t0 + pd.Timedelta(seconds=hold_seconds))
    end_mask = ts >= (t1 - pd.Timedelta(seconds=hold_seconds))

    start_df = df[start_mask]
    end_df = df[end_mask]

    if start_df.empty or end_df.empty:
        return {
            'closure_angle_deg': None,
            'error': 'Insufficient samples in start/end hold windows'
        }

    q_start = _mean_quaternion(start_df[required_q].values)
    q_end = _mean_quaternion(end_df[required_q].values)
    start_euler = _quaternion_to_euler_deg(q_start)
    end_euler = _quaternion_to_euler_deg(q_end)

    return {
        'closure_angle_deg': _closure_angle_deg(q_start, q_end),
        'start_window_samples': int(len(start_df)),
        'end_window_samples': int(len(end_df)),
        'start_euler_deg': start_euler,
        'end_euler_deg': end_euler,
        'delta_euler_deg': {
            'roll_deg': float(end_euler['roll_deg'] - start_euler['roll_deg']),
            'pitch_deg': float(end_euler['pitch_deg'] - start_euler['pitch_deg']),
            'yaw_deg': float(end_euler['yaw_deg'] - start_euler['yaw_deg']),
        },
    }


def _compute_stream_diagnostics(df, configured_sample_freq_hz):
    """Compute diagnostics to detect timing/scale mismatches in baseline runs."""
    diagnostics = {
        'configured_sample_freq_hz': float(configured_sample_freq_hz),
    }

    if df.empty:
        diagnostics['error'] = 'No samples captured'
        return diagnostics

    dt = pd.to_numeric(df.get('dt'), errors='coerce').dropna()
    if not dt.empty:
        mean_dt = float(dt.mean())
        effective_rate_hz = (1.0 / mean_dt) if mean_dt > 0.0 else None
        diagnostics['dt_mean_s'] = mean_dt
        diagnostics['dt_std_s'] = float(dt.std(ddof=0))
        diagnostics['dt_min_s'] = float(dt.min())
        diagnostics['dt_max_s'] = float(dt.max())
        diagnostics['effective_stream_rate_hz'] = effective_rate_hz
        if effective_rate_hz is not None and configured_sample_freq_hz > 0:
            mismatch_ratio = effective_rate_hz / float(configured_sample_freq_hz)
            diagnostics['rate_ratio_measured_over_configured'] = float(mismatch_ratio)
            diagnostics['rate_mismatch_percent'] = float((mismatch_ratio - 1.0) * 100.0)

    if 'filter_dt' in df.columns:
        filter_dt = pd.to_numeric(df['filter_dt'], errors='coerce').dropna()
        if not filter_dt.empty:
            diagnostics['filter_dt_mean_s'] = float(filter_dt.mean())
            diagnostics['filter_rate_hz'] = float(1.0 / filter_dt.mean()) if float(filter_dt.mean()) > 0.0 else None

    # Gyro scale sanity in physical units (dps)
    gyro_cols = ['gyro_x', 'gyro_y', 'gyro_z']
    if all(col in df.columns for col in gyro_cols):
        gyro = df[gyro_cols].apply(pd.to_numeric, errors='coerce')
        if not gyro.empty:
            abs_mean_rad_s = gyro.abs().mean()
            diagnostics['gyro_abs_mean_rad_s'] = {
                'x': float(abs_mean_rad_s['gyro_x']),
                'y': float(abs_mean_rad_s['gyro_y']),
                'z': float(abs_mean_rad_s['gyro_z']),
            }
            rad_to_deg = 180.0 / np.pi
            diagnostics['gyro_abs_mean_dps'] = {
                'x': float(abs_mean_rad_s['gyro_x'] * rad_to_deg),
                'y': float(abs_mean_rad_s['gyro_y'] * rad_to_deg),
                'z': float(abs_mean_rad_s['gyro_z'] * rad_to_deg),
            }

    warnings = []
    effective = diagnostics.get('effective_stream_rate_hz')
    configured = float(configured_sample_freq_hz)
    if effective is not None and configured > 0.0:
        mismatch = abs(effective - configured) / configured
        if mismatch > 0.15:
            warnings.append(
                'Effective stream rate differs from configured SAMPLE_FREC by more than 15%.'
            )

    filter_rate = diagnostics.get('filter_rate_hz')
    if effective is not None and filter_rate is not None and effective > 0.0:
        if abs(filter_rate - effective) / effective > 0.10:
            warnings.append('Filter rate does not match effective stream rate within 10%.')

    if warnings:
        diagnostics['warnings'] = warnings

    return diagnostics


def _ensure_output_dir(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def _countdown(seconds, label):
    """Print coarse countdown updates while sleeping."""
    if seconds <= 0:
        return

    for remaining in range(seconds, 0, -1):
        # Print every 5 seconds and final 5..1 seconds.
        if remaining <= 5 or remaining % 5 == 0:
            print(f'[{label}] {remaining}s remaining')
        time.sleep(1)


def _run_protocol_cues(total_duration_s, hold_seconds):
    """Emit explicit phase start/end cues aligned to capture time."""
    initial_hold = min(hold_seconds, total_duration_s)
    remaining_after_initial = max(total_duration_s - initial_hold, 0)
    final_hold = min(hold_seconds, remaining_after_initial)
    motion_seconds = max(total_duration_s - initial_hold - final_hold, 0)

    print('')
    print('Live protocol cues:')
    print('  >>> STEP 1 START: Keep sensor still now (initial hold).')
    _countdown(initial_hold, 'STEP 1')

    if motion_seconds > 0:
        print('  >>> STEP 2 START: Perform loop motion now.')
        _countdown(motion_seconds, 'STEP 2')
    else:
        print('  >>> STEP 2 SKIPPED: No motion window available with current duration/hold settings.')

    if final_hold > 0:
        print('  >>> STEP 3 START: Return to initial pose and hold still now (final hold).')
        _countdown(final_hold, 'STEP 3')

    print('  >>> Capture window complete.')


def run_baseline(duration_s, hold_seconds, output_dir, max_retries):
    print('Phase 1 baseline capture starting')
    print(f'  Duration: {duration_s}s')
    print(f'  Hold window (start/end): {hold_seconds}s')
    print(f'  BLE max retries: {max_retries}')
    print('')
    print('Protocol:')
    print('  1. Keep sensor still for initial hold window.')
    print('  2. Move through your repeatable loop path.')
    print('  3. Return to original pose and stay still for final hold window.')
    print('')

    streamer = IMUStreamer(
        DEVICE_ADDRESS,
        CHARACTERISTIC_UUID,
        sample_freq=SAMPLE_FREC,
        expected_packet_len=PACKET_LENGTH,
        raw_data_len=RAW_DATA_LENGTH,
    )

    run_result = {'df': None, 'error': None}

    def _capture_worker():
        try:
            run_result['df'] = streamer.run_stream_thread(duration_s, max_retries=max_retries)
        except Exception as exc:
            run_result['error'] = exc

    worker = threading.Thread(target=_capture_worker, daemon=True)
    worker.start()

    # Wait for capture to actually start before giving motion cues.
    while worker.is_alive() and streamer.start_time is None:
        time.sleep(0.1)

    if streamer.start_time is not None:
        print('Capture started. Follow cues below:')
        _run_protocol_cues(duration_s, hold_seconds)
    else:
        print('Capture did not start successfully; skipping protocol cues.')

    worker.join()

    if run_result['error'] is not None:
        raise run_result['error']

    df = run_result['df']
    df = streamer.get_dataframe() if df is None or df.empty else df
    static_df = streamer.get_static_windows_dataframe()
    summary = streamer.get_instrumentation_summary()
    closure = _compute_loop_closure_metrics(df, hold_seconds=hold_seconds)
    diagnostics = _compute_stream_diagnostics(df, configured_sample_freq_hz=SAMPLE_FREC)

    timestamp_tag = datetime.now().strftime('%Y%m%d_%H%M%S')
    _ensure_output_dir(output_dir)

    samples_csv = os.path.join(output_dir, f'baseline_samples_{timestamp_tag}.csv')
    static_csv = os.path.join(output_dir, f'baseline_static_windows_{timestamp_tag}.csv')
    metrics_json = os.path.join(output_dir, f'baseline_metrics_{timestamp_tag}.json')
    angle_plot_png = os.path.join(output_dir, f'baseline_start_end_angles_{timestamp_tag}.png')

    df.to_csv(samples_csv, index=False)
    static_df.to_csv(static_csv, index=False)
    angle_plot_saved = _save_start_end_angle_plot(closure, angle_plot_png)

    payload = {
        'capture_timestamp': timestamp_tag,
        'duration_s': duration_s,
        'hold_seconds': hold_seconds,
        'instrumentation_summary': summary,
        'loop_closure': closure,
        'stream_diagnostics': diagnostics,
        'samples_csv': samples_csv,
        'static_windows_csv': static_csv,
        'start_end_angles_plot': angle_plot_png if angle_plot_saved else None,
    }

    with open(metrics_json, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)

    print('Baseline capture complete')
    print(f'  Samples: {summary.get("sample_count", 0)}')

    dt_stats = summary.get('dt_stats', {})
    if dt_stats:
        print('  dt stats (s):')
        print(
            f"    mean={dt_stats['mean_s']:.6f}, std={dt_stats['std_s']:.6f}, "
            f"min={dt_stats['min_s']:.6f}, max={dt_stats['max_s']:.6f}, p95={dt_stats['p95_s']:.6f}"
        )
    else:
        print('  dt stats: unavailable (insufficient samples)')

    mag_stats = summary.get('mag_norm_stats', {})
    if mag_stats:
        print('  magnetometer norm stats (nT):')
        print(
            f"    raw_mean={mag_stats['raw_mean_nt']:.2f}, raw_std={mag_stats['raw_std_nt']:.2f}, "
            f"cal_mean={mag_stats['cal_mean_nt']:.2f}, cal_std={mag_stats['cal_std_nt']:.2f}"
        )

    static_summary = summary.get('static_windows', {})
    print(
        f"  static windows: count={static_summary.get('count', 0)}, "
        f"total_duration_s={static_summary.get('total_duration_s', 0.0):.3f}"
    )
    gyro_means = static_summary.get('gyro_mean_over_windows', {})
    if gyro_means:
        print(
            f"    gyro_mean(rad/s)=({gyro_means['x_rad_s']:.6f}, "
            f"{gyro_means['y_rad_s']:.6f}, {gyro_means['z_rad_s']:.6f})"
        )

    closure_angle = closure.get('closure_angle_deg')
    if closure_angle is not None:
        print(f'  loop-closure angle (deg): {closure_angle:.3f}')
        start_euler = closure.get('start_euler_deg', {})
        end_euler = closure.get('end_euler_deg', {})
        if start_euler and end_euler:
            print(
                '    start_euler_deg='
                f"({start_euler['roll_deg']:.2f}, {start_euler['pitch_deg']:.2f}, {start_euler['yaw_deg']:.2f})"
            )
            print(
                '    end_euler_deg='
                f"({end_euler['roll_deg']:.2f}, {end_euler['pitch_deg']:.2f}, {end_euler['yaw_deg']:.2f})"
            )
    else:
        print(f"  loop-closure angle: unavailable ({closure.get('error', 'unknown error')})")

    effective_rate = diagnostics.get('effective_stream_rate_hz')
    filter_rate = diagnostics.get('filter_rate_hz')
    rate_mismatch = diagnostics.get('rate_mismatch_percent')
    print('  stream diagnostics:')
    print(f'    configured_sample_freq_hz={SAMPLE_FREC:.2f}')
    if effective_rate is not None:
        print(f'    effective_stream_rate_hz={effective_rate:.2f}')
    if filter_rate is not None:
        print(f'    filter_rate_hz={filter_rate:.2f}')
    if rate_mismatch is not None:
        print(f'    rate_mismatch_percent={rate_mismatch:+.1f}%')

    gyro_abs_mean_dps = diagnostics.get('gyro_abs_mean_dps')
    if gyro_abs_mean_dps:
        print(
            '    gyro_abs_mean_dps='
            f"({gyro_abs_mean_dps['x']:.2f}, {gyro_abs_mean_dps['y']:.2f}, {gyro_abs_mean_dps['z']:.2f})"
        )

    for warning in diagnostics.get('warnings', []):
        print(f'    WARNING: {warning}')

    print('')
    print(f'Metrics JSON: {metrics_json}')
    print(f'Samples CSV: {samples_csv}')
    print(f'Static windows CSV: {static_csv}')
    if angle_plot_saved:
        print(f'Start/End angles plot: {angle_plot_png}')

    return payload


def main():
    parser = argparse.ArgumentParser(description='Phase 1 IMU loop-closure baseline metrics capture')
    parser.add_argument('--duration', type=int, default=45, help='Capture duration in seconds')
    parser.add_argument('--hold-seconds', type=int, default=5, help='Start/end still-window duration in seconds')
    parser.add_argument('--output-dir', type=str, default='docs', help='Directory for generated metrics files')
    parser.add_argument('--max-retries', type=int, default=3, help='Maximum BLE reconnect attempts')
    args = parser.parse_args()

    run_baseline(args.duration, args.hold_seconds, args.output_dir, args.max_retries)


if __name__ == '__main__':
    main()
