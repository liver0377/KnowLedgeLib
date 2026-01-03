import asyncio
import os
import logging
import sys
import urllib.parse
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from pydantic import ValidationError

# 假设这些是你本地的模块，保持原样导入
from client import AgentClient, AgentClientError
from schema import ChatHistory, ChatMessage
from schema.task_data import TaskData, TaskDataStatus
from voice import VoiceManager

# --- UI 配置 ---
APP_TITLE = "Agent Service Toolkit"
APP_ICON = "🧰"
PAGE_LAYOUT = "wide" # 使用宽屏模式更适合展示对话和复杂的工具输出

# Session-state keys
AUTH_USER_KEY = "auth_user"
AGENT_CLIENT_KEY = "agent_client"
THREAD_ID_KEY = "thread_id"
MESSAGES_KEY = "messages"
LAST_MESSAGE_KEY = "last_message"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# --- 自定义 CSS ---
# 这段 CSS 用于覆盖 Streamlit 默认样式，增加现代感
CUSTOM_CSS = """
<style>
    /* 全局字体优化 */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
    }
    
    /* 隐藏 Streamlit 默认的顶部汉堡菜单和 footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* 调整主容器顶部内边距，减少留白 */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 5rem !important;
    }

    /* 侧边栏样式优化 */
    [data-testid="stSidebar"] {
        background-color: #f7f9fb;
        border-right: 1px solid #e0e6ed;
    }
    
    /* 侧边栏标题样式 */
    [data-testid="stSidebarUserContent"] h2 {
        color: #1e293b;
        font-size: 1.2rem;
        margin-bottom: 1.5rem;
    }

    /* 登录卡片样式 */
    div[data-testid="stForm"] {
        border: 1px solid #e0e6ed;
        border-radius: 12px;
        padding: 1.5rem;
        background-color: white;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }

    /* 聊天消息气泡优化 - AI */
    [data-testid="stChatMessage"] {
        padding: 1rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        border: 1px solid transparent;
    }
    [data-testid="stChatMessage"][data-testid="chatAvatarIcon-ai"] {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
    }
    
    /* 聊天输入框悬浮优化 */
    [data-testid="stChatInput"] {
        border-radius: 20px;
        border: 1px solid #cbd5e1;
    }

    /* 状态/工具输出框美化 */
    [data-testid="stExpander"] {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        background-color: #ffffff;
    }
    
    /* 按钮统一样式 */
    button[kind="secondary"] {
        border: 1px solid #cbd5e1;
        color: #475569;
    }
    button[kind="primary"] {
        background-color: #0f172a; /* 深色主题色 */
        border: none;
    }
</style>
"""

def _is_unauthorized(err: Exception) -> bool:
    return " 401 " in str(err) or str(err).startswith("401") or "401_UNAUTHORIZED" in str(err)

def _mirror_cookies(src: Any, dst: Any) -> None:
    try:
        dst.cookies.update(src.cookies)
    except Exception:
        pass

async def _ensure_auth_user(agent_client: AgentClient) -> dict[str, Any] | None:
    if AUTH_USER_KEY in st.session_state and st.session_state[AUTH_USER_KEY] is not None:
        return st.session_state[AUTH_USER_KEY]

    try:
        user = await agent_client.ame()
        st.session_state[AUTH_USER_KEY] = user
        _mirror_cookies(agent_client._aclient, agent_client._client)
        return user
    except AgentClientError as e:
        if not _is_unauthorized(e):
            raise

    try:
        user = await asyncio.to_thread(agent_client.me)
        st.session_state[AUTH_USER_KEY] = user
        _mirror_cookies(agent_client._client, agent_client._aclient)
        return user
    except AgentClientError as e:
        if _is_unauthorized(e):
            st.session_state[AUTH_USER_KEY] = None
            return None
        raise

def _get_user_id_from_me(user: dict[str, Any] | None) -> str:
    if not user:
        return str(uuid.uuid4())
    for k in ("sub", "user_id", "id", "uid"):
        v = user.get(k)
        if v:
            return str(v)
    return str(uuid.uuid4())

async def _do_login(agent_client: AgentClient, username: str, password: str) -> dict[str, Any]:
    await asyncio.to_thread(agent_client.login, username, password)
    _mirror_cookies(agent_client._client, agent_client._aclient)
    user = await _ensure_auth_user(agent_client)
    if not user:
        raise AgentClientError("Login succeeded but /auth/me still unauthorized")
    return user

async def _do_logout(agent_client: AgentClient) -> None:
    try:
        await asyncio.to_thread(agent_client.logout)
    except AgentClientError:
        pass
    try:
        agent_client._client.cookies.clear()
    except Exception:
        pass
    try:
        agent_client._aclient.cookies.clear()
    except Exception:
        pass
    st.session_state[AUTH_USER_KEY] = None

async def main() -> None:
    # 页面基础配置
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=APP_ICON,
        layout=PAGE_LAYOUT, # 使用宽屏
        menu_items={},
    )
    
    # 注入自定义 CSS
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # 隐藏 Streamlit 自带的状态小组件
    st.html(
        """
        <style>
        [data-testid="stStatusWidget"] {
                visibility: hidden;
                height: 0%;
                position: fixed;
            }
        </style>
        """,
    )
    if st.get_option("client.toolbarMode") != "minimal":
        st.set_option("client.toolbarMode", "minimal")
        await asyncio.sleep(0.1)
        st.rerun()

    # Create AgentClient once per session
    if AGENT_CLIENT_KEY not in st.session_state:
        load_dotenv()
        agent_url = os.getenv("AGENT_URL")
        if not agent_url:
            host = os.getenv("HOST", "0.0.0.0")
            port = os.getenv("PORT", 8080)
            agent_url = f"http://{host}:{port}"
        try:
            with st.spinner("Initializing system connection..."):
                st.session_state[AGENT_CLIENT_KEY] = AgentClient(base_url=agent_url)
        except AgentClientError as e:
            st.error(f"⚠️ Connection Error: {e}")
            st.warning("Ensure the backend service is running.")
            st.stop()

    agent_client: AgentClient = st.session_state[AGENT_CLIENT_KEY]

    try:
        auth_user = await _ensure_auth_user(agent_client)
    except AgentClientError as e:
        st.error(f"Auth check failed: {e}")
        st.stop()

    if "voice_manager" not in st.session_state:
        st.session_state.voice_manager = VoiceManager.from_env()
    voice = st.session_state.voice_manager

    # -------------------------
    # Sidebar UI (Redesigned)
    # -------------------------
    with st.sidebar:
        # 顶部 Logo 区域
        st.markdown(f"### {APP_ICON} **{APP_TITLE}**")
        st.caption("Powered by LangGraph & FastAPI")
        st.markdown("---")

        # Login Logic UI
        if auth_user:
            user_id_for_display = _get_user_id_from_me(auth_user)
            roles = auth_user.get("roles", [])
            
            with st.container(border=True):
                st.markdown(f"**👤 Current User**")
                st.code(f"{user_id_for_display}", language="text")
                if roles:
                    st.caption(f"Roles: {', '.join(map(str, roles))}")
                
                if st.button("Logout", icon="👋", use_container_width=True, type="secondary"):
                    await _do_logout(agent_client)
                    st.session_state.pop(MESSAGES_KEY, None)
                    st.session_state.pop(THREAD_ID_KEY, None)
                    st.session_state.pop("last_audio", None)
                    st.rerun()
        else:
            # 登录表单美化
            st.info("🔐 Access Required")
            st.write("Please sign in to access the agent tools.")
            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                st.markdown("<br>", unsafe_allow_html=True) # Spacer
                submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")

            if submitted:
                if not username or not password:
                    st.error("Missing credentials.")
                else:
                    try:
                        with st.spinner("Verifying credentials..."):
                            st.session_state[AUTH_USER_KEY] = await _do_login(
                                agent_client, username=username, password=password
                            )
                        st.toast("Welcome back!", icon="✅")
                        st.rerun()
                    except AgentClientError as e:
                        st.error(f"Login failed: {e}")

            st.stop()

        # After Login Controls
        st.markdown("### 💬 Chat Control")
        if st.button("Start New Conversation", icon="➕", use_container_width=True, type="primary"):
            st.session_state[MESSAGES_KEY] = []
            st.session_state[THREAD_ID_KEY] = str(uuid.uuid4())
            st.session_state.pop("last_audio", None)
            st.rerun()

        st.markdown("---")
        
        # Settings Section
        with st.expander("⚙️ Configuration", expanded=False):
            model_idx = agent_client.info.models.index(agent_client.info.default_model)
            model = st.selectbox("LLM Model", options=agent_client.info.models, index=model_idx)

            agent_list = [a.key for a in agent_client.info.agents]
            agent_idx = agent_list.index(agent_client.info.default_agent)
            agent_client.agent = st.selectbox("Agent Persona", options=agent_list, index=agent_idx)

            use_streaming = st.toggle("Enable Streaming", value=True)

            enable_audio = st.toggle(
                "Audio Response",
                value=True,
                disabled=not voice or not voice.tts,
                key="enable_audio",
            )
            
            me_user = st.session_state.get(AUTH_USER_KEY) or {}
            st.text_input("Session ID", value=_get_user_id_from_me(me_user), disabled=True)

        # Tools & Architecture
        col1, col2 = st.columns(2)
        with col1:
             if st.button("Map", icon="🗺️", use_container_width=True):
                architecture_dialog()
        with col2:
             if st.button("Share", icon="🔗", use_container_width=True):
                share_chat_dialog()

        st.markdown("---")
        with st.popover("Privacy Policy", use_container_width=True):
            st.caption("Data Usage Policy")
            st.write("All interactions are recorded anonymously for quality assurance and model evaluation.")

    # -------------------------
    # Helper Dialogs
    # -------------------------
    @st.dialog("System Architecture")
    def architecture_dialog() -> None:
        st.image("https://github.com/JoshuaC215/agent-service-toolkit/blob/main/media/agent_architecture.png?raw=true")
        st.caption("Hosted on Streamlit Cloud • FastAPI Backend • Azure/AWS")

    @st.dialog("Share Session")
    def share_chat_dialog() -> None:
        session = st.runtime.get_instance()._session_mgr.list_active_sessions()[0]
        st_base_url = urllib.parse.urlunparse(
            [session.client.request.protocol, session.client.request.host, "", "", "", ""]
        )
        if not st_base_url.startswith("https") and "localhost" not in st_base_url:
            st_base_url = st_base_url.replace("http", "https")
        chat_url = f"{st_base_url}?thread_id={st.session_state[THREAD_ID_KEY]}"
        
        st.success("Link generated successfully!")
        st.code(chat_url, language="text")
        st.info("🔒 Note: Authentication is required to view this history.")

    # -------------------------
    # Main Chat Area
    # -------------------------
    auth_user = st.session_state.get(AUTH_USER_KEY)
    user_id = _get_user_id_from_me(auth_user)

    if THREAD_ID_KEY not in st.session_state:
        thread_id = st.query_params.get("thread_id")
        if not thread_id:
            thread_id = str(uuid.uuid4())
            messages: list[ChatMessage] = []
        else:
            try:
                messages = agent_client.get_history(thread_id=thread_id).messages
            except AgentClientError as e:
                if _is_unauthorized(e):
                    st.session_state[AUTH_USER_KEY] = None
                    st.error("Session expired. Please log in again.")
                    st.rerun()
                st.error("No message history found for this Thread ID.")
                messages = []
        st.session_state[MESSAGES_KEY] = messages
        st.session_state[THREAD_ID_KEY] = thread_id

    messages: list[ChatMessage] = st.session_state[MESSAGES_KEY]

    # Welcome Splash Screen (Only when empty)
    if len(messages) == 0:
        st.markdown(f"""
        <div style="text-align: center; margin-top: 50px;">
            <h1>👋 Welcome to {APP_TITLE}</h1>
            <p style="color: grey; font-size: 1.1em;">
                Your AI-powered assistant for research, HR policies, and daily tasks.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Select prompt based on agent
        match agent_client.agent:
            case "chatbot": WELCOME = "I'm ready to chat! How can I help?"
            case "interrupt-agent": WELCOME = "I can predict your personality based on your birthday."
            case "research-assistant": WELCOME = "I have web access. What would you like to research?"
            case "rag-assistant": WELCOME = "Ask me about company policies, benefits, or HR topics."
            case _: WELCOME = "I'm an AI agent. Ask me anything!"
            
        with st.chat_message("ai", avatar="🤖"):
            st.write(WELCOME)
    
    # Message Loop
    async def amessage_iter() -> AsyncGenerator[ChatMessage, None]:
        for m in messages:
            yield m

    await draw_messages(amessage_iter())

    # Audio Playback
    enable_audio = st.session_state.get("enable_audio", True)
    if (
        voice
        and enable_audio
        and "last_audio" in st.session_state
        and st.session_state.get(LAST_MESSAGE_KEY)
        and len(messages) > 0
        and messages[-1].type == "ai"
    ):
        with st.session_state[LAST_MESSAGE_KEY]:
            audio_data = st.session_state.last_audio
            st.audio(audio_data["data"], format=audio_data["format"])

    # Input Area
    input_container = st.container()
    with input_container:
        if voice:
            user_input = voice.get_chat_input()
        else:
            user_input = st.chat_input("Type your message here...")

    if user_input:
        messages.append(ChatMessage(type="human", content=user_input))
        st.chat_message("human", avatar="👤").write(user_input)

        # Settings retrieval
        model = getattr(agent_client.info, "default_model", None)
        try:
            use_streaming = st.session_state.get("Enable Streaming", True)
        except Exception:
            use_streaming = True

        try:
            if use_streaming:
                stream = agent_client.astream(
                    message=user_input,
                    model=st.session_state.get("LLM Model", model) or model,
                    thread_id=st.session_state[THREAD_ID_KEY],
                    user_id=user_id,
                )
                await draw_messages(stream, is_new=True)

                if voice and enable_audio and st.session_state[MESSAGES_KEY]:
                    last_msg = st.session_state[MESSAGES_KEY][-1]
                    if last_msg.type == "ai" and last_msg.content:
                        voice.render_message(
                            last_msg.content,
                            container=st.session_state[LAST_MESSAGE_KEY],
                            audio_only=True,
                        )
            else:
                with st.spinner("Thinking..."):
                    response = await agent_client.ainvoke(
                        message=user_input,
                        model=st.session_state.get("LLM Model", model) or model,
                        thread_id=st.session_state[THREAD_ID_KEY],
                        user_id=user_id,
                    )
                messages.append(response)
                with st.chat_message("ai", avatar="🤖"):
                    if voice and enable_audio:
                        voice.render_message(response.content)
                    else:
                        st.write(response.content)

            st.rerun()
        except AgentClientError as e:
            if _is_unauthorized(e):
                st.session_state[AUTH_USER_KEY] = None
                st.error("Session expired. Please log in again.")
                st.rerun()
            st.error(f"Error generating response: {e}")
            st.stop()

    # Feedback
    if len(messages) > 0 and st.session_state.get(LAST_MESSAGE_KEY):
        with st.session_state[LAST_MESSAGE_KEY]:
            await handle_feedback()

async def draw_messages(
    messages_agen: AsyncGenerator[ChatMessage | str, None],
    is_new: bool = False,
) -> None:
    last_message_type = None
    st.session_state[LAST_MESSAGE_KEY] = None

    streaming_content = ""
    streaming_placeholder = None

    while msg := await anext(messages_agen, None):
        if isinstance(msg, str):
            if not streaming_placeholder:
                if last_message_type != "ai":
                    last_message_type = "ai"
                    st.session_state[LAST_MESSAGE_KEY] = st.chat_message("ai", avatar="🤖")
                with st.session_state[LAST_MESSAGE_KEY]:
                    streaming_placeholder = st.empty()

            streaming_content += msg
            streaming_placeholder.markdown(streaming_content + "▌") # Cursor effect
            continue

        match msg.type:
            case "human":
                last_message_type = "human"
                st.chat_message("human", avatar="👤").write(msg.content)

            case "ai":
                if is_new:
                    st.session_state[MESSAGES_KEY].append(msg)

                if last_message_type != "ai":
                    last_message_type = "ai"
                    st.session_state[LAST_MESSAGE_KEY] = st.chat_message("ai", avatar="🤖")

                with st.session_state[LAST_MESSAGE_KEY]:
                    if msg.content:
                        if streaming_placeholder:
                            streaming_placeholder.markdown(msg.content) # Finalize markdown
                            streaming_content = ""
                            streaming_placeholder = None
                        else:
                            st.write(msg.content)

                    if msg.tool_calls:
                        call_results = {}
                        for tool_call in msg.tool_calls:
                            if "transfer_to" in tool_call["name"]:
                                label = f"""🔄 Handoff: {tool_call["name"]}"""
                                state_icon = "running" if is_new else "complete"
                            else:
                                label = f"""🛠️ Tool: {tool_call["name"]}"""
                                state_icon = "running" if is_new else "complete"

                            # Use status consistent with theme
                            status = st.status(
                                label,
                                state=state_icon,
                            )
                            call_results[tool_call["id"]] = status

                        for tool_call in msg.tool_calls:
                            if "transfer_to" in tool_call["name"]:
                                status = call_results[tool_call["id"]]
                                status.update(expanded=True)
                                await handle_sub_agent_msgs(messages_agen, status, is_new)
                                break

                            status = call_results[tool_call["id"]]
                            status.markdown("**Input Parameters:**")
                            status.code(tool_call["args"], language="json") 
                            
                            tool_result: ChatMessage = await anext(messages_agen)

                            if is_new:
                                st.session_state[MESSAGES_KEY].append(tool_result)
                            if tool_result.tool_call_id:
                                status = call_results[tool_result.tool_call_id]
                            
                            status.markdown("**Result Output:**")
                            # Try to format JSON output nicely
                            try:
                                status.json(tool_result.content)
                            except:
                                status.write(tool_result.content)
                                
                            status.update(state="complete")

            case "custom":
                try:
                    task_data: TaskData = TaskData.model_validate(msg.custom_data)
                except ValidationError:
                    st.error("Data validation error")
                    st.stop()

                if is_new:
                    st.session_state[MESSAGES_KEY].append(msg)

                if last_message_type != "task":
                    last_message_type = "task"
                    st.session_state[LAST_MESSAGE_KEY] = st.chat_message(
                        name="task", avatar="📊"
                    )
                    with st.session_state[LAST_MESSAGE_KEY]:
                        status = TaskDataStatus()

                status.add_and_draw_task_data(task_data)

async def handle_feedback() -> None:
    if "last_feedback" not in st.session_state:
        st.session_state.last_feedback = (None, None)

    latest_run_id = st.session_state[MESSAGES_KEY][-1].run_id
    
    # 使用 container 使反馈区域更紧凑
    with st.container():
        cols = st.columns([0.8, 0.2])
        with cols[0]:
             st.caption("How was the response?")
        with cols[1]:
            feedback = st.feedback("thumbs", key=latest_run_id) # 改用 thumbs 更简洁

    if feedback is not None and (latest_run_id, feedback) != st.session_state.last_feedback:
        # Map thumbs (0/1) to score (0.0/1.0)
        normalized_score = 1.0 if feedback == 1 else 0.0
        agent_client: AgentClient = st.session_state[AGENT_CLIENT_KEY]
        try:
            await agent_client.acreate_feedback(
                run_id=latest_run_id,
                key="human-feedback-thumbs",
                score=normalized_score,
                kwargs={"comment": "Thumbs feedback"},
            )
        except AgentClientError:
           pass # Ignore feedback errors softly

        st.session_state.last_feedback = (latest_run_id, feedback)
        st.toast("Feedback received!", icon="🙏")

async def handle_sub_agent_msgs(messages_agen, status, is_new):
    nested_popovers = {}
    first_msg = await anext(messages_agen)
    if is_new:
        st.session_state[MESSAGES_KEY].append(first_msg)

    while True:
        sub_msg = await anext(messages_agen)
        if is_new:
            st.session_state[MESSAGES_KEY].append(sub_msg)

        if sub_msg.type == "tool" and sub_msg.tool_call_id in nested_popovers:
            popover = nested_popovers[sub_msg.tool_call_id]
            popover.markdown("**Output:**")
            try:
                popover.json(sub_msg.content)
            except:
                 popover.write(sub_msg.content)
            continue

        if (
            hasattr(sub_msg, "tool_calls")
            and sub_msg.tool_calls
            and any("transfer_back_to" in tc.get("name", "") for tc in sub_msg.tool_calls)
        ):
            # Handle return logic
            for tc in sub_msg.tool_calls:
                 if "transfer_back_to" in tc.get("name", ""):
                    transfer_result = await anext(messages_agen)
                    if is_new:
                        st.session_state[MESSAGES_KEY].append(transfer_result)
            if status:
                status.update(state="complete")
            break

        if status:
            if sub_msg.content:
                status.write(sub_msg.content)

            if hasattr(sub_msg, "tool_calls") and sub_msg.tool_calls:
                for tc in sub_msg.tool_calls:
                    if "transfer_to" in tc["name"]:
                        nested_status = status.status(
                            f"""🔄 Sub Agent: {tc["name"]}""",
                            state="running" if is_new else "complete",
                            expanded=True,
                        )
                        await handle_sub_agent_msgs(messages_agen, nested_status, is_new)
                    else:
                        popover = status.popover(f"{tc['name']}", icon="🔧")
                        popover.markdown(f"**Tool:** `{tc['name']}`")
                        popover.markdown("**Input:**")
                        popover.code(tc["args"], language="json")
                        nested_popovers[tc["id"]] = popover

if __name__ == "__main__":
    asyncio.run(main())