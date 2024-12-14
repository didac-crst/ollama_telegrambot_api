
import os
from dotenv import load_dotenv
from ollama_telegrambot_api.agent import TelegramAgent
# Load .env file
load_dotenv()

# SPECIFIC CONFIGURATIONS - PLEASE CHANGE ACCORDINGLY
# It is needed to create an .env file
# Need to create a Telegrambot and get the token
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
# This is the chat_id (user or group) of the person who will receive the notifications
NOTIFICATION_TELEGRAM_ID = os.getenv("NOTIFICATION_TELEGRAM_ID")
# It is important to specify the right model
OLLAMA_MODEL: str = "tinyllama"

# STANDARD CONFIGURATIONS - CHANGE ONLY IF NECESSARY
# URL is the standard URL for the Ollama API
OLLAMA_URL: str = "http://localhost:11434/api/generate"
# Logger name - Name of the logger file
LOGGER_NAME: str = "ollama_chatbot"
# Logger directory path - Path to the directory where the log file will be stored
LOGGER_DIRECTORY_PATH: str = "./"

# Disclaimer messages are sent to users to inform them about the bot's capabilities and limitations
DISCLAIMER_MESSAGE = (
    "<b>✨ Didac's Digital Twinbot ✨</b>\n\n"
    "Welcome to the Twinbot! This AI-powered assistant 🤖 is a fun proof of concept 🚀, created using Ollama 🦙 and trained on data inspired by my real-life experiences 🌟.\n"
    "To keep things safe and private 🔒, I've carefully curated the dataset to avoid sharing too much personal information 🤫.\n"
    "To interact with the Twinbot, simply ask any question you’d like to know about me 💬.\n\n"
    "<i>As this is an experimental setup 🛠️ running on compact and energy-efficient hardware 🔋, the Twinbot operates on a Raspberry Pi 5 💻 (without a GPU 🧠). This may result in slightly longer response times ⏳.</i>\n\n"
    "Thanks for your patience and enjoy the experience! 😉"
)
# Minimum time between disclaimer messages (in seconds)
MIN_TIME_BETWEEN_DISCLAIMERS = 24 * 60 * 60  # 24 hours

def main() -> None:
    Agent = TelegramAgent(
        ollama_url=OLLAMA_URL,
        ollama_model=OLLAMA_MODEL,
        logger_name=LOGGER_NAME,
        telegram_token=TELEGRAM_TOKEN,
        notification_telegram_id = NOTIFICATION_TELEGRAM_ID,
        disclaimer_message=DISCLAIMER_MESSAGE,
        min_time_between_disclaimers=MIN_TIME_BETWEEN_DISCLAIMERS,
        logger_directory_path=LOGGER_DIRECTORY_PATH,
    )
    Agent.run()

if __name__ == '__main__':
    main()