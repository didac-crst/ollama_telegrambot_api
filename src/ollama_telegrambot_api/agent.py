from dataclasses import dataclass, field
from datetime import datetime
import html
import json
import os
import re
import requests
from time import time
from typing import Optional

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
class TelegramNotificator:
    """ 
    Class to provide a Telegram notification system.
    
    This class allows to inform the administrator about the requests made to the bot in real-time.
    
    """
    telegram_token: str
    notification_telegram_id: Optional[str]
    
    def __post_init__(self) -> None:
        # The active attribute will be used to determine if the notification system is active or not
        # It's useful as it won't be necessary to check if the notification_telegram_id is None every time
        if self.notification_telegram_id is not None:
            self.url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            self.chat_id = self.notification_telegram_id
            self.active = True
        else:
            self.active = False
    
    def send_telegram_message(self, msg: str) -> None:
        """
        Send a message to the chat_id asynchronously

        """
        if self.active:
            payload = {
                "chat_id": self.chat_id,
                "text": msg,
                "parse_mode": "HTML",
            }
            try:
                response = requests.post(self.url, data=payload)
                if response.status_code == 200:
                    print("Notification sent successfully")
                else:
                    print(f"Failed to send notification: {response.status_code}")
                    print(response.text)
            except Exception as e:
                print(f"An error occurred while trying to send a notification: {e}")
    
    def send_message(self,
                    user_id: str,
                    first_name: str,
                    last_name: str,
                    username: str,
                    question: str,
                    answer: Optional[str],
                    execution_time: Optional[float],
                    error: Optional[bool] = None, # To match the kwargs of the answer_dict
                    time: Optional[float] = None, # To match the kwargs of the answer_dict
                    ) -> None:
        """
        Send a message to the chat_id with the information about the request made to the bot

        """
        if self.active:
            msg = (
                f"👤 <b>User:</b>\n"
                f"     •ID: {user_id}\n"
                f"     •Username: {username}\n"
                f"     •Name: {first_name} {last_name}\n\n"
                f"💬 <b>Question:</b>\n{html.escape(question)}\n\n"
            )
            if answer:
                msg += (
                f"🧠 <b>Answer:</b>\n{html.escape(answer)}\n\n"
                )
            if execution_time:
                msg += (
                f"⏱️ <i><b>Execution time:</b> {execution_time:.2f}s</i>"
                )
            self.send_telegram_message(msg)

@dataclass
class OllamaAPI:
    url: str
    model: str
    
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
    notification_telegram_id: str
    disclaimer_message: str
    min_time_between_disclaimers: int = 3600 # Default value is 1 hour
    logger_directory_path: str = "./"

    def __post_init__(self):
        self.Notifier: TelegramNotificator = TelegramNotificator(telegram_token=self.telegram_token, notification_telegram_id=self.notification_telegram_id)
        self.Log: SQLiteLogger = SQLiteLogger(logger_name=self.logger_name, directory_path=self.logger_directory_path)
        self.chatOllama: OllamaAPI = OllamaAPI(
            url=self.ollama_url,
            model=self.ollama_model,
        )
        self.application = ApplicationBuilder().token(self.telegram_token).build()
        self.add_handlers()

    def add_handlers(self):
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # Send disclaimer message
        if (len(self.disclaimer_message) > 0):
            await update.message.reply_text(self.disclaimer_message, parse_mode=ParseMode.HTML)
            msg = "Disclaimer message sent."
        else:
            msg = "Nothing has been sent."
        # Log the user
        answer_dict = {
            "user_id": update.effective_user.id,
            "username": update.effective_user.username,
            "first_name": update.effective_user.first_name,
            "last_name": update.effective_user.last_name,
            "question": "/start",
            "answer": msg,
            "execution_time": 0.0,
            "error": False
        }
        self.Log(answer_dict=answer_dict)
        self.Notifier.send_message(**answer_dict)
        
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
        Send the disclaimer message to the user only if the time between messages is greater than the minimum time between disclaimers
        
        """
        if self.min_time_between_disclaimers > 0:
            now = time()
            user_id = update.effective_user.id
            last_record_timestamp = self.Log.find_last_record_user(user_id)
            if now - last_record_timestamp > self.min_time_between_disclaimers:
                await self.start(update, None)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message_payload = self.get_attributes_from_message(update)
        # Send disclaimer message only if the time between messages is greater than the minimum time between disclaimers
        await self.send_disclaimer_message(update)
        question = message_payload
        # Notify the administrator about the request made to the bot
        self.Notifier.send_message(**message_payload, answer=None, execution_time=None)
        # Ask the question to the chatbot
        answer_dict = self.chatOllama.ask(question)
        # Notify the administrator about the response from the chatbot
        self.Notifier.send_message(**answer_dict)
        # Log the answer
        self.Log(answer_dict=answer_dict)
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