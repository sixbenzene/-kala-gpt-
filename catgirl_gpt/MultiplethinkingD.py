# 该分裂思维正用于web版本gpt，作用与gpt4

from chatGPT.web.V1 import Chatbot
from loguru import logger
import asyncio
from cfg.botConfig import OpenAiConfig
import os

class MultiplethinkingD:
    def __init__(self):
        self.name = "chatGPT-web"
        self.sessions = {}  # 保存对话对象
        self.lock = asyncio.Lock()
        self.thinking = None   #作为存活判断
        self.config = OpenAiConfig.load_config()
        self.status = False    #作为是否忙的判断
        self.keyword = ["/gpt4"]

    def activate(self):
        if (
            not self.config["webEmail"] and
            not self.config["webProxy"] and
            not self.config["webAccessToken"]
        ):
            logger.error("openAiConfig.json 配置文件出错！请配置 OpenAI 的邮箱、密码，或者 session_token")
            return False
        try:
            self.thinking = Chatbot(
                config={
                    "url": self.config["webProxy"],
                    "email": self.config["webEmail"],
                    "model": self.config["webModel"],
                    "access_token": self.config["webAccessToken"],
                }
            )
            logger.info("清空所有对话")
            self.thinking.clear_conversations()
        except Exception as e:
            logger.warning("{} 初始化失败：{}".format(self.name, e))
            return False
        self.status = True
        return True

    # message：对话，id：谁说的
    async def response(self, message) -> str:
        # 从消息中去除keyword
        self.status = False
        for i in self.keyword:
            message = message.replace(i, "")
        async with self.lock:
            resp = ""
            for data in self.thinking.ask(
                prompt=message,
                # conversation_id = self.conversation_id
            ):
                resp = data["message"]
            self.status = True
            return resp
        
    # async def knowingOneself(self):
    #     if self.thinking == None or self.status == False:
    #         return False
    #     self.status = False
    #     logger.info("开始认识自我")
    #     for tel in self.config["preinstall"]:
    #         resp = await self.response(tel)
    #         logger.info("{}".format(resp))
    #     self.status = True
    #     logger.info("结束认识自我")
