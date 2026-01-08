<!-- FileManagerPage.vue -->
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import { listKBFiles, uploadKBFile, getDownloadUrl, createDepartment, deleteFile as deleteFileAPI } from "@/api/kb";
import type { KBDoc } from "@/types";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const auth = useAuthStore();

// 状态
const files = ref<KBDoc[]>([]);
const loading = ref(false);
const uploadDialogVisible = ref(false);
const newDeptDialogVisible = ref(false);
const selectedDeptForUpload = ref("");
const newDeptName = ref("");
const uploading = ref(false);
const searchQuery = ref("");
const selectedDept = ref<string | null>(null);
const newDeptError = ref("");

/** ===== Resizable Sidebar ===== */
const sidebarWidth = ref<number>(280);
const resizing = ref(false);

const MIN_SIDEBAR = 220;
const MAX_SIDEBAR = 520;

function startResize(e: MouseEvent) {
  resizing.value = true;
  document.body.style.cursor = "col-resize";
  document.body.style.userSelect = "none";
  e.preventDefault();
}

function onResizeMove(e: MouseEvent) {
  if (!resizing.value) return;
  const next = Math.min(MAX_SIDEBAR, Math.max(MIN_SIDEBAR, e.clientX));
  sidebarWidth.value = next;
}

function stopResize() {
  if (!resizing.value) return;
  resizing.value = false;
  document.body.style.cursor = "";
  document.body.style.userSelect = "";
}

// 系统管理员：拥有admin角色
const isAdmin = computed(() => auth.me?.roles?.includes("admin"));

// 部门管理员：用户所属的部门中至少有一个是editor角色且有写权限
const isDeptAdmin = computed(() => {
  const departments = auth.me?.departments || [];
  return departments.some((d: any) => d.dept_role === "editor" && d.can_write === 1);
});

// 用户有写权限的部门列表
const writableDepartments = computed(() => {
  const departments = auth.me?.departments || [];
  return departments
    .filter((d: any) => d.can_write === 1)
    .map((d: any) => d.dept_key);
});

// 用户可访问的部门列表（系统管理员可以访问所有部门）
const accessibleDepartments = computed(() => {
  if (isAdmin.value) return null; // null表示不限制
  
  const departments = auth.me?.departments || [];
  return departments.map((d: any) => d.dept_key);
});

// 判断用户对指定部门是否有写权限
function canWriteDept(deptKey: string): boolean {
  if (isAdmin.value) return true;
  return writableDepartments.value.includes(deptKey);
}

// 判断用户对指定部门是否可访问
function canAccessDept(deptKey: string): boolean {
  if (isAdmin.value) return true;
  return accessibleDepartments.value?.includes(deptKey) || false;
}

// 按部门分组文件
const groupedFiles = computed(() => {
  const groups: Record<string, KBDoc[]> = {};
  
  files.value.forEach(file => {
    // 只显示用户可访问的部门
    if (!canAccessDept(file.dept_key)) return;
    
    if (!groups[file.dept_key]) {
      groups[file.dept_key] = [];
    }
    groups[file.dept_key].push(file);
  });
  
  return groups;
});

// 获取所有部门列表
const departments = computed(() => {
  return Object.keys(groupedFiles.value).sort();
});

// 当前选中部门的文件
const currentDeptFiles = computed(() => {
  if (!selectedDept.value) return [];
  
  return groupedFiles.value[selectedDept.value]?.filter(file =>
    file.name.toLowerCase().includes(searchQuery.value.toLowerCase())
  ) || [];
});

// 文件大小格式化
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + " KB";
  return (bytes / (1024 * 1024)).toFixed(2) + " MB";
}

// 加载文件列表
async function loadFiles() {
  loading.value = true;
  try {
    const res = await listKBFiles();
    files.value = res.items || [];
  } catch (error: any) {
    console.error("加载文件失败:", error);
    alert("加载文件失败: " + error.message);
  } finally {
    loading.value = false;
  }
}

// 选择部门
function selectDept(deptKey: string) {
  selectedDept.value = deptKey;
}

// 显示上传对话框
function showUploadDialog(deptKey: string) {
  selectedDeptForUpload.value = deptKey;
  uploadDialogVisible.value = true;
}

// 处理文件上传
async function handleFileUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  
  if (!file) return;
  
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    alert("只能上传PDF文件");
    return;
  }
  
  uploading.value = true;
  try {
    await uploadKBFile(selectedDeptForUpload.value, file);
    alert("文件上传成功");
    uploadDialogVisible.value = false;
    await loadFiles();
  } catch (error: any) {
    console.error("上传失败:", error);
    alert("上传失败: " + error.message);
  } finally {
    uploading.value = false;
    input.value = "";
  }
}

// 显示新增部门对话框
function showNewDeptDialog() {
  newDeptName.value = "";
  newDeptError.value = "";
  newDeptDialogVisible.value = true;
}

// 创建新部门
async function createNewDept() {
  if (!newDeptName.value.trim()) {
    newDeptError.value = "部门名称不能为空";
    return;
  }
  
  // 部门名称只允许字母、数字、下划线、横杠
  const deptKey = newDeptName.value.trim().replace(/\s+/g, "_");
  
  if (!/^[a-zA-Z0-9_-]+$/.test(deptKey)) {
    newDeptError.value = "部门名称只能包含字母、数字、下划线和横杠";
    return;
  }
  
  if (departments.value.includes(deptKey)) {
    newDeptError.value = "该部门已存在";
    return;
  }
  
  // 调用API创建部门
  try {
    await createDepartment(deptKey, deptKey); // 使用deptKey作为name（可以后续改为让用户输入中文名称）
    
    alert("部门创建成功");
    newDeptDialogVisible.value = false;
    await loadFiles();
    
    // 自动选中新建的部门
    selectDept(deptKey);
  } catch (error: any) {
    console.error("创建部门失败:", error);
    newDeptError.value = "创建部门失败: " + (error.message || "未知错误");
  }
}

// 下载文件
function downloadFile(file: KBDoc) {
  const url = getDownloadUrl(file.file_id);
  window.open(url, "_blank");
}

// 删除文件
async function deleteFile(file: KBDoc) {
  if (!confirm(`确定要删除文件 "${file.name}" 吗？`)) return;
  
  try {
    await deleteFileAPI(file.file_id);
    alert("文件删除成功");
    await loadFiles();
  } catch (error: any) {
    console.error("删除文件失败:", error);
    alert("删除文件失败: " + (error.message || "未知错误"));
  }
}

// 返回聊天页面
function goBack() {
  router.push("/chat");
}

onMounted(() => {
  loadFiles();
  window.addEventListener("mousemove", onResizeMove);
  window.addEventListener("mouseup", stopResize);
});

onUnmounted(() => {
  window.removeEventListener("mousemove", onResizeMove);
  window.removeEventListener("mouseup", stopResize);
});
</script>

<template>
  <div class="file-manager">
    <!-- 顶部导航栏 -->
    <header class="header">
      <button class="back-btn" @click="goBack">← 返回</button>
      <h1 class="title">文件管理</h1>
      <div class="header-actions">
        <button v-if="isAdmin" class="btn btn-primary" @click="showNewDeptDialog">
          + 新增部门
        </button>
      </div>
    </header>

    <div class="content">
      <!-- 左侧部门列表 -->
      <aside class="dept-sidebar" :style="{ width: sidebarWidth + 'px' }">
        <div class="sidebar-resizer" @mousedown="startResize"></div>
        <h2 class="sidebar-title">部门列表</h2>
        <div class="dept-list">
          <div
            v-for="dept in departments"
            :key="dept"
            :class="['dept-item', { active: selectedDept === dept }]"
            @click="selectDept(dept)"
          >
            <span class="dept-name">{{ dept }}</span>
            <span class="file-count">{{ groupedFiles[dept]?.length || 0 }} 个文件</span>
          </div>
          <div v-if="departments.length === 0" class="empty-state">
            暂无部门
          </div>
        </div>
      </aside>

      <!-- 右侧文件列表 -->
      <main class="file-main">
        <div v-if="selectedDept" class="file-section">
          <div class="file-header">
            <h2 class="dept-title">{{ selectedDept }}</h2>
            <div class="file-actions">
              <button v-if="canWriteDept(selectedDept)" class="btn btn-primary" @click="showUploadDialog(selectedDept)">
                + 上传文件
              </button>
            </div>
          </div>
          
          <div class="search-bar">
            <input
              v-model="searchQuery"
              placeholder="搜索文件..."
              class="search-input"
            />
          </div>

          <div v-if="loading" class="loading">加载中...</div>
          
          <div v-else-if="currentDeptFiles.length === 0" class="empty-state">
            <p>该部门暂无文件</p>
            <p v-if="isAdmin">点击"上传文件"按钮添加PDF文件</p>
          </div>

          <div v-else class="file-list">
            <div class="list-header">
              <div class="header-cell"></div>
              <div class="header-cell">文件名</div>
              <div class="header-cell">大小</div>
              <div class="header-cell">更新时间</div>
              <div class="header-cell">操作</div>
            </div>
            <div
              v-for="file in currentDeptFiles"
              :key="file.file_id"
              class="file-row"
            >
              <div class="cell">
                <div class="file-icon">📄</div>
              </div>
              <div class="cell">
                <div class="file-name" :title="file.name">{{ file.name }}</div>
              </div>
              <div class="cell">
                <div class="file-meta">{{ formatFileSize(file.size_bytes || 0) }}</div>
              </div>
              <div class="cell">
                <div class="file-date">{{ file.updated_at ? new Date(file.updated_at).toLocaleDateString() : '-' }}</div>
              </div>
              <div class="cell file-buttons">
                <button class="btn-icon" @click="downloadFile(file)" title="下载">⬇️</button>
                <button
                  v-if="canWriteDept(file.dept_key)"
                  class="btn-icon btn-danger"
                  @click="deleteFile(file)"
                  title="删除"
                >🗑️</button>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="empty-state">
          <p>请从左侧选择一个部门查看文件</p>
          <p v-if="isAdmin">或点击"新增部门"创建新部门</p>
        </div>
      </main>
    </div>

    <!-- 上传文件对话框 -->
    <div v-if="uploadDialogVisible" class="modal-overlay" @click.self="uploadDialogVisible = false">
      <div class="modal">
        <h3 class="modal-title">上传文件到 {{ selectedDeptForUpload }}</h3>
        <div class="modal-content">
          <label class="upload-label">
            选择PDF文件
            <input
              type="file"
              accept="application/pdf"
              @change="handleFileUpload"
              :disabled="uploading"
            />
          </label>
        </div>
        <div class="modal-footer">
          <button class="btn" @click="uploadDialogVisible = false">取消</button>
        </div>
      </div>
    </div>

    <!-- 新增部门对话框 -->
    <div v-if="newDeptDialogVisible" class="modal-overlay" @click.self="newDeptDialogVisible = false">
      <div class="modal">
        <h3 class="modal-title">新增部门</h3>
        <div class="modal-content">
          <div class="form-group">
            <label>部门标识（英文）</label>
            <input
              v-model="newDeptName"
              placeholder="输入部门标识（仅限字母、数字、下划线和横杠）"
              class="input"
              @keyup.enter="createNewDept"
            />
            <div v-if="newDeptError" class="error-message">{{ newDeptError }}</div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn" @click="newDeptDialogVisible = false">取消</button>
          <button class="btn btn-primary" @click="createNewDept" :disabled="uploading">
            创建
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.file-manager {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f6f7fb;
  color: #0f172a;
}

/* Header */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
}

.back-btn {
  padding: 8px 16px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  font-size: 14px;
}

.back-btn:hover {
  background: #f8fafc;
}

.title {
  font-size: 20px;
  font-weight: 700;
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 8px;
}

/* Content Layout */
.content {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* Dept Sidebar */
.dept-sidebar {
  background: #fff;
  border-right: 1px solid #e2e8f0;
  padding: 12px;
  overflow-y: auto;
  position: relative;
  flex: 0 0 auto;
}

.sidebar-resizer {
  position: absolute;
  right: -3px;
  top: 0;
  width: 6px;
  height: 100%;
  cursor: col-resize;
  background: transparent;
}

.sidebar-resizer:hover {
  background: rgba(15, 23, 42, 0.06);
}

.sidebar-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 12px 0;
  color: #64748b;
}

.dept-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.dept-item {
  padding: 12px 16px;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
  transition: all 0.2s;
}

.dept-item:hover {
  background: #f8fafc;
}

.dept-item.active {
  background: #eef2ff;
  border: 1px solid #c7d2fe;
}

.dept-name {
  font-weight: 600;
  font-size: 14px;
}

.file-count {
  font-size: 12px;
  color: #64748b;
}

/* File Main */
.file-main {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

.file-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.dept-title {
  font-size: 24px;
  font-weight: 700;
  margin: 0;
}

.file-actions {
  display: flex;
  gap: 8px;
}

.search-bar {
  margin-bottom: 16px;
}

.search-input {
  width: 100%;
  max-width: 400px;
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  outline: none;
}

.search-input:focus {
  border-color: #6366f1;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
}

/* File List */
.file-list {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
}

.list-header {
  display: grid;
  grid-template-columns: 50px 1fr 120px 140px 100px;
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

.file-row {
  display: grid;
  grid-template-columns: 50px 1fr 120px 140px 100px;
  gap: 16px;
  padding: 12px 16px;
  border-bottom: 1px solid #f1f5f9;
  align-items: center;
  transition: background 0.2s;
}

.file-row:hover {
  background: #f8fafc;
}

.file-row:last-child {
  border-bottom: none;
}

.cell {
  display: flex;
  align-items: center;
  min-width: 0;
}

.file-icon {
  font-size: 24px;
}

.file-name {
  font-weight: 600;
  font-size: 14px;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-meta {
  font-size: 13px;
  color: #64748b;
}

.file-date {
  font-size: 13px;
  color: #64748b;
}

.file-buttons {
  display: flex;
  gap: 8px;
}

.btn-icon {
  padding: 8px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
}

.btn-icon:hover {
  background: #f8fafc;
}

.btn-danger:hover {
  background: #fee2e2;
  border-color: #fecaca;
}

/* Buttons */
.btn {
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  background: #fff;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.btn:hover {
  background: #f8fafc;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: #6366f1;
  color: #fff;
  border: none;
}

.btn-primary:hover {
  background: #5558e3;
}

.btn-primary:disabled {
  background: #a5a6f6;
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

.modal {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  min-width: 400px;
  max-width: 500px;
}

.modal-title {
  font-size: 18px;
  font-weight: 700;
  margin: 0 0 16px 0;
}

.modal-content {
  margin-bottom: 20px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

/* Form */
.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 500;
}

.input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  outline: none;
}

.input:focus {
  border-color: #6366f1;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
}

.upload-label {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 14px;
}

.upload-label input {
  padding: 8px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
}

.error-message {
  color: #dc2626;
  font-size: 12px;
  margin-top: 4px;
}

/* States */
.loading {
  text-align: center;
  padding: 40px;
  color: #64748b;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: #64748b;
}

.empty-state p {
  margin: 4px 0;
}
</style>
