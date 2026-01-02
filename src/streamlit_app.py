# streamlit_app.py
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

from client import AgentClient, AgentClientError
from schema import ChatHistory, ChatMessage
from schema.task_data import TaskData, TaskDataStatus
from voice import VoiceManager

APP_TITLE = "Agent Service Toolkit"
APP_ICON = "🧰"

# Session-state keys
AUTH_USER_KEY = "auth_user"          # dict returned by /auth/me (or None)
AGENT_CLIENT_KEY = "agent_client"
THREAD_ID_KEY = "thread_id"
MESSAGES_KEY = "messages"
LAST_MESSAGE_KEY = "last_message"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

def _is_unauthorized(err: Exception) -> bool:
    # AgentClientError messages look like: "Me failed: 401 {...}"
    return " 401 " in str(err) or str(err).startswith("401") or "401_UNAUTHORIZED" in str(err)


def _mirror_cookies(src: Any, dst: Any) -> None:
    """
    Copy cookie jar from one httpx client to the other.
    Works for httpx.Client and httpx.AsyncClient.
    """
    try:
        dst.cookies.update(src.cookies)
    except Exception:
        # Best-effort; if it fails, login will still work for the client that owns cookies.
        pass


async def _ensure_auth_user(agent_client: AgentClient) -> dict[str, Any] | None:
    """
    Try to resolve current login from either async or sync client.
    Keep st.session_state[AUTH_USER_KEY] updated.
    Mirror cookies between httpx clients when possible.
    """
    if AUTH_USER_KEY in st.session_state and st.session_state[AUTH_USER_KEY] is not None:
        return st.session_state[AUTH_USER_KEY]

    # Try async first (because we use async for invoke/stream)
    try:
        user = await agent_client.ame()
        st.session_state[AUTH_USER_KEY] = user
        # mirror cookies async -> sync (history uses sync)
        _mirror_cookies(agent_client._aclient, agent_client._client)  # noqa: SLF001
        return user
    except AgentClientError as e:
        if not _is_unauthorized(e):
            # unexpected error (network/500)
            raise

    # Try sync (in case cookie jar only exists there)
    try:
        user = await asyncio.to_thread(agent_client.me)
        st.session_state[AUTH_USER_KEY] = user
        # mirror cookies sync -> async
        _mirror_cookies(agent_client._client, agent_client._aclient)  # noqa: SLF001
        return user
    except AgentClientError as e:
        if _is_unauthorized(e):
            st.session_state[AUTH_USER_KEY] = None
            return None
        raise


def _get_user_id_from_me(user: dict[str, Any] | None) -> str:
    """
    Use JWT identity as user_id for agent config.
    The exact key depends on your get_current_user implementation; we defensively check several.
    """
    if not user:
        return str(uuid.uuid4())
    for k in ("sub", "user_id", "id", "uid"):
        v = user.get(k)
        if v:
            return str(v)
    return str(uuid.uuid4())


async def _do_login(agent_client: AgentClient, username: str, password: str) -> dict[str, Any]:
    """
    Login once via sync client (in a thread), then mirror cookies to async client.
    Finally call /auth/me to fetch identity.
    """
    await asyncio.to_thread(agent_client.login, username, password)
    _mirror_cookies(agent_client._client, agent_client._aclient)  # noqa: SLF001
    user = await _ensure_auth_user(agent_client)
    if not user:
        raise AgentClientError("Login succeeded but /auth/me still unauthorized")
    return user


async def _do_logout(agent_client: AgentClient) -> None:
    """
    Logout via sync client (thread), then clear both cookie jars.
    """
    try:
        await asyncio.to_thread(agent_client.logout)
    except AgentClientError:
        # If token already expired, treat as logged out anyway
        pass
    try:
        agent_client._client.cookies.clear()   # noqa: SLF001
    except Exception:
        pass
    try:
        agent_client._aclient.cookies.clear()  # noqa: SLF001
    except Exception:
        pass
    st.session_state[AUTH_USER_KEY] = None


async def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=APP_ICON,
        menu_items={},
    )

    # Hide the streamlit upper-right chrome
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
            with st.spinner("Connecting to agent service..."):
                st.session_state[AGENT_CLIENT_KEY] = AgentClient(base_url=agent_url)
        except AgentClientError as e:
            st.error(f"Error connecting to agent service at {agent_url}: {e}")
            st.markdown("The service might be booting up. Try again in a few seconds.")
            st.stop()

    agent_client: AgentClient = st.session_state[AGENT_CLIENT_KEY]

    # Resolve auth status (JWT cookie) if possible
    try:
        auth_user = await _ensure_auth_user(agent_client)
    except AgentClientError as e:
        st.error(f"Auth check failed: {e}")
        st.stop()

    # Initialize voice manager (once per session)
    if "voice_manager" not in st.session_state:
        st.session_state.voice_manager = VoiceManager.from_env()
    voice = st.session_state.voice_manager

    # -------------------------
    # Sidebar UI (login-first)
    # -------------------------
    with st.sidebar:
        st.header(f"{APP_ICON} {APP_TITLE}")
        st.caption("AI agent UI (FastAPI + LangGraph + Streamlit)")

        # Login block
        if auth_user:
            user_id_for_display = _get_user_id_from_me(auth_user)
            roles = auth_user.get("roles", [])
            st.success(f"Logged in: `{user_id_for_display}`")
            if roles:
                st.caption(f"Roles: {', '.join(map(str, roles))}")

            if st.button(":material/logout: Logout", use_container_width=True):
                await _do_logout(agent_client)
                # Reset chat UI state on logout
                st.session_state.pop(MESSAGES_KEY, None)
                st.session_state.pop(THREAD_ID_KEY, None)
                st.session_state.pop("last_audio", None)
                st.rerun()
        else:
            st.warning("Please log in to continue.")
            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("Username", placeholder="e.g. ryan / viewer")
                password = st.text_input("Password", type="password", placeholder="Password")
                submitted = st.form_submit_button("Log in", use_container_width=True)

            if submitted:
                if not username or not password:
                    st.error("Please enter username and password.")
                else:
                    try:
                        with st.spinner("Logging in..."):
                            st.session_state[AUTH_USER_KEY] = await _do_login(
                                agent_client, username=username, password=password
                            )
                        st.toast("Logged in", icon="✅")
                        st.rerun()
                    except AgentClientError as e:
                        st.error(f"Login failed: {e}")

            st.info("You must log in (JWT cookie) to use /invoke, /stream, /history, /feedback.")
            st.stop()

        # After this point, user is logged in

        if st.button(":material/chat: New Chat", use_container_width=True):
            st.session_state[MESSAGES_KEY] = []
            st.session_state[THREAD_ID_KEY] = str(uuid.uuid4())
            st.session_state.pop("last_audio", None)
            st.rerun()

        with st.popover(":material/settings: Settings", use_container_width=True):
            model_idx = agent_client.info.models.index(agent_client.info.default_model)
            model = st.selectbox("LLM to use", options=agent_client.info.models, index=model_idx)

            agent_list = [a.key for a in agent_client.info.agents]
            agent_idx = agent_list.index(agent_client.info.default_agent)
            agent_client.agent = st.selectbox("Agent to use", options=agent_list, index=agent_idx)

            use_streaming = st.toggle("Stream results", value=True)

            enable_audio = st.toggle(
                "Enable audio generation",
                value=True,
                disabled=not voice or not voice.tts,
                help="Configure VOICE_TTS_PROVIDER in .env to enable"
                if not voice or not voice.tts
                else None,
                on_change=lambda: st.session_state.pop("last_audio", None)
                if not st.session_state.get("enable_audio", True)
                else None,
                key="enable_audio",
            )

            # Show authenticated identity (from /auth/me)
            me_user = st.session_state.get(AUTH_USER_KEY) or {}
            st.text_input(
                "Authenticated user_id (read-only)",
                value=_get_user_id_from_me(me_user),
                disabled=True,
            )

        @st.dialog("Architecture")
        def architecture_dialog() -> None:
            st.image(
                "https://github.com/JoshuaC215/agent-service-toolkit/blob/main/media/agent_architecture.png?raw=true"
            )
            "[View full size on Github](https://github.com/JoshuaC215/agent-service-toolkit/blob/main/media/agent_architecture.png)"
            st.caption(
                "App hosted on Streamlit Cloud with FastAPI service running in Azure (example)."
            )

        if st.button(":material/schema: Architecture", use_container_width=True):
            architecture_dialog()

        with st.popover(":material/policy: Privacy", use_container_width=True):
            st.write(
                "Prompts, responses and feedback in this app are anonymously recorded and saved for product evaluation."
            )

        @st.dialog("Share/resume chat")
        def share_chat_dialog() -> None:
            session = st.runtime.get_instance()._session_mgr.list_active_sessions()[0]
            st_base_url = urllib.parse.urlunparse(
                [session.client.request.protocol, session.client.request.host, "", "", "", ""]
            )
            # if it's not localhost, switch to https by default
            if not st_base_url.startswith("https") and "localhost" not in st_base_url:
                st_base_url = st_base_url.replace("http", "https")

            # Auth is cookie-based, so recipients still need credentials to view history.
            chat_url = f"{st_base_url}?thread_id={st.session_state[THREAD_ID_KEY]}"
            st.markdown(f"**Chat URL:**\n```text\n{chat_url}\n```")
            st.info("Note: the viewer must log in to access protected endpoints.")

        if st.button(":material/upload: Share/resume chat", use_container_width=True):
            share_chat_dialog()

        "[View the source code](https://github.com/JoshuaC215/agent-service-toolkit)"
        st.caption("Made with :material/favorite: in Streamlit")

    # -------------------------
    # Main chat logic (requires auth)
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
                messages = agent_client.get_history(thread_id=thread_id).messages  # protected
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

    # Welcome (only when no messages)
    if len(messages) == 0:
        match agent_client.agent:
            case "chatbot":
                WELCOME = "Hello! I'm a simple chatbot. Ask me anything!"
            case "interrupt-agent":
                WELCOME = "Hello! I'm an interrupt agent. Tell me your birthday and I will predict your personality!"
            case "research-assistant":
                WELCOME = "Hello! I'm an AI-powered research assistant with web search and a calculator. Ask me anything!"
            case "rag-assistant":
                WELCOME = """Hello! I'm an AI-powered Company Policy & HR assistant.
I can help you find information about benefits, remote work, time-off policies, company values, and more. Ask me anything!"""
            case _:
                WELCOME = "Hello! I'm an AI agent. Ask me anything!"

        with st.chat_message("ai"):
            st.write(WELCOME)

    # draw_messages() expects an async iterator over messages
    async def amessage_iter() -> AsyncGenerator[ChatMessage, None]:
        for m in messages:
            yield m

    await draw_messages(amessage_iter())

    # Render saved audio for the last AI message (if it exists)
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

    # user input
    if voice:
        user_input = voice.get_chat_input()
    else:
        user_input = st.chat_input()

    if user_input:
        messages.append(ChatMessage(type="human", content=user_input))
        st.chat_message("human").write(user_input)

        # read settings values (they exist because user is logged in)
        # If settings popover never opened, fall back to defaults
        model = getattr(agent_client.info, "default_model", None)
        use_streaming = True  # default
        # Try to read from widget state if created; otherwise default is fine
        # (Streamlit doesn't expose a reliable way to check whether popover ran)
        try:
            use_streaming = st.session_state.get("Stream results", True)  # may not exist
        except Exception:
            pass

        try:
            if use_streaming:
                stream = agent_client.astream(
                    message=user_input,
                    model=st.session_state.get("model", model) or model,
                    thread_id=st.session_state[THREAD_ID_KEY],
                    user_id=user_id,
                )
                await draw_messages(stream, is_new=True)

                # TTS after streaming
                if voice and enable_audio and st.session_state[MESSAGES_KEY]:
                    last_msg = st.session_state[MESSAGES_KEY][-1]
                    if last_msg.type == "ai" and last_msg.content:
                        voice.render_message(
                            last_msg.content,
                            container=st.session_state[LAST_MESSAGE_KEY],
                            audio_only=True,
                        )
            else:
                response = await agent_client.ainvoke(
                    message=user_input,
                    model=st.session_state.get("model", model) or model,
                    thread_id=st.session_state[THREAD_ID_KEY],
                    user_id=user_id,
                )
                messages.append(response)
                with st.chat_message("ai"):
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

    # feedback (protected)
    if len(messages) > 0 and st.session_state.get(LAST_MESSAGE_KEY):
        with st.session_state[LAST_MESSAGE_KEY]:
            await handle_feedback()


async def draw_messages(
    messages_agen: AsyncGenerator[ChatMessage | str, None],
    is_new: bool = False,
) -> None:
    # Keep track of the last message container
    last_message_type = None
    st.session_state[LAST_MESSAGE_KEY] = None

    # Placeholder for intermediate streaming tokens
    streaming_content = ""
    streaming_placeholder = None

    while msg := await anext(messages_agen, None):
        if isinstance(msg, str):
            if not streaming_placeholder:
                if last_message_type != "ai":
                    last_message_type = "ai"
                    st.session_state[LAST_MESSAGE_KEY] = st.chat_message("ai")
                with st.session_state[LAST_MESSAGE_KEY]:
                    streaming_placeholder = st.empty()

            streaming_content += msg
            streaming_placeholder.write(streaming_content)
            continue

        if not isinstance(msg, ChatMessage):
            st.error(f"Unexpected message type: {type(msg)}")
            st.write(msg)
            st.stop()

        match msg.type:
            case "human":
                last_message_type = "human"
                st.chat_message("human").write(msg.content)

            case "ai":
                if is_new:
                    st.session_state[MESSAGES_KEY].append(msg)

                if last_message_type != "ai":
                    last_message_type = "ai"
                    st.session_state[LAST_MESSAGE_KEY] = st.chat_message("ai")

                with st.session_state[LAST_MESSAGE_KEY]:
                    if msg.content:
                        if streaming_placeholder:
                            streaming_placeholder.write(msg.content)
                            streaming_content = ""
                            streaming_placeholder = None
                        else:
                            st.write(msg.content)

                    if msg.tool_calls:
                        call_results = {}
                        for tool_call in msg.tool_calls:
                            if "transfer_to" in tool_call["name"]:
                                label = f"""💼 Sub Agent: {tool_call["name"]}"""
                            else:
                                label = f"""🛠️ Tool Call: {tool_call["name"]}"""

                            status = st.status(
                                label,
                                state="running" if is_new else "complete",
                            )
                            call_results[tool_call["id"]] = status

                        for tool_call in msg.tool_calls:
                            if "transfer_to" in tool_call["name"]:
                                status = call_results[tool_call["id"]]
                                status.update(expanded=True)
                                await handle_sub_agent_msgs(messages_agen, status, is_new)
                                break

                            status = call_results[tool_call["id"]]
                            status.write("Input:")
                            status.write(tool_call["args"])
                            tool_result: ChatMessage = await anext(messages_agen)

                            if tool_result.type != "tool":
                                st.error(f"Unexpected ChatMessage type: {tool_result.type}")
                                st.write(tool_result)
                                st.stop()

                            if is_new:
                                st.session_state[MESSAGES_KEY].append(tool_result)
                            if tool_result.tool_call_id:
                                status = call_results[tool_result.tool_call_id]
                            status.write("Output:")
                            status.write(tool_result.content)
                            status.update(state="complete")

            case "custom":
                try:
                    task_data: TaskData = TaskData.model_validate(msg.custom_data)
                except ValidationError:
                    st.error("Unexpected CustomData message received from agent")
                    st.write(msg.custom_data)
                    st.stop()

                if is_new:
                    st.session_state[MESSAGES_KEY].append(msg)

                if last_message_type != "task":
                    last_message_type = "task"
                    st.session_state[LAST_MESSAGE_KEY] = st.chat_message(
                        name="task", avatar=":material/manufacturing:"
                    )
                    with st.session_state[LAST_MESSAGE_KEY]:
                        status = TaskDataStatus()

                status.add_and_draw_task_data(task_data)

            case _:
                st.error(f"Unexpected ChatMessage type: {msg.type}")
                st.write(msg)
                st.stop()


async def handle_feedback() -> None:
    if "last_feedback" not in st.session_state:
        st.session_state.last_feedback = (None, None)

    latest_run_id = st.session_state[MESSAGES_KEY][-1].run_id
    feedback = st.feedback("stars", key=latest_run_id)

    if feedback is not None and (latest_run_id, feedback) != st.session_state.last_feedback:
        normalized_score = (feedback + 1) / 5.0
        agent_client: AgentClient = st.session_state[AGENT_CLIENT_KEY]
        try:
            await agent_client.acreate_feedback(
                run_id=latest_run_id,
                key="human-feedback-stars",
                score=normalized_score,
                kwargs={"comment": "In-line human feedback"},
            )
        except AgentClientError as e:
            if _is_unauthorized(e):
                st.session_state[AUTH_USER_KEY] = None
                st.error("Session expired. Please log in again.")
                st.rerun()
            st.error(f"Error recording feedback: {e}")
            st.stop()

        st.session_state.last_feedback = (latest_run_id, feedback)
        st.toast("Feedback recorded", icon=":material/reviews:")


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
            popover.write("**Output:**")
            popover.write(sub_msg.content)
            continue

        if (
            hasattr(sub_msg, "tool_calls")
            and sub_msg.tool_calls
            and any("transfer_back_to" in tc.get("name", "") for tc in sub_msg.tool_calls)
        ):
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
                            f"""💼 Sub Agent: {tc["name"]}""",
                            state="running" if is_new else "complete",
                            expanded=True,
                        )
                        await handle_sub_agent_msgs(messages_agen, nested_status, is_new)
                    else:
                        popover = status.popover(f"{tc['name']}", icon="🛠️")
                        popover.write(f"**Tool:** {tc['name']}")
                        popover.write("**Input:**")
                        popover.write(tc["args"])
                        nested_popovers[tc["id"]] = popover


if __name__ == "__main__":
    asyncio.run(main())
