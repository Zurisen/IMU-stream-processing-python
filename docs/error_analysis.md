# IMU Drift Error Analysis (LSM6DSV + LIS2MDL)

## Scope

This report analyzes why orientation vectors do not return to the initial position after returning the sensor to its original pose, and provides a measurement and mitigation plan.

Important context from current code:

- The runtime fusion implementation in `src/ble_stream.py` currently uses `ahrs.filters.Madgwick`, not an EKF.
- Magnetometer hard/soft-iron calibration is implemented and loaded from `mag_calibration.json`.
- Orientation is visualized from quaternion output in `src/visualizations/orientation_plot.py`.

The symptoms you describe (compounding error and poor loop closure) are still possible with Madgwick and can come from both implementation and environment.

## 1. Possible Sources Of Error

### A. High-probability implementation sources

1. Time-step mismatch (most likely)

- The filter is configured with fixed sample frequency (`SAMPLE_FREC = 100`), but BLE notifications are not guaranteed to arrive at exactly fixed intervals.
- If effective dt differs from assumed dt, gyro integration accumulates systematic error.
- This often appears exactly as loop-closure error: move away and come back, but orientation does not return.

2. Missing gyroscope bias estimation/compensation

- There is no runtime gyro bias tracking in `src/ble_stream.py`.
- Even small constant bias (for example a few mdps) integrates into large heading drift.
- Magnetometer can correct yaw only when magnetic measurements are reliable and correctly weighted.

3. No explicit accelerometer calibration (bias/scale/misalignment)

- The current flow calibrates magnetometer, but no equivalent acc/gyro calibration pipeline is applied at runtime.
- Tilt error from accelerometer bias propagates into orientation correction and can indirectly degrade heading.

4. Sensor-frame misalignment between LSM6DSV and LIS2MDL

- If accelerometer/gyro frame and magnetometer frame axes are not perfectly aligned, using raw vectors as if co-aligned introduces attitude errors.
- This is a common issue in multi-chip stacks, even when both sensors are on the same board.

5. Magnetometer correction without disturbance rejection

- Calibration corrects static hard/soft-iron effects, but runtime magnetic disturbances are still possible.
- Current runtime fusion does not gate or down-weight magnetometer updates when field norm is abnormal.
- During disturbance periods, heading updates can become wrong and look like compounding drift.

6. Potential API misuse risk in filter initialization

- Current initialization uses `Madgwick(sample_freq)` (positional).
- It resolves to valid defaults in the installed library, but keyword usage (`Madgwick(frequency=sample_freq)`) is safer and clearer.
- This is likely not the main drift cause, but worth hardening.

### B. High-probability environmental/mechanical sources

1. Local magnetic interference

- Nearby metal, motors, cables, magnets, power supplies, laptop chassis, desks with steel reinforcements can distort the field.
- Disturbance can be dynamic (changes during motion), which static calibration cannot fully remove.

2. Calibration environment mismatch

- If calibration was done in one place and operation in another magnetically different place, residual bias remains.

3. Vibration and linear acceleration

- During dynamic motion, accelerometer is not gravity-only.
- Gravity-based tilt correction becomes temporarily wrong, affecting quaternion convergence.

4. Temperature drift

- Gyro bias is temperature-dependent.
- If warm-up/state differs from calibration assumptions, drift increases over time.

## 2. Ways To Measure Error

Use repeatable quantitative metrics so each change can be validated.

### A. Loop-closure orientation error (primary metric)

Protocol:

1. Hold still 10 s (initial orientation reference).
2. Perform a repeatable motion path (for example yaw +90 deg, roll, pitch, return to start pose).
3. Hold still 10 s at the end.

Metrics:

- Quaternion closure angle:

  $$\theta_{close} = 2\cos^{-1}(|q_{start} \cdot q_{end}|)$$

- Report mean and 95th percentile across at least 20 runs.

Target:

- Good practical result for this setup: median closure < 2 deg and p95 < 5 deg (static/slow motion, low interference).

### B. Static drift rate

Protocol:

1. Keep sensor perfectly static for 2 to 5 minutes.
2. Track Euler yaw/pitch/roll or quaternion delta over time.

Metrics:

- Drift rate in deg/min for each axis.
- Allan deviation for gyro to estimate bias instability (optional but very useful).

Target:

- Near-zero pitch/roll drift.
- Yaw drift should be low and bounded if magnetic environment is clean.

### C. Magnetic health metrics (interference detector)

Protocol:

1. Log calibrated mag vector norm continuously.
2. Compare against local expected Earth field magnitude (or baseline mean).

Metrics:

- Relative field norm error:

  $$e_B = \frac{|\|m\| - B_0|}{B_0}$$

- Short-window variability (std/mean).

Interpretation:

- Sustained high norm error or variability indicates interference; magnetometer updates should be down-weighted or rejected in those windows.

### D. Gyro bias measurement

Protocol:

1. Keep IMU static for at least 60 s.
2. Compute mean gyro raw output per axis.

Metrics:

- Bias in rad/s per axis.
- Residual after subtracting estimated bias.

Interpretation:

- Non-zero mean gyro while static directly predicts integration drift.

### E. Timing quality measurement

Protocol:

1. Timestamp each packet arrival in runtime.
2. Compute dt histogram.

Metrics:

- Mean dt, std(dt), min/max dt, dropped/late packet count.

Interpretation:

- If dt jitter is significant relative to 10 ms nominal period, fixed-dt fusion will drift more.

## 3. Recommended Steps Forward

### Phase 1: Instrumentation first (no algorithm change yet)

1. Log per-sample dt from BLE notification timestamps.
2. Log raw and calibrated mag norm, and gyro mean during static windows.
3. Add loop-closure test script and produce baseline metrics.

Outcome: You can separate timing/bias/interference effects before tuning fusion.

### Phase 2: Low-risk implementation fixes

1. Use measured dt in fusion update (or resample to uniform time base).
2. Add startup static gyro bias calibration (10 to 30 s) and subtract bias online.
3. Harden filter construction with explicit keywords (`Madgwick(frequency=...)`).
4. Normalize/validate input vectors and guard against invalid magnitudes.

Outcome: Significant reduction in compounding integration error in most setups.

### Phase 3: Magnetic robustness

1. Add runtime magnetometer gating:
- Skip or down-weight mag corrections when norm error/variability exceeds threshold.
2. Recalibrate in final operating environment.
3. Verify sensor-frame alignment between accel/gyro and magnetometer; apply fixed alignment matrix if needed.

Outcome: Better yaw stability and improved return-to-origin behavior in real conditions.

### Phase 4: Advanced improvements (if needed)

1. Move to an EKF/MEKF with explicit gyro-bias state.
2. Add adaptive measurement covariance:
- Increase mag measurement noise when interference detected.
- Increase acc measurement noise during high linear acceleration.
3. Add temperature compensation for gyro bias.

Outcome: More robust performance across varying dynamics and environments.

## 4. Decision Matrix: Implementation Error vs Interference

Use this quick diagnosis logic:

- If static drift is high in magnetically clean environment and mag norm is stable: implementation/timing/bias issue likely.
- If static is good but drift spikes near specific places/objects: interference likely.
- If closure error scales strongly with trial duration: gyro bias/dt issue likely.
- If yaw is unstable but pitch/roll are good: magnetic disturbance or mag-frame alignment likely.

## 5. Practical First Actions (highest ROI)

1. Measure dt jitter and switch to variable-dt update.
2. Add static gyro bias estimation and compensation.
3. Add magnetic norm-based gating.
4. Run 20 loop-closure trials and compare metrics before/after.

If these four steps are done, you should be able to determine whether remaining error is mostly algorithmic or environmental, and whether an EKF migration is justified.