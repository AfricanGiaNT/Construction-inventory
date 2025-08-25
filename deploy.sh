#!/bin/bash

# Construction Inventory Bot Deployment Script
# This script helps prepare and deploy the bot to Render

set -e

echo "🚀 Construction Inventory Bot Deployment Script"
echo "=============================================="

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

# Check if .env file exists
if [ ! -f "config/.env" ]; then
    echo "⚠️  Warning: config/.env file not found"
    echo "   Please create it from config/env.example with your actual values"
    echo ""
    echo "   Required environment variables:"
    echo "   - TELEGRAM_BOT_TOKEN"
    echo "   - TELEGRAM_ALLOWED_CHAT_IDS"
    echo "   - AIRTABLE_API_KEY"
    echo "   - AIRTABLE_BASE_ID"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo "❌ Error: Git repository not initialized"
    echo "   Please run: git init && git add . && git commit -m 'Initial commit'"
    exit 1
fi

# Check if there are uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo "⚠️  Warning: You have uncommitted changes"
    git status --short
    echo ""
    read -p "Commit changes before deploying? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git add .
        git commit -m "Deploy to Render - $(date)"
    fi
fi

# Check if remote origin is set
if ! git remote get-url origin >/dev/null 2>&1; then
    echo "❌ Error: No remote origin set"
    echo "   Please add your remote repository:"
    echo "   git remote add origin <your-repo-url>"
    exit 1
fi

# Push to remote
echo "📤 Pushing to remote repository..."
git push origin main

echo ""
echo "✅ Deployment preparation complete!"
echo ""
echo "Next steps:"
echo "1. Go to https://render.com and sign in"
echo "2. Click 'New +' and select 'Background Worker'"
echo "3. Connect your repository"
echo "4. Configure the service:"
echo "   - Name: construction-inventory-bot"
echo "   - Environment: Docker"
echo "   - Plan: Free (or upgrade as needed)"
echo "5. Set environment variables (mark sensitive ones as 'Secret')"
echo "6. Click 'Create Background Worker'"
echo ""
echo "📖 See render-deployment-guide.md for detailed instructions"
echo ""
echo "🔍 Monitor deployment:"
echo "   - Check build logs in Render dashboard"
echo "   - Look for 'Construction Inventory Bot initialized successfully'"
echo "   - Test bot commands on Telegram"
