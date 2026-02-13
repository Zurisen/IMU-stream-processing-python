# Unit Tests for IMU Stream Processing

This directory contains comprehensive unit tests for the IMU stream processing Python project.

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures and pytest configuration
├── test_config.py           # Tests for configuration constants
├── test_utils.py            # Tests for utility functions
├── test_mag_calibration.py  # Tests for magnetometer calibration
├── test_ble_stream.py       # Tests for BLE streaming (with mocks)
└── test_visualizations.py   # Tests for visualization modules
```

## Installation

Install test dependencies:

```bash
pip install -r requirements-test.txt
```

Or install all dependencies including test requirements:

```bash
pip install -r requirements
pip install -r requirements-test.txt
```

## Running Tests

### Run all tests:

```bash
pytest
```

### Run with verbose output:

```bash
pytest -v
```

### Run specific test file:

```bash
pytest tests/test_config.py
pytest tests/test_mag_calibration.py
```

### Run specific test class:

```bash
pytest tests/test_mag_calibration.py::TestMagnetometerCalibration
```

### Run specific test function:

```bash
pytest tests/test_utils.py::TestQuaternionToRotationMatrix::test_identity_quaternion
```

### Run with coverage report:

```bash
pytest --cov=src --cov-report=html
```

This generates an HTML coverage report in `htmlcov/index.html`.

### Run tests in parallel (faster):

```bash
pytest -n auto
```

(Requires `pytest-xdist`: `pip install pytest-xdist`)

## Test Coverage

The test suite covers:

### 1. Configuration (`test_config.py`)

- Validation of all configuration constants
- MAC address and UUID format validation
- Sensitivity and conversion factor tests
- Configuration value range checks

### 2. Utilities (`test_utils.py`)

- Quaternion to rotation matrix conversion
- Identity quaternion handling
- Rotation matrix properties (orthogonality, determinant)
- Various rotation angles and axes
- Input type handling

### 3. Magnetometer Calibration (`test_mag_calibration.py`)

- Initialization and configuration
- Diagonal-only calibration
- Full 3x3 soft iron calibration
- Calibration application to data
- Save/load calibration files
- Calibration quality analysis
- Validation with quality metrics
- Matrix quality evaluation

### 4. BLE Streaming (`test_ble_stream.py`)

- IMUStreamer initialization
- Data buffer management
- Notification handler with mock BLE data
- Packet parsing and validation
- Sensor data unit conversions
- Magnetometer calibration integration
- Quaternion updates from Madgwick filter
- Deque overflow handling

### 5. Visualizations (`test_visualizations.py`)

- StreamPlot initialization for acc/gyr/mag
- Plot updates with data
- Axis limits and labels
- Text label updates
- OrientationPlot3D initialization
- 3D orientation visualization
- Quaternion-based rotation display
- Empty data handling

## Test Fixtures

Common fixtures are defined in `conftest.py`:

- `temp_json_file`: Temporary file for testing file I/O
- `sample_mag_data`: Synthetic magnetometer data
- `sample_mag_data_with_bias`: Biased magnetometer data
- `mock_streamer`: Mock IMU streamer object
- `mock_streamer_with_data`: Mock streamer with sample data
- `identity_quaternion`: Identity quaternion [1, 0, 0, 0]
- `rotation_quaternion_90deg_z`: 90° rotation about Z axis
- `sample_calibration_params`: Sample calibration parameters

## Writing New Tests

### Example test structure:

```python
import pytest
import numpy as np
from src.your_module import YourClass

class TestYourClass:
    """Test YourClass functionality."""

    def test_basic_functionality(self):
        """Test basic functionality."""
        obj = YourClass()
        result = obj.method()
        assert result == expected_value

    def test_with_fixture(self, sample_mag_data):
        """Test using a fixture."""
        obj = YourClass()
        result = obj.process(sample_mag_data)
        assert result.shape == sample_mag_data.shape
```

### Best Practices:

1. **Use descriptive test names**: `test_quaternion_to_rotation_matrix_identity`
2. **Test one thing per test**: Each test should verify one specific behavior
3. **Use fixtures for common setup**: Avoid code duplication
4. **Mock external dependencies**: BLE connections, file I/O, etc.
5. **Use pytest.mark for categorization**: `@pytest.mark.slow`, `@pytest.mark.integration`
6. **Test edge cases**: Empty data, invalid inputs, boundary conditions
7. **Check both success and failure**: Test error handling

## Continuous Integration

These tests are designed to run in CI/CD pipelines. Example GitHub Actions workflow:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: "3.10"
      - run: pip install -r requirements -r requirements-test.txt
      - run: pytest --cov=src --cov-report=xml
      - uses: codecov/codecov-action@v2
```

## Troubleshooting

### Import Errors

If you get import errors, make sure you're running pytest from the project root:

```bash
cd /path/to/IMU-stream-processing-python
pytest
```

### Matplotlib Backend Issues

Tests use the 'Agg' backend (non-GUI) for matplotlib. If you see display-related errors, ensure matplotlib is properly configured:

```python
import matplotlib
matplotlib.use('Agg')
```

### BLE Mock Issues

BLE streaming tests use mocks. They don't require actual BLE hardware. If you see BLE-related errors, ensure `unittest.mock` is working correctly.

### Coverage Not Showing

Make sure you have pytest-cov installed:

```bash
pip install pytest-cov
```

## Current Test Statistics

Run `pytest --cov=src --cov-report=term` to see current coverage statistics.

Target coverage: **>80%** for all modules.

## Contributing

When adding new features:

1. Write tests first (TDD approach)
2. Ensure all tests pass: `pytest`
3. Check coverage: `pytest --cov=src`
4. Add integration tests for complex features
5. Update this README if adding new test categories
