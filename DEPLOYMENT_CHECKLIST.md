# Vercel Deployment Checklist

Use this checklist to deploy your Telegram Invoice Bot to Vercel.

## Pre-Deployment

- [ ] Install Vercel CLI: `npm i -g vercel`
- [ ] Have your Telegram Bot Token ready (from @BotFather)
- [ ] Test bot locally: `uv run python src/bot.py`
- [ ] Verify environment variables in `.env` file

## Deployment Steps

### 1. Login to Vercel
```bash
vercel login
```

### 2. Deploy to Preview
```bash
vercel
```
- [ ] Confirm project settings
- [ ] Note the preview URL (e.g., `https://project-abc123.vercel.app`)

### 3. Add Environment Variables

Use Vercel CLI:
```bash
vercel env add TELEGRAM_BOT_TOKEN
vercel env add BUSINESS_NAME
vercel env add BUSINESS_ADDRESS
vercel env add BUSINESS_PHONE
vercel env add BUSINESS_EMAIL
vercel env add BUSINESS_REGISTRATION
vercel env add GST_RATE
vercel env add GST_THRESHOLD
```

Or use Vercel Dashboard:
- [ ] Go to project settings
- [ ] Navigate to "Environment Variables"
- [ ] Add all variables for Production, Preview, and Development

### 4. Deploy to Production
```bash
vercel --prod
```
- [ ] Note the production URL (e.g., `https://your-app.vercel.app`)

### 5. Configure Webhook
```bash
uv run python scripts/setup_webhook.py https://your-app.vercel.app/api/webhook
```
- [ ] Verify webhook is set successfully
- [ ] Check for any error messages

### 6. Test Production Bot
- [ ] Send `/start` command to your bot
- [ ] Send `/help` command
- [ ] Send a test invoice message
- [ ] Verify PDF is generated and sent back

## Verification

### Check Webhook Status
```bash
uv run python scripts/setup_webhook.py status
```

Expected output:
```
📊 Webhook Status:
   URL: https://your-app.vercel.app/api/webhook
   Pending updates: 0

🤖 Bot Info:
   Username: @your_bot
   Name: Your Bot Name
   ID: 1234567890
```

### Monitor Logs
```bash
vercel logs --follow
```

Or check in Vercel Dashboard:
- [ ] Go to Deployments
- [ ] Select latest deployment
- [ ] Click "Functions" → "webhook"

## Troubleshooting

### Bot Not Responding
- [ ] Check webhook status: `uv run python scripts/setup_webhook.py status`
- [ ] Verify environment variables in Vercel dashboard
- [ ] Check function logs in Vercel
- [ ] Test webhook URL manually: `curl https://your-app.vercel.app/api/webhook`

### Webhook Errors
- [ ] Ensure URL uses `https://` (not `http://`)
- [ ] Verify bot token is correct
- [ ] Check Telegram API: `curl "https://api.telegram.org/bot<TOKEN>/getMe"`

### PDF Generation Issues
- [ ] Check Vercel function logs for ReportLab errors
- [ ] Verify function completes within timeout (10s free tier)
- [ ] Test locally first: `uv run python src/bot.py`

## Rollback (If Needed)

### List Deployments
```bash
vercel ls
```

### Rollback to Previous Version
```bash
vercel rollback [deployment-url]
```

### Switch Back to Polling (Local)
```bash
uv run python scripts/setup_webhook.py remove
uv run python src/bot.py
```

## Post-Deployment

- [ ] Add custom domain (optional)
- [ ] Set up monitoring/alerts
- [ ] Document your deployment URL
- [ ] Share bot username with users

## Custom Domain (Optional)

### Add Domain in Vercel
- [ ] Go to Project Settings → Domains
- [ ] Add your domain
- [ ] Configure DNS records

### Update Webhook
```bash
uv run python scripts/setup_webhook.py https://yourdomain.com/api/webhook
```

## Success! 🎉

Your bot is now deployed and running on Vercel!

- Production URL: `https://your-app.vercel.app`
- Webhook: `https://your-app.vercel.app/api/webhook`
- Bot: `@your_bot_username`

## Regular Updates

```bash
# Make changes
git add .
git commit -m "Your changes"

# Deploy
vercel --prod

# Webhook stays configured automatically
```

---

For detailed instructions, see [DEPLOYMENT.md](./DEPLOYMENT.md)
