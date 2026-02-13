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

## Project Structure

```
IMU-stream-processing-python/
├── README.md
├── requirements.txt
├── run.py
└── src/
    ├── sensors/
    ├── processing/
    └── visualization/
```
