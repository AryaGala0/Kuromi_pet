# -*- coding: utf-8 -*-
"""
AI 聊天模块（智谱 GLM）
- 使用智谱官方 zai-sdk
- 在 QThread 子线程中调用，避免阻塞 UI
- 支持流式输出（stream=True），通过 Qt signal 回传增量文本
- 解析回复末尾的 😊 / 😠 / 😐 / 😈 情绪标签，便于联动桌宠状态切换
"""

import re
from typing import List, Dict, Optional

from PySide6.QtCore import QThread, Signal, QObject

# 中文情绪关键词 → 桌宠帧状态（必须和 KuromiPet.frames 的 key 对应）
# 桌宠可用状态：happy / angry / normal / peek
EMOTION_MAP = {
    "开心": "happy",   # 开心 → happy 帧
    "悲伤": "normal",  # 悲伤（暂无 sad 帧，归到 normal）
    "生气": "angry",   # 生气 → angry 帧
    "无语": "angry",   # 无语 → 也切到生气状态
}

# 主正则：匹配带括号的标签 "（开心）" / "(开心)"（兼容中英文括号）
_EMOTION_KEYS = sorted(EMOTION_MAP.keys(), key=len, reverse=True)
EMOTION_PATTERN = re.compile(
    r"[（(](" + "|".join(re.escape(k) for k in _EMOTION_KEYS) + r")[）)]"
)
# 兜底正则：模型有时会忘记加括号，直接抓裸关键词（限定在文本末尾附近）
_EMOTION_FALLBACK_PATTERN = re.compile(
    r"(" + "|".join(re.escape(k) for k in _EMOTION_KEYS) + r")"
)

DEFAULT_SYSTEM_PROMPT = (
    "你是库洛米（Kuromi），三丽鸥角色。性格傲娇、暗黑可爱、嘴硬心软。"
    "说话风格：中文、每句尽量短（不超过40字），多用「哼」「啦」「嘛」「~」等语气词。"
    "回复要求：一次只回1-2句话；禁止markdown；不要长篇大论。"
    "每次回复必须在最末尾用中文括号标记一个情绪标签，可选标签只有4个："
    "（开心）（悲伤）（生气）（无语），只能从这4个里选最贴合当前心情的一个，"
    "不要省略，不要用其他词，标签要严格写在回复正文的最后。"
)


# 全文关键词扫描：扩展词表，覆盖 AI 回复中常见的情绪表达
# 这些关键词只要在回复中出现，就会触发对应状态动画
EMOTION_KEYWORDS_FULLTEXT = {
    # happy 相关
    "happy": [
        "开心", "高兴", "快乐", "喜欢", "幸福", "哈哈", "嘿嘿", "嘻嘻",
        "么么", "♡", "❤", "笑", "可爱", "棒", "好耶", "嘿嘿嘿",
    ],
    # angry 相关
    "angry": [
        "气死", "烦死", "无语", "讨厌啦",
        "凶", "怒", "(╬", "╬", "╯°", "╰_╯",
    ],
    # peek 相关（偷看 / 害羞 / 偷偷）
    "peek": [
        "偷看", "偷偷", "害羞", "嘘", "悄悄",
    ],
}


def _scan_emotion_fulltext(text: str) -> Optional[str]:
    """扫描全文中的情绪关键词，返回最先命中的桌宠状态。

    优先级：angry > happy > peek（生气/讨厌信号最强，避免被普通"哈哈"覆盖）
    """
    if not text:
        return None
    # 按优先级顺序检查
    for state in ("angry", "happy", "peek"):
        for kw in EMOTION_KEYWORDS_FULLTEXT[state]:
            if kw in text:
                return state
    return None


def split_emotion(text: str) -> tuple[str, Optional[str]]:
    """从回复文本中分离情绪标签。

    返回：(去掉标签后的纯文本, 桌宠帧状态名或None)
        状态名取值范围：happy / angry / peek / normal

    识别策略（按优先级）：
        1) 优先匹配带括号的标签 "（开心）" —— 模型显式标注，最可信
        2) 文末 12 字符内的裸关键词（如 "好开心"）
        3) 全文情绪关键词扫描（"生气"/"开心"/"讨厌"/"哼" 等字眼）
    """
    if not text:
        return text, None

    # 策略1：括号标签
    print(f"---------{text}---------")
    m = EMOTION_PATTERN.search(text)
    if m:
        keyword = m.group(1)
        emotion = EMOTION_MAP.get(keyword)
        clean = EMOTION_PATTERN.sub("", text).strip()
        return clean, emotion

    # 策略2：裸关键词兜底（只在最后 12 字符内找）
    tail = text[-12:]
    m2 = _EMOTION_FALLBACK_PATTERN.search(tail)
    if m2:
        keyword = m2.group(1)
        emotion = EMOTION_MAP.get(keyword)
        return text.strip(), emotion

    # 策略3：全文关键词扫描（只要 AI 回复中带情绪字眼就触发）
    emotion = _scan_emotion_fulltext(text)
    if emotion:
        return text.strip(), emotion

    return text.strip(), None


class ChatHistory:
    """对话历史管理：保留 system + 最近 N 轮 user/assistant。"""

    def __init__(self, system_prompt: str, max_turns: int = 10):
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.max_turns = max_turns
        # 不含 system 的轮次列表
        self._turns: List[Dict[str, str]] = []

    def add_user(self, text: str):
        self._turns.append({"role": "user", "content": text})
        self._trim()

    def add_assistant(self, text: str):
        self._turns.append({"role": "assistant", "content": text})
        self._trim()

    def _trim(self):
        # 一轮 = user+assistant，2 条消息；保留最近 max_turns 轮
        keep = self.max_turns * 2
        if len(self._turns) > keep:
            self._turns = self._turns[-keep:]

    def build_messages(self, user_input: str) -> List[Dict[str, str]]:
        """构造发给模型的 messages。"""
        msgs = [{"role": "system", "content": self.system_prompt}]
        msgs.extend(self._turns)
        msgs.append({"role": "user", "content": user_input})
        return msgs

    def clear(self):
        self._turns.clear()


class ChatWorker(QThread):
    """后台线程：调用 GLM 接口并流式返回结果。"""

    # 流式增量片段（仅纯文本，不含情绪标签）
    chunk_received = Signal(str)
    # 完成：完整文本（去标签）, 情绪
    finished_ok = Signal(str, str)
    # 出错
    error = Signal(str)

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        messages: List[Dict[str, str]],
        stream: bool = True,
        timeout: int = 30,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.messages = messages
        self.stream = stream
        self.timeout = timeout
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            client = self._build_client()
            if self.stream:
                self._run_stream(client)
            else:
                self._run_once(client)
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}")

    # ------------------------------------------------------------------
    def _build_client(self):
        """优先用 zai-sdk（智谱官方），不可用时回退到 openai SDK。"""
        try:
            from zai import ZaiClient  # type: ignore
            # zai-sdk 默认连接 open.bigmodel.cn，base_url 一般可省
            kwargs = {"api_key": self.api_key, "timeout": self.timeout}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            return ("zai", ZaiClient(**kwargs))
        except ImportError:
            pass

        try:
            from openai import OpenAI  # type: ignore
            base = self.base_url or "https://open.bigmodel.cn/api/paas/v4/"
            return ("openai", OpenAI(api_key=self.api_key, base_url=base, timeout=self.timeout))
        except ImportError as e:
            raise RuntimeError(
                "未安装可用的 SDK，请执行：pip install zai-sdk 或 pip install openai"
            ) from e

    def _create_completion(self, client_pair, stream: bool):
        kind, client = client_pair
        # zai-sdk 与 openai SDK 接口完全兼容：client.chat.completions.create
        return client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            stream=stream,
        )

    def _run_stream(self, client_pair):
        full_text = []
        resp = self._create_completion(client_pair, stream=True)
        for chunk in resp:
            if self._cancelled:
                return
            try:
                delta = chunk.choices[0].delta
                piece = getattr(delta, "content", None) or ""
            except (AttributeError, IndexError):
                piece = ""
            if not piece:
                continue
            full_text.append(piece)
            # 边收边发：实时显示给用户（情绪标签也会一起闪过，最终会被清掉）
            self.chunk_received.emit(piece)

        complete = "".join(full_text)
        clean, emotion = split_emotion(complete)
        self.finished_ok.emit(clean, emotion or "")

    def _run_once(self, client_pair):
        resp = self._create_completion(client_pair, stream=False)
        try:
            content = resp.choices[0].message.content or ""
        except (AttributeError, IndexError):
            content = ""
        clean, emotion = split_emotion(content)
        self.finished_ok.emit(clean, emotion or "")
