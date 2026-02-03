# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v1.1.0.html).

## [1.1.1] - 2026-02-03

### Fixed
- **ML detection parsing**: Obico ML API returns detections as `[name, confidence, bbox]` (3 elements). Was incorrectly checking for 5 elements and reading confidence from index 4. Now correctly reads from index 1.
- **RTSP frame staleness**: OpenCV buffers RTSP frames internally, causing stale images to be served when only reading every 10 seconds. Replaced single-read approach with a background reader thread that continuously consumes frames, so `get_frame()` always returns the latest.
- **Status logic**: Failure-only ML model was mapped to a 3-tier confidence system (idle/ok/failure), but the model only outputs on failure — a normal print and an empty bed both returned 0%. Replaced with motion-based detection: motion detected = printing, no motion = idle. ML checks only run when active.

### Added
- **Motion detection**: Frame-to-frame pixel differencing determines whether the printer is actively printing or idle. Configurable via `MOTION_INTENSITY_THRESHOLD`, `MOTION_PIXEL_THRESHOLD`, and `IDLE_TIMEOUT`.
- **Timestamp overlay**: Live timestamp drawn on each frame for visual confirmation the feed is updating.
- **Auto-standby via motion**: Auto-standby now triggers based on idle state from motion detection instead of the broken confidence threshold. Motion detected while in standby automatically resumes monitoring.

### Changed
- Renamed "Detection Confidence" to "Failure Confidence" in web UI for clarity — the value represents how confident the model is that a failure is occurring, not general print detection.
- Replaced `monitoring` status with `idle` status in UI and health checks.

---

## [1.1.0] - 2026-02-02

### Added
- **Standby Mode**: Automatically stop/start ML API container to free VRAM when idle
  - Manual control via web UI toggle button
  - MQTT control commands (`standby` and `active`)
  - Auto-standby feature with configurable timeout
  - New ENV variables: `STANDBY_MODE_ENABLED`, `STANDBY_AUTO_TIMEOUT`, `ML_API_CONTAINER_NAME`
- **Enhanced Web UI**:
  - Standby mode controls and status indicator
  - ML container status display
  - New purple standby status indicator
- **MQTT Control Topic**: New `MQTT_TOPIC_CONTROL` for sending commands
- **Docker Integration**: Container management via Docker API
  - Requires `/var/run/docker.sock` mount
  - Python docker library added to dependencies

### Changed
- Updated state management to track standby mode and container status
- Enhanced heartbeat messages to include standby state
- Monitoring loop now respects standby mode (skips ML checks when in standby)
- Health check endpoint now considers standby as healthy state
- Updated documentation with standby mode usage and examples

### Technical Details
- Added Docker API client for container control
- ML API container stops completely to free VRAM (not just paused)
- Container restart takes ~5-10 seconds when exiting standby
- Auto-standby triggers after configured period of low confidence (<5%)
- Last activity timestamp tracked to determine auto-standby eligibility

### Breaking Changes
- ML API container name changed from `print-monitor-ml-api` to `ml_api` for consistency
- Docker socket mount required for standby mode functionality

### Dependencies
- Added: `docker==7.0.0`

---

## [1.0.0] - 2026-02-01

### Added
- Initial release of Print Monitor
- ML-based print failure detection using Obico/Spaghetti Detective model
- RTSP camera stream support
- MQTT integration for real-time notifications
  - Heartbeat messages every 30 seconds
  - Failure alerts when detected
- Web UI dashboard
  - Live camera feed display
  - Status indicators
  - Detection confidence display
  - System health monitoring
- Smart status detection:
  - Starting, Monitoring, OK, Failure, Error states
  - Confidence-based thresholds
- Docker Compose deployment
- GPU acceleration support via NVIDIA Container Toolkit
- Configurable via environment variables
- Health check endpoint for Docker monitoring
- Comprehensive logging with rotation

### Features
- Automatic reconnection for RTSP/MQTT
- Retry logic for failed connections
- Frame buffering and efficient capture
- Base64 frame encoding for web display
- Statistics tracking (total checks, failed checks)
- Error message reporting
- Responsive web design for mobile/desktop

---

## Release Notes

### Upgrading to v1.1.0

1. **Update `.env` file** with new parameters:
   ```bash
   # Add these lines to your existing .env
   MQTT_TOPIC_CONTROL=printer/control
   STANDBY_MODE_ENABLED=true
   STANDBY_AUTO_TIMEOUT=300
   ML_API_CONTAINER_NAME=ml_api
   ```

2. **Update docker-compose.yml**:
   - Pull latest version from repository
   - ML API container name changed to `ml_api`
   - Docker socket mount added for standby mode

3. **Restart services**:
   ```bash
   docker-compose down
   docker-compose pull
   docker-compose up -d
   ```

### New in v1.1.0: Standby Mode

Save GPU VRAM when your printer is idle! The new standby mode completely stops the ML API container, freeing all VRAM until you need it again.

**Control Options:**
- **Web UI**: Click the "Enter Standby" button
- **MQTT**: Send `{"command":"standby"}` to control topic
- **Automatic**: Configure `STANDBY_AUTO_TIMEOUT` for hands-free operation

**Perfect for:**
- Multi-user GPU systems
- Power saving when idle
- Reducing heat/noise during long idle periods

**Quick Stats:**
- VRAM freed: ~2-4GB (depending on model)
- Resume time: ~5-10 seconds
- Auto-standby default: 5 minutes of idle

---

[1.1.1]: https://github.com/Dustpan95/3dprinter-Vision-Monitor/releases/tag/v1.1.1
[1.1.0]: https://github.com/Dustpan95/3dprinter-Vision-Monitor/releases/tag/v1.1.0
[1.0.0]: https://github.com/Dustpan95/3dprinter-Vision-Monitor/releases/tag/v1.0.0
