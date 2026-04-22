import os
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import Channel, Chat

from dotenv import load_dotenv
from storage import storage

load_dotenv()

# ================== CONFIG ==================

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 30))  # seconds

# Authorized users (personal and work accounts)
AUTHORIZED_USERS = {
    493498734: {"username": "Nyakitochka", "name": "Personal Account"},
    7437085614: {"username": "nikitamolchanovdd", "name": "Work Account"}
}

# Additional authorized usernames (backup verification)
AUTHORIZED_USERNAMES = {"nyakitochka", "nikitamolchanovdd"}

DATA_DIR = Path("/app/data")
DATA_DIR.mkdir(exist_ok=True)

# ================== CLIENT ==================

client = TelegramClient(
    StringSession(),
    API_ID,
    API_HASH
)

# ================== ACCESS CONTROL ==================

def is_authorized(user_id: int, username: str = None) -> bool:
    """Check if user is authorized to use the bot"""
    # Check by user ID first (most reliable)
    if user_id in AUTHORIZED_USERS:
        return True
    
    # Check by username as backup
    if username and username.lower() in AUTHORIZED_USERNAMES:
        return True
    
    return False

def get_user_info(user_id: int, username: str = None) -> str:
    """Get user display name for authorized users"""
    if user_id in AUTHORIZED_USERS:
        user_data = AUTHORIZED_USERS[user_id]
        return f"{user_data['name']} (@{user_data['username']})"
    
    if username and username.lower() in AUTHORIZED_USERNAMES:
        return f"Authorized User (@{username})"
    
    return f"User {user_id}"

# ================== UNPIN MANAGER ==================

class UnpinManager:
    def __init__(self):
        self.processed_messages = set()  # Track processed message IDs
    
    async def check_pinned_messages(self):
        """Check all configured chats for pinned messages to unpin"""
        configs = storage.get_chat_configs()
        
        for chat_id, config in configs.items():
            try:
                await self._process_chat(chat_id, config)
            except Exception as e:
                print(f"**LOG: Error processing chat {chat_id}: {e}**")
    
    async def _process_chat(self, chat_id: str, config: dict):
        """Process a single chat for unpinning"""
        try:
            entity = await client.get_entity(int(chat_id))
            
            # Get all pinned messages (using get_messages with limit)
            pinned_messages = []
            async for message in client.iter_messages(entity, limit=10):
                if message and message.pinned:
                    pinned_messages.append(message)
            
            if not pinned_messages:
                return
            
            # Get accounts/bots to unpin
            accounts_to_unpin = config.get("accounts_to_unpin", [])
            bots_to_unpin = config.get("bots_to_unpin", [])
            
            for message in pinned_messages:
                if not message:
                    continue
                
                await self._check_and_unpin_message(message, accounts_to_unpin, bots_to_unpin, chat_id)
                    
        except Exception as e:
            print(f"**LOG: Error in _process_chat for {chat_id}: {e}**")
    
    async def _check_and_unpin_message(self, message, accounts_to_unpin: list, bots_to_unpin: list, chat_id: str):
        """Check if message should be unpinned and unpin it"""
        try:
            message_id = message.id
            sender_id = message.sender_id
            
            # Skip if already processed
            if message_id in self.processed_messages:
                return
            
            # Check if sender is in accounts to unpin
            if sender_id in accounts_to_unpin:
                await self._unpin_message(message, chat_id, "account")
                return
            
            # Check if sender is a bot and in bots to unpin list
            if message.from_id and hasattr(message.from_id, 'user_id'):
                sender_info = await client.get_entity(message.from_id.user_id)
                if sender_info.bot and sender_info.username in bots_to_unpin:
                    await self._unpin_message(message, chat_id, "bot")
                    return
            
            # Add to processed to avoid rechecking
            self.processed_messages.add(message_id)
            
            # Clean old processed messages (keep last 1000)
            if len(self.processed_messages) > 1000:
                self.processed_messages = set(list(self.processed_messages)[-500:])
                
        except Exception as e:
            print(f"**LOG: Error checking message {message.id}: {e}**")
    
    async def _unpin_message(self, message, chat_id: str, message_type: str):
        """Unpin a message and log the action"""
        try:
            chat_entity = await client.get_entity(int(chat_id))
            
            # Unpin the message
            await client.unpin_message(chat_entity, message.id)
            
            print(f"**LOG: Unpinned {message_type} message {message.id} from chat {chat_id}**")
            
            # Add to tracking
            message_info = {
                "message_id": message.id,
                "sender_id": message.sender_id,
                "chat_id": chat_id,
                "unpinned_at": datetime.now().isoformat(),
                "type": message_type
            }
            storage.add_pinned_message(chat_id, message_info)
            
        except Exception as e:
            print(f"**LOG: Error unpinning message {message.id}: {e}**")

# ================== COMMAND HANDLERS ==================

@client.on(events.NewMessage(pattern="/start"))
async def start(event):
    if not event.is_private:
        return
    
    user_id = event.sender_id
    username = getattr(event.sender, 'username', None)
    
    if not is_authorized(user_id, username):
        await event.reply("Sorry, this bot is for private use only.")
        print(f"**LOG: Unauthorized access attempt by User {user_id} (@{username})**")
        return
    
    user_info = get_user_info(user_id, username)
    print(f"**LOG: {user_info} accessed /start command**")
    
    await event.reply(
        "Welcome to your **Personal Unpin Bot**! \n\n"
        "This bot automatically unpins messages from specific accounts or bots "
        "in linked channel chats.\n\n"
        "**Commands:**\n"
        "   `/add_chat` - Add chat to monitoring\n"
        "   `/remove_chat` - Remove chat from monitoring\n"
        "   `/list_chats` - List monitored chats\n"
        "   `/config_chat` - Configure chat settings\n"
        "   `/status` - Show bot status\n\n"
        "**How it works:**\n"
        "1. Add chat to monitoring\n"
        "2. Configure which accounts/bots to unpin\n"
        "3. Bot automatically checks and unpins messages\n\n"
        "Bot must be admin in the chat with unpining rights."
    )

@client.on(events.NewMessage(pattern="/add_chat"))
async def add_chat(event):
    if not event.is_private:
        return
    
    user_id = event.sender_id
    username = getattr(event.sender, 'username', None)
    
    if not is_authorized(user_id, username):
        await event.reply("Sorry, this bot is for private use only.")
        return
    
    user_info = get_user_info(user_id, username)
    print(f"**LOG: {user_info} accessed /add_chat command**")
    
    await event.reply(
        "Add Chat to Monitoring\n\n"
        "Forward a message from the chat you want to monitor, "
        "or send the chat username (for public chats):\n\n"
        "Examples:\n"
        "   Forward message from chat\n"
        "   `@channel_username`\n"
        "   `-1001234567890` (chat ID)\n\n"
        "The bot will automatically detect the chat and add it to monitoring."
    )

@client.on(events.NewMessage(pattern="/remove_chat"))
async def remove_chat(event):
    if not event.is_private:
        return
    
    user_id = event.sender_id
    username = getattr(event.sender, 'username', None)
    
    if not is_authorized(user_id, username):
        await event.reply("Sorry, this bot is for private use only.")
        return
    
    user_info = get_user_info(user_id, username)
    print(f"**LOG: {user_info} accessed /remove_chat command**")
    
    await event.reply(
        "Remove Chat from Monitoring\n\n"
        "Forward a message from the chat you want to remove from monitoring,\n"
        "or send the chat username/ID.\n\n"
        "This will stop automatic unpinning for that chat."
    )

@client.on(events.NewMessage(pattern="/list_chats"))
async def list_chats(event):
    user_id = event.sender_id
    username = getattr(event.sender, 'username', None)
    
    if not is_authorized(user_id, username):
        await event.reply("Sorry, this bot is for private use only.")
        return
    
    user_info = get_user_info(user_id, username)
    print(f"**LOG: {user_info} accessed /list_chats command**")
    
    configs = storage.get_chat_configs()
    
    if not configs:
        await event.reply("No chats are currently monitored.")
        return
    
    response = "Monitored Chats:\n\n"
    
    for chat_id, config in configs.items():
        chat_name = config.get("chat_name", f"Chat {chat_id}")
        accounts_count = len(config.get("accounts_to_unpin", []))
        bots_count = len(config.get("bots_to_unpin", []))
        
        response += f"**{chat_name}**\n"
        response += f"   Accounts to unpin: {accounts_count}\n"
        response += f"   Bots to unpin: {bots_count}\n"
        response += f"   Added: {config.get('added_at', 'Unknown')}\n\n"
    
    await event.reply(response)

@client.on(events.NewMessage(pattern="/status"))
async def status(event):
    user_id = event.sender_id
    username = getattr(event.sender, 'username', None)
    
    if not is_authorized(user_id, username):
        await event.reply("Sorry, this bot is for private use only.")
        return
    
    user_info = get_user_info(user_id, username)
    print(f"**LOG: {user_info} accessed /status command**")
    
    configs = storage.get_chat_configs()
    total_chats = len(configs)
    
    await event.reply(
        f"Bot Status\n\n"
        f"Active chats: {total_chats}\n"
        f"Check interval: {CHECK_INTERVAL} seconds\n"
        f"Storage: {'Redis' if storage.use_redis else 'Local'}\n"
        f"Redis Status: {'Connected' if storage.use_redis and storage.redis_client else 'Disconnected'}\n"
        f"Redis URL: {os.getenv('REDIS_URL', 'Not configured')}\n"
        f"Uptime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"Bot is running and monitoring chats."
    )

# ================== MESSAGE HANDLER ==================

@client.on(events.NewMessage)
async def handle_message(event):
    """Handle forwarded messages for chat management"""
    user_id = event.sender_id
    username = getattr(event.sender, 'username', None)
    
    # Check authorization
    if not is_authorized(user_id, username):
        await event.reply("Sorry, this bot is for private use only.")
        print(f"**LOG: Unauthorized message from User {user_id} (@{username})**: {event.raw_text[:50]}...")
        return
    
    # Check if this is a forwarded message
    if event.fwd_from:
        await handle_forwarded_message(event)
    else:
        await handle_direct_message(event)

async def handle_forwarded_message(event):
    """Handle forwarded messages for chat identification"""
    try:
        user_id = event.sender_id
        text = event.raw_text.strip()
        
        # Get the original chat from forwarded message
        if event.fwd_from.from_id:
            chat_id = event.fwd_from.from_id.chat_id if hasattr(event.fwd_from.from_id, 'chat_id') else None
            
            if chat_id:
                await process_chat_action(user_id, chat_id, text, event)
                
    except Exception as e:
        print(f"**LOG: Error handling forwarded message: {e}**")

async def handle_direct_message(event):
    """Handle direct messages with chat usernames/IDs"""
    try:
        user_id = event.sender_id
        text = event.raw_text.strip()
        
        # Skip if empty text
        if not text:
            return
        
        # Check if this looks like a chat identifier
        # Skip if it's just a regular message (not a chat identifier)
        if not (text.startswith('@') or text.startswith('-100') or text.isdigit()):
            # This is a regular message, not a chat identifier
            return
        
        chat_identifier = text
        # This will be processed in the main logic
        await process_chat_action(user_id, chat_identifier, text, event)
            
    except Exception as e:
        print(f"**LOG: Error handling direct message: {e}**")

async def process_chat_action(user_id: int, chat_identifier: str, text: str, event):
    """Process chat-related actions"""
    try:
        # Get chat entity (handle different input types)
        entity = None
        
        if chat_identifier.startswith('@'):
            # Username format
            entity = await client.get_entity(chat_identifier)
        elif chat_identifier.startswith('-100'):
            # Chat ID format
            chat_id = int(chat_identifier)
            entity = await client.get_entity(chat_id)
        elif chat_identifier.isdigit():
            # Numeric ID (try as chat ID first)
            try:
                chat_id = int(chat_identifier)
                entity = await client.get_entity(chat_id)
            except:
                # If not a chat, try as username
                entity = await client.get_entity(chat_identifier)
        else:
            # Try as username
            entity = await client.get_entity(chat_identifier)
        
        # Validate that we got a chat/channel entity
        if not entity:
            await event.reply(f"❌ Could not find chat: {chat_identifier}")
            return
        
        # Check if it's actually a chat/channel (not a user)
        if not hasattr(entity, 'title') and not hasattr(entity, 'username'):
            await event.reply(f"❌ {chat_identifier} is not a chat or channel")
            return
        
        chat_id = str(entity.id)
        chat_name = entity.title if hasattr(entity, 'title') else f"Chat {chat_id}"
        
        # Check user permissions
        try:
            perms = await client.get_permissions(entity, user_id)
            if not perms.is_admin:
                await event.reply("❌ You must be an admin in this chat to manage it.")
                return
        except Exception as e:
            await event.reply(f"❌ Bot doesn't have access to check permissions in this chat: {str(e)}")
            return
        
        # Determine action based on command context
        last_command = getattr(event, '_last_command', '/add_chat')
        
        if last_command == '/add_chat':
            await add_chat_to_monitoring(user_id, chat_id, chat_name, event)
        elif last_command == '/remove_chat':
            await remove_chat_from_monitoring(user_id, chat_id, chat_name, event)
        elif last_command in ['/config_chat', '/chat_config']:
            await configure_chat(user_id, chat_id, chat_name, event)
            
    except Exception as e:
        await event.reply(f"❌ Error processing chat: {str(e)}")
        print(f"**LOG: Error in process_chat_action for {chat_identifier}: {e}**")

async def add_chat_to_monitoring(user_id: int, chat_id: str, chat_name: str, event):
    """Add chat to monitoring list"""
    try:
        config = {
            "chat_name": chat_name,
            "added_by": user_id,
            "added_at": datetime.now().isoformat(),
            "accounts_to_unpin": [],
            "bots_to_unpin": []
        }
        
        storage.save_chat_config(chat_id, config)
        
        await event.reply(
            f"✅ **Chat added to monitoring!**\n\n"
            f"📌 **{chat_name}**\n"
            f"Chat ID: {chat_id}\n\n"
            f"Use `/config_chat` to configure which accounts/bots to unpin.\n\n"
            f"⚠️ Make sure the bot has admin rights with unpinning permission."
        )
        
    except Exception as e:
        await event.reply(f"❌ Error adding chat: {str(e)}")

async def remove_chat_from_monitoring(user_id: int, chat_id: str, chat_name: str, event):
    """Remove chat from monitoring list"""
    try:
        storage.delete_chat_config(chat_id)
        
        await event.reply(
            f"🗑️ **Chat removed from monitoring!**\n\n"
            f"📌 **{chat_name}**\n"
            f"Chat ID: {chat_id}\n\n"
            f"The bot will no longer unpin messages in this chat."
        )
        
    except Exception as e:
        await event.reply(f"❌ Error removing chat: {str(e)}")

async def configure_chat(user_id: int, chat_id: str, chat_name: str, event):
    """Configure chat settings"""
    try:
        config = storage.get_chat_config(chat_id)
        
        if not config:
            await event.reply("❌ Chat not found in monitoring list.")
            return
        
        response = f"⚙️ **Configure Chat: {chat_name}**\n\n"
        response += f"Chat ID: {chat_id}\n\n"
        response += f"**Current settings:**\n"
        response += f"• Accounts to unpin: {len(config.get('accounts_to_unpin', []))}\n"
        response += f"• Bots to unpin: {len(config.get('bots_to_unpin', []))}\n\n"
        response += f"**To add accounts/bots to unpin:**\n"
        response += f"Send usernames or IDs in format:\n"
        response += f"`accounts: @username1, @username2`\n"
        response += f"`bots: @bot1, @bot2`\n\n"
        response += f"**To remove:**\n"
        response += f"`remove_accounts: @username1`\n"
        response += f"`remove_bots: @bot1`"
        
        await event.reply(response)
        
    except Exception as e:
        await event.reply(f"❌ Error configuring chat: {str(e)}")

# ================== MAIN LOOP ==================

unpin_manager = UnpinManager()

async def main_loop():
    """Main monitoring loop"""
    print("🚀 Unpin bot started")
    print(f"📊 Check interval: {CHECK_INTERVAL} seconds")
    print(f"💾 Storage: {'Redis' if storage.use_redis else 'Local'}")
    
    while True:
        try:
            await unpin_manager.check_pinned_messages()
            await asyncio.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"**LOG: Error in main loop: {e}**")
            await asyncio.sleep(CHECK_INTERVAL)

# ================== MAIN ==================

async def main():
    print("=" * 50)
    print("=== UNPIN BOT STARTED ===")
    print(f"Server time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Storage: {'Redis' if storage.use_redis else 'Local'}")
    
    # Check environment variables
    print(f"Environment check:")
    print(f"  API_ID: {'Set' if os.getenv('API_ID') else 'Missing'}")
    print(f"  API_HASH: {'Set' if os.getenv('API_HASH') else 'Missing'}")
    print(f"  BOT_TOKEN: {'Set' if os.getenv('BOT_TOKEN') else 'Missing'}")
    print(f"  USE_REDIS: {os.getenv('USE_REDIS')}")
    print(f"  REDIS_URL: {'Set' if os.getenv('REDIS_URL') else 'Missing'}")
    
    await client.start(bot_token=BOT_TOKEN)
    
    print("=" * 50)
    
    # Start main monitoring loop
    asyncio.create_task(main_loop())
    
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
