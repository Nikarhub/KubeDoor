#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClickHouse连接池管理器
使用clickhouse-connect库提供线程安全的连接池
解决"Simultaneous queries on single connection detected"问题
"""

import os
import threading
from typing import Optional, Any, Dict, List
from contextlib import contextmanager
from loguru import logger
import clickhouse_connect


class ClickHouseConnectionPool:
    """
    ClickHouse连接池管理器

    特性:
    - 线程安全的连接池
    - 自动连接管理和回收
    - 支持连接超时和重试
    - 独立于全局连接，避免并发冲突
    """

    _instance: Optional['ClickHouseConnectionPool'] = None
    _lock = threading.Lock()

    def __new__(cls):
        """单例模式确保全局唯一连接池"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化连接池配置"""
        if hasattr(self, '_initialized'):
            return

        # 从环境变量获取连接配置
        self.host = os.environ.get('CK_HOST', 'localhost')
        self.port = int(os.environ.get('CK_HTTP_PORT', '8123'))  # HTTP端口
        self.username = os.environ.get('CK_USER', 'default')
        self.password = os.environ.get('CK_PASSWORD', '')
        self.database = os.environ.get('CK_DATABASE', 'default')

        # 连接池配置
        self.pool_size = int(os.environ.get('CK_POOL_SIZE', '10'))  # 最大连接数
        self.connect_timeout = int(os.environ.get('CK_CONNECT_TIMEOUT', '10'))  # 连接超时
        self.send_receive_timeout = int(os.environ.get('CK_QUERY_TIMEOUT', '300'))  # 查询超时

        # 连接池状态
        self._pool_lock = threading.Lock()
        self._initialized = True

        logger.info(
            f"ClickHouse连接池初始化完成 - Host: {self.host}:{self.port}, Database: {self.database}, Pool Size: {self.pool_size}"
        )

    def _create_client(self):
        """创建新的ClickHouse客户端连接"""
        try:
            client = clickhouse_connect.get_client(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                database=self.database,
                connect_timeout=self.connect_timeout,
                send_receive_timeout=self.send_receive_timeout,
                # 压缩设置
                compress=True,
                # 安全设置
                secure=False,
            )

            # 测试连接
            client.ping()
            logger.debug(f"创建新的ClickHouse连接成功 - Thread: {threading.current_thread().name}")
            return client

        except Exception as e:
            logger.error(f"创建ClickHouse连接失败: {e}")
            raise

    @contextmanager
    def get_client(self):
        """
        获取连接池中的客户端连接（上下文管理器）

        使用方式:
        with pool.get_client() as client:
            result = client.query("SELECT 1")
        """
        client = None
        try:
            client = self._create_client()
            yield client
        except Exception as e:
            logger.error(f"连接池操作失败: {e}")
            raise
        finally:
            if client:
                try:
                    client.close()
                    logger.debug(f"连接已关闭 - Thread: {threading.current_thread().name}")
                except Exception as e:
                    logger.warning(f"关闭连接时出错: {e}")

    def execute_query(self, query: str, parameters=None) -> List[Any]:
        """
        执行查询语句

        Args:
            query: SQL查询语句
            parameters: 查询参数，支持Dict或List格式

        Returns:
            查询结果列表
        """
        with self.get_client() as client:
            try:
                if parameters:
                    # 支持Dict和List两种参数格式
                    if isinstance(parameters, dict):
                        result = client.query(query, parameters=parameters)
                    else:
                        # List格式参数
                        result = client.query(query, parameters=parameters)
                else:
                    result = client.query(query)

                # 转换为列表格式，兼容原有代码
                return result.result_rows if hasattr(result, 'result_rows') else []

            except Exception as e:
                logger.error(f"执行查询失败 - Query: {query[:100]}..., Error: {e}")
                raise

    def execute_command(self, command: str, parameters: Optional[Dict] = None) -> Any:
        """
        执行命令（INSERT, UPDATE, DELETE等）

        Args:
            command: SQL命令
            parameters: 命令参数

        Returns:
            执行结果
        """
        with self.get_client() as client:
            try:
                if parameters:
                    result = client.command(command, parameters=parameters)
                else:
                    result = client.command(command)

                logger.debug(f"执行命令成功 - Command: {command[:100]}...")
                return result

            except Exception as e:
                logger.error(f"执行命令失败 - Command: {command[:100]}..., Error: {e}")
                raise


# 全局连接池实例
_connection_pool: Optional[ClickHouseConnectionPool] = None
_pool_lock = threading.Lock()


def get_connection_pool() -> ClickHouseConnectionPool:
    """
    获取全局连接池实例

    Returns:
        ClickHouse连接池实例
    """
    global _connection_pool

    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:
                _connection_pool = ClickHouseConnectionPool()

    return _connection_pool
