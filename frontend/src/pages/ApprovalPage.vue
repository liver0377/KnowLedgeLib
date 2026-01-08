<script setup lang="ts">
import { ref, onMounted } from "vue";
import { apiFetch } from "@/api/http";

interface PendingUser {
  id: number;
  username: string;
  display_name: string;
  email: string | null;
  requested_dept_id: number | null;
  dept_name: string | null;
  dept_key: string | null;
  reason: string | null;
  created_at: string;
}

interface Department {
  id: number;
  dept_key: string;
  name: string;
}

const pendingUsers = ref<PendingUser[]>([]);
const departments = ref<Department[]>([]);
const loading = ref(false);
const error = ref("");
const successMessage = ref("");

// 当前对话框的临时值
const currentSelectedDept = ref<number | undefined>(undefined);
const currentComment = ref("");

// 当前操作（approve/reject）
const actionDialog = ref<{userId: number; action: "approve" | "reject"} | null>(null);
const actionLoading = ref(false);

onMounted(async () => {
  await loadPendingUsers();
  await loadDepartments();
});

async function loadPendingUsers() {
  loading.value = true;
  error.value = "";
  try {
    const data = await apiFetch<{items: PendingUser[]}>("/admin/pending-users");
    pendingUsers.value = data.items || [];
  } catch (e) {
    error.value = "Failed to load pending users";
    console.error(e);
  } finally {
    loading.value = false;
  }
}

async function loadDepartments() {
  try {
    const data = await apiFetch<{items: Department[]}>("/departments");
    departments.value = data.items || [];
  } catch (e) {
    console.error("Failed to load departments:", e);
  }
}

function openApproveDialog(userId: number, requestedDeptId: number | null) {
  currentSelectedDept.value = requestedDeptId || 0;
  currentComment.value = "";
  actionDialog.value = { userId, action: "approve" };
}

function openRejectDialog(userId: number) {
  currentSelectedDept.value = undefined;
  currentComment.value = "";
  actionDialog.value = { userId, action: "reject" };
}

function closeDialog() {
  actionDialog.value = null;
  currentSelectedDept.value = undefined;
  currentComment.value = "";
}

async function confirmAction() {
  if (!actionDialog.value) return;

  const { userId, action } = actionDialog.value;
  actionLoading.value = true;
  error.value = "";
  successMessage.value = "";

  try {
    const endpoint = action === "approve"
      ? `/admin/pending-users/${userId}/approve`
      : `/admin/pending-users/${userId}/reject`;

    const body = action === "approve"
      ? { dept_id: currentSelectedDept.value, comment: currentComment.value || undefined }
      : { comment: currentComment.value || undefined };

    await apiFetch(endpoint, {
      method: "POST",
      body: JSON.stringify(body),
    });

    successMessage.value = action === "approve" ? "User approved successfully" : "User rejected successfully";
    
    // 刷新列表
    await loadPendingUsers();
    
    // 关闭对话框
    closeDialog();
    
    // 3秒后清除成功消息
    setTimeout(() => {
      successMessage.value = "";
    }, 3000);
  } catch (e: any) {
    error.value = e?.message || `${action} failed`;
  } finally {
    actionLoading.value = false;
  }
}

function formatDate(dateString: string) {
  const date = new Date(dateString);
  return date.toLocaleString("zh-CN");
}
</script>

<template>
  <div style="padding: 20px; max-width: 1200px; margin: 0 auto;">
    <h1 style="margin: 0 0 20px;">User Approval</h1>

    <!-- 成功消息 -->
    <div v-if="successMessage" 
         style="background: #d1fae5; color: #065f46; padding: 12px; border-radius: 8px; margin-bottom: 16px;">
      {{ successMessage }}
    </div>

    <!-- 错误消息 -->
    <div v-if="error"
         style="background: #fee2e2; color: #991b1b; padding: 12px; border-radius: 8px; margin-bottom: 16px;">
      {{ error }}
      <button @click="error = ''" style="float: right; background: none; border: none; cursor: pointer; font-size: 16px;">&times;</button>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" style="text-align: center; padding: 40px;">
      Loading...
    </div>

    <!-- 空列表 -->
    <div v-else-if="pendingUsers.length === 0" 
         style="text-align: center; padding: 60px; color: #6b7280; background: #f9fafb; border-radius: 8px;">
      <div style="font-size: 48px; margin-bottom: 16px;">📭</div>
      <p style="margin: 0; font-size: 18px;">No pending user approvals</p>
    </div>

    <!-- 待审批用户列表 -->
    <div v-else>
      <div v-for="user in pendingUsers" :key="user.id"
           style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; margin-bottom: 16px;">
        
        <!-- 用户信息 -->
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px;">
          <div style="flex: 1;">
            <h3 style="margin: 0 0 8px;">{{ user.display_name }} ({{ user.username }})</h3>
            <div style="color: #6b7280; font-size: 14px; margin-bottom: 4px;">
              <span v-if="user.email">📧 {{ user.email }}</span>
            </div>
            <div style="color: #6b7280; font-size: 14px;">
              <span>📅 Applied at: {{ formatDate(user.created_at) }}</span>
            </div>
          </div>
        </div>

        <!-- 申请部门 -->
        <div style="background: #f3f4f6; padding: 12px; border-radius: 6px; margin-bottom: 12px;">
          <div style="font-weight: 600; margin-bottom: 4px;">
            Requested Department:
          </div>
          <div style="color: #374151;">
            {{ user.dept_name || 'Not specified' }}
          </div>
        </div>

        <!-- 申请理由 -->
        <div v-if="user.reason" style="background: #fef3c7; padding: 12px; border-radius: 6px; margin-bottom: 12px;">
          <div style="font-weight: 600; margin-bottom: 4px;">
            Reason:
          </div>
          <div style="color: #92400e;">
            {{ user.reason }}
          </div>
        </div>

        <!-- 操作按钮 -->
        <div style="display: flex; gap: 12px; margin-top: 16px;">
          <button
            @click="openApproveDialog(user.id, user.requested_dept_id)"
            style="flex: 1; padding: 12px; border-radius: 6px; border: none; background: #10b981; color: white; cursor: pointer; font-size: 14px;"
          >
            ✅ Approve
          </button>
          <button
            @click="openRejectDialog(user.id)"
            style="flex: 1; padding: 12px; border-radius: 6px; border: none; background: #ef4444; color: white; cursor: pointer; font-size: 14px;"
          >
            ❌ Reject
          </button>
        </div>
      </div>
    </div>

    <!-- 审批对话框 -->
    <div v-if="actionDialog" 
         style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000;">
      <div style="background: white; border-radius: 12px; padding: 24px; max-width: 500px; width: 90%;">
        <h2 style="margin: 0 0 20px;">
          {{ actionDialog.action === 'approve' ? 'Approve User' : 'Reject User' }}
        </h2>

        <!-- 批准时的部门选择 -->
        <div v-if="actionDialog.action === 'approve'" style="margin-bottom: 16px;">
          <label style="display: block; font-weight: 600; margin-bottom: 8px;">
            Assign Department:
          </label>
          <select
            v-model="currentSelectedDept"
            style="width: 100%; padding: 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 14px;"
          >
            <option v-for="dept in departments" :key="dept.id" :value="dept.id">
              {{ dept.name }}
            </option>
          </select>
        </div>

        <!-- 审批意见 -->
        <div style="margin-bottom: 20px;">
          <label style="display: block; font-weight: 600; margin-bottom: 8px;">
            {{ actionDialog.action === 'approve' ? 'Approval Comment (Optional)' : 'Rejection Reason (Optional)' }}
          </label>
          <textarea
            v-model="currentComment"
            :placeholder="actionDialog.action === 'approve' ? 'Enter approval comment...' : 'Enter rejection reason...'"
            rows="3"
            style="width: 100%; padding: 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 14px; resize: vertical;"
          ></textarea>
        </div>

        <!-- 对话框按钮 -->
        <div style="display: flex; gap: 12px; justify-content: flex-end;">
          <button
            @click="closeDialog"
            :disabled="actionLoading"
            style="padding: 10px 24px; border-radius: 6px; border: 1px solid #d1d5db; background: white; cursor: pointer; font-size: 14px;"
          >
            Cancel
          </button>
          <button
            @click="confirmAction"
            :disabled="actionLoading || (actionDialog.action === 'approve' && !currentSelectedDept)"
            :style="{
              padding: '10px 24px',
              borderRadius: '6px',
              border: 'none',
              background: actionDialog.action === 'approve' ? '#10b981' : '#ef4444',
              color: 'white',
              cursor: actionLoading ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              opacity: (actionDialog.action === 'approve' && !currentSelectedDept) ? '0.5' : '1'
            }"
          >
            {{ actionLoading ? 'Processing...' : (actionDialog.action === 'approve' ? 'Approve' : 'Reject') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
