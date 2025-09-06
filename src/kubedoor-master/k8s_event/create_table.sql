-- K8S事件表结构
-- 使用ReplacingMergeTree引擎处理数据更新
-- eventUid确保唯一性，lastTimestamp作为版本列
-- 支持90天TTL，基于lastTimestamp排序

CREATE TABLE IF NOT EXISTS k8s_events (
    eventUid String,                    -- 事件唯一标识符（来自metadata.uid）
    eventStatus LowCardinality(String), -- 事件状态（ADDED/MODIFIED/DELETED）
    level LowCardinality(String),       -- 事件级别（Normal/Warning）
    count UInt32,                       -- 事件发生次数
    kind LowCardinality(String),        -- 涉及对象的类型
    k8s String,                         -- K8S集群名称
    namespace LowCardinality(String),   -- 命名空间
    name String,                        -- 涉及对象的名称
    reason LowCardinality(String),      -- 事件原因
    message String,                     -- 事件详细消息
    firstTimestamp DateTime('Asia/Shanghai'), -- 首次发生时间（北京时间）
    lastTimestamp DateTime('Asia/Shanghai'),  -- 最后发生时间（北京时间）
    reportingComponent String,          -- 报告组件
    reportingInstance String,           -- 报告实例
    createdAt DateTime('Asia/Shanghai') DEFAULT now('Asia/Shanghai') -- 记录创建时间
)
ENGINE = ReplacingMergeTree(lastTimestamp)
PARTITION BY (k8s, toYYYYMM(lastTimestamp))
ORDER BY (eventUid, k8s, namespace)
PRIMARY KEY (eventUid)
TTL lastTimestamp + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;

-- 创建索引以优化常用查询
-- 基于k8s, namespace, lastTimestamp, level, kind的查询优化
CREATE INDEX IF NOT EXISTS idx_k8s_namespace_time ON k8s_events (k8s, namespace, lastTimestamp) TYPE minmax GRANULARITY 1;
CREATE INDEX IF NOT EXISTS idx_level_kind ON k8s_events (level, kind) TYPE set(100) GRANULARITY 1;
CREATE INDEX IF NOT EXISTS idx_reason ON k8s_events (reason) TYPE bloom_filter(0.01) GRANULARITY 1;