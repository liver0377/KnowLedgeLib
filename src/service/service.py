import inspect
import json
import os
import logging
import warnings
import re
from pathlib import Path
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from urllib.parse import quote
from typing import Annotated, Any, Optional, Tuple
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL
from datetime import datetime, timezone

from fastapi import Query, UploadFile, File
from fastapi import APIRouter, Depends, FastAPI, HTTPException, status, Response
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from langchain_core._api import LangChainBetaWarning
from langchain_core.messages import AIMessage, AIMessageChunk, AnyMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langfuse import Langfuse  # type: ignore[import-untyped]
from langfuse.langchain import (
    CallbackHandler,  # type: ignore[import-untyped]
)
from langgraph.types import Command, Interrupt
from langsmith import Client as LangsmithClient

from agents import DEFAULT_AGENT, AgentGraph, get_agent, get_all_agent_info, load_agent
from core import settings
from memory import initialize_database, initialize_store
from schema import (
    ChatHistory,
    ChatHistoryInput,
    ChatMessage,
    Feedback,
    FeedbackResponse,
    ServiceMetadata,
    StreamInput,
    UserInput,
    LoginInput,
    RegisterInput,
    PendingUserItem,
    PendingUsersResponse,
    ApproveUserInput,
    RejectUserInput,
    KBFilesResponse,
    KBFileItem,
    KBFileDetail,
    UpdatePermissionsInput,
    UploadFileResponse,
    CreateDeptInput,
    CreateDeptResponse,
)
from service.utils import (
    convert_message_content_to_string,
    langchain_to_chat_message,
    remove_tool_calls,
)
from service.auth import (
    create_access_token,
    get_user_context,
    require_admin,
    can_access_dept,
    can_write_dept,
    permission_manager,
)
from service.db import RBACDAO


warnings.filterwarnings("ignore", category=LangChainBetaWarning)
logger = logging.getLogger(__name__)


def custom_generate_unique_id(route: APIRoute) -> str:
    """Generate idiomatic operation IDs for OpenAPI client generation."""
    return route.name


def verify_bearer(
    http_auth: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(HTTPBearer(description="Please provide AUTH_SECRET api key.", auto_error=False)),
    ],
) -> None:
    if not settings.AUTH_SECRET:
        return
    auth_secret = settings.AUTH_SECRET.get_secret_value()
    if not http_auth or http_auth.credentials != auth_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Configurable lifespan that initializes the appropriate database checkpointer, store,
    and agents with async loading - for example for starting up MCP clients.
    """
    try:
        # Initialize both checkpointer (for short-term memory) and store (for long-term memory)
        async with initialize_database() as saver, initialize_store() as store:
            # Set up both components
            if hasattr(saver, "setup"):  # ignore: union-attr
                await saver.setup()
            # Only setup store for Postgres as InMemoryStore doesn't need setup
            if hasattr(store, "setup"):  # ignore: union-attr
                await store.setup()

            # Configure agents with both memory components and async loading
            agents = get_all_agent_info()
            for a in agents:
                try:
                    await load_agent(a.key)
                    logger.info(f"Agent loaded: {a.key}")
                except Exception as e:
                    logger.error(f"Failed to load agent {a.key}: {e}")
                    # Continue with other agents rather than failing startup

                agent = get_agent(a.key)
                # Set checkpointer for thread-scoped memory (conversation history)
                agent.checkpointer = saver
                # Set store for long-term memory (cross-conversation knowledge)
                agent.store = store
            yield
    except Exception as e:
        logger.error(f"Error during database/store/agents initialization: {e}")
        raise


app = FastAPI(lifespan=lifespan, generate_unique_id_function=custom_generate_unique_id)
# 给所有接口添加verify_token依赖，每个接口会先跑verify_bearer
# router = APIRouter(dependencies=[Depends(verify_bearer)])

# 公开接口: /health, /info
public_router = APIRouter()
# 需要登录的接口: /invoke, /stream, /history, /feedback
# protected_router = APIRouter(dependencies=[Depends(get_current_user)])
protected_router = APIRouter(dependencies=[Depends(get_user_context)])
# 保留AUTH_SECRET给后台任务使用
internal_router = APIRouter(prefix="/internal", dependencies=[Depends(verify_bearer)])
# 专门用于鉴权的接口: /login, /logout, /me
auth_router = APIRouter(prefix="/auth", tags=["auth"])
# 知识库专用接口
kb_router = APIRouter(prefix="/kb", tags=["kb"], dependencies=[Depends(get_user_context)])
# 管理员接口
admin_router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_user_context)])


@auth_router.post("/login")
async def login(data: LoginInput, response: Response):
    """用户登录：从数据库验证用户名和密码"""
    # 从数据库查询用户
    user = RBACDAO.get_user_by_username(data.username)

    # 找不到用户或者密码不对
    if not user:
        logger.warning(f"Login failed: user not found - {data.username}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad credentials")

    # 验证密码
    if not RBACDAO.verify_password(user["password_hash"], data.password):
        logger.warning(f"Login failed: invalid password - {data.username}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad credentials")

    # 获取用户角色
    user_id = user["id"]
    roles = RBACDAO.get_user_roles(user_id)

    # 生成JWT token
    token = create_access_token(sub=str(user_id), roles=roles)

    logger.info(f"User logged in: {data.username} (id={user_id}, roles={roles})")

    # 本地开发：secure=False；上线 HTTPS：secure=True
    # 设置cookie
    response.set_cookie(
        key=settings.JWT_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.JWT_EXPIRES_SECONDS,
        path="/",
    )
    return {"ok": True}


@auth_router.post("/register")
async def register(data: RegisterInput):
    """用户注册：创建待审批用户，等待管理员审批"""
    # 验证用户名长度
    if len(data.username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username must be at least 3 characters"
        )

    if len(data.username) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be less than 50 characters",
        )

    # 验证密码长度
    if len(data.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters"
        )

    # 验证显示名称
    if not data.display_name or len(data.display_name.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Display name is required"
        )

    # 创建待审批用户（如果用户名已存在会返回None）
    pending_id = RBACDAO.create_pending_user(
        username=data.username,
        password=data.password,
        display_name=data.display_name,
        email=data.email,
        dept_id=data.dept_id,
        reason=data.reason,
    )

    if pending_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists or pending approval",
        )

    logger.info(f"User registration submitted: {data.username} (pending_id={pending_id})")

    return {
        "ok": True,
        "message": "Registration submitted successfully. Please wait for admin approval.",
        "pending_id": pending_id,
        "username": data.username,
    }


@public_router.get("/departments")
async def list_departments_for_registration():
    """获取所有部门列表（用于注册时选择部门）"""
    departments = RBACDAO.list_all_departments()
    return {"items": departments}


@auth_router.post("/logout")
async def logout(
    response: Response,
    user: dict[str, Any] = Depends(get_user_context),
):
    response.delete_cookie(settings.JWT_COOKIE_NAME, path="/")
    return {"ok": True}


@auth_router.get("/me")
async def me(user: dict[str, Any] = Depends(get_user_context)):
    """返回已登录用户的用户身份"""
    return user


@public_router.get("/info")
async def info() -> ServiceMetadata:
    models = list(settings.AVAILABLE_MODELS)
    models.sort()
    return ServiceMetadata(
        agents=get_all_agent_info(),
        models=models,
        default_agent=DEFAULT_AGENT,
        default_model=settings.DEFAULT_MODEL,
    )


def _make_file_id(dept_key: str, filename: str) -> str:
    # 必须与 list 接口保持一致
    return str(uuid5(NAMESPACE_URL, f"{dept_key}/{filename}"))


def _can_edit_file(user: dict[str, Any], dept_key: str) -> bool:
    if not permission_manager.has_permission(user, "kb", "file:upload"):
        return False
    return can_write_dept(user, dept_key)


def _find_visible_pdf_by_id(
    root: Path, user: dict[str, Any], file_id: str
) -> Optional[Tuple[Path, str, str]]:
    # returns (path, dept_key, filename) or None

    # Get valid departments from database to ensure we only access active departments
    try:
        db_depts = RBACDAO.list_all_departments()
        valid_dept_keys = {d["dept_key"] for d in db_depts if d["is_active"]}
    except Exception as e:
        logger.error(f"Failed to load departments from database: {e}")
        # If database query fails, fall back to file system (but still check permissions)
        valid_dept_keys = None

    for dept_dir in sorted([p for p in root.iterdir() if p.is_dir()]):
        dk = dept_dir.name

        # Skip departments not in database (if database filtering is enabled)
        if valid_dept_keys is not None and dk not in valid_dept_keys:
            continue

        if not can_access_dept(user, dk):
            continue
        for f in dept_dir.iterdir():
            if f.is_file() and f.suffix.lower() == ".pdf":
                if _make_file_id(dk, f.name) == file_id:
                    return (f, dk, f.name)
    return None


@kb_router.get("/files", response_model=KBFilesResponse)
async def list_kb_files(
    user: dict[str, Any] = Depends(get_user_context),
    q: str | None = Query(default=None, description="Search by filename"),
    dept_key: str | None = Query(default=None, description="Filter by dept_key"),
    type: str | None = Query(default="pdf", description="Only 'pdf' supported for now"),
    cursor: int = Query(default=0, ge=0, description="Offset for pagination"),
    limit: int = Query(default=50, ge=1, le=200, description="Page size"),
) -> KBFilesResponse:
    permission_manager.require_permission(user, "kb", "file:list")

    # 1) Resolve KB root dir (可用环境变量覆盖)
    kb_root = getattr(settings, "KB_FILES_ROOT", None)
    kb_root = kb_root or os.getenv("KB_FILES_ROOT")
    root = Path(kb_root).resolve()

    if not root.exists():
        # 没有知识库目录也不要 500，前端当空列表即可
        return KBFilesResponse(items=[], next_cursor=None)

    # 2) Get all departments from database (only active ones)
    # 这样确保只显示数据库中存在的部门，而不是文件系统中所有目录
    try:
        db_depts = RBACDAO.list_all_departments()
        valid_dept_keys = {d["dept_key"] for d in db_depts if d["is_active"]}
    except Exception as e:
        logger.error(f"Failed to load departments from database: {e}")
        # 如果数据库查询失败，降级为从文件系统读取
        valid_dept_keys = None

    # 3) Collect pdf files
    items: list[KBFileItem] = []
    # 期望结构：root/<dept_key>/*.pdf
    for dept_dir in sorted([p for p in root.iterdir() if p.is_dir()]):
        dk = dept_dir.name

        # 如果启用了数据库部门过滤，跳过数据库中不存在的部门
        if valid_dept_keys is not None and dk not in valid_dept_keys:
            continue

        if dept_key and dk != dept_key:
            continue

        if not can_access_dept(user, dk):
            continue

        for f in sorted(dept_dir.iterdir()):
            if not f.is_file():
                continue
            if type and type != "pdf":
                continue
            if f.suffix.lower() != ".pdf":
                continue

            name = f.name
            if q and (q.lower() not in name.lower()):
                continue

            stat = f.stat()
            updated_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

            # 稳定 file_id：用 dept_key + 相对路径生成 uuid5
            fid = _make_file_id(dk, name)

            items.append(
                KBFileItem(
                    file_id=fid,
                    name=name,
                    type="pdf",
                    dept_key=dk,
                    size_bytes=stat.st_size,
                    updated_at=updated_at,
                    can_view=True,
                    can_edit=_can_edit_file(user, dk),
                )
            )

    # 4) Pagination: cursor is offset
    total = len(items)
    page = items[cursor : cursor + limit]
    next_cursor = cursor + limit if (cursor + limit) < total else None

    return KBFilesResponse(items=page, next_cursor=next_cursor)


@kb_router.get("/files/{file_id}", response_model=KBFileDetail)
async def get_kb_file_detail(
    file_id: str,
    user: dict[str, Any] = Depends(get_user_context),
) -> KBFileDetail:
    permission_manager.require_permission(user, "kb", "file:detail")

    # 1) Resolve KB root dir
    kb_root = getattr(settings, "KB_FILES_ROOT", None)
    kb_root = kb_root or os.getenv("KB_FILES_ROOT")
    root = Path(kb_root).resolve()

    if not root.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # 2) Use helper to find visible pdf by file_id
    found = _find_visible_pdf_by_id(root, user, file_id)
    if not found:
        # 不区分“不存在”和“无权限”，统一 404
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    target_path, target_dept, target_name = found

    stat = target_path.stat()
    updated_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

    # 3) Try to compute page_count (optional)
    page_count: int | None = None
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(target_path))
        page_count = len(reader.pages)
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore

            reader = PdfReader(str(target_path))
            page_count = len(reader.pages)
        except Exception:
            page_count = None

    return KBFileDetail(
        file_id=file_id,
        name=target_name,
        type="pdf",
        dept_key=target_dept,
        size_bytes=stat.st_size,
        updated_at=updated_at,
        page_count=page_count,
        can_view=True,
        can_edit=_can_edit_file(user, target_dept),
    )


@kb_router.get("/files/{file_id}/download")
async def download_kb_file(
    file_id: str,
    user: dict[str, Any] = Depends(get_user_context),
) -> FileResponse:
    permission_manager.require_permission(user, "kb", "file:download")

    kb_root = getattr(settings, "KB_FILES_ROOT", None) or os.getenv("KB_FILES_ROOT") or "./kb_files"
    root = Path(kb_root).resolve()

    if not root.exists():
        raise HTTPException(status_code=404, detail="File not found")

    found = _find_visible_pdf_by_id(root, user, file_id)
    if not found:
        raise HTTPException(status_code=404, detail="File not found")

    pdf_path, dept_key, filename = found  # dept_key 如暂时不用也保留，方便后续扩展

    quoted = quote(filename)
    headers = {"Content-Disposition": f"inline; filename*=UTF-8''{quoted}"}

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=filename,
        headers=headers,
    )


@kb_router.post("/files/upload", response_model=UploadFileResponse)
async def upload_kb_file(
    dept_key: str = Query(..., description="目标部门标识"),
    file: UploadFile = File(..., description="要上传的文件（目前只支持PDF）"),
    user: dict[str, Any] = Depends(get_user_context),
) -> UploadFileResponse:
    """
    上传文件到指定部门（需要有file:upload权限）

    目前只支持PDF文件，文件会被保存到 KB_FILES_ROOT/<dept_key>/ 目录下
    """
    # 1. 验证权限
    permission_manager.require_permission(user, "kb", "file:upload")

    # 2. 验证部门访问权限
    if not can_write_dept(user, dept_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No permission to upload to department: {dept_key}",
        )

    # 3. 验证文件类型（目前只支持PDF）
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required")

    filename = file.filename
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are supported"
        )

    # 4. 确定保存路径
    kb_root = getattr(settings, "KB_FILES_ROOT", None) or os.getenv("KB_FILES_ROOT") or "./kb_files"
    root = Path(kb_root).resolve()
    dept_dir = root / dept_key

    # 5. 创建部门目录（如果不存在）
    try:
        dept_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create department directory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create department directory: {dept_key}",
        )

    # 6. 保存文件
    file_path = dept_dir / filename
    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # 获取文件大小
        file_size = file_path.stat().st_size

        # 生成file_id（与list接口保持一致）
        file_id = _make_file_id(dept_key, filename)

        logger.info(
            f"File uploaded successfully: dept_key={dept_key}, filename={filename}, user={user.get('username')}, size={file_size}"
        )

        return UploadFileResponse(
            ok=True,
            file_id=file_id,
            name=filename,
            dept_key=dept_key,
            size_bytes=file_size,
            message="File uploaded successfully",
        )

    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}",
        )


async def _handle_input(
    user_input: UserInput, agent: AgentGraph, user: dict[str, Any]
) -> tuple[dict[str, Any], UUID]:
    """
    Parse user input and handle any required interrupt resumption.
    Returns kwargs for agent invocation and the run_id.
    """
    run_id = uuid4()
    thread_id = user_input.thread_id or str(uuid4())

    user_id = user.get("user_id")
    roles = user.get("roles", [])
    allowed_dept_keys = user.get("allowed_dept_keys", [])

    configurable = {
        "thread_id": thread_id,
        "user_id": user_id,
        "roles": roles,
        "allowed_dept_keys": allowed_dept_keys,
    }

    if user_input.model is not None:
        configurable["model"] = user_input.model

    callbacks: list[Any] = []
    if settings.LANGFUSE_TRACING:
        # Initialize Langfuse CallbackHandler for Langchain (tracing)
        langfuse_handler = CallbackHandler()

        callbacks.append(langfuse_handler)

    if user_input.agent_config:
        # Check for reserved keys (including 'model' even if not in configurable)
        reserved_keys = {"thread_id", "user_id", "model"}
        if overlap := reserved_keys & user_input.agent_config.keys():
            raise HTTPException(
                status_code=422,
                detail=f"agent_config contains reserved keys: {overlap}",
            )
        configurable.update(user_input.agent_config)

    config = RunnableConfig(
        configurable=configurable,
        run_id=run_id,
        callbacks=callbacks,
    )

    # Check for interrupts that need to be resumed
    state = await agent.aget_state(config=config)
    interrupted_tasks = [
        task for task in state.tasks if hasattr(task, "interrupts") and task.interrupts
    ]

    input: Command | dict[str, Any]
    if interrupted_tasks:
        # assume user input is response to resume agent execution from interrupt
        input = Command(resume=user_input.message)
    else:
        input = {"messages": [HumanMessage(content=user_input.message)]}

    kwargs = {
        "input": input,
        "config": config,
    }

    return kwargs, run_id


@protected_router.post("/{agent_id}/invoke", operation_id="invoke_with_agent_id")
@protected_router.post("/invoke")
async def invoke(
    user_input: UserInput,
    agent_id: str = DEFAULT_AGENT,
    user: dict[str, Any] = Depends(get_user_context),
) -> ChatMessage:
    """
    Invoke an agent with user input to retrieve a final response.

    If agent_id is not provided, the default agent will be used.
    Use thread_id to persist and continue a multi-turn conversation. run_id kwarg
    is also attached to messages for recording feedback.
    Use user_id to persist and continue a conversation across multiple threads.
    """
    # NOTE: Currently this only returns the last message or interrupt.
    # In the case of an agent outputting multiple AIMessages (such as the background step
    # in interrupt-agent, or a tool step in research-assistant), it's omitted. Arguably,
    # you'd want to include it. You could update the API to return a list of ChatMessages
    # in that case.
    agent: AgentGraph = get_agent(agent_id)
    kwargs, run_id = await _handle_input(user_input, agent, user)

    try:
        response_events: list[tuple[str, Any]] = await agent.ainvoke(**kwargs, stream_mode=["updates", "values"])  # type: ignore # fmt: skip
        response_type, response = response_events[-1]
        if response_type == "values":
            # Normal response, the agent completed successfully
            output = langchain_to_chat_message(response["messages"][-1])
        elif response_type == "updates" and "__interrupt__" in response:
            # The last thing to occur was an interrupt
            # Return the value of the first interrupt as an AIMessage
            output = langchain_to_chat_message(
                AIMessage(content=response["__interrupt__"][0].value)
            )
        else:
            raise ValueError(f"Unexpected response type: {response_type}")

        output.run_id = str(run_id)
        return output
    except Exception as e:
        logger.error(f"An exception occurred: {e}")
        raise HTTPException(status_code=500, detail="Unexpected error")


async def message_generator(
    user_input: StreamInput, agent_id: str = DEFAULT_AGENT, user: dict[str, Any] = None
) -> AsyncGenerator[str, None]:
    """
    Generate a stream of messages from the agent.

    This is the workhorse method for the /stream endpoint.
    """
    agent: AgentGraph = get_agent(agent_id)
    kwargs, run_id = await _handle_input(user_input, agent, user)

    logger.info(f"Starting stream with stream_tokens={user_input.stream_tokens}")

    try:
        # Process streamed events from the graph and yield messages over the SSE stream.
        async for stream_event in agent.astream(
            **kwargs, stream_mode=["updates", "messages", "custom"], subgraphs=True
        ):
            if not isinstance(stream_event, tuple):
                continue
            # Handle different stream event structures based on subgraphs
            if len(stream_event) == 3:
                # With subgraphs=True: (node_path, stream_mode, event)
                _, stream_mode, event = stream_event
            else:
                # Without subgraphs: (stream_mode, event)
                stream_mode, event = stream_event

            # When stream_tokens is enabled, skip updates/custom modes entirely
            # to avoid overwriting the token-by-token content
            if user_input.stream_tokens and stream_mode in ["updates", "custom"]:
                continue

            new_messages = []
            if stream_mode == "updates":
                for node, updates in event.items():
                    # A simple approach to handle agent interrupts.
                    # In a more sophisticated implementation, we could add
                    # some structured ChatMessage type to return the interrupt value.
                    if node == "__interrupt__":
                        interrupt: Interrupt
                        for interrupt in updates:
                            new_messages.append(AIMessage(content=interrupt.value))
                        continue
                    updates = updates or {}
                    update_messages = updates.get("messages", [])
                    # special cases for using langgraph-supervisor library
                    if "supervisor" in node or "sub-agent" in node:
                        # the only tools that come from the actual agent are the handoff and handback tools
                        if isinstance(update_messages[-1], ToolMessage):
                            if "sub-agent" in node and len(update_messages) > 1:
                                # If this is a sub-agent, we want to keep the last 2 messages - the handback tool, and it's result
                                update_messages = update_messages[-2:]
                            else:
                                # If this is a supervisor, we want to keep the last message only - the handoff result. The tool comes from the 'agent' node.
                                update_messages = [update_messages[-1]]
                        else:
                            update_messages = []
                    new_messages.extend(update_messages)

            if stream_mode == "custom":
                new_messages = [event]

            # LangGraph streaming may emit tuples: (field_name, field_value)
            # e.g. ('content', <str>), ('tool_calls', [ToolCall,...]), ('additional_kwargs', {...}), etc.
            # We accumulate only supported fields into `parts` and skip unsupported metadata.
            # More info at: https://langchain-ai.github.io/langgraph/cloud/how-tos/stream_messages/
            processed_messages = []
            current_message: dict[str, Any] = {}
            for message in new_messages:
                if isinstance(message, tuple):
                    key, value = message
                    # Store parts in temporary dict
                    current_message[key] = value
                else:
                    # Add complete message if we have one in progress
                    if current_message:
                        processed_messages.append(_create_ai_message(current_message))
                        current_message = {}
                    processed_messages.append(message)

            # Add any remaining message parts
            if current_message:
                processed_messages.append(_create_ai_message(current_message))

            for message in processed_messages:
                try:
                    chat_message = langchain_to_chat_message(message)
                    chat_message.run_id = str(run_id)
                except Exception as e:
                    logger.error(f"Error parsing message: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'content': 'Unexpected error'})}\n\n"
                    continue
                # LangGraph re-sends the input message, which feels weird, so drop it
                if chat_message.type == "human" and chat_message.content == user_input.message:
                    continue
                yield f"data: {json.dumps({'type': 'message', 'content': chat_message.model_dump()})}\n\n"

            if stream_mode == "messages":
                if not user_input.stream_tokens:
                    continue
                msg, metadata = event
                if "skip_stream" in metadata.get("tags", []):
                    continue
                # For some reason, astream("messages") causes non-LLM nodes to send extra messages.
                # Drop them.
                if not isinstance(msg, AIMessageChunk):
                    continue
                content = remove_tool_calls(msg.content)
                if content:
                    # Empty content in the context of OpenAI usually means
                    # that the model is asking for a tool to be invoked.
                    # So we only print non-empty content.
                    yield f"data: {json.dumps({'type': 'token', 'content': convert_message_content_to_string(content)})}\n\n"
    except Exception as e:
        logger.error(f"Error in message generator: {e}")
        yield f"data: {json.dumps({'type': 'error', 'content': 'Internal server error'})}\n\n"
    finally:
        yield "data: [DONE]\n\n"


def _create_ai_message(parts: dict) -> AIMessage:
    sig = inspect.signature(AIMessage)
    valid_keys = set(sig.parameters)
    filtered = {k: v for k, v in parts.items() if k in valid_keys}
    return AIMessage(**filtered)


def _sse_response_example() -> dict[int | str, Any]:
    return {
        status.HTTP_200_OK: {
            "description": "Server Sent Event Response",
            "content": {
                "text/event-stream": {
                    "example": "data: {'type': 'token', 'content': 'Hello'}\n\ndata: {'type': 'token', 'content': ' World'}\n\ndata: [DONE]\n\n",
                    "schema": {"type": "string"},
                }
            },
        }
    }


@protected_router.post(
    "/{agent_id}/stream",
    response_class=StreamingResponse,
    responses=_sse_response_example(),
    operation_id="stream_with_agent_id",
)
@protected_router.post(
    "/stream", response_class=StreamingResponse, responses=_sse_response_example()
)
async def stream(
    user_input: StreamInput,
    agent_id: str = DEFAULT_AGENT,
    user: dict[str, Any] = Depends(get_user_context),
) -> StreamingResponse:
    """
    Stream an agent's response to a user input, including intermediate messages and tokens.

    If agent_id is not provided, the default agent will be used.
    Use thread_id to persist and continue a multi-turn conversation. run_id kwarg
    is also attached to all messages for recording feedback.
    Use user_id to persist and continue a conversation across multiple threads.

    Set `stream_tokens=false` to return intermediate messages but not token-by-token.
    """
    return StreamingResponse(
        message_generator(user_input, agent_id, user),
        media_type="text/event-stream",
    )


@protected_router.post("/feedback")
async def feedback(feedback: Feedback) -> FeedbackResponse:
    """
    Record feedback for a run to LangSmith.

    This is a simple wrapper for the LangSmith create_feedback API, so the
    credentials can be stored and managed in the service rather than the client.
    See: https://api.smith.langchain.com/redoc#tag/feedback/operation/create_feedback_api_v1_feedback_post
    """
    client = LangsmithClient()
    kwargs = feedback.kwargs or {}
    client.create_feedback(
        run_id=feedback.run_id,
        key=feedback.key,
        score=feedback.score,
        **kwargs,
    )
    return FeedbackResponse()


@protected_router.post("/history")
async def history(input: ChatHistoryInput) -> ChatHistory:
    agent: AgentGraph = get_agent(DEFAULT_AGENT)
    try:
        state_snapshot = await agent.aget_state(
            config=RunnableConfig(configurable={"thread_id": input.thread_id})
        )

        values = getattr(state_snapshot, "values", None) or {}
        messages: list[AnyMessage] = values.get("messages", []) or []

        chat_messages: list[ChatMessage] = [langchain_to_chat_message(m) for m in messages]
        return ChatHistory(messages=chat_messages)

    except Exception as e:
        logger.error(f"An exception occurred: {e}")
        raise HTTPException(status_code=500, detail="Unexpected error")


@public_router.get("/health")
async def health_check():
    """Health check endpoint."""

    health_status = {"status": "ok"}

    if settings.LANGFUSE_TRACING:
        try:
            langfuse = Langfuse()
            health_status["langfuse"] = "connected" if langfuse.auth_check() else "disconnected"
        except Exception as e:
            logger.error(f"Langfuse connection error: {e}")
            health_status["langfuse"] = "disconnected"

    return health_status


# ============== Admin 接口 ==============


@admin_router.get("/users")
async def list_users(user: dict[str, Any] = Depends(get_user_context)):
    """获取所有用户列表（仅管理员可用）"""
    require_admin(user)

    # 从数据库获取所有用户
    users = RBACDAO.list_all_users()

    # 转换为API返回格式
    result = []
    for u in users:
        # 获取用户的部门信息
        departments = RBACDAO.get_user_departments(u["id"])
        dept_info = [
            {
                "dept_key": d["dept_key"],
                "dept_name": d["dept_name"],
                "can_write": d["can_write"],
                "dept_role": d["dept_role"],
            }
            for d in departments
        ]

        result.append(
            {
                "id": str(u["id"]),
                "name": u.get("display_name") or u["username"],  # 优先使用display_name
                "username": u["username"],
                "email": u.get("email"),
                "is_active": u["is_active"],
                "roles": u["roles"],
                "departments": dept_info,
            }
        )
    return result


@admin_router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    user: dict[str, Any] = Depends(get_user_context),
):
    """删除用户（仅管理员可用）"""
    require_admin(user)

    # 不允许删除自己
    if str(user["user_id"]) == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself"
        )

    # 删除用户
    success = RBACDAO.delete_user(int(user_id))

    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    logger.info(f"User deleted: user_id={user_id}, operator={user['user_id']}")

    return {"ok": True, "message": "User deleted successfully"}


@admin_router.post("/users/{user_id}/permissions")
async def update_user_permissions(
    user_id: str,
    data: UpdatePermissionsInput,
    user: dict[str, Any] = Depends(get_user_context),
):
    """更新用户权限（仅管理员可用）"""
    require_admin(user)

    # 验证角色值
    valid_roles = {"admin", "member"}
    for role in data.roles:
        logger.info(f"role: {role}")
        if role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {role}. Valid roles are: {valid_roles}",
            )

    # 更新数据库中的用户角色
    success = RBACDAO.update_user_roles(user_id, data.roles)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user permissions",
        )

    logger.info(
        f"User permissions updated: user_id={user_id}, roles={data.roles}, operator={user['user_id']}"
    )

    return {"ok": True, "user_id": user_id, "roles": data.roles}


@kb_router.delete("/files/{file_id}")
async def delete_kb_file(
    file_id: str,
    user: dict[str, Any] = Depends(get_user_context),
):
    """
    删除知识库文件（需要有file:delete权限）

    从文件系统中删除指定文件，不涉及数据库记录（因为文件信息不存在于数据库中）
    """
    # 1. 验证权限
    permission_manager.require_permission(user, "kb", "file:delete")

    # 2. 解析文件ID获取dept_key和filename
    kb_root = getattr(settings, "KB_FILES_ROOT", None) or os.getenv("KB_FILES_ROOT") or "./kb_files"
    root = Path(kb_root).resolve()

    # 查找文件
    found = _find_visible_pdf_by_id(root, user, file_id)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    pdf_path, dept_key, filename = found

    # 3. 验证部门上传权限
    if not can_write_dept(user, dept_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No permission to delete files from department: {dept_key}",
        )

    # 4. 删除文件
    try:
        # 4.1. 先计算 doc_id（文件还存在）
        from service.milvus_service import sha1_file, delete_document_from_milvus

        try:
            doc_id = sha1_file(str(pdf_path))
        except Exception as e:
            logger.warning(f"Cannot compute doc_id: {e}")
            doc_id = None

        # 4.2. 删除文件
        os.remove(pdf_path)

        # 4.3. 删除向量数据（使用已计算的 doc_id）
        if doc_id:
            try:
                deleted_count = delete_document_from_milvus(
                    file_path=str(pdf_path),
                    dept_key=dept_key,
                    filename=filename,
                    doc_id=doc_id,
                )
                logger.info(f"Vector data deleted: {deleted_count} chunks, file: {filename}")
            except Exception as e:
                logger.warning(f"Failed to delete vector data: {e}")

        logger.info(
            f"File deleted: dept_key={dept_key}, filename={filename}, user={user.get('username')}"
        )
        return {"ok": True, "message": "File deleted successfully"}
    except Exception as e:
        logger.error(f"Failed to delete file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}",
        )


@admin_router.get("/pending-users", response_model=PendingUsersResponse)
async def list_pending_users(user: dict[str, Any] = Depends(get_user_context)):
    """获取所有待审批用户（仅管理员可用）"""
    require_admin(user)

    pending_users = RBACDAO.list_pending_users()

    # 将 datetime 对象转换为 ISO 字符串
    for user_item in pending_users:
        if "created_at" in user_item and isinstance(user_item["created_at"], datetime):
            user_item["created_at"] = user_item["created_at"].isoformat()
        if "reviewed_at" in user_item and isinstance(user_item["reviewed_at"], datetime):
            user_item["reviewed_at"] = user_item["reviewed_at"].isoformat()

    return PendingUsersResponse(items=pending_users)


@admin_router.post("/pending-users/{pending_id}/approve")
async def approve_user(
    pending_id: int,
    data: ApproveUserInput,
    user: dict[str, Any] = Depends(get_user_context),
):
    """审批通过用户（仅管理员可用）"""
    require_admin(user)

    admin_id = int(user["user_id"])
    user_id = RBACDAO.approve_user(pending_id, data.dept_id, admin_id, data.comment)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending user not found or already processed",
        )

    logger.info(
        f"User approved: pending_id={pending_id}, user_id={user_id}, dept_id={data.dept_id}, admin={admin_id}"
    )

    return {"ok": True, "message": "User approved successfully", "user_id": user_id}


@admin_router.post("/pending-users/{pending_id}/reject")
async def reject_user(
    pending_id: int,
    data: RejectUserInput,
    user: dict[str, Any] = Depends(get_user_context),
):
    """驳回用户申请（仅管理员可用）"""
    require_admin(user)

    admin_id = int(user["user_id"])
    success = RBACDAO.reject_user(pending_id, admin_id, data.comment)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending user not found or already processed",
        )

    logger.info(f"User rejected: pending_id={pending_id}, admin={admin_id}")

    return {"ok": True, "message": "User rejected successfully"}


@admin_router.post("/users/{user_id}/departments/{dept_key}/{action}")
async def update_user_department(
    user_id: str,
    dept_key: str,
    action: str,
    user: dict[str, Any] = Depends(get_user_context),
):
    """
    更新用户对部门的访问权限

    支持的action:
    - set_admin: 设置为部门管理员 (can_write=1, dept_role='editor')
    - unset_admin: 取消部门管理员 (can_write=0, dept_role='viewer')
    - set_read: 设置读权限 (can_read=1)
    - unset_read: 取消读权限 (can_read=0)
    - set_write: 设置写权限 (can_write=1, dept_role='editor')
    - unset_write: 取消写权限 (can_write=0, dept_role='viewer')
    - remove: 完全移除用户对部门的访问权限
    """
    require_admin(user)

    success = RBACDAO.update_user_department(int(user_id), dept_key, action)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update department access: {action}",
        )

    logger.info(
        f"Department access updated: user_id={user_id}, dept_key={dept_key}, action={action}, operator={user['user_id']}"
    )

    return {
        "ok": True,
        "message": "Department access updated successfully",
        "user_id": user_id,
        "dept_key": dept_key,
        "action": action,
    }


@admin_router.post("/departments", response_model=CreateDeptResponse)
async def create_department(
    data: CreateDeptInput,
    user: dict[str, Any] = Depends(get_user_context),
) -> CreateDeptResponse:
    """
    创建新部门（仅管理员可用）

    部门创建后，会在数据库中创建部门记录，并自动授予创建者该部门的读写权限。
    同时会在文件系统中创建对应的目录。
    """
    # 1. 验证权限：只有管理员可以创建部门
    require_admin(user)

    # 2. 验证部门标识格式
    dept_key = data.dept_key.strip()
    if not dept_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Department key cannot be empty"
        )

    if not re.match(r"^[a-zA-Z0-9_-]+$", dept_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department key can only contain letters, numbers, underscores, and hyphens",
        )

    # 3. 在数据库中创建部门
    user_id = int(user["user_id"])
    dept_id = RBACDAO.create_department(dept_key, data.name, user_id)

    if dept_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Department already exists"
        )

    # 4. 在文件系统中创建部门目录
    kb_root = getattr(settings, "KB_FILES_ROOT", None) or os.getenv("KB_FILES_ROOT") or "./kb_files"
    root = Path(kb_root).resolve()
    dept_dir = root / dept_key

    try:
        dept_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Department directory created: {dept_dir}")
    except Exception as e:
        logger.error(f"Failed to create department directory: {e}")
        # 即使目录创建失败，数据库中的部门记录仍然保留
        # 管理员可以手动创建目录或稍后重试

    logger.info(
        f"Department created successfully: dept_key={dept_key}, name={data.name}, user={user.get('username')}"
    )

    return CreateDeptResponse(
        ok=True,
        dept_id=dept_id,
        dept_key=dept_key,
        name=data.name,
        message="Department created successfully",
    )


app.include_router(public_router)
app.include_router(protected_router)
app.include_router(auth_router)
app.include_router(internal_router)
app.include_router(kb_router)
app.include_router(admin_router)
