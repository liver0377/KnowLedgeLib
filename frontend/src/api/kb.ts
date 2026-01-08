// src/api/kb.ts
import { apiFetch } from "./http";
import type { KBDoc, KBFilesResponse, UploadFileResponse } from "@/types";

// 获取知识库文件列表
export async function listKBFiles(params?: {
  q?: string;
  dept_key?: string;
  type?: string;
  cursor?: number;
  limit?: number;
}): Promise<KBFilesResponse> {
  const queryParams = new URLSearchParams();
  if (params?.q) queryParams.append("q", params.q);
  if (params?.dept_key) queryParams.append("dept_key", params.dept_key);
  if (params?.type) queryParams.append("type", params.type);
  if (params?.cursor !== undefined) queryParams.append("cursor", String(params.cursor));
  if (params?.limit !== undefined) queryParams.append("limit", String(params.limit));

  const url = `/kb/files${queryParams.toString() ? "?" + queryParams.toString() : ""}`;
  return apiFetch<KBFilesResponse>(url);
}

// 上传文件到指定部门
export async function uploadKBFile(
  deptKey: string,
  file: File
): Promise<UploadFileResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return apiFetch<UploadFileResponse>(
    `/kb/files/upload?dept_key=${encodeURIComponent(deptKey)}`,
    {
      method: "POST",
      body: formData,
    }
  );
}

// 获取文件详情
export async function getKBFileDetail(fileId: string): Promise<KBDoc> {
  return apiFetch<KBDoc>(`/kb/files/${fileId}`);
}

// 获取文件下载URL
export function getDownloadUrl(fileId: string): string {
  return `/kb/files/${fileId}/download`;
}

// 创建新部门
export async function createDepartment(deptKey: string, deptName: string): Promise<{
  ok: boolean;
  dept_id: number;
  dept_key: string;
  name: string;
  message: string;
}> {
  return apiFetch("/admin/departments", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      dept_key: deptKey,
      name: deptName,
    }),
  });
}

// 删除文件
export async function deleteFile(fileId: string): Promise<{
  ok: boolean;
  message: string;
}> {
  return apiFetch(`/kb/files/${fileId}`, {
    method: "DELETE",
  });
}
