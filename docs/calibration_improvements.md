# Magnetometer Calibration Improvements

This document describes the improvements made to the magnetometer calibration system based on the critic review.

## Summary of Changes

### 1. Full 3x3 Soft Iron Matrix Support with Regularization

**Issue**: The original implementation only used a diagonal soft iron matrix, which couldn't account for cross-axis interference and axis misalignment. Additionally, unrestricted optimization could produce non-physical matrices that overfit calibration data.

**Solution**: Implemented full 3x3 soft iron matrix calibration with multi-term regularization to ensure physical plausibility.

**Benefits**:

- Handles cross-axis magnetic interference
- Corrects for sensor axis misalignment
- Reduces residual drift in high-accuracy applications
- Better handles soft iron distortions from nearby materials
- **Prevents overfitting through regularization**
- **Ensures physically plausible matrices (orthogonality, determinant ≈ 1)**
- **Improves sphericity of calibrated data**

**Implementation Details**:

- Uses `scipy.optimize.minimize` with L-BFGS-B method
- Directly optimizes 9 matrix parameters with regularization constraints
- **Multi-term regularization** enforces orthogonality, volume preservation, and diagonal dominance
- Adjustable regularization weight (default: 0.01) for fine-tuning
- Reports matrix quality metrics (determinant, condition number, orthogonality)
- Falls back to diagonal-only method if explicitly requested for backward compatibility

**See [regularization.md](regularization.md) for detailed technical documentation.**

### 2. Calibration Validation System

**Issue**: No automated way to verify calibration quality beyond basic variance metrics.

**Solution**: Implemented comprehensive validation system with:

- Visual inspection via 3D plots
- Statistical quality metrics
- Automated pass/fail determination
- Residual bias and ellipticity checks

**Key Features**:

#### Visualization

- **Before/After 3D Scatter Plots**: Shows raw vs calibrated magnetometer data
- **Reference Sphere**: Overlays ideal sphere on calibrated data for visual comparison
- **Field Magnitude Distribution**: Histogram showing improvement in field uniformity

#### Quality Metrics

1. **Variability**: Standard deviation of field magnitude (should be < 5% for excellent)
2. **Ellipticity**: Ratio of (max-min)/mean radius (should be < 0.1 for excellent)
3. **Residual Bias**: Distance of mean position from origin (should be < 2% for excellent)
4. **Field Uniformity**: Range and distribution of field magnitudes

#### Quality Thresholds

- **EXCELLENT**: Variability < 5%, Ellipticity < 0.1
- **GOOD**: Variability < 10%, Ellipticity < 0.15
- **ACCEPTABLE**: Variability < 15%, Ellipticity < 0.25
- **POOR**: Above acceptable thresholds (requires recalibration)

### 3. Real-Time 3D Sphere Visualization

**Issue**: Users couldn't see if they were achieving uniform sphere coverage during data collection, leading to poor calibration quality.

**Solution**: Implemented real-time 3D visualization showing magnetometer data as it's collected, with coverage estimation and environmental monitoring.

**Key Features**:

#### Live Data Display

- **3D scatter plot**: Shows magnetometer readings in real-time
- **Color coding**: Newer points are brighter for visual tracking
- **Dynamic sphere**: Reference sphere updates based on data
- **Auto-scaling**: View adjusts to data range automatically

#### Coverage Estimation

- **Octant tracking**: Monitors 8 major sphere regions
- **Percentage display**: Shows 0-100% coverage in real-time
- **Status indicators**:
  - 🔴 < 50%: "More rotation needed!"
  - 🟡 50-80%: "Good, keep rotating"
  - 🟢 > 80%: "Excellent coverage!"

#### Environmental Monitoring

- **Field strength tracking**: Monitors mean and variability
- **Disturbance detection**: Warns when field changes suddenly (>15% variability)
- **Visual indicators**: Color-coded field quality display
- **Warning throttling**: Prevents spam during transient interference

#### Benefits

- Ensures uniform data coverage
- Immediate feedback on collection quality
- Detects magnetic interference during (not after) collection
- Guides users to fill coverage gaps
- Reduces need for recalibration

**See [realtime_visualization.md](realtime_visualization.md) for complete details.**

### 4. Enhanced User Interface

**Improvements**:

- Interactive choice between diagonal and full 3x3 calibration
- Detailed validation report with interpretation
- Clear pass/fail indication
- Conditional save based on validation results
- Guidance for improving poor calibrations

**Workflow**:

1. User selects calibration method and regularization strength
2. Optional: Enable/disable real-time 3D visualization
3. Data collection with real-time visual feedback and coverage tracking
4. Environmental monitoring alerts user to magnetic interference
5. Calibration computation with regularization
6. Automatic validation with 3D visualization
7. Quality assessment and detailed report
8. Conditional save with user confirmation if quality is poor

## Usage

### Running Calibration

```bash
python calibrate.py
```

The script will:

1. Ask for calibration method (full 3x3 or diagonal-only)
2. Ask for regularization strength (if using full 3x3)
3. Ask if you want real-time 3D visualization
4. Collect magnetometer data with live visual feedback
5. Monitor for environmental disturbances
6. Display coverage percentage and guidance
7. Compute calibration parameters
8. Validate calibration quality
9. Display validation plots and quality report
10. Save calibration if validation passes
11. Save calibration if validation passes (or with user confirmation)

### Calibration Method Selection

**Full 3x3 Soft Iron Matrix with Regularization (Recommended)**:

- Use when: Maximum accuracy with physical plausibility is needed
- Best for: Applications requiring minimal drift and stable calibration
- Time: Slightly longer computation time
- Output: Full 9-parameter soft iron correction with quality guarantees
- Adjustable: Regularization weight can be tuned (0.001-0.1)

**Diagonal-only Soft Iron Matrix**:

- Use when: Simpler calibration is sufficient
- Best for: Quick calibration or less critical applications
- Time: Faster computation
- Output: 3-parameter diagonal scaling only

## Validation Output

### Files Generated

- `mag_calibration.json`: Calibration parameters (saved only if validation passes)
- `calibration_validation.png`: Visualization plot showing raw vs calibrated data

### Validation Report Example

```
======================================================================
CALIBRATION VALIDATION REPORT
======================================================================
Overall Quality: EXCELLENT
Validation Status: ✓ PASSED

Metrics:
  Field Variability: 2.34%
  Ellipticity: 0.0456
  Residual Bias: 123.45 nT (1.23%)
  Mean Field Strength: 48532.1 nT
  Field Range: 47234.5 - 49876.3 nT

Interpretation:
  ✓ Excellent field uniformity
  ✓ Excellent sphericity (minimal ellipticity)
  ✓ Minimal residual bias (well-centered)
======================================================================
```

## Technical Details

### Full Soft Iron Calibration Algorithm (with Regularization)

The optimization minimizes a regularized cost function:

```
Total Cost = Data Cost + λ × Regularization Cost
```

**Data Cost**:

```
Σ(||A · (m - b)|| - r)² / N
```

**Regularization Cost** (multi-term):

```
10×||A^T·A - scale·I||² +     # Orthogonality
5×(log|det(A)|)² +             # Volume preservation
2×||off_diagonal(A)||² +       # Diagonal dominance
1×||diag(A) - 1||²             # Scale constraint
```

Where:

- `m`: Raw magnetometer reading
- `b`: Hard iron offset (3 parameters)
- `A`: Soft iron matrix (9 parameters, directly optimized)
- `r`: Expected field magnitude
- `λ`: Regularization weight (default: 0.01)

### Regularization Benefits

The regularization terms ensure:

1. **Orthogonality**: Axes remain approximately perpendicular
2. **Volume Preservation**: Determinant stays near 1
3. **Simplicity**: Prefers diagonal unless data demands otherwise
4. **Stability**: Prevents extreme parameter values

See [regularization.md](regularization.md) for complete technical details.

### Validation Metrics

**Variability**:

```
variability = (std(||m_cal||) / mean(||m_cal||)) × 100%
```

**Ellipticity**:

```
ellipticity = (max(||m_cal||) - min(||m_cal||)) / mean(||m_cal||)
```

**Residual Bias**:

```
residual_bias = ||mean(m_cal)||
```

## Benefits Over Previous Implementation

1. **Accuracy**: Full 3x3 matrix handles complex distortions
2. **Physical Plausibility**: Regularization ensures orthogonality and volume preservation
3. **Improved Sphericity**: Regularization reduces overfitting and ellipticity
4. **Real-Time Guidance**: Live 3D visualization ensures uniform coverage
5. **Environmental Awareness**: Detects magnetic interference during collection
6. **Coverage Feedback**: Shows completion percentage and guides rotation
7. **Validation**: Automated quality assessment prevents poor calibrations
8. **Matrix Quality Metrics**: Determinant, condition number, orthogonality diagnostics
9. **Visualization**: Clear before/after comparison aids debugging
10. **User Guidance**: Detailed feedback helps users improve calibration
11. **Flexibility**: Choice between accuracy and speed
12. **Adjustable Regularization**: Fine-tune trade-off between fit and plausibility
13. **Robustness**: More stable across different calibration datasets
14. **Fail-Safe**: Warns and prompts before using uncalibrated data
15. **Robustness**: Validation prevents saving poor calibrations

## Recommendations

### For Best Results

1. **Environment**:
   - Perform calibration away from magnetic interference
   - Avoid metal desks, computers, magnets
   - Use consistent environment for calibration and operation

2. **Data Collection**:
   - Rotate sensor smoothly through ALL orientations
   - Use figure-8 patterns in multiple planes
   - Collect data for 30-60 seconds minimum
   - Aim for 1000+ data points

3. **Validation**:
   - Always review the validation plot
   - Check for even coverage in 3D space
   - Verify the calibrated data forms a sphere
   - If validation fails, recalibrate with better coverage

4. **Method Selection**:
   - Use full 3x3 for precision applications
   - Use diagonal-only for rapid prototyping
   - Re-calibrate if moving to different magnetic environment

## Addressing Critic Feedback

### ✓ Full Soft Iron Correction with Regularization

- **Implemented**: Full 3x3 soft iron matrix with multi-term regularization
- **Physical Constraints**: Orthogonality, volume preservation, diagonal dominance
- **Choice**: User can select between full and diagonal methods
- **Adjustable**: Regularization weight customizable (0.001-0.1)
- **Quality**: Significantly reduces residual drift and improves sphericity

### ✓ Calibration Validation

- **Visualization**: 3D plots of raw and calibrated data with reference sphere
- **Metrics**: Comprehensive quality assessment (variability, ellipticity, bias)
- **Pass/Fail**: Automated validation with clear thresholds
- **Guidance**: Detailed report with interpretation and recommendations

### ✓ User Guidance & Real-Time Feedback

- **Live 3D Visualization**: Shows data as it's collected during calibration
- **Coverage Tracking**: Real-time percentage and octant-based monitoring
- **Visual Indicators**: Color-coded status (red/yellow/green)
- **Gap Detection**: Helps users identify and fill coverage gaps
- **Progress Feedback**: Updates every 50 samples with coverage info

### ✓ Environmental Checks

- **Real-Time Monitoring**: Tracks field strength during collection
- **Disturbance Detection**: Warns when variability exceeds 15%
- **Warning System**: Alerts about magnetic interference immediately
- **Post-Collection Summary**: Reports mean field, variability, disturbances
- **Quality Thresholds**: Prevents saving poor calibrations

### ✓ Fail-Safe Error Handling

- **Calibration Required**: Strong warning if no calibration found
- **User Confirmation**: Requires explicit agreement to proceed uncalibrated
- **Detailed Impact**: Explains consequences of uncalibrated data
- **Easy Instructions**: Clear steps to run calibration
- **Validation Required**: Calibration must pass validation to be saved automatically
- **Poor Quality Handling**: Explicit user approval needed for below-threshold calibrations

## Future Enhancements

Potential improvements for future versions:

1. ~~Real-time coverage visualization during data collection~~ ✓ **IMPLEMENTED**
2. ~~Adaptive sampling suggestions to fill coverage gaps~~ ✓ **IMPLEMENTED** (via coverage display)
3. ~~Automatic magnetic disturbance detection~~ ✓ **IMPLEMENTED**
4. Temperature compensation for magnetometer drift
5. Multi-session calibration averaging
6. Field strength validation against known Earth field values
7. Heatmap overlay showing spatial density of coverage
8. Predictive quality estimation during data collection
9. Recording playback for reviewing collection patterns
10. Multi-sensor support (all 3 IMUs simultaneously)
