<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { apiFetch } from "@/api/http";
import { useAuthStore } from "@/stores/auth";

type UserRow = { id: string; name: string; username: string; roles: string[] };

const router = useRouter();
const auth = useAuthStore();

const search = ref("");
const users = ref<UserRow[]>([]);
const loading = ref(false);
const saving = ref<string | null>(null);

const avatarText = computed(() => (auth.displayId ? auth.displayId[0].toUpperCase() : "?"));

const filtered = computed(() =>
  users.value.filter((u) => u.username.toLowerCase().includes(search.value.toLowerCase()))
);

async function loadUsers() {
  loading.value = true;
  try {
    users.value = await apiFetch<UserRow[]>("/admin/users");
  } finally {
    loading.value = false;
  }
}

async function toggleRole(user: UserRow, role: "viewer" | "editor") {
  saving.value = user.id;
  // 支持多选：添加或移除单个角色，不影响其他角色
  const nextRoles = user.roles.includes(role)
    ? user.roles.filter((r) => r !== role)  // 移除该角色
    : [...user.roles, role];  // 添加该角色
  await apiFetch(`/admin/users/${user.id}/permissions`, {
    method: "POST",
    body: JSON.stringify({ roles: nextRoles }),
  });
  await loadUsers();
  saving.value = null;
}

function goBack() {
  router.push("/chat");
}

async function onLogout() {
  await auth.logout();
  router.replace("/login");
}

onMounted(async () => {
  await auth.refreshMe();
  if (!auth.isAuthed) {
    router.replace("/login");
    return;
  }
  await loadUsers();
});
</script>

<template>
  <div class="layout">
    <!-- Main -->
    <section class="main">
      <!-- Topbar -->
      <header class="topbar">
        <div class="brand-area">
          <button class="back-btn" @click="goBack" title="返回">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M19 12H5M12 19l-7-7 7-7"/>
            </svg>
          </button>
          <div class="brand">权限控制</div>
        </div>

        <div class="actions">
          <button class="btn" @click="onLogout">Logout</button>
          <div class="avatar">{{ avatarText }}</div>
        </div>
      </header>

      <!-- Content Area -->
      <div class="content-area">
        <!-- Search Section -->
        <div class="search-section">
          <div class="search-wrapper">
            <svg class="search-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="8"/>
              <path d="m21 21-4.3-4.3"/>
            </svg>
            <input 
              v-model="search" 
              class="search-input" 
              placeholder="按用户名搜索..." 
            />
          </div>
          <div class="user-count">
            共 {{ filtered.length }} 位用户
          </div>
        </div>

        <!-- User List -->
        <div class="user-list-container">
          <!-- Loading State -->
          <div v-if="loading" class="loading-state">
            <div class="spinner"></div>
            <span>加载中...</span>
          </div>

          <!-- Empty State -->
          <div v-else-if="filtered.length === 0" class="empty-state">
            <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
              <circle cx="9" cy="7" r="4"/>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
              <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
            </svg>
            <p>没有找到匹配的用户</p>
          </div>

          <!-- User Cards -->
          <div v-else class="user-grid">
            <div 
              v-for="u in filtered" 
              :key="u.id" 
              class="user-card"
              :class="{ 'saving': saving === u.id }"
            >
              <div class="user-avatar">
                {{ u.name ? u.name[0].toUpperCase() : u.username[0].toUpperCase() }}
              </div>
              
              <div class="user-info">
                <div class="user-name">{{ u.name || '未设置姓名' }}</div>
                <div class="user-username">@{{ u.username }}</div>
              </div>

              <div class="permissions">
                <label 
                  class="permission-tag"
                  :class="{ active: u.roles.includes('viewer') }"
                >
                  <input 
                    type="checkbox" 
                    :checked="u.roles.includes('viewer')" 
                    @change="toggleRole(u, 'viewer')"
                    :disabled="saving === u.id"
                  />
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                    <circle cx="12" cy="12" r="3"/>
                  </svg>
                  <span>查看</span>
                </label>

                <label 
                  class="permission-tag"
                  :class="{ active: u.roles.includes('editor') }"
                >
                  <input 
                    type="checkbox" 
                    :checked="u.roles.includes('editor')" 
                    @change="toggleRole(u, 'editor')"
                    :disabled="saving === u.id"
                  />
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                  <span>编辑</span>
                </label>
              </div>

              <!-- Saving Indicator -->
              <div v-if="saving === u.id" class="saving-indicator">
                <div class="mini-spinner"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  height: 100vh;
  background: #f6f7fb;
  color: #0f172a;
}

/* Main */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* Topbar */
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  border-bottom: 1px solid #e2e8f0;
  background: #fff;
}

.brand-area {
  display: flex;
  align-items: center;
  gap: 12px;
}

.back-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  transition: all 0.2s;
}

.back-btn:hover {
  background: #f8fafc;
  color: #0f172a;
  border-color: #d1d5db;
}

.brand {
  font-weight: 800;
  font-size: 18px;
}

.actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.btn {
  padding: 8px 14px;
  border-radius: 10px;
  border: 1px solid #d1d5db;
  background: white;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.btn:hover {
  background: #f8fafc;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  background: #111827;
  color: #fff;
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 14px;
}

/* Content Area */
.content-area {
  flex: 1;
  overflow: auto;
  padding: 24px;
}

/* Search Section */
.search-section {
  max-width: 1200px;
  margin: 0 auto 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.search-wrapper {
  position: relative;
  flex: 1;
  max-width: 400px;
}

.search-icon {
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: #9ca3af;
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: 12px 14px 12px 44px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: #fff;
  font-size: 14px;
  outline: none;
  transition: all 0.2s;
}

.search-input:focus {
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.search-input::placeholder {
  color: #9ca3af;
}

.user-count {
  font-size: 14px;
  color: #64748b;
  white-space: nowrap;
}

/* User List Container */
.user-list-container {
  max-width: 1200px;
  margin: 0 auto;
}

/* Loading State */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #64748b;
  gap: 16px;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #e2e8f0;
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #94a3b8;
  gap: 16px;
}

.empty-state p {
  font-size: 15px;
}

/* User Grid */
.user-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}

/* User Card */
.user-card {
  position: relative;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: all 0.2s;
}

.user-card:hover {
  border-color: #d1d5db;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);
}

.user-card.saving {
  opacity: 0.7;
  pointer-events: none;
}

.user-avatar {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 18px;
  flex-shrink: 0;
}

.user-info {
  flex: 1;
  min-width: 0;
}

.user-name {
  font-weight: 600;
  font-size: 15px;
  color: #0f172a;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-username {
  font-size: 13px;
  color: #64748b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Permissions */
.permissions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.permission-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  cursor: pointer;
  font-size: 13px;
  color: #64748b;
  transition: all 0.2s;
  user-select: none;
}

.permission-tag input {
  display: none;
}

.permission-tag:hover {
  border-color: #d1d5db;
  background: #f1f5f9;
}

.permission-tag.active {
  background: #eef2ff;
  border-color: #c7d2fe;
  color: #4f46e5;
}

.permission-tag.active svg {
  color: #6366f1;
}

/* Saving Indicator */
.saving-indicator {
  position: absolute;
  top: 12px;
  right: 12px;
}

.mini-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid #e2e8f0;
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* Responsive */
@media (max-width: 768px) {
  .content-area {
    padding: 16px;
  }

  .search-section {
    flex-direction: column;
    align-items: stretch;
  }

  .search-wrapper {
    max-width: none;
  }

  .user-count {
    text-align: center;
  }

  .user-grid {
    grid-template-columns: 1fr;
  }

  .user-card {
    flex-wrap: wrap;
  }

  .permissions {
    width: 100%;
    margin-top: 8px;
    padding-top: 12px;
    border-top: 1px solid #f1f5f9;
    justify-content: flex-end;
  }
}
</style>
