import asyncio
from bleak import BleakClient
from ahrs.filters import Madgwick
import numpy as np
import pandas as pd
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
        self.madgwick_filter = Madgwick(sample_freq)
        self.Q = np.array([1., 0., 0., 0.])
        self.start_time = None
        
        # Magnetometer calibration
        self.mag_calibration = MagnetometerCalibration()
        self._load_calibration_if_available()
    
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
                            
                            print(f"Raw: {mag_x_nt:.1f} {mag_y_nt:.1f} {mag_z_nt:.1f} | "
                                  f"Cal: {mag_calibrated[0]:.1f} {mag_calibrated[1]:.1f} {mag_calibrated[2]:.1f}")

                            q = self.madgwick_filter.updateMARG(
                                q = self.Q,
                                gyr=np.array([gyro_x_rad, gyro_y_rad, gyro_z_rad]),
                                acc=np.array([accel_x_g, accel_y_g, accel_z_g]),
                                mag = mag_calibrated
                            ) 

                            # Add quaternion data
                            self.quat_w_data.append(q[0])
                            self.quat_x_data.append(q[1])
                            self.quat_y_data.append(q[2])
                            self.quat_z_data.append(q[3])

                            self.Q = copy(q)

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
                                'mag_z': mag_z_nt
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

                    return pd.DataFrame(self.data_buffer)
            except Exception as e:
                print(f"BLE Connection Error: {e}")
        return pd.DataFrame(self.data_buffer)

    
    def run_stream_thread(self, duration):
        """Run BLE streaming in a separate thread with its own event loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        df = loop.run_until_complete(self.stream_data(duration))
        loop.close()
        return df

