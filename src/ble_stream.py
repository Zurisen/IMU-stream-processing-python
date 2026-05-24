import asyncio
from bleak import BleakClient
from ahrs.filters import EKF, Madgwick
import numpy as np
import pandas as pd
import json
from datetime import datetime
import struct
from collections import deque
from copy import copy
import os
from .config import *
from .mag_calibration import MagnetometerCalibration


class IMUStreamer:
    def __init__(self, device_address, characteristic_uuid, sample_freq, expected_packet_len, raw_data_len, maxlen=100):
        self.device_address = device_address
        self.characteristic_uuid = characteristic_uuid
        self.sample_freq = sample_freq
        self.expected_packet_len = expected_packet_len 
        self.raw_data_len = raw_data_len

        # Data buffers
        self.data_buffer = []
        # Create deques for real-time plotting
        self.time_data = deque(maxlen=maxlen)
        self.accel_x_data = deque(maxlen=maxlen)
        self.accel_y_data = deque(maxlen=maxlen)
        self.accel_z_data = deque(maxlen=maxlen)

        self.gyr_x_data = deque(maxlen=maxlen)
        self.gyr_y_data = deque(maxlen=maxlen)
        self.gyr_z_data = deque(maxlen=maxlen)

        self.mag_x_data = deque(maxlen=maxlen)
        self.mag_y_data = deque(maxlen=maxlen)
        self.mag_z_data = deque(maxlen=maxlen)
        self.start_time = None

        # Add quaternion deques at the top
        self.quat_w_data = deque(maxlen=maxlen)
        self.quat_x_data = deque(maxlen=maxlen)
        self.quat_y_data = deque(maxlen=maxlen)
        self.quat_z_data = deque(maxlen=maxlen)
        
        # Processing
        self.fusion_filter_name = str(FUSION_FILTER).strip().lower()
        self.ekf_noises = list(EKF_DEFAULT_NOISES)

        # Phase 1 instrumentation state
        self.last_sample_timestamp = None
        self.static_windows = []
        self.current_static_window = []
        self.static_window_start = None
        self.static_window_min_samples = max(10, int(0.5 * sample_freq))
        self.static_gyro_threshold_rad_s = np.deg2rad(2.0)
        self.static_accel_tolerance_m_s2 = 0.8
        
        # Magnetometer calibration
        self.mag_calibration = MagnetometerCalibration()
        self._load_calibration_if_available()
        self._load_ekf_noises_if_available()

        self.orientation_filter = self._build_orientation_filter(sample_freq)
        # Backward-compatible attribute for existing code/tests.
        self.madgwick_filter = self.orientation_filter
        self.Q = np.array([1., 0., 0., 0.])
        self.start_time = None

    def _build_orientation_filter(self, sample_freq):
        """Build the configured orientation filter implementation."""
        if self.fusion_filter_name == 'madgwick':
            return Madgwick(frequency=sample_freq)
        if self.fusion_filter_name == 'ekf':
            # ahrs.EKF requires a magnetic reference at construction time when
            # update() is called with mag measurements, otherwise it falls back
            # to a 3D measurement model and raises a shape mismatch.
            return EKF(
                frequency=sample_freq,
                mag=np.array([1.0, 0.0, 0.0]),
                noises=self.ekf_noises,
            )

        raise ValueError(
            f"Unsupported FUSION_FILTER '{FUSION_FILTER}'. Use 'madgwick' or 'ekf'."
        )
    
    def _load_calibration_if_available(self):
        """Try to load magnetometer calibration from file if it exists."""
        calibration_file = 'mag_calibration.json'
        if os.path.exists(calibration_file):
            try:
                self.mag_calibration.load_calibration(calibration_file)
                print("✓ Magnetometer calibration loaded successfully")
            except Exception as e:
                print(f"⚠ WARNING: Could not load calibration file: {e}")
                print("⚠ Using uncalibrated magnetometer values")
                print("⚠ Run 'python calibrate.py' to calibrate for accurate orientation")
        else:
            print("\n" + "="*70)
            print("⚠ WARNING: No magnetometer calibration found!")
            print("="*70)
            print("Magnetometer data will be used UNCALIBRATED.")
            print("This will likely result in:")
            print("  - Inaccurate heading estimates")
            print("  - Unreliable orientation data")
            print("  - Drift and errors in sensor fusion")
            print("\nTo calibrate:")
            print("  1. Stop this program")
            print("  2. Run: python calibrate.py")
            print("  3. Follow calibration instructions")
            print("  4. Restart this program")
            print("="*70 + "\n")
            
            # Ask user if they want to continue
            try:
                response = input("Continue with uncalibrated data? (yes/no) [no]: ").strip().lower()
                if response not in ['yes', 'y']:
                    print("Exiting. Please run calibration first.")
                    import sys
                    sys.exit(1)
            except (EOFError, KeyboardInterrupt):
                print("\nExiting. Please run calibration first.")
                import sys
                sys.exit(1)

    def _load_ekf_noises_if_available(self):
        """Try to load EKF noise variances from JSON file if it exists."""
        if self.fusion_filter_name != 'ekf':
            return

        if not os.path.exists(EKF_NOISE_FILE):
            print(
                f"ℹ EKF noise file '{EKF_NOISE_FILE}' not found; "
                f"using defaults {self.ekf_noises}"
            )
            return

        try:
            with open(EKF_NOISE_FILE, 'r', encoding='utf-8') as f:
                payload = json.load(f)

            noises = payload.get('noises')
            if noises is None:
                var_gyr = payload.get('var_gyr')
                var_acc = payload.get('var_acc')
                var_mag = payload.get('var_mag')
                noises = [var_gyr, var_acc, var_mag]

            if not isinstance(noises, (list, tuple)) or len(noises) != 3:
                raise ValueError("Expected 'noises' to be a list of 3 numeric variances")

            parsed = [float(v) for v in noises]
            if any((not np.isfinite(v)) or v <= 0.0 for v in parsed):
                raise ValueError("EKF noise variances must be finite and > 0")

            self.ekf_noises = parsed
            print(
                f"✓ EKF noises loaded from {EKF_NOISE_FILE}: "
                f"var_gyr={parsed[0]:.6e}, var_acc={parsed[1]:.6e}, var_mag={parsed[2]:.6e}"
            )
        except Exception as e:
            print(f"⚠ WARNING: Could not load EKF noises from {EKF_NOISE_FILE}: {e}")
            print(f"⚠ Using default EKF noises: {self.ekf_noises}")
    
    def notification_handler(self, sender, data):
        """Callback function that handles incoming data from the characteristic"""
        timestamp = datetime.now()
        if self.start_time is None:
            self.start_time = timestamp
        
        if len(data) >= 2:
            
            # Extract raw sensor data (from byte 2 to byte packet_length)
            if len(data) == self.expected_packet_len:
                raw_data = data[2:2+self.raw_data_len] ## MOD: First two bytes are reserved for length and packet type
                if len(raw_data) == self.raw_data_len:
                    current_byte = 0
                    for imu_index in range(3): ## We are unpacking 3 imus
                        values = struct.unpack('<hhhhhhhhh', raw_data[current_byte:current_byte+18])
                        current_byte += 20 # MOD: 4*6 = 20 bytes

                        if imu_index == 0: ## TODO: we are just working with imu 0 for now
                            # Unpack into accel, gyro, mag
                            accel_x, accel_y, accel_z = values[0], values[1], values[2]
                            gyro_x, gyro_y, gyro_z = values[3], values[4], values[5]
                            mag_x, mag_y, mag_z = values[6], values[7], values[8]
                            
                            accel_x_g = accel_x * ACCEL_SENSITIVITY * GRAVITY ## MOD: Multiply by gravity to convert from g units to m/s2
                            accel_y_g = accel_y * ACCEL_SENSITIVITY * GRAVITY ## in m/s2
                            accel_z_g = accel_z * ACCEL_SENSITIVITY * GRAVITY
                            
                            gyro_x_rad = (gyro_x * GYRO_SENSITIVITY) * DEG_TO_RAD ## MOD: Changed to documentation sensitivity
                            gyro_y_rad = (gyro_y * GYRO_SENSITIVITY) * DEG_TO_RAD ## in rad/s
                            gyro_z_rad = (gyro_z * GYRO_SENSITIVITY) * DEG_TO_RAD

                            mag_x_nt = mag_x * MAG_SENSITIVITY ## in nT
                            mag_y_nt = mag_y * MAG_SENSITIVITY
                            mag_z_nt = mag_z * MAG_SENSITIVITY
                            
                            # Apply magnetometer calibration if available
                            mag_raw = np.array([mag_x_nt, mag_y_nt, mag_z_nt])
                            mag_calibrated = self.mag_calibration.apply_calibration(mag_raw)
                            mag_norm_raw = float(np.linalg.norm(mag_raw))
                            mag_norm_cal = float(np.linalg.norm(mag_calibrated))

                            dt = None
                            if self.last_sample_timestamp is not None:
                                dt = (timestamp - self.last_sample_timestamp).total_seconds()
                            self.last_sample_timestamp = timestamp

                            # Use measured packet timing when available to keep filter dynamics
                            # consistent even if configured and actual sample rates differ.
                            filter_dt = dt if dt is not None and dt > 0.0 else (1.0 / float(self.sample_freq))
                            
                            # print(f"Raw: {mag_x_nt:.1f} {mag_y_nt:.1f} {mag_z_nt:.1f} | "
                            #       f"Cal: {mag_calibrated[0]:.1f} {mag_calibrated[1]:.1f} {mag_calibrated[2]:.1f}")

                            gyr_vec = np.array([gyro_x_rad, gyro_y_rad, gyro_z_rad])
                            acc_vec = np.array([accel_x_g, accel_y_g, accel_z_g])

                            if self.fusion_filter_name == 'madgwick':
                                q = self.orientation_filter.updateMARG(
                                    q=self.Q,
                                    gyr=gyr_vec,
                                    acc=acc_vec,
                                    mag=mag_calibrated,
                                    dt=filter_dt,
                                )
                            else:
                                q = self.orientation_filter.update(
                                    q=self.Q,
                                    gyr=gyr_vec,
                                    acc=acc_vec,
                                    mag=mag_calibrated,
                                    dt=filter_dt,
                                )

                            # Add quaternion data
                            self.quat_w_data.append(q[0])
                            self.quat_x_data.append(q[1])
                            self.quat_y_data.append(q[2])
                            self.quat_z_data.append(q[3])

                            self.Q = copy(q)

                            gyro_vec = gyr_vec
                            accel_vec = acc_vec
                            gyro_norm = float(np.linalg.norm(gyro_vec))
                            accel_norm = float(np.linalg.norm(accel_vec))
                            is_static_sample = (
                                gyro_norm <= self.static_gyro_threshold_rad_s and
                                abs(accel_norm - GRAVITY) <= self.static_accel_tolerance_m_s2
                            )
                            self._update_static_window(timestamp, gyro_vec, is_static_sample)

                            self.data_buffer.append({
                                'timestamp': timestamp,
                                'imu_index': imu_index,  # 0=Cervical, 1=Thoracic, 2=Lumbar
                                'accel_x': accel_x_g,
                                'accel_y': accel_y_g,
                                'accel_z': accel_z_g,
                                'gyro_x': gyro_x_rad,
                                'gyro_y': gyro_y_rad,
                                'gyro_z': gyro_z_rad,
                                'mag_x': mag_x_nt,
                                'mag_y': mag_y_nt,
                                'mag_z': mag_z_nt,
                                'quat_w': q[0],
                                'quat_x': q[1],
                                'quat_y': q[2],
                                'quat_z': q[3],
                                'dt': dt,
                                'filter_dt': filter_dt,
                                'filter_type': self.fusion_filter_name,
                                'gyro_norm': gyro_norm,
                                'accel_norm': accel_norm,
                                'mag_norm_raw': mag_norm_raw,
                                'mag_norm_calibrated': mag_norm_cal,
                                'is_static_sample': is_static_sample
                            })

                            elapsed_time = (timestamp - self.start_time).total_seconds()
                            self.time_data.append(elapsed_time)
                            self.accel_x_data.append(accel_x_g)
                            self.accel_y_data.append(accel_y_g)
                            self.accel_z_data.append(accel_z_g)

                            self.gyr_x_data.append(gyro_x_rad)
                            self.gyr_y_data.append(gyro_y_rad)
                            self.gyr_z_data.append(gyro_z_rad)
                            
                            self.mag_x_data.append(mag_x_nt)
                            self.mag_y_data.append(mag_y_nt)
                            self.mag_z_data.append(mag_z_nt)

    def _update_static_window(self, timestamp, gyro_vec, is_static_sample):
        """Track contiguous static periods and store gyro mean/std for each completed window."""
        if is_static_sample:
            if self.static_window_start is None:
                self.static_window_start = timestamp
                self.current_static_window = []
            self.current_static_window.append(gyro_vec)
            return

        self._finalize_static_window(timestamp)

    def _finalize_static_window(self, end_timestamp=None):
        """Finalize the current static window if it has enough samples."""
        if self.static_window_start is None:
            return

        sample_count = len(self.current_static_window)
        if sample_count >= self.static_window_min_samples:
            gyro_arr = np.array(self.current_static_window)
            if end_timestamp is None:
                end_timestamp = datetime.now()
            duration_s = (end_timestamp - self.static_window_start).total_seconds()
            self.static_windows.append({
                'start_timestamp': self.static_window_start,
                'end_timestamp': end_timestamp,
                'duration_s': float(duration_s),
                'sample_count': int(sample_count),
                'gyro_mean_x': float(np.mean(gyro_arr[:, 0])),
                'gyro_mean_y': float(np.mean(gyro_arr[:, 1])),
                'gyro_mean_z': float(np.mean(gyro_arr[:, 2])),
                'gyro_std_x': float(np.std(gyro_arr[:, 0])),
                'gyro_std_y': float(np.std(gyro_arr[:, 1])),
                'gyro_std_z': float(np.std(gyro_arr[:, 2]))
            })

        self.current_static_window = []
        self.static_window_start = None

    def finalize_instrumentation(self):
        """Finalize pending static window before exporting summaries."""
        self._finalize_static_window(self.last_sample_timestamp)

    def get_dataframe(self):
        """Return all collected samples as a DataFrame."""
        self.finalize_instrumentation()
        return pd.DataFrame(self.data_buffer)

    def get_static_windows_dataframe(self):
        """Return static window summaries as a DataFrame."""
        self.finalize_instrumentation()
        return pd.DataFrame(self.static_windows)

    def get_instrumentation_summary(self):
        """Compute aggregate timing, magnetic, and static-window metrics."""
        self.finalize_instrumentation()
        df = pd.DataFrame(self.data_buffer)

        if df.empty:
            return {
                'sample_count': 0,
                'dt_stats': {},
                'mag_norm_stats': {},
                'static_windows': {
                    'count': 0,
                    'total_duration_s': 0.0,
                    'gyro_mean_over_windows': {}
                }
            }

        dt_series = df['dt'].dropna() if 'dt' in df.columns else pd.Series(dtype=float)
        dt_stats = {}
        if not dt_series.empty:
            dt_stats = {
                'mean_s': float(dt_series.mean()),
                'std_s': float(dt_series.std(ddof=0)),
                'min_s': float(dt_series.min()),
                'max_s': float(dt_series.max()),
                'p95_s': float(dt_series.quantile(0.95))
            }

        mag_norm_stats = {}
        if 'mag_norm_raw' in df.columns and 'mag_norm_calibrated' in df.columns:
            raw = df['mag_norm_raw']
            cal = df['mag_norm_calibrated']
            mag_norm_stats = {
                'raw_mean_nt': float(raw.mean()),
                'raw_std_nt': float(raw.std(ddof=0)),
                'cal_mean_nt': float(cal.mean()),
                'cal_std_nt': float(cal.std(ddof=0))
            }

        static_df = pd.DataFrame(self.static_windows)
        static_summary = {
            'count': int(len(static_df)),
            'total_duration_s': float(static_df['duration_s'].sum()) if not static_df.empty else 0.0,
            'gyro_mean_over_windows': {}
        }
        if not static_df.empty:
            static_summary['gyro_mean_over_windows'] = {
                'x_rad_s': float(static_df['gyro_mean_x'].mean()),
                'y_rad_s': float(static_df['gyro_mean_y'].mean()),
                'z_rad_s': float(static_df['gyro_mean_z'].mean())
            }

        return {
            'sample_count': int(len(df)),
            'dt_stats': dt_stats,
            'mag_norm_stats': mag_norm_stats,
            'static_windows': static_summary
        }

    
    async def stream_data(self, duration=30, max_retries=10):
        for attempt in range(max_retries):
            if attempt > 0: print("...Trying again...")
            try:
                async with BleakClient(self.device_address, timeout=20.0) as client:
                    print(f"Connected: {client.is_connected}")
                    
                    # Wait for services to be discovered
                    await asyncio.sleep(1)
                    
                    await client.start_notify(self.characteristic_uuid, self.notification_handler)
                    print(f"Started streaming from {self.characteristic_uuid}")

                    await asyncio.sleep(duration)
                    await client.stop_notify(self.characteristic_uuid)
                    print("Stopped streaming")

                    self.finalize_instrumentation()

                    return pd.DataFrame(self.data_buffer)
            except Exception as e:
                print(f"BLE Connection Error: {e}")
        self.finalize_instrumentation()
        return pd.DataFrame(self.data_buffer)

    
    def run_stream_thread(self, duration, max_retries=10):
        """Run BLE streaming in a separate thread with its own event loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        df = loop.run_until_complete(self.stream_data(duration, max_retries=max_retries))
        loop.close()
        return df

