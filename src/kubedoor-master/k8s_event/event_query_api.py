#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
K8S事件查询API模块
提供K8S事件的高级查询接口
"""

import asyncio
from datetime import datetime
from aiohttp import web
from loguru import logger
from .clickhouse_client import get_clickhouse_client


def serialize_datetime_objects(data):
    """将数据中的datetime对象转换为字符串格式"""
    if isinstance(data, list):
        return [serialize_datetime_objects(item) for item in data]
    elif isinstance(data, tuple):
        return tuple(serialize_datetime_objects(item) for item in data)
    elif isinstance(data, dict):
        return {key: serialize_datetime_objects(value) for key, value in data.items()}
    elif isinstance(data, datetime):
        return data.strftime('%Y-%m-%d %H:%M:%S')
    else:
        return data


async def get_k8s_events_menu_options(request):
    """获取K8S事件查询的菜单选项"""
    try:
        # 获取查询参数
        k8s = request.query.get('k8s')
        start_time_str = request.query.get('start_time')
        end_time_str = request.query.get('end_time')
        namespace = request.query.get('namespace')  # 可选参数

        # 验证必填参数
        if not all([k8s, start_time_str, end_time_str]):
            return web.json_response({"code": 400, "message": "缺少必填参数: k8s, start_time, end_time"})

        # 获取ClickHouse客户端
        clickhouse_client = get_clickhouse_client()

        # 查询各字段的唯一值 - 并发执行
        menu_fields = ['namespace', 'kind', 'name', 'reason', 'reportingComponent', 'reportingInstance']

        async def query_field_options(field):
            """异步查询单个字段的选项"""
            try:
                # 构建WHERE条件（移除IS NOT NULL条件以包含空值）
                where_conditions = ["k8s = %s", "lastTimestamp >= %s", "lastTimestamp <= %s"]
                params = [k8s, f'{start_time_str} 00:00:00', f'{end_time_str} 23:59:59']

                # 如果传入了namespace参数，根据值添加相应的过滤条件
                if namespace and field != 'namespace':
                    if namespace == "[全部]":
                        # [全部]表示不添加namespace过滤条件，查询所有namespace
                        pass
                    elif namespace == "[空值]":
                        # [空值]表示查询namespace为空的记录
                        where_conditions.append("(namespace IS NULL OR namespace = '')")
                    else:
                        # 具体的namespace值
                        where_conditions.append("namespace = %s")
                        params.append(namespace)

                where_clause = " AND ".join(where_conditions)

                sql = f"""
                SELECT DISTINCT {field}
                FROM k8s_events 
                WHERE {where_clause}
                ORDER BY {field}
                LIMIT 1000
                """
                # 在线程池中执行同步的数据库查询
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: clickhouse_client.pool.execute_query(sql, params))
                # 包含所有值，包括空值（None、空字符串等）
                field_values = ["[全部]"]  # 在列表第一个位置添加"[全部]"选项
                for row in result:
                    value = row[0] if row[0] else "[空值]"
                    if value not in field_values:  # 去重
                        field_values.append(value)
                return field, field_values

            except Exception as e:
                logger.error(f"查询{field}字段选项失败: {e}")
                return field, []

        # 并发执行所有字段查询
        tasks = [query_field_options(field) for field in menu_fields]
        results = await asyncio.gather(*tasks)

        # 构建结果字典
        menu_options = {field: options for field, options in results}

        return web.json_response({"success": True, "data": menu_options})

    except Exception as e:
        logger.error(f"获取菜单选项失败: {e}")
        return web.json_response({"code": 500, "message": f"获取菜单选项失败: {str(e)}"})


async def query_k8s_events_handler(request):
    """查询K8S事件接口"""
    try:
        # 获取请求体数据
        data = await request.json()

        # 验证必填参数
        required_fields = ['k8s', 'start_time', 'end_time', 'limit']
        for field in required_fields:
            if field not in data:
                return web.json_response({"code": 400, "message": f"缺少必填参数: {field}"})

        # 获取ClickHouse客户端
        clickhouse_client = get_clickhouse_client()

        # 执行查询
        result = clickhouse_client.query_events_advanced(
            k8s=data['k8s'],
            start_time=data.get('start_time'),
            end_time=data.get('end_time'),
            limit=int(data['limit']),
            namespace=data.get('namespace'),
            count=data.get('count'),
            level=data.get('level'),
            kind=data.get('kind'),
            name=data.get('name'),
            reason=data.get('reason'),
            reporting_component=data.get('reportingComponent'),
            reporting_instance=data.get('reportingInstance'),
            message=data.get('message'),
        )

        # 序列化datetime对象
        serialized_result = serialize_datetime_objects(result)

        return web.json_response({"success": True, "data": serialized_result, "total": len(serialized_result)})

    except Exception as e:
        logger.error(f"查询K8S事件失败: {e}")
        return web.json_response({"code": 500, "message": f"查询失败: {str(e)}"})
