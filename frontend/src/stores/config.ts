import { defineStore } from "pinia";
import { ref } from "vue";
import type { AgentConfigOut } from "../api";
import { agentConfigApi, modelsApi } from "../api";

export const useConfigStore = defineStore("config", () => {
  const agentConfig = ref<AgentConfigOut | null>(null);
  const modelList = ref<{ id: string; name: string; provider: string; description: string }[]>([]);

  async function fetchAgentConfig() {
    agentConfig.value = await agentConfigApi.get();
    return agentConfig.value;
  }

  async function updateAgentConfig(data: Partial<AgentConfigOut>) {
    agentConfig.value = await agentConfigApi.update(data);
    return agentConfig.value;
  }

  async function fetchModelList() {
    modelList.value = await modelsApi.list();
    return modelList.value;
  }

  return {
    agentConfig,
    modelList,
    fetchAgentConfig,
    updateAgentConfig,
    fetchModelList,
  };
});
