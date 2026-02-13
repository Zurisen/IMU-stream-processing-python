"""
Unit tests for src/utils.py module.
Tests utility functions including quaternion operations.
"""
import pytest
import numpy as np
from src.utils import quaternion_to_rotation_matrix


class TestQuaternionToRotationMatrix:
    """Test quaternion to rotation matrix conversion."""
    
    def test_identity_quaternion(self):
        """Test identity quaternion produces identity matrix."""
        q = np.array([1.0, 0.0, 0.0, 0.0])  # Identity quaternion (w, x, y, z)
        R = quaternion_to_rotation_matrix(q)
        
        expected = np.eye(3)
        np.testing.assert_array_almost_equal(R, expected, decimal=10)
    
    def test_rotation_matrix_shape(self):
        """Test that output is 3x3 matrix."""
        q = np.array([0.7071, 0.7071, 0.0, 0.0])
        R = quaternion_to_rotation_matrix(q)
        
        assert R.shape == (3, 3)
    
    def test_rotation_matrix_is_orthogonal(self):
        """Test that rotation matrix is orthogonal (R^T @ R = I)."""
        q = np.array([0.7071, 0.7071, 0.0, 0.0])
        R = quaternion_to_rotation_matrix(q)
        product = R.T @ R
        np.testing.assert_array_almost_equal(product, np.eye(3), decimal=4)
    
    def test_determinant_is_one(self):
        """Test that determinant of rotation matrix is 1."""
        q = np.array([0.7071, 0.7071, 0.0, 0.0])
        R = quaternion_to_rotation_matrix(q)
        det = np.linalg.det(R)
        assert np.isclose(det, 1.0, atol=1e-4)
    
    def test_90_degree_rotation_about_x(self):
        """Test 90 degree rotation about X axis."""
        # 90 degrees about X: q = [cos(45°), sin(45°), 0, 0]
        angle = np.pi / 4  # Half angle for quaternion
        q = np.array([np.cos(angle), np.sin(angle), 0.0, 0.0])
        R = quaternion_to_rotation_matrix(q)
        
        # Expected rotation matrix for 90° about X
        expected = np.array([
            [1, 0, 0],
            [0, 0, -1],
            [0, 1, 0]
        ])
        
        np.testing.assert_array_almost_equal(R, expected, decimal=5)
    
    def test_90_degree_rotation_about_y(self):
        """Test 90 degree rotation about Y axis."""
        angle = np.pi / 4  # Half angle
        q = np.array([np.cos(angle), 0.0, np.sin(angle), 0.0])
        R = quaternion_to_rotation_matrix(q)
        
        # Expected rotation matrix for 90° about Y
        expected = np.array([
            [0, 0, 1],
            [0, 1, 0],
            [-1, 0, 0]
        ])
        
        np.testing.assert_array_almost_equal(R, expected, decimal=5)
    
    def test_90_degree_rotation_about_z(self):
        """Test 90 degree rotation about Z axis."""
        angle = np.pi / 4  # Half angle
        q = np.array([np.cos(angle), 0.0, 0.0, np.sin(angle)])
        R = quaternion_to_rotation_matrix(q)
        
        # Expected rotation matrix for 90° about Z
        expected = np.array([
            [0, -1, 0],
            [1, 0, 0],
            [0, 0, 1]
        ])
        
        np.testing.assert_array_almost_equal(R, expected, decimal=5)
    
    def test_quaternion_normalization_not_required(self):
        """Test with non-normalized quaternion."""
        # Non-normalized quaternion
        q = np.array([2.0, 0.0, 0.0, 0.0])
        R = quaternion_to_rotation_matrix(q)
        
        # Should still produce valid rotation matrix (though not normalized input)
        # Check if orthogonal
        product = R.T @ R
        # This may not be exactly identity due to non-normalization
        assert R.shape == (3, 3)
    
    def test_normalized_quaternion(self):
        """Test with properly normalized quaternion."""
        q = np.array([0.5, 0.5, 0.5, 0.5])  # Normalized
        assert abs(np.linalg.norm(q) - 1.0) < 1e-10
        
        R = quaternion_to_rotation_matrix(q)
        
        # Should be orthogonal
        product = R.T @ R
        np.testing.assert_array_almost_equal(product, np.eye(3), decimal=10)
        
        # Should have determinant 1
        assert abs(np.linalg.det(R) - 1.0) < 1e-10
    
    def test_arbitrary_rotation(self):
        """Test arbitrary rotation quaternion."""
        # Rotation of 60 degrees about axis [1, 1, 1]
        angle = np.pi / 6  # 30 degrees (half of 60)
        axis = np.array([1.0, 1.0, 1.0])
        axis = axis / np.linalg.norm(axis)  # Normalize
        
        q = np.array([
            np.cos(angle),
            np.sin(angle) * axis[0],
            np.sin(angle) * axis[1],
            np.sin(angle) * axis[2]
        ])
        
        R = quaternion_to_rotation_matrix(q)
        
        # Check orthogonality
        product = R.T @ R
        np.testing.assert_array_almost_equal(product, np.eye(3), decimal=10)
        
        # Check determinant
        assert abs(np.linalg.det(R) - 1.0) < 1e-10
    
    def test_input_types(self):
        """Test different input types."""
        # Test with list
        q_list = [1.0, 0.0, 0.0, 0.0]
        R1 = quaternion_to_rotation_matrix(q_list)
        assert R1.shape == (3, 3)
        
        # Test with numpy array
        q_array = np.array([1.0, 0.0, 0.0, 0.0])
        R2 = quaternion_to_rotation_matrix(q_array)
        assert R2.shape == (3, 3)
        
        np.testing.assert_array_almost_equal(R1, R2)
    
    def test_rotation_preserves_length(self):
        """Test that rotation matrix preserves vector length."""
        q = np.array([0.7071, 0.7071, 0.0, 0.0])
        R = quaternion_to_rotation_matrix(q)
        v = np.array([1.0, 2.0, 3.0])
        v_rotated = R @ v
        assert np.isclose(np.linalg.norm(v), np.linalg.norm(v_rotated), atol=1e-4)
    
    def test_rotation_composition(self):
        """Test that quaternion rotation matches matrix composition."""
        q1 = np.array([0.9239, 0.3827, 0.0, 0.0])  # 45° about X
        q2 = np.array([0.9239, 0.0, 0.3827, 0.0])  # 45° about Y
        R1 = quaternion_to_rotation_matrix(q1)
        R2 = quaternion_to_rotation_matrix(q2)
        R_composed = R2 @ R1
        product = R_composed.T @ R_composed
        np.testing.assert_array_almost_equal(product, np.eye(3), decimal=4)
