
import os
from dotenv import load_dotenv
from ollama_telegrambot_api.agent import TelegramAgent
# Load .env file
load_dotenv()

# SPECIFIC CONFIGURATIONS - PLEASE CHANGE ACCORDINGLY
# It is needed to create an .env file with the TELEGRAM_TOKEN
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
# It is important to specify the right model
OLLAMA_MODEL: str = "tinyllama"

# STANDARD CONFIGURATIONS - CHANGE ONLY IF NECESSARY
# URL is the standard URL for the Ollama API
OLLAMA_URL: str = "http://localhost:11434/api/generate"
# Logger name - Name of the logger file
LOGGER_NAME: str = "ollama_chatbot"
# Logger directory path - Path to the directory where the log file will be stored
LOGGER_DIRECTORY_PATH: str = "./"

def main() -> None:
    Agent = TelegramAgent(
        ollama_url=OLLAMA_URL,
        ollama_model=OLLAMA_MODEL,
        logger_name=LOGGER_NAME,
        telegram_token=TELEGRAM_TOKEN,
        logger_directory_path=LOGGER_DIRECTORY_PATH,
    )
    Agent.run()

if __name__ == '__main__':
    main()