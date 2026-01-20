import math

DEVICE_ADDRESS = "F2:3C:0E:CF:1B:FA"  # Device's MAC address
CHARACTERISTIC_UUID = "6cc9e001-b908-4dc9-8a1a-9fd001a8b75c"  # Characteristic UUID
PACKET_LENGTH = 62 # Expected packet length in bytes
RAW_DATA_LENGTH = 58 # Expected bytes of contiguous raw data (accelerometer, gyroscope and magnetometer)
ACCEL_SENSITIVITY = 0.061/1000.0
GYRO_SENSITIVITY = 17.5/1000.0 ## Mod: sensitivity
MAG_SENSITIVITY = 1.5 * 100 ## Mod: sensitivity
DEG_TO_RAD = math.pi / 180.0
GRAVITY = 9.80665
SAMPLE_FREC = 100
MAX_POINTS = 100  # Number of points to display