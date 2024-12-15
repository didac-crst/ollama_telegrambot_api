from dataclasses import dataclass, field
from datetime import datetime
import html
import json
import os
import re
import requests
import threading
from time import time, sleep
from typing import Optional

import numpy as np
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
                if response.status_code != 200:
                    print(f"Failed to send notification: {response.status_code}")
                    print(response.text)
                # else:
                #     print("Notification sent successfully")
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
            if execution_time:
                msg += (
                f"⏱️ <i><b>Execution time:</b> {execution_time:.2f}s</i>\n\n"
                )
            if answer:
                msg += (
                f"🧠 <b>Answer:</b>\n{html.escape(answer)}"
                )
            self.send_telegram_message(msg)
            
@dataclass
class OllamaStreamResponse:
    url: str
    model: str
    question: str
    answer_finished: bool = False
    answer: str = ""
    error: bool = False
    
    def __post_init__(self):
        self.payload = {
            "model": self.model,
            "prompt": self.question,
        }
    
    def ask(self) -> None:
        try:
            # Make a streaming POST request
            with requests.post(self.url, json=self.payload, stream=True) as response:
                if response.status_code == 200:
                    # Stream the response token by token
                    for line in response.iter_lines():
                        if line:  # Skip empty lines
                            # Decode and parse the token
                            token = line.decode("utf-8")
                            token_json = json.loads(token)
                            self.answer  = self.answer + token_json["response"]
                            self.answer_finished = token_json["done"]
                else:
                    self.response_text = response.text
                    print(f"Error: {response.status_code}, {self.response_text }")
                    self.error = True
                # The following assignments need to be done outside the for loop, if not the loop will not start until the request is finished
                # This will avoid the streaming effect
                self.status_code = response.status_code
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            self.error = True

    def delete(self) -> None:
        self.ask_thread.join()
        del self
        
    def __call__(self) -> None:
        self.ask_thread = threading.Thread(target=self.ask)
        self.ask_thread.start()
    

@dataclass
class OllamaAPI:
    url: str
    model: str
    
    def ask(self, message_payload: dict[str,str]) -> None:
        self.start_time = time()
        self.message_payload = message_payload
        question = message_payload['question']
        # Ask the question to the chatbot
        self.Response = OllamaStreamResponse(url=self.url, model=self.model, question=question)
        self.Response()
            
    def parse_response(self) -> dict[str, any]:
        message_payload = self.message_payload
        Response = self.Response
        answer = dict()
        if Response.error:
            answer['answer'] = f"Status Code: {Response.status_code} - Response: {Response.response_text}"
            answer['error'] = True
        else:
            answer['answer'] = Response.answer
            answer['error'] = False
        for key in message_payload.keys():
            answer[key] = message_payload[key]
        end_time = time()
        answer["time"] = self.start_time
        answer['execution_time'] = end_time - self.start_time
        self.Response.delete()
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
        answer = self.chatOllama.Response.answer
        split_answer = answer.split("```")
        answer_blocks = []
        answer_blocks.append(
            {
                'type': 'time',
                'format': 'HTML',
                'text': f"🕒 <i>Execution time: {answer_dict['execution_time']:.2f}s</i>"
            }
        )
        for i in range(len(split_answer)):
            tmp_block = dict()
            if i % 2 == 0:
                tmp_block['type'] = 'answer'
                tmp_block['format'] = 'HTML'
                tmp_block['text'] = split_answer[i]
            else:
                tmp_block['type'] = 'answer'
                tmp_block['format'] = 'MarkdownV2'
                tmp_block['text'] = f"```{split_answer[i]}```"
            # We don't want to add empty blocks
            # This could happen if split happens at the beginning or end of the string
            if tmp_block['text'] != "":
                answer_blocks.append(tmp_block)
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
    
    async def stream_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        message_id = None
        Response = self.chatOllama.Response
        parse_mode = ParseMode.HTML
        # To avoid sending to much messages to Telegram, we well decrease the frequency of the messages as the answer is being longer.
        while_iteration = 1
        while not Response.answer_finished:
            # In case of an error, we change the parse_mode to None to avoid the HTML tags
            try:
                if Response.error:
                    break
                # This is a simple way to decrease the frequency of the messages as the answer is being longer
                sleep_time = int(np.log2(1+while_iteration/10)+1)
                sleep(sleep_time)
                while_iteration += 1
                # In case of error we stop using html parsing and tags.
                if parse_mode is None:
                    answer = Response.answer
                else:
                    answer = f"<i>{Response.answer}...</i>"
                # We edit the message once we have a message_id
                if message_id:
                    # Edit the message only if the answer has changed
                    if answer != previous_answer:
                        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=message_id, text=answer, parse_mode=parse_mode)
                # If there is no message sent yet, we send the message for the first time
                else:
                    telegram_answer = await update.message.reply_text(answer, parse_mode=parse_mode)
                    message_id = telegram_answer.message_id
                previous_answer = answer
                # Response = self.chatOllama.Response
            except Exception as e:
                print(f"An error occurred while streaming the response: {e}")
                # In case of an error, we change the parse_mode to None to avoid the HTML tags
                parse_mode = None
        return message_id

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message_payload = self.get_attributes_from_message(update)
        # Send disclaimer message only if the time between messages is greater than the minimum time between disclaimers
        await self.send_disclaimer_message(update)
        question = message_payload
        # Notify the administrator about the request made to the bot
        # self.Notifier.send_message(**message_payload, answer=None, execution_time=None)
        # Ask the question to the chatbot
        self.chatOllama.ask(question)
        # Stream the answer
        message_id = await self.stream_response(update, context)
        answer_dict = self.chatOllama.parse_response()
        # Notify the administrator about the response from the chatbot
        self.Notifier.send_message(**answer_dict)
        # Log the answer
        self.Log(answer_dict=answer_dict)
        if not answer_dict['error']:
            answer_blocks = self.format_answer(answer_dict)
            # Send the answer to the user
            for block in answer_blocks:
                answer = block['text']
                format = block['format']
                # We use the stream_response to provide the execution time
                if block['type'] == 'time':
                    await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=message_id, text=answer, parse_mode=format)
                # For the other answer blocks, we use the normal reply_text
                else:
                    await update.message.reply_text(answer, parse_mode=format)
        else:
            error_message = "❌ <b>An error occurred. Please try again later.</b>"
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=message_id, text=error_message, parse_mode=ParseMode.HTML)

    def run(self):
        print("Running the bot...")
        self.application.run_polling()