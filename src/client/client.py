import json
import os
import logging
from collections.abc import AsyncGenerator, Generator
from typing import Any, Optional

import httpx

from schema import (
    ChatHistory,
    ChatHistoryInput,
    ChatMessage,
    Feedback,
    ServiceMetadata,
    StreamInput,
    UserInput,
    LoginInput,
)


logger = logging.getLogger(__name__)

class AgentClientError(Exception):
    pass


class AgentClient:
    """Client for interacting with the agent service."""

    def __init__(
        self,
        base_url: str = "http://0.0.0.0",
        agent: str | None = None,
        timeout: float | None = None,
        get_info: bool = True,
    ) -> None:
        """
        Initialize the client.

        Args:
            base_url (str): The base URL of the agent service.
            agent (str): The name of the default agent to use.
            timeout (float, optional): The timeout for requests.
            get_info (bool, optional): Whether to fetch agent information on init.
                Default: True
        """
        self.base_url = base_url.rstrip("/")
        self.auth_secret = os.getenv("AUTH_SECRET")
        self.timeout = timeout
        self.info: ServiceMetadata | None = None
        self.agent: str | None = None

        # IMPORTANT:
        # Keep persistent clients so cookies (JWT) persist across requests.
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=self._headers,
            timeout=self.timeout,
            follow_redirects=True,
        )
        self._aclient = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._headers,
            timeout=self.timeout,
            follow_redirects=True,
        )

        if get_info:
            self.retrieve_info()
        if agent:
            self.update_agent(agent)

    @property
    def _headers(self) -> dict[str, str]:
        """ 请求头"""
        headers: dict[str, str] = {}
        if self.auth_secret:
            headers["Authorization"] = f"Bearer {self.auth_secret}"
        return headers

    def close(self) -> None:
        """Close the sync client."""
        self._client.close()

    async def aclose(self) -> None:
        """Close the async client."""
        await self._aclient.aclose()

    def _raise(self, response: httpx.Response, prefix: str = "Error") -> None:
        """ response 错误处理 """
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            # try to surface backend error detail
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise AgentClientError(f"{prefix}: {e.response.status_code} {detail}")
        except httpx.HTTPError as e:
            raise AgentClientError(f"{prefix}: {e}")

    # -------------------------
    # Public /info
    # -------------------------
    def retrieve_info(self) -> None:
        """ 初始化时检索 ServiceMetaData """
        response = self._client.get("/info")
        self._raise(response, "Error getting service info")

        # 反序列化
        self.info = ServiceMetadata.model_validate(response.json())
        if not self.agent or self.agent not in [a.key for a in self.info.agents]:
            self.agent = self.info.default_agent

    def update_agent(self, agent: str, verify: bool = True) -> None:
        """ 检查agent是否在/info返回的agents列表中 """
        if verify:
            if not self.info:
                self.retrieve_info()
            agent_keys = [a.key for a in self.info.agents]  # type: ignore[union-attr]
            if agent not in agent_keys:
                raise AgentClientError(
                    f"Agent {agent} not found in available agents: {', '.join(agent_keys)}"
                )
        self.agent = agent

    # -------------------------
    # Auth APIs (NEW)
    # -------------------------
    def login(self, username: str, password: str) -> dict[str, Any]:
        """
        POST /auth/login
        Server sets HttpOnly JWT cookie; httpx stores it in this client's cookie jar.
        """
        req = LoginInput(username=username, password=password)
        resp = self._client.post("/auth/login", json=req.model_dump())
        self._raise(resp, "Login failed")
        return resp.json()

    async def alogin(self, username: str, password: str) -> dict[str, Any]:
        req = LoginInput(username=username, password=password)
        resp = await self._aclient.post("/auth/login", json=req.model_dump())
        self._raise(resp, "Login failed")
        return resp.json()

    def logout(self) -> dict[str, Any]:
        resp = self._client.post("/auth/logout")
        self._raise(resp, "Logout failed")
        return resp.json()

    async def alogout(self) -> dict[str, Any]:
        resp = await self._aclient.post("/auth/logout")
        self._raise(resp, "Logout failed")
        return resp.json()

    def me(self) -> dict[str, Any]:
        resp = self._client.get("/auth/me")
        self._raise(resp, "Me failed")
        return resp.json()

    async def ame(self) -> dict[str, Any]:
        resp = await self._aclient.get("/auth/me")
        self._raise(resp, "Me failed")
        return resp.json()

    # -------------------------
    # Invoke
    # -------------------------
    async def ainvoke(
        self,
        message: str,
        model: str | None = None,
        thread_id: str | None = None,
        user_id: str | None = None,
        agent_config: dict[str, Any] | None = None,
    ) -> ChatMessage:

        # logger.info(f"ainvoke()...")

        if not self.agent:
            raise AgentClientError("No agent selected. Use update_agent() to select an agent.")

        request = UserInput(message=message)
        if thread_id:
            request.thread_id = thread_id
        if model:
            request.model = model  # type: ignore[assignment]
        if agent_config:
            request.agent_config = agent_config
        if user_id:
            request.user_id = user_id

        response = await self._aclient.post(f"/{self.agent}/invoke", json=request.model_dump())
        self._raise(response, "Invoke failed")
        # 反序列化为ChatmMessage对象
        return ChatMessage.model_validate(response.json())

    def invoke(
        self,
        message: str,
        model: str | None = None,
        thread_id: str | None = None,
        user_id: str | None = None,
        agent_config: dict[str, Any] | None = None,
    ) -> ChatMessage:

        # logger.info(f"invoke()...")

        if not self.agent:
            raise AgentClientError("No agent selected. Use update_agent() to select an agent.")

        request = UserInput(message=message)
        if thread_id:
            request.thread_id = thread_id
        if model:
            request.model = model  # type: ignore[assignment]
        if agent_config:
            request.agent_config = agent_config
        if user_id:
            request.user_id = user_id

        response = self._client.post(f"/{self.agent}/invoke", json=request.model_dump())
        self._raise(response, "Invoke failed")
        return ChatMessage.model_validate(response.json())

    # -------------------------
    # Stream
    # -------------------------
    def _parse_stream_line(self, line: str) -> ChatMessage | str | None:
        """ 把服务端 流式接口 (SSE风格)返回的一行文本解析为ChatMessage/str/None"""
        line = line.strip()

        # logger.info(f"line: {line}")

        if line.startswith("data: "):
            data = line[6:]
            if data == "[DONE]":
                return None
            try:
                parsed = json.loads(data)
            except Exception as e:
                raise Exception(f"Error JSON parsing message from server: {e}")

            match parsed["type"]:
                case "message":
                    try:
                        return ChatMessage.model_validate(parsed["content"])
                    except Exception as e:
                        raise Exception(f"Server returned invalid message: {e}")
                case "token":
                    return parsed["content"]
                case "error":
                    error_msg = "Error: " + parsed["content"]
                    return ChatMessage(type="ai", content=error_msg)
        return None

    def stream(
        self,
        message: str,
        model: str | None = None,
        thread_id: str | None = None,
        user_id: str | None = None,
        agent_config: dict[str, Any] | None = None,
        stream_tokens: bool = True,
    ) -> Generator[ChatMessage | str, None, None]:
        # logger.info(f"stream()...")
        if not self.agent:
            raise AgentClientError("No agent selected. Use update_agent() to select an agent.")

        request = StreamInput(message=message, stream_tokens=stream_tokens)
        if thread_id:
            request.thread_id = thread_id
        if user_id:
            request.user_id = user_id
        if model:
            request.model = model  # type: ignore[assignment]
        if agent_config:
            request.agent_config = agent_config

        with self._client.stream(
            "POST",
            f"/{self.agent}/stream",
            json=request.model_dump(),
        ) as response:
            self._raise(response, "Stream failed")

            
            # 将响应体当成文本流，按行迭代
            for line in response.iter_lines():
                # 每一行的文本
                # data: {"type":"token","content":"xxx"}
                # ...
                # data: [Done]
                if line.strip():
                    parsed = self._parse_stream_line(line)
                    if parsed is None:
                        break
                    yield parsed

    async def astream(
        self,
        message: str,
        model: str | None = None,
        thread_id: str | None = None,
        user_id: str | None = None,
        agent_config: dict[str, Any] | None = None,
        stream_tokens: bool = True,
    ) -> AsyncGenerator[ChatMessage | str, None]:
        logger.info("astream()...")
        if not self.agent:
            raise AgentClientError("No agent selected. Use update_agent() to select an agent.")

        request = StreamInput(message=message, stream_tokens=stream_tokens)
        if thread_id:
            request.thread_id = thread_id
        if model:
            request.model = model  # type: ignore[assignment]
        if agent_config:
            request.agent_config = agent_config
        if user_id:
            request.user_id = user_id

        async with self._aclient.stream(
            "POST",
            f"/{self.agent}/stream",
            json=request.model_dump(),
        ) as response:
            self._raise(response, "Stream failed")

            async for line in response.aiter_lines():
                if line.strip():
                    parsed = self._parse_stream_line(line)
                    if parsed is None:
                        break
                    if parsed != "":
                        yield parsed

    # -------------------------
    # Feedback
    # -------------------------
    async def acreate_feedback(
        self, run_id: str, key: str, score: float, kwargs: Optional[dict[str, Any]] = None
    ) -> None:
        request = Feedback(run_id=run_id, key=key, score=score, kwargs=kwargs or {})
        response = await self._aclient.post("/feedback", json=request.model_dump())
        self._raise(response, "Create feedback failed")
        response.json()

    # -------------------------
    # History
    # -------------------------
    def get_history(self, thread_id: str) -> ChatHistory:
        request = ChatHistoryInput(thread_id=thread_id)
        response = self._client.post("/history", json=request.model_dump())
        self._raise(response, "Get history failed")
        return ChatHistory.model_validate(response.json())
