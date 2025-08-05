#!/bin/bash

echo "Checking git status..."
git status

echo "Adding all files..."
git add .

echo "Committing changes..."
git commit -m "Initial commit: Homebrew Bottles Sync System

Complete AWS-based automated solution for Homebrew bottle mirroring with:
- Intelligent routing between Lambda and ECS based on download size
- External hash file support for S3 and HTTPS sources  
- Comprehensive Terraform infrastructure modules
- Real-time Slack notifications and monitoring
- Duplicate prevention via SHA256 checksums
- Date-based S3 storage organization
- Complete documentation and troubleshooting guides"

echo "Setting up remote..."
git remote add origin https://github.com/mosiko1234/homebrew_airgap.git 2>/dev/null || echo "Remote already exists"

echo "Pushing to GitHub..."
git push -u origin master

echo "Upload complete!"