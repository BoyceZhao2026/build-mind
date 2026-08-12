export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function readError(response: Response) {
  try {
    const payload = await response.json();
    return payload.detail ?? "请求失败";
  } catch {
    return `请求失败（${response.status}）`;
  }
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function upload<T>(path: string, field: string, file: Blob, filename: string): Promise<T> {
  const form = new FormData();
  form.append(field, file, filename);
  const response = await fetch(`${API_BASE}${path}`, { method: "POST", body: form });
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}
