"""
Magnetometer calibration utilities for hard iron and soft iron correction.
"""
import numpy as np
from scipy.optimize import least_squares, minimize
import json
import os
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D


class MagnetometerCalibration:
    """Class to handle magnetometer calibration operations."""
    
    def __init__(self, use_full_soft_iron=True, regularization_weight=0.01):
        self.hard_iron_offset = np.array([0.0, 0.0, 0.0])
        self.soft_iron_matrix = np.eye(3)
        self.is_calibrated = False
        self.use_full_soft_iron = use_full_soft_iron  # True for full 3x3, False for diagonal only
        self.regularization_weight = regularization_weight  # Weight for regularization terms
    
    def calibrate(self, mag_data):
        """
        Perform magnetometer calibration using ellipsoid fitting.
        
        Args:
            mag_data: numpy array of shape (N, 3) containing raw magnetometer readings
        
        Returns:
            dict: Calibration parameters (hard_iron_offset, soft_iron_matrix)
        """
        if len(mag_data) < 100:
            raise ValueError("Need at least 100 data points for calibration")
        
        if self.use_full_soft_iron:
            return self._calibrate_full_soft_iron(mag_data)
        else:
            return self._calibrate_diagonal_only(mag_data)
    
    def _calibrate_diagonal_only(self, mag_data):
        """Calibrate using diagonal-only soft iron matrix (original method)."""
        # Initial guess: center of the data cloud
        center = np.mean(mag_data, axis=0)
        
        # Estimate expected field strength from data range
        data_range = np.ptp(mag_data, axis=0)
        expected_field = np.mean(data_range) / 2
        
        # Initial parameters: [center_x, center_y, center_z, scale_x, scale_y, scale_z]
        initial_params = np.concatenate([center, [1.0, 1.0, 1.0]])
        
        # Optimize to fit ellipsoid
        result = least_squares(
            self._ellipsoid_residuals_diagonal,
            initial_params,
            args=(mag_data, expected_field),
            method='lm'
        )
        
        # Extract calibration parameters
        self.hard_iron_offset = result.x[:3]
        scales = result.x[3:6]
        self.soft_iron_matrix = np.diag(scales)
        self.is_calibrated = True
        
        # Calculate quality metrics
        corrected_data = self.apply_calibration(mag_data)
        field_magnitudes = np.linalg.norm(corrected_data, axis=1)
        expected_mag = np.mean(field_magnitudes)
        std_deviation = np.std(field_magnitudes)
        
        calibration_params = {
            'hard_iron_offset': self.hard_iron_offset.tolist(),
            'soft_iron_matrix': self.soft_iron_matrix.tolist(),
            'expected_field_strength': float(expected_mag),
            'std_deviation': float(std_deviation),
            'num_samples': len(mag_data),
            'calibration_type': 'diagonal',
            'matrix_quality': self._evaluate_matrix_quality(self.soft_iron_matrix)
        }
        
        return calibration_params
    
    def _calibrate_full_soft_iron(self, mag_data):
        """Calibrate using full 3x3 soft iron matrix with regularization for better accuracy."""
        # Initial guess: center of the data cloud
        center = np.mean(mag_data, axis=0)
        
        # Estimate expected field strength
        centered = mag_data - center
        radii = np.linalg.norm(centered, axis=1)
        expected_field = np.median(radii)
        
        # Initial parameters: [center(3), matrix_elements(9)]
        # We directly parameterize the soft iron matrix elements for better control
        # Start with identity matrix (no distortion)
        A_init = np.eye(3)
        A_flat = A_init.flatten()
        
        initial_params = np.concatenate([center, A_flat])
        
        # Optimize using minimize with regularization
        result = minimize(
            self._ellipsoid_cost_full_regularized,
            initial_params,
            args=(mag_data, expected_field),
            method='L-BFGS-B',
            options={'maxiter': 1000, 'ftol': 1e-9}
        )
        
        # Extract calibration parameters
        self.hard_iron_offset = result.x[:3]
        
        # Reconstruct the soft iron matrix from flattened parameters
        A = result.x[3:].reshape(3, 3)
        
        # The optimization directly produces the correction matrix
        self.soft_iron_matrix = A
        self.is_calibrated = True
        
        # Calculate quality metrics
        corrected_data = self.apply_calibration(mag_data)
        field_magnitudes = np.linalg.norm(corrected_data, axis=1)
        expected_mag = np.mean(field_magnitudes)
        std_deviation = np.std(field_magnitudes)
        
        calibration_params = {
            'hard_iron_offset': self.hard_iron_offset.tolist(),
            'soft_iron_matrix': self.soft_iron_matrix.tolist(),
            'expected_field_strength': float(expected_mag),
            'std_deviation': float(std_deviation),
            'num_samples': len(mag_data),
            'calibration_type': 'full_3x3',
            'matrix_quality': self._evaluate_matrix_quality(self.soft_iron_matrix)
        }
        
        return calibration_params
    
    def _evaluate_matrix_quality(self, A):
        """Evaluate physical plausibility of soft iron matrix."""
        # Check orthogonality
        ATA = A.T @ A
        scale = np.trace(ATA) / 3
        ortho_error = np.linalg.norm(ATA - scale * np.eye(3), 'fro')
        
        # Check determinant
        det = np.linalg.det(A)
        
        # Check condition number (should be close to 1 for well-conditioned)
        cond = np.linalg.cond(A)
        
        # Off-diagonal magnitude
        diagonal = np.diag(np.diag(A))
        off_diag_norm = np.linalg.norm(A - diagonal, 'fro')
        diag_norm = np.linalg.norm(diagonal, 'fro')
        off_diag_ratio = off_diag_norm / diag_norm if diag_norm > 0 else 0
        
        return {
            'determinant': float(det),
            'condition_number': float(cond),
            'orthogonality_error': float(ortho_error),
            'off_diagonal_ratio': float(off_diag_ratio),
            'is_well_conditioned': cond < 10,
            'is_nearly_orthogonal': ortho_error < 0.1 * scale
        }
    
    def _ellipsoid_cost_full_regularized(self, params, data, expected_field):
        """Cost function with regularization for physical plausibility."""
        center = params[:3]
        A = params[3:].reshape(3, 3)
        
        # Data fitting term: minimize deviation from spherical
        centered = data - center
        try:
            transformed = (A @ centered.T).T
        except:
            return 1e10
        
        magnitudes = np.linalg.norm(transformed, axis=1)
        data_residuals = magnitudes - expected_field
        data_cost = np.sum(data_residuals**2) / len(data)
        
        # Regularization terms for physical plausibility
        reg_weight = self.regularization_weight
        
        # 1. Orthogonality constraint: A^T @ A should be close to scaled identity
        # This ensures axes remain roughly perpendicular
        ATA = A.T @ A
        scale = np.trace(ATA) / 3  # Average scaling factor
        ortho_penalty = np.sum((ATA - scale * np.eye(3))**2)
        
        # 2. Determinant constraint: det(A) should be close to 1
        # This prevents excessive volume distortion
        try:
            det_A = np.linalg.det(A)
            if det_A <= 0:
                return 1e10  # Reject negative determinants
            det_penalty = (np.log(abs(det_A)))**2  # Penalize deviation from det=1
        except:
            return 1e10
        
        # 3. Diagonal dominance: encourage matrix to be close to diagonal
        # This reduces unnecessary complexity
        diagonal = np.diag(np.diag(A))
        off_diagonal = A - diagonal
        diag_penalty = np.sum(off_diagonal**2)
        
        # 4. Scale constraint: keep matrix elements reasonable
        # Prevent extreme scaling that might indicate numerical issues
        scale_penalty = np.sum((np.diag(A) - 1)**2)  # Encourage scales near 1
        
        # Total regularized cost
        reg_cost = (ortho_penalty * 10 +      # Strong orthogonality constraint
                   det_penalty * 5 +           # Moderate determinant constraint  
                   diag_penalty * 2 +          # Mild diagonal preference
                   scale_penalty * 1)          # Gentle scale constraint
        
        total_cost = data_cost + reg_weight * reg_cost
        
        return total_cost
    
    def _ellipsoid_residuals_diagonal(self, params, data, expected_field):
        """Calculate residuals for diagonal-only ellipsoid fitting optimization."""
        center = params[:3]
        scales = params[3:6]
        
        # Center and scale the data
        centered = data - center
        scaled = centered * scales
        
        # Calculate distance from expected field strength
        magnitudes = np.linalg.norm(scaled, axis=1)
        residuals = magnitudes - expected_field
        
        return residuals
    
    def apply_calibration(self, mag_data):
        """
        Apply calibration to raw magnetometer data.
        
        Args:
            mag_data: numpy array of shape (N, 3) or (3,) containing raw magnetometer readings
        
        Returns:
            numpy array: Calibrated magnetometer data
        """
        if not self.is_calibrated:
            return mag_data
        
        # Handle single reading (1D array)
        if mag_data.ndim == 1:
            centered = mag_data - self.hard_iron_offset
            calibrated = self.soft_iron_matrix @ centered
            return calibrated
        
        # Handle multiple readings (2D array)
        centered = mag_data - self.hard_iron_offset
        calibrated = (self.soft_iron_matrix @ centered.T).T
        return calibrated
    
    def save_calibration(self, filepath):
        """Save calibration parameters to a JSON file."""
        if not self.is_calibrated:
            raise ValueError("No calibration data to save. Run calibrate() first.")
        
        params = {
            'hard_iron_offset': self.hard_iron_offset.tolist(),
            'soft_iron_matrix': self.soft_iron_matrix.tolist(),
            'is_calibrated': self.is_calibrated
        }
        
        with open(filepath, 'w') as f:
            json.dump(params, f, indent=2)
        
        print(f"Calibration saved to {filepath}")
    
    def load_calibration(self, filepath):
        """Load calibration parameters from a JSON file."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Calibration file not found: {filepath}")
        
        with open(filepath, 'r') as f:
            params = json.load(f)
        
        self.hard_iron_offset = np.array(params['hard_iron_offset'])
        self.soft_iron_matrix = np.array(params['soft_iron_matrix'])
        self.is_calibrated = params['is_calibrated']
        
        print(f"Calibration loaded from {filepath}")
        print(f"Hard iron offset: {self.hard_iron_offset}")
        print(f"Soft iron matrix:\n{self.soft_iron_matrix}")
    
    def print_calibration_info(self):
        """Print current calibration parameters."""
        if not self.is_calibrated:
            print("No calibration loaded.")
            return
        
        print("\n=== Magnetometer Calibration ===")
        print(f"Hard Iron Offset (nT): {self.hard_iron_offset}")
        print(f"Soft Iron Matrix:\n{self.soft_iron_matrix}")
        print("================================\n")


def analyze_calibration_quality(mag_data, calibration):
    """
    Analyze the quality of magnetometer calibration.
    
    Args:
        mag_data: numpy array of raw magnetometer readings
        calibration: MagnetometerCalibration object
    
    Returns:
        dict: Quality metrics
    """
    corrected = calibration.apply_calibration(mag_data)
    magnitudes = np.linalg.norm(corrected, axis=1)
    
    # Calculate ellipticity (ratio of max to min radius)
    radii = magnitudes
    ellipticity = (np.max(radii) - np.min(radii)) / np.mean(radii)
    
    # Check for residual bias by looking at mean position
    mean_position = np.mean(corrected, axis=0)
    residual_bias = np.linalg.norm(mean_position)
    
    metrics = {
        'mean_field_strength': np.mean(magnitudes),
        'std_deviation': np.std(magnitudes),
        'min_field': np.min(magnitudes),
        'max_field': np.max(magnitudes),
        'variability_percent': (np.std(magnitudes) / np.mean(magnitudes)) * 100,
        'ellipticity': ellipticity,
        'residual_bias': residual_bias,
        'residual_bias_percent': (residual_bias / np.mean(magnitudes)) * 100
    }
    
    return metrics


def validate_calibration(mag_data, calibration, show_plot=True, save_plot=None):
    """
    Validate magnetometer calibration with visualization and statistical checks.
    
    Args:
        mag_data: numpy array of raw magnetometer readings
        calibration: MagnetometerCalibration object
        show_plot: Whether to display the validation plot
        save_plot: Optional filepath to save the plot
    
    Returns:
        dict: Validation results with pass/fail status
    """
    raw_data = mag_data.copy()
    corrected_data = calibration.apply_calibration(mag_data)
    
    # Calculate metrics
    raw_magnitudes = np.linalg.norm(raw_data, axis=1)
    corrected_magnitudes = np.linalg.norm(corrected_data, axis=1)
    
    # Quality thresholds
    EXCELLENT_THRESHOLD = 5.0  # % variability
    GOOD_THRESHOLD = 10.0
    ACCEPTABLE_THRESHOLD = 15.0
    
    variability = (np.std(corrected_magnitudes) / np.mean(corrected_magnitudes)) * 100
    
    # Check for sphericity
    mean_corrected = np.mean(corrected_data, axis=0)
    residual_bias = np.linalg.norm(mean_corrected)
    residual_bias_percent = (residual_bias / np.mean(corrected_magnitudes)) * 100
    
    # Ellipticity check
    ellipticity = (np.max(corrected_magnitudes) - np.min(corrected_magnitudes)) / np.mean(corrected_magnitudes)
    
    # Determine quality level
    if variability < EXCELLENT_THRESHOLD and ellipticity < 0.1:
        quality = "EXCELLENT"
        passed = True
    elif variability < GOOD_THRESHOLD and ellipticity < 0.15:
        quality = "GOOD"
        passed = True
    elif variability < ACCEPTABLE_THRESHOLD and ellipticity < 0.25:
        quality = "ACCEPTABLE"
        passed = True
    else:
        quality = "POOR"
        passed = False
    
    validation_results = {
        'passed': passed,
        'quality': quality,
        'variability_percent': variability,
        'ellipticity': ellipticity,
        'residual_bias': residual_bias,
        'residual_bias_percent': residual_bias_percent,
        'mean_field_strength': np.mean(corrected_magnitudes),
        'field_range': (np.min(corrected_magnitudes), np.max(corrected_magnitudes))
    }
    
    # Visualization
    if show_plot or save_plot:
        fig = plt.figure(figsize=(15, 5))
        
        # Plot 1: Raw data
        ax1 = fig.add_subplot(131, projection='3d')
        ax1.scatter(raw_data[:, 0], raw_data[:, 1], raw_data[:, 2], 
                   c=raw_magnitudes, cmap='viridis', s=1, alpha=0.6)
        ax1.set_xlabel('X (nT)')
        ax1.set_ylabel('Y (nT)')
        ax1.set_zlabel('Z (nT)')
        ax1.set_title('Raw Magnetometer Data')
        ax1.set_box_aspect([1,1,1])
        
        # Plot 2: Corrected data
        ax2 = fig.add_subplot(132, projection='3d')
        ax2.scatter(corrected_data[:, 0], corrected_data[:, 1], corrected_data[:, 2],
                   c=corrected_magnitudes, cmap='viridis', s=1, alpha=0.6)
        ax2.set_xlabel('X (nT)')
        ax2.set_ylabel('Y (nT)')
        ax2.set_zlabel('Z (nT)')
        ax2.set_title(f'Calibrated Data ({quality})')
        ax2.set_box_aspect([1,1,1])
        
        # Add a reference sphere
        u = np.linspace(0, 2 * np.pi, 50)
        v = np.linspace(0, np.pi, 50)
        mean_radius = np.mean(corrected_magnitudes)
        x_sphere = mean_radius * np.outer(np.cos(u), np.sin(v))
        y_sphere = mean_radius * np.outer(np.sin(u), np.sin(v))
        z_sphere = mean_radius * np.outer(np.ones(np.size(u)), np.cos(v))
        ax2.plot_surface(x_sphere, y_sphere, z_sphere, alpha=0.1, color='gray')
        
        # Plot 3: Field magnitude distribution
        ax3 = fig.add_subplot(133)
        ax3.hist(raw_magnitudes, bins=50, alpha=0.5, label='Raw', density=True)
        ax3.hist(corrected_magnitudes, bins=50, alpha=0.5, label='Calibrated', density=True)
        ax3.axvline(np.mean(corrected_magnitudes), color='red', linestyle='--', 
                   label=f'Mean: {np.mean(corrected_magnitudes):.1f} nT')
        ax3.set_xlabel('Field Strength (nT)')
        ax3.set_ylabel('Density')
        ax3.set_title('Field Magnitude Distribution')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_plot:
            plt.savefig(save_plot, dpi=150, bbox_inches='tight')
            print(f"Validation plot saved to: {save_plot}")
        
        if show_plot:
            plt.show()
        else:
            plt.close()
    
    return validation_results


def print_validation_report(validation_results):
    """Print a formatted validation report."""
    print("\n" + "="*70)
    print("CALIBRATION VALIDATION REPORT")
    print("="*70)
    print(f"Overall Quality: {validation_results['quality']}")
    print(f"Validation Status: {'✓ PASSED' if validation_results['passed'] else '✗ FAILED'}")
    print("\nMetrics:")
    print(f"  Field Variability: {validation_results['variability_percent']:.2f}%")
    print(f"  Ellipticity: {validation_results['ellipticity']:.4f}")
    print(f"  Residual Bias: {validation_results['residual_bias']:.2f} nT ({validation_results['residual_bias_percent']:.2f}%)")
    print(f"  Mean Field Strength: {validation_results['mean_field_strength']:.1f} nT")
    print(f"  Field Range: {validation_results['field_range'][0]:.1f} - {validation_results['field_range'][1]:.1f} nT")
    
    print("\nInterpretation:")
    if validation_results['variability_percent'] < 5:
        print("  ✓ Excellent field uniformity")
    elif validation_results['variability_percent'] < 10:
        print("  ✓ Good field uniformity")
    elif validation_results['variability_percent'] < 15:
        print("  ⚠ Acceptable field uniformity")
    else:
        print("  ✗ Poor field uniformity - consider recalibrating")
    
    if validation_results['ellipticity'] < 0.1:
        print("  ✓ Excellent sphericity (minimal ellipticity)")
    elif validation_results['ellipticity'] < 0.15:
        print("  ✓ Good sphericity")
    elif validation_results['ellipticity'] < 0.25:
        print("  ⚠ Acceptable sphericity")
    else:
        print("  ✗ Poor sphericity - full 3x3 soft iron matrix recommended")
    
    if validation_results['residual_bias_percent'] < 2:
        print("  ✓ Minimal residual bias (well-centered)")
    elif validation_results['residual_bias_percent'] < 5:
        print("  ⚠ Some residual bias present")
    else:
        print("  ✗ Significant residual bias - check hard iron correction")
    
    print("="*70 + "\n")
