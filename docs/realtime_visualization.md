# Real-Time 3D Calibration Visualization

## Overview

Implemented **real-time 3D sphere visualization** during magnetometer calibration to address critic.md recommendations for better user guidance and data collection quality.

## Features Implemented

### 1. Live 3D Scatter Plot

- **Real-time data display**: Shows magnetometer readings as they're collected
- **Color coding**: Newer points are brighter (using viridis colormap)
- **Dynamic scaling**: Automatically adjusts view based on data range
- **Centered visualization**: Tracks data center and adjusts sphere accordingly

### 2. Coverage Estimation

- **Octant-based coverage**: Divides sphere into 8 major regions
- **Real-time percentage**: Shows coverage from 0-100%
- **Visual feedback**:
  - 🔴 < 50%: "More rotation needed!"
  - 🟡 50-80%: "Good, keep rotating"
  - 🟢 > 80%: "Excellent coverage!"

### 3. Reference Sphere

- **Adaptive wireframe**: Shows expected sphere based on collected data
- **Visual target**: Helps users understand desired coverage pattern
- **Green overlay**: Updates as mean radius is calculated

### 4. Environmental Monitoring

- **Field strength tracking**: Monitors mean field magnitude
- **Variability detection**: Calculates standard deviation and percentage
- **Disturbance warnings**: Alerts when sudden field changes occur (>15% variability)
- **Warning throttling**: Limits warnings to once per 5 seconds
- **Visual indicators**:
  - 🟢 Green: Low variability (< 10%)
  - 🟡 Yellow: Moderate variability (10-15%)
  - 🔴 Red: High variability (> 15%) or disturbances

### 5. Status Information Display

Two information boxes show:

**Box 1 (Coverage Status)**:

- Sample count
- Coverage percentage
- Status message with icon

**Box 2 (Field Quality)**:

- Mean field strength ± std deviation
- Variability percentage
- Disturbance count (if any)

### 6. Interactive Controls

- **Enable/Disable**: User can opt-out of visualization for better performance
- **Thread-based**: Runs in separate thread to not block data collection
- **Graceful shutdown**: Properly closes matplotlib when done

### 7. Performance Optimizations

- **Smart downsampling**: Limits displayed points to 500 (configurable) to prevent crashes
- **Intelligent sampling**: Keeps recent points + uniform sampling of older data
- **Larger points**: Uses s=15 point size for better visibility with fewer points
- **Adaptive refresh**: Slower updates (0.15s) when dataset is large (>1000 points)
- **All data tracked**: Coverage calculation uses ALL points, not just displayed ones
- **Status indicator**: Shows "(showing N)" when downsampling is active

## Implementation Details

### Threading Architecture

```python
Main Thread (asyncio)          Visualization Thread
      │                                 │
      ├─ BLE Connection                 │
      ├─ Data Collection ──────────────>│
      │  (with thread lock)             │
      │                                 ├─ Update plot
      │                                 ├─ Calculate coverage
      │                                 └─ Display info
      └─ Wait for Ctrl+C                │
                                        └─ Close on stop
```

### Coverage Algorithm

```python
def _estimate_coverage():
    # Normalize data to unit sphere
    normalized = data / norms

    # Check 8 octants (combinations of ±x, ±y, ±z)
    for each octant:
        if any points with dominant direction in octant:
            octants_covered += 1

    coverage = (octants_covered / 8) * 100
```

### Environmental Monitoring

```python
# Check last 20 samples for variability
if len(field_magnitudes) > 20:
    recent = field_magnitudes[-20:]
    variability = std(recent) / mean(recent) * 100

    if variability > 15% and time_since_last_warning > 5s:
        warn_user()
```

## Usage

### Starting Calibration

```bash
$ python calibrate.py

Enable real-time 3D visualization during data collection?
  (Helps ensure good coverage, but may impact performance)
Enable visualization? (y/n) [default: y]: y

✓ Real-time visualization enabled
```

### During Calibration

1. **3D window opens** showing empty sphere
2. **Rotate sensor** - data points appear in real-time
3. **Watch coverage** - aim for all 8 octants (>80%)
4. **Monitor field quality** - green is good, red indicates interference
5. **Continue until coverage complete** (usually 30-60 seconds)
6. **Press Ctrl+C** when satisfied with coverage

### Visual Feedback Example

```
╔══════════════════════════╗
║ Samples: 847             ║
║ Coverage: 87.5%          ║
║ ✓ Excellent coverage!    ║
╚══════════════════════════╝

╔══════════════════════════╗
║ Field: 48532 ± 892 nT    ║
║ Var: 1.8%                ║
╚══════════════════════════╝
```

## Terminal Output Enhancements

### Progress Messages

```
Collected 50 samples (5.2s) - Coverage: 37.5% - Latest: [-7200.0, -1050.0, 71250.0] nT
Collected 100 samples (10.5s) - Coverage: 62.5% - Latest: [3450.0, 8920.0, 69340.0] nT
Collected 150 samples (15.8s) - Coverage: 87.5% - Latest: [-5120.0, 6780.0, 72100.0] nT
```

### Disturbance Warnings

```
⚠ WARNING: High magnetic field variability (18.3%)
  Possible magnetic interference detected!
  Consider moving away from metal objects or electronics
```

### Environmental Summary

```
Environmental Assessment:
  Mean Field Strength: 48532.1 nT
  Field Variability: 1.8%
  Disturbance Warnings: 0
  ✓ Good environment - low magnetic interference
```

## Benefits

### For Users

1. **Visual confirmation** of coverage quality
2. **Real-time feedback** on data collection progress
3. **Immediate detection** of magnetic interference
4. **Guided calibration** ensures better results
5. **Confidence** in calibration quality before processing

### For Calibration Quality

1. **Uniform coverage** - users can see gaps and fill them
2. **Environmental awareness** - detects interference during collection
3. **Adequate sampling** - visual confirmation of coverage
4. **Reduced recalibration** - better first-time results

### Addresses Critic Recommendations

✅ **User Guidance**: Real-time feedback ensures good coverage  
✅ **Environmental Checks**: Monitors field variability and warns about disturbances  
✅ **Data Collection Quality**: Visual feedback improves uniform coverage  
✅ **Soft Iron Correction**: Better data → better regularized fit → better sphericity

## Performance Considerations

### Minimal Impact on Data Collection

- **Separate thread**: Visualization doesn't block BLE data reception
- **Thread locking**: Safe data access between threads
- **Update rate**: 10Hz (0.1s pause) is sufficient without lag
- **Optional**: Can be disabled for maximum performance

### Smart Downsampling (Anti-Crash Protection)

To prevent visualization crashes with high point density:

- **Display limit**: Maximum 500 points shown (configurable via `max_plot_points`)
- **Intelligent sampling**:
  - Keeps last 100 points (recent data always visible)
  - Uniformly samples older points to fill remaining slots
  - Ensures even distribution across entire dataset
- **Adaptive refresh**: Slows to 0.15s when dataset exceeds 1000 points
- **Larger points**: Point size increased (s=15) for better visibility with fewer points
- **Coverage accuracy**: All data points used for coverage calculation (not just displayed ones)
- **Status indicator**: Shows "Samples: N (showing M)" when downsampling active

This prevents matplotlib rendering performance degradation while maintaining:

- Accurate coverage tracking (uses ALL data)
- Clear visualization of data distribution
- Responsive real-time updates

### Memory Usage

- **Plotting overhead**: ~50MB for matplotlib figure
- **Data storage**: Minimal (just numpy arrays)
- **Update efficiency**: Only redraws changed elements

## Troubleshooting

### Visualization Not Appearing

```python
# Ensure matplotlib backend is configured
import matplotlib
matplotlib.use('TkAgg')  # or 'Qt5Agg'
```

### Performance Issues

- Disable visualization: Answer 'n' when prompted
- Reduce update rate: Change `plt.pause(0.1)` to `plt.pause(0.2)`
- Close other applications using GPU

### Thread Safety

- All data access uses `with self.lock:` for thread safety
- Visualization stops gracefully on Ctrl+C

## Future Enhancements

Potential improvements:

1. **Heatmap overlay**: Show spatial density of coverage
2. **Target indicators**: Highlight which octants need more data
3. **Quality prediction**: Estimate final calibration quality during collection
4. **Recording playback**: Review collection pattern after calibration
5. **Multi-sensor support**: Show all 3 IMUs simultaneously

## Code Structure

### Key Components

**CalibrationCollector class**:

- `__init__`: Added visualization and monitoring state
- `notification_handler`: Added environmental checks and coverage updates
- `start_visualization()`: Launches visualization thread
- `_visualization_loop()`: Main plotting loop
- `_estimate_coverage()`: Calculates sphere coverage
- `stop_collection()`: Gracefully closes visualization

**Visual Elements**:

- 3D scatter plot (data points)
- Wireframe sphere (reference)
- Two text boxes (status info)
- Dynamic axes scaling
- Color gradients

## Testing

### Validation Scenarios

1. ✅ Collect data with visualization enabled
2. ✅ Collect data with visualization disabled
3. ✅ Handle Ctrl+C gracefully
4. ✅ Detect environmental disturbances
5. ✅ Update coverage percentage correctly
6. ✅ Scale sphere appropriately
7. ✅ Thread-safe data access

### Example Session

```bash
$ python calibrate.py
# Enable visualization
# Rotate sensor through all orientations
# Watch coverage reach 87.5%
# Press Ctrl+C
# Visualization closes
# Calibration proceeds
# Validation shows EXCELLENT quality
```

## Conclusion

The real-time 3D visualization feature significantly improves magnetometer calibration by:

1. **Guiding users** to achieve uniform sphere coverage
2. **Detecting problems** during data collection (not after)
3. **Building confidence** through visual feedback
4. **Improving quality** through better data collection
5. **Preventing failures** by catching interference early

This directly addresses the critic.md recommendations for better user guidance and environmental checks, resulting in higher-quality calibrations and better soft iron correction outcomes.
