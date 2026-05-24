# IMU Stream Processing (Python)

A Python application for processing real-time streaming data from IMU (Inertial Measurement Unit) sensors, specifically designed for the LSM6DSV16X (6-axis accelerometer and gyroscope) and LIS2MDL (3-axis magnetometer).

## Features

- Real-time streaming data acquisition from IMU sensors
- Support for LSM6DSV16X accelerometer and gyroscope
- Support for LIS2MDL magnetometer
- Data processing and filtering
- Stream visualization and analysis

## Hardware Requirements

- **LSM6DSV16X**: 6-axis IMU with 3-axis accelerometer and 3-axis gyroscope
- **LIS2MDL**: 3-axis magnetometer
- Compatible microcontroller or development board with I2C/SPI interface

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/IMU-stream-processing-python.git
cd IMU-stream-processing-python

# Install dependencies
pip install -r requirements.txt
```

## Magnetometer Calibration

**Important:** Before using the magnetometer for orientation estimation, you must calibrate it to remove hard iron and soft iron distortions.

### Running Calibration

1. Run the calibration script:

```bash
python calibrate.py
```

2. Choose calibration options:
   - Select calibration method (full 3x3 with regularization recommended)
   - Adjust regularization strength if desired (default: 0.01)
   - Enable/disable real-time 3D visualization (recommended for first time)

3. Follow the on-screen instructions:
   - Watch the 3D visualization window showing data in real-time
   - Slowly rotate the sensor in all directions
   - Make figure-8 patterns in different orientations
   - Aim for >80% coverage (all octants filled - shown in real-time)
   - Monitor for environmental warnings (magnetic interference)
   - Continue for at least 30-60 seconds to cover all possible angles
   - Press `Ctrl+C` when coverage is complete

4. The calibration parameters will be saved to `mag_calibration.json` (if validation passes)

### What the Calibration Does

- **Hard Iron Correction**: Removes constant magnetic field offsets from nearby ferromagnetic materials
- **Soft Iron Correction**: Compensates for field distortions caused by nearby materials
- **Regularization**: Ensures physically plausible correction matrices (orthogonality, volume preservation)
- **Validation**: Automatically checks calibration quality and sphericity

### Calibration Methods

The script supports two calibration methods:

1. **Full 3x3 Soft Iron Matrix with Regularization** (recommended): Handles cross-axis interference and axis misalignment with physical constraints. Includes real-time 3D visualization for coverage feedback.
2. **Diagonal-only Soft Iron Matrix**: Simpler, faster calibration for basic applications

**Real-Time Visualization Features**:

- Live 3D scatter plot of magnetometer data
- Coverage percentage and octant tracking
- Environmental monitoring and disturbance warnings
- Visual guidance for complete sphere coverage

See [docs/realtime_visualization.md](docs/realtime_visualization.md), [docs/regularization.md](docs/regularization.md), and [docs/calibration_improvements.md](docs/calibration_improvements.md) for technical details.

### Calibration Quality

The calibration script will report quality metrics:

- **Excellent** (< 5% variability): Calibration is very accurate
- **Good** (5-10% variability): Calibration is acceptable
- **Fair** (> 10% variability): Consider recalibrating with more varied rotations

## Usage

```bash
# Run the main application (calibration will be loaded automatically if available)
python run.py
```

## EKF Noise Calibration (Q/R)

If you are using `FUSION_FILTER = "ekf"`, you can estimate EKF noise variances from a static capture and save them to JSON.

```bash
python calibrate_ekf_noise.py --duration 30
```

This generates `ekf_noise.json`, which is automatically loaded by the streamer at startup (similar to `mag_calibration.json`).

The file contains:

- `var_gyr`: gyroscope variance estimate (used in process noise/Q)
- `var_acc`: accelerometer variance estimate (used in measurement noise/R)
- `var_mag`: magnetometer variance estimate (used in measurement noise/R)
- `noises`: `[var_gyr, var_acc, var_mag]` ready for `ahrs.filters.EKF`

Re-run the calibration whenever sensor mounting, environment, or firmware settings change.

## Testing

This project includes comprehensive unit tests for all modules.

### Running Tests

Install test dependencies:

```bash
pip install -r requirements-test.txt
```

Run all tests:

```bash
pytest
```

Run tests with coverage report:

```bash
pytest --cov=src --cov-report=html
```

Or use the provided test runner:

```bash
python run_tests.py -v -c
```

See [tests/README.md](tests/README.md) for detailed testing documentation.

### Test Coverage

The test suite includes:

- Configuration validation tests
- Quaternion and rotation matrix tests
- Magnetometer calibration tests (with synthetic data)
- BLE streaming tests (with mocked connections)
- Visualization tests

Target coverage: **>80%** for all modules.

## Project Structure

```
IMU-stream-processing-python/
├── README.md
├── requirements.txt
├── requirements-test.txt
├── pyproject.toml
├── run.py
├── calibrate.py
├── run_tests.py
├── mag_calibration.json
├── docs/
│   ├── calibration_improvements.md
│   ├── critic_implementation.md
│   ├── critic.md
│   ├── realtime_visualization.md
│   ├── regularization_summary.md
│   └── regularization.md
├── src/
│   ├── __init__.py
│   ├── ble_stream.py
│   ├── config.py
│   ├── mag_calibration.py
│   ├── utils.py
│   └── visualizations/
│       ├── __init__.py
│       ├── orientation_plot.py
│       └── stream_plot.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── README.md
    ├── test_config.py
    ├── test_utils.py
    ├── test_mag_calibration.py
    ├── test_ble_stream.py
    └── test_visualizations.py
```
