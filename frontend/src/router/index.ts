import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: "/", name: "chat", component: () => import("../views/ChatView.vue"), meta: { title: "聊天" } },
    { path: "/models", name: "models", component: () => import("../views/ModelsView.vue"), meta: { title: "模型配置" } },
    { path: "/skills", name: "skills", component: () => import("../views/SkillsView.vue"), meta: { title: "技能管理" } },
  ],
});

export default router;
