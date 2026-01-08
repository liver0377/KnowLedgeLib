from typing import Any, Literal, NotRequired, Optional

from pydantic import BaseModel, Field, SerializeAsAny
from typing_extensions import TypedDict

from schema.models import AllModelEnum, AnthropicModelName, OpenAIModelName


class AgentInfo(BaseModel):
    """Info about an available agent."""

    key: str = Field(
        description="Agent key.",
        examples=["research-assistant"],
    )
    description: str = Field(
        description="Description of the agent.",
        examples=["A research assistant for generating research papers."],
    )


class ServiceMetadata(BaseModel):
    """Metadata about the service including available agents and models."""

    agents: list[AgentInfo] = Field(
        description="List of available agents.",
    )
    models: list[AllModelEnum] = Field(
        description="List of available LLMs.",
    )
    default_agent: str = Field(
        description="Default agent used when none is specified.",
        examples=["research-assistant"],
    )
    default_model: AllModelEnum = Field(
        description="Default model used when none is specified.",
    )


class UserInput(BaseModel):
    """Basic user input for the agent."""

    message: str = Field(
        description="User input to the agent.",
        examples=["What is the weather in Tokyo?"],
    )
    model: SerializeAsAny[AllModelEnum] | None = Field(
        title="Model",
        description="LLM Model to use for the agent. Defaults to the default model set in the settings of the service.",
        default=None,
        examples=[OpenAIModelName.GPT_5_NANO, AnthropicModelName.HAIKU_45],
    )
    thread_id: str | None = Field(
        description="Thread ID to persist and continue a multi-turn conversation.",
        default=None,
        examples=["847c6285-8fc9-4560-a83f-4e6285809254"],
    )
    user_id: str | None = Field(
        description="User ID to persist and continue a conversation across multiple threads.",
        default=None,
        examples=["847c6285-8fc9-4560-a83f-4e6285809254"],
    )
    agent_config: dict[str, Any] = Field(
        description="Additional configuration to pass through to the agent",
        default={},
        examples=[{"spicy_level": 0.8}],
    )


class StreamInput(UserInput):
    """User input for streaming the agent's response."""

    stream_tokens: bool = Field(
        description="Whether to stream LLM tokens to the client.",
        default=True,
    )

class LoginInput(BaseModel):
    """ 用户登录时的iput"""
    username: str
    password: str

class RegisterInput(BaseModel):
    """用户注册时的输入"""
    username: str = Field(description="用户名（唯一）", examples=["user-new"])
    password: str = Field(description="密码", examples=["123456"])
    display_name: str = Field(description="显示名称", examples=["新用户"])
    email: str | None = Field(default=None, description="邮箱地址", examples=["user@example.com"])
    dept_id: int | None = Field(default=None, description="申请的部门ID", examples=[1])
    reason: str | None = Field(default=None, description="申请理由", examples=["需要访问该部门的知识库"])

class PendingUserItem(BaseModel):
    """待审批用户项"""
    id: int
    username: str
    display_name: str
    email: str | None
    requested_dept_id: int | None
    dept_name: str | None = None
    dept_key: str | None = None
    reason: str | None
    status: str
    created_at: str

class PendingUsersResponse(BaseModel):
    """待审批用户列表响应"""
    items: list[PendingUserItem]

class ApproveUserInput(BaseModel):
    """审批用户输入"""
    dept_id: int = Field(description="分配的部门ID", examples=[1])
    comment: str | None = Field(default=None, description="审批意见", examples=["同意申请"])

class RejectUserInput(BaseModel):
    """驳回用户输入"""
    comment: str | None = Field(default=None, description="驳回理由", examples=["部门不合适"])

class ToolCall(TypedDict):
    """Represents a request to call a tool."""

    name: str
    """The name of the tool to be called."""
    args: dict[str, Any]
    """The arguments to the tool call."""
    id: str | None
    """An identifier associated with the tool call."""
    type: NotRequired[Literal["tool_call"]]


class ChatMessage(BaseModel):
    """Message in a chat."""

    type: Literal["human", "ai", "tool", "custom"] = Field(
        description="Role of the message.",
        examples=["human", "ai", "tool", "custom"],
    )
    content: str = Field(
        description="Content of the message.",
        examples=["Hello, world!"],
    )
    tool_calls: list[ToolCall] = Field(
        description="Tool calls in the message.",
        default=[],
    )
    tool_call_id: str | None = Field(
        description="Tool call that this message is responding to.",
        default=None,
        examples=["call_Jja7J89XsjrOLA5r!MEOW!SL"],
    )
    run_id: str | None = Field(
        description="Run ID of the message.",
        default=None,
        examples=["847c6285-8fc9-4560-a83f-4e6285809254"],
    )
    response_metadata: dict[str, Any] = Field(
        description="Response metadata. For example: response headers, logprobs, token counts.",
        default={},
    )
    custom_data: dict[str, Any] = Field(
        description="Custom message data.",
        default={},
    )

    def pretty_repr(self) -> str:
        """Get a pretty representation of the message."""
        base_title = self.type.title() + " Message"
        padded = " " + base_title + " "
        sep_len = (80 - len(padded)) // 2
        sep = "=" * sep_len
        second_sep = sep + "=" if len(padded) % 2 else sep
        title = f"{sep}{padded}{second_sep}"
        return f"{title}\n\n{self.content}"

    def pretty_print(self) -> None:
        print(self.pretty_repr())  # noqa: T201


class Feedback(BaseModel):  # type: ignore[no-redef]
    """Feedback for a run, to record to LangSmith."""

    run_id: str = Field(
        description="Run ID to record feedback for.",
        examples=["847c6285-8fc9-4560-a83f-4e6285809254"],
    )
    key: str = Field(
        description="Feedback key.",
        examples=["human-feedback-stars"],
    )
    score: float = Field(
        description="Feedback score.",
        examples=[0.8],
    )
    kwargs: dict[str, Any] = Field(
        description="Additional feedback kwargs, passed to LangSmith.",
        default={},
        examples=[{"comment": "In-line human feedback"}],
    )


class FeedbackResponse(BaseModel):
    status: Literal["success"] = "success"


class ChatHistoryInput(BaseModel):
    """Input for retrieving chat history."""

    thread_id: str = Field(
        description="Thread ID to persist and continue a multi-turn conversation.",
        examples=["847c6285-8fc9-4560-a83f-4e6285809254"],
    )


class ChatHistory(BaseModel):
    messages: list[ChatMessage]


class KBFileItem(BaseModel):
    file_id: str
    name: str
    type: Literal["pdf"]
    dept_key: str
    size_bytes: int
    updated_at: str  # ISO string
    can_view: bool
    can_edit: bool

class KBFileDetail(BaseModel):
    file_id: str
    name: str
    type: Literal["pdf"]
    dept_key: str
    size_bytes: int
    updated_at: str  # ISO string
    page_count: Optional[int] = None
    can_view: bool
    can_edit: bool
    
class KBFilesResponse(BaseModel):
    items: list[KBFileItem]
    next_cursor: Optional[int] = None


class UpdatePermissionsInput(BaseModel):
    """更新用户权限的请求体"""
    roles: list[str] = Field(
        description="用户角色列表",
        examples=[["viewer"], ["editor"], ["admin"]],
    )

class UploadFileResponse(BaseModel):
    """上传文件响应"""
    ok: bool
    file_id: str
    name: str
    dept_key: str
    size_bytes: int
    message: str = "File uploaded successfully"

class CreateDeptInput(BaseModel):
    """创建部门请求体"""
    dept_key: str = Field(
        description="部门标识（英文，用于文件存储）",
        examples=["security", "hr", "it"],
    )
    name: str = Field(
        description="部门名称（中文，用于显示）",
        examples=["安全部", "人力资源部", "信息技术部"],
    )

class CreateDeptResponse(BaseModel):
    """创建部门响应"""
    ok: bool
    dept_id: int
    dept_key: str
    name: str
    message: str = "Department created successfully"
