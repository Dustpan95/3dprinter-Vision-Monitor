# Docker Hub Deployment Guide

This guide will help you push the Print Monitor project to Docker Hub.

## 🆕 v1.1.0 Release Notes

**Major new feature:** Standby Mode for VRAM management!
- See `RELEASE_v1.1.0.md` for full details
- See `CHANGELOG.md` for complete change log

## Pre-Deployment Checklist

✅ **Security Check - COMPLETE**
- [x] No passwords in code files
- [x] No IP addresses in source code
- [x] .env excluded via .gitignore
- [x] .env.example created with placeholders
- [x] Local docs with sensitive info moved to local-docs/

✅ **Documentation - COMPLETE**
- [x] README.docker.md created
- [x] LICENSE file added (MIT)
- [x] .env.example with configuration guide
- [x] Quick setup script (setup.sh)

✅ **Code Quality - COMPLETE**
- [x] Error handling implemented
- [x] Logging configured
- [x] Health checks added
- [x] Configuration via environment variables

## Files to Push to Git Repository

### Include These Files:
```
├── .gitignore
├── LICENSE
├── README.md
├── CHANGELOG.md
├── RELEASE_v1.1.0.md
├── .env.example
├── setup.sh
├── docker-compose.yml
└── monitor/
    ├── Dockerfile
    ├── requirements.txt
    ├── app.py
    ├── templates/
    │   └── index.html
    └── static/
        └── .gitkeep
```

### DO NOT Include:
```
✗ .env (contains secrets)
✗ local-docs/ (contains your specific config)
✗ monitor/logs/ (log files)
✗ README.md (old local readme)
```

## Step-by-Step Deployment

### 1. Initialize Git Repository

```bash
cd /home/dustin/docker/print-monitor

# Initialize git
git init

# Add all files (gitignore will exclude sensitive ones)
git add .

# Commit
git commit -m "Initial commit: 3D Print Monitor with ML detection"
```

### 2. Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `3d-print-monitor` (or your choice)
3. Description: "AI-powered 3D print failure detection with MQTT and web UI"
4. Public or Private: **Public** (for Docker Hub)
5. **Do NOT** initialize with README (we have one)
6. Click "Create repository"

### 3. Push to GitHub

```bash
# Rename README
mv README.docker.md README.md

# Add remote
git remote add origin https://github.com/YOUR-USERNAME/3d-print-monitor.git

# Push
git branch -M main
git push -u origin main
```

### 4. Build and Push Docker Images

#### Option A: Automated Docker Hub Build

1. Go to https://hub.docker.com
2. Click "Create Repository"
3. Connect to your GitHub account
4. Select your repository
5. Configure automated builds
6. Docker Hub will build on every push

#### Option B: Manual Push

```bash
cd /home/dustin/docker/print-monitor

# Login to Docker Hub
docker login

# Build the image
docker-compose build print-monitor

# Tag for Docker Hub
docker tag print-monitor-print-monitor YOUR-USERNAME/3d-print-monitor:latest
docker tag print-monitor-print-monitor YOUR-USERNAME/3d-print-monitor:v1.0.0

# Push to Docker Hub
docker push YOUR-USERNAME/3d-print-monitor:latest
docker push YOUR-USERNAME/3d-print-monitor:v1.0.0
```

### 5. Update docker-compose.yml for Public Use

After pushing, update docker-compose.yml to use your Docker Hub image:

```yaml
services:
  ml_api:
    image: ghcr.io/gabe565/obico/ml-api
    # ... rest stays the same

  print-monitor:
    image: YOUR-USERNAME/3d-print-monitor:latest
    # Remove the 'build' line
    # ... rest stays the same
```

Commit and push this change:
```bash
git add docker-compose.yml
git commit -m "Use Docker Hub image instead of local build"
git push
```

## Docker Hub Repository Settings

### Description
```
AI-powered 3D print failure detection system using Obico ML model. Features MQTT notifications, web UI, and GPU-accelerated detection. Monitor your prints 24/7 and get instant alerts when failures occur.
```

### Tags to Create
- `latest` - Latest stable version
- `v1.0.0` - Version 1.0.0
- `gpu` - GPU-enabled version
- `cpu` - CPU-only version (if you create one)

### README for Docker Hub

The README.md will automatically display on Docker Hub. Make sure it includes:
- [x] Quick start guide
- [x] Configuration examples
- [x] MQTT message formats
- [x] Troubleshooting section

## Testing the Public Image

After pushing, test that others can use it:

```bash
# In a clean directory
mkdir test-deploy
cd test-deploy

# Download docker-compose.yml
wget https://raw.githubusercontent.com/YOUR-USERNAME/3d-print-monitor/main/docker-compose.yml

# Download .env.example
wget https://raw.githubusercontent.com/YOUR-USERNAME/3d-print-monitor/main/.env.example

# Download setup script
wget https://raw.githubusercontent.com/YOUR-USERNAME/3d-print-monitor/main/setup.sh
chmod +x setup.sh

# Run setup
./setup.sh
```

## Adding GitHub Topics

Add these topics to your GitHub repo for better discoverability:
- 3d-printing
- machine-learning
- mqtt
- docker
- monitoring
- failure-detection
- obico
- spaghetti-detective
- home-automation
- nvidia-gpu

## Optional: Create GitHub Release

1. Go to your repo → Releases → "Create a new release"
2. Tag version: `v1.0.0`
3. Release title: `v1.0.0 - Initial Release`
4. Description: Features, changelog, etc.
5. Publish release

## Post-Deployment

### Update README with Install Command

Add one-line install to README:
```bash
# Quick Install
curl -fsSL https://raw.githubusercontent.com/YOUR-USERNAME/3d-print-monitor/main/setup.sh | bash
```

### Create Shields/Badges

Add to top of README.md:
```markdown
![Docker Pulls](https://img.shields.io/docker/pulls/YOUR-USERNAME/3d-print-monitor)
![GitHub Stars](https://img.shields.io/github/stars/YOUR-USERNAME/3d-print-monitor)
![License](https://img.shields.io/github/license/YOUR-USERNAME/3d-print-monitor)
```

## Maintenance

### Updating the Image

```bash
# Make changes
git add .
git commit -m "Update: description of changes"
git push

# Build new version
docker-compose build print-monitor

# Tag and push
docker tag print-monitor-print-monitor YOUR-USERNAME/3d-print-monitor:v1.0.1
docker tag print-monitor-print-monitor YOUR-USERNAME/3d-print-monitor:latest
docker push YOUR-USERNAME/3d-print-monitor:v1.0.1
docker push YOUR-USERNAME/3d-print-monitor:latest
```

## Final Security Check

Before pushing, verify:
```bash
# Check for any remaining sensitive data
cd /home/dustin/docker/print-monitor
grep -r "password\|secret\|token" --include="*.py" --include="*.yml" --include="*.md" . | grep -v ".env" | grep -v "MQTT_PASSWORD"

# Should only show references to environment variables, not actual values
```

## You're Ready! 🚀

Your Print Monitor is now ready to be shared with the world!

**Repository structure is clean ✓**
**No sensitive information ✓**
**Documentation complete ✓**
**Easy to deploy ✓**

Just follow the steps above to push to GitHub and Docker Hub!
