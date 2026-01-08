// src/router/index.ts
import { createRouter, createWebHistory } from "vue-router";
import LoginPage from "@/pages/LoginPage.vue";
import RegisterPage from "@/pages/RegisterPage.vue";
import ChatPage from "@/pages/ChatPage.vue";
import { useAuthStore } from "@/stores/auth";
import PermissionPage from "@/pages/PermissionPage.vue";
import FileManagerPage from "@/pages/FileManagerPage.vue";
import ApprovalPage from "@/pages/ApprovalPage.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/chat" },
    { path: "/login", component: LoginPage },
    { path: "/register", component: RegisterPage },
    {
      path: "/chat",
      component: ChatPage,
      meta: { requiresAuth: true },
    },
    { 
      path: "/permissions",
      component: PermissionPage,
      meta: { requiresAuth: true, adminOnly: true } 
    },
    { 
      path: "/files",
      component: FileManagerPage,
      meta: { requiresAuth: true, adminOnly: true } 
    },
    { 
      path: "/approvals",
      component: ApprovalPage,
      meta: { requiresAuth: true, adminOnly: true } 
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

  if (to.meta.adminOnly && !auth.me?.roles?.includes("admin")) {
    return "/chat";
  }

  if ((to.path === "/login" || to.path === "/register") && auth.isAuthed) {
    return "/chat";
  }

  return true;
});

export default router;
