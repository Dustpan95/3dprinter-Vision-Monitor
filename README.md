# 3D Print Monitor with ML Failure Detection

AI-powered 3D print failure detection system using Obico/Spaghetti Detective ML model with MQTT notifications and web UI.

[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

🤖 **ML-Based Detection** - Uses proven Obico/Spaghetti Detective model
📹 **RTSP Support** - Works with any RTSP camera stream
📡 **MQTT Integration** - Real-time notifications via MQTT
🌐 **Web UI** - Clean, lightweight monitoring dashboard
⚡ **GPU Accelerated** - NVIDIA GPU support for ML inference
🔔 **Smart Status** - Distinguishes between idle, printing, and failures
💤 **Standby Mode (v2.0)** - Automatically unload ML model to free VRAM when idle
🎛️ **MQTT/Web Control** - Toggle standby mode remotely or via web interface
⏰ **Auto-Standby** - Automatically enter standby after configurable timeout

## Quick Start

### Prerequisites

- Docker & Docker Compose
- NVIDIA GPU (optional but recommended for better performance)
- NVIDIA Container Toolkit (if using GPU)
- RTSP camera pointed at your 3D printer
- MQTT broker (Mosquitto, etc.)

### Installation

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd print-monitor
```

2. **Configure your settings**
```bash
cp .env.example .env
nano .env
```

Edit the following in `.env`:
- `RTSP_STREAM_URL` - Your camera's RTSP URL
- `MQTT_BROKER_HOST` - Your MQTT broker IP/hostname
- `MQTT_BROKER_PORT` - MQTT port (default: 1883)
- `MQTT_USERNAME` and `MQTT_PASSWORD` - MQTT credentials
- `MQTT_TOPIC_FAILURE`, `MQTT_TOPIC_HEARTBEAT`, `MQTT_TOPIC_CONTROL` - Custom topics
- `STANDBY_MODE_ENABLED` - Enable/disable standby mode (default: true)
- `STANDBY_AUTO_TIMEOUT` - Auto-standby timeout in seconds (default: 300)

3. **Start the services**
```bash
docker-compose up -d
```

4. **Access the Web UI**
```
http://your-server-ip:8090
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RTSP_STREAM_URL` | Camera RTSP stream URL | Required |
| `MQTT_BROKER_HOST` | MQTT broker hostname/IP | Required |
| `MQTT_BROKER_PORT` | MQTT broker port | 1883 |
| `MQTT_USERNAME` | MQTT username (optional) | - |
| `MQTT_PASSWORD` | MQTT password (optional) | - |
| `MQTT_TOPIC_FAILURE` | Topic for failure alerts | printer/failure |
| `MQTT_TOPIC_HEARTBEAT` | Topic for status updates | printer/heartbeat |
| `MQTT_TOPIC_CONTROL` | Topic for control commands | printer/control |
| `CHECK_INTERVAL_SECONDS` | Frame check interval | 10 |
| `DETECTION_THRESHOLD` | Failure threshold (0.0-1.0) | 0.6 |
| `WEB_PORT` | Web UI port | 8090 |
| `MOTION_INTENSITY_THRESHOLD` | Min pixel intensity diff to count as changed | 30 |
| `MOTION_PIXEL_THRESHOLD` | Min changed pixels to register as motion | 500 |
| `IDLE_TIMEOUT` | Seconds without motion before going idle | 60 |
| `STANDBY_MODE_ENABLED` | Enable standby mode | true |
| `STANDBY_AUTO_TIMEOUT` | Auto-standby timeout (seconds) | 300 |
| `ML_API_CONTAINER_NAME` | ML container name | ml_api |

### Detection Threshold

The `DETECTION_THRESHOLD` controls sensitivity:
- **Lower (0.4-0.5)**: More sensitive, may have false positives
- **Default (0.6)**: Balanced detection
- **Higher (0.7-0.8)**: Less sensitive, fewer false alarms

### Motion Detection

The monitor uses frame-to-frame pixel differencing to determine whether the printer is actively printing or idle. This avoids the need for a printer API and works with any printer.

- **`MOTION_INTENSITY_THRESHOLD`** — Minimum pixel value difference (0-255) to count a pixel as "changed". Higher values ignore subtle lighting changes. Default: `30`
- **`MOTION_PIXEL_THRESHOLD`** — Minimum number of changed pixels to consider motion detected. Higher values require more movement. Default: `500`
- **`IDLE_TIMEOUT`** — How many seconds without motion before the status switches to idle. Default: `60`

When idle, ML failure checks are skipped. If motion is detected while in standby, the monitor automatically exits standby and resumes ML checks.

### Standby Mode (VRAM Management) 💤

**NEW in v2.0!** Save GPU VRAM when not actively printing.

When enabled, standby mode stops the ML API container to free VRAM. Perfect for:
- Shared GPU systems running multiple services
- Saving power when printer is idle
- Reducing heat/noise from GPU

**Features:**
- **Manual Control**: Toggle via web UI or MQTT
- **Auto-Standby**: Automatically enter standby after no activity (default: 5 minutes)
- **Quick Resume**: ML container restarts in ~5-10 seconds when needed

**Configuration:**
```bash
STANDBY_MODE_ENABLED=true        # Enable standby feature
STANDBY_AUTO_TIMEOUT=300         # Auto-standby after 300 seconds (5 min) of idle
ML_API_CONTAINER_NAME=ml_api     # Container name to control
```

**Control via MQTT:**
```bash
# Enter standby mode
mosquitto_pub -h broker-ip -t "printer/control" -m '{"command":"standby"}'

# Resume monitoring
mosquitto_pub -h broker-ip -t "printer/control" -m '{"command":"active"}'
```

**Control via Web UI:**
- Click "Enter Standby" button in the web dashboard
- Or "Resume Monitoring" to exit standby

**Disable Standby Mode:**
Set `STANDBY_MODE_ENABLED=false` to disable standby features entirely. ML container will always run.

## Status States

| Status | Meaning | When |
|--------|---------|------|
| 🔵 Starting | Initializing | First 5-10 seconds |
| ⚫ Idle | No motion detected | Printer idle, ML checks skipped |
| 🟢 OK | Print running normally | Motion detected, no failure |
| 🔴 Failure | Print failure detected | Failure confidence > threshold |
| 🟠 Error | System error | Camera/MQTT/ML API issue |
| 💤 Standby | VRAM freed | ML container stopped to save resources |

## MQTT Messages

### Heartbeat (every 30 seconds)
Topic: `MQTT_TOPIC_HEARTBEAT`

```json
{
  "status": "ok",
  "timestamp": "2026-02-02T12:00:00Z",
  "mqtt_connected": true,
  "ml_api_healthy": true,
  "stream_connected": true,
  "total_checks": 150,
  "failed_checks": 0,
  "detection_confidence": 0.25,
  "standby_mode": false,
  "standby_enabled": true,
  "ml_container_running": true
}
```

### Failure Alert (when detected)
Topic: `MQTT_TOPIC_FAILURE`

```json
{
  "status": "failure",
  "confidence": 0.85,
  "timestamp": "2026-02-02T12:00:00Z",
  "detections": [[0.85, [512, 384, 128, 96]]]
}
```

### Control Commands (v2.0+)
Topic: `MQTT_TOPIC_CONTROL`

Send commands to control the monitor:

```json
{"command": "standby"}  // Enter standby mode (stop ML container)
{"command": "active"}   // Exit standby mode (start ML container)
```

## Integration Examples

### Home Assistant

```yaml
mqtt:
  sensor:
    - name: "3D Printer Status"
      state_topic: "printer/heartbeat"
      value_template: "{{ value_json.status }}"

automation:
  - alias: "Print Failure Alert"
    trigger:
      platform: mqtt
      topic: "printer/failure"
    action:
      service: notify.mobile_app
      data:
        message: "Print failure! Confidence: {{ trigger.payload_json.confidence * 100 }}%"
        title: "🚨 Printer Alert"
```

### Node-RED

Use MQTT In node to subscribe to topics and create custom flows.

## Architecture

```
┌─────────────┐      RTSP       ┌──────────────┐
│   Camera    │◄────────────────┤Print Monitor │
└─────────────┘                 │   Service    │
                                └──────┬───────┘
                      ┌────────────────┼────────────────┐
                      │                │                │
                      ▼                ▼                ▼
                ┌──────────┐     ┌─────────┐     ┌──────────┐
                │ ML API   │     │  MQTT   │     │  Web UI  │
                │ (Obico)  │     │ Broker  │     │  :8090   │
                └──────────┘     └─────────┘     └──────────┘
```

## Troubleshooting

### RTSP Stream Not Connecting
- Verify RTSP URL is correct (test with VLC)
- Check network connectivity to camera
- Ensure camera supports RTSP
- Try different stream quality settings

### ML API Not Working
- Verify NVIDIA runtime is available: `docker info | grep -i runtime`
- Check GPU is detected: `nvidia-smi`
- View ML API logs: `docker-compose logs ml_api`

### MQTT Not Connecting
- Verify broker is running and accessible
- Check credentials are correct
- Test with mosquitto_pub/sub
- Check firewall rules

### No Frames Displayed
- Verify RTSP stream is working
- Check logs: `docker-compose logs print-monitor`
- Ensure sufficient network bandwidth

## Performance

- **CPU**: Low usage for frame capture
- **GPU**: ML inference runs on NVIDIA GPU
- **RAM**: ~500MB per container
- **Network**: ~1 frame every 10 seconds
- **Storage**: Minimal (no video recording)

## Development

### Building

```bash
docker-compose build
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f print-monitor
```

### Restart After Changes

```bash
docker-compose restart print-monitor
```

## License

MIT License - See LICENSE file for details

## Credits

- ML Model: [Obico](https://www.obico.io/) (formerly Spaghetti Detective)
- Inspired by the 3D printing community's need for automated monitoring

## Support

For issues, questions, or contributions, please open an issue on GitHub.

## Acknowledgments

Built with:
- [Obico ML API](https://github.com/TheSpaghettiDetective/obico-server)
- Python, Flask, OpenCV
- Docker, NVIDIA Container Toolkit
- MQTT (Paho)

---

Made with ❤️ for the 3D printing community
