import re
import logging
import aiohttp
from aiocqhttp import CQHttp, Event, MessageSegment
from loguru import logger
import creart
import asyncio
from typing_extensions import Annotated
from asyncio import AbstractEventLoop
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Image as GraiaImage, At, Plain, Voice
from graia.ariadne.message.parser.base import DetectPrefix
from graia.ariadne.connection.config import (
    HttpClientConfig,
    WebsocketClientConfig,
    config as ariadne_config,
)

from typing import Union, Optional
from graia.ariadne.model import Friend, Group
from graia.ariadne.message import Source
import brain
from graia.ariadne.event.lifecycle import AccountLaunch
from cfg.botConfig import BotConfig

config = BotConfig.load_config()
bot = CQHttp()

loop = creart.create(AbstractEventLoop)
bots = []

from cfg.botConfig import BotConfig

config = BotConfig.load_config()
async def create_timeout_task(target: Union[Friend, Group], source: Source):
    await asyncio.sleep(config["responseTimeout"])
    await app.send_message(
        target,
        config["responseText"]["timeout"],
        quote=source if config["responseQuoteTextFlag"] == "True" else False,
    )

async def start_task():
    """|coro|
    以异步方式启动
    """
    return await bot.run_task(host="127.0.0.1", port=8566)

class MentionMe:
    """At 账号或者提到账号群昵称"""

    def __init__(self, name: Union[bool, str] = True) -> None:
        self.name = name

    async def __call__(self, chain: MessageChain, event: Event) -> Optional[MessageChain]:
        first = chain[0]
        if isinstance(first, At) and first.target == config["mirai"]["qq"]
            return MessageChain(chain.__root__[1:], inline=True).removeprefix(" ")
        elif isinstance(first, Plain):
            member_info = await bot.get_group_member_info(group_id=event.group_id, user_id=config["mirai"]["qq"])
            if member_info.get("nickname") and chain.startswith(member_info.get("nickname")):
                return chain.removeprefix(" ")
        raise ExecutionStop
class Image(GraiaImage):
    async def get_bytes(self) -> bytes:
        """尝试获取消息元素的 bytes, 注意, 你无法获取并不包含 url 且不包含 base64 属性的本元素的 bytes.

        Raises:
            ValueError: 你尝试获取并不包含 url 属性的本元素的 bytes.

        Returns:
            bytes: 元素原始数据
        """
        if self.base64:
            return b64decode(self.base64)
        if not self.url:
            raise ValueError("you should offer a url.")
        async with aiohttp.ClientSession() as session:
            async with session.get(self.url) as response:
                response.raise_for_status()
                data = await response.read()
                self.base64 = b64encode(data).decode("ascii")
                return data

def transform_message_chain(text: str) -> MessageChain:
    pattern = r"\[CQ:(\w+),([^\]]+)\]"
    matches = re.finditer(pattern, text)

    message_classes = {
        "text": Plain,
        "image": Image,
        "at": At,
        # Add more message classes here
    }

    messages = []
    start = 0
    for match in matches:
        cq_type, params_str = match.groups()
        params = dict(re.findall(r"(\w+)=([^,]+)", params_str))
        if message_class := message_classes.get(cq_type):
            text_segment = text[start:match.start()]
            if text_segment and not text_segment.startswith('[CQ:reply,'):
                messages.append(Plain(text_segment))
            if cq_type == "at":
                if params.get('qq') == 'all':
                    continue
                params["target"] = int(params.pop("qq"))
            elem = message_class(**params)
            messages.append(elem)
            start = match.end()
    if text_segment := text[start:]:
        messages.append(Plain(text_segment))

    return MessageChain(*messages)


def response(event, is_group: bool):
    async def respond(resp):
        logger.debug(f"[OneBot] 尝试发送消息：{str(resp)}")
        try:
            if not isinstance(resp, MessageChain):
                resp = MessageChain(resp)
            resp = transform_from_message_chain(resp)
            # if config.response.quote and '[CQ:record,file=' not in str(resp):  # skip voice
            #     resp = MessageSegment.reply(event.message_id) + resp
            return await bot.send(event, resp)
        except Exception as e:
            logger.exception(e)
            logger.warning("原始消息发送失败，尝试通过转发发送")
            return await bot.call_action(
                "send_group_forward_msg" if is_group else "send_private_forward_msg",
                group_id=event.group_id,
                messages=[
                    MessageSegment.node_custom(event.self_id, "ChatGPT", resp)
                ]
            )

    return respond

def transform_from_message_chain(chain: MessageChain):
    result = ''
    for elem in chain:
        if isinstance(elem, (Image, GraiaImage)):
            result = result + MessageSegment.image(f"base64://{elem.base64}")
        elif isinstance(elem, Plain):
            result = result + MessageSegment.text(str(elem))
        elif isinstance(elem, Voice):
            result = result + MessageSegment.record(f"base64://{elem.base64}")
    return result


# # 处理消息
async def handle_message(
        target: Union[Friend, Group], session_id: str, message: str, source: Source
) -> str:
    if not message.strip():
        return config["responseText"]["nullText"]

    # 匹配关键词 切换思维
    tk, contents = brain.matchingThinking(message)
    logger.info("匹配到的思维：{}".format(tk))
    if (brain.activateThinking(tk) == False):  # 激活
        return "激活思维：{} 失败".format(tk)
    brain.changeThinking(tk)  # 切换
    if brain.thinking is None:
        return "目前处于失魂状态，无法回复消息。"
    #
    timeout_task = asyncio.create_task(create_timeout_task(target, source))
    try:
        # session = brain.matching_session(session_id)
        # 重置会话
        # if message.strip() in "重置会话":
        #     session.reset_conversation()
        #     return "重置会话"
        #
        # if message.strip() in "回滚":
        #     resp = session.rollback_conversation()
        #     if resp:
        #         return config.response.rollback_success + '\n' + resp
        #     return "回滚"

        # 手动激活思维 例： /激活 /bing 激活
        # if contents.strip() == "激活":
        #     if(brain.thinking.activate() == True):
        #         return "激活成功"
        #     else:
        #         return "激活失败"

        # 正常交流
        resp = await brain.response(message)
        logger.info("对{}的消息：[{}],进行应答：".format(session_id, message))
        return resp

        # resp = await session.chat_response(message)
        # logger.info("对{}的消息：[{}],进行应答：".format(session_id,message))
        # logger.info(resp)
        # return resp

    except Exception as e:
        if "Too many requests" in str(e):
            return config["responseText"]["tooFast"]
        if "Connection aborted" in str(e):
            return "大概是代理服务器挂了"
        logger.exception(e)
        return "出现故障：{}".format(e)
    finally:
        timeout_task.cancel()

@bot.on_message('private')
async def _(event: Event):
    if event.message.startswith('.'):
        return
    chain = transform_message_chain(event.message)

    logger.debug(f"私聊消息：{event.message}")
    resp = await handle_message(Friend, f"friend-{event.user_id}", chain.display, Source)
    respond = response(event, True)
    await respond(resp)


GroupTrigger = [MentionMe("at" != "at")]
@bot.on_message('group')
async def _(event: Event):

    if event.message.startswith('.'):
        return
    chain = transform_message_chain(event.message)
    try:
        for it in GroupTrigger:
            chain = await it(chain, event)
    except:
        logger.debug(f"丢弃群聊消息：{event.message}（原因：不符合触发前缀）")
        return
    resp = await handle_message(Group,f"group-{event.group_id}",chain.display,Source)
    respond = response(event,True)
    await respond(resp)




# logger.info("激活默认思维: {}".format(config["defaultThinking"]))
# if brain.defaultActivate():
#     logger.info("激活成功，尝试连接到 Mirai 服务")
# else:
#     logger.info("激活失败，在连接上 Mirai 服务后请手动激活")


bots.append(loop.create_task(start_task()))
loop.run_until_complete(asyncio.gather(*bots))
loop.run_forever()