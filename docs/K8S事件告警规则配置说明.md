# K8S 事件告警规则配置说明

## 概述

KubeDoor K8S事件告警系统是一个基于规则驱动的智能告警解决方案，能够根据配置的规则自动检测和处理 Kubernetes 事件，并发送相应的告警通知。

## 功能特性

- 🎯 **规则驱动**: 基于 JSON 配置文件的灵活告警规则
- 🔍 **多条件匹配**: 支持字段包含/不包含、开头/结尾匹配、数值比较等多种匹配条件
- 🚫 **智能过滤**: 忽略 DELETED 事件和配置的忽略规则
- 🔄 **热重载**: 支持运行时重新加载告警规则
- 📱 **多渠道通知**: 支持企业微信、钉钉、飞书、Slack 等多种告警通知方式

## DELETED 事件说明

接收到 `eventStatus=DELETED` 的事件，表示该事件超过TTL时间后没有再次触发，事件被K8S删除。并不是实际触发了事件，所以DELETED 事件不会触发任何告警，同时事件状态会记录到数据库。

## 告警规则配置示例

告警规则配置文件configmap：`kubedoor-master-file-cfg`

```json
{
  "global_ignore_rules": [
    {
      "name": "环境过滤规则(排除非生产环境[注意:当前未开启])",
      "enabled": false,
      "conditions": {
        "k8s": {
          "not_contains": ["prod"]
        }
      }
    },
    {
      "name": "常见忽略事件[示例:防止告警规则中有正常事件被匹配到,可以加到忽略规则中]",
      "enabled": true,
      "conditions": {
        "reason": {
          "contains": ["BackOffStart", "SuccessfulCreate", "SuccessfulMountVolume"]
        }
      }
    }
  ],
  "alert_rules": [
    {
      "name": "关键事件告警",
      "enabled": true,
      "severity": "critical",
      "conditions": {
        "reason": {
          "contains": ["OOM", "NodeNotReady", "Unreachable"]
        },
        "level": {
          "contains": ["Warning"]
        }
      }
    },
    {
      "name": "健康检查失败告警",
      "enabled": true,
      "severity": "warning",
      "conditions": {
        "reason": {
          "contains": ["Unhealthy"]
        },
        "name": {
          "not_starts_with": ["deploy-datax-cloud-"]
        },
        "count": {
          "greater_than": 1
        }
      }
    },
    {
      "name": "资源压力告警",
      "enabled": true,
      "severity": "warning",
      "conditions": {
        "reason": {
          "contains": ["Pressure", "OutOf", "Evict"]
        }
      }
    }
  ]
}
```

## 规则说明

### 1. 规则匹配逻辑

- 共2个规则组，每个规则组有若干条规则。
- 可以通过 `enabled` 字段控制规则是否开启。
- 触发K8S事件后，先进入`global_ignore_rules`**规则组**，**任意一条规则**匹配即忽略事件。如果未忽略，则进入`alert_rules`**规则组**，**第一个匹配的规则**生效，即触发告警。**

### 2. 规则组之间的关系

1. **global_ignore_rules**: 多条忽略规则之间是 **OR** 关系，任意一条规则匹配即忽略事件。
2. **alert_rules**: 多条告警规则之间是 **OR** 关系，按数组顺序匹配，第一个匹配的规则生效。

### 3. 单条规则内的条件关系

每条规则的 `conditions` 内的多个字段条件之间是 **AND** 关系，必须所有条件都满足才算匹配：

```json
{
  "conditions": {
    "reason": { "contains": ["OOMKilling"] }, // 条件1
    "level": { "equals": "Warning" }, // 条件2
    "namespace": { "not_contains": ["test"] } // 条件3
  }
  // 只有当 reason包含OOMKilling AND level等于Warning AND namespace不包含test 时才匹配
}
```

### 4. 字段条件内的值关系

对于同一字段的多个值，关系取决于条件类型：

- **contains**: 多个值之间是 **OR** 关系（包含任一值即匹配）
- **not_contains**: 多个值之间是 **AND** 关系（不包含任何值才匹配）
- **starts_with/ends_with**: 多个值之间是 **OR** 关系
- **not_starts_with/not_ends_with**: 多个值之间是 **AND** 关系

## 支持的条件类型

| 条件类型          | 说明                      | 示例                                               |
| ----------------- | ------------------------- | -------------------------------------------------- |
| `contains`        | 字段包含任一指定值        | `{"reason": {"contains": ["OOM", "Failed"]}}`      |
| `not_contains`    | 字段不包含任何指定值      | `{"namespace": {"not_contains": ["test", "dev"]}}` |
| `equals`          | 字段等于指定值            | `{"level": {"equals": "Warning"}}`                 |
| `not_equals`      | 字段不等于指定值          | `{"eventStatus": {"not_equals": "DELETED"}}`       |
| `starts_with`     | 字段以指定值开头          | `{"name": {"starts_with": ["deploy-"]}}`           |
| `not_starts_with` | 字段不以指定值开头        | `{"name": {"not_starts_with": ["test-"]}}`         |
| `ends_with`       | 字段以指定值结尾          | `{"name": {"ends_with": ["-service", "-pod"]}}`    |
| `not_ends_with`   | 字段不以指定值结尾        | `{"name": {"not_ends_with": ["-test", "-debug"]}}` |
| `greater_than`    | 数值大于（仅 count 字段） | `{"count": {"greater_than": 3}}`                   |
| `less_than`       | 数值小于（仅 count 字段） | `{"count": {"less_than": 10}}`                     |

## 支持的事件字段

| 字段名 | 描述 |
|--------|------|
| level | 事件级别（Normal/Warning） |
| count | 事件发生次数 |
| kind | 对象的类型 |
| k8s | K8S集群名称 |
| namespace | 命名空间 |
| name | 对象的名称 |
| reason | 事件原因 |
| message | 事件详细消息 |
| reportingComponent | 事件来源 |
| reportingInstance | 来源IP |

#### 注意：K8S事件告警去重时间窗口，通过变量`ALERT_DEDUP_WINDOW`控制（configmap：kubedoor-config），默认300秒。（即重复事件告警5分钟最多通知一次。）
