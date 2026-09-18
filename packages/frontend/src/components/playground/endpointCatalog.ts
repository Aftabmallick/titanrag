export interface EndpointParam {
  name: string;
  type: "string" | "number" | "boolean";
  required: boolean;
  description: string;
  default?: any;
}

export interface EndpointSpec {
  id: string;
  category: "Chat & Search" | "Documents" | "Workspaces" | "Settings" | "Plugins" | "FinOps";
  name: string;
  method: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
  path: string;
  description: string;
  pathParams?: EndpointParam[];
  queryParams?: EndpointParam[];
  defaultBody?: any;
}

export const ENDPOINT_CATALOG: EndpointSpec[] = [
  {
    id: "chat-query",
    category: "Chat & Search",
    name: "Chat Query (Synchronous)",
    method: "POST",
    path: "/api/v1/workspaces/{workspace_id}/chat",
    description: "Submit a prompt to the RAG pipeline and receive grounded answer with citations.",
    pathParams: [
      { name: "workspace_id", type: "string", required: true, description: "Workspace UUID" }
    ],
    defaultBody: {
      query: "What are the key findings in the latest quarterly report?",
      grounding_mode: "Balanced",
      session_id: null
    }
  },
  {
    id: "list-docs",
    category: "Documents",
    name: "List Documents",
    method: "GET",
    path: "/api/v1/workspaces/{workspace_id}/documents",
    description: "Retrieve all indexed documents, chunk counts, and status in the workspace.",
    pathParams: [
      { name: "workspace_id", type: "string", required: true, description: "Workspace UUID" }
    ]
  },
  {
    id: "list-workspaces",
    category: "Workspaces",
    name: "List Workspaces",
    method: "GET",
    path: "/api/v1/workspaces",
    description: "List all accessible workspaces for the current tenant."
  },
  {
    id: "create-workspace",
    category: "Workspaces",
    name: "Create Workspace",
    method: "POST",
    path: "/api/v1/workspaces",
    description: "Create a new isolated multi-tenant workspace.",
    defaultBody: {
      name: "Research & Development",
      description: "Technical specifications and whitepapers"
    }
  },
  {
    id: "get-settings",
    category: "Settings",
    name: "Get RAG Settings",
    method: "GET",
    path: "/api/v1/workspaces/{workspace_id}/settings",
    description: "Fetch active RAG retrieval weights, reranker configuration, and cache thresholds.",
    pathParams: [
      { name: "workspace_id", type: "string", required: true, description: "Workspace UUID" }
    ]
  },
  {
    id: "update-settings",
    category: "Settings",
    name: "Update RAG Settings",
    method: "PUT",
    path: "/api/v1/workspaces/{workspace_id}/settings",
    description: "Modify retrieval mode, alpha weights, and confidence thresholds.",
    pathParams: [
      { name: "workspace_id", type: "string", required: true, description: "Workspace UUID" }
    ],
    defaultBody: {
      retrieval_mode: "HYBRID",
      dense_weight: 0.75,
      sparse_weight: 0.25,
      top_k: 30,
      rerank_top_k: 5,
      score_threshold: 0.40,
      hyde_enabled: false,
      semantic_cache_enabled: true
    }
  },
  {
    id: "list-plugins",
    category: "Plugins",
    name: "List Plugins",
    method: "GET",
    path: "/api/v1/workspaces/{workspace_id}/plugins",
    description: "List registered webhook micro-hook extensions and their health status.",
    pathParams: [
      { name: "workspace_id", type: "string", required: true, description: "Workspace UUID" }
    ]
  },
  {
    id: "register-plugin",
    category: "Plugins",
    name: "Register Plugin",
    method: "POST",
    path: "/api/v1/workspaces/{workspace_id}/plugins",
    description: "Register an external webhook micro-hook with HMAC-SHA256 signing.",
    pathParams: [
      { name: "workspace_id", type: "string", required: true, description: "Workspace UUID" }
    ],
    defaultBody: {
      name: "Legal Contract Specialized Parser",
      endpoint_url: "https://my-webhook-service.corp.internal/webhook",
      hooks: ["ON_PARSE", "ON_POST_GENERATE"],
      timeout_ms: 2000,
      is_active: true
    }
  },
  {
    id: "finops-usage",
    category: "FinOps",
    name: "Get Compute Unit Usage",
    method: "GET",
    path: "/api/v1/workspaces/{workspace_id}/finops/usage",
    description: "Fetch real-time Compute Unit consumption and dollar spend breakdown.",
    pathParams: [
      { name: "workspace_id", type: "string", required: true, description: "Workspace UUID" }
    ]
  }
];
