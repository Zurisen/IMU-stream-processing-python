from src.ble_stream import IMUStreamer
from src.visualizations.stream_plot import StreamPlot
from src.visualizations.orientation_plot import OrientationPlot3D
from src.config import *
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import threading

def main():
    duration = 30
    
    # Create streamer instance
    streamer = IMUStreamer(DEVICE_ADDRESS, CHARACTERISTIC_UUID, sample_freq=SAMPLE_FREC,
                           expected_packet_len=PACKET_LENGTH, raw_data_len=RAW_DATA_LENGTH)
    
    # Start streaming in thread
    ble_thread = threading.Thread(target=streamer.run_stream_thread, args=(duration,))
    ble_thread.start()
    
    # Wait for connection
    print("Waiting for BLE connection...")
    while streamer.start_time is None:
        pass
    
    # Create plot
    #plot = StreamPlot(streamer, type="acc")
    #ani = FuncAnimation(plot.fig, plot.update, interval=50, blit=False, cache_frame_data=False)
    plot = OrientationPlot3D(streamer)
    ani = FuncAnimation(plot.fig, plot.update, interval=50, blit=False, cache_frame_data=False)
    plt.show()
    
    ble_thread.join()
    return streamer.get_dataframe()

if __name__ == "__main__":
    df = main()