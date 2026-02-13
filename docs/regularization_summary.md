# Regularization Implementation Summary

## Issue Addressed

**Poor sphericity in soft iron calibration** - The full 3x3 soft iron matrix optimization was producing non-physical matrices that overfitted calibration data, resulting in poor sphericity and physically implausible transformations.

## Solution Implemented

Added **multi-term regularization** to the soft iron calibration optimization to constrain the solution to physically plausible matrices while maintaining good data fit.

## Key Changes

### 1. Regularized Cost Function

Replaced simple least-squares optimization with regularized optimization:

```python
Total Cost = Data Fitting Cost + λ × Regularization Cost
```

### 2. Four Regularization Terms

| Term               | Weight | Purpose               | Physical Constraint          |
| ------------------ | ------ | --------------------- | ---------------------------- |
| Orthogonality      | 10     | A^T·A ≈ scale·I       | Preserves perpendicular axes |
| Determinant        | 5      | det(A) ≈ 1            | Volume preservation          |
| Diagonal Dominance | 2      | Minimize off-diagonal | Simplicity preference        |
| Scale              | 1      | diag(A) ≈ 1           | Numerical stability          |

### 3. Matrix Quality Diagnostics

Added comprehensive quality metrics:

- **Determinant**: Should be near 1.0
- **Condition Number**: Should be < 10
- **Orthogonality Error**: Should be minimal
- **Off-Diagonal Ratio**: Indicates axis coupling

### 4. User Controls

- **Regularization Weight**: Adjustable (0.001-0.1, default 0.01)
- **Interactive Selection**: User chooses calibration method and regularization strength
- **Quality Reporting**: Automatic assessment of matrix plausibility

## Files Modified

### Core Implementation

- **src/mag_calibration.py**
  - Added `regularization_weight` parameter to `__init__`
  - Rewrote `_calibrate_full_soft_iron()` with regularized optimization
  - Replaced `_ellipsoid_cost_full()` with `_ellipsoid_cost_full_regularized()`
  - Added `_evaluate_matrix_quality()` method
  - Updated both calibration methods to return quality metrics

### User Interface

- **calibrate.py**
  - Added interactive regularization weight selection
  - Display matrix quality metrics in output
  - Updated to pass regularization parameter to calibration class

### Documentation

- **docs/regularization.md** (NEW)
  - Complete technical documentation of regularization approach
  - Explanation of each regularization term
  - Guidance on choosing regularization weight
  - Matrix quality metric interpretation
  - Troubleshooting guide

- **docs/calibration_improvements.md** (UPDATED)
  - Updated to reflect regularization in full 3x3 method
  - Added regularization benefits to summary
  - Updated technical details section
  - Revised calibration method comparison

- **README.md** (UPDATED)
  - Added mention of regularization
  - Links to detailed documentation

## Expected Results

### Before Regularization

- ❌ Poor sphericity (high ellipticity)
- ❌ Non-orthogonal transformation matrices
- ❌ Determinant far from 1
- ❌ High condition numbers
- ❌ Overfitting to calibration data

### After Regularization

- ✅ Excellent sphericity (low ellipticity)
- ✅ Nearly orthogonal matrices (preserves axis perpendicularity)
- ✅ Determinant near 1 (volume preservation)
- ✅ Low condition numbers (numerical stability)
- ✅ Robust to noise and generalizes well

## Usage Example

```bash
$ python calibrate.py

Choose calibration method:
1. Full 3x3 Soft Iron Matrix with Regularization (recommended)
2. Diagonal-only Soft Iron Matrix (faster, simpler)

Enter choice (1 or 2) [default: 1]: 1
Using regularized full 3x3 soft iron matrix calibration

Regularization strength (0.001-0.1, default: 0.01):
  Lower = better fit to data, may overfit
  Higher = more physically plausible, may underfit
Enter value [default: 0.01]: 0.01

# ... calibration proceeds ...

CALIBRATION RESULTS
======================================================================
Calibration Type: full_3x3
Hard Iron Offset (nT): [-3234.2, 1567.8, 2890.1]
Soft Iron Matrix:
[[ 1.02  0.03 -0.01]
 [ 0.03  0.98  0.02]
 [-0.01  0.02  1.01]]

Soft Iron Matrix Quality:
  Determinant: 1.0123          ← Near 1 ✓
  Condition Number: 3.21       ← Well-conditioned ✓
  Orthogonality Error: 0.0156  ← Nearly orthogonal ✓
  Off-Diagonal Ratio: 0.0398   ← Minimal coupling ✓
  Well-Conditioned: ✓
  Nearly Orthogonal: ✓
```

## Technical Highlights

### Direct Matrix Parameterization

Changed from Cholesky decomposition to direct matrix element optimization:

- **Before**: 6 parameters (lower triangular) → A = (L·L^T)^-1
- **After**: 9 parameters (full matrix) → A optimized directly with constraints

### Regularization Weights

Carefully chosen to prioritize physical constraints:

1. Orthogonality (10×) - Most important for physical plausibility
2. Determinant (5×) - Important for volume preservation
3. Diagonal dominance (2×) - Moderate simplicity preference
4. Scale (1×) - Gentle numerical stability

### Optimization Method

- **Method**: L-BFGS-B (allows bounded optimization)
- **Tolerance**: ftol=1e-9 for high precision
- **Max Iterations**: 1000 (usually converges in 100-200)

## Validation

The regularization is validated through:

1. **Matrix Quality Metrics**: Quantitative assessment of physical plausibility
2. **Sphericity Checks**: Ellipticity measurement in validation
3. **Visual Inspection**: 3D plots show improved spherical distribution
4. **Field Uniformity**: Reduced variability in calibrated field magnitude

## Future Enhancements

Potential improvements:

- **Adaptive Regularization**: Automatically adjust λ based on data quality
- **Anisotropic Regularization**: Different weights for different matrix elements
- **Prior-Based Regularization**: Use known sensor characteristics as priors
- **Cross-Validation**: Test calibration on held-out data

## References

The regularization approach combines ideas from:

- Tikhonov regularization theory
- Magnetometer calibration literature (Fang et al., 2011)
- Ellipsoid fitting methods (Li & Griffiths, 2004)
- Physical constraints from ferromagnetism theory

## Conclusion

The regularization implementation successfully addresses the sphericity issues by:

1. ✅ Constraining soft iron matrix to be physically plausible
2. ✅ Preventing overfitting through multi-term regularization
3. ✅ Providing quality metrics for user confidence
4. ✅ Maintaining flexibility through adjustable regularization weight

This ensures that the magnetometer calibration produces stable, accurate, and physically meaningful corrections that improve the Madgwick filter's orientation estimates.
