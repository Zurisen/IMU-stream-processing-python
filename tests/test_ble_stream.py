"""
Unit tests for src/ble_stream.py module.
Tests IMU data streaming and processing with mocked BLE connections.
"""
import pytest
import numpy as np
import struct
import json
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, AsyncMock, mock_open
from collections import deque
import asyncio

from src.ble_stream import IMUStreamer
from src.config import *


class TestIMUStreamerInit:
    """Test IMUStreamer initialization."""
    
    def test_initialization(self):
        """Test basic initialization."""
        streamer = IMUStreamer(
            device_address=DEVICE_ADDRESS,
            characteristic_uuid=CHARACTERISTIC_UUID,
            sample_freq=SAMPLE_FREC,
            expected_packet_len=PACKET_LENGTH,
            raw_data_len=RAW_DATA_LENGTH,
            maxlen=100
        )
        
        assert streamer.device_address == DEVICE_ADDRESS
        assert streamer.characteristic_uuid == CHARACTERISTIC_UUID
        assert streamer.expected_packet_len == PACKET_LENGTH
        assert streamer.raw_data_len == RAW_DATA_LENGTH
        assert len(streamer.data_buffer) == 0
        assert streamer.start_time is None
    
    def test_deque_initialization(self):
        """Test that data deques are initialized correctly."""
        maxlen = 150
        streamer = IMUStreamer(
            DEVICE_ADDRESS, CHARACTERISTIC_UUID,
            SAMPLE_FREC, PACKET_LENGTH, RAW_DATA_LENGTH,
            maxlen=maxlen
        )
        
        # Check all deques are initialized with correct maxlen
        assert streamer.time_data.maxlen == maxlen
        assert streamer.accel_x_data.maxlen == maxlen
        assert streamer.accel_y_data.maxlen == maxlen
        assert streamer.accel_z_data.maxlen == maxlen
        assert streamer.gyr_x_data.maxlen == maxlen
        assert streamer.gyr_y_data.maxlen == maxlen
        assert streamer.gyr_z_data.maxlen == maxlen
        assert streamer.mag_x_data.maxlen == maxlen
        assert streamer.mag_y_data.maxlen == maxlen
        assert streamer.mag_z_data.maxlen == maxlen
        assert streamer.quat_w_data.maxlen == maxlen
        assert streamer.quat_x_data.maxlen == maxlen
        assert streamer.quat_y_data.maxlen == maxlen
        assert streamer.quat_z_data.maxlen == maxlen
    
    def test_madgwick_filter_initialization(self):
        """Test Madgwick filter is initialized."""
        streamer = IMUStreamer(
            DEVICE_ADDRESS, CHARACTERISTIC_UUID,
            SAMPLE_FREC, PACKET_LENGTH, RAW_DATA_LENGTH
        )
        
        assert streamer.madgwick_filter is not None
        # Initial quaternion should be [1, 0, 0, 0]
        np.testing.assert_array_equal(streamer.Q, np.array([1., 0., 0., 0.]))

    @patch('builtins.input', return_value='yes')
    @patch('builtins.print')
    def test_ekf_noises_loaded_from_json(self, mock_print, mock_input):
        """Test EKF noises are loaded from ekf_noise.json when present."""
        mock_payload = json.dumps({'noises': [1e-4, 2e-3, 3e-2]})

        def exists_side_effect(path):
            return path == EKF_NOISE_FILE

        with patch('os.path.exists', side_effect=exists_side_effect):
            with patch('builtins.open', mock_open(read_data=mock_payload)):
                streamer = IMUStreamer(
                    DEVICE_ADDRESS, CHARACTERISTIC_UUID,
                    SAMPLE_FREC, PACKET_LENGTH, RAW_DATA_LENGTH
                )

        assert streamer.ekf_noises == [1e-4, 2e-3, 3e-2]

    @patch('os.path.exists', return_value=False)
    @patch('builtins.input', return_value='yes')
    @patch('builtins.print')
    def test_ekf_noises_default_when_json_missing(self, mock_print, mock_input, mock_exists):
        """Test EKF default noises are used when ekf_noise.json is absent."""
        streamer = IMUStreamer(
            DEVICE_ADDRESS, CHARACTERISTIC_UUID,
            SAMPLE_FREC, PACKET_LENGTH, RAW_DATA_LENGTH
        )

        assert streamer.ekf_noises == EKF_DEFAULT_NOISES
    
    @patch('os.path.exists')
    @patch('builtins.print')
    def test_calibration_file_not_found_warning(self, mock_print, mock_exists):
        """Test warning when calibration file doesn't exist."""
        mock_exists.return_value = False
        
        # Mock input to automatically say 'yes' to continue
        with patch('builtins.input', return_value='yes'):
            streamer = IMUStreamer(
                DEVICE_ADDRESS, CHARACTERISTIC_UUID,
                SAMPLE_FREC, PACKET_LENGTH, RAW_DATA_LENGTH
            )
        
        # Should print warning
        assert mock_print.called
        printed_text = ' '.join([str(call[0][0]) if call[0] else '' 
                                for call in mock_print.call_args_list])
        assert 'WARNING' in printed_text or 'calibration' in printed_text.lower()


class TestNotificationHandler:
    """Test BLE notification handler."""
    
    def create_valid_imu_packet(self, accel=(1000, 2000, 3000),
                                gyro=(100, 200, 300),
                                mag=(4000, 5000, 6000)):
        """Create a valid IMU data packet."""
        # Packet structure: [length, packet_type, IMU_data(58 bytes), checksum(2)]
        packet_type = 0x01
        packet_length = PACKET_LENGTH
        
        # Create IMU data for 3 IMUs (we only use first one)
        imu_data = b''
        for imu_idx in range(3):
            if imu_idx == 0:
                # Use provided values for first IMU
                values = accel + gyro + mag
            else:
                # Dummy values for other IMUs
                values = (0, 0, 0, 0, 0, 0, 0, 0, 0)
            
            # Pack 9 int16 values (accel_xyz, gyro_xyz, mag_xyz)
            imu_data += struct.pack('<hhhhhhhhh', *values)
            # Add 2 padding bytes to make 20 bytes per IMU
            imu_data += b'\x00\x00'
        
        # Ensure we have exactly RAW_DATA_LENGTH bytes
        imu_data = imu_data[:RAW_DATA_LENGTH]
        if len(imu_data) < RAW_DATA_LENGTH:
            imu_data += b'\x00' * (RAW_DATA_LENGTH - len(imu_data))
        
        # Create full packet
        packet = struct.pack('BB', packet_length, packet_type) + imu_data + b'\x00\x00'
        
        return packet
    
    @patch('os.path.exists', return_value=False)
    @patch('builtins.input', return_value='yes')
    @patch('builtins.print')
    def test_notification_handler_valid_packet(self, mock_print, mock_input, mock_exists):
        """Test notification handler with valid packet."""
        streamer = IMUStreamer(
            DEVICE_ADDRESS, CHARACTERISTIC_UUID,
            SAMPLE_FREC, PACKET_LENGTH, RAW_DATA_LENGTH
        )
        
        # Create valid packet
        packet = self.create_valid_imu_packet(
            accel=(1000, 2000, 3000),
            gyro=(100, 200, 300),
            mag=(4000, 5000, 6000)
        )
        
        # Call notification handler
        streamer.notification_handler(sender=None, data=packet)
        
        # Check that data was added to buffers
        assert len(streamer.data_buffer) == 1
        assert len(streamer.time_data) == 1
        assert len(streamer.accel_x_data) == 1
        assert len(streamer.quat_w_data) == 1
        
        # Check data values are in expected range
        data = streamer.data_buffer[0]
        assert 'accel_x' in data
        assert 'gyro_x' in data
        assert 'mag_x' in data
        assert 'timestamp' in data
    
    @patch('os.path.exists', return_value=False)
    @patch('builtins.input', return_value='yes')
    @patch('builtins.print')
    def test_notification_handler_multiple_packets(self, mock_print, mock_input, mock_exists):
        """Test processing multiple packets."""
        streamer = IMUStreamer(
            DEVICE_ADDRESS, CHARACTERISTIC_UUID,
            SAMPLE_FREC, PACKET_LENGTH, RAW_DATA_LENGTH,
            maxlen=10
        )
        
        # Send 5 packets
        for i in range(5):
            packet = self.create_valid_imu_packet(
                accel=(1000 + i*100, 2000, 3000),
                gyro=(100, 200, 300),
                mag=(4000, 5000, 6000)
            )
            streamer.notification_handler(sender=None, data=packet)
        
        # Check data buffer has 5 entries
        assert len(streamer.data_buffer) == 5
        assert len(streamer.time_data) == 5
    
    @patch('os.path.exists', return_value=False)
    @patch('builtins.input', return_value='yes')
    @patch('builtins.print')
    def test_notification_handler_deque_overflow(self, mock_print, mock_input, mock_exists):
        """Test that deques correctly limit size."""
        maxlen = 3
        streamer = IMUStreamer(
            DEVICE_ADDRESS, CHARACTERISTIC_UUID,
            SAMPLE_FREC, PACKET_LENGTH, RAW_DATA_LENGTH,
            maxlen=maxlen
        )
        
        # Send more packets than maxlen
        for i in range(5):
            packet = self.create_valid_imu_packet()
            streamer.notification_handler(sender=None, data=packet)
        
        # Deques should only contain last 'maxlen' items
        assert len(streamer.time_data) == maxlen
        assert len(streamer.accel_x_data) == maxlen
        
        # Data buffer should have all items (no maxlen)
        assert len(streamer.data_buffer) == 5
    
    @patch('os.path.exists', return_value=False)
    @patch('builtins.input', return_value='yes')
    @patch('builtins.print')
    def test_notification_handler_invalid_packet_length(self, mock_print, mock_input, mock_exists):
        """Test handler ignores packets with wrong length."""
        streamer = IMUStreamer(
            DEVICE_ADDRESS, CHARACTERISTIC_UUID,
            SAMPLE_FREC, PACKET_LENGTH, RAW_DATA_LENGTH
        )
        
        # Create packet with wrong length
        invalid_packet = b'\x00' * 30  # Too short
        
        initial_buffer_len = len(streamer.data_buffer)
        streamer.notification_handler(sender=None, data=invalid_packet)
        
        # Should not add to buffer
        assert len(streamer.data_buffer) == initial_buffer_len
    
    @patch('os.path.exists', return_value=False)
    @patch('builtins.input', return_value='yes')
    @patch('builtins.print')
    def test_start_time_set_on_first_packet(self, mock_print, mock_input, mock_exists):
        """Test that start_time is set on first packet."""
        streamer = IMUStreamer(
            DEVICE_ADDRESS, CHARACTERISTIC_UUID,
            SAMPLE_FREC, PACKET_LENGTH, RAW_DATA_LENGTH
        )
        
        assert streamer.start_time is None
        
        packet = self.create_valid_imu_packet()
        streamer.notification_handler(sender=None, data=packet)
        
        assert streamer.start_time is not None
        assert isinstance(streamer.start_time, datetime)
    
    @patch('os.path.exists', return_value=False)
    @patch('builtins.input', return_value='yes')
    @patch('builtins.print')
    def test_time_data_increases(self, mock_print, mock_input, mock_exists):
        """Test that elapsed time increases with packets."""
        streamer = IMUStreamer(
            DEVICE_ADDRESS, CHARACTERISTIC_UUID,
            SAMPLE_FREC, PACKET_LENGTH, RAW_DATA_LENGTH
        )
        
        import time
        
        packet = self.create_valid_imu_packet()
        streamer.notification_handler(sender=None, data=packet)
        first_time = streamer.time_data[0]
        
        time.sleep(0.01)  # Small delay
        
        streamer.notification_handler(sender=None, data=packet)
        second_time = streamer.time_data[1]
        
        # Second timestamp should be greater
        assert second_time > first_time


class TestDataConversions:
    """Test sensor data unit conversions."""
    
    @patch('os.path.exists', return_value=False)
    @patch('builtins.input', return_value='yes')
    @patch('builtins.print')
    def test_accelerometer_conversion(self, mock_print, mock_input, mock_exists):
        """Test accelerometer raw to m/s² conversion."""
        streamer = IMUStreamer(
            DEVICE_ADDRESS, CHARACTERISTIC_UUID,
            SAMPLE_FREC, PACKET_LENGTH, RAW_DATA_LENGTH
        )
        
        # Known raw value
        raw_accel = 1000  # Raw int16 value
        
        packet = self.create_valid_imu_packet(accel=(raw_accel, 0, 0))
        streamer.notification_handler(sender=None, data=packet)
        
        # Check conversion: raw * ACCEL_SENSITIVITY * GRAVITY
        expected = raw_accel * ACCEL_SENSITIVITY * GRAVITY
        actual = streamer.data_buffer[0]['accel_x']
        
        assert abs(actual - expected) < 0.001
    
    @patch('os.path.exists', return_value=False)
    @patch('builtins.input', return_value='yes')
    @patch('builtins.print')
    def test_gyroscope_conversion(self, mock_print, mock_input, mock_exists):
        """Test gyroscope raw to rad/s conversion."""
        streamer = IMUStreamer(
            DEVICE_ADDRESS, CHARACTERISTIC_UUID,
            SAMPLE_FREC, PACKET_LENGTH, RAW_DATA_LENGTH
        )
        
        raw_gyro = 500  # Raw int16 value
        
        packet = self.create_valid_imu_packet(gyro=(raw_gyro, 0, 0))
        streamer.notification_handler(sender=None, data=packet)
        
        # Check conversion: raw * GYRO_SENSITIVITY * DEG_TO_RAD
        expected = raw_gyro * GYRO_SENSITIVITY * DEG_TO_RAD
        actual = streamer.data_buffer[0]['gyro_x']
        
        assert abs(actual - expected) < 0.0001
    
    @patch('os.path.exists', return_value=False)
    @patch('builtins.input', return_value='yes')
    @patch('builtins.print')
    def test_magnetometer_conversion(self, mock_print, mock_input, mock_exists):
        """Test magnetometer raw to nT conversion."""
        streamer = IMUStreamer(
            DEVICE_ADDRESS, CHARACTERISTIC_UUID,
            SAMPLE_FREC, PACKET_LENGTH, RAW_DATA_LENGTH
        )
        
        raw_mag = 200  # Raw int16 value
        
        packet = self.create_valid_imu_packet(mag=(raw_mag, 0, 0))
        streamer.notification_handler(sender=None, data=packet)
        
        # Check conversion: raw * MAG_SENSITIVITY
        expected = raw_mag * MAG_SENSITIVITY
        actual = streamer.data_buffer[0]['mag_x']
        
        assert abs(actual - expected) < 0.1
    
    def create_valid_imu_packet(self, accel=(1000, 2000, 3000),
                                gyro=(100, 200, 300),
                                mag=(4000, 5000, 6000)):
        """Helper method for creating packets."""
        packet_type = 0x01
        packet_length = PACKET_LENGTH
        
        imu_data = b''
        for imu_idx in range(3):
            if imu_idx == 0:
                values = accel + gyro + mag
            else:
                values = (0, 0, 0, 0, 0, 0, 0, 0, 0)
            
            imu_data += struct.pack('<hhhhhhhhh', *values)
            imu_data += b'\x00\x00'
        
        imu_data = imu_data[:RAW_DATA_LENGTH]
        if len(imu_data) < RAW_DATA_LENGTH:
            imu_data += b'\x00' * (RAW_DATA_LENGTH - len(imu_data))
        
        packet = struct.pack('BB', packet_length, packet_type) + imu_data + b'\x00\x00'
        return packet


class TestMagnetometerCalibration:
    """Test magnetometer calibration integration."""
    
    @patch('os.path.exists', return_value=True)
    @patch('builtins.print')
    def test_load_calibration_on_init(self, mock_print, mock_exists):
        """Test that calibration is loaded on initialization if file exists."""
        import tempfile
        import json
        
        # Create a temporary calibration file
        cal_data = {
            'hard_iron_offset': [10.0, 20.0, 30.0],
            'soft_iron_matrix': [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0]
            ],
            'is_calibrated': True
        }
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(cal_data, f)
            temp_file = f.name
        
        try:
            # Mock the file path
            with patch('os.path.exists', return_value=True):
                with patch('src.ble_stream.MagnetometerCalibration.load_calibration') as mock_load:
                    streamer = IMUStreamer(
                        DEVICE_ADDRESS, CHARACTERISTIC_UUID,
                        SAMPLE_FREC, PACKET_LENGTH, RAW_DATA_LENGTH
                    )
                    
                    # Should try to load calibration
                    mock_load.assert_called_once()
        finally:
            import os
            if os.path.exists(temp_file):
                os.remove(temp_file)


class TestQuaternionUpdate:
    """Test quaternion updates from Madgwick filter."""
    
    @patch('os.path.exists', return_value=False)
    @patch('builtins.input', return_value='yes')
    @patch('builtins.print')
    def test_quaternion_updated_on_packet(self, mock_print, mock_input, mock_exists):
        """Test that quaternion is updated when packet received."""
        streamer = IMUStreamer(
            DEVICE_ADDRESS, CHARACTERISTIC_UUID,
            SAMPLE_FREC, PACKET_LENGTH, RAW_DATA_LENGTH
        )
        
        # Initial quaternion should be identity
        np.testing.assert_array_equal(streamer.Q, np.array([1., 0., 0., 0.]))
        
        # Create and process packet
        packet = self.create_valid_imu_packet()
        streamer.notification_handler(sender=None, data=packet)
        
        # Quaternion should be updated (may still be close to identity for one packet)
        assert len(streamer.quat_w_data) == 1
        assert len(streamer.quat_x_data) == 1
        assert len(streamer.quat_y_data) == 1
        assert len(streamer.quat_z_data) == 1
        
        # Quaternion should be normalized
        q_norm = np.sqrt(
            streamer.quat_w_data[0]**2 + 
            streamer.quat_x_data[0]**2 +
            streamer.quat_y_data[0]**2 + 
            streamer.quat_z_data[0]**2
        )
        assert abs(q_norm - 1.0) < 0.1  # Should be close to 1
    
    def create_valid_imu_packet(self, accel=(1000, 2000, 3000),
                                gyro=(100, 200, 300),
                                mag=(4000, 5000, 6000)):
        """Helper method."""
        packet_type = 0x01
        packet_length = PACKET_LENGTH
        
        imu_data = b''
        for imu_idx in range(3):
            if imu_idx == 0:
                values = accel + gyro + mag
            else:
                values = (0, 0, 0, 0, 0, 0, 0, 0, 0)
            
            imu_data += struct.pack('<hhhhhhhhh', *values)
            imu_data += b'\x00\x00'
        
        imu_data = imu_data[:RAW_DATA_LENGTH]
        if len(imu_data) < RAW_DATA_LENGTH:
            imu_data += b'\x00' * (RAW_DATA_LENGTH - len(imu_data))
        
        packet = struct.pack('BB', packet_length, packet_type) + imu_data + b'\x00\x00'
        return packet


class TestInstrumentation:
    """Test Phase 1 instrumentation outputs."""

    def create_valid_imu_packet(self, accel=(1000, 2000, 3000),
                                gyro=(100, 200, 300),
                                mag=(4000, 5000, 6000)):
        packet_type = 0x01
        packet_length = PACKET_LENGTH

        imu_data = b''
        for imu_idx in range(3):
            if imu_idx == 0:
                values = accel + gyro + mag
            else:
                values = (0, 0, 0, 0, 0, 0, 0, 0, 0)

            imu_data += struct.pack('<hhhhhhhhh', *values)
            imu_data += b'\x00\x00'

        imu_data = imu_data[:RAW_DATA_LENGTH]
        if len(imu_data) < RAW_DATA_LENGTH:
            imu_data += b'\x00' * (RAW_DATA_LENGTH - len(imu_data))

        packet = struct.pack('BB', packet_length, packet_type) + imu_data + b'\x00\x00'
        return packet

    @patch('os.path.exists', return_value=False)
    @patch('builtins.input', return_value='yes')
    @patch('builtins.print')
    def test_per_sample_dt_and_mag_norm_logged(self, mock_print, mock_input, mock_exists):
        streamer = IMUStreamer(
            DEVICE_ADDRESS, CHARACTERISTIC_UUID,
            SAMPLE_FREC, PACKET_LENGTH, RAW_DATA_LENGTH
        )

        packet = self.create_valid_imu_packet()
        streamer.notification_handler(sender=None, data=packet)
        streamer.notification_handler(sender=None, data=packet)

        assert len(streamer.data_buffer) == 2
        first = streamer.data_buffer[0]
        second = streamer.data_buffer[1]

        assert 'dt' in first
        assert 'mag_norm_raw' in first
        assert 'mag_norm_calibrated' in first
        assert first['dt'] is None
        assert second['dt'] is not None
        assert second['dt'] >= 0.0
        assert first['mag_norm_raw'] > 0.0
        assert first['mag_norm_calibrated'] > 0.0

    @patch('os.path.exists', return_value=False)
    @patch('builtins.input', return_value='yes')
    @patch('builtins.print')
    def test_static_window_gyro_summary_generated(self, mock_print, mock_input, mock_exists):
        streamer = IMUStreamer(
            DEVICE_ADDRESS, CHARACTERISTIC_UUID,
            SAMPLE_FREC, PACKET_LENGTH, RAW_DATA_LENGTH
        )

        # Approximate +1g on Z-axis raw value for LSM6DSV sensitivity.
        static_packet = self.create_valid_imu_packet(
            accel=(0, 0, 16384),
            gyro=(0, 0, 0),
            mag=(4000, 5000, 6000)
        )
        moving_packet = self.create_valid_imu_packet(
            accel=(0, 0, 16384),
            gyro=(2000, 0, 0),
            mag=(4000, 5000, 6000)
        )

        for _ in range(55):
            streamer.notification_handler(sender=None, data=static_packet)

        # End static segment so it is finalized into a window summary.
        streamer.notification_handler(sender=None, data=moving_packet)

        static_df = streamer.get_static_windows_dataframe()
        assert not static_df.empty

        first_window = static_df.iloc[0]
        assert first_window['sample_count'] >= streamer.static_window_min_samples
        assert abs(first_window['gyro_mean_x']) < 1e-6
        assert abs(first_window['gyro_mean_y']) < 1e-6
        assert abs(first_window['gyro_mean_z']) < 1e-6

    @patch('os.path.exists', return_value=False)
    @patch('builtins.input', return_value='yes')
    @patch('builtins.print')
    def test_instrumentation_summary_contains_expected_sections(self, mock_print, mock_input, mock_exists):
        streamer = IMUStreamer(
            DEVICE_ADDRESS, CHARACTERISTIC_UUID,
            SAMPLE_FREC, PACKET_LENGTH, RAW_DATA_LENGTH
        )

        packet = self.create_valid_imu_packet()
        for _ in range(3):
            streamer.notification_handler(sender=None, data=packet)

        summary = streamer.get_instrumentation_summary()

        assert summary['sample_count'] == 3
        assert 'dt_stats' in summary
        assert 'mag_norm_stats' in summary
        assert 'static_windows' in summary


@pytest.mark.asyncio
class TestAsyncStreaming:
    """Test async BLE streaming (with mocks)."""
    
    @patch('os.path.exists', return_value=False)
    @patch('builtins.input', return_value='yes')
    @patch('builtins.print')
    async def test_stream_data_structure(self, mock_print, mock_input, mock_exists):
        """Test stream_data return structure."""
        # This is a basic structure test - full BLE testing would require
        # more complex mocking of bleak library
        streamer = IMUStreamer(
            DEVICE_ADDRESS, CHARACTERISTIC_UUID,
            SAMPLE_FREC, PACKET_LENGTH, RAW_DATA_LENGTH
        )
        
        # Add some mock data to buffer
        streamer.data_buffer.append({
            'timestamp': datetime.now(),
            'imu_index': 0,
            'accel_x': 1.0, 'accel_y': 2.0, 'accel_z': 3.0,
            'gyro_x': 0.1, 'gyro_y': 0.2, 'gyro_z': 0.3,
            'mag_x': 100.0, 'mag_y': 200.0, 'mag_z': 300.0
        })
        
        # The stream_data method returns a DataFrame
        # We can't fully test BLE connection without real hardware or complex mocks
        # but we can verify the structure
        assert hasattr(streamer, 'stream_data')
        assert callable(streamer.stream_data)
