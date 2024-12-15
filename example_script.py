
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

# File path to the disclaimer message
DISCLAIMER_FILE_PATH = "./disclaimer.txt"
# Minimum time between disclaimer messages (in seconds)
MIN_TIME_BETWEEN_DISCLAIMERS = 3 * 24 * 60 * 60  # 3 days

# Read txt file
def read_txt(file_path: str) -> str:
    with open(file_path, "r") as f:
        return f.read()


def main() -> None:
    # Read disclaimer message from file
    DISCLAIMER_MESSAGE = read_txt(DISCLAIMER_FILE_PATH)
    
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