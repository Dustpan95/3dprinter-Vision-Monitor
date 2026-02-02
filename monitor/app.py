#!/usr/bin/env python3
"""
Print Monitor Service
Monitors 3D printer via RTSP stream using ML-based failure detection.
Publishes status updates via MQTT and provides a lightweight web UI.
"""

import os
import sys
import time
import json
import logging
import threading
import signal
from datetime import datetime
from typing import Optional, Dict, Any
from io import BytesIO
import base64

import cv2
import numpy as np
import requests
import paho.mqtt.client as mqtt
import docker
from flask import Flask, render_template, jsonify, request
from PIL import Image

# Configuration from environment variables
class Config:
    # RTSP
    RTSP_STREAM_URL = os.getenv('RTSP_STREAM_URL', 'rtsp://localhost:8554/stream')
    RTSP_TIMEOUT = int(os.getenv('RTSP_TIMEOUT', '10'))

    # MQTT
    MQTT_BROKER_HOST = os.getenv('MQTT_BROKER_HOST', 'localhost')
    MQTT_BROKER_PORT = int(os.getenv('MQTT_BROKER_PORT', '1883'))
    MQTT_USERNAME = os.getenv('MQTT_USERNAME', '')
    MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', '')
    MQTT_TOPIC_FAILURE = os.getenv('MQTT_TOPIC_FAILURE', 'printer/mk4s/failure')
    MQTT_TOPIC_HEARTBEAT = os.getenv('MQTT_TOPIC_HEARTBEAT', 'printer/mk4s/heartbeat')
    MQTT_TOPIC_CONTROL = os.getenv('MQTT_TOPIC_CONTROL', 'printer/mk4s/control')
    MQTT_HEARTBEAT_INTERVAL = int(os.getenv('MQTT_HEARTBEAT_INTERVAL', '30'))
    MQTT_CLIENT_ID = os.getenv('MQTT_CLIENT_ID', 'print-monitor')

    # Detection
    CHECK_INTERVAL_SECONDS = int(os.getenv('CHECK_INTERVAL_SECONDS', '10'))
    ML_API_URL = os.getenv('ML_API_URL', 'http://ml_api:3333')
    DETECTION_THRESHOLD = float(os.getenv('DETECTION_THRESHOLD', '0.6'))
    ML_API_TIMEOUT = int(os.getenv('ML_API_TIMEOUT', '15'))

    # Web UI - Internal port is always 8080, external port mapping is in docker-compose
    INTERNAL_PORT = 8080
    WEB_PORT = int(os.getenv('WEB_PORT', '8080'))  # Only used for logging external port

    # Standby Mode
    STANDBY_MODE_ENABLED = os.getenv('STANDBY_MODE_ENABLED', 'true').lower() == 'true'
    STANDBY_AUTO_TIMEOUT = int(os.getenv('STANDBY_AUTO_TIMEOUT', '300'))  # seconds
    ML_API_CONTAINER_NAME = os.getenv('ML_API_CONTAINER_NAME', 'ml_api')

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Setup logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/logs/print-monitor.log')
    ]
)
logger = logging.getLogger(__name__)

# Global state
class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.last_check_time: Optional[datetime] = None
        self.last_frame: Optional[np.ndarray] = None
        self.last_frame_base64: Optional[str] = None
        self.current_status: str = 'starting'  # starting, ok, failure, error, standby
        self.failure_detected: bool = False
        self.detection_confidence: float = 0.0
        self.error_message: Optional[str] = None
        self.mqtt_connected: bool = False
        self.ml_api_healthy: bool = False
        self.stream_connected: bool = False
        self.total_checks: int = 0
        self.failed_checks: int = 0
        # Standby mode
        self.standby_mode: bool = False
        self.last_activity_time: Optional[datetime] = datetime.now()
        self.ml_container_running: bool = True

    def update(self, **kwargs):
        with self.lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)

    def get_state_dict(self) -> Dict[str, Any]:
        with self.lock:
            return {
                'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
                'current_status': self.current_status,
                'failure_detected': self.failure_detected,
                'detection_confidence': self.detection_confidence,
                'error_message': self.error_message,
                'mqtt_connected': self.mqtt_connected,
                'ml_api_healthy': self.ml_api_healthy,
                'stream_connected': self.stream_connected,
                'total_checks': self.total_checks,
                'failed_checks': self.failed_checks,
                'last_frame': self.last_frame_base64,
                'standby_mode': self.standby_mode,
                'standby_enabled': Config.STANDBY_MODE_ENABLED,
                'ml_container_running': self.ml_container_running
            }

state = State()
shutdown_event = threading.Event()

# Docker Handler for ML API Container Control
class DockerHandler:
    def __init__(self):
        self.client: Optional[docker.DockerClient] = None
        self.container: Optional[docker.models.containers.Container] = None
        self.enabled = Config.STANDBY_MODE_ENABLED

        if not self.enabled:
            logger.info("Standby mode is DISABLED - ML container will always run")
            return

        try:
            self.client = docker.from_env()
            self.container = self.client.containers.get(Config.ML_API_CONTAINER_NAME)
            logger.info(f"✓ Docker handler initialized for container: {Config.ML_API_CONTAINER_NAME}")
        except docker.errors.DockerException as e:
            logger.error(f"✗ Failed to initialize Docker handler: {e}")
            logger.error("  → Standby mode will not be available")
            self.enabled = False
        except Exception as e:
            logger.error(f"✗ Unexpected error initializing Docker handler: {e}")
            self.enabled = False

    def is_container_running(self) -> bool:
        """Check if ML API container is running"""
        if not self.enabled or not self.container:
            return True

        try:
            self.container.reload()
            return self.container.status == 'running'
        except Exception as e:
            logger.error(f"Error checking container status: {e}")
            return False

    def stop_container(self) -> bool:
        """Stop the ML API container"""
        if not self.enabled or not self.container:
            logger.warning("Standby mode not enabled or container not available")
            return False

        try:
            logger.info(f"Stopping ML API container: {Config.ML_API_CONTAINER_NAME}")
            self.container.stop(timeout=10)
            state.update(ml_container_running=False, ml_api_healthy=False)
            logger.info("✓ ML API container stopped - VRAM freed")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to stop ML API container: {e}")
            return False

    def start_container(self) -> bool:
        """Start the ML API container"""
        if not self.enabled or not self.container:
            logger.warning("Standby mode not enabled or container not available")
            return False

        try:
            logger.info(f"Starting ML API container: {Config.ML_API_CONTAINER_NAME}")
            self.container.start()

            # Wait for container to be running
            for i in range(30):  # Wait up to 30 seconds
                self.container.reload()
                if self.container.status == 'running':
                    state.update(ml_container_running=True)
                    logger.info("✓ ML API container started - warming up...")
                    # Give it a few more seconds to fully initialize
                    time.sleep(5)
                    return True
                time.sleep(1)

            logger.error("ML API container did not start in time")
            return False
        except Exception as e:
            logger.error(f"✗ Failed to start ML API container: {e}")
            return False

    def enter_standby(self) -> bool:
        """Enter standby mode by stopping ML container"""
        if not self.enabled:
            logger.info("Standby mode is disabled")
            return False

        if state.standby_mode:
            logger.info("Already in standby mode")
            return True

        logger.info("Entering standby mode...")
        if self.stop_container():
            state.update(standby_mode=True, current_status='standby')
            logger.info("✓ Entered standby mode - VRAM freed")
            return True
        else:
            logger.error("✗ Failed to enter standby mode")
            return False

    def exit_standby(self) -> bool:
        """Exit standby mode by starting ML container"""
        if not self.enabled:
            logger.info("Standby mode is disabled")
            return False

        if not state.standby_mode:
            logger.info("Not in standby mode")
            return True

        logger.info("Exiting standby mode...")
        if self.start_container():
            state.update(
                standby_mode=False,
                current_status='monitoring',
                last_activity_time=datetime.now()
            )
            logger.info("✓ Exited standby mode - ML API ready")
            return True
        else:
            logger.error("✗ Failed to exit standby mode")
            return False

docker_handler = DockerHandler()

# MQTT Client Setup
class MQTTHandler:
    def __init__(self):
        self.client = mqtt.Client(client_id=Config.MQTT_CLIENT_ID, protocol=mqtt.MQTTv5)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.connected = False
        self.logged_error = False  # Track if we've already logged connection errors

        if Config.MQTT_USERNAME and Config.MQTT_PASSWORD:
            self.client.username_pw_set(Config.MQTT_USERNAME, Config.MQTT_PASSWORD)

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info("✓ Successfully connected to MQTT broker")
            self.connected = True
            self.logged_error = False
            state.update(mqtt_connected=True)

            # Subscribe to control topic if standby mode is enabled
            if Config.STANDBY_MODE_ENABLED:
                self.client.subscribe(Config.MQTT_TOPIC_CONTROL, qos=1)
                logger.info(f"✓ Subscribed to control topic: {Config.MQTT_TOPIC_CONTROL}")
        else:
            if not self.logged_error:
                logger.error(f"✗ MQTT CONNECTION ERROR: Failed with code {rc}")
                logger.error(f"  → Check MQTT_BROKER_HOST and MQTT_BROKER_PORT in .env file")
                logger.error(f"  → Broker: {Config.MQTT_BROKER_HOST}:{Config.MQTT_BROKER_PORT}")
                self.logged_error = True
            self.connected = False
            state.update(mqtt_connected=False)

    def _on_disconnect(self, client, userdata, rc, properties=None):
        logger.warning(f"Disconnected from MQTT broker with code: {rc}")
        self.connected = False
        state.update(mqtt_connected=False)

    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages (control commands)"""
        try:
            payload = json.loads(msg.payload.decode())
            command = payload.get('command', '').lower()

            logger.info(f"Received control command: {command}")

            if command == 'standby':
                docker_handler.enter_standby()
            elif command == 'active':
                docker_handler.exit_standby()
            else:
                logger.warning(f"Unknown command received: {command}")

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in control message: {msg.payload}")
        except Exception as e:
            logger.error(f"Error processing control message: {e}")

    def connect(self):
        try:
            self.client.connect(Config.MQTT_BROKER_HOST, Config.MQTT_BROKER_PORT, 60)
            self.client.loop_start()
        except Exception as e:
            if not self.logged_error:
                logger.error(f"✗ MQTT CONFIGURATION ERROR: {e}")
                logger.error(f"  → Check MQTT_BROKER_HOST and MQTT_BROKER_PORT in .env file")
                logger.error(f"  → Current config: {Config.MQTT_BROKER_HOST}:{Config.MQTT_BROKER_PORT}")
                logger.error(f"  → Ensure MQTT broker is running and accessible")
                self.logged_error = True
            state.update(mqtt_connected=False)

    def publish(self, topic: str, message: Dict[str, Any], qos: int = 1):
        if not self.connected:
            logger.debug("Cannot publish: MQTT not connected")
            return False

        try:
            payload = json.dumps(message)
            result = self.client.publish(topic, payload, qos=qos)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"Published to {topic}: {payload}")
                return True
            else:
                logger.error(f"Failed to publish to {topic}: {result.rc}")
                return False
        except Exception as e:
            logger.error(f"Error publishing to MQTT: {e}")
            return False

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

mqtt_handler = MQTTHandler()

# RTSP Stream Handler
class RTSPStreamHandler:
    def __init__(self):
        self.cap: Optional[cv2.VideoCapture] = None
        self.last_connection_attempt = 0
        self.connection_retry_delay = 60  # seconds - retry every minute
        self.logged_error = False  # Track if we've already logged the error

    def connect(self) -> bool:
        """Connect to RTSP stream with retry logic"""
        current_time = time.time()
        if current_time - self.last_connection_attempt < self.connection_retry_delay:
            return False

        self.last_connection_attempt = current_time

        try:
            if not self.logged_error:
                logger.info(f"Attempting to connect to RTSP stream: {Config.RTSP_STREAM_URL}")
            self.cap = cv2.VideoCapture(Config.RTSP_STREAM_URL, cv2.CAP_FFMPEG)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if self.cap.isOpened():
                logger.info("✓ Successfully connected to RTSP stream")
                state.update(stream_connected=True, error_message=None)
                self.logged_error = False
                return True
            else:
                if not self.logged_error:
                    logger.error("✗ RTSP CONFIGURATION ERROR: Cannot connect to RTSP stream")
                    logger.error(f"  → Check RTSP_STREAM_URL in .env file: {Config.RTSP_STREAM_URL}")
                    logger.error(f"  → Will retry every {self.connection_retry_delay} seconds")
                    self.logged_error = True
                state.update(stream_connected=False, error_message=f"Cannot connect to RTSP stream: {Config.RTSP_STREAM_URL}")
                return False
        except Exception as e:
            if not self.logged_error:
                logger.error(f"✗ RTSP CONNECTION ERROR: {e}")
                logger.error(f"  → Check RTSP_STREAM_URL in .env file: {Config.RTSP_STREAM_URL}")
                logger.error(f"  → Will retry every {self.connection_retry_delay} seconds")
                self.logged_error = True
            state.update(stream_connected=False, error_message=str(e))
            return False

    def get_frame(self) -> Optional[np.ndarray]:
        """Capture a single frame from the stream"""
        if not self.cap or not self.cap.isOpened():
            if not self.connect():
                return None

        try:
            ret, frame = self.cap.read()
            if ret and frame is not None and frame.size > 0:
                return frame
            else:
                logger.warning("Failed to read frame from stream")
                state.update(stream_connected=False)
                self.disconnect()
                return None
        except Exception as e:
            logger.error(f"Error reading frame: {e}")
            self.disconnect()
            return None

    def disconnect(self):
        """Disconnect from RTSP stream"""
        if self.cap:
            self.cap.release()
            self.cap = None
        state.update(stream_connected=False)

stream_handler = RTSPStreamHandler()

# ML API Handler
class MLAPIHandler:
    def __init__(self):
        self.session = requests.Session()
        self.last_health_check = 0
        self.health_check_interval = 30  # seconds

    def check_health(self) -> bool:
        """Check if ML API is healthy"""
        current_time = time.time()
        if current_time - self.last_health_check < self.health_check_interval:
            return state.ml_api_healthy

        self.last_health_check = current_time

        try:
            response = self.session.get(
                f"{Config.ML_API_URL}/hc/",
                timeout=5
            )
            healthy = response.status_code == 200 and response.text == 'ok'
            state.update(ml_api_healthy=healthy)
            if healthy:
                logger.debug("ML API health check passed")
            else:
                logger.warning(f"ML API health check failed: {response.status_code} - {response.text}")
            return healthy
        except Exception as e:
            logger.error(f"ML API health check error: {e}")
            state.update(ml_api_healthy=False)
            return False

    def analyze_frame(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        """Send frame to ML API for analysis"""
        # Check health for monitoring purposes
        self.check_health()

        try:
            # The ML API expects a GET request with an img URL parameter
            # We serve the frame from our own Flask server at /latest_frame.jpg
            frame_url = f"http://print-monitor:8080/latest_frame.jpg"

            # Send to ML API
            logger.debug("Sending frame URL to ML API for analysis")
            response = self.session.get(
                f"{Config.ML_API_URL}/p/",
                params={'img': frame_url},
                timeout=Config.ML_API_TIMEOUT
            )

            if response.status_code == 200:
                result = response.json()
                logger.debug(f"ML API response: {result}")
                return result
            else:
                logger.error(f"ML API returned error: {response.status_code} - {response.text}")
                return None

        except requests.exceptions.Timeout:
            logger.error("ML API request timed out")
            return None
        except Exception as e:
            logger.error(f"Error analyzing frame with ML API: {e}")
            return None

ml_api_handler = MLAPIHandler()

# Frame to base64 for web display
def frame_to_base64(frame: np.ndarray) -> str:
    """Convert OpenCV frame to base64 encoded JPEG"""
    try:
        success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if success:
            return base64.b64encode(buffer).decode('utf-8')
    except Exception as e:
        logger.error(f"Error converting frame to base64: {e}")
    return ""

# Main monitoring loop
def monitor_loop():
    """Main monitoring loop that checks frames periodically"""
    logger.info("Starting monitor loop")

    while not shutdown_event.is_set():
        try:
            # Check if in standby mode
            if state.standby_mode:
                logger.debug("In standby mode - skipping ML checks")
                time.sleep(Config.CHECK_INTERVAL_SECONDS)
                continue

            # Get frame from stream
            frame = stream_handler.get_frame()

            if frame is None:
                logger.debug("No frame available, will retry")
                state.update(
                    current_status='error',
                    error_message='Cannot capture frame from stream'
                )
                time.sleep(Config.CHECK_INTERVAL_SECONDS)
                continue

            # Update state with frame
            frame_b64 = frame_to_base64(frame)
            state.update(
                last_frame=frame,
                last_frame_base64=frame_b64,
                last_check_time=datetime.now()
            )

            # Analyze frame with ML API
            result = ml_api_handler.analyze_frame(frame)

            if result is None:
                logger.warning("ML API analysis failed")
                state.update(
                    current_status='error',
                    error_message='ML API analysis failed',
                    failed_checks=state.failed_checks + 1
                )
            else:
                # Parse ML API response
                # Obico ML API returns: {"detections": [...], "classes": [...]}
                # We check if there are any detections above threshold
                detections = result.get('detections', [])

                max_confidence = 0.0
                failure_detected = False

                if detections:
                    # Get maximum confidence from detections
                    for detection in detections:
                        if isinstance(detection, list) and len(detection) >= 5:
                            confidence = detection[4]  # confidence is typically 5th element
                            max_confidence = max(max_confidence, confidence)
                            if confidence >= Config.DETECTION_THRESHOLD:
                                failure_detected = True

                state.update(
                    total_checks=state.total_checks + 1,
                    detection_confidence=max_confidence,
                    failure_detected=failure_detected
                )

                if failure_detected:
                    logger.warning(f"FAILURE DETECTED! Confidence: {max_confidence:.2%}")
                    state.update(
                        current_status='failure',
                        error_message=None,
                        last_activity_time=datetime.now()
                    )

                    # Publish failure to MQTT
                    failure_message = {
                        'status': 'failure',
                        'confidence': max_confidence,
                        'timestamp': datetime.now().isoformat(),
                        'detections': detections
                    }
                    mqtt_handler.publish(Config.MQTT_TOPIC_FAILURE, failure_message, qos=2)
                elif max_confidence < 0.05:
                    # Very low confidence - likely no print or nothing significant
                    logger.info(f"Monitoring - No significant activity detected (Confidence: {max_confidence:.2%})")
                    state.update(current_status='monitoring', error_message=None)

                    # Check for auto-standby
                    if Config.STANDBY_MODE_ENABLED and Config.STANDBY_AUTO_TIMEOUT > 0:
                        if state.last_activity_time:
                            time_since_activity = (datetime.now() - state.last_activity_time).total_seconds()
                            if time_since_activity > Config.STANDBY_AUTO_TIMEOUT:
                                logger.info(f"Auto-standby: {int(time_since_activity)}s since last activity (threshold: {Config.STANDBY_AUTO_TIMEOUT}s)")
                                docker_handler.enter_standby()
                else:
                    # Low-medium confidence - print appears OK
                    logger.info(f"Print OK - Confidence: {max_confidence:.2%}")
                    state.update(
                        current_status='ok',
                        error_message=None,
                        last_activity_time=datetime.now()
                    )

            # Wait for next check
            time.sleep(Config.CHECK_INTERVAL_SECONDS)

        except Exception as e:
            logger.error(f"Error in monitor loop: {e}", exc_info=True)
            state.update(
                current_status='error',
                error_message=str(e),
                failed_checks=state.failed_checks + 1
            )
            time.sleep(Config.CHECK_INTERVAL_SECONDS)

    logger.info("Monitor loop stopped")

# Heartbeat loop
def heartbeat_loop():
    """Send periodic heartbeat messages via MQTT"""
    logger.info("Starting heartbeat loop")

    while not shutdown_event.is_set():
        try:
            heartbeat_message = {
                'status': state.current_status,
                'timestamp': datetime.now().isoformat(),
                'mqtt_connected': state.mqtt_connected,
                'ml_api_healthy': state.ml_api_healthy,
                'stream_connected': state.stream_connected,
                'total_checks': state.total_checks,
                'failed_checks': state.failed_checks,
                'detection_confidence': state.detection_confidence,
                'standby_mode': state.standby_mode,
                'standby_enabled': Config.STANDBY_MODE_ENABLED,
                'ml_container_running': state.ml_container_running
            }

            mqtt_handler.publish(Config.MQTT_TOPIC_HEARTBEAT, heartbeat_message, qos=0)
            logger.debug(f"Heartbeat sent: {state.current_status} (standby: {state.standby_mode})")

        except Exception as e:
            logger.error(f"Error in heartbeat loop: {e}")

        # Wait for next heartbeat
        shutdown_event.wait(Config.MQTT_HEARTBEAT_INTERVAL)

    logger.info("Heartbeat loop stopped")

# Flask Web UI
app = Flask(__name__)

@app.route('/')
def index():
    """Serve the main web UI"""
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    """API endpoint for current status"""
    return jsonify(state.get_state_dict())

@app.route('/latest_frame.jpg')
def latest_frame():
    """Serve the latest frame as JPEG"""
    if state.last_frame is not None:
        success, buffer = cv2.imencode('.jpg', state.last_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if success:
            from flask import send_file
            from io import BytesIO
            return send_file(BytesIO(buffer), mimetype='image/jpeg')
    return jsonify({'error': 'No frame available'}), 404

@app.route('/health')
def health():
    """Health check endpoint for Docker"""
    if state.current_status in ['ok', 'failure', 'starting', 'monitoring', 'standby']:
        return jsonify({'status': 'healthy'}), 200
    else:
        return jsonify({'status': 'unhealthy', 'error': state.error_message}), 503

@app.route('/api/standby/enable', methods=['POST'])
def api_standby_enable():
    """Enable standby mode"""
    if not Config.STANDBY_MODE_ENABLED:
        return jsonify({'error': 'Standby mode is disabled in configuration'}), 400

    success = docker_handler.enter_standby()
    if success:
        return jsonify({'success': True, 'standby_mode': True})
    else:
        return jsonify({'error': 'Failed to enter standby mode'}), 500

@app.route('/api/standby/disable', methods=['POST'])
def api_standby_disable():
    """Disable standby mode"""
    if not Config.STANDBY_MODE_ENABLED:
        return jsonify({'error': 'Standby mode is disabled in configuration'}), 400

    success = docker_handler.exit_standby()
    if success:
        return jsonify({'success': True, 'standby_mode': False})
    else:
        return jsonify({'error': 'Failed to exit standby mode'}), 500

@app.route('/api/standby/status')
def api_standby_status():
    """Get standby mode status"""
    return jsonify({
        'standby_mode': state.standby_mode,
        'standby_enabled': Config.STANDBY_MODE_ENABLED,
        'auto_timeout': Config.STANDBY_AUTO_TIMEOUT,
        'ml_container_running': state.ml_container_running
    })

def run_flask():
    """Run Flask server"""
    logger.info(f"Starting web server on internal port {Config.INTERNAL_PORT} (external: {Config.WEB_PORT})")
    app.run(host='0.0.0.0', port=Config.INTERNAL_PORT, debug=False, threaded=True)

# Signal handlers
def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, shutting down...")
    shutdown_event.set()

# Main entry point
def main():
    """Main entry point for the application"""
    logger.info("=" * 80)
    logger.info("Print Monitor Service Starting")
    logger.info("=" * 80)

    # Configuration validation and warnings
    config_warnings = []
    if Config.RTSP_STREAM_URL == 'rtsp://localhost:8554/stream':
        config_warnings.append("RTSP_STREAM_URL is set to default - you need to configure your camera stream")
    if Config.MQTT_BROKER_HOST == 'localhost':
        config_warnings.append("MQTT_BROKER_HOST is set to localhost - ensure your MQTT broker is accessible")

    if config_warnings:
        logger.warning("⚠ CONFIGURATION WARNINGS:")
        for warning in config_warnings:
            logger.warning(f"  → {warning}")
        logger.warning("  → Edit .env file and restart the service to update configuration")
        logger.warning("=" * 80)

    logger.info(f"RTSP Stream: {Config.RTSP_STREAM_URL}")
    logger.info(f"ML API: {Config.ML_API_URL}")
    logger.info(f"MQTT Broker: {Config.MQTT_BROKER_HOST}:{Config.MQTT_BROKER_PORT}")
    logger.info(f"Check Interval: {Config.CHECK_INTERVAL_SECONDS}s")
    logger.info(f"Heartbeat Interval: {Config.MQTT_HEARTBEAT_INTERVAL}s")
    logger.info(f"Detection Threshold: {Config.DETECTION_THRESHOLD}")
    logger.info(f"Web UI Port: {Config.WEB_PORT}")
    logger.info(f"Standby Mode: {'ENABLED' if Config.STANDBY_MODE_ENABLED else 'DISABLED'}")
    if Config.STANDBY_MODE_ENABLED:
        logger.info(f"  → Auto-Standby Timeout: {Config.STANDBY_AUTO_TIMEOUT}s ({Config.STANDBY_AUTO_TIMEOUT/60:.1f} min)")
        logger.info(f"  → ML Container: {Config.ML_API_CONTAINER_NAME}")
    logger.info("=" * 80)

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Connect to MQTT
    mqtt_handler.connect()

    # Start threads
    monitor_thread = threading.Thread(target=monitor_loop, name="MonitorThread", daemon=True)
    heartbeat_thread = threading.Thread(target=heartbeat_loop, name="HeartbeatThread", daemon=True)
    flask_thread = threading.Thread(target=run_flask, name="FlaskThread", daemon=True)

    monitor_thread.start()
    heartbeat_thread.start()
    flask_thread.start()

    logger.info("All threads started successfully")

    # Wait for shutdown signal
    try:
        while not shutdown_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        shutdown_event.set()

    # Cleanup
    logger.info("Shutting down...")
    stream_handler.disconnect()
    mqtt_handler.disconnect()

    # Wait for threads to finish
    monitor_thread.join(timeout=5)
    heartbeat_thread.join(timeout=5)

    logger.info("Shutdown complete")

if __name__ == '__main__':
    main()
