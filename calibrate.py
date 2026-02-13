"""
Magnetometer calibration script for IMU sensor.

Usage:
    python calibrate.py
    
Debug Mode:
    set CALIBRATE_DEBUG=1
    python calibrate.py
    
    This will print detailed statistics showing:
    - Total samples collected vs. samples displayed
    - Downsampling behavior for visualization
    - Confirms ALL data is saved for calibration

Instructions:
    1. Run this script
    2. When prompted, slowly rotate the sensor in all directions (figure-8 patterns work well)
    3. Try to cover all possible orientations
    4. Press Ctrl+C when you have enough data (at least 30 seconds recommended)
    5. Calibration parameters will be saved to mag_calibration.json

IMPORTANT - Data Collection vs. Visualization:
    - ALL magnetometer samples are stored in memory (no windowing or maxlen)
    - Visualization may show downsampled data (max 500 points) to prevent crashes
    - Coverage calculation and calibration use ALL collected samples
    - The downsampling is ONLY for the 3D plot display
"""
import asyncio
from bleak import BleakClient
import numpy as np
import struct
from datetime import datetime
from src.config import *
from src.mag_calibration import (MagnetometerCalibration, analyze_calibration_quality, 
                                  validate_calibration, print_validation_report)
import signal
import sys
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import threading
import time
import os


class CalibrationCollector:
    """Collects magnetometer data for calibration with real-time visualization."""
    
    def __init__(self, enable_visualization=True, max_plot_points=500, debug_plotting=False):
        self.mag_data = []  # IMPORTANT: Regular list - stores ALL samples, no windowing!
        self.is_collecting = True
        self.start_time = None
        self.enable_visualization = enable_visualization
        self.max_plot_points = max_plot_points  # Limit DISPLAYED points for performance
        self.debug_plotting = debug_plotting  # If True, prints plotting stats
        self.viz_thread = None
        self.fig = None
        self.ax = None
        self.scatter = None
        self.scatter_outliers = None  # Separate scatter for outlier visualization
        self.sphere_surface = None
        self.text_annotations = []
        self.lock = threading.Lock()
        
        # Environmental monitoring
        self.field_magnitudes = []
        self.disturbance_warnings = 0
        self.last_warning_time = None
    
    def notification_handler(self, sender, data):
        """Handle incoming BLE data and extract magnetometer readings."""
        if not self.is_collecting:
            return
        
        if self.start_time is None:
            self.start_time = datetime.now()
        
        if len(data) >= 2:
            # Extract raw sensor data
            if len(data) == PACKET_LENGTH:
                raw_data = data[2:data[1]-2]
                if len(raw_data) == RAW_DATA_LENGTH:
                    current_byte = 0
                    for imu_index in range(3):
                        values = struct.unpack('<hhhhhhhhh', raw_data[current_byte:current_byte+18])
                        current_byte += 20
                        
                        if imu_index == 0:  # Using first IMU
                            # Extract magnetometer values (indices 6, 7, 8)
                            mag_x, mag_y, mag_z = values[6], values[7], values[8]
                            
                            # Convert to nT
                            mag_x_nt = mag_x * MAG_SENSITIVITY
                            mag_y_nt = mag_y * MAG_SENSITIVITY
                            mag_z_nt = mag_z * MAG_SENSITIVITY
                            
                            with self.lock:
                                self.mag_data.append([mag_x_nt, mag_y_nt, mag_z_nt])  # ALL samples saved!
                                
                                # Environmental monitoring
                                field_mag = np.sqrt(mag_x_nt**2 + mag_y_nt**2 + mag_z_nt**2)
                                self.field_magnitudes.append(field_mag)
                                
                                # Check for disturbances (sudden large changes)
                                if len(self.field_magnitudes) > 20:
                                    recent_mags = self.field_magnitudes[-20:]
                                    variability = np.std(recent_mags) / np.mean(recent_mags) * 100
                                    
                                    # Warn if variability is high (> 15%) and enough time since last warning
                                    current_time = time.time()
                                    if variability > 15 and (self.last_warning_time is None or 
                                                            current_time - self.last_warning_time > 5):
                                        self.disturbance_warnings += 1
                                        self.last_warning_time = current_time
                                        print(f"\n⚠ WARNING: High magnetic field variability ({variability:.1f}%)")
                                        print("  Possible magnetic interference detected!")
                                        print("  Consider moving away from metal objects or electronics\n")
                            
                            # Print progress every 50 samples
                            if len(self.mag_data) % 50 == 0:
                                elapsed = (datetime.now() - self.start_time).total_seconds()
                                coverage = self._estimate_coverage()
                                print(f"Collected {len(self.mag_data)} samples ({elapsed:.1f}s) - "
                                      f"Coverage: {coverage:.1f}% - "
                                      f"Latest: [{mag_x_nt:.1f}, {mag_y_nt:.1f}, {mag_z_nt:.1f}] nT")
    
    def stop_collection(self):
        """Stop data collection and visualization."""
        self.is_collecting = False
        if self.fig:
            plt.ioff()
            plt.close(self.fig)
    
    def _estimate_coverage(self):
        """Estimate percentage of sphere coverage using grid-based approach."""
        if len(self.mag_data) < 10:
            return 0.0
        
        with self.lock:
            data = np.array(self.mag_data)
        
        # Normalize to unit sphere
        norms = np.linalg.norm(data, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        normalized = data / norms
        
        # Create octants (8 major directions)
        octants_covered = 0
        for x_sign in [-1, 1]:
            for y_sign in [-1, 1]:
                for z_sign in [-1, 1]:
                    # Check if any points in this octant
                    in_octant = np.all([
                        normalized[:, 0] * x_sign > 0.3,
                        normalized[:, 1] * y_sign > 0.3,
                        normalized[:, 2] * z_sign > 0.3
                    ], axis=0)
                    if np.any(in_octant):
                        octants_covered += 1
        
        # Rough coverage estimate
        return (octants_covered / 8.0) * 100
    
    def setup_visualization(self):
        """Initialize the matplotlib figure (called from main thread after BLE connection)."""
        if not self.enable_visualization:
            return
        
        print("Initializing 3D visualization...")
        plt.ion()  # Enable interactive mode
        self.fig = plt.figure(figsize=(12, 10))
        self.ax = self.fig.add_subplot(111, projection='3d')
        
        # Set FIXED axis limits (±80000 nT) - no dynamic scaling
        plot_limit = 80000
        self.ax.set_xlim([-plot_limit, plot_limit])
        self.ax.set_ylim([-plot_limit, plot_limit])
        self.ax.set_zlim([-plot_limit, plot_limit])
        self.ax.set_xlabel('X (nT)', fontsize=10)
        self.ax.set_ylabel('Y (nT)', fontsize=10)
        self.ax.set_zlabel('Z (nT)', fontsize=10)
        self.ax.set_title('Real-Time Magnetometer Calibration\n(Rotate sensor to fill sphere)', 
                         fontsize=12, fontweight='bold')
        
        # Initialize scatter plots: inliers (colored) and outliers (gray)
        self.scatter = self.ax.scatter([], [], [], c='blue', s=15, alpha=0.7, edgecolors='none', label='Inliers')
        self.scatter_outliers = self.ax.scatter([], [], [], c='gray', s=10, alpha=0.2, edgecolors='none', label='Outliers')
        
        # Add reference sphere wireframe (Earth's field ~50000 nT)
        u = np.linspace(0, 2 * np.pi, 30)
        v = np.linspace(0, np.pi, 20)
        ref_radius = 50000  # Approximate Earth's magnetic field strength
        x_sphere = ref_radius * np.outer(np.cos(u), np.sin(v))
        y_sphere = ref_radius * np.outer(np.sin(u), np.sin(v))
        z_sphere = ref_radius * np.outer(np.ones(np.size(u)), np.cos(v))
        self.sphere_surface = self.ax.plot_wireframe(x_sphere, y_sphere, z_sphere, 
                                                      color='gray', alpha=0.2, linewidth=0.5)
        
        # Add text annotations
        self.text_annotations = [
            self.ax.text2D(0.02, 0.98, '', transform=self.ax.transAxes, 
                          fontsize=10, verticalalignment='top',
                          bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8)),
            self.ax.text2D(0.02, 0.88, '', transform=self.ax.transAxes,
                          fontsize=9, verticalalignment='top',
                          bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.7))
        ]
        
        plt.show(block=False)
        print("Visualization ready!\n")
    
    def start_visualization(self):
        """Enable visualization flag (actual updates called from main thread)."""
        # No separate thread needed - updates called from main async loop
        pass
    
    def update_plot(self):
        """Update the plot with current data (called from main thread for GUI refresh).
        
        IMPORTANT: This method downsamples data for VISUALIZATION ONLY to prevent crashes.
        - ALL collected data remains in self.mag_data
        - Coverage calculation uses ALL data
        - Calibration algorithm uses ALL data
        - Only the 3D plot display is downsampled for performance
        
        Visualization features:
        - Inliers (points within 2.5σ of mean radius) plotted with color gradient (time-based)
        - Outliers (deviations >2.5σ from mean radius) plotted in transparent gray
        - Provides immediate visual feedback on data quality and disturbances
        
        Performance optimizations:
        - Downsamples plot data when > max_plot_points (default: 500)
        - Uses larger point size for better visibility with fewer points
        - Intelligent sampling: keeps recent points + uniform sampling of older points
        """
        if not self.enable_visualization or self.fig is None:
            return
        
        # Reference for sphere updates
        u = np.linspace(0, 2 * np.pi, 30)
        v = np.linspace(0, np.pi, 20)
        
        data = None
        with self.lock:
            if len(self.mag_data) > 0:
                data = np.array(self.mag_data)  # Get ALL collected samples
            else:
                return  # No data yet
        
        try:
            # Calculate sphere center and radius from ALL data
            center = np.mean(data, axis=0)
            radii = np.linalg.norm(data - center, axis=1)
            mean_radius = np.mean(radii)
            std_radius = np.std(radii)
            
            # Classify points as inliers or outliers using statistical threshold
            # Outliers are points beyond mean ± 2.5 standard deviations
            # This is a more robust statistical approach than using % of mean
            outlier_threshold = 2.5 * std_radius
            is_inlier = np.abs(radii - mean_radius) <= outlier_threshold
            is_outlier = ~is_inlier
            
            inlier_data = data[is_inlier]
            outlier_data = data[is_outlier]
            
            if self.debug_plotting and len(data) % 50 == 0:  # Print every 50 samples
                print(f"[DEBUG] Radius stats: mean={mean_radius:.1f} nT, std={std_radius:.1f} nT, "
                      f"threshold={outlier_threshold:.1f} nT")
            
            # Downsample both inliers and outliers for plotting
            def downsample_points(points, max_points):
                if len(points) == 0:
                    return points, np.array([])
                if len(points) <= max_points:
                    return points, np.linspace(0.3, 1.0, len(points))
                
                # Keep recent + uniform sampling of older
                n_recent = min(50, len(points) // 4)
                n_old = max_points - n_recent
                step = max(1, (len(points) - n_recent) // n_old)
                old_indices = np.arange(0, len(points) - n_recent, step)[:n_old]
                recent_indices = np.arange(len(points) - n_recent, len(points))
                indices = np.concatenate([old_indices, recent_indices])
                return points[indices], np.linspace(0.3, 1.0, len(indices))
            
            # Downsample inliers (always plot these - they show calibration quality)
            plot_inliers, inlier_colors = downsample_points(inlier_data, self.max_plot_points)
            
            # Downsample outliers (plot fewer - just to show disturbances)
            max_outliers = min(100, self.max_plot_points // 5)  # Max 100 outliers shown
            plot_outliers, _ = downsample_points(outlier_data, max_outliers)
            
            if self.debug_plotting:
                print(f"[DEBUG] Total: {len(data)} | Inliers: {len(inlier_data)} (showing {len(plot_inliers)}) | "
                      f"Outliers: {len(outlier_data)} (showing {len(plot_outliers)})")
            
            # Update inlier scatter plot (colored by time)
            if len(plot_inliers) > 0:
                self.scatter._offsets3d = (plot_inliers[:, 0], plot_inliers[:, 1], plot_inliers[:, 2])
                self.scatter.set_array(inlier_colors)
                self.scatter.set_cmap('viridis')
            else:
                self.scatter._offsets3d = ([], [], [])
            
            # Update outlier scatter plot (transparent gray)
            if len(plot_outliers) > 0:
                self.scatter_outliers._offsets3d = (plot_outliers[:, 0], plot_outliers[:, 1], plot_outliers[:, 2])
            else:
                self.scatter_outliers._offsets3d = ([], [], [])
            
            # Update reference sphere based on data center (but keep fixed plot limits)
            if len(data) > 10:
                # Update reference sphere to match data distribution
                x_sphere = center[0] + mean_radius * np.outer(np.cos(u), np.sin(v))
                y_sphere = center[1] + mean_radius * np.outer(np.sin(u), np.sin(v))
                z_sphere = center[2] + mean_radius * np.outer(np.ones(np.size(u)), np.cos(v))
                
                if self.sphere_surface:
                    self.sphere_surface.remove()
                self.sphere_surface = self.ax.plot_wireframe(x_sphere, y_sphere, z_sphere,
                                                            color='green', alpha=0.2, 
                                                            linewidth=0.5)
            
            # Update text annotations
            # IMPORTANT: coverage uses ALL data, not just plotted points
            coverage = self._estimate_coverage()  # Uses ALL self.mag_data
            n_samples = len(data)  # Total samples collected
            n_inliers = len(inlier_data)
            n_outliers = len(outlier_data)
            outlier_pct = (n_outliers / n_samples * 100) if n_samples > 0 else 0
            
            status_text = f"Samples: {n_samples}"
            status_text += f"\nInliers: {n_inliers} | Outliers: {n_outliers} ({outlier_pct:.1f}%)"
            status_text += f"\nCoverage: {coverage:.1f}%"
            if coverage < 50:
                status_color = 'lightcoral'
                status_text += "\n⚠ More rotation needed!"
            elif coverage < 80:
                status_color = 'lightyellow'
                status_text += "\n△ Good, keep rotating"
            else:
                status_color = 'lightgreen'
                status_text += "\n✓ Excellent coverage!"
            
            # Add outlier warning to status
            if outlier_pct > 10:
                status_text += "\n⚠ High outlier rate!"
                status_color = 'lightcoral'
            
            self.text_annotations[0].set_text(status_text)
            self.text_annotations[0].set_bbox(dict(boxstyle='round', 
                                                  facecolor=status_color, alpha=0.8))
            
            # Field strength info
            if len(self.field_magnitudes) > 0:
                mean_field = np.mean(self.field_magnitudes)
                std_field = np.std(self.field_magnitudes)
                variability = (std_field / mean_field * 100) if mean_field > 0 else 0
                
                field_text = f"Field: {mean_field:.0f} ± {std_field:.0f} nT\n"
                field_text += f"Var: {variability:.1f}%"
                
                if self.disturbance_warnings > 0:
                    field_text += f"\n⚠ {self.disturbance_warnings} disturbance(s)"
                    field_color = 'lightcoral'
                elif variability > 10:
                    field_color = 'lightyellow'
                else:
                    field_color = 'lightgreen'
                
                self.text_annotations[1].set_text(field_text)
                self.text_annotations[1].set_bbox(dict(boxstyle='round',
                                                      facecolor=field_color, alpha=0.7))
            
            # Flush canvas updates (but don't pause - that's done in main thread)
            self.fig.canvas.draw_idle()
            
        except Exception as e:
            print(f"Visualization update error: {e}")


async def collect_calibration_data(device_address, characteristic_uuid, enable_viz=True, debug_plotting=False):
    """Connect to device and collect magnetometer data with real-time visualization.
    
    Args:
        device_address: BLE device address
        characteristic_uuid: BLE characteristic UUID for IMU data
        enable_viz: Enable real-time 3D visualization
        debug_plotting: Print detailed plotting statistics (set CALIBRATE_DEBUG=1 to enable)
    """
    # Check environment variable for debug mode
    if os.environ.get('CALIBRATE_DEBUG', '0') == '1':
        debug_plotting = True
        print("[DEBUG MODE ENABLED - Detailed plotting stats will be shown]\n")
    
    collector = CalibrationCollector(enable_visualization=enable_viz, debug_plotting=debug_plotting)
    
    # Set up signal handler for graceful exit
    def signal_handler(sig, frame):
        print("\n\nStopping data collection...")
        collector.stop_collection()
    
    signal.signal(signal.SIGINT, signal_handler)
    
    print(f"Connecting to device {device_address}...")
    
    async with BleakClient(device_address) as client:
        if not client.is_connected:
            print("Failed to connect to device")
            return None
        
        print("Connected successfully!")
        print("\n" + "="*70)
        print("CALIBRATION INSTRUCTIONS")
        print("="*70)
        print("1. Slowly rotate the sensor in ALL directions")
        print("2. Make figure-8 patterns in different orientations")
        print("3. Watch the 3D visualization to ensure good coverage")
        print("4. Aim for >80% coverage (all octants filled)")
        print("5. Continue for at least 30-60 seconds")
        print("6. Press Ctrl+C when coverage is complete")
        print("="*70 + "\n")
        
        # Now that BLE is connected, setup visualization (avoids GUI/asyncio conflict)
        if enable_viz:
            collector.setup_visualization()
            collector.start_visualization()
        
        await client.start_notify(characteristic_uuid, collector.notification_handler)
        
        # Collect data until user stops
        # Also pump matplotlib GUI events in main thread for real-time visualization
        try:
            update_counter = 0
            while collector.is_collecting:
                await asyncio.sleep(0.05)  # 20Hz async loop
                
                # Update visualization every ~200ms (5Hz) from main thread
                if enable_viz and update_counter % 4 == 0:
                    collector.update_plot()
                    plt.pause(0.001)  # Pump GUI events in main thread
                
                update_counter += 1
        except KeyboardInterrupt:
            pass
        
        await client.stop_notify(characteristic_uuid)
        
        # Stop visualization and print summary
        collector.stop_collection()
        
        # Verification: Confirm all data was collected
        print(f"\n✓ Verification: {len(collector.mag_data)} total samples collected")
        print(f"  (Visualization showed up to {collector.max_plot_points} at a time for performance)")
        print(f"\nData collection complete! Collected {len(collector.mag_data)} samples")
        
        # Environmental summary
        if len(collector.field_magnitudes) > 0:
            mean_field = np.mean(collector.field_magnitudes)
            std_field = np.std(collector.field_magnitudes)
            variability = (std_field / mean_field * 100) if mean_field > 0 else 0
            
            print(f"\nEnvironmental Assessment:")
            print(f"  Mean Field Strength: {mean_field:.1f} nT")
            print(f"  Field Variability: {variability:.1f}%")
            print(f"  Disturbance Warnings: {collector.disturbance_warnings}")
            
            if variability > 15:
                print("  ⚠ WARNING: High variability detected - calibration may be affected")
                print("     Consider recalibrating in a magnetically cleaner environment")
            elif variability > 10:
                print("  △ CAUTION: Moderate variability - calibration should work but not ideal")
            else:
                print("  ✓ Good environment - low magnetic interference")
        
        return np.array(collector.mag_data)


def main():
    """Main calibration routine."""
    print("\n" + "="*70)
    print("MAGNETOMETER CALIBRATION")
    print("="*70 + "\n")
    
    # Ask about real-time visualization
    print("Enable real-time 3D visualization during data collection?")
    print("  (Helps ensure good coverage, but may impact performance)")
    viz_choice = input("Enable visualization? (y/n) [default: y]: ").strip().lower()
    enable_viz = viz_choice != 'n' and viz_choice != 'no'
    
    if enable_viz:
        print("\n✓ Real-time visualization enabled")
    else:
        print("\n✗ Visualization disabled (text-only mode)")
    
    print()
    
    # Ask user for calibration method
    print("Choose calibration method:")
    print("1. Full 3x3 Soft Iron Matrix with Regularization (recommended)")
    print("2. Diagonal-only Soft Iron Matrix (faster, simpler)")
    
    while True:
        choice = input("\nEnter choice (1 or 2) [default: 1]: ").strip()
        if choice == '' or choice == '1':
            use_full_soft_iron = True
            print("Using regularized full 3x3 soft iron matrix calibration\n")
            
            # Ask about regularization strength
            print("Regularization strength (0.001-0.1, default: 0.01):")
            print("  Lower = better fit to data, may overfit")
            print("  Higher = more physically plausible, may underfit")
            reg_input = input("Enter value [default: 0.01]: ").strip()
            
            try:
                reg_weight = float(reg_input) if reg_input else 0.01
                reg_weight = max(0.001, min(0.1, reg_weight))  # Clamp to reasonable range
                print(f"Using regularization weight: {reg_weight}\n")
            except ValueError:
                reg_weight = 0.01
                print("Invalid input, using default: 0.01\n")
            break
        elif choice == '2':
            use_full_soft_iron = False
            reg_weight = 0.01  # Not used for diagonal
            print("Using diagonal-only soft iron matrix calibration\n")
            break
        else:
            print("Invalid choice. Please enter 1 or 2.")
    
    # Collect data from sensor
    mag_data = asyncio.run(collect_calibration_data(DEVICE_ADDRESS, CHARACTERISTIC_UUID))
    
    if mag_data is None or len(mag_data) < 100:
        print("Error: Not enough data collected for calibration")
        print("Please try again and collect more data points")
        return 1
    
    print(f"\nProcessing {len(mag_data)} data points...")    
    # Perform calibration
    calibration = MagnetometerCalibration(
        use_full_soft_iron=use_full_soft_iron,
        regularization_weight=reg_weight
    )
    
    try:
        params = calibration.calibrate(mag_data)
        
        print("\n" + "="*70)
        print("CALIBRATION RESULTS")
        print("="*70)
        print(f"Calibration Type: {params['calibration_type']}")
        print(f"Hard Iron Offset (nT): {params['hard_iron_offset']}")
        print(f"Soft Iron Matrix:\n{np.array(params['soft_iron_matrix'])}")
        print(f"Expected Field Strength: {params['expected_field_strength']:.1f} nT")
        print(f"Standard Deviation: {params['std_deviation']:.1f} nT")
        print(f"Samples Used: {params['num_samples']}")
        
        # Print matrix quality metrics if available
        if 'matrix_quality' in params:
            mq = params['matrix_quality']
            print(f"\nSoft Iron Matrix Quality:")
            print(f"  Determinant: {mq['determinant']:.4f}")
            print(f"  Condition Number: {mq['condition_number']:.2f}")
            print(f"  Orthogonality Error: {mq['orthogonality_error']:.4f}")
            print(f"  Off-Diagonal Ratio: {mq['off_diagonal_ratio']:.4f}")
            print(f"  Well-Conditioned: {'✓' if mq['is_well_conditioned'] else '✗'}")
            print(f"  Nearly Orthogonal: {'✓' if mq['is_nearly_orthogonal'] else '✗'}")
        
        # Analyze quality
        quality = analyze_calibration_quality(mag_data, calibration)
        print(f"\nBasic Quality Metrics:")
        print(f"  Variability: {quality['variability_percent']:.2f}%")
        print(f"  Ellipticity: {quality['ellipticity']:.4f}")
        print(f"  Residual Bias: {quality['residual_bias']:.2f} nT ({quality['residual_bias_percent']:.2f}%)")
        print(f"  Field Range: {quality['min_field']:.1f} - {quality['max_field']:.1f} nT")
        
        # Perform validation with visualization
        print("\n" + "="*70)
        print("VALIDATION")
        print("="*70)
        print("Generating validation plots...")
        
        validation_results = validate_calibration(
            mag_data, 
            calibration, 
            show_plot=True,
            save_plot='calibration_validation.png'
        )
        
        # Print validation report
        print_validation_report(validation_results)
        
        # Save calibration if validation passed
        if validation_results['passed']:
            output_file = 'mag_calibration.json'
            calibration.save_calibration(output_file)
            
            print(f"\n{'='*70}")
            print(f"✓ Calibration saved to: {output_file}")
            print(f"{'='*70}\n")
            return 0
        else:
            print(f"\n{'='*70}")
            print("⚠ Calibration quality is below acceptable threshold")
            print("="*70)
            save_anyway = input("\nSave calibration anyway? (y/n) [default: n]: ").strip().lower()
            
            if save_anyway == 'y' or save_anyway == 'yes':
                output_file = 'mag_calibration.json'
                calibration.save_calibration(output_file)
                print(f"\nCalibration saved to: {output_file}")
                print("Note: Consider recalibrating for better results\n")
                return 0
            else:
                print("\nCalibration not saved. Please recalibrate:")
                print("  - Ensure sensor is rotated through ALL orientations")
                print("  - Perform calibration away from magnetic interference")
                print("  - Use smooth, continuous rotations")
                print("  - Collect data for at least 30-60 seconds\n")
                return 1
        
    except Exception as e:
        print(f"\nError during calibration: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
