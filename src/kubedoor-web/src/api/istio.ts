import { http } from "@/utils/http";

type ResultTable = {
  success: boolean;
  data?: Array<any>;
  meta?: Array<any>;
  count: any;
};

/**
 * 获取VirtualService列表
 * @param k8s_cluster K8S集群
 * @param namespace 命名空间（可选）
 */
export const getVirtualServices = (k8s_cluster: string, namespace?: string) => {
  const params: Record<string, string> = { k8s_cluster };
  if (namespace) {
    params.namespace = namespace;
  }
  return http.request<ResultTable>("get", "/api/istio/vs", {
    params
  });
};

/**
 * 获取VirtualService详情
 * @param vs_id VirtualService ID
 */
export const getVirtualServiceDetail = (vs_id: number) => {
  return http.request<any>("get", "/api/istio/vs", {
    params: { vs_id }
  });
};

/**
 * 更新VirtualService的K8S集群
 * @param vs_id VirtualService ID
 * @param k8s_clusters K8S集群列表
 */
export const updateVirtualServiceClusters = (
  vs_id: number,
  k8s_clusters: string[]
) => {
  return http.request<any>("post", "/api/istio/vs/k8s", {
    data: {
      vs_id,
      k8s_clusters
    }
  });
};

/**
 * 更新VirtualService
 * @param vs_id VirtualService ID
 * @param data VirtualService数据
 */
export const updateVirtualService = (vs_id: number, data: any) => {
  return http.request<any>("put", "/api/istio/vs", {
    params: { vs_id },
    data
  });
};

/**
 * 获取HTTP路由列表
 * @param vs_id VirtualService ID
 */
export const getHttpRoutes = (vs_id: number) => {
  return http.request<ResultTable>("get", "/api/istio/httproute", {
    params: { vs_id }
  });
};

/**
 * 创建HTTP路由
 * @param vs_id VirtualService ID
 * @param data 路由数据
 */
export const createHttpRoute = (vs_id: number, data: any) => {
  return http.request<any>("post", "/api/istio/httproute", {
    params: { vs_id },
    data
  });
};

/**
 * 更新HTTP路由
 * @param route_id 路由ID
 * @param vs_id VirtualService ID
 * @param data 路由数据
 */
export const updateHttpRoute = (route_id: number, vs_id: number, data: any) => {
  return http.request<any>("put", "/api/istio/httproute", {
    params: { route_id, vs_id },
    data
  });
};

/**
 * 下发VirtualService到K8S集群
 * @param vs_id VirtualService ID
 * @param env K8S集群名称
 */
export const deployVirtualService = (vs_id: number, env: string) => {
  return http.request<any>("post", "/api/agent/istio/vs/apply", {
    params: { vs_id, env }
  });
};

/**
 * 获取服务的第一个端口号
 * @param env 集群名称
 * @param namespace 命名空间
 * @param service_name 服务名称
 */
export const getServiceFirstPort = (
  env: string,
  namespace: string,
  service_name: string
) => {
  return http.request<any>("get", "/api/agent/service/first-port", {
    params: { env, namespace, service_name }
  });
};

/**
 * 获取代理名称列表
 */
export const getAgentNames = () => {
  return http.request<ResultTable>("get", "/api/agent_names");
};

/**
 * 采集VirtualService路由
 * @param env K8S集群名称
 */
export const collectVirtualServiceRoutes = (env: string) => {
  return http.request<any>("get", "/api/agent/istio/vs", {
    params: { env }
  });
};
