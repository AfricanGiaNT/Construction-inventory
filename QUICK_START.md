# Quick Start: Deploy to Render

## 🚀 Fast Deployment (5 minutes)

### 1. Prepare Environment Variables
```bash
# Copy and edit the environment file
cp config/env.example config/.env

# Edit config/.env with your actual values:
# - TELEGRAM_BOT_TOKEN (from @BotFather)
# - AIRTABLE_API_KEY (from Airtable)
# - AIRTABLE_BASE_ID (from Airtable)
# - TELEGRAM_ALLOWED_CHAT_IDS (optional - if not set, bot works in any chat)
```

### 2. Run Deployment Script
```bash
./deploy.sh
```

### 3. Deploy on Render
1. Go to [render.com](https://render.com)
2. Click "New +" → "Background Worker"
3. Connect your GitHub repository
4. Configure:
   - **Name**: `construction-inventory-bot`
   - **Environment**: `Docker`
   - **Plan**: `Free`
5. Set environment variables (mark sensitive ones as "Secret")
6. Click "Create Background Worker"

### 4. Test Your Bot
- Wait for build to complete
- Send `/help` to your bot on Telegram
- Check logs in Render dashboard

## 🔧 What Gets Deployed

- **Background Worker**: Runs continuously, handling Telegram commands
- **Scheduled Tasks**: Daily reports (8 AM), weekly backups (Monday 9 AM)
- **Health Monitoring**: Built-in health checks for all services
- **Auto-scaling**: Handles multiple users and commands

## 📊 Free Tier Limits

- **Runtime**: 750 hours/month (about 31 days)
- **Perfect for**: Development, testing, small teams
- **Upgrade when**: Need unlimited runtime or more resources

## 🆘 Need Help?

- **Detailed Guide**: See `render-deployment-guide.md`
- **Troubleshooting**: Check logs in Render dashboard
- **Common Issues**: See troubleshooting section in deployment guide

## 🎯 Next Steps

After successful deployment:
1. Test all bot commands
2. Set up monitoring alerts
3. Configure backup strategies
4. Plan feature updates
