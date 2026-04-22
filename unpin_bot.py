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

# ================== USER STATE MANAGEMENT ==================

# User states: None (normal), 'add_chat', 'remove_chat', 'config_chat'
user_states = {}

def set_user_state(user_id: int, state: str = None):
    """Set user state"""
    user_states[user_id] = state

def get_user_state(user_id: int) -> str:
    """Get user state"""
    return user_states.get(user_id)

def clear_user_state(user_id: int):
    """Clear user state"""
    if user_id in user_states:
        del user_states[user_id]

# ================== ACCESS CONTROL ==================

def is_authorized(user_id: int, username: str = None) -> bool:
    """Check if user is authorized to use the bot"""
    if user_id in AUTHORIZED_USERS:
        return True
    
    if username and username.lower() in AUTHORIZED_USERNAMES:
        return True
    
    return False

def get_user_info(user_id: int, username: str = None) -> str:
    """Get user info string for logging"""
    if user_id == 493498734:
        return "Personal Account (@Nyakitochka)"
    elif user_id == 7437085614:
        return "Work Account (@nikitamolchanovdd)"
    elif username and username.lower() in AUTHORIZED_USERNAMES:
        return f"User {user_id} (@{username})"
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
            
            # Get usernames to unpin
            usernames_to_unpin = config.get("usernames_to_unpin", [])
            
            for message in pinned_messages:
                if not message:
                    continue
                
                await self._check_and_unpin_message(message, usernames_to_unpin, chat_id)
                    
        except Exception as e:
            print(f"**LOG: Error in _process_chat for {chat_id}: {e}**")
    
    async def _check_and_unpin_message(self, message, usernames_to_unpin: list, chat_id: str):
        """Check if message should be unpinned and unpin it"""
        try:
            message_id = message.id
            sender_id = message.sender_id
            
            # Skip if already processed
            if message_id in self.processed_messages:
                return
            
            # Get sender info
            sender = await client.get_entity(sender_id)
            sender_username = getattr(sender, 'username', None)
            
            # Check if sender username is in usernames to unpin
            should_unpin = False
            if sender_username:
                sender_username_lower = sender_username.lower()
                for username in usernames_to_unpin:
                    if username.lower().lstrip('@') == sender_username_lower:
                        should_unpin = True
                        reason = f"@{sender_username}"
                        break
            
            if should_unpin:
                await client.unpin_message(message, chat_id)
                self.processed_messages.add(message_id)
                
                # Track unpinned message
                message_info = {
                    'message_id': message_id,
                    'chat_id': chat_id,
                    'unpinned_at': datetime.now().isoformat(),
                    'reason': reason
                }
                storage.add_pinned_message(chat_id, message_info)
                
                print(f"**LOG: Unpinned {reason} message {message_id} from chat {chat_id}**")
            
        except Exception as e:
            print(f"**LOG: Error unpinning message {message.id}: {e}**")
    
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
    user_id = event.sender_id
    username = getattr(event.sender, 'username', None)
    
    if not is_authorized(user_id, username):
        await event.reply("Sorry, this bot is for private use only.")
        return
    
    user_info = get_user_info(user_id, username)
    print(f"**LOG: {user_info} accessed /start command**")
    
    # Clear any existing state
    clear_user_state(user_id)
    
    await event.reply(
        "🤖 **Personal Unpin Bot**\n\n"
        "This bot automatically unpins messages from specific accounts or bots "
        "in linked channel chats.\n\n"
        "**Available Commands:**\n"
        "   `/add_chat` - Add chat to monitoring\n"
        "   `/remove_chat` - Remove chat from monitoring\n"
        "   `/list_chats` - List monitored chats\n"
        "   `/config_chat` - Configure chat settings\n"
        "   `/status` - Show bot status\n"
        "   `/exit` - Exit current command mode\n\n"
        "**How it works:**\n"
        "1. Use command to start action\n"
        "2. Send chat ID when requested\n"
        "3. Bot processes the action\n"
        "4. Use /exit to cancel\n\n"
        "Bot must be admin in the chat with unpining rights."
    )

@client.on(events.NewMessage(pattern="/exit"))
async def exit_mode(event):
    user_id = event.sender_id
    username = getattr(event.sender, 'username', None)
    
    if not is_authorized(user_id, username):
        await event.reply("Sorry, this bot is for private use only.")
        return
    
    # Clear user state
    clear_user_state(user_id)
    
    user_info = get_user_info(user_id, username)
    print(f"**LOG: {user_info} used /exit command**")
    
    await event.reply(
        "🚪 **Exited command mode**\n\n"
        "You are now back to the main menu.\n"
        "Use /start to see available commands."
    )

@client.on(events.NewMessage(pattern="/add_chat"))
async def add_chat(event):
    user_id = event.sender_id
    username = getattr(event.sender, 'username', None)
    
    if not is_authorized(user_id, username):
        await event.reply("Sorry, this bot is for private use only.")
        return
    
    user_info = get_user_info(user_id, username)
    print(f"**LOG: {user_info} accessed /add_chat command**")
    
    # Set user state to waiting for chat ID
    set_user_state(user_id, 'add_chat')
    
    await event.reply(
        "➕ **Add Chat to Monitoring**\n\n"
        "Please send the chat ID or username:\n\n"
        "Examples:\n"
        "   `@channel_username`\n"
        "   `-1001234567890`\n"
        "   `1234567890`\n\n"
        "Use `/exit` to cancel."
    )

@client.on(events.NewMessage(pattern="/remove_chat"))
async def remove_chat(event):
    user_id = event.sender_id
    username = getattr(event.sender, 'username', None)
    
    if not is_authorized(user_id, username):
        await event.reply("Sorry, this bot is for private use only.")
        return
    
    user_info = get_user_info(user_id, username)
    print(f"**LOG: {user_info} accessed /remove_chat command**")
    
    # Set user state to waiting for chat ID
    set_user_state(user_id, 'remove_chat')
    
    await event.reply(
        "➖ **Remove Chat from Monitoring**\n\n"
        "Please send the chat ID or username:\n\n"
        "Examples:\n"
        "   `@channel_username`\n"
        "   `-1001234567890`\n"
        "   `1234567890`\n\n"
        "Use `/exit` to cancel."
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

@client.on(events.NewMessage(pattern="/config_chat"))
async def config_chat(event):
    user_id = event.sender_id
    username = getattr(event.sender, 'username', None)
    
    if not is_authorized(user_id, username):
        await event.reply("Sorry, this bot is for private use only.")
        return
    
    user_info = get_user_info(user_id, username)
    print(f"**LOG: {user_info} accessed /config_chat command**")
    
    # Set user state to waiting for chat ID
    set_user_state(user_id, 'config_chat')
    
    await event.reply(
        "⚙️ **Configure Chat Settings**\n\n"
        "Please send the chat ID or username:\n\n"
        "Examples:\n"
        "   `@channel_username`\n"
        "   `-1001234567890`\n"
        "   `1234567890`\n\n"
        "Use `/exit` to cancel."
    )

@client.on(events.NewMessage(pattern="/chat_config"))
async def chat_config(event):
    user_id = event.sender_id
    username = getattr(event.sender, 'username', None)
    
    if not is_authorized(user_id, username):
        await event.reply("Sorry, this bot is for private use only.")
        return
    
    user_info = get_user_info(user_id, username)
    print(f"**LOG: {user_info} accessed /chat_config command**")
    
    # Set user state to waiting for chat ID
    set_user_state(user_id, 'config_chat')
    
    await event.reply(
        "⚙️ **Configure Chat Settings**\n\n"
        "Please send the chat ID or username:\n\n"
        "Examples:\n"
        "   `@channel_username`\n"
        "   `-1001234567890`\n"
        "   `1234567890`\n\n"
        "Use `/exit` to cancel."
    )

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
    """Handle messages based on user state"""
    user_id = event.sender_id
    username = getattr(event.sender, 'username', None)
    
    # Check authorization
    if not is_authorized(user_id, username):
        await event.reply("Sorry, this bot is for private use only.")
        print(f"**LOG: Unauthorized message from User {user_id} (@{username})**: {event.raw_text[:50]}...")
        return
    
    # Check user state
    current_state = get_user_state(user_id)
    
    if current_state:
        # User is in a command mode
        text = event.raw_text.strip()
        
        # Handle forwarded messages
        if event.fwd_from:
            await handle_forwarded_message(event)
        elif current_state == 'config_chat_username':
            # Handle username input for config_chat
            await handle_username_input(user_id, text, event)
        elif text:
            # Handle direct message with chat ID
            await handle_chat_input(user_id, text, event, current_state)
        else:
            await event.reply("❌ Please send a valid input.")
    else:
        # User is in normal mode
        # If they send something that looks like a chat ID without command, ask for command
        text = event.raw_text.strip()
        if text and (text.startswith('@') or text.startswith('-100') or text.isdigit()):
            await event.reply(
                "❌ Please use a command first.\n\n"
                "Use `/start` to see available commands."
            )
        # Otherwise ignore (let command handlers process commands)

async def handle_chat_input(user_id: int, text: str, event, state: str):
    """Handle chat ID input based on user state"""
    try:
        # Validate input looks like a chat identifier
        if not (text.startswith('@') or text.startswith('-100') or text.isdigit()):
            await event.reply(
                "❌ Invalid format. Please send a valid chat ID or username.\n\n"
                "Examples:\n"
                "   `@channel_username`\n"
                "   `-1001234567890`\n"
                "   `1234567890`\n\n"
                "Use `/exit` to cancel."
            )
            return
        
        # Process based on state
        if state == 'add_chat':
            await process_chat_action(user_id, text, event, 'add_chat')
            clear_user_state(user_id)
        elif state == 'remove_chat':
            await process_chat_action(user_id, text, event, 'remove_chat')
            clear_user_state(user_id)
        elif state == 'config_chat':
            # For config_chat, process chat ID then ask for username
            await process_chat_action(user_id, text, event, 'config_chat')
            # Set state to wait for username input
            set_user_state(user_id, 'config_chat_username')
            await event.reply(
                "⚙️ **Configure Chat - Add Username**\n\n"
                "Please send the @username to unpin messages from:\n\n"
                "Example: `@username_to_unpin`\n\n"
                "Use `/exit` to cancel."
            )
        
    except Exception as e:
        await event.reply(f"❌ Error: {str(e)}")
        print(f"**LOG: Error in handle_chat_input: {e}**")

async def handle_username_input(user_id: int, text: str, event):
    """Handle username input for config_chat"""
    try:
        # Validate input looks like a username
        if not text.startswith('@'):
            await event.reply(
                "❌ Invalid format. Please send a valid @username.\n\n"
                "Example: `@username_to_unpin`\n\n"
                "Use `/exit` to cancel."
            )
            return
        
        # Store the username for the last configured chat
        # For simplicity, we'll store it in a temporary dict
        if not hasattr(event, '_config_chat_id'):
            await event.reply("❌ Error: No chat configured. Please start over with /config_chat")
            clear_user_state(user_id)
            return
        
        chat_id = event._config_chat_id
        
        # Add username to chat configuration
        config = storage.get_chat_config(chat_id)
        if not config:
            await event.reply("❌ Error: Chat not found in monitoring.")
            clear_user_state(user_id)
            return
        
        # Add username to usernames_to_unpin list
        if 'usernames_to_unpin' not in config:
            config['usernames_to_unpin'] = []
        
        config['usernames_to_unpin'].append(text)
        storage.update_chat_config(chat_id, config)
        
        await event.reply(
            f"✅ **Added username to unpin list**\n\n"
            f"Chat: {config.get('chat_name', 'Unknown')}\n"
            f"Username: {text}\n\n"
            f"Total usernames to unpin: {len(config['usernames_to_unpin'])}\n\n"
            f"Add more usernames or use `/exit` to finish."
        )
        
        # Keep user in config_chat_username state to allow adding more usernames
        
    except Exception as e:
        await event.reply(f"❌ Error: {str(e)}")
        print(f"**LOG: Error in handle_username_input: {e}**")

async def handle_forwarded_message(event):
    """Handle forwarded messages for chat identification"""
    try:
        user_id = event.sender_id
        current_state = get_user_state(user_id)
        
        # Get the original chat from forwarded message
        if event.fwd_from.from_id:
            chat_id = event.fwd_from.from_id.chat_id if hasattr(event.fwd_from.from_id, 'chat_id') else None
            if chat_id:
                chat_identifier = str(chat_id)
                # Process based on state
                if current_state == 'add_chat':
                    await process_chat_action(user_id, chat_identifier, event, 'add_chat')
                elif current_state == 'remove_chat':
                    await process_chat_action(user_id, chat_identifier, event, 'remove_chat')
                elif current_state == 'config_chat':
                    await process_chat_action(user_id, chat_identifier, event, 'config_chat')
                
                # Clear state after processing
                clear_user_state(user_id)
                return
        
        await event.reply("❌ Could not extract chat information from forwarded message. Please send chat ID directly.")
            
    except Exception as e:
        await event.reply(f"❌ Error handling forwarded message: {str(e)}")
        print(f"**LOG: Error in handle_forwarded_message: {e}**")

async def process_chat_action(user_id: int, chat_identifier: str, event, action: str):
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
        
        # Determine action based on action parameter
        if action == 'add_chat':
            await add_chat_to_monitoring(user_id, chat_id, chat_name, event)
        elif action == 'remove_chat':
            await remove_chat_from_monitoring(user_id, chat_id, chat_name, event)
        elif action == 'config_chat':
            # Store chat_id in event for username input
            event._config_chat_id = chat_id
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
        
        # Initialize usernames_to_unpin if not exists
        if 'usernames_to_unpin' not in config:
            config['usernames_to_unpin'] = []
            storage.update_chat_config(chat_id, config)
        
        usernames = config.get('usernames_to_unpin', [])
        
        response = f"⚙️ **Configure Chat: {chat_name}**\n\n"
        response += f"Chat ID: {chat_id}\n\n"
        response += f"**Usernames to unpin:**\n"
        
        if usernames:
            for username in usernames:
                response += f"• {username}\n"
        else:
            response += "• No usernames configured\n"
        
        response += f"\n**Total:** {len(usernames)} username(s)\n\n"
        response += f"**Next:** Send @username to add to unpin list\n\n"
        response += f"Use `/exit` to finish."
        
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
