#!/bin/bash
# Deploy script for v1.1.0 release

set -e

VERSION="v1.1.0"
DOCKER_USERNAME="${1:-YOUR_DOCKER_USERNAME}"

if [ "$DOCKER_USERNAME" == "YOUR_DOCKER_USERNAME" ]; then
    echo "Usage: ./deploy-v2.sh YOUR_DOCKER_USERNAME"
    echo "Example: ./deploy-v2.sh johndoe"
    exit 1
fi

echo "=========================================="
echo "  Print Monitor v1.1.0 Deployment"
echo "=========================================="
echo ""
echo "Docker Username: $DOCKER_USERNAME"
echo "Version: $VERSION"
echo ""

# Confirm
read -p "Ready to deploy? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled"
    exit 1
fi

# Git operations
echo ""
echo "📦 Preparing Git release..."
git add .
git commit -m "Release $VERSION: Add standby mode for VRAM management" || true
git tag -a $VERSION -m "Release $VERSION - Standby Mode Update"

echo ""
echo "🔼 Pushing to GitHub..."
git push origin main
git push origin $VERSION

# Docker build and push
echo ""
echo "🐳 Building Docker image..."
docker-compose build print-monitor

echo ""
echo "🏷️  Tagging Docker images..."
docker tag print-monitor-print-monitor $DOCKER_USERNAME/3d-print-monitor:latest
docker tag print-monitor-print-monitor $DOCKER_USERNAME/3d-print-monitor:$VERSION
docker tag print-monitor-print-monitor $DOCKER_USERNAME/3d-print-monitor:1.1.0
docker tag print-monitor-print-monitor $DOCKER_USERNAME/3d-print-monitor:1.1
docker tag print-monitor-print-monitor $DOCKER_USERNAME/3d-print-monitor:2

echo ""
echo "⬆️  Pushing to Docker Hub..."
docker push $DOCKER_USERNAME/3d-print-monitor:latest
docker push $DOCKER_USERNAME/3d-print-monitor:$VERSION
docker push $DOCKER_USERNAME/3d-print-monitor:1.1.0
docker push $DOCKER_USERNAME/3d-print-monitor:1.1
docker push $DOCKER_USERNAME/3d-print-monitor:2

echo ""
echo "=========================================="
echo "  ✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "GitHub: https://github.com/YOUR_USERNAME/3d-print-monitor/releases/tag/$VERSION"
echo "Docker Hub: https://hub.docker.com/r/$DOCKER_USERNAME/3d-print-monitor"
echo ""
echo "Next steps:"
echo "1. Create GitHub release with RELEASE_v1.1.0.md content"
echo "2. Update Docker Hub description with README.md"
echo "3. Announce release!"
echo ""
