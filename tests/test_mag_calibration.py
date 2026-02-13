"""
Unit tests for src/mag_calibration.py module.
Tests magnetometer calibration functionality.
"""
import pytest
import numpy as np
import json
import os
import tempfile
from unittest.mock import patch, MagicMock
from src.mag_calibration import (
    MagnetometerCalibration,
    analyze_calibration_quality,
    validate_calibration,
    print_validation_report
)


class TestMagnetometerCalibrationInit:
    """Test MagnetometerCalibration initialization."""
    
    def test_default_initialization(self):
        """Test default initialization values."""
        cal = MagnetometerCalibration()
        
        assert cal.is_calibrated is False
        assert cal.use_full_soft_iron is True
        assert cal.regularization_weight == 0.01
        np.testing.assert_array_equal(cal.hard_iron_offset, np.array([0.0, 0.0, 0.0]))
        np.testing.assert_array_equal(cal.soft_iron_matrix, np.eye(3))
    
    def test_initialization_with_parameters(self):
        """Test initialization with custom parameters."""
        cal = MagnetometerCalibration(use_full_soft_iron=False, regularization_weight=0.05)
        
        assert cal.use_full_soft_iron is False
        assert cal.regularization_weight == 0.05
        assert cal.is_calibrated is False
    
    def test_hard_iron_offset_shape(self):
        """Test hard iron offset is 3D vector."""
        cal = MagnetometerCalibration()
        assert cal.hard_iron_offset.shape == (3,)
    
    def test_soft_iron_matrix_shape(self):
        """Test soft iron matrix is 3x3."""
        cal = MagnetometerCalibration()
        assert cal.soft_iron_matrix.shape == (3, 3)


class TestMagnetometerCalibration:
    """Test calibration methods."""
    
    def generate_synthetic_data(self, n_points=500, hard_iron=[10, 20, 30], 
                                soft_iron=None, field_strength=50.0, noise_level=1.0):
        """Generate synthetic magnetometer data for testing."""
        if soft_iron is None:
            soft_iron = np.eye(3)
        
        # Generate points on a sphere
        phi = np.random.uniform(0, 2*np.pi, n_points)
        theta = np.random.uniform(0, np.pi, n_points)
        
        x = field_strength * np.sin(theta) * np.cos(phi)
        y = field_strength * np.sin(theta) * np.sin(phi)
        z = field_strength * np.cos(theta)
        
        clean_data = np.column_stack([x, y, z])
        
        # Apply soft iron distortion
        distorted = (np.linalg.inv(soft_iron) @ clean_data.T).T
        
        # Apply hard iron offset
        biased = distorted + hard_iron
        
        # Add noise
        noisy = biased + np.random.normal(0, noise_level, biased.shape)
        
        return noisy
    
    def test_calibrate_requires_minimum_samples(self):
        """Test that calibration requires minimum number of samples."""
        cal = MagnetometerCalibration()
        insufficient_data = np.random.rand(50, 3)  # Less than 100 samples
        
        with pytest.raises(ValueError, match="Need at least 100 data points"):
            cal.calibrate(insufficient_data)
    
    def test_calibrate_diagonal_only(self):
        """Test diagonal-only calibration."""
        cal = MagnetometerCalibration(use_full_soft_iron=False)
        
        # Generate synthetic data with known biases
        mag_data = self.generate_synthetic_data(
            n_points=500,
            hard_iron=[100, 50, -30],
            field_strength=45000.0
        )
        
        result = cal.calibrate(mag_data)
        
        # Check calibration was performed
        assert cal.is_calibrated is True
        assert result['calibration_type'] == 'diagonal'
        
        # Check returned parameters
        assert 'hard_iron_offset' in result
        assert 'soft_iron_matrix' in result
        assert 'expected_field_strength' in result
        assert 'std_deviation' in result
        assert 'num_samples' in result
        
        # Check calibration improves data
        corrected = cal.apply_calibration(mag_data)
        magnitudes = np.linalg.norm(corrected, axis=1)
        std_dev = np.std(magnitudes)
        
        # After calibration, std should be reasonable
        assert std_dev < 5000  # Less than 10% for 50k nT field
    
    def test_calibrate_full_soft_iron(self):
        """Test full 3x3 soft iron calibration."""
        cal = MagnetometerCalibration(use_full_soft_iron=True)
        
        # Generate synthetic data with soft iron distortion
        soft_iron = np.array([
            [1.2, 0.1, 0.0],
            [0.1, 0.9, 0.0],
            [0.0, 0.0, 1.1]
        ])
        
        mag_data = self.generate_synthetic_data(
            n_points=500,
            hard_iron=[100, 50, -30],
            soft_iron=soft_iron,
            field_strength=45000.0
        )
        
        result = cal.calibrate(mag_data)
        
        # Check calibration was performed
        assert cal.is_calibrated is True
        assert result['calibration_type'] == 'full_3x3'
        
        # Check matrix quality metrics
        assert 'matrix_quality' in result
        quality = result['matrix_quality']
        assert 'determinant' in quality
        assert 'condition_number' in quality
        assert 'orthogonality_error' in quality
    
    def test_apply_calibration_single_reading(self):
        """Test applying calibration to a single reading."""
        cal = MagnetometerCalibration()
        cal.hard_iron_offset = np.array([10.0, 20.0, 30.0])
        cal.soft_iron_matrix = np.eye(3) * 2.0
        cal.is_calibrated = True
        
        raw = np.array([110.0, 120.0, 130.0])
        calibrated = cal.apply_calibration(raw)
        
        expected = (raw - cal.hard_iron_offset) * 2.0
        np.testing.assert_array_almost_equal(calibrated, expected)
    
    def test_apply_calibration_multiple_readings(self):
        """Test applying calibration to multiple readings."""
        cal = MagnetometerCalibration()
        cal.hard_iron_offset = np.array([10.0, 20.0, 30.0])
        cal.soft_iron_matrix = np.diag([1.5, 1.8, 2.0])
        cal.is_calibrated = True
        
        raw = np.array([
            [110.0, 120.0, 130.0],
            [210.0, 220.0, 230.0],
            [310.0, 320.0, 330.0]
        ])
        
        calibrated = cal.apply_calibration(raw)
        
        assert calibrated.shape == raw.shape
        # Check first reading manually
        expected_first = cal.soft_iron_matrix @ (raw[0] - cal.hard_iron_offset)
        np.testing.assert_array_almost_equal(calibrated[0], expected_first)
    
    def test_apply_calibration_without_calibration(self):
        """Test that uncalibrated returns original data."""
        cal = MagnetometerCalibration()
        assert cal.is_calibrated is False
        
        raw = np.array([100.0, 200.0, 300.0])
        calibrated = cal.apply_calibration(raw)
        
        np.testing.assert_array_equal(calibrated, raw)


class TestCalibrationSaveLoad:
    """Test saving and loading calibration."""
    
    def test_save_calibration(self):
        """Test saving calibration to file."""
        cal = MagnetometerCalibration()
        cal.hard_iron_offset = np.array([10.0, 20.0, 30.0])
        cal.soft_iron_matrix = np.array([
            [1.0, 0.1, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0]
        ])
        cal.is_calibrated = True
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            filepath = f.name
        
        try:
            cal.save_calibration(filepath)
            
            # Check file exists and contains correct data
            assert os.path.exists(filepath)
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            assert 'hard_iron_offset' in data
            assert 'soft_iron_matrix' in data
            assert 'is_calibrated' in data
            assert data['is_calibrated'] is True
            
            np.testing.assert_array_almost_equal(
                np.array(data['hard_iron_offset']),
                cal.hard_iron_offset
            )
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)
    
    def test_save_without_calibration_raises_error(self):
        """Test that saving without calibration raises error."""
        cal = MagnetometerCalibration()
        assert cal.is_calibrated is False
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            filepath = f.name
        
        try:
            with pytest.raises(ValueError, match="No calibration data to save"):
                cal.save_calibration(filepath)
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)
    
    def test_load_calibration(self):
        """Test loading calibration from file."""
        # Create calibration data
        cal_data = {
            'hard_iron_offset': [10.0, 20.0, 30.0],
            'soft_iron_matrix': [
                [1.0, 0.1, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0]
            ],
            'is_calibrated': True
        }
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(cal_data, f)
            filepath = f.name
        
        try:
            cal = MagnetometerCalibration()
            cal.load_calibration(filepath)
            
            assert cal.is_calibrated is True
            np.testing.assert_array_almost_equal(
                cal.hard_iron_offset,
                np.array([10.0, 20.0, 30.0])
            )
            np.testing.assert_array_almost_equal(
                cal.soft_iron_matrix,
                np.array([[1.0, 0.1, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
            )
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)
    
    def test_load_nonexistent_file_raises_error(self):
        """Test loading from non-existent file raises error."""
        cal = MagnetometerCalibration()
        
        with pytest.raises(FileNotFoundError):
            cal.load_calibration('nonexistent_file.json')
    
    def test_save_load_roundtrip(self):
        """Test save and load preserve calibration data."""
        cal1 = MagnetometerCalibration()
        cal1.hard_iron_offset = np.array([15.5, 25.3, 35.7])
        cal1.soft_iron_matrix = np.array([
            [1.2, 0.05, 0.02],
            [0.05, 0.9, 0.01],
            [0.02, 0.01, 1.1]
        ])
        cal1.is_calibrated = True
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            filepath = f.name
        
        try:
            cal1.save_calibration(filepath)
            
            cal2 = MagnetometerCalibration()
            cal2.load_calibration(filepath)
            
            assert cal2.is_calibrated == cal1.is_calibrated
            np.testing.assert_array_almost_equal(
                cal2.hard_iron_offset,
                cal1.hard_iron_offset
            )
            np.testing.assert_array_almost_equal(
                cal2.soft_iron_matrix,
                cal1.soft_iron_matrix
            )
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)


class TestAnalyzeCalibrationQuality:
    """Test calibration quality analysis."""
    
    def test_analyze_calibration_quality(self):
        """Test quality analysis returns expected metrics."""
        # Create synthetic calibrated data
        n_points = 500
        field_strength = 45000.0
        
        phi = np.random.uniform(0, 2*np.pi, n_points)
        theta = np.random.uniform(0, np.pi, n_points)
        
        x = field_strength * np.sin(theta) * np.cos(phi)
        y = field_strength * np.sin(theta) * np.sin(phi)
        z = field_strength * np.cos(theta)
        
        mag_data = np.column_stack([x, y, z])
        mag_data += np.random.normal(0, 500, mag_data.shape)
        
        cal = MagnetometerCalibration()
        cal.is_calibrated = True  # Pretend it's calibrated
        
        metrics = analyze_calibration_quality(mag_data, cal)
        
        assert 'mean_field_strength' in metrics
        assert 'std_deviation' in metrics
        assert 'min_field' in metrics
        assert 'max_field' in metrics
        assert 'variability_percent' in metrics
        assert 'ellipticity' in metrics
        assert 'residual_bias' in metrics
        assert 'residual_bias_percent' in metrics
        
        # Check values are reasonable
        assert metrics['mean_field_strength'] > 0
        assert metrics['std_deviation'] >= 0
        assert metrics['variability_percent'] >= 0


class TestValidateCalibration:
    """Test calibration validation."""
    
    @patch('matplotlib.pyplot.show')
    @patch('matplotlib.pyplot.close')
    def test_validate_calibration_without_plot(self, mock_close, mock_show):
        """Test validation without showing plot."""
        # Create good calibrated data
        n_points = 500
        field_strength = 45000.0
        
        phi = np.random.uniform(0, 2*np.pi, n_points)
        theta = np.random.uniform(0, np.pi, n_points)
        
        x = field_strength * np.sin(theta) * np.cos(phi)
        y = field_strength * np.sin(theta) * np.sin(phi)
        z = field_strength * np.cos(theta)
        
        mag_data = np.column_stack([x, y, z])
        mag_data += np.random.normal(0, 200, mag_data.shape)
        
        cal = MagnetometerCalibration()
        cal.is_calibrated = True
        
        results = validate_calibration(mag_data, cal, show_plot=False)
        
        assert 'passed' in results
        assert 'quality' in results
        assert 'variability_percent' in results
        assert 'ellipticity' in results
        
        assert isinstance(results['passed'], bool)
        assert results['quality'] in ['EXCELLENT', 'GOOD', 'ACCEPTABLE', 'POOR']
        
        # Should not show plot
        mock_show.assert_not_called()
    
    def test_validation_quality_levels(self):
        """Test that validation correctly identifies quality levels."""
        cal = MagnetometerCalibration()
        cal.is_calibrated = True
        
        # Generate excellent quality data
        n_points = 500
        field_strength = 45000.0
        phi = np.random.uniform(0, 2*np.pi, n_points)
        theta = np.random.uniform(0, np.pi, n_points)
        
        x = field_strength * np.sin(theta) * np.cos(phi)
        y = field_strength * np.sin(theta) * np.sin(phi)
        z = field_strength * np.cos(theta)
        
        excellent_data = np.column_stack([x, y, z])
        excellent_data += np.random.normal(0, 100, excellent_data.shape)  # Low noise
        
        results = validate_calibration(excellent_data, cal, show_plot=False)
        
        # Should pass and be good quality
        assert results['variability_percent'] < 20  # Should be low


class TestMatrixQualityEvaluation:
    """Test matrix quality evaluation."""
    
    def test_identity_matrix_quality(self):
        """Test quality metrics for identity matrix."""
        cal = MagnetometerCalibration()
        A = np.eye(3)
        quality = cal._evaluate_matrix_quality(A)
        assert quality['determinant'] == pytest.approx(1.0, abs=1e-5)
        assert quality['condition_number'] == pytest.approx(1.0, abs=1e-5)
        assert quality['orthogonality_error'] < 0.01
        assert bool(quality['is_well_conditioned']) is True
        assert bool(quality['is_nearly_orthogonal']) is True
    
    def test_diagonal_matrix_quality(self):
        """Test quality metrics for diagonal matrix."""
        cal = MagnetometerCalibration()
        A = np.diag([1.2, 0.9, 1.1])
        quality = cal._evaluate_matrix_quality(A)
        assert quality['determinant'] > 0
        assert bool(quality['is_well_conditioned']) is True
        # Diagonal matrix is orthogonal scaled, so should have low error
        assert quality['orthogonality_error'] >= 0


class TestPrintFunctions:
    """Test print and display functions."""
    
    @patch('builtins.print')
    def test_print_calibration_info_uncalibrated(self, mock_print):
        """Test printing info for uncalibrated instance."""
        cal = MagnetometerCalibration()
        cal.print_calibration_info()
        
        # Should print "No calibration loaded"
        mock_print.assert_called()
        args = [str(call[0][0]) for call in mock_print.call_args_list]
        assert any("No calibration loaded" in arg for arg in args)
    
    @patch('builtins.print')
    def test_print_calibration_info_calibrated(self, mock_print):
        """Test printing info for calibrated instance."""
        cal = MagnetometerCalibration()
        cal.hard_iron_offset = np.array([10.0, 20.0, 30.0])
        cal.soft_iron_matrix = np.eye(3)
        cal.is_calibrated = True
        
        cal.print_calibration_info()
        
        mock_print.assert_called()
    
    @patch('builtins.print')
    def test_print_validation_report(self, mock_print):
        """Test printing validation report."""
        results = {
            'passed': True,
            'quality': 'EXCELLENT',
            'variability_percent': 3.5,
            'ellipticity': 0.05,
            'residual_bias': 100.0,
            'residual_bias_percent': 0.5,
            'mean_field_strength': 45000.0,
            'field_range': (44000.0, 46000.0)
        }
        
        print_validation_report(results)
        
        mock_print.assert_called()
        # Check that key information was printed
        printed_text = ' '.join([str(call[0][0]) for call in mock_print.call_args_list])
        assert 'EXCELLENT' in printed_text
        assert 'PASSED' in printed_text or 'passed' in printed_text.lower()
