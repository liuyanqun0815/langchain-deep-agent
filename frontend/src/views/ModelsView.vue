<template>
  <div class="models-view">
    <n-card title="模型配置" class="card">
      <n-form ref="formRef" :model="form" label-placement="left" label-width="120">
        <n-form-item label="默认模型">
          <n-select
            v-model:value="form.default_model"
            :options="modelOptions"
            placeholder="选择模型"
            filterable
          />
        </n-form-item>
        <n-form-item label="最大 Token">
          <n-input-number v-model:value="form.max_tokens" :min="256" :max="128000" style="width: 100%" />
        </n-form-item>
        <n-form-item label="温度">
          <n-slider v-model:value="form.temperature" :min="0" :max="2" :step="0.1" />
          <span class="form-value">{{ form.temperature }}</span>
        </n-form-item>
        <n-space>
          <n-button type="primary" :loading="saving" @click="save">保存配置</n-button>
          <n-button :loading="testing" @click="testModel">测试连接</n-button>
        </n-space>
      </n-form>
      <template v-if="testResult !== null">
        <n-alert :type="testResult.success ? 'success' : 'error'" style="margin-top: 12px">
          {{ testResult.success ? "连接成功" : "连接失败" }}：{{ testResult.message }}
        </n-alert>
      </template>
    </n-card>
    <n-card title="可用模型列表" class="card">
      <n-data-table :columns="columns" :data="configStore.modelList" :bordered="false" />
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from "vue";
import { NCard, NForm, NFormItem, NSelect, NInputNumber, NSlider, NButton, NSpace, NAlert, NDataTable } from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import { useConfigStore } from "../stores/config";
import { modelsApi } from "../api";

const configStore = useConfigStore();
const saving = ref(false);
const testing = ref(false);
const testResult = ref<{ success: boolean; message: string } | null>(null);

const form = reactive({
  default_model: "",
  max_tokens: 4096,
  temperature: 0.7,
});

const modelOptions = computed(() =>
  configStore.modelList.map((m) => ({ label: `${m.name} (${m.provider})`, value: m.id }))
);

const columns: DataTableColumns<{ id: string; name: string; provider: string; description: string }> = [
  { title: "ID", key: "id", width: 200, ellipsis: { tooltip: true } },
  { title: "名称", key: "name", width: 140 },
  { title: "提供方", key: "provider", width: 100 },
  { title: "描述", key: "description" },
];

async function save() {
  saving.value = true;
  testResult.value = null;
  try {
    await configStore.updateAgentConfig({
      default_model: form.default_model,
      max_tokens: form.max_tokens,
      temperature: form.temperature,
    });
  } finally {
    saving.value = false;
  }
}

async function testModel() {
  testing.value = true;
  testResult.value = null;
  try {
    const res = await modelsApi.test();
    testResult.value = res;
  } finally {
    testing.value = false;
  }
}

onMounted(async () => {
  await configStore.fetchModelList();
  await configStore.fetchAgentConfig();
  if (configStore.agentConfig) {
    form.default_model = configStore.agentConfig.default_model;
    form.max_tokens = configStore.agentConfig.max_tokens;
    form.temperature = configStore.agentConfig.temperature;
  }
});
</script>

<style scoped>
.models-view {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  padding: 24px;
  overflow-y: auto;
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
  background: var(--bg-base);
}

.models-view :deep(.n-card) {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.card {
  margin-bottom: 24px;
}

.form-value {
  margin-left: 12px;
  font-size: 13px;
  color: var(--text-secondary);
}
</style>
