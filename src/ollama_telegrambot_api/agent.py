from dataclasses import dataclass, field
from datetime import datetime
import html
import json
import os
import re
import requests
from time import time

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    filters,
    MessageHandler,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from .sql_logger import SQLiteLogger


@dataclass
class OllamaAPI:
    url: str
    model: str
    logger_name: str
    logger_directory_path: str
    
    def __post_init__(self):
        self.Log: SQLiteLogger = SQLiteLogger(logger_name=self.logger_name, directory_path=self.logger_directory_path)
    
    def parse_response(self, data: str) -> dict[str, any]:
        answer = ""
        lines = data.split("\n")
        for line in lines:
            json_line=json.loads(line)
            word = json_line["response"]
            answer = answer + word
            if json_line["done"]:
                break
        output = dict()
        output["answer"] = answer
        return output
    
    def ask(self, message_payload: dict[str,str]) -> dict[str, any]:
        start_time = time()
        question = message_payload['question']
        print(f"Question: {question}")
        response = requests.post(self.url, json={"model": self.model, "prompt": question})
        print(f"Response: {response}")
        if response.status_code == 200:
            answer = self.parse_response(response.text)
            answer['error'] = False
        else:
            status_code = response.status_code
            answer = dict()
            answer['answer'] = f"Status Code: {status_code} - {response.text}"
            answer['error'] = True
        for key in message_payload.keys():
            answer[key] = message_payload[key]
        end_time = time()
        answer["time"] = start_time
        answer['execution_time'] = end_time - start_time
        self.Log(answer)
        return answer
    
@dataclass
class TelegramAgent:
    """
    Class to handle the Telegram bot
    """
    ollama_url: str
    ollama_model: str
    logger_name: str
    telegram_token: str
    disclaimer_message: str
    min_time_between_disclaimers: int = 3600 # Default value is 1 hour
    logger_directory_path: str = "./"

    def __post_init__(self):
        self.chatOllama: OllamaAPI = OllamaAPI(
            url=self.ollama_url,
            model=self.ollama_model,
            logger_name=self.logger_name,
            logger_directory_path=self.logger_directory_path,
        )
        self.application = ApplicationBuilder().token(self.telegram_token).build()
        self.add_handlers()

    def add_handlers(self):
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(self.disclaimer_message, parse_mode=ParseMode.HTML)
        
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
                'text': f"🕒 <i>Execution time: {answer_dict['execution_time']:.2f}s</i>"
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
    
    async def send_disclaimer_message(self, update: Update) -> None:
        """
        Send a disclaimer message to the user if the time between messages is greater than the minimum time between disclaimers.
        
        """
        now = time()
        user_id = update.effective_user.id
        last_record_timestamp = self.chatOllama.Log.find_last_record_user(user_id)
        if now - last_record_timestamp > self.min_time_between_disclaimers:
            await self.start(update, None)
            

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message_payload = self.get_attributes_from_message(update)
        # Send disclaimer message only if the time between messages is greater than the minimum time between disclaimers
        if (len(self.disclaimer_message) > 0) and (self.min_time_between_disclaimers > 0):
            await self.send_disclaimer_message(update)
        question = message_payload
        # Here you can integrate with Ollama or any other logic
        answer_dict = self.chatOllama.ask(question)
        if not answer_dict['error']:
            answer_blocks = self.format_answer(answer_dict)
            for block in answer_blocks:
                answer = block['text']
                format = block['format']
                await update.message.reply_text(answer, parse_mode=format)
        else:
            await update.message.reply_text("❌ <b>An error occurred. Please try again.</b>", parse_mode=ParseMode.HTML)

    def run(self):
        print("Running the bot...")
        self.application.run_polling()