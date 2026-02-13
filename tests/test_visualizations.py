"""
Unit tests for src/visualizations modules.
Tests visualization classes for streaming and orientation plots.
"""
import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from collections import deque
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend for testing
import matplotlib.pyplot as plt

from src.visualizations.stream_plot import StreamPlot
from src.visualizations.orientation_plot import OrientationPlot3D


class TestStreamPlotInit:
    """Test StreamPlot initialization."""
    
    def create_mock_streamer(self, maxlen=100):
        """Create a mock streamer with data deques."""
        streamer = Mock()
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
        return streamer
    
    def test_init_accelerometer_plot(self):
        """Test initialization with accelerometer type."""
        streamer = self.create_mock_streamer()
        plot = StreamPlot(streamer, type="acc")
        
        assert plot.streamer == streamer
        assert plot.x_data is streamer.accel_x_data
        assert plot.y_data is streamer.accel_y_data
        assert plot.z_data is streamer.accel_z_data
        assert plot.fig is not None
        assert plot.ax is not None
        
        plt.close(plot.fig)
    
    def test_init_gyroscope_plot(self):
        """Test initialization with gyroscope type."""
        streamer = self.create_mock_streamer()
        plot = StreamPlot(streamer, type="gyr")
        
        assert plot.x_data is streamer.gyr_x_data
        assert plot.y_data is streamer.gyr_y_data
        assert plot.z_data is streamer.gyr_z_data
        
        plt.close(plot.fig)
    
    def test_init_magnetometer_plot(self):
        """Test initialization with magnetometer type."""
        streamer = self.create_mock_streamer()
        plot = StreamPlot(streamer, type="mag")
        
        assert plot.x_data is streamer.mag_x_data
        assert plot.y_data is streamer.mag_y_data
        assert plot.z_data is streamer.mag_z_data
        
        plt.close(plot.fig)
    
    def test_init_invalid_type_raises_error(self):
        """Test that invalid type raises ValueError."""
        streamer = self.create_mock_streamer()
        
        with pytest.raises(ValueError, match="Invalid type"):
            plot = StreamPlot(streamer, type="invalid")
    
    def test_plot_lines_created(self):
        """Test that plot lines are created."""
        streamer = self.create_mock_streamer()
        plot = StreamPlot(streamer, type="acc")
        
        assert plot.line_x is not None
        assert plot.line_y is not None
        assert plot.line_z is not None
        
        plt.close(plot.fig)
    
    def test_text_labels_created(self):
        """Test that text labels are created."""
        streamer = self.create_mock_streamer()
        plot = StreamPlot(streamer, type="acc")
        
        assert plot.text_x is not None
        assert plot.text_y is not None
        assert plot.text_z is not None
        
        plt.close(plot.fig)
    
    def test_axis_labels_set(self):
        """Test that axis labels are set correctly."""
        streamer = self.create_mock_streamer()
        plot = StreamPlot(streamer, type="acc")
        
        assert plot.ax.get_xlabel() == 'Time (s)'
        assert 'Acceleration' in plot.ax.get_ylabel()
        
        plt.close(plot.fig)
    
    def test_axis_limits_set(self):
        """Test that axis limits are set."""
        streamer = self.create_mock_streamer()
        plot = StreamPlot(streamer, type="acc")
        
        xlim = plot.ax.get_xlim()
        ylim = plot.ax.get_ylim()
        
        assert xlim[0] == 0
        assert xlim[1] == 10
        assert ylim[0] == -20
        assert ylim[1] == 20
        
        plt.close(plot.fig)


class TestStreamPlotUpdate:
    """Test StreamPlot update method."""
    
    def create_mock_streamer_with_data(self):
        """Create mock streamer with sample data."""
        streamer = Mock()
        streamer.time_data = deque([0, 0.01, 0.02, 0.03], maxlen=100)
        streamer.accel_x_data = deque([1.0, 1.5, 2.0, 2.5], maxlen=100)
        streamer.accel_y_data = deque([2.0, 2.5, 3.0, 3.5], maxlen=100)
        streamer.accel_z_data = deque([3.0, 3.5, 4.0, 4.5], maxlen=100)
        streamer.gyr_x_data = deque([0.1, 0.2, 0.3, 0.4], maxlen=100)
        streamer.gyr_y_data = deque([0.2, 0.3, 0.4, 0.5], maxlen=100)
        streamer.gyr_z_data = deque([0.3, 0.4, 0.5, 0.6], maxlen=100)
        streamer.mag_x_data = deque([100, 110, 120, 130], maxlen=100)
        streamer.mag_y_data = deque([200, 210, 220, 230], maxlen=100)
        streamer.mag_z_data = deque([300, 310, 320, 330], maxlen=100)
        return streamer
    
    def test_update_with_data(self):
        """Test update method with data."""
        streamer = self.create_mock_streamer_with_data()
        plot = StreamPlot(streamer, type="acc")
        
        result = plot.update(frame=0)
        
        # Should return line and text objects
        assert len(result) == 6  # 3 lines + 3 texts
        
        # Check that line data was set
        x_data, y_data = plot.line_x.get_data()
        assert len(x_data) > 0
        assert len(y_data) > 0
        
        plt.close(plot.fig)
    
    def test_update_empty_data(self):
        """Test update with empty data."""
        streamer = Mock()
        streamer.time_data = deque(maxlen=100)
        streamer.accel_x_data = deque(maxlen=100)
        streamer.accel_y_data = deque(maxlen=100)
        streamer.accel_z_data = deque(maxlen=100)
        streamer.gyr_x_data = deque(maxlen=100)
        streamer.gyr_y_data = deque(maxlen=100)
        streamer.gyr_z_data = deque(maxlen=100)
        streamer.mag_x_data = deque(maxlen=100)
        streamer.mag_y_data = deque(maxlen=100)
        streamer.mag_z_data = deque(maxlen=100)
        
        plot = StreamPlot(streamer, type="acc")
        result = plot.update(frame=0)
        
        # Should still return objects even with empty data
        assert result is not None
        
        plt.close(plot.fig)
    
    def test_update_adjusts_xlim(self):
        """Test that update adjusts x-axis limits for scrolling."""
        streamer = self.create_mock_streamer_with_data()
        # Add more data to trigger scrolling
        for i in range(100):
            streamer.time_data.append(15 + i*0.01)
            streamer.accel_x_data.append(1.0)
            streamer.accel_y_data.append(2.0)
            streamer.accel_z_data.append(3.0)
        
        plot = StreamPlot(streamer, type="acc")
        plot.update(frame=0)
        
        xlim = plot.ax.get_xlim()
        # Should adjust to show last 10 seconds
        assert xlim[1] > 15
        
        plt.close(plot.fig)
    
    def test_text_position_updated(self):
        """Test that text positions are updated."""
        streamer = self.create_mock_streamer_with_data()
        plot = StreamPlot(streamer, type="acc")
        
        plot.update(frame=0)
        
        # Text should be positioned at last data point
        x_pos, y_pos = plot.text_x.get_position()
        assert x_pos == streamer.time_data[-1]
        assert abs(y_pos - streamer.accel_x_data[-1]) < 0.01
        
        plt.close(plot.fig)


class TestOrientationPlot3DInit:
    """Test OrientationPlot3D initialization."""
    
    def create_mock_streamer_with_quaternions(self):
        """Create mock streamer with quaternion data."""
        streamer = Mock()
        # Identity quaternion
        streamer.quat_w_data = deque([1.0], maxlen=100)
        streamer.quat_x_data = deque([0.0], maxlen=100)
        streamer.quat_y_data = deque([0.0], maxlen=100)
        streamer.quat_z_data = deque([0.0], maxlen=100)
        return streamer
    
    def test_init_creates_3d_plot(self):
        """Test that 3D plot is created."""
        streamer = self.create_mock_streamer_with_quaternions()
        plot = OrientationPlot3D(streamer)
        
        assert plot.fig is not None
        assert plot.ax is not None
        assert hasattr(plot.ax, 'plot3D')  # Check it's a 3D axis
        
        plt.close(plot.fig)
    
    def test_init_creates_axes_arrows(self):
        """Test that coordinate axes arrows are created."""
        streamer = self.create_mock_streamer_with_quaternions()
        plot = OrientationPlot3D(streamer)
        
        assert plot.x_axis is not None
        assert plot.y_axis is not None
        assert plot.z_axis is not None
        
        plt.close(plot.fig)
    
    def test_init_sets_axis_limits(self):
        """Test that axis limits are set."""
        streamer = self.create_mock_streamer_with_quaternions()
        plot = OrientationPlot3D(streamer)
        
        xlim = plot.ax.get_xlim()
        ylim = plot.ax.get_ylim()
        zlim = plot.ax.get_zlim()
        
        assert xlim == (-1, 1)
        assert ylim == (-1, 1)
        assert zlim == (-1, 1)
        
        plt.close(plot.fig)
    
    def test_quaternion_data_references(self):
        """Test that quaternion data is correctly referenced."""
        streamer = self.create_mock_streamer_with_quaternions()
        plot = OrientationPlot3D(streamer)
        
        assert plot.quat_w is streamer.quat_w_data
        assert plot.quat_x is streamer.quat_x_data
        assert plot.quat_y is streamer.quat_y_data
        assert plot.quat_z is streamer.quat_z_data
        
        plt.close(plot.fig)


class TestOrientationPlot3DUpdate:
    """Test OrientationPlot3D update method."""
    
    def create_mock_streamer_with_quaternions(self, w=1.0, x=0.0, y=0.0, z=0.0):
        """Create mock streamer with quaternion data."""
        streamer = Mock()
        streamer.quat_w_data = deque([w], maxlen=100)
        streamer.quat_x_data = deque([x], maxlen=100)
        streamer.quat_y_data = deque([y], maxlen=100)
        streamer.quat_z_data = deque([z], maxlen=100)
        return streamer
    
    def test_update_identity_quaternion(self):
        """Test update with identity quaternion."""
        streamer = self.create_mock_streamer_with_quaternions(1.0, 0.0, 0.0, 0.0)
        plot = OrientationPlot3D(streamer)
        
        result = plot.update(frame=0)
        
        # Should return the three axis objects
        assert len(result) == 3
        
        plt.close(plot.fig)
    
    def test_update_rotated_quaternion(self):
        """Test update with rotated quaternion."""
        # 90 degree rotation about Z axis
        angle = np.pi / 4  # Half angle for quaternion
        streamer = self.create_mock_streamer_with_quaternions(
            w=np.cos(angle),
            x=0.0,
            y=0.0,
            z=np.sin(angle)
        )
        
        plot = OrientationPlot3D(streamer)
        result = plot.update(frame=0)
        
        assert result is not None
        
        plt.close(plot.fig)
    
    def test_update_empty_quaternion_data(self):
        """Test update with empty quaternion data."""
        streamer = Mock()
        streamer.quat_w_data = deque(maxlen=100)
        streamer.quat_x_data = deque(maxlen=100)
        streamer.quat_y_data = deque(maxlen=100)
        streamer.quat_z_data = deque(maxlen=100)
        
        plot = OrientationPlot3D(streamer)
        result = plot.update(frame=0)
        
        # Should handle empty data gracefully
        assert result is not None
        
        plt.close(plot.fig)
    
    def test_update_removes_old_arrows(self):
        """Test that old arrows are removed before drawing new ones."""
        streamer = self.create_mock_streamer_with_quaternions(1.0, 0.0, 0.0, 0.0)
        plot = OrientationPlot3D(streamer)
        
        # First update
        plot.update(frame=0)
        initial_collections = len(plot.ax.collections)
        
        # Second update should not keep accumulating arrows
        plot.update(frame=1)
        final_collections = len(plot.ax.collections)
        
        # Should have same or fewer collections (old ones removed)
        assert final_collections <= initial_collections + 3  # 3 new arrows
        
        plt.close(plot.fig)
    
    def test_multiple_quaternions_in_buffer(self):
        """Test with multiple quaternion values."""
        streamer = Mock()
        streamer.quat_w_data = deque([1.0, 0.9, 0.8], maxlen=100)
        streamer.quat_x_data = deque([0.0, 0.1, 0.2], maxlen=100)
        streamer.quat_y_data = deque([0.0, 0.2, 0.3], maxlen=100)
        streamer.quat_z_data = deque([0.0, 0.3, 0.4], maxlen=100)
        
        plot = OrientationPlot3D(streamer)
        result = plot.update(frame=0)
        
        # Should use the last quaternion
        assert result is not None
        
        plt.close(plot.fig)


class TestPlotIntegration:
    """Integration tests for plot classes."""
    
    def test_stream_plot_types_compatibility(self):
        """Test all stream plot types work with same streamer."""
        streamer = Mock()
        streamer.time_data = deque([0, 1, 2], maxlen=100)
        streamer.accel_x_data = deque([1.0, 2.0, 3.0], maxlen=100)
        streamer.accel_y_data = deque([2.0, 3.0, 4.0], maxlen=100)
        streamer.accel_z_data = deque([3.0, 4.0, 5.0], maxlen=100)
        streamer.gyr_x_data = deque([0.1, 0.2, 0.3], maxlen=100)
        streamer.gyr_y_data = deque([0.2, 0.3, 0.4], maxlen=100)
        streamer.gyr_z_data = deque([0.3, 0.4, 0.5], maxlen=100)
        streamer.mag_x_data = deque([100, 110, 120], maxlen=100)
        streamer.mag_y_data = deque([200, 210, 220], maxlen=100)
        streamer.mag_z_data = deque([300, 310, 320], maxlen=100)
        
        # All plot types should work
        plot_acc = StreamPlot(streamer, type="acc")
        plot_gyr = StreamPlot(streamer, type="gyr")
        plot_mag = StreamPlot(streamer, type="mag")
        
        # All should update successfully
        plot_acc.update(0)
        plot_gyr.update(0)
        plot_mag.update(0)
        
        plt.close('all')
    
    def test_plots_can_be_created_simultaneously(self):
        """Test that multiple plots can exist at the same time."""
        streamer_acc = Mock()
        streamer_acc.time_data = deque(maxlen=100)
        streamer_acc.accel_x_data = deque(maxlen=100)
        streamer_acc.accel_y_data = deque(maxlen=100)
        streamer_acc.accel_z_data = deque(maxlen=100)
        streamer_acc.gyr_x_data = deque(maxlen=100)
        streamer_acc.gyr_y_data = deque(maxlen=100)
        streamer_acc.gyr_z_data = deque(maxlen=100)
        streamer_acc.mag_x_data = deque(maxlen=100)
        streamer_acc.mag_y_data = deque(maxlen=100)
        streamer_acc.mag_z_data = deque(maxlen=100)
        
        streamer_ori = Mock()
        streamer_ori.quat_w_data = deque([1.0], maxlen=100)
        streamer_ori.quat_x_data = deque([0.0], maxlen=100)
        streamer_ori.quat_y_data = deque([0.0], maxlen=100)
        streamer_ori.quat_z_data = deque([0.0], maxlen=100)
        
        plot1 = StreamPlot(streamer_acc, type="acc")
        plot2 = OrientationPlot3D(streamer_ori)
        
        assert plot1 is not None
        assert plot2 is not None
        assert plot1.fig != plot2.fig  # Different figures
        
        plt.close('all')
