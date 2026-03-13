<template>
  <div class="chat-view">
    <aside class="session-list-wrap">
      <div class="session-list-header">
        <span>会话</span>
        <div class="session-header-actions">
          <n-button quaternary type="primary" size="small" @click="onNewSession">新建</n-button>
          <n-button quaternary size="small" type="error" @click="onClearAll">清空</n-button>
        </div>
      </div>
      <n-scrollbar class="session-scroll">
        <n-list hoverable clickable>
          <n-list-item
            v-for="s in chatStore.sessionList"
            :key="s.id"
            :class="{ active: s.id === chatStore.currentSessionId }"
            @click="onSelectSession(s.id)"
          >
            <n-thing>
              <template #header>{{ s.title || "新会话" }}</template>
              <template #header-extra>
                <n-text depth="3" style="font-size: 12px">
                  {{ formatTime(s.updated_at) }}
                </n-text>
              </template>
            </n-thing>
            <template #suffix>
              <n-button quaternary size="tiny" type="error" @click.stop="onDeleteSession(s.id)">删</n-button>
            </template>
          </n-list-item>
        </n-list>
      </n-scrollbar>
    </aside>
    <section class="chat-main">
      <template v-if="chatStore.currentSessionId">
        <div class="chat-messages" ref="messagesEl">
          <div
            v-for="m in renderMessages"
            :key="m.id"
            :class="['message-row', m.role]"
          >
            <div class="message-stack" :class="{ right: m.role === 'user' }">
              <div class="message-bubble">
                <div class="message-meta">
                  <span class="message-role">{{ m.role === "user" ? "你" : "Agent" }}</span>
                  <span class="message-time">{{ formatTime(m.created_at) }}</span>
                </div>
                <div class="message-content">
                  {{ m.id === streamingMessageId ? streamingContent : m.content }}
                  <span v-if="m.role === 'assistant' && m.id === streamingMessageId" class="streaming-cursor">|</span>
                </div>
              </div>
              <!-- 每条 Agent 消息后面自己的推理块（放在输出下面） -->
              <div
                v-if="m.role === 'assistant' && m.inference_steps && m.inference_steps.length"
                class="inference-inline"
              >
                <div class="inference-inline-header" @click="toggleInference(m)">
                  <span class="inference-label">推理过程</span>
                  <span class="inference-toggle">{{ m.inferenceCollapsed ? "展开" : "收起" }}</span>
                </div>
                <div v-show="!m.inferenceCollapsed" class="inference-inline-content">
                  <div
                    v-for="(step, i) in m.inference_steps"
                    :key="i"
                    :class="['inference-item', step.kind]"
                  >
                    <span class="inference-kind">{{ kindLabel(step.kind) }}</span>
                    <span v-if="step.name" class="inference-name">{{ step.name }}</span>
                    <pre class="inference-content">{{ step.content }}</pre>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="chat-bottom">
          <div class="chat-input-wrap">
            <div class="upload-row">
              <input
                ref="fileInputRef"
                type="file"
                multiple
                class="file-input-hidden"
                @change="onFilesChange"
              />
              <n-button quaternary size="small" @click="triggerFileSelect">上传文件</n-button>
              <span
                v-for="(f, i) in selectedFiles"
                :key="i"
                class="file-pill"
              >
                {{ f.name }}
                <span class="file-pill-remove" @click.stop="removeFile(i)">×</span>
              </span>
            </div>
            <div class="input-row">
              <n-input
                v-model:value="inputText"
                type="textarea"
                placeholder="输入消息，Enter 发送，Shift+Enter 换行"
                :autosize="{ minRows: 2, maxRows: 5 }"
                :disabled="sending"
                @keydown.enter.exact.prevent="send"
              />
              <n-button type="primary" :loading="sending" :disabled="!inputText.trim()" @click="send" class="send-btn">
                发送
              </n-button>
            </div>
          </div>
        </div>
      </template>
      <div v-else class="chat-empty">
        <p>选择左侧会话或点击「新建」开始对话</p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, watch, computed } from "vue";
import { NButton, NScrollbar, NList, NListItem, NThing, NText, NInput } from "naive-ui";
import { useChatStore } from "../stores/chat";
import { sessionsApi } from "../api";
import type { MessageOut } from "../api";

export interface InferenceStep {
  kind: string;
  name?: string;
  content: string;
}

type UiMessage = MessageOut & {
  inference_steps?: InferenceStep[];
  inferenceCollapsed?: boolean;
};

const chatStore = useChatStore();
const inputText = ref("");
const sending = ref(false);
const messagesEl = ref<HTMLElement | null>(null);
const fileInputRef = ref<HTMLInputElement | null>(null);
const selectedFiles = ref<File[]>([]);
const streamingController = ref<AbortController | null>(null);
/** 当前正在流式输出的消息 ID，用于显示打字光标 */
const streamingMessageId = ref<number | null>(null);
/** 流式输出时的增量内容，独立 ref 确保 Vue 能逐字触发渲染 */
const streamingContent = ref("");

const renderMessages = computed(() => chatStore.messages as unknown as UiMessage[]);

function formatTime(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" }) + " " + d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function kindLabel(kind: string) {
  const map: Record<string, string> = {
    thinking: "思考",
    tool_call: "调用工具",
    tool_result: "工具结果",
  };
  return map[kind] || kind;
}

async function onNewSession() {
  const s = await chatStore.createSession();
  await chatStore.selectSession(s.id);
}

function onSelectSession(id: number) {
  chatStore.selectSession(id);
}

async function streamAssistantReply(
  sessionId: number,
  userMessage: string,
  assistantMsg: UiMessage
) {
  const controller = new AbortController();
  streamingController.value = controller;
  streamingMessageId.value = assistantMsg.id;
  streamingContent.value = "";
  try {
    const resp = await fetch(`/api/sessions/${sessionId}/messages/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_message: userMessage }),
      signal: controller.signal,
    });
    if (!resp.ok) throw new Error(`请求失败: ${resp.status}`);
    if (!resp.body) throw new Error("浏览器不支持流式响应");
    const reader = resp.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
      let idx: number;
      // eslint-disable-next-line no-cond-assign
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const rawEvent = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const dataLine = rawEvent.split("\n").find((line) => line.startsWith("data:"));
        if (!dataLine) continue;
        const jsonStr = dataLine.slice(5).trim();
        if (!jsonStr) continue;
        let payload: { event?: string; delta?: string; content?: string; message_id?: number; created_at?: string; inference_steps?: InferenceStep[]; message?: string };
        try {
          payload = JSON.parse(jsonStr);
        } catch {
          continue;
        }
        const eventType = payload.event;
        if (eventType === "chunk") {
          streamingContent.value += payload.delta ?? "";
          await nextTick();
          messagesEl.value?.scrollTo({ top: messagesEl.value.scrollHeight, behavior: "smooth" });
        } else if (eventType === "end") {
          assistantMsg.content = payload.content ?? assistantMsg.content;
          assistantMsg.id = payload.message_id ?? assistantMsg.id;
          assistantMsg.created_at = payload.created_at ?? assistantMsg.created_at;
          assistantMsg.inference_steps = (payload.inference_steps || []) as InferenceStep[];
          assistantMsg.inferenceCollapsed = true;
          return;
        } else if (eventType === "error") {
          throw new Error(payload.message || "Agent 流式返回错误");
        }
      }
      if (done) break;
    }
  } finally {
    streamingController.value = null;
    streamingMessageId.value = null;
    streamingContent.value = "";
  }
}

async function send() {
  const text = inputText.value.trim();
  const sessionId = chatStore.currentSessionId;
  if (!text || !sessionId || sending.value) return;

  // 发送前折叠并清空所有历史推理内容，只保留最新一轮的推理
  renderMessages.value.forEach((m) => {
    if (m.inference_steps && m.inference_steps.length) {
      m.inferenceCollapsed = true;
      m.inference_steps = [];
    }
  });

  // 先在前端展示用户消息（本地乐观更新）
  const userMsg: UiMessage = {
    id: Date.now(),
    session_id: sessionId,
    role: "user",
    content: text,
    created_at: new Date().toISOString(),
  };

  chatStore.appendMessage(userMsg as unknown as MessageOut);
  inputText.value = "";
  sending.value = true;
  try {
    const hasFiles = selectedFiles.value.length > 0;
    if (hasFiles) {
      const res = await sessionsApi.sendMessageWithFiles(sessionId, text, selectedFiles.value);
      selectedFiles.value = [];
      const steps = res.inference_steps || [];
      const assistantMsg: UiMessage = {
        id: res.message_id,
        session_id: sessionId,
        role: "assistant",
        content: res.content,
        created_at: res.created_at,
        inference_steps: steps,
        inferenceCollapsed: true,
      };
      chatStore.appendMessage(assistantMsg as unknown as MessageOut);
      await nextTick();
      messagesEl.value?.scrollTo({ top: messagesEl.value.scrollHeight, behavior: "smooth" });
    } else {
      // 无文件时走流式接口
      const placeholderId = Date.now() + 1;
      const assistantMsg: UiMessage = {
        id: placeholderId,
        session_id: sessionId,
        role: "assistant",
        content: "",
        created_at: new Date().toISOString(),
        inference_steps: [],
        inferenceCollapsed: true,
      };
      chatStore.appendMessage(assistantMsg as unknown as MessageOut);
      await nextTick();
      messagesEl.value?.scrollTo({ top: messagesEl.value.scrollHeight, behavior: "smooth" });
      await streamAssistantReply(sessionId, text, assistantMsg);
      await nextTick();
      messagesEl.value?.scrollTo({ top: messagesEl.value.scrollHeight, behavior: "smooth" });
      selectedFiles.value = [];
    }
  } finally {
    sending.value = false;
  }
}

function triggerFileSelect() {
  fileInputRef.value?.click();
}

function onFilesChange(e: Event) {
  const input = e.target as HTMLInputElement;
  if (!input.files) return;
  selectedFiles.value = Array.from(input.files);
}

function removeFile(index: number) {
  selectedFiles.value.splice(index, 1);
}

function toggleInference(msg: UiMessage) {
  msg.inferenceCollapsed = !msg.inferenceCollapsed;
}

async function onDeleteSession(id: number) {
  await sessionsApi.delete(id);
  if (chatStore.currentSessionId === id) {
    chatStore.clearCurrent();
  }
  chatStore.removeSessionFromList(id);
}

async function onClearAll() {
  await sessionsApi.clearAll();
  chatStore.clearAllSessions();
}

watch(
  () => chatStore.messages.length,
  () => nextTick(() => messagesEl.value?.scrollTo({ top: messagesEl.value.scrollHeight, behavior: "smooth" }))
);

onMounted(() => {
  chatStore.fetchSessions();
});
</script>

<style scoped>
.chat-view {
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 0;
}

.session-list-wrap {
  width: 260px;
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  background: var(--bg-surface);
}

.session-list-header {
  padding: 12px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  background: var(--bg-surface);
}

.session-header-actions {
  display: flex;
  gap: 8px;
}

.session-header-actions :deep(.n-button) {
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border-radius: 999px;
}

.session-header-actions :deep(.n-button--primary-type) {
  background: rgba(34, 211, 238, 0.16);
  color: var(--accent);
  box-shadow: none;
}

.session-header-actions :deep(.n-button--error-type) {
  background: rgba(239, 68, 68, 0.08);
  color: #fca5a5;
  box-shadow: none;
}

.session-scroll {
  flex: 1;
  min-height: 0;
}

.session-scroll :deep(.n-list-item) {
  cursor: pointer;
}
.session-scroll :deep(.n-list-item.active) {
  background: rgba(15, 23, 42, 0.85);
  border-left: 2px solid var(--accent);
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  background: var(--bg-base);
  /* 限制中间对话区域的最大宽度，让输入与输出更集中 */
  align-items: center; /* 对话内容与输入框整体居中 */
  padding-right: 150px; /* 轻微向左偏移，避免太贴近右侧栏 */
}

.chat-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px 12px 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 750px;
  max-width: 750px; /* 收窄对话宽度，靠近输入框 */
}

.message-row {
  display: flex;
  width: 100%;
}
.message-row.user {
  justify-content: flex-end;
}
.message-stack {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 78%;
}
.message-stack.right {
  align-items: flex-end;
}

.message-bubble {
  max-width: 78%;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
}
.message-row.assistant .message-bubble {
  border-color: rgba(34, 211, 238, 0.35);
  box-shadow: 0 0 12px rgba(34, 211, 238, 0.06);
}
.message-meta {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.message-role {
  font-weight: 600;
  color: var(--accent);
}
.message-content {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.55;
}

.streaming-cursor {
  display: inline-block;
  margin-left: 1px;
  color: var(--accent);
  animation: blink 0.8s ease-in-out infinite;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

.chat-bottom {
  flex-shrink: 0;
  border-top: 1px solid var(--border);
  background: var(--bg-surface);
  /* 使输入框与消息区域距离更紧凑 */
  padding-top: 2px;
  width: 100%;
  display: flex;
  justify-content: center;
}

.chat-input-wrap {
  padding: 6px 12px 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: stretch;
  width: 750px;
  max-width: 750px; /* 与消息区域同宽，输入/输出更贴近 */
}
.chat-input-wrap :deep(.n-input) {
  width: 100%;
}
.chat-input-wrap :deep(.n-input .n-input__textarea-el) {
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 6px;
}
.chat-input-wrap :deep(.n-input .n-input__textarea-el:focus) {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-dim);
}
.send-btn {
  flex-shrink: 0;
  background: var(--accent) !important;
  color: #020617 !important;
  border: none;
  box-shadow: 0 0 12px rgba(15, 23, 42, 0.9);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 12px;
  transition: background-color 0.15s ease, box-shadow 0.15s ease;
}

.send-btn:hover {
  background-color: #38e0f4 !important;
  box-shadow: 0 0 14px rgba(34, 211, 238, 0.6);
}

.send-btn:active {
  box-shadow: 0 0 8px rgba(15, 23, 42, 0.9);
}

.input-row {
  display: flex;
  align-items: flex-end;
  gap: 12px;
}

.upload-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.upload-row :deep(.n-button) {
  padding-inline: 10px;
  border-radius: 999px;
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border: 1px solid rgba(148, 163, 184, 0.35);
  box-shadow: none;
}

.file-input-hidden {
  display: none;
}

.file-pill {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.8);
  background: rgba(15, 23, 42, 0.2);
  color: var(--text-primary);
}

.file-pill-remove {
  margin-left: 4px;
  cursor: pointer;
}

.inference-inline {
  margin-top: 2px;
  width: 100%;
  font-size: 12px;
}

.inference-inline-header {
  display: flex;
  justify-content: space-between;
  cursor: pointer;
  color: var(--text-muted);
}

.inference-toggle {
  font-size: 11px;
}

.inference-box {
  border-top: 1px solid var(--border);
  max-height: 200px;
  display: flex;
  flex-direction: column;
  background: var(--bg-elevated);
}

.inference-title {
  padding: 8px 16px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.inference-label {
  color: var(--accent);
}
.inference-status {
  color: var(--accent);
  animation: pulse 1s ease-in-out infinite;
}
@keyframes pulse {
  50% { opacity: 0.6; }
}

.inference-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.inference-item {
  font-size: 12px;
  padding: 8px 10px;
  border-radius: 4px;
  border-left: 3px solid var(--border);
  background: rgba(0, 0, 0, 0.2);
}
.inference-item.thinking {
  border-left-color: var(--accent);
  color: var(--text-secondary);
}
.inference-item.tool_call {
  border-left-color: #a78bfa;
  color: var(--text-secondary);
}
.inference-item.tool_result {
  border-left-color: #34d399;
  color: var(--text-secondary);
}
.inference-kind {
  font-weight: 600;
  margin-right: 8px;
  color: var(--text-muted);
}
.inference-name {
  color: var(--accent);
  margin-right: 6px;
}
.inference-content {
  margin: 4px 0 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 11px;
  color: var(--text-secondary);
  font-family: inherit;
}

.chat-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: 14px;
}
</style>
