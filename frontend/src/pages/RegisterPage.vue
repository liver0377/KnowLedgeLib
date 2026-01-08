<!-- RegisterPage.vue -->
<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { apiFetch } from "@/api/http";

const auth = useAuthStore();
const router = useRouter();

const username = ref("");
const password = ref("");
const displayName = ref("");
const email = ref("");
const deptId = ref<number | null>(null);
const reason = ref("");
const localError = ref("");
const departments = ref<Array<{ id: number; dept_key: string; name: string }>>([]);
const loading = ref(false);
const deptLoading = ref(false);

onMounted(async () => {
  // 加载部门列表
  deptLoading.value = true;
  try {
    const data = await apiFetch<{ items: Array<{ id: number; dept_key: string; name: string }> }>(
      "/departments"
    );
    departments.value = data.items || [];

    // 可选：如果只有一个部门，自动选中
    if (departments.value.length === 1) {
      deptId.value = departments.value[0].id;
    }
  } catch (e) {
    console.error("Failed to load departments:", e);
  } finally {
    deptLoading.value = false;
  }
});

async function onSubmit() {
  localError.value = "";
  loading.value = true;

  // 可选：前端校验（避免提交空部门）
  if (deptId.value == null) {
    localError.value = "Please select a department";
    loading.value = false;
    return;
  }

  try {
    const response = await apiFetch("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        username: username.value.trim(),
        password: password.value,
        display_name: displayName.value.trim(),
        email: email.value.trim() || undefined,
        dept_id: deptId.value,
        reason: reason.value.trim() || undefined,
      }),
    });

    const message =
      (response as any).message ||
      "Registration submitted successfully. Please wait for admin approval.";
    alert(message);

    router.push("/login");
  } catch (e: any) {
    localError.value = e?.message || "Registration failed";
  } finally {
    loading.value = false;
  }
}

function goToLogin() {
  router.push("/login");
}
</script>

<template>
  <div style="min-height: 100vh; display:flex; align-items:center; justify-content:center; font-family: system-ui;">
    <div style="width: 360px; padding: 24px; border: 1px solid #e5e7eb; border-radius: 12px;">
      <h2 style="margin: 0 0 16px;">Sign up</h2>

      <div style="display:flex; flex-direction:column; gap: 10px;">
        <label>
          <div style="font-size: 12px; color:#6b7280; margin-bottom:6px;">Username</div>
          <input
            v-model="username"
            placeholder="At least 3 characters"
            style="width:100%; padding:10px; border:1px solid #d1d5db; border-radius:10px;"
          />
        </label>

        <label>
          <div style="font-size: 12px; color:#6b7280; margin-bottom:6px;">Display Name</div>
          <input
            v-model="displayName"
            placeholder="Your display name"
            style="width:100%; padding:10px; border:1px solid #d1d5db; border-radius:10px;"
          />
        </label>

        <!-- ✅ Department 改成下拉列表 -->
        <label>
          <div style="font-size: 12px; color:#6b7280; margin-bottom:6px;">Department</div>

          <select
            v-model.number="deptId"
            :disabled="deptLoading || departments.length === 0"
            style="width:100%; padding:10px; border:1px solid #d1d5db; border-radius:10px; background:white;"
          >
            <option :value="null" disabled>
              {{ deptLoading ? "Loading departments..." : "Please select a department" }}
            </option>

            <option v-for="dept in departments" :key="dept.id" :value="dept.id">
              {{ dept.name }}
            </option>
          </select>

          <div
            v-if="!deptLoading && departments.length === 0"
            style="margin-top:6px; font-size:12px; color:#6b7280;"
          >
            No departments available.
          </div>
        </label>

        <label>
          <div style="font-size: 12px; color:#6b7280; margin-bottom:6px;">Password</div>
          <input
            v-model="password"
            type="password"
            placeholder="At least 6 characters"
            style="width:100%; padding:10px; border:1px solid #d1d5db; border-radius:10px;"
          />
        </label>

        <label>
          <div style="font-size: 12px; color:#6b7280; margin-bottom:6px;">Email (Optional)</div>
          <input
            v-model="email"
            type="email"
            placeholder="your@email.com"
            style="width:100%; padding:10px; border:1px solid #d1d5db; border-radius:10px;"
          />
        </label>

        <label>
          <div style="font-size: 12px; color:#6b7280; margin-bottom:6px;">Reason for Request (Optional)</div>
          <textarea
            v-model="reason"
            placeholder="Why do you need access to this department?"
            rows="3"
            style="width:100%; padding:10px; border:1px solid #d1d5db; border-radius:10px; resize: vertical;"
          ></textarea>
        </label>

        <button
          @click="onSubmit"
          :disabled="loading"
          style="margin-top: 8px; padding:10px; border-radius:10px; border:none; background:#111827; color:white; cursor:pointer;"
        >
          {{ loading ? "Submitting..." : "Sign Up" }}
        </button>

        <p v-if="localError" style="color:#dc2626; margin: 8px 0 0;">
          {{ localError }}
        </p>

        <p style="font-size:12px; color:#6b7280; margin-top: 12px;">
          After registration, your account will be pending approval from an administrator.
        </p>

        <p style="font-size:12px; color:#6b7280; margin-top: 8px;">
          Already have an account?
          <a @click="goToLogin" style="color:#111827; cursor:pointer; text-decoration:underline;">Sign in</a>
        </p>
      </div>
    </div>
  </div>
</template>
