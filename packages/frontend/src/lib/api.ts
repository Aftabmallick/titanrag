export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  tenant_id: string;
}

export interface Workspace {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  is_archived: boolean;
  created_at: string;
}

export interface DocumentRecord {
  id: string;
  tenant_id: string;
  workspace_id: string;
  title: string;
  source_type: string;
  storage_path: string;
  content_hash: string;
  mime_type: string;
  file_size_bytes: number;
  status: string;
  doc_type: string;
  folder: string | null;
  tags: string[];
  is_stale: boolean;
  is_shared: boolean;
  created_at: string;
  updated_at: string;
}

export interface IngestionPreviewChunk {
  index: number;
  chunk_type: "PARENT" | "CHILD";
  token_count: number;
  section_heading: string | null;
  context_prefix: string | null;
  content: string;
}

export interface IngestionPreviewResponse {
  filename: string;
  total_parent_chunks: number;
  total_child_chunks: number;
  sample_chunks: IngestionPreviewChunk[];
}

export interface ApiKeyRecord {
  id: string;
  name: string;
  key_prefix: string;
  role: string;
  expires_at: string | null;
  created_at: string;
  last_used_at: string | null;
}

export interface DLQTaskRecord {
  id: string;
  document_id: string | null;
  task_type: string;
  status: string;
  error_message: string | null;
  retry_count: number;
  created_at: string;
  updated_at: string;
}

export interface HealthStatus {
  status: string;
  dependencies: {
    postgres: { status: string; latency_ms: number; error: string | null };
    redis: { status: string; latency_ms: number; error: string | null };
    qdrant: { status: string; latency_ms: number; error: string | null };
    minio: { status: string; latency_ms: number; error: string | null };
  };
}

class ApiClient {
  private getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("titan_token");
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(endpoint, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      if (typeof window !== "undefined") {
        localStorage.removeItem("titan_token");
        window.dispatchEvent(new Event("titan:unauthorized"));
      }
      throw new Error("Session expired or unauthorized. Please log in.");
    }

    if (!response.ok) {
      let errMsg = `Request failed (${response.status})`;
      try {
        const errJson = await response.json();
        errMsg = errJson.error?.message || errJson.detail || errMsg;
      } catch {
        // use default message
      }
      throw new Error(errMsg);
    }

    if (response.status === 204) {
      return {} as T;
    }

    return response.json();
  }

  // Auth
  async login(email: string, password: string): Promise<{ access_token: string }> {
    return this.request("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  }

  async register(data: { email: string; password: string; full_name: string; tenant_name: string }): Promise<{ access_token: string }> {
    return this.request("/api/v1/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
  }

  async getMe(): Promise<User> {
    return this.request("/api/v1/auth/me");
  }

  // Workspaces
  async listWorkspaces(): Promise<Workspace[]> {
    return this.request("/api/v1/workspaces");
  }

  async createWorkspace(name: string, description?: string): Promise<Workspace> {
    return this.request("/api/v1/workspaces", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description }),
    });
  }

  // Documents
  async listDocuments(
    workspaceId: string,
    params: { page?: number; limit?: number; folder?: string; search?: string } = {}
  ): Promise<{ items: DocumentRecord[]; total: number; page: number; limit: number }> {
    const q = new URLSearchParams();
    if (params.page) q.append("page", params.page.toString());
    if (params.limit) q.append("limit", params.limit.toString());
    if (params.folder && params.folder !== "ALL") q.append("folder", params.folder);
    if (params.search) q.append("search", params.search);

    const queryStr = q.toString() ? `?${q.toString()}` : "";
    return this.request(`/api/v1/workspaces/${workspaceId}/documents${queryStr}`);
  }

  async uploadDocument(workspaceId: string, formData: FormData): Promise<{ document: DocumentRecord; task_id: string }> {
    return this.request(`/api/v1/workspaces/${workspaceId}/documents`, {
      method: "POST",
      body: formData,
    });
  }

  async previewDocument(workspaceId: string, formData: FormData): Promise<IngestionPreviewResponse> {
    return this.request(`/api/v1/workspaces/${workspaceId}/documents/preview`, {
      method: "POST",
      body: formData,
    });
  }

  async reindexDocument(workspaceId: string, documentId: string): Promise<{ document_id: string; task_id: string }> {
    return this.request(`/api/v1/workspaces/${workspaceId}/documents/${documentId}/reindex`, {
      method: "POST",
    });
  }

  async deleteDocument(workspaceId: string, documentId: string): Promise<{ status: string }> {
    return this.request(`/api/v1/workspaces/${workspaceId}/documents/${documentId}`, {
      method: "DELETE",
    });
  }

  async getDocument(workspaceId: string, documentId: string): Promise<DocumentRecord> {
    return this.request(`/api/v1/workspaces/${workspaceId}/documents/${documentId}`);
  }

  // API Keys
  async listApiKeys(): Promise<ApiKeyRecord[]> {
    return this.request("/api/v1/api-keys");
  }

  async createApiKey(name: string, role: string, expires_in_days?: number): Promise<{ api_key: string; key_record: ApiKeyRecord }> {
    return this.request("/api/v1/api-keys", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, role, expires_in_days }),
    });
  }

  async revokeApiKey(keyId: string): Promise<void> {
    return this.request(`/api/v1/api-keys/${keyId}`, {
      method: "DELETE",
    });
  }

  // DLQ Tasks
  async listDLQTasks(): Promise<{ items: DLQTaskRecord[]; total: number }> {
    return this.request("/api/v1/admin/dlq");
  }

  async retryDLQTask(taskId: string): Promise<{ status: string; task_id: string }> {
    return this.request(`/api/v1/admin/dlq/${taskId}/retry`, {
      method: "POST",
    });
  }

  // Health
  async getHealthReady(): Promise<HealthStatus> {
    try {
      const token = this.getToken();
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch("/api/v1/health/ready", { headers });
      return await res.json();
    } catch {
      return {
        status: "unknown",
        dependencies: {
          postgres: { status: "unknown", latency_ms: 0, error: null },
          redis: { status: "unknown", latency_ms: 0, error: null },
          qdrant: { status: "unknown", latency_ms: 0, error: null },
          minio: { status: "down", latency_ms: 0, error: "Connection error" },
        },
      };
    }
  }
}

export const api = new ApiClient();
