import logging
from datetime import datetime

from aiohttp import web
from kubernetes_asyncio import client
from kubernetes_asyncio.client.exceptions import ApiException

# 配置日志
logger = logging.getLogger(__name__)


async def get_service_list(core_v1, request):
    """
    GET接口：查询Service列表
    参数：
    - env: 集群名称
    - namespace: 命名空间
    - core_v1: Kubernetes CoreV1Api客户端
    返回：集群名、命名空间、Service名称、type、clusterip、ports、selector、External IPs、externalTrafficPolicy、internalTrafficPolicy、创建时间
    """
    try:
        env = request.query.get('env')
        namespace = request.query.get('namespace')

        if not env or not namespace:
            return web.json_response({"error": "缺少必要参数: env 和 namespace"}, status=400)

        # 查询Service列表
        service_list = await core_v1.list_namespaced_service(namespace=namespace)

        result = []
        for svc in service_list.items:
            # 处理 clusterip:port 格式
            cluster_ip = svc.spec.cluster_ip or ""
            ports_info = []
            clusterip_ports = []

            if svc.spec.ports:
                for port in svc.spec.ports:
                    # ports格式: targetPort:nodePort
                    target_port = port.target_port if port.target_port else port.port
                    node_port = port.node_port if port.node_port else ""
                    port_info = f"{target_port}:{node_port}" if node_port else str(target_port)
                    ports_info.append(port_info)

                    # clusterip:port 格式
                    if cluster_ip and cluster_ip != "None":
                        clusterip_ports.append(f"{cluster_ip}:{port.port}")

            clusterip_str = ", ".join(clusterip_ports) if clusterip_ports else cluster_ip
            ports_str = ", ".join(ports_info)

            # 处理 Selector
            selector = svc.spec.selector or {}
            selector_str = ", ".join([f"{k}={v}" for k, v in selector.items()]) if selector else ""

            # 处理 External IPs
            external_ips = svc.spec.external_i_ps or []
            external_ips_str = ", ".join(external_ips) if external_ips else ""

            # 处理 Traffic Policies
            external_traffic_policy = svc.spec.external_traffic_policy or ""
            internal_traffic_policy = svc.spec.internal_traffic_policy or ""

            result.append(
                {
                    "env": env,
                    "namespace": namespace,
                    "name": svc.metadata.name,
                    "type": svc.spec.type or "",
                    "clusterip": clusterip_str,
                    "ports": ports_str,
                    "selector": selector_str,
                    "external_ips": external_ips_str,
                    "external_traffic_policy": external_traffic_policy,
                    "internal_traffic_policy": internal_traffic_policy,
                    "creation_timestamp": (
                        svc.metadata.creation_timestamp.isoformat() if svc.metadata.creation_timestamp else None
                    ),
                }
            )

        return web.json_response({"success": True, "data": result, "total": len(result)})

    except ApiException as e:
        logger.error(f"查询Service列表失败: {e}")
        return web.json_response({"error": f"Kubernetes API错误: {e.reason}"}, status=e.status)
    except Exception as e:
        logger.error(f"查询Service列表异常: {e}")
        return web.json_response({"error": f"服务器内部错误: {str(e)}"}, status=500)


async def get_service_content(core_v1, request):
    """
    GET接口：获取指定Service内容
    参数：
    - env: 集群名称
    - namespace: 命名空间
    - service_name: Service名称
    - core_v1: Kubernetes CoreV1Api客户端
    """
    try:
        env = request.query.get('env')
        namespace = request.query.get('namespace')
        service_name = request.query.get('service_name')

        if not all([env, namespace, service_name]):
            return web.json_response({"error": "缺少必要参数: env, namespace, service_name"}, status=400)

        # 获取指定Service
        service = await core_v1.read_namespaced_service(name=service_name, namespace=namespace)

        # 处理端口信息
        ports_detail = []
        if service.spec.ports:
            for port in service.spec.ports:
                port_detail = {
                    "name": port.name,
                    "port": port.port,
                    "target_port": port.target_port,
                    "protocol": port.protocol,
                    "node_port": port.node_port,
                }
                ports_detail.append(port_detail)

        result = {
            "env": env,
            "namespace": namespace,
            "name": service.metadata.name,
            "spec": {
                "type": service.spec.type,
                "cluster_ip": service.spec.cluster_ip,
                "cluster_i_ps": service.spec.cluster_i_ps or [],
                "external_i_ps": service.spec.external_i_ps or [],
                "ports": ports_detail,
                "selector": service.spec.selector or {},
                "session_affinity": service.spec.session_affinity,
                "external_traffic_policy": service.spec.external_traffic_policy,
                "internal_traffic_policy": service.spec.internal_traffic_policy,
                "load_balancer_ip": service.spec.load_balancer_ip,
                "load_balancer_source_ranges": service.spec.load_balancer_source_ranges or [],
                "external_name": service.spec.external_name,
            },
            "status": {
                "load_balancer": service.status.load_balancer.to_dict() if service.status.load_balancer else None
            },
            "metadata": {
                "creation_timestamp": (
                    service.metadata.creation_timestamp.isoformat() if service.metadata.creation_timestamp else None
                ),
                "resource_version": service.metadata.resource_version,
                "uid": service.metadata.uid,
                "labels": service.metadata.labels or {},
                "annotations": service.metadata.annotations or {},
            },
        }

        return web.json_response({"success": True, "data": result})

    except ApiException as e:
        logger.error(f"获取Service内容失败: {e}")
        if e.status == 404:
            return web.json_response(
                {"error": f"Service '{service_name}' 在命名空间 '{namespace}' 中不存在"}, status=404
            )
        return web.json_response({"error": f"Kubernetes API错误: {e.reason}"}, status=e.status)
    except Exception as e:
        logger.error(f"获取Service内容异常: {e}")
        return web.json_response({"error": f"服务器内部错误: {str(e)}"}, status=500)


async def update_service_content(core_v1, request):
    """
    POST接口：更新指定Service内容
    参数：
    - env: 集群名称
    - namespace: 命名空间
    - service_name: Service名称
    - service_data: Service的完整内容（JSON字符串）
    - core_v1: Kubernetes CoreV1Api客户端
    """
    try:
        import json

        env = request.query.get('env')
        namespace = request.query.get('namespace')
        service_name = request.query.get('service_name')
        service_data_str = request.query.get('service_data', '{}')

        # 解析JSON字符串
        try:
            service_data = json.loads(service_data_str)
        except json.JSONDecodeError:
            return web.json_response({"error": "service_data 参数必须是有效的JSON字符串"}, status=400)

        if not all([env, namespace, service_name]):
            return web.json_response({"error": "缺少必要参数: env, namespace, service_name"}, status=400)

        # 先获取现有的Service以保留metadata
        try:
            existing_svc = await core_v1.read_namespaced_service(name=service_name, namespace=namespace)
        except ApiException as e:
            if e.status == 404:
                return web.json_response(
                    {"error": f"Service '{service_name}' 在命名空间 '{namespace}' 中不存在"}, status=404
                )
            raise

        # 构建端口列表
        ports = []
        if service_data.get('spec', {}).get('ports'):
            for port_data in service_data['spec']['ports']:
                port = client.V1ServicePort(
                    name=port_data.get('name'),
                    port=port_data.get('port'),
                    target_port=port_data.get('target_port'),
                    protocol=port_data.get('protocol', 'TCP'),
                    node_port=port_data.get('node_port'),
                )
                ports.append(port)

        # 构建更新的Service对象
        updated_service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(
                name=service_name,
                namespace=namespace,
                labels=existing_svc.metadata.labels,
                annotations=existing_svc.metadata.annotations,
            ),
            spec=client.V1ServiceSpec(
                type=service_data.get('spec', {}).get('type', existing_svc.spec.type),
                cluster_ip=service_data.get('spec', {}).get('cluster_ip', existing_svc.spec.cluster_ip),
                external_i_ps=service_data.get('spec', {}).get('external_i_ps', existing_svc.spec.external_i_ps),
                ports=ports if ports else existing_svc.spec.ports,
                selector=service_data.get('spec', {}).get('selector', existing_svc.spec.selector),
                session_affinity=service_data.get('spec', {}).get(
                    'session_affinity', existing_svc.spec.session_affinity
                ),
                external_traffic_policy=service_data.get('spec', {}).get(
                    'external_traffic_policy', existing_svc.spec.external_traffic_policy
                ),
                internal_traffic_policy=service_data.get('spec', {}).get(
                    'internal_traffic_policy', existing_svc.spec.internal_traffic_policy
                ),
                load_balancer_ip=service_data.get('spec', {}).get(
                    'load_balancer_ip', existing_svc.spec.load_balancer_ip
                ),
                load_balancer_source_ranges=service_data.get('spec', {}).get(
                    'load_balancer_source_ranges', existing_svc.spec.load_balancer_source_ranges
                ),
                external_name=service_data.get('spec', {}).get('external_name', existing_svc.spec.external_name),
            ),
        )

        # 更新Service
        result_svc = await core_v1.replace_namespaced_service(
            name=service_name, namespace=namespace, body=updated_service
        )

        result = {
            "success": True,
            "message": f"Service '{service_name}' 更新成功",
            "data": {
                "env": env,
                "namespace": namespace,
                "name": result_svc.metadata.name,
                "resource_version": result_svc.metadata.resource_version,
                "updated_timestamp": datetime.now().isoformat(),
            },
        }

        logger.info(f"Service '{service_name}' 在命名空间 '{namespace}' 中更新成功")
        return web.json_response(result)

    except ApiException as e:
        logger.error(f"更新Service失败: {e}")
        return web.json_response({"error": f"Kubernetes API错误: {e.reason}"}, status=e.status)
    except Exception as e:
        logger.error(f"更新Service异常: {e}")
        return web.json_response({"error": f"服务器内部错误: {str(e)}"}, status=500)


async def get_service_endpoints(core_v1, request):
    """
    GET接口：获取指定Service的Endpoints信息
    参数：
    - env: 集群名称
    - namespace: 命名空间
    - service_name: Service名称
    - core_v1: Kubernetes CoreV1Api客户端
    返回：Endpoint的namespace、pod name、pod ip、nodeName、以及ports信息
    """
    try:
        env = request.query.get('env')
        namespace = request.query.get('namespace')
        service_name = request.query.get('service_name')

        if not all([env, namespace, service_name]):
            return web.json_response({"error": "缺少必要参数: env, namespace, service_name"}, status=400)

        # 获取指定Service的Endpoints
        try:
            endpoints = await core_v1.read_namespaced_endpoints(name=service_name, namespace=namespace)
        except ApiException as e:
            if e.status == 404:
                return web.json_response(
                    {"error": f"Service '{service_name}' 的 Endpoints 在命名空间 '{namespace}' 中不存在"}, status=404
                )
            raise

        result = {"env": env, "namespace": namespace, "service_name": service_name, "subsets": []}

        # 处理 subsets 信息
        if endpoints.subsets:
            for subset in endpoints.subsets:
                subset_info = {"addresses": [], "ports": []}

                # 处理 addresses 信息
                if subset.addresses:
                    for address in subset.addresses:
                        address_info = {
                            "ip": address.ip,
                            "nodeName": address.node_name,
                            "pod_name": None,
                            "pod_namespace": None,
                        }

                        # 处理 targetRef 信息（Pod 引用）
                        if address.target_ref:
                            if address.target_ref.kind == "Pod":
                                address_info["pod_name"] = address.target_ref.name
                                address_info["pod_namespace"] = address.target_ref.namespace

                        subset_info["addresses"].append(address_info)

                # 处理 ports 信息
                if subset.ports:
                    for port in subset.ports:
                        port_info = {"name": port.name, "port": port.port, "protocol": port.protocol}
                        subset_info["ports"].append(port_info)

                result["subsets"].append(subset_info)

        return web.json_response({"success": True, "data": result})

    except ApiException as e:
        logger.error(f"获取Service Endpoints失败: {e}")
        return web.json_response({"error": f"Kubernetes API错误: {e.reason}"}, status=e.status)
    except Exception as e:
        logger.error(f"获取Service Endpoints异常: {e}")
        return web.json_response({"error": f"服务器内部错误: {str(e)}"}, status=500)


async def get_service_first_port(core_v1, request):
    """
    GET接口：获取指定Service的第一个端口号
    参数：
    - env: 集群名称
    - namespace: 命名空间
    - service_name: Service名称
    - core_v1: Kubernetes CoreV1Api客户端
    返回：Service的spec.ports第一个元素的port值
    """
    try:
        namespace = request.query.get('namespace')
        service_name = request.query.get('service_name')

        # 获取指定Service
        try:
            service = await core_v1.read_namespaced_service(name=service_name, namespace=namespace)
        except ApiException as e:
            if e.status == 404:
                return web.json_response(
                    {"error": f"Service '{service_name}' 在命名空间 '{namespace}' 中不存在"}, status=404
                )
            raise

        # 获取第一个端口的port值
        first_port = service.spec.ports[0].port
        result = {"first_port": first_port}
        return web.json_response({"success": True, "data": result})

    except ApiException as e:
        logger.error(f"获取Service第一个端口失败: {e}")
        return web.json_response({"error": f"Kubernetes API错误: {e.reason}"}, status=e.status)
    except Exception as e:
        logger.error(f"获取Service第一个端口异常: {e}")
        return web.json_response({"error": f"服务器内部错误: {str(e)}"}, status=500)
