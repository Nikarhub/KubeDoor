<template>
  <div class="events-container events-page">
    <!-- 顶部筛选菜单 -->
    <div class="filter-menu mb-3">
      <el-card class="filter-card">
        <!-- 第一行：基本筛选项 -->
        <div class="filter-row">
          <!-- 时间范围选择器 -->
          <div class="filter-item">
            <label class="filter-label">时间</label>
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              unlink-panels
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              :shortcuts="shortcuts"
              size="default"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              style="width: 220px"
              @change="onDateRangeChange"
            />
          </div>

          <!-- K8S字段选择 -->
          <div class="filter-item">
            <label class="filter-label">K8S</label>
            <el-select
              v-model="selectedK8s"
              placeholder="请选择K8S集群"
              filterable
              style="width: 180px"
              @change="onK8sChange"
            >
              <el-option
                v-for="item in k8sList"
                :key="item"
                :label="item"
                :value="item"
              />
            </el-select>
          </div>

          <!-- 命名空间字段选择 -->
          <div class="filter-item">
            <label class="filter-label">空间</label>
            <el-select
              v-model="selectedNamespace"
              placeholder="请选择命名空间"
              filterable
              clearable
              :disabled="!selectedK8s"
              style="width: 100px"
              @change="onNamespaceChange"
              @clear="() => (selectedNamespace = '[全部]')"
            >
              <el-option
                v-for="item in namespaceList"
                :key="item"
                :label="item"
                :value="item"
              />
            </el-select>
          </div>

          <!-- Kind字段选择 -->
          <div class="filter-item">
            <label class="filter-label">Kind</label>
            <el-select
              v-model="selectedKind"
              placeholder="请选择Kind"
              filterable
              clearable
              :disabled="!selectedK8s"
              style="width: 120px"
              @clear="() => (selectedKind = '[全部]')"
            >
              <el-option
                v-for="item in kindList"
                :key="item"
                :label="item"
                :value="item"
              />
            </el-select>
          </div>

          <!-- Name字段选择 -->
          <div class="filter-item">
            <label class="filter-label">名称</label>
            <el-select
              v-model="selectedName"
              filterable
              clearable
              :disabled="!selectedK8s"
              style="width: 200px"
              @clear="() => (selectedName = '[全部]')"
            >
              <el-option
                v-for="item in nameList"
                :key="item"
                :label="item"
                :value="item"
              />
            </el-select>
          </div>

          <!-- Reason字段选择 -->
          <div class="filter-item">
            <label class="filter-label">原因</label>
            <el-tooltip
              content="支持输入, 模糊匹配"
              placement="top"
              effect="dark"
            >
              <el-select
                v-model="selectedReason"
                placeholder="支持输入, 模糊匹配"
                filterable
                clearable
                allow-create
                :disabled="!selectedK8s"
                style="width: 180px"
                @clear="() => (selectedReason = '[全部]')"
              >
                <el-option
                  v-for="item in reasonList"
                  :key="item"
                  :label="item"
                  :value="item"
                />
              </el-select>
            </el-tooltip>
          </div>

          <!-- Level字段选择 -->
          <div class="filter-item">
            <label class="filter-label">级别</label>
            <el-select
              v-model="selectedLevel"
              placeholder="默认全部"
              clearable
              style="width: 100px"
            >
              <el-option label="已告警" value="已告警" />
              <el-option label="Warning" value="Warning" />
              <el-option label="Normal" value="Normal" />
            </el-select>
          </div>

          <!-- 展开/收起按钮 -->
          <div class="filter-item">
            <el-button
              type="text"
              class="toggle-btn"
              @click="toggleAdvancedFilters"
            >
              <el-icon
                class="toggle-icon"
                :class="{ 'is-expanded': showAdvancedFilters }"
              >
                <ArrowDown />
              </el-icon>
              {{ showAdvancedFilters ? "收起" : "更多" }}
            </el-button>
          </div>

          <!-- 查询按钮 -->
          <div class="filter-item">
            <el-button
              type="primary"
              :loading="loading"
              @click="queryEventsData"
            >
              查询
            </el-button>
          </div>

          <!-- 重置按钮 -->
          <div class="filter-item">
            <el-button type="primary" plain @click="resetFilters">
              重置
            </el-button>
          </div>
        </div>

        <!-- 第二行：高级筛选项（可折叠） -->
        <el-collapse-transition>
          <div v-show="showAdvancedFilters" class="filter-row advanced-filters">
            <!-- ReportingComponent字段选择 -->
            <div class="filter-item">
              <label class="filter-label">来源</label>
              <el-select
                v-model="selectedReportingComponent"
                placeholder="请选择ReportingComponent"
                filterable
                clearable
                :disabled="!selectedK8s"
                style="width: 220px"
                @clear="() => (selectedReportingComponent = '[全部]')"
              >
                <el-option
                  v-for="item in reportingComponentList"
                  :key="item"
                  :label="item"
                  :value="item"
                />
              </el-select>
            </div>

            <!-- ReportingInstance字段选择 -->
            <div class="filter-item">
              <label class="filter-label">来源IP</label>
              <el-select
                v-model="selectedReportingInstance"
                placeholder="请选择ReportingInstance"
                filterable
                clearable
                :disabled="!selectedK8s"
                style="width: 140px"
                @clear="() => (selectedReportingInstance = '[全部]')"
              >
                <el-option
                  v-for="item in reportingInstanceList"
                  :key="item"
                  :label="item"
                  :value="item"
                />
              </el-select>
            </div>

            <!-- Count字段输入 -->
            <div class="filter-item">
              <label class="filter-label">次数</label>
              <el-input-number
                v-model="selectedCount"
                :min="0"
                :controls="false"
                style="width: 100px"
              >
                <template #prefix><span>≧</span></template>
              </el-input-number>
            </div>

            <!-- Message字段输入 -->
            <div class="filter-item">
              <label class="filter-label">消息</label>
              <el-input
                v-model="selectedMessage"
                placeholder="支持模糊匹配"
                style="width: 260px"
              />
            </div>

            <!-- Limit字段选择 -->
            <div class="filter-item">
              <label class="filter-label">Limit</label>
              <el-select
                v-model="selectedLimit"
                placeholder="请选择Limit"
                style="width: 100px"
              >
                <el-option label="100" :value="100" />
                <el-option label="200" :value="200" />
                <el-option label="300" :value="300" />
                <el-option label="500" :value="500" />
                <el-option label="1000" :value="1000" />
              </el-select>
            </div>
          </div>
        </el-collapse-transition>
      </el-card>
    </div>

    <!-- 事件数据表格展示区域 -->
    <div v-if="eventsData.length > 0" class="events-table">
      <el-table
        :data="eventsData"
        stripe
        border
        style="width: 100%"
        :loading="loading"
      >
        <el-table-column label="状态" align="center" width="80">
          <template #default="{ row }">
            <el-tag
              :type="
                row[0] === 'ADDED'
                  ? 'success'
                  : row[0] === 'DELETED'
                    ? 'danger'
                    : 'warning'
              "
              size="small"
            >
              {{
                row[0] === "ADDED"
                  ? "新增"
                  : row[0] === "DELETED"
                    ? "删除"
                    : "更新"
              }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="级别" align="center" width="80">
          <template #default="{ row }">
            <el-tag
              :type="
                row[1] === '已告警'
                  ? 'danger'
                  : row[1] === 'Warning'
                    ? 'warning'
                    : 'primary'
              "
              effect="dark"
            >
              {{ row[1] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          label="次数"
          width="80"
          align="center"
          sortable
          prop="2"
        >
          <template #default="{ row }">
            {{ row[2] }}
          </template>
        </el-table-column>
        <el-table-column label="类型" width="80" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row[3] }}
          </template>
        </el-table-column>
        <el-table-column label="K8S集群" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row[4] }}
          </template>
        </el-table-column>
        <el-table-column label="命名空间" width="100">
          <template #default="{ row }">
            {{ row[5] }}
          </template>
        </el-table-column>
        <el-table-column label="名称" width="150" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row[6] }}
          </template>
        </el-table-column>
        <el-table-column label="原因" width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span style="color: #ff5555">{{ row[7] }}</span>
          </template>
        </el-table-column>
        <el-table-column label="消息" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row[8] }}
          </template>
        </el-table-column>
        <el-table-column label="首次时间" width="150">
          <template #default="{ row }">
            {{ new Date(row[9]).toLocaleString() }}
          </template>
        </el-table-column>
        <el-table-column label="最后时间" width="150">
          <template #default="{ row }">
            <span style="color: #409eff; font-weight: bold">{{
              new Date(row[10]).toLocaleString()
            }}</span>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="160" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row[11] }}
          </template>
        </el-table-column>
        <el-table-column label="来源IP" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row[12] }}
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 无数据提示 -->
    <div v-else-if="!loading" class="no-data">
      <el-empty description="暂无事件数据" />
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted, watch } from "vue";
import { ElMessage } from "element-plus";
import { ArrowDown } from "@element-plus/icons-vue";
import { getAgentNames } from "@/api/istio";
import { getEventsMenu, queryEvents } from "@/api/alarm";
import { useSearchStoreHook } from "@/store/modules/search";
const searchStore = useSearchStoreHook();
// 响应式数据
const dateRange = ref<[string, string] | null>(null);
const selectedK8s = ref<string>(searchStore.env || "");
const selectedNamespace = ref<string>("");
const selectedKind = ref<string>("");
const selectedName = ref<string>("");
const selectedReason = ref<string>("");
const selectedReportingComponent = ref<string>("");
const selectedReportingInstance = ref<string>("");
const showAdvancedFilters = ref<boolean>(false);
const selectedLevel = ref<string>("");
const selectedCount = ref<number | null>(null);
const selectedMessage = ref<string>("");
const selectedLimit = ref<number>(100);
const k8sList = ref<string[]>([]);
const namespaceList = ref<string[]>([]);
const kindList = ref<string[]>([]);
const nameList = ref<string[]>([]);
const reasonList = ref<string[]>([]);
const reportingComponentList = ref<string[]>([]);
const reportingInstanceList = ref<string[]>([]);
const eventsMenuData = ref<Record<string, any[]> | null>(null);
const eventsData = ref<any[]>([]);
const loading = ref(false);

// 格式化日期为本地时间字符串
const formatLocalDate = (date: Date): string => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

// 时间快捷选项
const shortcuts = [
  {
    text: "今天",
    value: () => {
      const today = new Date();
      const todayStr = formatLocalDate(today);
      return [todayStr, todayStr];
    }
  },
  {
    text: "昨天",
    value: () => {
      const yesterday = new Date();
      yesterday.setTime(yesterday.getTime() - 3600 * 1000 * 24);
      const yesterdayStr = formatLocalDate(yesterday);
      return [yesterdayStr, yesterdayStr];
    }
  },
  {
    text: "最近3天",
    value: () => {
      const end = new Date();
      const start = new Date();
      start.setTime(start.getTime() - 3600 * 1000 * 24 * 3);
      return [formatLocalDate(start), formatLocalDate(end)];
    }
  },
  {
    text: "本周",
    value: () => {
      const today = new Date();
      const dayOfWeek = today.getDay(); // 0是周日，1是周一
      const mondayOffset = dayOfWeek === 0 ? -6 : 1 - dayOfWeek; // 计算到周一的偏移

      const monday = new Date(today);
      monday.setDate(today.getDate() + mondayOffset);

      const sunday = new Date(monday);
      sunday.setDate(monday.getDate() + 6);

      return [formatLocalDate(monday), formatLocalDate(sunday)];
    }
  },
  {
    text: "最近1周",
    value: () => {
      const end = new Date();
      const start = new Date();
      start.setTime(start.getTime() - 3600 * 1000 * 24 * 7);
      return [formatLocalDate(start), formatLocalDate(end)];
    }
  },
  {
    text: "最近1个月",
    value: () => {
      const end = new Date();
      const start = new Date();
      start.setTime(start.getTime() - 3600 * 1000 * 24 * 30);
      return [formatLocalDate(start), formatLocalDate(end)];
    }
  },
  {
    text: "最近3个月",
    value: () => {
      const end = new Date();
      const start = new Date();
      start.setTime(start.getTime() - 3600 * 1000 * 24 * 90);
      return [formatLocalDate(start), formatLocalDate(end)];
    }
  }
];

// 加载K8S列表
const loadK8sList = async () => {
  try {
    const response = await getAgentNames();
    console.log("K8S API响应:", response);
    if (response.success && response.data) {
      console.log("K8S数据:", response.data);
      // 检查数据格式，如果是字符串数组直接使用，如果是对象数组则取第一个字段
      if (Array.isArray(response.data) && response.data.length > 0) {
        if (typeof response.data[0] === "string") {
          k8sList.value = response.data;
        } else if (Array.isArray(response.data[0])) {
          k8sList.value = response.data.map(item => item[0]);
        } else {
          // 如果是对象，尝试获取第一个属性值
          k8sList.value = response.data.map(
            item => Object.values(item)[0] as string
          );
        }
        // 优先使用 store 中的值，如果不存在或无效则使用第一个
        if (k8sList.value.length > 0) {
          if (searchStore.env && k8sList.value.includes(searchStore.env)) {
            selectedK8s.value = searchStore.env;
          } else {
            selectedK8s.value = k8sList.value[0];
            // 更新 store 中的值
            searchStore.setEnv(k8sList.value[0]);
          }

          // 如果有时间范围，自动加载事件菜单数据
          if (dateRange.value) {
            loadEventsMenu();
          }
        }
      }
      console.log("处理后的K8S列表:", k8sList.value);
    } else {
      console.log("K8S API返回数据为空或失败");
    }
  } catch (error) {
    console.error("加载K8S列表失败:", error);
    ElMessage.error("加载K8S列表失败");
  }
};

// 切换高级筛选显示状态
const toggleAdvancedFilters = () => {
  showAdvancedFilters.value = !showAdvancedFilters.value;
};

// 重置筛选条件
const resetFilters = () => {
  // 重置时间范围为今天（北京时间）
  const now = new Date();
  // 转换为北京时间（UTC+8）
  const beijingTime = new Date(now.getTime() + 8 * 60 * 60 * 1000);
  const today = beijingTime.toISOString().split("T")[0]; // 格式化为 YYYY-MM-DD
  dateRange.value = [today, today];

  // 重置K8S选择为第一个
  if (k8sList.value.length > 0) {
    selectedK8s.value = k8sList.value[0];
  }

  // 重置其他筛选条件
  selectedNamespace.value = "[全部]";
  selectedName.value = "[全部]";
  selectedReason.value = "";
  selectedLevel.value = "";
  selectedReportingComponent.value = "[全部]";
  selectedReportingInstance.value = "[全部]";
  selectedCount.value = "";
  selectedMessage.value = "";
  selectedLimit.value = 100;

  // 清空事件数据
  eventsData.value = [];

  // 收起高级筛选
  showAdvancedFilters.value = false;

  ElMessage.success("筛选条件已重置");
};

// 查询事件数据
const queryEventsData = async () => {
  if (!selectedK8s.value || !dateRange.value) {
    ElMessage.warning("请选择K8S集群和时间范围");
    return;
  }

  loading.value = true;
  try {
    const params = {
      k8s: selectedK8s.value,
      start_time: dateRange.value[0],
      end_time: dateRange.value[1],
      limit: selectedLimit.value
    };

    // 如果选择了命名空间，添加namespace参数
    if (selectedNamespace.value) {
      params.namespace = selectedNamespace.value;
    }

    // 如果选择了level，添加level参数
    if (selectedLevel.value) {
      params.level = selectedLevel.value;
    }

    // 如果输入了count，添加count参数
    if (selectedCount.value !== null && selectedCount.value !== undefined) {
      params.count = selectedCount.value;
    }

    // 如果选择了kind，添加kind参数
    if (selectedKind.value) {
      params.kind = selectedKind.value;
    }

    // 如果选择了name，添加name参数
    if (selectedName.value) {
      params.name = selectedName.value;
    }

    // 如果选择了reason，添加reason参数
    if (selectedReason.value) {
      params.reason = selectedReason.value;
    }

    // 如果选择了reportingComponent，添加reporting_component参数
    if (selectedReportingComponent.value) {
      params.reporting_component = selectedReportingComponent.value;
    }

    // 如果选择了reportingInstance，添加reporting_instance参数
    if (selectedReportingInstance.value) {
      params.reporting_instance = selectedReportingInstance.value;
    }

    // 如果输入了message，添加message参数
    if (selectedMessage.value) {
      params.message = selectedMessage.value;
    }

    const response = await queryEvents(params);

    console.log("事件查询API响应:", response);
    if (response.success && response.data) {
      // 处理事件列表数据
      eventsData.value = response.data;
      console.log("查询到的事件数据:", eventsData.value);
    } else {
      // 清空事件数据
      eventsData.value = [];
      ElMessage.warning("未查询到相关事件数据");
    }
  } catch (error) {
    console.error("查询事件数据失败:", error);
    ElMessage.error("查询事件数据失败");
    // 清空事件数据
    eventsData.value = [];
  } finally {
    loading.value = false;
  }
};

// 加载事件菜单数据
const loadEventsMenu = async () => {
  if (!selectedK8s.value || !dateRange.value) {
    ElMessage.warning("请选择K8S集群和时间范围");
    return;
  }

  loading.value = true;
  try {
    const params = {
      k8s: selectedK8s.value,
      start_time: dateRange.value[0],
      end_time: dateRange.value[1],
      limit: selectedLimit.value
    };

    // 如果选择了命名空间，添加namespace参数
    if (selectedNamespace.value) {
      params.namespace = selectedNamespace.value;
    }

    // 如果选择了level，添加level参数
    if (selectedLevel.value) {
      params.level = selectedLevel.value;
    }

    // 如果输入了count，添加count参数
    if (selectedCount.value !== null && selectedCount.value !== undefined) {
      params.count = selectedCount.value;
    }

    // 如果输入了message，添加message参数
    if (selectedMessage.value) {
      params.message = selectedMessage.value;
    }

    const response = await getEventsMenu(params);

    console.log("事件菜单API响应:", response);
    if (response.success && response.data) {
      // 处理菜单字段的数据
      namespaceList.value = response.data.namespace || [];
      kindList.value = response.data.kind || [];
      nameList.value = response.data.name || [];
      reasonList.value = response.data.reason || [];
      reportingComponentList.value = response.data.reportingComponent || [];
      reportingInstanceList.value = response.data.reportingInstance || [];

      // 自动选择每个字段的第一个值（仅在没有选中值时）
      if (namespaceList.value.length > 0 && !selectedNamespace.value) {
        selectedNamespace.value = namespaceList.value[0];
      }

      if (kindList.value.length > 0 && !selectedKind.value) {
        selectedKind.value = kindList.value[0];
      }
      if (nameList.value.length > 0 && !selectedName.value) {
        selectedName.value = nameList.value[0];
      }
      if (reasonList.value.length > 0 && !selectedReason.value) {
        selectedReason.value = reasonList.value[0];
      }
      if (
        reportingComponentList.value.length > 0 &&
        !selectedReportingComponent.value
      ) {
        selectedReportingComponent.value = reportingComponentList.value[0];
      }
      if (
        reportingInstanceList.value.length > 0 &&
        !selectedReportingInstance.value
      ) {
        selectedReportingInstance.value = reportingInstanceList.value[0];
      }

      console.log("处理后的菜单数据:", {
        namespace: namespaceList.value,
        kind: kindList.value,
        name: nameList.value,
        reason: reasonList.value,
        reportingComponent: reportingComponentList.value,
        reportingInstance: reportingInstanceList.value
      });

      eventsMenuData.value = response.data;
    } else {
      // 清空菜单数据
      namespaceList.value = [];
      kindList.value = [];
      nameList.value = [];
      reasonList.value = [];
      reportingComponentList.value = [];
      reportingInstanceList.value = [];
      eventsMenuData.value = null;
      ElMessage.warning("未查询到相关事件数据");
    }
  } catch (error) {
    console.error("加载事件菜单失败:", error);
    ElMessage.error("加载事件菜单失败");
    // 清空菜单数据
    namespaceList.value = [];
    kindList.value = [];
    nameList.value = [];
    reasonList.value = [];
    reportingComponentList.value = [];
    reportingInstanceList.value = [];
    eventsMenuData.value = null;
  } finally {
    loading.value = false;
  }
};

// 事件处理函数
const onDateRangeChange = () => {
  eventsMenuData.value = null;

  // 如果有K8S和时间范围，重新加载事件菜单数据
  if (selectedK8s.value && dateRange.value) {
    loadEventsMenu();
  }
};

const onK8sChange = () => {
  // 清空菜单数据但不清空选中值
  namespaceList.value = [];
  kindList.value = [];
  nameList.value = [];
  reasonList.value = [];
  reportingComponentList.value = [];
  reportingInstanceList.value = [];
  eventsMenuData.value = null;

  // 当选择K8S时，如果有时间范围，则加载事件菜单数据
  if (selectedK8s.value && dateRange.value) {
    loadEventsMenu();
  }
};

const onNamespaceChange = () => {
  // 清空事件菜单数据但不清空选中值
  eventsMenuData.value = null;

  // 如果有K8S和时间范围，重新加载事件菜单数据
  if (selectedK8s.value && dateRange.value) {
    loadEventsMenu();
  }
};

// 监听 K8S 选择变化，更新 store
watch(
  () => selectedK8s.value,
  newVal => {
    if (newVal) {
      searchStore.setEnv(newVal);
    }
  }
);

// 组件挂载时加载数据
onMounted(() => {
  loadK8sList();

  // 设置默认时间范围为今天（使用本地时间）
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");
  const todayStr = `${year}-${month}-${day}`;
  dateRange.value = [todayStr, todayStr];
});
</script>

<style scoped>
.events-container {
  padding: 8px;
}

.filter-menu {
  margin-bottom: 20px;
}

.filter-card {
  border-radius: 8px;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.filter-label {
  font-weight: 500;
  color: var(--el-text-color-regular);
  white-space: nowrap;
}

/* 高级筛选区域样式 */
.advanced-filters {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e4e7ed;
}

/* 展开/收起按钮样式 */
.toggle-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #409eff;
  font-size: 14px;
  padding: 4px 4px;
}

.toggle-btn:hover {
  color: #66b1ff;
}

.toggle-icon {
  transition: transform 0.3s ease;
}

.toggle-icon.is-expanded {
  transform: rotate(180deg);
}

.events-menu {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.menu-content {
  max-height: 600px;
  overflow-y: auto;
}

.menu-section {
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.menu-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
}

.menu-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0 0 12px 0;
}

.menu-items {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.menu-tag {
  margin: 2px;
}

.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 300px;
}

/* 响应式设计 */
@media screen and (max-width: 768px) {
  .filter-row {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-item {
    flex-direction: column;
    align-items: stretch;
    gap: 4px;
  }

  .filter-label {
    font-size: 14px;
  }
}

/* 事件表格样式 */
.events-table {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.event-count {
  font-size: 14px;
  color: #909399;
}

.no-data {
  margin-top: 20px;
  text-align: center;
  padding: 40px 0;
}

/* 覆盖全局main-content的margin设置，只影响当前页面 */
.events-page {
  margin: 0px !important;
  /* 抵消父级的24px margin，设置为10px效果 */
  padding: 10px;
}
</style>
