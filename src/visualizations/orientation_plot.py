import matplotlib.pyplot as plt
import numpy as np
from ..utils import quaternion_to_rotation_matrix

class OrientationPlot3D:
    def __init__(self, streamer):
        self.quat_w = streamer.quat_w_data
        self.quat_x = streamer.quat_x_data
        self.quat_y = streamer.quat_y_data
        self.quat_z = streamer.quat_z_data
        
        # Create 3D plot
        self.fig = plt.figure(figsize=(8, 8))
        self.ax = self.fig.add_subplot(111, projection='3d')
        
        # Initial axes (identity orientation)
        self.x_axis = self.ax.quiver(0, 0, 0, 1, 0, 0, color='r', arrow_length_ratio=0.3, linewidth=3, label='X')
        self.y_axis = self.ax.quiver(0, 0, 0, 0, 1, 0, color='g', arrow_length_ratio=0.3, linewidth=3, label='Y')
        self.z_axis = self.ax.quiver(0, 0, 0, 0, 0, 1, color='b', arrow_length_ratio=0.3, linewidth=3, label='Z')
        
        # Set plot limits and labels
        self.ax.set_xlim([-1, 1])
        self.ax.set_ylim([-1, 1])
        self.ax.set_zlim([-1, 1])
        self.ax.set_xlabel('X')
        self.ax.set_ylabel('Y')
        self.ax.set_zlabel('Z')
        self.ax.set_title('IMU Orientation (Real-time)')
        self.ax.legend()
        
        # Set equal aspect ratio
        self.ax.set_box_aspect([1,1,1])
    
    def update(self, frame):
        if len(self.quat_w) > 0:
            # Get latest quaternion
            q = [self.quat_w[-1], self.quat_x[-1], self.quat_y[-1], self.quat_z[-1]]
            
            # Convert to rotation matrix
            R = quaternion_to_rotation_matrix(q)
            
            # Rotated axes
            x_rotated = R @ np.array([1, 0, 0])
            y_rotated = R @ np.array([0, 1, 0])
            z_rotated = R @ np.array([0, 0, 1])
            
            # Remove old arrows
            while self.ax.collections:
                self.ax.collections[0].remove()
            
            # Draw new arrows
            self.x_axis = self.ax.quiver(0, 0, 0, x_rotated[0], x_rotated[1], x_rotated[2], 
                                         color='r', arrow_length_ratio=0.3, linewidth=3)
            self.y_axis = self.ax.quiver(0, 0, 0, y_rotated[0], y_rotated[1], y_rotated[2], 
                                         color='g', arrow_length_ratio=0.3, linewidth=3)
            self.z_axis = self.ax.quiver(0, 0, 0, z_rotated[0], z_rotated[1], z_rotated[2], 
                                         color='b', arrow_length_ratio=0.3, linewidth=3)
        
        return self.x_axis, self.y_axis, self.z_axis
