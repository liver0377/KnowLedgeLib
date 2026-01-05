// src/api/http.ts
export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const isFormData = options.body instanceof FormData;
  const headers = isFormData
    ? options.headers
    : { "Content-Type": "application/json", ...(options.headers || {}) };

  const res = await fetch(path, {
    ...options,
    headers,
    credentials: "include",
    body: isFormData ? options.body : options.body ?? undefined,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${text}`);
  }

  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/json")) {
    return (await res.text()) as any;
  }
  return (await res.json()) as T;
}


