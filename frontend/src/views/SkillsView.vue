<template>
  <div class="skills-view">
    <n-card title="技能列表" class="card">
      <template #header-extra>
        <n-space wrap :size="[8, 8]">
          <n-button type="primary" size="small" @click="showLocalModal = true">从本地路径添加</n-button>
          <n-button size="small" @click="showGitHubModal = true">从 GitHub 添加</n-button>
        </n-space>
      </template>
      <n-data-table
        :columns="columns"
        :data="skillList"
        :bordered="false"
        :loading="loading"
      />
    </n-card>

    <n-modal v-model:show="showLocalModal" preset="dialog" title="从本地路径添加" positive-text="添加" @positive-click="onAddLocal">
      <n-form :model="localForm" label-placement="left" label-width="120">
        <n-form-item label="路径" required>
          <n-input v-model:value="localForm.source_path" placeholder="绝对路径如 E:\chrome_downloads\skills\docx 或相对路径 example_skill" />
        </n-form-item>
      </n-form>
    </n-modal>

    <n-modal v-model:show="showGitHubModal" preset="dialog" title="从 GitHub 添加" positive-text="添加" @positive-click="onAddGitHub">
      <n-form :model="githubForm" label-placement="left" label-width="120">
        <n-form-item label="仓库地址" required>
          <n-input v-model:value="githubForm.repo_url" placeholder="如 https://github.com/owner/repo 或 owner/repo" />
        </n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h } from "vue";
import {
  NCard,
  NButton,
  NDataTable,
  NModal,
  NForm,
  NFormItem,
  NInput,
  NSpace,
  NPopconfirm,
  useMessage,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import type { SkillOut } from "../api";
import { skillsApi } from "../api";

const message = useMessage();
const skillList = ref<SkillOut[]>([]);
const loading = ref(false);
const showLocalModal = ref(false);
const showGitHubModal = ref(false);

const localForm = ref({ source_path: "" });
const githubForm = ref({ repo_url: "" });
const columns: DataTableColumns<SkillOut> = [
  { title: "ID", key: "id", width: 70 },
  { title: "名称", key: "name", width: 140 },
  { title: "描述", key: "description", ellipsis: { tooltip: true } },
  { title: "类型", key: "type", width: 90 },
  { title: "来源", key: "source_type", width: 80 },
  { title: "路径", key: "source_path", width: 120, ellipsis: { tooltip: true } },
  { title: "启用", key: "enabled", width: 70, render: (row) => (row.enabled ? "是" : "否") },
  {
    title: "操作",
    key: "actions",
    width: 150,
    render: (row) =>
      h(NSpace, { size: 8 }, () => [
        h(NButton, { size: "small", onClick: () => toggleSkill(row) }, () => (row.enabled ? "禁用" : "启用")),
        h(
          NPopconfirm,
          { positiveText: "删除", negativeText: "取消", onPositiveClick: () => deleteSkill(row) },
          { default: () => "确定删除该技能？", trigger: () => h(NButton, { size: "small", type: "error" }, () => "删除") }
        ),
      ]),
  },
];

async function fetchSkills() {
  loading.value = true;
  try {
    skillList.value = await skillsApi.list();
  } finally {
    loading.value = false;
  }
}

async function toggleSkill(skill: SkillOut) {
  await skillsApi.toggle(skill.id, !skill.enabled);
  await fetchSkills();
}

async function deleteSkill(skill: SkillOut) {
  try {
    await skillsApi.delete(skill.id);
    message.success("已删除");
    await fetchSkills();
  } catch (e: unknown) {
    message.error(e instanceof Error ? e.message : "删除失败");
  }
}

async function onAddLocal() {
  const path = localForm.value.source_path?.trim();
  if (!path) return false;
  try {
    await skillsApi.addFromLocal(path);
    showLocalModal.value = false;
    localForm.value = { source_path: "" };
    await fetchSkills();
    message.success("添加成功");
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "添加失败";
    message.error(msg);
    return false;
  }
}

async function onAddGitHub() {
  const url = githubForm.value.repo_url?.trim();
  if (!url) return;
  await skillsApi.addFromGitHub(url);
  showGitHubModal.value = false;
  githubForm.value = { repo_url: "" };
  await fetchSkills();
}

onMounted(() => {
  fetchSkills();
});
</script>

<style scoped>
.skills-view {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 24px;
  overflow-y: auto;
  max-width: 1000px;
  margin: 0 auto;
  width: 100%;
  background: var(--bg-base);
  box-sizing: border-box;
}

.skills-view :deep(.n-card) {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.skills-view :deep(.n-card__content) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.skills-view :deep(.n-card-header) {
  flex-shrink: 0;
}

.skills-view :deep(.n-data-table) {
  flex: 1;
}

.card {
  margin-bottom: 0;
}
</style>
