import { defineStore } from "pinia";
import { ref, computed } from "vue";
import type { SessionOut, MessageOut } from "../api";
import { sessionsApi } from "../api";

export const useChatStore = defineStore("chat", () => {
  const sessionList = ref<SessionOut[]>([]);
  const total = ref(0);
  const currentSessionId = ref<number | null>(null);
  const messages = ref<MessageOut[]>([]);
  const loading = ref(false);

  const currentSession = computed(() =>
    currentSessionId.value ? sessionList.value.find((s) => s.id === currentSessionId.value) ?? null : null
  );

  async function fetchSessions(limit = 50, offset = 0) {
    loading.value = true;
    try {
      const res = await sessionsApi.list({ limit, offset });
      sessionList.value = res.items;
      total.value = res.total;
      return res;
    } finally {
      loading.value = false;
    }
  }

  async function createSession(title?: string) {
    const s = await sessionsApi.create({ title });
    sessionList.value = [s, ...sessionList.value];
    total.value += 1;
    return s;
  }

  async function selectSession(id: number) {
    currentSessionId.value = id;
    const res = await sessionsApi.get(id);
    messages.value = res.messages;
    const idx = sessionList.value.findIndex((s) => s.id === id);
    if (idx >= 0) sessionList.value[idx] = res.session;
    return res;
  }

  async function loadSession(sessionId: number) {
    const res = await sessionsApi.get(sessionId);
    messages.value = res.messages;
    return res;
  }

  function setMessages(msgs: MessageOut[]) {
    messages.value = msgs;
  }

  function appendMessage(msg: MessageOut) {
    messages.value.push(msg);
  }

  function clearCurrent() {
    currentSessionId.value = null;
    messages.value = [];
  }

  function removeSessionFromList(id: number) {
    sessionList.value = sessionList.value.filter((s) => s.id !== id);
    total.value = Math.max(0, total.value - 1);
  }

  function clearAllSessions() {
    sessionList.value = [];
    total.value = 0;
    clearCurrent();
  }

  return {
    sessionList,
    total,
    currentSessionId,
    currentSession,
    messages,
    loading,
    fetchSessions,
    createSession,
    selectSession,
    loadSession,
    setMessages,
    appendMessage,
    clearCurrent,
    removeSessionFromList,
    clearAllSessions,
  };
});
