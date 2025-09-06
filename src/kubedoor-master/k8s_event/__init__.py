#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
K8S事件处理模块
提供K8S事件数据的ClickHouse存储和查询功能
"""

from .clickhouse_client import ClickHouseClient, get_clickhouse_client, init_clickhouse_tables
from .event_processor import (
    K8SEventProcessor, 
    get_event_processor, 
    process_k8s_event_async,
    reload_alert_rules,
    get_alert_stats
)
from .alert_rule_matcher import AlertRuleMatcher
from .event_alert_processor import EventAlertProcessor

__all__ = [
    'ClickHouseClient',
    'get_clickhouse_client',
    'init_clickhouse_tables',
    'K8SEventProcessor',
    'get_event_processor',
    'process_k8s_event_async',
    'reload_alert_rules',
    'get_alert_stats',
    'AlertRuleMatcher',
    'EventAlertProcessor',
]

__version__ = '1.0.0'
