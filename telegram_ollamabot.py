from dataclasses import dataclass, field
from dotenv import load_dotenv
from datetime import datetime
import html
import json
import os
import re
import requests

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    filters,
    MessageHandler,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from sql_logger import SQLiteLogger

# Load .env file
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

def parse_time(timestamp_str: str) -> datetime:
    parsed_time = datetime.fromisoformat(timestamp_str.rstrip('Z')[:26])
    return parsed_time

# @dataclass
# class Logger:
#     log: list[dict[str, any]] = field(default_factory=list)
    
#     def __post_init__(self):
#         self.log = []
    
#     def record(self, answer: dict[str, any]):
#         self.log.append(answer)


@dataclass
class Ollama:
    url: str = "http://localhost:11434/api/generate"
    model: str = "llama2-uncensored"
    
    def __post_init__(self):
        self.Log: SQLiteLogger = SQLiteLogger("TwinAI_log")
    
    def parse_response(self, data: str) -> dict[str, any]:
        answer = ""
        lines = data.split("\n")
        start = True
        for line in lines:
            json_line=json.loads(line)
            if start:
                time_start = parse_time(json_line["created_at"])
                start = False
            word = json_line["response"]
            answer = answer + word
            if json_line["done"]:
                time_end = parse_time(json_line["created_at"])
                break
        execution_time = (time_end - time_start).total_seconds()
        output = dict()
        output["answer"] = answer
        output["execution_time"] = execution_time
        output["time"] = time_start
        return output
    
    def ask(self, message_payload: dict[str,str]) -> dict[str, any]:
        question = message_payload['question']
        response = requests.post(self.url, json={"model": self.model, "prompt": question})
        if response.status_code == 200:
            answer = self.parse_response(response.text)
        else:
            answer = dict()
            answer['answer'] = "Error"
            answer['execution_time'] = None
            answer['time'] = datetime.now()

        for key in message_payload.keys():
            answer[key] = message_payload[key]
        self.Log(answer)
        return answer
    
@dataclass
class TelegramAgent:
    """
    Class to handle the Telegram bot
    """

    def __post_init__(self):
        self.Model_AI: Ollama = Ollama()
        self.application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        self.add_handlers()

    def add_handlers(self):
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text('Hi! Send me a question and I will answer it.')
        
    def format_answer(self, answer_dict: dict[str, any]) -> dict[str, str]:
        answer = answer_dict['answer']
        split_answer = answer.split("```")
        answer_blocks = []
        for i in range(len(split_answer)):
            tmp_block = dict()
            if i % 2 == 0:
                tmp_block['format'] = 'HTML'
                tmp_block['text'] = split_answer[i]
            else:
                tmp_block['format'] = 'MarkdownV2'
                tmp_block['text'] = f"```{split_answer[i]}```"
            # We don't want to add empty blocks
            # This could happen if split happens at the beginning or end of the string
            if tmp_block['text'] != "":
                answer_blocks.append(tmp_block)
        answer_blocks.append(
            {
                'format': 'HTML',
                'text': f"🕒 <i>Time elapsed: {answer_dict['execution_time']:.2f}s</i>"
            }
        )
        return answer_blocks
    
    def get_attributes_from_message(self, update: Update) -> dict[str, str]:
        first_name = update.effective_chat.first_name
        last_name = update.effective_chat.last_name
        username = update.effective_chat.username
        user_id = update.effective_user.id
        question = update.message.text
        message_payload = {
            "first_name": first_name,
            "last_name": last_name,
            "username": username,
            "user_id": user_id,
            "question": question
        }
        return message_payload

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message_payload = self.get_attributes_from_message(update)
        question = message_payload
        # Here you can integrate with Ollama or any other logic
        try:
            answer_dict = self.Model_AI.ask(question)
            answer_blocks = self.format_answer(answer_dict)
            for block in answer_blocks:
                answer = block['text']
                format = block['format']
                await update.message.reply_text(answer, parse_mode=format)
        except Exception as e:
            await update.message.reply_text("❌ <b>An error occurred. Please try again.</b>", parse_mode=ParseMode.HTML)

    def run(self):
        self.application.run_polling()