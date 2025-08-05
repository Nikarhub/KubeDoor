<template>
  <div class="alarm-container">
    <!-- 搜索框 -->
    <div class="search-section">
      <div
        style="
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
        "
      >
        <el-form :inline="true" style="margin-bottom: -18px">
          <el-form-item label="开始时间">
            <el-select
              v-model="timeRange"
              placeholder="选择时间范围"
              style="width: 200px"
              @change="handleTimeRangeChange"
            >
              <el-option label="今天" :value="0" />
              <el-option label="最近1天" :value="1" />
              <el-option label="最近3天" :value="3" />
              <el-option label="最近5天" :value="5" />
              <el-option label="最近7天" :value="7" />
              <el-option label="最近15天" :value="15" />
              <el-option label="最近30天" :value="30" />
            </el-select>
          </el-form-item>

          <el-form-item label="K8S">
            <el-select
              v-model="queryParams.env"
              placeholder="请选择环境"
              filterable
              clearable
              style="width: 200px"
              @change="getAlarmData"
            >
              <el-option
                v-for="item in envOptions"
                :key="item"
                :label="item"
                :value="item"
              />
            </el-select>
          </el-form-item>

          <el-form-item>
            <el-checkbox
              v-model="hideZeroAlerts"
              @change="handleHideZeroChange"
            >
              隐藏0告警
            </el-checkbox>
          </el-form-item>
        </el-form>

        <el-tooltip
          effect="dark"
          :content="
            autoRefreshInterval === 0 ? `自动刷新已关闭` : '设置自动刷新间隔'
          "
          placement="top"
        >
          <el-button-group>
            <el-button @click="getAlarmData()">
              <el-icon style="margin-right: 4px"><RefreshRight /></el-icon>
              刷新
            </el-button>
            <el-dropdown trigger="click" @command="handleRefreshIntervalChange">
              <el-button>
                {{ autoRefreshInterval === 0 ? "" : autoRefreshInterval + "s" }}
                <el-icon style="margin-left: 4px"><ArrowDown /></el-icon>
              </el-button>

              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item :command="0">关</el-dropdown-item>
                  <el-dropdown-item :command="15">15s</el-dropdown-item>
                  <el-dropdown-item :command="30">30s</el-dropdown-item>
                  <el-dropdown-item :command="60">1m</el-dropdown-item>
                  <el-dropdown-item :command="300">5m</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </el-button-group>
        </el-tooltip>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="statistics-cards">
      <el-row :gutter="20">
        <el-col v-for="(stat, index) in statistics" :key="index" :span="6">
          <div class="stat-card" @click="handleCardClick(stat[0])">
            <div class="card-content">
              <div class="stat-header">
                <div class="stat-title-row">
                  <div
                    class="stat-label"
                    :style="{ color: getSeverityColor(stat[4]) }"
                    :title="stat[0]"
                  >
                    {{ stat[0] }}
                  </div>
                  <el-tag :type="getSeverityType(stat[4])" size="small">
                    {{ getSeverityText(stat[4]) }}
                  </el-tag>
                </div>
              </div>
              <div class="stat-body">
                <div v-if="stat[2] > 0" class="stat-firing">
                  <span class="stat-value firing">{{ stat[2] }}</span>
                  <span class="stat-unit">告警中</span>
                </div>
                <div v-else>
                  <span class="stat-value info">0</span>
                  <span class="stat-unit">告警中</span>
                </div>
                <span class="stat-separator">/</span>
                <div class="stat-total">
                  <span class="stat-value">{{ stat[1] }}</span>
                  <span class="stat-unit">总数</span>
                </div>
              </div>
            </div>
          </div>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch, onUnmounted } from "vue";
import { getAlarmTotal, getEnv } from "@/api/alarm";
import { useRouter } from "vue-router";
import { RefreshRight, ArrowDown } from "@element-plus/icons-vue";
import dayjs from "dayjs";
import { useSearchStoreHook } from "@/store/modules/search";

const router = useRouter();
const searchStore = useSearchStoreHook();
const loading = ref(false);
const statistics = ref([]);

// 自动刷新相关
const autoRefreshInterval = ref(0); // 默认关闭
let refreshTimer: ReturnType<typeof setInterval> | null = null;

// 开始自动刷新
const startAutoRefresh = () => {
  stopAutoRefresh(); // 先清除可能存在的定时器
  refreshTimer = setInterval(() => {
    getAlarmData();
  }, autoRefreshInterval.value * 1000);
};

// 停止自动刷新
const stopAutoRefresh = () => {
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
};

// 处理刷新间隔变化
const handleRefreshIntervalChange = (interval: number) => {
  autoRefreshInterval.value = interval;
  if (autoRefreshInterval.value) {
    startAutoRefresh(); // 重启定时器以应用新间隔
  } else {
    stopAutoRefresh();
  }
};

// 环境选项
const envOptions = ref<string[]>([]);

// 查询参数
const timeRange = ref<number | null>(0);
const hideZeroAlerts = ref(false);

const queryParams = reactive({
  startTime: dayjs().startOf("day").format("YYYY-MM-DD HH:mm:ss"),
  env: searchStore.env
});

const getSeverityColor = (severity: string) => {
  const map: Record<string, string> = {
    critical: "#F56C6C",
    warning: "#E6A23C",
    notice: "#409EFF",
    info: "#909399"
  };
  return map[severity.toLowerCase()] || "black";
};

const getSeverityType = (
  severity: string
): "success" | "warning" | "danger" | "info" => {
  switch (severity.toLowerCase()) {
    case "critical":
      return "danger";
    case "warning":
      return "warning";
    case "info":
      return "info";
  }
};

const getSeverityText = (severity: string) => {
  const map: Record<string, string> = {
    critical: "严重",
    warning: "警告",
    info: "信息",
    notice: "提示"
  };
  return map[severity.toLowerCase()] || severity;
};

// 处理卡片点击
const handleCardClick = (alertName: string) => {
  console.log(alertName);
  router.push({
    name: "alarm-detail",
    query: {
      alertName,
      timeRange: timeRange.value,
      env: queryParams.env
    }
  });
};

const handleTimeRangeChange = (val: number) => {
  let startTime;
  if (val === 0) {
    // 今天的0点
    startTime = dayjs().startOf("day");
  } else {
    // 前n天的0点
    startTime = dayjs().subtract(val, "day").startOf("day");
  }
  getAlarmData({ startTime: startTime.format("YYYY-MM-DD HH:mm:ss") });
};

// 获取告警统计数据
const getAlarmData = async (data?: Partial<typeof queryParams>) => {
  try {
    loading.value = true;
    // 合并查询参数
    Object.assign(queryParams, data);
    console.log(queryParams);
    const res = await getAlarmTotal(queryParams.env, queryParams.startTime);
    statistics.value = res.data;

    // 如果勾选了隐藏0告警，过滤掉告警数为0的项
    if (hideZeroAlerts.value) {
      statistics.value = statistics.value.filter((stat: any) => stat[2] > 0);
    }
  } catch (error) {
    console.error("获取告警统计数据失败:", error);
  } finally {
    loading.value = false;
  }
};

// 获取环境选项
const getEnvOptions = async () => {
  try {
    const res = await getEnv();
    envOptions.value = res.data.map((item: string[]) => item[0]);
    // 如果 store 中有值且存在于选项中，则使用 store 中的值
    if (searchStore.env && envOptions.value.includes(searchStore.env)) {
      queryParams.env = searchStore.env;
    } else {
      queryParams.env = envOptions.value[0];
      searchStore.setEnv(envOptions.value[0]);
    }
    return Promise.resolve(envOptions.value);
  } catch (error) {
    console.error("获取环境选项失败:", error);
    return Promise.reject(error);
  }
};

// 监听环境变化
watch(
  () => queryParams.env,
  newVal => {
    if (newVal) {
      searchStore.setEnv(newVal);
      getAlarmData();
    }
  }
);

// 处理隐藏0告警状态变化
const handleHideZeroChange = (val: boolean) => {
  getAlarmData();
};

// 页面初始化时获取数据
onMounted(async () => {
  await getEnvOptions();
  if (queryParams.env) {
    getAlarmData();
  }
});

onUnmounted(() => {
  stopAutoRefresh(); // 组件卸载时清除定时器
});
</script>

<style scoped>
.search-section {
  padding: 16px;
  margin-bottom: 20px;
  background-color: var(--el-bg-color);
  border-radius: 8px;
}

.statistics-cards {
  margin-bottom: 20px;
}

.statistics-cards .el-row {
  margin-bottom: 20px;
}

.stat-card {
  position: relative;
  height: 100%;
  padding: 16px;
  overflow: hidden;
  cursor: pointer;
  background: linear-gradient(135deg, #fff 0%, #f5f7fa 100%);
  border-radius: 12px;
  box-shadow: 0 4px 20px rgb(0 0 0 / 5%);
  transition: all 0.3s ease;
}

.stat-card::before {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 4px;
  content: "";
  background: linear-gradient(90deg, #409eff, #67c23a);
  opacity: 0.8;
  transition: opacity 0.3s ease;
}

.stat-card:hover {
  box-shadow: 0 8px 24px rgb(0 0 0 / 12%);
  transform: translateY(-5px);
}

.stat-card:hover::before {
  opacity: 1;
}

.stat-card:active {
  box-shadow: 0 4px 12px rgb(0 0 0 / 8%);
  transform: translateY(-2px);
}

.card-content {
  position: relative;
  z-index: 0;
  padding-top: 16px;
}

.stat-header {
  margin-bottom: 16px;
}

.stat-title-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.stat-label {
  flex: 1;
  overflow: hidden;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stat-body {
  display: flex;
  gap: 8px;
  align-items: center;
}

.stat-total,
.stat-firing {
  display: flex;
  align-items: baseline;
}

.stat-value {
  margin-right: 4px;
  font-size: 24px;
  font-weight: 600;
  color: var(--el-color-primary);

  &.firing {
    font-size: 20px;
    color: var(--el-color-danger);
  }

  &.info {
    font-size: 20px;
    color: var(--el-color-info);
  }
}

.stat-unit {
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.stat-separator {
  margin: 0 4px;
  font-size: 20px;
  line-height: 1;
  color: var(--el-text-color-secondary);
}

.statistics-cards .el-col {
  margin-bottom: 20px;
}
</style>
