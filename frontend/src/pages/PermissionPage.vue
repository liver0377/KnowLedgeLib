<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { apiFetch } from "@/api/http";
import { useAuthStore } from "@/stores/auth";

type UserRow = { 
  id: string; 
  name: string; 
  username: string; 
  roles: string[];
  departments: Array<{
    dept_key: string;
    dept_name: string;
    can_write: number;
    dept_role: string;
  }>;
};

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

// 检查用户是否是某个部门的管理员
function isDeptAdmin(user: UserRow, deptKey: string): boolean {
  const dept = user.departments?.find(d => d.dept_key === deptKey);
  return dept?.dept_role === "editor" && dept?.can_write === 1;
}

async function setDepartmentAdmin(user: UserRow, deptKey: string) {
  saving.value = user.id;
  try {
    // 设置用户为指定部门的管理员
    await apiFetch(`/admin/users/${user.id}/departments/${deptKey}/set_admin`, {
      method: "POST",
    });
    await loadUsers();
  } catch (error: any) {
    alert(error?.message || "设置部门管理员失败");
  } finally {
    saving.value = null;
  }
}

async function unsetDepartmentAdmin(user: UserRow, deptKey: string) {
  saving.value = user.id;
  try {
    // 取消用户为指定部门的管理员
    await apiFetch(`/admin/users/${user.id}/departments/${deptKey}/unset_admin`, {
      method: "POST",
    });
    await loadUsers();
  } catch (error: any) {
    alert(error?.message || "取消部门管理员失败");
  } finally {
    saving.value = null;
  }
}

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
              <div class="header-cell permissions-cell">所属部门及权限</div>
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

              <!-- 部门权限 -->
              <div class="cell dept-permissions-cell">
                <div v-if="u.departments && u.departments.length > 0" class="dept-list">
                  <div v-for="dept in u.departments" :key="dept.dept_key" class="dept-item">
                    <span class="dept-name">{{ dept.dept_name || dept.dept_key }}</span>
                    <span class="dept-role" :class="{ 'editor': dept.dept_role === 'editor' || u.roles.includes('admin') }">
                      {{ dept.dept_role === 'editor' || u.roles.includes('admin') ? '管理员' : '只读' }}
                    </span>
                    <!-- 系统管理员不显示权限设置按钮 -->
                    <template v-if="!u.roles.includes('admin')">
                      <button 
                        v-if="isDeptAdmin(u, dept.dept_key)"
                        class="dept-action-btn unset-btn"
                        @click="unsetDepartmentAdmin(u, dept.dept_key)"
                        :disabled="saving === u.id"
                        title="取消管理员"
                      >
                        ✕
                      </button>
                      <button 
                        v-else
                        class="dept-action-btn set-btn"
                        @click="setDepartmentAdmin(u, dept.dept_key)"
                        :disabled="saving === u.id"
                        title="设置为管理员"
                      >
                        设置成管理员
                      </button>
                    </template>
                  </div>
                </div>
                <div v-else class="no-dept">未分配部门</div>
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

/* Department Permissions */
.dept-permissions-cell {
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

.dept-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}

.dept-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.dept-name {
  font-size: 13px;
  font-weight: 500;
  color: #334155;
  flex: 1;
}

.dept-role {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  background: #e2e8f0;
  color: #64748b;
  font-weight: 500;
}

.dept-role.editor {
  background: #dcfce7;
  color: #166534;
}

.dept-action-btn {
  padding: 4px 10px;
  border-radius: 4px;
  border: none;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.dept-action-btn.set-btn {
  background: #e0e7ff;
  color: #4338ca;
}

.dept-action-btn.set-btn:hover:not(:disabled) {
  background: #c7d2fe;
}

.dept-action-btn.unset-btn {
  background: #fee2e2;
  color: #dc2626;
}

.dept-action-btn.unset-btn:hover:not(:disabled) {
  background: #fecaca;
}

.dept-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.no-dept {
  font-size: 13px;
  color: #94a3b8;
  font-style: italic;
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

  .dept-permissions-cell {
    grid-column: 1 / -1;
    justify-content: flex-start;
    padding-top: 8px;
    border-top: 1px solid #f1f5f9;
  }
}
</style>
