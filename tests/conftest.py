"""
Pytest configuration and shared fixtures.
"""
import pytest
import numpy as np
import tempfile
import os
from unittest.mock import Mock
from collections import deque


@pytest.fixture
def temp_json_file():
    """Provide a temporary JSON file path."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        filepath = f.name
    
    yield filepath
    
    # Cleanup
    if os.path.exists(filepath):
        os.remove(filepath)


@pytest.fixture
def sample_mag_data():
    """Generate sample magnetometer data for testing."""
    n_points = 500
    field_strength = 45000.0
    
    # Generate points on a sphere
    phi = np.random.uniform(0, 2*np.pi, n_points)
    theta = np.random.uniform(0, np.pi, n_points)
    
    x = field_strength * np.sin(theta) * np.cos(phi)
    y = field_strength * np.sin(theta) * np.sin(phi)
    z = field_strength * np.cos(theta)
    
    data = np.column_stack([x, y, z])
    # Add some noise
    data += np.random.normal(0, 500, data.shape)
    
    return data


@pytest.fixture
def sample_mag_data_with_bias():
    """Generate magnetometer data with known bias."""
    n_points = 500
    field_strength = 45000.0
    hard_iron = np.array([1000.0, 2000.0, 3000.0])
    
    # Generate points on a sphere
    phi = np.random.uniform(0, 2*np.pi, n_points)
    theta = np.random.uniform(0, np.pi, n_points)
    
    x = field_strength * np.sin(theta) * np.cos(phi)
    y = field_strength * np.sin(theta) * np.sin(phi)
    z = field_strength * np.cos(theta)
    
    clean_data = np.column_stack([x, y, z])
    
    # Apply bias
    biased_data = clean_data + hard_iron
    
    # Add noise
    biased_data += np.random.normal(0, 500, biased_data.shape)
    
    return biased_data, hard_iron


@pytest.fixture
def mock_streamer():
    """Create a mock IMU streamer with data buffers."""
    streamer = Mock()
    
    # Initialize deques
    maxlen = 100
    streamer.time_data = deque(maxlen=maxlen)
    streamer.accel_x_data = deque(maxlen=maxlen)
    streamer.accel_y_data = deque(maxlen=maxlen)
    streamer.accel_z_data = deque(maxlen=maxlen)
    streamer.gyr_x_data = deque(maxlen=maxlen)
    streamer.gyr_y_data = deque(maxlen=maxlen)
    streamer.gyr_z_data = deque(maxlen=maxlen)
    streamer.mag_x_data = deque(maxlen=maxlen)
    streamer.mag_y_data = deque(maxlen=maxlen)
    streamer.mag_z_data = deque(maxlen=maxlen)
    streamer.quat_w_data = deque(maxlen=maxlen)
    streamer.quat_x_data = deque(maxlen=maxlen)
    streamer.quat_y_data = deque(maxlen=maxlen)
    streamer.quat_z_data = deque(maxlen=maxlen)
    
    streamer.data_buffer = []
    streamer.start_time = None
    
    return streamer


@pytest.fixture
def mock_streamer_with_data():
    """Create a mock streamer with sample data."""
    streamer = Mock()
    
    maxlen = 100
    # Add sample data
    time_points = np.linspace(0, 10, 50)
    streamer.time_data = deque(time_points, maxlen=maxlen)
    
    # Accelerometer data (m/s²)
    streamer.accel_x_data = deque(np.sin(time_points) * 5, maxlen=maxlen)
    streamer.accel_y_data = deque(np.cos(time_points) * 5, maxlen=maxlen)
    streamer.accel_z_data = deque(np.ones_like(time_points) * 9.8, maxlen=maxlen)
    
    # Gyroscope data (rad/s)
    streamer.gyr_x_data = deque(np.sin(time_points) * 0.5, maxlen=maxlen)
    streamer.gyr_y_data = deque(np.cos(time_points) * 0.5, maxlen=maxlen)
    streamer.gyr_z_data = deque(np.sin(time_points * 2) * 0.3, maxlen=maxlen)
    
    # Magnetometer data (nT)
    streamer.mag_x_data = deque(np.ones_like(time_points) * 25000, maxlen=maxlen)
    streamer.mag_y_data = deque(np.ones_like(time_points) * 30000, maxlen=maxlen)
    streamer.mag_z_data = deque(np.ones_like(time_points) * 35000, maxlen=maxlen)
    
    # Quaternion data
    streamer.quat_w_data = deque(np.ones_like(time_points), maxlen=maxlen)
    streamer.quat_x_data = deque(np.zeros_like(time_points), maxlen=maxlen)
    streamer.quat_y_data = deque(np.zeros_like(time_points), maxlen=maxlen)
    streamer.quat_z_data = deque(np.zeros_like(time_points), maxlen=maxlen)
    
    return streamer


@pytest.fixture
def identity_quaternion():
    """Provide identity quaternion [w, x, y, z]."""
    return np.array([1.0, 0.0, 0.0, 0.0])


@pytest.fixture
def rotation_quaternion_90deg_z():
    """Provide 90-degree rotation about Z axis quaternion."""
    angle = np.pi / 4  # Half angle for quaternion
    return np.array([np.cos(angle), 0.0, 0.0, np.sin(angle)])


@pytest.fixture
def sample_calibration_params():
    """Provide sample calibration parameters."""
    return {
        'hard_iron_offset': [100.0, 200.0, 300.0],
        'soft_iron_matrix': [
            [1.2, 0.1, 0.0],
            [0.1, 0.9, 0.0],
            [0.0, 0.0, 1.1]
        ],
        'is_calibrated': True
    }


@pytest.fixture(autouse=True)
def reset_random_seed():
    """Reset random seed before each test for reproducibility."""
    np.random.seed(42)


@pytest.fixture
def suppress_matplotlib_warnings():
    """Suppress matplotlib warnings during tests."""
    import warnings
    import matplotlib
    
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=matplotlib.MatplotlibDeprecationWarning)
        warnings.filterwarnings("ignore", category=UserWarning)
        yield
