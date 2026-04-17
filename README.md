# UOB - Personal Telegram Unpin Bot

**Private bot for automatic message unpinning in channel chats.**

## **IMPORTANT: Private Use Only**

This bot is configured for **private use only** and will only respond to authorized users:
- Personal Account: @Nyakitochka (ID: 493498734)
- Work Account: @nikitamolchanovdd (ID: 7437085614)

**Unauthorized users will receive:** "Sorry, this bot is for private use only."

## **Purpose**

This bot solves the problem of cluttered pinned messages in channel chats by automatically unpining messages from specific accounts or bots while preserving pins from other users.

## **Features**

- **Private Access Control** - Only authorized users can operate the bot
- **Automatic Monitoring** - Tracks pinned messages in real-time
- **Account Filtering** - Unpin messages from specific user accounts
- **Bot Filtering** - Unpin messages from specific bots
- **Multi-Chat Support** - Monitor multiple chats simultaneously
- **Flexible Configuration** - Individual settings per chat
- **Redis Storage** - Reliable persistent storage
- **Comprehensive Logging** - Detailed action tracking

## **Installation & Setup**

### 1. Clone and Install Dependencies

```bash
git clone https://github.com/Nyakitoss/UOB.git
cd UOB
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Telegram API
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token

# Redis (for Railway)
USE_REDIS=true
REDIS_URL=${{ Redis.REDIS_URL }}

# Local Development
# USE_REDIS=false
# REDIS_HOST=localhost
# REDIS_PORT=6379
# REDIS_PASSWORD=your_redis_password

# Bot Settings
CHECK_INTERVAL=30  # seconds between checks
LOG_LEVEL=INFO
```

### 3. Get API Credentials

1. Visit [my.telegram.org](https://my.telegram.org)
2. Sign in with your account
3. Create an application
4. Copy `api_id` and `api_hash`

### 4. Create Bot

1. Find [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`
3. Follow instructions
4. Copy the bot token

## **Usage**

### **Available Commands**

- `/start` - Welcome message and help
- `/add_chat` - Add chat to monitoring
- `/remove_chat` - Remove chat from monitoring
- `/list_chats` - List all monitored chats
- `/config_chat` - Configure chat settings
- `/status` - Show bot status and statistics

### **Adding a Chat to Monitoring**

```
/start
/add_chat
[forward message from chat or send @username]
```

### **Configuring Filters**

```
/config_chat
[forward message from chat]
accounts: @user1, @user2
bots: @bot1, @bot2
```

### **Managing Chats**

- `/list_chats` - Show all monitored chats
- `/remove_chat` - Remove chat from monitoring
- `/status` - Bot status and statistics

## **How It Works**

1. **Monitoring**: Bot checks pinned messages every 30 seconds
2. **Filtering**: Verifies message sender against configured lists
3. **Unpinning**: Removes pins from matching accounts/bots
4. **Logging**: Records all actions for audit trail

## **Security Features**

- **Access Control**: Only authorized users can operate the bot
- **Permission Verification**: Admin rights required for chat management
- **Secure Storage**: Configurations stored in Redis
- **Audit Logging**: All actions logged with user identification

## **Chat Configuration Structure**

```json
{
  "chat_name": "Channel Discussion",
  "added_by": 493498734,
  "added_at": "2026-04-17T10:30:00",
  "accounts_to_unpin": ["@spam_user1", "@spam_user2"],
  "bots_to_unpin": ["@reminder_bot", "@news_bot"]
}
```

## **Deployment on Railway**

1. Create new project on Railway
2. Add Redis service
3. Add bot service from GitHub repository
4. Configure environment variables:
   - `API_ID`, `API_HASH`, `BOT_TOKEN`
   - `REDIS_URL=${{ Redis.REDIS_URL }}`
   - `USE_REDIS=true`

### **Required Environment Variables**

```
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
USE_REDIS=true
REDIS_URL=${{ Redis.REDIS_URL }}
CHECK_INTERVAL=30
LOG_LEVEL=INFO
```

## **Project Structure**

```
UOB/
|-- unpin_bot.py      # Main bot code with access control
|-- storage.py         # Redis/local storage management
|-- requirements.txt    # Python dependencies
|-- Dockerfile         # Container configuration
|-- railway.toml       # Railway deployment settings
|-- .env.example      # Environment variables template
|-- README.md         # Documentation
```

## **Access Control System**

The bot implements a dual-verification system:

1. **User ID Verification** (Primary)
   - Personal: 493498734 (@Nyakitochka)
   - Work: 7437085614 (@nikitamolchanovdd)

2. **Username Verification** (Backup)
   - @nyakitochka
   - @nikitamolchanovdd

**Unauthorized access attempts are logged:**
```
**LOG: Unauthorized access attempt by User 123456789 (@unknown_user)**
```

## **Logging Examples**

```
**LOG: Personal Account (@Nyakitochka) accessed /start command**
**LOG: Work Account (@nikitamolchanovdd) added chat to monitoring**
**LOG: Unpinned bot message 123 from chat -1001234567890**
**LOG: Redis connected successfully**
```

## **Troubleshooting**

### Bot doesn't respond
- Verify your user ID is in AUTHORIZED_USERS
- Check bot has admin rights in target chat
- Review logs for authorization errors

### Redis connection issues
- Verify REDIS_URL variable
- Ensure Redis service is running
- Try local storage: `USE_REDIS=false`

### Messages not being unpinned
- Check chat configuration
- Verify account/bot usernames are correct
- Ensure bot has unpinning permissions

## **Updates**

1. Stop the bot
2. Run `git pull`
3. Install dependencies: `pip install -r requirements.txt`
4. Restart the bot

## **License**
MIT License

## 🤝 Поддержка

При возникновении проблем создайте issue в репозитории или свяжитесь с разработчиком.
