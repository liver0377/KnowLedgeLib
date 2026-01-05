<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { apiFetch } from "@/api/http";

type UserRow = { id: string; name: string; username: string; roles: string[] };
const search = ref("");
const users = ref<UserRow[]>([]);
const loading = ref(false);
const saving = ref<string | null>(null);

const filtered = computed(() =>
  users.value.filter((u) => u.username.toLowerCase().includes(search.value.toLowerCase()))
);

async function loadUsers() {
  loading.value = true;
  users.value = await apiFetch<UserRow[]>("/admin/users"); // 后端需提供接口，包含当前权限
  loading.value = false;
}

async function toggleRole(user: UserRow, role: "viewer" | "editor") {
  saving.value = user.id;
  const nextRoles = user.roles.includes(role)
    ? user.roles.filter((r) => r !== role)
    : [...user.roles.filter((r) => r !== "viewer" && r !== "editor"), role];
  await apiFetch(`/admin/users/${user.id}/permissions`, {
    method: "POST",
    body: JSON.stringify({ roles: nextRoles }),
  });
  await loadUsers();
  saving.value = null;
}

onMounted(loadUsers);
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <input v-model="search" placeholder="按用户名搜索" />
    </div>
    <table class="user-table">
      <thead><tr><th>姓名</th><th>用户名</th><th>权限</th></tr></thead>
      <tbody>
        <tr v-for="u in filtered" :key="u.id">
          <td>{{ u.name }}</td>
          <td>{{ u.username }}</td>
          <td>
            <label><input type="checkbox" :checked="u.roles.includes('viewer')" @change="toggleRole(u, 'viewer')" />查看</label>
            <label><input type="checkbox" :checked="u.roles.includes('editor')" @change="toggleRole(u, 'editor')" />编辑</label>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="loading" class="hint">加载中...</div>
    <div v-if="saving" class="hint">保存 {{ saving }} ...</div>
  </div>
</template>
