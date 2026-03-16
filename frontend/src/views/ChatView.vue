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
        <div class="session-list" role="list">
          <div
            v-for="s in chatStore.sessionList"
            :key="s.id"
            :class="['session-item', { active: s.id === chatStore.currentSessionId }]"
            role="listitem"
            @click="onSelectSession(s.id)"
          >
            <div class="session-item-main">
              <n-tooltip trigger="hover" :delay="300">
                <template #trigger>
                  <span class="session-item-title">{{ s.title || "新会话" }}</span>
                </template>
                {{ s.title || "新会话" }}
              </n-tooltip>
              <div class="session-item-meta">
                <span class="session-item-time">{{ formatTime(s.updated_at) }}</span>
                <n-button
                  quaternary
                  size="tiny"
                  type="error"
                  class="session-item-delete"
                  @click.stop="onDeleteSession(s.id)"
                >
                  删
                </n-button>
              </div>
            </div>
          </div>
        </div>
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
              <!-- 上方框：推理过程，先流式展示，结束后折叠 -->
              <div
                v-if="m.role === 'assistant' && m.inference_steps && m.inference_steps.length"
                class="inference-box-top"
              >
                <div class="inference-inline-header" @click="toggleInference(m)">
                  <span class="inference-label">
                    {{ m.inferenceDurationSec != null ? `推理中(用时${m.inferenceDurationSec}秒)` : "推理中" }}<span class="inference-caret">^</span>
                  </span>
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
              <!-- 下方框：最终执行结果，流式展示 -->
              <div class="message-bubble result-box">
                <div class="message-meta">
                  <span class="message-role">{{ m.role === "user" ? "你" : "Agent" }}</span>
                  <span class="message-time">{{ formatTime(m.created_at) }}</span>
                </div>
                <div class="message-content">
                  <template v-if="m.role === 'assistant' && (m.inference_steps?.length || m.content || streamingContent)">
                    <div v-if="(m.id === streamingMessageId ? streamingContent : m.content)" class="result-label">执行结果</div>
                  </template>
                  <div class="message-body">
                    <template v-if="m.id === streamingMessageId">
                      <template v-if="streamingContent">{{ streamingContent }}<span v-if="m.role === 'assistant'" class="streaming-cursor">|</span></template>
                    </template>
                    <template v-else>{{ m.content }}</template>
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
              <span v-for="(f, i) in selectedFiles" :key="i" class="file-pill">
                <span class="file-pill-name">{{ f.name }}</span>
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
              <button
                type="button"
                class="send-btn"
                :disabled="sending || !inputText.trim()"
                @click="send"
              >
                {{ sending ? "发送中…" : "发送" }}
              </button>
            </div>
          </div>
        </div>
      </template>
      <div v-else class="chat-empty">
        <div class="chat-empty-inner">
          <div class="chat-empty-icon">💬</div>
          <p class="chat-empty-text">选择左侧会话或点击「新建」开始对话</p>
          <p class="chat-empty-hint">在左侧边栏管理历史会话</p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, watch, computed } from "vue";
import { NButton, NScrollbar, NInput, NTooltip } from "naive-ui";
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
  /** 推理耗时（秒），从首条消息到 end 的时长，用于展示「推理中(用时X秒)」 */
  inferenceDurationSec?: number;
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
  assistantMsg: UiMessage,
  files?: File[]
) {
  const controller = new AbortController();
    streamingController.value = controller;
  streamingMessageId.value = assistantMsg.id;
  streamingContent.value = "";
  /** 首个消息接收时间，用于计算「从收到首个消息到最后一个消息」的耗时 */
  let firstEventTime: number | null = null;
  try {
    const url = files?.length
      ? `/api/sessions/${sessionId}/messages/upload/stream`
      : `/api/sessions/${sessionId}/messages/stream`;
    const body = files?.length
      ? (() => {
          const form = new FormData();
          form.append("user_message", userMessage);
          files.forEach((f) => form.append("files", f));
          return form;
        })()
      : JSON.stringify({ user_message: userMessage });
    const headers: Record<string, string> = files?.length ? {} : { "Content-Type": "application/json" };
    const resp = await fetch(url, {
      method: "POST",
      headers,
      body,
      signal: controller.signal,
    });
    if (!resp.ok) throw new Error(`请求失败: ${resp.status}`);
    if (!resp.body) throw new Error("浏览器不支持流式响应");
    const reader = resp.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let last_tool_content: boolean | undefined = undefined;

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
        let payload: {
          event?: string;
          delta?: string;
          step?: InferenceStep;
          content?: string;
          tool_content?: boolean;
          message_id?: number;
          created_at?: string;
          inference_steps?: InferenceStep[];
          message?: string;
        };
        try {
          payload = JSON.parse(jsonStr);
        } catch {
          continue;
        }
        const eventType = payload.event;
        if (firstEventTime == null) firstEventTime = Date.now();
        if (eventType === "inference_step" && payload.step) {
          streamingContent.value = "";
          assistantMsg.inference_steps = assistantMsg.inference_steps || [];
          assistantMsg.inference_steps.push(payload.step as InferenceStep);
          assistantMsg.inferenceCollapsed = false;
          await nextTick();
          messagesEl.value?.scrollTo({ top: messagesEl.value.scrollHeight, behavior: "smooth" });
        } else if (eventType === "chunk") {
          assistantMsg.inferenceCollapsed = true;
          const is_tool_content = payload.tool_content === true;
          if (last_tool_content === true && is_tool_content === false) {
            streamingContent.value = "";
          }
          last_tool_content = is_tool_content;
          streamingContent.value += payload.delta ?? "";
          await nextTick();
          messagesEl.value?.scrollTo({ top: messagesEl.value.scrollHeight, behavior: "smooth" });
        } else if (eventType === "end") {
          // 从收到首个消息到最后一个消息(end)的耗时
          assistantMsg.inferenceDurationSec = Math.round((Date.now() - (firstEventTime ?? Date.now())) / 1000);
          const fromStream = streamingContent.value;
          const fromPayload = payload.content ?? "";
          assistantMsg.content = fromStream && fromStream.length >= (fromPayload?.length || 0) ? fromStream : (fromPayload || assistantMsg.content);
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

  // 发送前折叠历史推理块（保留内容），推理保留在各自的框里
  renderMessages.value.forEach((m) => {
    if (m.inference_steps && m.inference_steps.length) {
      m.inferenceCollapsed = true;
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
    const files = selectedFiles.value.length > 0 ? [...selectedFiles.value] : undefined;
    selectedFiles.value = [];

    // 统一走流式接口：无文件用 /messages/stream，有文件用 /messages/upload/stream
    const placeholderId = Date.now() + 1;
    const assistantMsg: UiMessage = {
      id: placeholderId,
      session_id: sessionId,
      role: "assistant",
      content: "",
      created_at: new Date().toISOString(),
      inference_steps: [],
      inferenceCollapsed: false,
    };
    chatStore.appendMessage(assistantMsg as unknown as MessageOut);
    await nextTick();
    messagesEl.value?.scrollTo({ top: messagesEl.value.scrollHeight, behavior: "smooth" });
    await streamAssistantReply(sessionId, text, assistantMsg, files);
    await nextTick();
    messagesEl.value?.scrollTo({ top: messagesEl.value.scrollHeight, behavior: "smooth" });
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
  flex-direction: row;
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
  background: var(--accent-dim);
  color: var(--accent);
  box-shadow: none;
}

.session-header-actions :deep(.n-button--error-type) {
  background: rgba(239, 68, 68, 0.08);
  color: #dc2626;
  box-shadow: none;
}

.session-scroll {
  flex: 1;
  min-height: 0;
}

.session-list {
  padding: 8px 0;
}

.session-item {
  display: flex;
  align-items: stretch;
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.15s ease;
  border-left: 2px solid transparent;
}

.session-item:hover {
  background: var(--bg-base);
}

.session-item.active {
  background: var(--accent-soft);
  border-left-color: var(--accent);
}

.session-item-main {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.session-item-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  color: var(--text-primary);
}

.session-item-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.session-item-time {
  font-size: 11px;
  color: var(--text-muted);
}

.session-item-delete {
  opacity: 0.6;
  transition: opacity 0.15s ease;
}

.session-item:hover .session-item-delete {
  opacity: 1;
}

.session-item-delete :deep(.n-button__content) {
  font-size: 11px;
  padding: 0 6px;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  background: var(--bg-base);
  align-items: center;
  justify-content: flex-start;
  padding: 0 140px 0 20px; /* 右侧 80px，整体向左移 40px */
}

.chat-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px 16px 12px;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 16px;
  width: 100%;
  max-width: 720px;
  scroll-behavior: smooth;
  background: var(--bg-base);
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
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}
.message-row.assistant .message-bubble {
  border-color: var(--accent-dim);
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

.inference-placeholder {
  color: var(--text-tertiary, #999);
  font-style: italic;
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
  width: 100%;
  display: flex;
  justify-content: center;
}

.chat-input-wrap {
  padding: 12px 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: stretch;
  width: 100%;
  max-width: 720px;
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

.input-row {
  display: flex;
  align-items: flex-end;
  gap: 12px;
}

.input-row :deep(.n-input) {
  flex: 1;
  min-width: 0;
}

.send-btn {
  flex-shrink: 0;
  min-height: 36px;
  min-width: 80px;
  padding: 0 24px;
  border-radius: 8px;
  background: var(--accent);
  color: #fff;
  border: none;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.15s ease;
  white-space: nowrap;
  overflow: visible;
}
.send-btn:hover:not(:disabled) {
  background-color: var(--accent-hover);
}
.send-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.upload-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.upload-row :deep(.n-button) {
  padding-inline: 10px;
  border-radius: 999px;
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border: 1px solid var(--border);
}

.file-input-hidden {
  display: none;
}

.file-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--accent-soft);
  color: var(--text-primary);
  max-width: 160px;
}

.file-pill-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-pill-remove {
  flex-shrink: 0;
  cursor: pointer;
  opacity: 0.8;
}
.file-pill-remove:hover {
  opacity: 1;
}

.inference-inline {
  margin-top: 8px;
  width: 100%;
  font-size: 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg-elevated);
  overflow: hidden;
}

/* 上方推理框：先流式展示，结束后折叠 */
.inference-box-top {
  width: 100%;
  margin-bottom: 8px;
  font-size: 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg-elevated);
  overflow: hidden;
}

.inference-caret {
  margin-left: 4px;
  font-size: 10px;
  opacity: 0.7;
}

/* 下方执行结果框 */
.result-box .result-label {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border);
}

.result-box .message-body {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.55;
}

.inference-inline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  padding: 8px 12px;
  color: var(--text-muted);
  transition: background 0.15s ease;
}

.inference-inline-header:hover {
  background: var(--bg-base);
}

.inference-toggle {
  font-size: 11px;
  color: var(--accent);
}

.inference-inline-content {
  padding: 8px 12px;
  border-top: 1px solid var(--border);
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
  background: var(--accent-soft);
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
  min-height: 200px;
}

.chat-empty-inner {
  text-align: center;
  padding: 32px 24px;
}

.chat-empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.6;
}

.chat-empty-text {
  color: var(--text-secondary);
  font-size: 15px;
  font-weight: 500;
  margin: 0 0 8px;
}

.chat-empty-hint {
  color: var(--text-muted);
  font-size: 13px;
  margin: 0;
}
</style>
