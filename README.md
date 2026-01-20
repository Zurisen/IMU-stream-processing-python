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

## Usage

```bash
# Run the main application
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
