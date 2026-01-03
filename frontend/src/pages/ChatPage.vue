<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { apiFetch } from "@/api/http";
import { streamChat } from "@/api/sse";
import { useAuthStore } from "@/stores/auth";

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
};

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

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

function toUiMessage(m: ChatMsg): UiMessage {
  const base: UiMessage = {
    id: uuid(),
    role: m.type,
    content: typeof m.content === "string" ? m.content : JSON.stringify(m.content, null, 2),
    runId: m.run_id,
    toolCalls: m.tool_calls || undefined,
    toolResults: {},
  };
  return base;
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
  const aiPlaceholder: UiMessage = {
    id: uuid(),
    role: "ai",
    content: "",
    toolCalls: [],
    toolResults: {},
  };
  messages.value.push(aiPlaceholder);
  input.value = "";
  await scrollToBottom();

  // 3) 走 /stream（建议用 /{agent_id}/stream）
  const streamUrl =
  "/stream" +
  (selectedAgent.value ? `?agent_id=${encodeURIComponent(selectedAgent.value)}` : "");

  const payload = {
    message: text,
    thread_id: threadId.value,
    user_id: userId.value,
    model: selectedModel.value || undefined,
    stream_tokens: true,
  };

  try {
    await streamChat(streamUrl, payload, (ev) => {
      if (ev.type === "token") {
        aiPlaceholder.content += ev.content;
        // 不要每个 token 都 scroll（会卡），简单做节流：只有内容增长时偶尔滚动
        return;
      }

      if (ev.type === "error") {
        aiPlaceholder.content += `\n\n[Error] ${ev.content}`;
        return;
      }

      if (ev.type === "message") {
        const m = ev.content as ChatMsg;

        if (m.type === "ai") {
          // 最终 ai 消息会包含完整 content / tool_calls / run_id
          if (typeof m.content === "string" && m.content.length > 0) {
            aiPlaceholder.content = m.content;
          } else if (m.content) {
            aiPlaceholder.content = JSON.stringify(m.content, null, 2);
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

  await loadInfo();
  await ensureThreadId();
  await loadHistory();
});
</script>

<template>
  <div style="height: 100vh; display: flex; flex-direction: column; font-family: system-ui;">
    <!-- Top Bar -->
    <div
      style="display:flex; align-items:center; gap:12px; padding:12px 16px; border-bottom:1px solid #e5e7eb;"
    >
      <div style="font-weight: 700;">KnowledgeLib Chat</div>

      <div style="margin-left:auto; display:flex; gap:10px; align-items:center;">
        <label style="font-size:12px; color:#6b7280;">Agent</label>
        <select v-model="selectedAgent" style="padding:6px 8px; border:1px solid #d1d5db; border-radius:8px;">
          <option v-for="a in availableAgents" :key="a.key" :value="a.key">
            {{ a.key }}
          </option>
        </select>

        <label style="font-size:12px; color:#6b7280;">Model</label>
        <select v-model="selectedModel" style="padding:6px 8px; border:1px solid #d1d5db; border-radius:8px;">
          <option v-for="m in availableModels" :key="m" :value="m">
            {{ m }}
          </option>
        </select>

        <button
          @click="startNewConversation"
          style="padding:8px 10px; border-radius:10px; border:1px solid #d1d5db; background:white; cursor:pointer;"
        >
          New
        </button>

        <button
          @click="onLogout"
          style="padding:8px 10px; border-radius:10px; border:1px solid #d1d5db; background:white; cursor:pointer;"
        >
          Logout
        </button>
      </div>
    </div>

    <!-- Thread Info -->
    <div style="padding: 8px 16px; font-size: 12px; color:#6b7280; border-bottom:1px solid #f1f5f9;">
      <span><b>thread_id:</b> {{ threadId }}</span>
      <span style="margin-left:12px;"><b>user_id:</b> {{ userId }}</span>
    </div>

    <!-- Chat List -->
    <div ref="chatBoxRef" style="flex:1; overflow:auto; padding:16px; background:#fafafa;">
      <div v-for="m in messages" :key="m.id" style="margin-bottom: 12px;">
        <div
          :style="{
            maxWidth: '900px',
            marginLeft: m.role === 'human' ? 'auto' : '0',
            background: m.role === 'human' ? '#111827' : '#ffffff',
            color: m.role === 'human' ? 'white' : '#111827',
            border: '1px solid ' + (m.role === 'human' ? '#111827' : '#e5e7eb'),
            borderRadius: '12px',
            padding: '10px 12px',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }"
        >
          <div style="font-size:12px; opacity:0.75; margin-bottom:6px;">
            {{ m.role.toUpperCase() }}
            <span v-if="m.runId" style="margin-left:8px;">run_id: {{ m.runId }}</span>
          </div>

          <div>{{ m.content || (m.role === 'ai' && loading ? '...' : '') }}</div>

          <!-- Tool calls -->
          <div v-if="m.role === 'ai' && m.toolCalls && m.toolCalls.length" style="margin-top: 10px;">
            <details
              v-for="tc in m.toolCalls"
              :key="tc.id"
              style="margin-top:8px; border:1px solid #e5e7eb; border-radius:10px; padding:8px; background:#f8fafc;"
            >
              <summary style="cursor:pointer;">
                🛠️ {{ tc.name }} <span style="opacity:0.7;">({{ tc.id }})</span>
              </summary>

              <div style="margin-top:8px; font-size:12px; opacity:0.8;">Input</div>
              <pre style="margin:6px 0; padding:10px; background:#fff; border:1px solid #e5e7eb; border-radius:10px; overflow:auto;">
{{ typeof tc.args === 'string' ? tc.args : JSON.stringify(tc.args, null, 2) }}
              </pre>

              <div style="margin-top:8px; font-size:12px; opacity:0.8;">Output</div>
              <pre style="margin:6px 0; padding:10px; background:#fff; border:1px solid #e5e7eb; border-radius:10px; overflow:auto;">
{{ m.toolResults?.[tc.id] ? (typeof m.toolResults[tc.id] === 'string' ? m.toolResults[tc.id] : JSON.stringify(m.toolResults[tc.id], null, 2)) : '(waiting...)' }}
              </pre>
            </details>
          </div>
        </div>
      </div>
    </div>

    <!-- Input -->
    <div style="padding: 12px 16px; border-top: 1px solid #e5e7eb; display:flex; gap:10px;">
      <input
        v-model="input"
        @keydown.enter.exact.prevent="send"
        placeholder="Type your message..."
        style="flex:1; padding:10px 12px; border-radius:12px; border:1px solid #d1d5db;"
      />
      <button
        @click="send"
        :disabled="loading"
        style="padding:10px 14px; border-radius:12px; border:none; background:#111827; color:white; cursor:pointer;"
      >
        {{ loading ? "Sending..." : "Send" }}
      </button>
    </div>
  </div>
</template>
