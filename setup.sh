#!/bin/bash
# Quick setup script for Print Monitor

set -e

echo "=========================================="
echo "  3D Print Monitor - Quick Setup"
echo "=========================================="
echo ""

# Check if .env exists
if [ -f ".env" ]; then
    echo "⚠️  .env file already exists!"
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled. Edit .env manually or delete it to run setup again."
        exit 1
    fi
fi

# Copy example env
cp .env.example .env
echo "✓ Created .env file from template"

# Prompt for configuration
echo ""
echo "Please provide your configuration:"
echo ""

read -p "RTSP Stream URL (e.g., rtsp://user:pass@192.168.1.100:554/stream): " rtsp_url
read -p "MQTT Broker Host (e.g., 192.168.1.50): " mqtt_host
read -p "MQTT Broker Port [1883]: " mqtt_port
mqtt_port=${mqtt_port:-1883}
read -p "MQTT Username (leave empty if none): " mqtt_user
read -sp "MQTT Password (leave empty if none): " mqtt_pass
echo ""
read -p "MQTT Topic Prefix [printer]: " topic_prefix
topic_prefix=${topic_prefix:-printer}
read -p "Web UI Port [8090]: " web_port
web_port=${web_port:-8090}

# Update .env file
sed -i "s|RTSP_STREAM_URL=.*|RTSP_STREAM_URL=$rtsp_url|" .env
sed -i "s|MQTT_BROKER_HOST=.*|MQTT_BROKER_HOST=$mqtt_host|" .env
sed -i "s|MQTT_BROKER_PORT=.*|MQTT_BROKER_PORT=$mqtt_port|" .env
sed -i "s|MQTT_USERNAME=.*|MQTT_USERNAME=$mqtt_user|" .env
sed -i "s|MQTT_PASSWORD=.*|MQTT_PASSWORD=$mqtt_pass|" .env
sed -i "s|MQTT_TOPIC_FAILURE=.*|MQTT_TOPIC_FAILURE=$topic_prefix/failure|" .env
sed -i "s|MQTT_TOPIC_HEARTBEAT=.*|MQTT_TOPIC_HEARTBEAT=$topic_prefix/heartbeat|" .env
sed -i "s|WEB_PORT=.*|WEB_PORT=$web_port|" .env

echo ""
echo "✓ Configuration saved to .env"
echo ""
echo "Starting services..."
docker-compose up -d

echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "Services are starting up..."
echo "Web UI will be available at: http://$(hostname -I | awk '{print $1}'):$web_port"
echo ""
echo "MQTT Topics:"
echo "  - Heartbeat: $topic_prefix/heartbeat"
echo "  - Failures: $topic_prefix/failure"
echo ""
echo "To view logs: docker-compose logs -f"
echo "To stop: docker-compose down"
echo ""
