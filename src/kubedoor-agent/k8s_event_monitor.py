#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
K8S事件实时监控模块
使用kubernetes_asyncio库异步监听K8S事件，并通过WebSocket推送到kubedoor-master
"""

import asyncio
import json
from datetime import datetime
from kubernetes_asyncio import client, watch
from kubernetes_asyncio.client.rest import ApiException
from loguru import logger
from utils import PROM_K8S_TAG_VALUE, MSG_TOKEN


class K8sEventMonitor:
    """K8S事件监听器"""

    def __init__(self, core_v1_api):
        self.core_v1 = core_v1_api
        self.ws_conn = None
        self.monitor_task = None
        self.is_running = False

    def set_websocket_connection(self, ws_conn):
        """设置WebSocket连接"""
        self.ws_conn = ws_conn



    def format_event_data(self, event):
        """格式化事件数据为指定的JSON格式"""
        try:
            event_type = event['type']  # ADDED, MODIFIED, DELETED
            raw_object = event['raw_object']

            # 提取metadata信息
            metadata = raw_object.get('metadata', {})
            event_uid = metadata.get('uid', '')

            # 提取involvedObject信息
            involved_object = raw_object.get('involvedObject', {})
            kind = involved_object.get('kind', '')
            namespace = involved_object.get('namespace', '')
            name = involved_object.get('name', '')

            # 提取其他字段
            level = raw_object.get('type', '')  # Normal, Warning
            count = raw_object.get('count', 0)
            reason = raw_object.get('reason', '')
            message = raw_object.get('message', '')

            # 直接使用原始时间戳
            first_timestamp = raw_object.get('firstTimestamp')
            last_timestamp = raw_object.get('lastTimestamp')

            # 报告组件信息
            source = raw_object.get('source', {})
            reporting_component = source.get('component', '')
            reporting_instance = source.get('host', '')

            # 构造事件数据
            event_data = {
                "eventUid": event_uid,
                "eventStatus": event_type,
                "level": level,
                "count": count,
                "kind": kind,
                "k8s": PROM_K8S_TAG_VALUE,
                "namespace": namespace,
                "name": name,
                "reason": reason,
                "message": message,
                "firstTimestamp": first_timestamp,
                "lastTimestamp": last_timestamp,
                "reportingComponent": reporting_component,
                "reportingInstance": reporting_instance,
                "msgToken": MSG_TOKEN,
            }

            return event_data

        except Exception as e:
            logger.error(f"格式化事件数据失败: {e}")
            logger.debug(f"原始事件数据: {json.dumps(event, indent=2, ensure_ascii=False)}")
            return None

    async def send_event_to_master(self, event_data):
        """通过WebSocket发送事件数据到kubedoor-master"""
        if not self.ws_conn:
            logger.warning("WebSocket连接未建立，无法发送事件")
            return

        try:
            # 构造WebSocket消息
            ws_message = {"type": "k8s_event", "data": event_data, "timestamp": datetime.now().isoformat()}

            await self.ws_conn.send_json(ws_message)
            logger.debug(f"事件已发送: {event_data['kind']}/{event_data['name']} - {event_data['reason']}")

        except Exception as e:
            logger.error(f"发送事件到master失败: {e}")

    async def monitor_events(self, namespace=None):
        """监控K8S事件"""
        try:
            logger.info("🚀 开始监控K8S事件...")
            logger.info(f"📍 监控范围: {'所有命名空间' if not namespace else f'命名空间 {namespace}'}")

            # 创建事件监听器
            w = watch.Watch()

            # 开始监听事件
            if namespace:
                stream = w.stream(self.core_v1.list_namespaced_event, namespace=namespace)
            else:
                stream = w.stream(self.core_v1.list_event_for_all_namespaces)

            async for event in stream:
                if not self.is_running:
                    logger.info("事件监控已停止")
                    break

                try:
                    # 格式化事件数据
                    event_data = self.format_event_data(event)

                    if event_data:
                        # 发送事件到master
                        await self.send_event_to_master(event_data)

                        # 记录事件日志
                        logger.info(
                            f"📨 [{event_data['eventStatus']}] {event_data['level']} - "
                            f"{event_data['kind']}/{event_data['name']} - {event_data['reason']} - "
                            f"首次: {event_data['firstTimestamp']} 最后: {event_data['lastTimestamp']}"
                        )

                except Exception as e:
                    logger.error(f"处理事件时出错: {e}")
                    continue

        except asyncio.CancelledError:
            logger.info("⏹️ 事件监控被取消")
        except ApiException as e:
            logger.error(f"❌ K8S API错误: {e}")
        except Exception as e:
            logger.error(f"❌ 监控过程中出错: {e}")
        finally:
            self.is_running = False

    async def start_monitoring(self, namespace=None):
        """启动事件监控"""
        if self.is_running:
            logger.warning("事件监控已在运行中")
            return

        self.is_running = True
        self.monitor_task = asyncio.create_task(self.monitor_events(namespace))
        logger.info("K8S事件监控已启动")

    async def stop_monitoring(self):
        """停止事件监控"""
        if not self.is_running:
            logger.warning("事件监控未在运行")
            return

        self.is_running = False

        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("K8S事件监控已停止")
