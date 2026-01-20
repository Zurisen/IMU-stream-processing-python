import matplotlib.pyplot as plt

class StreamPlot():
    def __init__(self, streamer, type="acc"):

        self.streamer = streamer

        # Setup the plot in the main thread
        self.fig, self.ax = plt.subplots(figsize=(10, 6))
        self.line_x, = self.ax.plot([], [], 'r-', label='Accel X')
        self.line_y, = self.ax.plot([], [], 'g-', label='Accel Y')
        self.line_z, = self.ax.plot([], [], 'b-', label='Accel Z')

        self.text_x = self.ax.text(0, 0, '', color='r', fontsize=10)
        self.text_y = self.ax.text(0, 0, '', color='g', fontsize=10)
        self.text_z = self.ax.text(0, 0, '', color='b', fontsize=10)

        self.ax.set_xlabel('Time (s)')
        self.time_data = self.streamer.time_data
        match type:
            case "acc":
                self.x_data = self.streamer.accel_x_data
                self.y_data = self.streamer.accel_y_data
                self.z_data = self.streamer.accel_z_data
                self.ax.set_ylabel('Acceleration (m/s²)')
                self.ax.set_title('IMU 0 - Accelerometer (Real-time)')
                self.ax.legend()
                self.ax.grid(True)
                self.ax.set_xlim(0, 10)
                self.ax.set_ylim(-20, 20)
            case "gyr":
                self.x_data = self.streamer.gyr_x_data
                self.y_data = self.streamer.gyr_y_data
                self.z_data = self.streamer.gyr_z_data
                self.ax.set_ylabel('Rotation (rad/s)')
                self.ax.set_title('GYR 0 - Gyroscope(Real-time)')
                self.ax.legend()
                self.ax.grid(True)
                self.ax.set_xlim(0, 10)
                self.ax.set_ylim(-100, 100)
            case "mag":
                self.x_data = self.streamer.mag_x_data
                self.y_data = self.streamer.mag_y_data
                self.z_data = self.streamer.mag_z_data
                self.ax.set_ylabel('Rotation (nT)')
                self.ax.set_title('MAG 0 - (Real-time)')
                self.ax.legend()
                self.ax.grid(True)
                self.ax.set_xlim(0, 10)
                self.ax.set_ylim(-100, 100)
            case _:
                raise ValueError(f"Invalid type '{type}'. Must be 'acc', 'gyr', or 'mag'.")
            
    
    def update(self, frame):
        if len(self.time_data) > 0:
            
            self.line_x.set_data(list(self.time_data), list(self.x_data))
            self.line_y.set_data(list(self.time_data), list(self.y_data))
            self.line_z.set_data(list(self.time_data), list(self.z_data))

            self.text_x.set_position((self.time_data[-1], self.x_data[-1]))
            self.text_x.set_text(f'{self.x_data[-1]:.2f}')
            
            self.text_y.set_position((self.time_data[-1], self.y_data[-1]))
            self.text_y.set_text(f'{self.y_data[-1]:.2f}')
            
            self.text_z.set_position((self.time_data[-1], self.z_data[-1]))
            self.text_z.set_text(f'{self.z_data[-1]:.2f}')
            
            if len(self.time_data) > 1:
                self.ax.set_xlim(max(0, self.time_data[-1] - 10), self.time_data[-1] + 1)
        
        return self.line_x, self.line_y, self.line_z, self.text_x, self.text_y, self.text_z
