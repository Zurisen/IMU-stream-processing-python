# Magnetometer Calibration Audit (Critic Review)

## 1. Calibration Model & Implementation

- **Type**: The code implements both hard iron (offset) and soft iron (scaling, via diagonal matrix) calibration using ellipsoid fitting (least squares).
- **Application**: Calibration is applied to all incoming data in real time, both for single and batch readings.
- **Persistence**: Calibration parameters are saved/loaded from `mag_calibration.json`.

## 2. Code Quality & Best Practices

- **Positive**:
  - Uses ellipsoid fitting for calibration, which is standard for hard/soft iron correction.
  - Handles both saving and loading of calibration parameters robustly.
  - Applies calibration to all magnetometer data before use in sensor fusion (Madgwick filter).
  - Provides calibration quality metrics and user feedback.
- **Potential Issues**:
  - **Soft Iron Correction**: Only a diagonal matrix is used for soft iron correction. True soft iron effects may require a full (non-diagonal) 3x3 matrix to account for axis misalignment and scaling.
  - **Ellipsoid Fitting**: The optimization only fits for center and scale (not full orientation/shear). This may leave some residual drift if the sensor's axes are not perfectly orthogonal or if there is cross-axis interference.
  - **Data Collection**: The calibration script instructs the user to rotate the sensor in all directions, but if the coverage is not uniform, calibration quality may suffer.
  - **Environmental Factors**: No explicit check for environmental magnetic disturbances during calibration.
  - **Error Handling**: If calibration is not loaded, the system falls back to uncalibrated data, which may not be safe for all applications.

## 3. Recommendations

- **Full Soft Iron Correction**: Consider implementing a full 3x3 soft iron matrix (not just diagonal) for more accurate calibration if drift persists.
- **Calibration Validation**: Add a post-calibration validation step that visualizes the corrected data as a sphere (or at least checks for residual bias/ellipticity).
- **User Guidance**: Provide more explicit instructions or real-time feedback during calibration to ensure good coverage.
- **Environmental Checks**: Warn users if the field strength during calibration is highly variable (may indicate interference).
- **Fail-Safe**: Consider halting or warning if calibration is missing, rather than using uncalibrated data silently.

## 4. Summary Table

| Aspect                | Status  | Notes                                                     |
| --------------------- | ------- | --------------------------------------------------------- |
| Hard Iron Correction  | Good    | Center offset fitted and applied                          |
| Soft Iron Correction  | Poor    | Full 3x3 matrix fit is unstable; poor sphericity observed |
| Real-Time Application | Good    | Calibration applied to all data before use                |
| Data Persistence      | Good    | JSON save/load robust                                     |
| User Feedback         | Good    | Quality metrics and progress messages                     |
| Error Handling        | Fair    | Falls back to uncalibrated data if calibration missing    |
| Environmental Checks  | Lacking | No explicit check for magnetic disturbances               |

## 5. Key Questions

- Is the poor spheroid fit due to insufficient or non-uniform calibration data?
- Is the full 3x3 soft iron matrix overfitting due to noise or lack of regularization?
- Would regularizing the fit or improving data collection improve sphericity?

## 6. Soft Iron Calibration & Spheroid Fit: Critic Analysis

### Observations

- Poor spheroid fit (high ellipticity) is common, even with full 3x3 soft iron calibration.
- This suggests the soft iron correction is not fully effective, or the fit is unstable.

### Causes

- **Data Quality**: Calibration data may not cover all orientations uniformly, or may be contaminated by environmental noise.
- **Algorithmic Instability**: Full 3x3 matrix fitting is sensitive to noise and can overfit if not regularized.
- **Physical Limitations**: Some sensors or environments may have non-linear or time-varying distortions that cannot be fully corrected with a linear model.

### Recommendations

1. **Improve Data Collection**

- Move the sensor slowly and uniformly through all orientations during calibration.
- Avoid magnetic disturbances (metal objects, electronics) nearby.
- Collect more data points for better coverage.
- **Implement a real-time 3D points display** during calibration to visually confirm that the sphere is being properly filled. This immediate feedback helps ensure uniform coverage and higher calibration quality.

2. **Regularize the Fit**

- Add constraints or regularization to the soft iron matrix fitting (e.g., penalize large off-diagonal terms, enforce determinant near 1).
- Consider using a hybrid approach: start with a diagonal matrix, then incrementally add off-diagonal terms if justified by the data.

3. **Post-Calibration Validation**

- Always visualize the corrected data cloud. It should be spherical and centered at the origin.
- If sphericity is poor, repeat calibration with improved data or adjust the fitting method.

4. **Fallback**

- If the full 3x3 fit is unstable, use a diagonal matrix and document the limitation.

### Conclusion

Persistent poor spheroid fit indicates a need for better soft iron calibration. Focus on improving data quality and consider regularizing the fitting algorithm. If instability persists, a simpler (diagonal) model may be preferable for your application.

---

**Overall:**

- The calibration and application logic is robust and follows standard practice, but could be improved by supporting a full soft iron matrix and adding more user/environmental checks. The current approach is likely sufficient for moderate accuracy, but for minimal drift, consider the above recommendations.
