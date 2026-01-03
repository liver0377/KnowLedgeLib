<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

const username = ref("ryan");
const password = ref("123456");
const localError = ref("");

onMounted(async () => {
  await auth.refreshMe();
  if (auth.isAuthed) router.replace("/chat");
});

async function onSubmit() {
  localError.value = "";
  try {
    await auth.login(username.value.trim(), password.value);
    const redirect = (route.query.redirect as string) || "/chat";
    router.replace(redirect);
  } catch (e: any) {
    localError.value = auth.error || e?.message || "Login failed";
  }
}
</script>

<template>
  <div style="min-height: 100vh; display:flex; align-items:center; justify-content:center; font-family: system-ui;">
    <div style="width: 360px; padding: 24px; border: 1px solid #e5e7eb; border-radius: 12px;">
      <h2 style="margin: 0 0 16px;">Sign in</h2>

      <div style="display:flex; flex-direction:column; gap: 10px;">
        <label>
          <div style="font-size: 12px; color:#6b7280; margin-bottom:6px;">Username</div>
          <input v-model="username" style="width:100%; padding:10px; border:1px solid #d1d5db; border-radius:10px;" />
        </label>

        <label>
          <div style="font-size: 12px; color:#6b7280; margin-bottom:6px;">Password</div>
          <input v-model="password" type="password"
                 style="width:100%; padding:10px; border:1px solid #d1d5db; border-radius:10px;" />
        </label>

        <button
          @click="onSubmit"
          :disabled="auth.loading"
          style="margin-top: 8px; padding:10px; border-radius:10px; border:none; background:#111827; color:white; cursor:pointer;"
        >
          {{ auth.loading ? "Signing in..." : "Sign In" }}
        </button>

        <p v-if="localError" style="color:#dc2626; margin: 8px 0 0;">
          {{ localError }}
        </p>

        <p style="font-size:12px; color:#6b7280; margin-top: 12px;">
          Demo: ryan/123456 or viewer/123456
        </p>
      </div>
    </div>
  </div>
</template>
