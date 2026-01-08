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
const deleting = ref<string | null>(null);
const showDeleteDialog = ref<UserRow | null>(null);

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

async function toggleRole(user: UserRow, role: "admin" | "member") {
  saving.value = user.id;
  // 切换用户的全局角色（admin 或 member）
  // 注意：editor 和 viewer 不再是全局角色，而是部门级别权限
  const nextRoles = user.roles.includes(role)
    ? user.roles.filter((r) => r !== role)  // 移除该角色
    : [...user.roles, role];  // 添加该角色
  
  // 确保用户至少有一个角色（至少是 member）
  if (nextRoles.length === 0) {
    nextRoles.push("member");
  }
  
  await apiFetch(`/admin/users/${user.id}/permissions`, {
    method: "POST",
    body: JSON.stringify({ roles: nextRoles }),
  });
  await loadUsers();
  saving.value = null;
}

function openDeleteDialog(user: UserRow) {
  showDeleteDialog.value = user;
}

function closeDeleteDialog() {
  showDeleteDialog.value = null;
}

async function confirmDeleteUser() {
  if (!showDeleteDialog.value) return;

  const user = showDeleteDialog.value;
  deleting.value = user.id;

  try {
    await apiFetch(`/admin/users/${user.id}`, {
      method: "DELETE",
    });
    await loadUsers();
    closeDeleteDialog();
  } catch (e: any) {
    alert(e?.message || "删除用户失败");
  } finally {
    deleting.value = null;
  }
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

          <!-- User List -->
          <div v-else class="user-list">
            <div class="list-header">
              <div class="header-cell avatar-cell"></div>
              <div class="header-cell name-cell">用户名</div>
              <div class="header-cell username-cell">账号</div>
              <div class="header-cell permissions-cell">权限</div>
            </div>
            <div 
              v-for="u in filtered" 
              :key="u.id" 
              class="user-row"
              :class="{ 'saving': saving === u.id }"
            >
              <div class="cell avatar-cell">
                <div class="user-avatar-small">
                  {{ u.name ? u.name[0].toUpperCase() : u.username[0].toUpperCase() }}
                </div>
              </div>
              
              <div class="cell name-cell">
                <div class="user-name">{{ u.name || '未设置姓名' }}</div>
              </div>
              
              <div class="cell username-cell">
                <div class="user-username">@{{ u.username }}</div>
              </div>

              <div class="cell permissions-cell">
                <label 
                  class="permission-label"
                  :class="{ active: u.roles.includes('admin') }"
                >
                  <input 
                    type="checkbox" 
                    :checked="u.roles.includes('admin')" 
                    @change="toggleRole(u, 'admin')"
                    :disabled="saving === u.id"
                  />
                  <span>管理员</span>
                </label>

                <label 
                  class="permission-label"
                  :class="{ active: u.roles.includes('member') }"
                >
                  <input 
                    type="checkbox" 
                    :checked="u.roles.includes('member')" 
                    @change="toggleRole(u, 'member')"
                    :disabled="saving === u.id"
                  />
                  <span>普通用户</span>
                </label>

                <!-- Delete Button -->
                <button 
                  class="delete-btn"
                  @click="openDeleteDialog(u)"
                  :disabled="deleting === u.id || saving === u.id"
                  title="删除用户"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                  </svg>
                </button>

                <!-- Saving Indicator -->
                <div v-if="saving === u.id" class="saving-indicator">
                  <div class="mini-spinner"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Delete Confirmation Dialog -->
      <div v-if="showDeleteDialog" class="modal-overlay" @click="closeDeleteDialog">
        <div class="modal-content" @click.stop>
          <div class="modal-header">
            <h3>确认删除用户</h3>
          </div>
          <div class="modal-body">
            <p>确定要删除用户 <strong>{{ showDeleteDialog.name || showDeleteDialog.username }}</strong> 吗？</p>
            <p class="warning-text">此操作不可撤销，该用户的所有数据和权限将被永久删除。</p>
          </div>
          <div class="modal-footer">
            <button 
              class="btn-secondary" 
              @click="closeDeleteDialog"
              :disabled="deleting === showDeleteDialog.id"
            >
              取消
            </button>
            <button 
              class="btn-danger" 
              @click="confirmDeleteUser"
              :disabled="deleting === showDeleteDialog.id"
            >
              {{ deleting === showDeleteDialog.id ? '删除中...' : '确认删除' }}
            </button>
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

/* User List */
.user-list {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
}

.list-header {
  display: grid;
  grid-template-columns: 60px 200px 200px 1fr;
  gap: 16px;
  padding: 12px 16px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
}

.header-cell {
  display: flex;
  align-items: center;
}

.user-row {
  display: grid;
  grid-template-columns: 60px 200px 200px 1fr;
  gap: 16px;
  padding: 12px 16px;
  border-bottom: 1px solid #f1f5f9;
  align-items: center;
  transition: background 0.2s;
  position: relative;
}

.user-row:hover {
  background: #f8fafc;
}

.user-row:last-child {
  border-bottom: none;
}

.user-row.saving {
  opacity: 0.7;
  pointer-events: none;
}

.cell {
  display: flex;
  align-items: center;
  min-width: 0;
}

.user-avatar-small {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
}

.user-name {
  font-weight: 600;
  font-size: 14px;
  color: #0f172a;
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

.permissions-cell {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.permission-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  cursor: pointer;
  font-size: 13px;
  color: #64748b;
  transition: all 0.2s;
  user-select: none;
}

.permission-label input {
  display: none;
}

.permission-label:hover {
  border-color: #d1d5db;
  background: #f1f5f9;
}

.permission-label.active {
  background: #eef2ff;
  border-color: #c7d2fe;
  color: #4f46e5;
}

.saving-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #6366f1;
  font-size: 12px;
}

.mini-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid #e2e8f0;
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* Delete Button */
.delete-btn {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  border: 1px solid #fecaca;
  background: #fef2f2;
  color: #dc2626;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.delete-btn:hover:not(:disabled) {
  background: #fee2e2;
  border-color: #fca5a5;
}

.delete-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  max-width: 400px;
  width: 90%;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
}

.modal-header {
  margin-bottom: 20px;
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
}

.modal-body {
  margin-bottom: 24px;
  color: #4b5563;
  line-height: 1.6;
}

.modal-body strong {
  color: #1f2937;
}

.warning-text {
  color: #dc2626;
  font-size: 13px;
  margin-top: 8px;
}

.modal-footer {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.btn-secondary {
  padding: 10px 20px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  background: #fff;
  color: #374151;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.btn-secondary:hover:not(:disabled) {
  background: #f9fafb;
}

.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-danger {
  padding: 10px 20px;
  border-radius: 8px;
  border: none;
  background: #dc2626;
  color: #fff;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.btn-danger:hover:not(:disabled) {
  background: #b91c1c;
}

.btn-danger:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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

  .list-header {
    display: none;
  }

  .user-row {
    grid-template-columns: 60px 1fr;
    grid-template-rows: auto auto;
    gap: 8px 12px;
  }

  .name-cell {
    grid-column: 2;
    grid-row: 1;
  }

  .username-cell {
    grid-column: 2;
    grid-row: 2;
  }

  .permissions-cell {
    grid-column: 1 / -1;
    justify-content: flex-start;
    padding-top: 8px;
    border-top: 1px solid #f1f5f9;
  }
}
</style>
