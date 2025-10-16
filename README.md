😈 Demon Dating Bot

A fully functional AI-powered Telegram dating bot built using aiogram 3.x.
It allows users to create profiles, like or dislike others, match with mutual likes, and receive notifications about new profiles.
Includes an admin broadcast system for sending updates or announcements to all users.

🧠 Features

📝 Profile creation and editing — users can easily create or update their profile (photo + bio).

❤️ Like / Dislike system — interactive inline buttons with live counters.

💌 Match detection — shows mutual likes (matches).

🎲 Random profile viewing — users can browse other profiles randomly.

🔔 Real-time notifications — new profiles automatically notify subscribers.

🗑️ Profile deletion and updating — users can manage their data anytime.

👑 Admin broadcast support — send global messages or updates to all users using spam.py or /broadcast command.

💾 SQLite-based persistent storage — safe, simple, and local.

🧱 FSM (Finite State Machine) — clean state management for user interactions.

💀 Colored logging system — detailed demon-style console logs for better debugging.

🧩 Tech Stack

Language: Python 3.11+

Framework: aiogram 3.x

Database: SQLite

Async: asyncio

Logging: Custom demon-themed logger with colors & emojis

🚀 Setup
1. Clone the repository
git clone https://github.com/yourusername/demon-dating-bot.git
cd demon-dating-bot

2. Install dependencies
pip install -r requirements.txt


If you don’t have requirements.txt, you can install manually:

pip install aiogram

3. Set your bot token

Edit both main.py and spam.py — replace this line with your actual token:

BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

4. (Optional) Set your admin ID

To use the /broadcast command:

YOUR_ADMIN_ID = 123456789  # Replace with your Telegram ID

🧙‍♂️ Running the bot
Start the main bot
python main.py


The bot will automatically initialize the database (dating_bot.db) and start polling updates.

Start the broadcast script (mass messaging)
python spam.py


Then enter the message you want to send to all registered users.

⚙️ File Structure
.
├── main.py          # Core bot logic (profiles, likes, menus, etc.)
├── spam.py          # Admin mass broadcast script
├── dating_bot.db    # Auto-generated SQLite database
├── demon_logs.log   # Log file with user actions and errors
└── README.md        # You are here 😈

🕹️ Commands
Command	Description
/start	Start the bot / show main menu
/profile	Create or edit your profile
/random	View a random profile
/broadcast	(Admin only) Send update messages to all users
💾 Database Tables
Table	Purpose
users	Stores user info (id, username, name, bio)
photos	Stores file IDs of user photos
likes	Stores likes/dislikes with mutual detection
queues	Keeps random browsing queue for each user
notifications	Tracks who receives new profile alerts
⚠️ Notes

The bot uses Telegram’s polling method — for large-scale usage, consider migrating to webhooks.

Sending mass messages too fast may lead to rate limits or temporary bans — add small delays (e.g. await asyncio.sleep(0.5)) between sends in spam.py.

The bot does not use external APIs, only local storage — safe to run offline (except Telegram network).

🧛 Author

Demon King 👑
Created with 💀, 🍆, and a touch of chaos.
