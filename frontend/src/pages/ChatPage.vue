```vue
<!-- ChatPage.vue -->
<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, reactive } from "vue";
import { useRoute, useRouter } from "vue-router";
import { apiFetch } from "@/api/http";
import { streamChat } from "@/api/sse";
import { useAuthStore } from "@/stores/auth";
import { marked } from "marked";

// 配置 marked 选项
marked.setOptions({
  breaks: false, // 使用标准 Markdown 规则（双换行符才是段落）
});

type KBDoc = {
  file_id: string;
  name: string;
  type: "pdf";
  dept_key: string;
  size_bytes?: number;
  updated_at?: string;
  can_view?: boolean;
  can_edit?: boolean;
};

type KBFilesResponse = {
  items: KBDoc[];
  next_cursor: number | null;
};




type ToolCall = { id: string; name: string; args: any };
type ChatMsg = {
  type: "human" | "ai" | "tool" | "custom";
  content: any;
  run_id?: string;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
  custom_data?: any;
};

type UiMessage = {
  id: string;
  role: "human" | "ai" | "tool" | "custom";
  content: string;
  runId?: string;
  toolCalls?: ToolCall[];
  toolResults?: Record<string, any>; // tool_call_id -> result
  _forceUpdate?: number; // 用于强制重新渲染
};

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

/** ===== Knowledge Sidebar State ===== */
const knowledge = ref<KBDoc[]>([]);
const docSearch = ref("");
const activeDoc = ref<KBDoc | null>(null);
const sidebarLoading = ref(false);
const showUploadMenu = ref(false);

// 系统管理员：拥有admin角色
const isAdmin = computed(() => auth.me?.roles?.includes("admin"));

// 部门管理员：用户所属的部门中至少有一个是editor角色且有写权限
const isDeptAdmin = computed(() => {
  const departments = auth.me?.departments || [];
  return departments.some((d: any) => d.dept_role === "editor" && d.can_write === 1);
});

// 可以编辑文件：系统管理员或部门管理员
const canEdit = computed(() => isAdmin.value || isDeptAdmin.value);

const avatarText = computed(() => (auth.displayId ? auth.displayId[0].toUpperCase() : "?"));

const filteredDocs = computed(() =>
  knowledge.value.filter((d) => d.name.toLowerCase().includes(docSearch.value.toLowerCase()))
);

/** ===== Resizable Sidebar ===== */
const sidebarWidth = ref<number>(280);
const resizing = ref(false);

const MIN_SIDEBAR = 220;
const MAX_SIDEBAR = 520;

function startResize(e: MouseEvent) {
  resizing.value = true;
  document.body.style.cursor = "col-resize";
  document.body.style.userSelect = "none";
  e.preventDefault();
}

function onResizeMove(e: MouseEvent) {
  if (!resizing.value) return;

  // sidebar 在 layout 左侧，鼠标 x 就是目标宽度
  const next = Math.min(MAX_SIDEBAR, Math.max(MIN_SIDEBAR, e.clientX));
  sidebarWidth.value = next;
}

function stopResize() {
  if (!resizing.value) return;
  resizing.value = false;
  document.body.style.cursor = "";
  document.body.style.userSelect = "";
}



const pdfUrl = computed(() => {
  if (!activeDoc.value) return "";
  return `/kb/files/${encodeURIComponent(activeDoc.value.file_id)}/download`;
});

function openPdf() {
  if (!pdfUrl.value) return;
  // 新窗口打开（最像“Edge 打开”）
  window.open(pdfUrl.value, "_blank");
}

function closeDoc() {
  activeDoc.value = null;
}

async function loadKnowledge() {
  sidebarLoading.value = true;
  try {
    const res = await apiFetch<any>("/kb/files");
    // 兼容两种情况：后端直接返回数组 或 返回 {items:[]}
    const items = Array.isArray(res) ? res : (res.items || []);
    knowledge.value = items;

    // 不自动选中第一个文档，重新进入时不显示文件预览
    // activeDoc.value = knowledge.value[0] || null;
    activeDoc.value = null;
  } finally {
    sidebarLoading.value = false;
  }
}


async function onUploadPdf(evt: Event) {
  const inputEl = evt.target as HTMLInputElement;
  const file = inputEl.files?.[0];
  if (!file) return;

  const fd = new FormData();
  fd.append("file", file);

  await apiFetch("/kb/files/upload", { method: "POST", body: fd });

  // 清空 input，避免同名文件再次选择不触发 change
  inputEl.value = "";
  showUploadMenu.value = false;

  await loadKnowledge();
}

function goPermission() {
  router.push("/permissions");
}

function goFiles() {
  router.push("/files");
}

function goApprovals() {
  router.push("/approvals");
}

/** ===== Chat State ===== */
const messages = ref<UiMessage[]>([]);
const input = ref("");
const loading = ref(false);

const threadId = ref<string>("");
const selectedModel = ref<string>("");
const selectedAgent = ref<string>(""); // 对应后端 agent_id
const availableModels = ref<string[]>([]);
const availableAgents = ref<{ key: string; name?: string; description?: string }[]>([]);

const chatBoxRef = ref<HTMLDivElement | null>(null);

function uuid() {
  // @ts-ignore
  if (crypto?.randomUUID) return crypto.randomUUID();
  return Math.random().toString(16).slice(2) + "-" + Date.now().toString(16);
}

const userId = computed(() => {
  // 优先使用 /auth/me 中可用的 id 字段；否则用本地持久化 uuid
  const me: any = auth.me || {};
  const id = me.sub || me.user_id || me.id || me.uid;
  if (id) return String(id);

  const key = "kb_user_id";
  const existing = localStorage.getItem(key);
  if (existing) return existing;

  const newId = uuid();
  localStorage.setItem(key, newId);
  return newId;
});

async function scrollToBottom() {
  await nextTick();
  if (chatBoxRef.value) {
    chatBoxRef.value.scrollTop = chatBoxRef.value.scrollHeight;
  }
}

function renderMarkdown(text: string): string {
  if (!text) return '';
  try {
    // 预处理文本: 清理过多的连续空行,但保留段落分隔
    // 将3个或更多连续换行符替换为2个换行符(标准段落分隔)
    const cleanedText = text.replace(/\n{3,}/g, '\n\n');
    return marked.parse(cleanedText) as string;
  } catch (e) {
    console.error('Markdown parsing error:', e);
    return text;
  }
}

function toUiMessage(m: ChatMsg): UiMessage {
  return {
    id: uuid(),
    role: m.type,
    content: typeof m.content === "string" ? m.content : JSON.stringify(m.content, null, 2),
    runId: m.run_id,
    toolCalls: m.tool_calls || undefined,
    toolResults: {},
  };
}

function attachToolResult(toolCallId: string, result: any) {
  // 从后往前找最近一个包含该 tool_call 的 ai 消息
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const msg = messages.value[i];
    if (msg.role !== "ai") continue;
    if (!msg.toolCalls || msg.toolCalls.length === 0) continue;
    const has = msg.toolCalls.some((tc) => tc.id === toolCallId);
    if (!has) continue;

    msg.toolResults = msg.toolResults || {};
    msg.toolResults[toolCallId] = result;
    return;
  }

  // 找不到就作为单独 tool 消息展示
  messages.value.push({
    id: uuid(),
    role: "tool",
    content: typeof result === "string" ? result : JSON.stringify(result, null, 2),
  });
}

async function loadInfo() {
  const info = await apiFetch<any>("/info");
  availableModels.value = info.models || [];
  availableAgents.value = (info.agents || []).map((a: any) => ({
    key: a.key,
    name: a.name,
    description: a.description,
  }));
  selectedModel.value = info.default_model || availableModels.value[0] || "";
  selectedAgent.value = info.default_agent || availableAgents.value[0]?.key || "";
}

async function ensureThreadId() {
  const q = route.query.thread_id;
  if (typeof q === "string" && q.trim()) {
    threadId.value = q.trim();
    return;
  }
  const tid = uuid();
  threadId.value = tid;
  // 把 thread_id 写回 URL，便于分享
  router.replace({ path: "/chat", query: { thread_id: tid } });
}

async function loadHistory() {
  // 你的后端 /history 是 POST
  const res = await apiFetch<{ messages: ChatMsg[] }>("/history", {
    method: "POST",
    body: JSON.stringify({ thread_id: threadId.value }),
  });

  const ui: UiMessage[] = [];
  for (const m of res.messages || []) {
    const u = toUiMessage(m);
    ui.push(u);

    // 历史里如果有 tool 消息，尝试挂到上一个 ai tool call 上
    if (m.type === "tool" && m.tool_call_id) {
      attachToolResult(m.tool_call_id, m.content);
    }
  }
  messages.value = ui;
  await scrollToBottom();
}

async function startNewConversation() {
  messages.value = [];
  const tid = uuid();
  threadId.value = tid;
  router.replace({ path: "/chat", query: { thread_id: tid } });
}

async function onLogout() {
  await auth.logout();
  router.replace("/login");
}

async function send() {
  const text = input.value.trim();
  if (!text || loading.value) return;

  loading.value = true;

  // 1) 先把用户消息放进 UI
  messages.value.push({
    id: uuid(),
    role: "human",
    content: text,
  });

  // 2) 放一个 AI 占位消息，用于 token 流式拼接
  const aiPlaceholder = reactive<UiMessage>({
    id: uuid(),
    role: "ai",
    content: "",
    toolCalls: [],
    toolResults: {},
    _forceUpdate: 0,
  });
  messages.value.push(aiPlaceholder);


  input.value = "";
  await scrollToBottom();

  // 3) 走 /stream（建议用 /{agent_id}/stream）
  const streamUrl =
    "/stream" + (selectedAgent.value ? `?agent_id=${encodeURIComponent(selectedAgent.value)}` : "");

  const payload = {
    message: text,
    thread_id: threadId.value,
    user_id: userId.value,
    model: selectedModel.value || undefined,
    stream_tokens: true,

    // 如果你后端支持把当前选中文档作为检索范围/上下文，可以打开：
    // kb_doc_id: activeDoc.value?.id,
  };

    try {
    await streamChat(streamUrl, payload, async (ev) => {
      if (ev.type === "token") {
        console.log("收到 token:", ev.content);
        aiPlaceholder.content += ev.content;
        // 强制触发响应式更新
        aiPlaceholder._forceUpdate = (aiPlaceholder._forceUpdate || 0) + 1;
        await nextTick();
        if (chatBoxRef.value) {
          chatBoxRef.value.scrollTop = chatBoxRef.value.scrollHeight;
        }
        return;
      }

      if (ev.type === "error") {
        aiPlaceholder.content += `\n\n[Error] ${ev.content}`;
        return;
      }

      if (ev.type === "message") {
        const m = ev.content as ChatMsg;

        if (m.type === "ai") {
          // 当使用 stream_tokens 时，完整的 message 事件会覆盖已累积的 token
          // 只有当 content 为空时才覆盖，保留 token 累积的内容
          if (typeof m.content === "string" && m.content.length > 0) {
            // 如果已经累积了 token 内容，就不要覆盖了
            if (!aiPlaceholder.content) {
              aiPlaceholder.content = m.content;
            }
          } else if (m.content) {
            if (!aiPlaceholder.content) {
              aiPlaceholder.content = JSON.stringify(m.content, null, 2);
            }
          }

          aiPlaceholder.runId = m.run_id;
          aiPlaceholder.toolCalls = m.tool_calls || [];
          aiPlaceholder.toolResults = aiPlaceholder.toolResults || {};
        }

        if (m.type === "tool" && m.tool_call_id) {
          attachToolResult(m.tool_call_id, m.content);
        }

        if (m.type === "custom") {
          messages.value.push({
            id: uuid(),
            role: "custom",
            content:
              typeof m.custom_data === "string"
                ? m.custom_data
                : JSON.stringify(m.custom_data ?? m.content, null, 2),
          });
        }
      }
    });

    scrollToBottom();
  } catch (e: any) {
    aiPlaceholder.content += `\n\n[Stream Failed] ${e?.message || String(e)}`;
  } finally {
    loading.value = false;
    scrollToBottom();
  }
}

onMounted(async () => {
  await auth.refreshMe();
  if (!auth.isAuthed) {
    router.replace("/login");
    return;
  }

  await loadKnowledge(); // ✅ 新增：加载知识库侧边栏

  await loadInfo();
  await ensureThreadId();
  await loadHistory();
  window.addEventListener("mousemove", onResizeMove);
  window.addEventListener("mouseup", stopResize);
});

onUnmounted(() => {
  window.removeEventListener("mousemove", onResizeMove);
  window.removeEventListener("mouseup", stopResize);
});

</script>

<template>
  <div class="layout">
    <!-- Sidebar -->
    <aside class="sidebar" :style="{ width: sidebarWidth + 'px' }">
      <header class="sidebar-header">知识库</header>

      <input v-model="docSearch" class="search" placeholder="搜索文档" />

      <div class="sidebar-resizer" @mousedown="startResize"></div>
      <div class="doc-list" v-if="!sidebarLoading">
        <div
          v-for="doc in filteredDocs"
          :key="doc.file_id"
          :class="['doc-item', { active: doc.file_id === activeDoc?.file_id }]"
          @click="activeDoc = doc"
        >
          <div class="title" :title="doc.name">{{ doc.name }}</div>
          <div class="meta">{{ doc.dept_key || "未分组" }}</div>
        </div>

        <div v-if="filteredDocs.length === 0" class="hint">没有匹配的文档</div>
      </div>
      <div v-else class="hint">加载中...</div>
    </aside>

    <!-- Main -->
    <section class="main">
      <!-- Topbar -->
      <header class="topbar">
        <div class="brand">KnowLedgeLib</div>

        <div class="actions">
          <!-- 只有系统管理员可以看到权限控制和审批列表 -->
          <button v-if="isAdmin" class="btn" @click="goPermission">权限控制</button>
          <!-- 系统管理员和部门管理员都可以看到文件管理 -->
          <button v-if="canEdit" class="btn" @click="goFiles">文件管理</button>
          <button v-if="isAdmin" class="btn" @click="goApprovals">审批列表</button>

          <div class="divider"></div>

          <label class="lbl">Agent</label>
          <select v-model="selectedAgent" class="select">
            <option v-for="a in availableAgents" :key="a.key" :value="a.key">
              {{ a.key }}
            </option>
          </select>

          <label class="lbl">Model</label>
          <select v-model="selectedModel" class="select">
            <option v-for="m in availableModels" :key="m" :value="m">
              {{ m }}
            </option>
          </select>

          <button class="btn" @click="startNewConversation">New</button>
          <button class="btn" @click="onLogout">Logout</button>

          <div class="avatar">{{ avatarText }}</div>
        </div>
      </header>

      <!-- Doc preview -->
      <div class="doc-preview" v-if="activeDoc">
          <div class="doc-title-row">
            <div>
              <div class="doc-title">{{ activeDoc.name }}</div>
            </div>
            <button class="close-btn" @click="closeDoc" title="关闭">×</button>
          </div>


         <div style="margin-top: 12px; height: 520px; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;">
           <iframe
             v-if="pdfUrl"
             :src="pdfUrl"
             style="width: 100%; height: 100%; border: 0;"
           />
         </div>
       </div>


      <!-- Thread Info -->
      <div class="thread-info">
        <span><b>thread_id:</b> {{ threadId }}</span>
        <span class="ml"><b>user_id:</b> {{ userId }}</span>
      </div>

      <!-- Chat List -->
      <div ref="chatBoxRef" class="chat-area">
        <div v-for="m in messages" :key="m.id" class="msg-wrap">
          <div
            class="msg"
            :class="{ human: m.role === 'human', other: m.role !== 'human' }"
            :style="{ marginLeft: m.role === 'human' ? 'auto' : '0' }"
          >
            <div class="msg-meta">
              {{ m.role.toUpperCase() }}
              <span v-if="m.runId" class="runid">run_id: {{ m.runId }}</span>
            </div>

            <div class="msg-content" v-if="m.role === 'human'">{{ m.content || '' }}</div>
            <div 
              class="msg-content markdown-content" 
              v-else
              :key="m._forceUpdate"
              v-html="renderMarkdown(m.content || '')"
            ></div>

            <!-- Tool calls -->
            <div v-if="m.role === 'ai' && m.toolCalls && m.toolCalls.length" class="toolcalls">
              <details v-for="tc in m.toolCalls" :key="tc.id" class="toolcall">
                <summary class="tool-summary">
                  🛠️ {{ tc.name }} <span class="tool-id">({{ tc.id }})</span>
                </summary>

                <div class="tool-h">Input</div>
                <pre class="tool-pre">{{
                  typeof tc.args === "string" ? tc.args : JSON.stringify(tc.args, null, 2)
                }}</pre>

                <div class="tool-h">Output</div>
                <pre class="tool-pre">{{
                  m.toolResults?.[tc.id]
                    ? typeof m.toolResults[tc.id] === "string"
                      ? m.toolResults[tc.id]
                      : JSON.stringify(m.toolResults[tc.id], null, 2)
                    : "(waiting...)"
                }}</pre>
              </details>
            </div>
          </div>
        </div>
      </div>

      <!-- Composer -->
      <div class="composer">
        <input
          v-model="input"
          @keydown.enter.exact.prevent="send"
          placeholder="搜索知识库并提问..."
          class="composer-input"
        />
        <button class="send" :disabled="loading" @click="send">
          {{ loading ? "发送中..." : "发送" }}
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  height: 100vh;
  background: #f6f7fb;
  color: #0f172a;
}

/* Sidebar */
.sidebar {
  border-right: 1px solid #e2e8f0;
  padding: 12px;
  background: #fff;
  display: flex;
  flex-direction: column;
  gap: 10px;

  position: relative;
  flex: 0 0 auto; /* 避免被 flex 自动挤压 */
}

.sidebar-resizer {
  position: absolute;
  right: -3px;
  top: 0;
  width: 6px;
  height: 100%;
  cursor: col-resize;
  background: transparent;
}
.sidebar-resizer:hover {
  background: rgba(15, 23, 42, 0.06);
}

.sidebar-header {
  font-weight: 700;
}
.search {
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid #d1d5db;
  outline: none;
}
.doc-list {
  flex: 1;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.doc-item {
  padding: 10px 10px;
  border: 1px solid transparent;
  border-radius: 10px;
  cursor: pointer;
  background: #fff;
}
.doc-item:hover {
  background: #f8fafc;
  border-color: #e5e7eb;
}
.doc-item.active {
  background: #eef2ff;
  border-color: #c7d2fe;
}
.title {
  font-weight: 600;
  font-size: 13px;

  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.meta {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;

  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hint {
  font-size: 12px;
  color: #64748b;
  padding: 8px 2px;
}

/* Main */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #e2e8f0;
  background: #fff;
}
.brand {
  font-weight: 800;
}
.actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.divider {
  width: 1px;
  height: 20px;
  background: #e5e7eb;
  margin: 0 2px;
}
.lbl {
  font-size: 12px;
  color: #6b7280;
}
.select {
  padding: 6px 8px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  background: white;
}
.btn {
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid #d1d5db;
  background: white;
  cursor: pointer;
}
.btn:hover {
  background: #f8fafc;
}
.avatar {
  width: 34px;
  height: 34px;
  border-radius: 999px;
  background: #111827;
  color: #fff;
  display: grid;
  place-items: center;
  font-weight: 700;
}

.upload {
  position: relative;
}
.upload .menu {
  position: absolute;
  right: 0;
  top: 42px;
  padding: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 6px 20px rgba(15, 23, 42, 0.08);
  z-index: 10;
}
.upload-label {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  font-size: 12px;
  color: #0f172a;
  cursor: pointer;
}
.upload-label input {
  display: none;
}

.doc-preview {
  padding: 12px 16px;
  border-bottom: 1px solid #e2e8f0;
  background: #fff;
}
.doc-title {
  font-weight: 700;
}
.doc-path {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}

.doc-title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.close-btn {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px solid #d1d5db;
  background: #fff;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}

.close-btn:hover {
  background: #f3f4f6;
  border-color: #9ca3af;
}

.doc-summary {
  margin-top: 8px;
  font-size: 13px;
  color: #0f172a;
}

.thread-info {
  padding: 8px 16px;
  font-size: 12px;
  color: #6b7280;
  border-bottom: 1px solid #f1f5f9;
  background: #fff;
}
.ml {
  margin-left: 12px;
}

/* Chat */
.chat-area {
  flex: 1;
  overflow: auto;
  padding: 16px;
  background: #f8fafc;
  min-width: 0;
}
.msg-wrap {
  margin-bottom: 12px;
}
.msg {
  max-width: 900px;
  border-radius: 12px;
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  word-break: break-word;
}
.msg.human {
  background: #111827;
  color: white;
  border-color: #111827;
}
.msg.other {
  background: #ffffff;
  color: #111827;
}
.msg-meta {
  font-size: 12px;
  opacity: 0.75;
  margin-bottom: 6px;
}
.runid {
  margin-left: 8px;
}
.msg-content {
  font-size: 14px;
}

/* Markdown 样式 */
.markdown-content {
  line-height: 1.6;
  white-space: normal;
}

.markdown-content h1,
.markdown-content h2,
.markdown-content h3,
.markdown-content h4,
.markdown-content h5,
.markdown-content h6 {
  margin-top: 16px;
  margin-bottom: 8px;
  font-weight: 600;
  line-height: 1.25;
}

.markdown-content h1 {
  font-size: 1.5em;
}

.markdown-content h2 {
  font-size: 1.25em;
}

.markdown-content h3 {
  font-size: 1.1em;
}

.markdown-content p {
  margin-bottom: 8px;
}

.markdown-content code {
  padding: 2px 6px;
  background: rgba(0, 0, 0, 0.06);
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 0.9em;
}

.markdown-content pre {
  background: rgba(0, 0, 0, 0.04);
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin-bottom: 12px;
}

.markdown-content pre code {
  background: transparent;
  padding: 0;
  border-radius: 0;
  font-size: 0.9em;
}

.markdown-content ul,
.markdown-content ol {
  margin-bottom: 12px;
  padding-left: 24px;
}

.markdown-content li {
  margin-bottom: 4px;
}

.markdown-content blockquote {
  border-left: 4px solid #6366f1;
  padding-left: 12px;
  margin-left: 0;
  margin-bottom: 12px;
  color: #64748b;
}

.markdown-content a {
  color: #6366f1;
  text-decoration: underline;
}

.markdown-content a:hover {
  color: #4f46e5;
}

.markdown-content table {
  border-collapse: collapse;
  width: 100%;
  margin-bottom: 12px;
}

.markdown-content th,
.markdown-content td {
  border: 1px solid #e5e7eb;
  padding: 8px 12px;
  text-align: left;
}

.markdown-content th {
  background: rgba(0, 0, 0, 0.04);
  font-weight: 600;
}

.markdown-content hr {
  border: none;
  border-top: 2px solid #e5e7eb;
  margin: 16px 0;
}

.markdown-content strong {
  font-weight: 700;
}

.markdown-content em {
  font-style: italic;
}

/* Tools */
.toolcalls {
  margin-top: 10px;
}
.toolcall {
  margin-top: 8px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 8px;
  background: #f8fafc;
}
.tool-summary {
  cursor: pointer;
}
.tool-id {
  opacity: 0.7;
}
.tool-h {
  margin-top: 8px;
  font-size: 12px;
  opacity: 0.8;
}
.tool-pre {
  margin: 6px 0;
  padding: 10px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  overflow: auto;
}

/* Composer */
.composer {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  border-top: 1px solid #e2e8f0;
  background: #fff;
}
.composer-input {
  flex: 1;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid #d1d5db;
  outline: none;
}
.send {
  padding: 10px 14px;
  border-radius: 12px;
  border: none;
  background: #111827;
  color: white;
  cursor: pointer;
}
.send:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
```
