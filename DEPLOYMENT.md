# Deploying to Vercel

This guide explains how to deploy your Telegram Invoice Bot to Vercel as a serverless function using webhooks.

## Prerequisites

1. [Vercel Account](https://vercel.com/signup) (free tier works!)
2. [Vercel CLI](https://vercel.com/docs/cli) installed: `npm i -g vercel`
3. Your Telegram Bot Token from [@BotFather](https://t.me/botfather)

## Deployment Steps

### 1. Install Vercel CLI

```bash
npm i -g vercel
```

### 2. Login to Vercel

```bash
vercel login
```

### 3. Deploy to Vercel

```bash
vercel
```

Follow the prompts:
- Set up and deploy? **Y**
- Which scope? (select your account)
- Link to existing project? **N**
- What's your project's name? `telegram-bot-accounting` (or your choice)
- In which directory is your code located? `./`
- Want to modify settings? **N**

### 4. Set Environment Variables

Add your environment variables to Vercel:

```bash
# Required
vercel env add TELEGRAM_BOT_TOKEN
# Paste your bot token when prompted

# Business details
vercel env add BUSINESS_NAME
vercel env add BUSINESS_ADDRESS
vercel env add BUSINESS_PHONE
vercel env add BUSINESS_EMAIL

# Optional
vercel env add BUSINESS_REGISTRATION
vercel env add GST_RATE        # Default: 0.09
vercel env add GST_THRESHOLD   # Default: 400.00
```

Or set them in the Vercel dashboard:
1. Go to your project settings
2. Navigate to "Environment Variables"
3. Add each variable for Production, Preview, and Development

### 5. Deploy to Production

```bash
vercel --prod
```

You'll get a URL like: `https://your-app.vercel.app`

### 6. Configure Telegram Webhook

Set your webhook URL to point to your Vercel deployment:

```bash
uv run python scripts/setup_webhook.py https://your-app.vercel.app/api/webhook
```

Example output:
```
✅ Removed existing webhook
✅ Webhook set successfully: https://your-app.vercel.app/api/webhook

📊 Webhook Info:
   URL: https://your-app.vercel.app/api/webhook
   Pending updates: 0
```

### 7. Test Your Bot

Send a message to your bot on Telegram! It should respond using the webhook.

## Important Notes

### Webhook vs Polling

- **Webhook (Production)**: Telegram sends updates to your Vercel function
- **Polling (Local Dev)**: Your bot checks Telegram for updates

The webhook version is in `api/webhook.py` and is optimized for serverless.

### Local Development

For local development, you can still use polling:

```bash
# Remove webhook
uv run python scripts/setup_webhook.py remove

# Run locally with polling
uv run python src/bot.py
```

When ready to deploy again, set the webhook back up.

### File Storage Limitations

⚠️ **Important**: Vercel serverless functions have **read-only file systems** except for `/tmp`.

The `InvoiceGenerator` creates PDFs in `/tmp` which is automatically cleaned up. This works fine for serverless!

### Function Timeout

Vercel free tier has a **10-second timeout** for serverless functions. Invoice generation should complete well within this limit.

## Monitoring

### Check Webhook Status

```bash
uv run python scripts/setup_webhook.py status
```

### View Logs

In Vercel dashboard:
1. Go to your project
2. Click "Deployments"
3. Select your deployment
4. Click "Functions" → "webhook" to see logs

Or use CLI:
```bash
vercel logs
```

## Troubleshooting

### Webhook Not Working

1. **Check webhook is set correctly**:
   ```bash
   uv run python scripts/setup_webhook.py status
   ```

2. **Verify environment variables** are set in Vercel dashboard

3. **Check function logs** in Vercel dashboard

4. **Test webhook endpoint** manually:
   ```bash
   curl https://your-app.vercel.app/api/webhook
   ```

### Bot Not Responding

1. Check Vercel function logs for errors
2. Verify `TELEGRAM_BOT_TOKEN` is set correctly
3. Ensure webhook URL uses `https://` (not `http://`)
4. Test the bot token with:
   ```bash
   curl "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"
   ```

### Invoice Generation Fails

1. Check that ReportLab dependencies are installed
2. Verify `/tmp` directory is being used (automatic in the code)
3. Check function timeout - may need to optimize PDF generation

## Updating Your Bot

```bash
# Make your changes
git add .
git commit -m "Update bot"

# Deploy
vercel --prod

# Webhook stays configured automatically
```

## Cost

Vercel's **free tier** includes:
- 100GB bandwidth/month
- Serverless function executions
- Automatic HTTPS
- Global CDN

This is more than enough for a personal/small business invoice bot!

## Rollback

If something goes wrong:

```bash
# List deployments
vercel ls

# Rollback to previous deployment
vercel rollback [deployment-url]
```

## Custom Domain (Optional)

1. Go to Vercel dashboard → Your project → Settings → Domains
2. Add your custom domain
3. Update webhook:
   ```bash
   uv run python scripts/setup_webhook.py https://yourdomain.com/api/webhook
   ```

## Security

- ✅ HTTPS enforced by Vercel
- ✅ Environment variables encrypted
- ✅ No long-running processes (serverless)
- ✅ Automatic scaling
- ✅ DDoS protection by Vercel

## Support

If you encounter issues:
1. Check Vercel function logs
2. Review Telegram webhook info
3. Test locally first with `uv run python src/bot.py`
