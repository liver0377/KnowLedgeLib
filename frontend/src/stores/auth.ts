// src/stores/auth.ts
import { defineStore } from "pinia";
import { apiFetch } from "@/api/http";

export type Me = {
  sub?: string;
  user_id?: string;
  id?: string;
  uid?: string;
  roles?: string[];
  [k: string]: any;
};

export const useAuthStore = defineStore("auth", {
  state: () => ({
    me: null as Me | null,
    loading: false,
    error: "" as string,
    _meChecked: false, // 避免每次路由跳转都反复请求 /auth/me
  }),

  getters: {
    isAuthed: (s) => !!s.me,
    displayId: (s) => s.me?.sub || s.me?.user_id || s.me?.id || s.me?.uid || "",
  },

  actions: {
    async refreshMe(force = false) {
      if (this._meChecked && !force) return;

      this.loading = true;
      this.error = "";
      try {
        this.me = await apiFetch<Me>("/auth/me");
      } catch {
        this.me = null;
      } finally {
        this.loading = false;
        this._meChecked = true;
      }
    },

    async login(username: string, password: string) {
      this.loading = true;
      this.error = "";
      try {
        await apiFetch("/auth/login", {
          method: "POST",
          body: JSON.stringify({ username, password }),
        });
        // 登录成功后立刻拉一次 /auth/me 确认登录态
        await this.refreshMe(true);
        if (!this.me) throw new Error("Login succeeded but /auth/me returned empty");
      } catch (e: any) {
        this.error = e?.message || String(e);
        throw e;
      } finally {
        this.loading = false;
      }
    },

    async logout() {
      this.loading = true;
      this.error = "";
      try {
        await apiFetch("/auth/logout", { method: "POST" });
      } catch {
        // 就算后端失败，也清本地态
      } finally {
        this.me = null;
        this._meChecked = true;
        this.loading = false;
      }
    },
  },
});
