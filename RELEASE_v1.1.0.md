# Release v1.1.0 - Standby Mode Update

## 🎉 Major New Feature: VRAM Management

This release adds intelligent standby mode to automatically free GPU VRAM when your printer is idle!

## 🚀 What's New

### Standby Mode 💤
- **Automatically stop ML container** when printer is idle to free VRAM
- **Manual control** via web UI or MQTT
- **Auto-standby** after configurable timeout (default: 5 minutes)
- **Quick resume** in ~5-10 seconds when needed

### Enhanced Control
- New MQTT control topic for remote commands
- Beautiful web UI toggle for standby mode
- Real-time container status display
- ML container running/stopped indicators

### Smart VRAM Savings
- Completely stops ML API container (not just paused)
- Frees 2-4GB of VRAM depending on model
- Perfect for shared GPU systems
- Reduces power consumption and heat when idle

## 📋 Upgrade Instructions

### Step 1: Update Configuration

Add these new variables to your `.env` file:

```bash
# Standby Mode Configuration
MQTT_TOPIC_CONTROL=printer/control      # New control topic
STANDBY_MODE_ENABLED=true               # Enable standby feature
STANDBY_AUTO_TIMEOUT=300                # Auto-standby after 5 minutes
ML_API_CONTAINER_NAME=ml_api            # Container to control
```

### Step 2: Update Docker Compose

```bash
cd /path/to/print-monitor

# Pull latest changes
git pull origin main

# Or download new docker-compose.yml
wget https://raw.githubusercontent.com/YOUR-USERNAME/print-monitor/main/docker-compose.yml

# Restart services
docker-compose down
docker-compose up -d --build
```

### Step 3: Verify Installation

1. Check web UI at `http://your-server:8090`
2. Look for "Standby Mode (VRAM)" card
3. Click "Enter Standby" to test
4. Container should stop and VRAM be freed
5. Click "Resume Monitoring" to restart

## 🎮 How to Use

### Via Web UI
1. Open web dashboard
2. Find "Standby Mode (VRAM)" card
3. Click "Enter Standby" to free VRAM
4. Click "Resume Monitoring" when ready to print

### Via MQTT
```bash
# Enter standby mode
mosquitto_pub -h mqtt-broker -t "printer/control" -m '{"command":"standby"}'

# Resume monitoring
mosquitto_pub -h mqtt-broker -t "printer/control" -m '{"command":"active"}'
```

### Automatic Mode
Configure in `.env`:
```bash
STANDBY_AUTO_TIMEOUT=300  # Enter standby after 5 minutes idle
```

System automatically enters standby when:
- No print detected (confidence < 5%)
- No activity for configured timeout period
- Printer is in "monitoring" state

## 📊 Technical Details

### Container Management
- Uses Docker API to stop/start ML container
- Requires `/var/run/docker.sock` mount
- Container name must match `ML_API_CONTAINER_NAME` in config

### VRAM Savings
- ML API container fully stopped (not paused)
- All VRAM released back to system
- Other GPU processes can utilize freed memory
- Resume time: ~5-10 seconds (container restart)

### Status States
New `standby` status added:
- **standby**: ML container stopped, VRAM freed
- Status visible in web UI and MQTT heartbeats

### MQTT Messages
Heartbeat now includes:
```json
{
  "standby_mode": false,
  "standby_enabled": true,
  "ml_container_running": true
}
```

## ⚙️ Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `STANDBY_MODE_ENABLED` | `true` | Enable/disable standby feature |
| `STANDBY_AUTO_TIMEOUT` | `300` | Seconds of idle before auto-standby |
| `ML_API_CONTAINER_NAME` | `ml_api` | Name of ML container to control |
| `MQTT_TOPIC_CONTROL` | `printer/control` | Topic for control commands |

## 🐛 Known Issues

None at this time!

## 🔄 Reverting to v1.0.0

If you need to revert:
```bash
docker-compose down
git checkout v1.0.0
docker-compose up -d
```

## 💬 Feedback

Found a bug or have a suggestion? Open an issue on GitHub!

## 📚 Documentation

Full documentation updated at:
- README.md - Complete usage guide
- CHANGELOG.md - Detailed change log

---

**Full Changelog**: v1.0.0...v1.1.0

Made with ❤️ for the 3D printing community
