import logging
from datetime import datetime

from aiohttp import web
from kubernetes_asyncio import client
from kubernetes_asyncio.client.exceptions import ApiException

# 配置日志
logger = logging.getLogger(__name__)


async def get_configmap_list(core_v1, request):
    """
    GET接口：查询ConfigMap列表
    参数：
    - env: 集群名称
    - namespace: 命名空间
    - core_v1: Kubernetes CoreV1Api客户端
    返回：集群名、命名空间、ConfigMap名称、data的keys、创建时间
    """
    try:
        env = request.query.get('env')
        namespace = request.query.get('namespace')

        if not env or not namespace:
            return web.json_response({"error": "缺少必要参数: env 和 namespace"}, status=400)

        # 查询ConfigMap列表
        configmap_list = await core_v1.list_namespaced_config_map(namespace=namespace)

        result = []
        for cm in configmap_list.items:
            data_keys = list(cm.data.keys()) if cm.data else []
            binary_data_keys = list(cm.binary_data.keys()) if cm.binary_data else []
            all_keys = data_keys + binary_data_keys

            result.append(
                {
                    "env": env,
                    "namespace": namespace,
                    "name": cm.metadata.name,
                    "data_keys": all_keys,
                    "creation_timestamp": (
                        cm.metadata.creation_timestamp.isoformat() if cm.metadata.creation_timestamp else None
                    ),
                }
            )

        return web.json_response({"success": True, "data": result, "total": len(result)})

    except ApiException as e:
        logger.error(f"查询ConfigMap列表失败: {e}")
        return web.json_response({"error": f"Kubernetes API错误: {e.reason}"}, status=e.status)
    except Exception as e:
        logger.error(f"查询ConfigMap列表异常: {e}")
        return web.json_response({"error": f"服务器内部错误: {str(e)}"}, status=500)


async def get_configmap_content(core_v1, request):
    """
    GET接口：获取指定ConfigMap内容
    参数：
    - env: 集群名称
    - namespace: 命名空间
    - configmap_name: ConfigMap名称
    - core_v1: Kubernetes CoreV1Api客户端
    """
    try:
        env = request.query.get('env')
        namespace = request.query.get('namespace')
        configmap_name = request.query.get('configmap_name')

        if not all([env, namespace, configmap_name]):
            return web.json_response({"error": "缺少必要参数: env, namespace, configmap_name"}, status=400)

        # 获取指定ConfigMap
        configmap = await core_v1.read_namespaced_config_map(name=configmap_name, namespace=namespace)

        result = {
            "env": env,
            "namespace": namespace,
            "name": configmap.metadata.name,
            "data": configmap.data or {},
            "binary_data": configmap.binary_data or {},
            "metadata": {
                "creation_timestamp": (
                    configmap.metadata.creation_timestamp.isoformat() if configmap.metadata.creation_timestamp else None
                ),
                "resource_version": configmap.metadata.resource_version,
                "uid": configmap.metadata.uid,
                "labels": configmap.metadata.labels or {},
                "annotations": configmap.metadata.annotations or {},
            },
            "immutable": configmap.immutable,
        }

        return web.json_response({"success": True, "data": result})

    except ApiException as e:
        logger.error(f"获取ConfigMap内容失败: {e}")
        if e.status == 404:
            return web.json_response(
                {"error": f"ConfigMap '{configmap_name}' 在命名空间 '{namespace}' 中不存在"}, status=404
            )
        return web.json_response({"error": f"Kubernetes API错误: {e.reason}"}, status=e.status)
    except Exception as e:
        logger.error(f"获取ConfigMap内容异常: {e}")
        return web.json_response({"error": f"服务器内部错误: {str(e)}"}, status=500)


async def update_configmap_content(core_v1, request):
    """
    POST接口：更新指定ConfigMap内容
    参数：
    - env: 集群名称
    - namespace: 命名空间
    - configmap_name: ConfigMap名称
    - configmap_data: ConfigMap的完整内容（JSON字符串）
    - core_v1: Kubernetes CoreV1Api客户端
    """
    try:
        import json
        env = request.query.get('env')
        namespace = request.query.get('namespace')
        configmap_name = request.query.get('configmap_name')
        configmap_data_str = request.query.get('configmap_data', '{}')
        
        # 解析JSON字符串
        try:
            configmap_data = json.loads(configmap_data_str)
        except json.JSONDecodeError:
            return web.json_response({"error": "configmap_data 参数必须是有效的JSON字符串"}, status=400)

        if not all([env, namespace, configmap_name]):
            return web.json_response({"error": "缺少必要参数: env, namespace, configmap_name"}, status=400)

        # 先获取现有的ConfigMap以保留metadata
        try:
            existing_cm = await core_v1.read_namespaced_config_map(name=configmap_name, namespace=namespace)
        except ApiException as e:
            if e.status == 404:
                return web.json_response(
                    {"error": f"ConfigMap '{configmap_name}' 在命名空间 '{namespace}' 中不存在"}, status=404
                )
            raise

        # 构建更新的ConfigMap对象
        updated_configmap = client.V1ConfigMap(
            api_version="v1",
            kind="ConfigMap",
            metadata=client.V1ObjectMeta(
                name=configmap_name,
                namespace=namespace,
                labels=existing_cm.metadata.labels,
                annotations=existing_cm.metadata.annotations,
            ),
            data=configmap_data.get('data', {}),
            binary_data=configmap_data.get('binary_data', {}),
            immutable=configmap_data.get('immutable', existing_cm.immutable),
        )

        # 更新ConfigMap
        result_cm = await core_v1.replace_namespaced_config_map(
            name=configmap_name, namespace=namespace, body=updated_configmap
        )

        result = {
            "success": True,
            "message": f"ConfigMap '{configmap_name}' 更新成功",
            "data": {
                "env": env,
                "namespace": namespace,
                "name": result_cm.metadata.name,
                "resource_version": result_cm.metadata.resource_version,
                "updated_timestamp": datetime.now().isoformat(),
            },
        }

        logger.info(f"ConfigMap '{configmap_name}' 在命名空间 '{namespace}' 中更新成功")
        return web.json_response(result)

    except ApiException as e:
        logger.error(f"更新ConfigMap失败: {e}")
        return web.json_response({"error": f"Kubernetes API错误: {e.reason}"}, status=e.status)
    except Exception as e:
        logger.error(f"更新ConfigMap异常: {e}")
        return web.json_response({"error": f"服务器内部错误: {str(e)}"}, status=500)
