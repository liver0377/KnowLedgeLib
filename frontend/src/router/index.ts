// src/router/index.ts
import { createRouter, createWebHistory } from "vue-router";
import LoginPage from "@/pages/LoginPage.vue";
import ChatPage from "@/pages/ChatPage.vue";
import { useAuthStore } from "@/stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/chat" },
    { path: "/login", component: LoginPage },
    {
      path: "/chat",
      component: ChatPage,
      meta: { requiresAuth: true },
    },
  ],
});

// 全局守卫：需要登录的页面先检查 /auth/me
router.beforeEach(async (to) => {
  const auth = useAuthStore();

  if (!auth._meChecked) {
    await auth.refreshMe();
  }

  if (to.meta.requiresAuth && !auth.isAuthed) {
    return { path: "/login", query: { redirect: to.fullPath } };
  }

  if (to.path === "/login" && auth.isAuthed) {
    return "/chat";
  }

  return true;
});

export default router;
