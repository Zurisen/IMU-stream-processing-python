# Soft Iron Matrix Regularization

## Problem Statement

The original full 3x3 soft iron calibration could produce matrices that:

- Were poorly conditioned (high condition number)
- Had non-physical transformations (determinant far from 1)
- Lacked orthogonality (non-perpendicular axes)
- Resulted in poor sphericity after calibration

These issues indicate **overfitting** to the calibration data, producing mathematically valid but physically implausible correction matrices.

## Solution: Regularized Optimization

Added multi-term regularization to constrain the soft iron matrix to be physically plausible while still fitting the data well.

### Regularization Terms

The cost function now includes:

```
Total Cost = Data Fitting Cost + λ × Regularization Cost
```

Where the regularization cost includes:

#### 1. **Orthogonality Constraint** (Weight: 10)

```python
ATA = A.T @ A
scale = trace(ATA) / 3
penalty = ||ATA - scale × I||²
```

**Purpose**: Ensures the transformation maintains approximately perpendicular axes, as physical magnetic distortions should preserve axis orthogonality.

**Effect**: Diagonal elements of A^T·A should be similar, off-diagonal elements should be small.

#### 2. **Determinant Constraint** (Weight: 5)

```python
penalty = (log|det(A)|)²
```

**Purpose**: Prevents excessive volume distortion. Physical soft iron effects should not drastically change the overall scale of measurements.

**Effect**: det(A) ≈ 1, ensuring the transformation is approximately volume-preserving.

#### 3. **Diagonal Dominance** (Weight: 2)

```python
off_diagonal = A - diag(diag(A))
penalty = ||off_diagonal||²
```

**Purpose**: Encourages the matrix to be primarily diagonal unless the data strongly demands off-diagonal terms.

**Effect**: Reduces unnecessary complexity, making calibration more robust to noise.

#### 4. **Scale Constraint** (Weight: 1)

```python
penalty = ||(diag(A) - 1)||²
```

**Purpose**: Keeps scaling factors reasonable, preventing extreme values that might indicate numerical instability.

**Effect**: Diagonal elements stay close to 1 unless data requires otherwise.

### Total Regularization Cost

```python
reg_cost = 10 × ortho_penalty +
           5 × det_penalty +
           2 × diag_penalty +
           1 × scale_penalty
```

The weights are chosen to prioritize:

1. **Most important**: Orthogonality (physical plausibility)
2. **Important**: Determinant near 1 (volume preservation)
3. **Moderate**: Diagonal dominance (simplicity)
4. **Gentle**: Scale near 1 (numerical stability)

## Regularization Weight (λ)

The user-adjustable parameter `regularization_weight` (default: 0.01) controls the trade-off:

- **Lower values** (0.001): Better fit to calibration data, may overfit
- **Higher values** (0.1): More physically plausible matrix, may underfit
- **Default** (0.01): Balanced approach for most applications

### How to Choose λ

```
λ = 0.001 → Use when:
  - Large, high-quality calibration dataset
  - Minimal sensor noise
  - Complex magnetic environment requiring full correction

λ = 0.01 → Use when:
  - Standard calibration (recommended default)
  - Typical IMU sensor applications
  - Balance between fit and physical plausibility

λ = 0.1 → Use when:
  - Small or noisy calibration dataset
  - Simple magnetic environment
  - Prefer robustness over perfect fit
```

## Matrix Quality Metrics

The calibration now reports diagnostic metrics to assess the physical plausibility of the resulting soft iron matrix:

### 1. Determinant

- **Ideal**: Close to 1.0
- **Acceptable**: 0.8 to 1.2
- **Poor**: < 0.5 or > 2.0

Indicates overall volume scaling of the transformation.

### 2. Condition Number

- **Excellent**: < 5
- **Good**: < 10
- **Poor**: > 20

Measures numerical stability. High values indicate near-singular matrix.

### 3. Orthogonality Error

- **Excellent**: < 0.1 × scale
- **Good**: < 0.3 × scale
- **Poor**: > 0.5 × scale

Measures deviation from orthogonal transformation. Lower is better.

### 4. Off-Diagonal Ratio

- **Minimal**: < 0.1 (mostly diagonal)
- **Moderate**: 0.1 - 0.5 (some axis coupling)
- **High**: > 0.5 (significant axis coupling)

Indicates degree of axis misalignment or cross-coupling.

### 5. Well-Conditioned Flag

- **True**: Condition number < 10 ✓
- **False**: Condition number ≥ 10 ✗

Quick check for numerical stability.

### 6. Nearly Orthogonal Flag

- **True**: Orthogonality error acceptable ✓
- **False**: Significant non-orthogonality ✗

Quick check for physical plausibility.

## Expected Improvements

With regularization, you should see:

1. **Better Sphericity**: Calibrated data forms a more perfect sphere
2. **Lower Ellipticity**: Reduced eccentricity in field magnitude distribution
3. **Improved Stability**: More consistent results across calibration runs
4. **Physical Plausibility**: Matrix properties consistent with real soft iron effects
5. **Better Generalization**: Calibration works well even in environments slightly different from calibration conditions

## Example Output

```
Soft Iron Matrix Quality:
  Determinant: 0.9823          ← Near 1, good ✓
  Condition Number: 3.45       ← Well-conditioned ✓
  Orthogonality Error: 0.0234  ← Low, nearly orthogonal ✓
  Off-Diagonal Ratio: 0.0567   ← Minimal coupling ✓
  Well-Conditioned: ✓
  Nearly Orthogonal: ✓
```

## Implementation Changes

### Before (Without Regularization)

```python
# Simple data fitting only
cost = sum((||A @ (m - b)|| - r)²)
```

Problems:

- Could produce any matrix that fits data
- No constraints on physical plausibility
- Prone to overfitting with noisy data

### After (With Regularization)

```python
# Data fitting + regularization
data_cost = sum((||A @ (m - b)|| - r)²) / N
reg_cost = 10×ortho + 5×det + 2×diag + 1×scale
total_cost = data_cost + λ × reg_cost
```

Benefits:

- Constrains solution to physically plausible matrices
- Prevents overfitting
- More robust to noise
- Better generalization

## Usage

### In Code

```python
# Create calibration with custom regularization
calibration = MagnetometerCalibration(
    use_full_soft_iron=True,
    regularization_weight=0.01  # Adjust as needed
)

# Perform calibration
params = calibration.calibrate(mag_data)

# Check matrix quality
if params['matrix_quality']['is_well_conditioned']:
    print("Matrix is well-conditioned ✓")
if params['matrix_quality']['is_nearly_orthogonal']:
    print("Matrix is nearly orthogonal ✓")
```

### From Command Line

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
```

## Troubleshooting

### Poor Sphericity Despite Regularization

**Possible Causes**:

1. Insufficient calibration data coverage
2. Too much regularization (increase λ to 0.05-0.1)
3. Environmental magnetic interference during calibration

**Solutions**:

- Collect more data with better angular coverage
- Lower regularization weight slightly (0.005)
- Recalibrate in magnetically clean environment

### Matrix Quality Warnings

**"Not Well-Conditioned"**:

- Increase regularization weight
- Check for outliers in calibration data
- Ensure sufficient data points (> 500)

**"Not Nearly Orthogonal"**:

- Increase regularization weight
- May indicate severe magnetic distortion
- Consider whether full 3x3 correction is actually needed

### Validation Fails

If calibration fails validation after regularization:

1. Try different regularization weights (0.005 - 0.05)
2. Collect more calibration data
3. Check for magnetic interference
4. Consider using diagonal-only calibration if environment is simple

## References

This regularization approach is inspired by:

- Ellipsoid fitting methods (Li & Griffiths, 2004)
- Magnetometer calibration best practices (Fang et al., 2011)
- Regularized optimization techniques (Tikhonov regularization)

The specific multi-term regularization was designed to enforce physical constraints based on the properties of real soft iron distortions in magnetometer applications.
