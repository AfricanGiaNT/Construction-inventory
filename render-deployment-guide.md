# Render Deployment Guide for Construction Inventory Bot

## Overview
This guide will help you deploy your Construction Inventory Bot as a background worker on Render. The bot will run continuously, handling Telegram commands and scheduled tasks.

## Prerequisites
- A Render account (free tier available)
- Your Telegram bot token from @BotFather
- Airtable API key and base ID
- Git repository with your code

## Step 1: Prepare Your Repository

### 1.1 Environment Variables
Create a `.env` file in your `config/` directory with your actual values:

```bash
# Copy the example file
cp config/env.example config/.env

# Edit with your real values
TELEGRAM_BOT_TOKEN=your_actual_bot_token
TELEGRAM_ALLOWED_CHAT_IDS=123456789,-987654321
AIRTABLE_API_KEY=your_actual_airtable_key
AIRTABLE_BASE_ID=your_actual_base_id
```

### 1.2 Commit and Push
```bash
git add .
git commit -m "Add Render deployment configuration"
git push origin main
```

## Step 2: Deploy on Render

### 2.1 Connect Repository
1. Go to [render.com](https://render.com) and sign in
2. Click "New +" and select "Background Worker"
3. Connect your GitHub/GitLab repository
4. Select the repository containing your bot

### 2.2 Configure Service
- **Name**: `construction-inventory-bot`
- **Environment**: `Python 3`
- **Build Command**: `pip install -e .`
- **Start Command**: `python -m src.main`
- **Plan**: Free (or upgrade as needed)

### 2.3 Set Environment Variables
Add these environment variables in Render (mark sensitive ones as "Secret"):

**Required (Mark as Secret):**
- `TELEGRAM_BOT_TOKEN` - Your bot token from @BotFather
- `TELEGRAM_ALLOWED_CHAT_IDS` - Comma-separated chat IDs
- `AIRTABLE_API_KEY` - Your Airtable API key
- `AIRTABLE_BASE_ID` - Your Airtable base ID

**Optional (Default values):**
- `REDIS_URL` - `redis://localhost:6379`
- `REDIS_ENABLED` - `false`
- `APP_ENV` - `production`
- `LOG_LEVEL` - `INFO`
- `DEFAULT_APPROVAL_THRESHOLD` - `100`
- `RATE_LIMIT_PER_MINUTE` - `30`
- `DAILY_REPORT_TIME` - `08:00`
- `WEEKLY_BACKUP_DAY` - `0` (Monday)
- `WEEKLY_BACKUP_TIME` - `09:00`
- `WORKER_SLEEP_INTERVAL` - `10`

### 2.4 Deploy
Click "Create Background Worker" and wait for the build to complete.

## Step 3: Verify Deployment

### 3.1 Check Logs
- Go to your service dashboard
- Click on "Logs" to see real-time output
- Look for "Construction Inventory Bot initialized successfully"

### 3.2 Test Bot
1. Send a message to your bot on Telegram
2. Check the logs to see if it's processing commands
3. Verify scheduled tasks are running (daily reports, weekly backups)

## Step 4: Monitor and Maintain

### 4.1 Health Checks
- Monitor the service status in Render dashboard
- Set up alerts for service failures
- Check logs regularly for errors

### 4.2 Scaling
- Free tier: 750 hours/month (about 31 days)
- Upgrade to paid plans for unlimited runtime
- Consider upgrading if you need more resources

### 4.3 Updates
- Push changes to your main branch
- Render will automatically redeploy
- Monitor logs after updates

## Troubleshooting

### Common Issues

**Build Failures:**
- Check Python version compatibility
- Verify all dependencies in `requirements.txt`
- Check for syntax errors in your code

**Runtime Errors:**
- Verify environment variables are set correctly
- Check Airtable API permissions
- Ensure Telegram bot token is valid

**Scheduled Tasks Not Running:**
- Verify timezone settings
- Check if the worker is running continuously
- Look for errors in the scheduler logs

### Debug Commands
```bash
# Check service status
curl -s https://your-service-name.onrender.com/health

# View recent logs
# Use Render dashboard or CLI
```

## Security Considerations

1. **Environment Variables**: Never commit sensitive data to your repository
2. **Bot Permissions**: Limit bot access to only necessary chats
3. **API Keys**: Rotate Airtable API keys regularly
4. **Monitoring**: Set up alerts for unusual activity

## Cost Optimization

- **Free Tier**: 750 hours/month (suitable for development/testing)
- **Paid Plans**: Start at $7/month for unlimited runtime
- **Auto-scaling**: Configure based on your usage patterns

## Next Steps

After successful deployment:
1. Test all bot commands thoroughly
2. Set up monitoring and alerting
3. Configure backup strategies
4. Document any custom configurations
5. Plan for future feature deployments

## Support

- **Render Documentation**: [docs.render.com](https://docs.render.com)
- **Telegram Bot API**: [core.telegram.org/bots](https://core.telegram.org/bots)
- **Airtable API**: [airtable.com/api](https://airtable.com/api)
