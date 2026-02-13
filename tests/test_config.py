"""
Unit tests for src/config.py module.
Tests configuration constants and values.
"""
import pytest
import math
from src.config import *


class TestConfigConstants:
    """Test configuration constants."""
    
    def test_device_address_format(self):
        """Test that device address is in correct MAC address format."""
        assert isinstance(DEVICE_ADDRESS, str)
        # Check MAC address format (XX:XX:XX:XX:XX:XX)
        parts = DEVICE_ADDRESS.split(':')
        assert len(parts) == 6
        for part in parts:
            assert len(part) == 2
            # Should be valid hex
            int(part, 16)
    
    def test_characteristic_uuid_format(self):
        """Test that characteristic UUID is valid."""
        assert isinstance(CHARACTERISTIC_UUID, str)
        # UUID format: 8-4-4-4-12 hexadecimal digits
        parts = CHARACTERISTIC_UUID.split('-')
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12
    
    def test_packet_length_positive(self):
        """Test packet length is positive integer."""
        assert isinstance(PACKET_LENGTH, int)
        assert PACKET_LENGTH > 0
        assert PACKET_LENGTH == 62
    
    def test_raw_data_length_positive(self):
        """Test raw data length is positive and less than packet length."""
        assert isinstance(RAW_DATA_LENGTH, int)
        assert RAW_DATA_LENGTH > 0
        assert RAW_DATA_LENGTH <= PACKET_LENGTH
        assert RAW_DATA_LENGTH == 58
    
    def test_accel_sensitivity_positive(self):
        """Test accelerometer sensitivity is positive float."""
        assert isinstance(ACCEL_SENSITIVITY, float)
        assert ACCEL_SENSITIVITY > 0
        assert ACCEL_SENSITIVITY == 0.061 / 1000.0
    
    def test_gyro_sensitivity_positive(self):
        """Test gyroscope sensitivity is positive float."""
        assert isinstance(GYRO_SENSITIVITY, float)
        assert GYRO_SENSITIVITY > 0
        assert GYRO_SENSITIVITY == 17.5 / 1000.0
    
    def test_mag_sensitivity_positive(self):
        """Test magnetometer sensitivity is positive float."""
        assert isinstance(MAG_SENSITIVITY, (int, float))
        assert MAG_SENSITIVITY > 0
        assert MAG_SENSITIVITY == 1.5 * 100
    
    def test_deg_to_rad_conversion(self):
        """Test degree to radian conversion factor."""
        assert isinstance(DEG_TO_RAD, float)
        expected = math.pi / 180.0
        assert abs(DEG_TO_RAD - expected) < 1e-10
    
    def test_gravity_constant(self):
        """Test gravity constant value."""
        assert isinstance(GRAVITY, float)
        assert abs(GRAVITY - 9.80665) < 1e-10
    
    def test_sample_frequency_positive(self):
        """Test sample frequency is positive integer."""
        assert isinstance(SAMPLE_FREC, int)
        assert SAMPLE_FREC > 0
        assert SAMPLE_FREC == 100
    
    def test_max_points_positive(self):
        """Test max points for display is positive."""
        assert isinstance(MAX_POINTS, int)
        assert MAX_POINTS > 0
        assert MAX_POINTS == 100
    
    def test_conversion_values_realistic(self):
        """Test that sensitivity and conversion values are realistic."""
        # Accelerometer sensitivity should be in reasonable range
        assert 0.00001 < ACCEL_SENSITIVITY < 1.0
        
        # Gyro sensitivity should be in reasonable range
        assert 0.001 < GYRO_SENSITIVITY < 1.0
        
        # Mag sensitivity should be in reasonable range
        assert 1.0 < MAG_SENSITIVITY < 1000.0
        
        # Sample frequency should be reasonable
        assert 1 <= SAMPLE_FREC <= 10000


class TestConfigIntegration:
    """Integration tests for config values."""
    
    def test_packet_and_raw_data_relationship(self):
        """Test that packet length and raw data length are consistent."""
        # Raw data should fit within packet with some overhead
        overhead = PACKET_LENGTH - RAW_DATA_LENGTH
        assert overhead >= 4  # At least some header/footer space
    
    def test_sample_frequency_for_filter(self):
        """Test sample frequency is suitable for filter initialization."""
        # Should be positive and reasonable for real-time processing
        assert 10 <= SAMPLE_FREC <= 1000
