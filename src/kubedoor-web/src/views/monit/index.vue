<template>
  <div class="realtime-monitor-container">
    <!-- 搜索表单 -->
    <div class="search-section">
      <el-form :model="searchForm" inline style="margin-bottom: -18px">
        <el-form-item label="K8S">
          <el-select
            v-model="searchForm.env"
            placeholder="请选择K8S环境"
            class="!w-[180px]"
            filterable
            @change="handleEnvChange"
          >
            <el-option
              v-for="item in envOptions"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="命名空间">
          <el-select
            v-model="searchForm.ns"
            placeholder="请选择命名空间"
            class="!w-[180px]"
            filterable
            clearable
            @change="handleSearch"
          >
            <el-option
              v-for="item in nsOptions"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="关键字">
          <el-input
            v-model="searchForm.keyword"
            placeholder="请输入关键字"
            clearable
            @keyup.enter="handleSearch"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            :disabled="!searchForm.env"
            @click="handleSearch"
          >
            搜索
          </el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 表格数据 -->
    <!-- 更新弹窗 -->
    <el-dialog v-model="updateDialogVisible" title="更新镜像" width="500px">
      <el-form :model="updateForm" label-width="80px">
        <el-form-item label="镜像标签">
          <el-input
            v-model="updateForm.imageTag"
            placeholder="请输入镜像标签"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="updateDialogVisible = false">取消</el-button>
          <el-button
            type="primary"
            :loading="updateLoading"
            @click="handleUpdate"
          >
            确定
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- Pod日志查看弹窗 -->
    <el-dialog
      v-model="logDialogVisible"
      width="99%"
      top="0.5vh"
      :style="{ 'padding-top': '7px' }"
      :close-on-click-modal="false"
      @close="stopLogStream"
    >
      <template #header>
        <div class="log-dialog-header">
          <div class="log-controls-header">
            <el-button
              v-if="!isLogConnected"
              type="primary"
              size="small"
              :loading="logConnecting"
              @click="startLogStream"
            >
              开始查看日志
            </el-button>
            <el-button v-else type="danger" size="small" @click="stopLogStream">
              停止查看
            </el-button>
            <el-button size="small" @click="clearLogs">清空日志</el-button>
            <el-button size="small" @click="scrollToBottom"
              >滚动到底部</el-button
            >
            <div class="log-status">
              <span
                :class="{
                  'status-connected': isLogConnected,
                  'status-disconnected': !isLogConnected
                }"
              >
                {{ isLogConnected ? "已连接" : "未连接" }}
              </span>
            </div>
            <!-- 日志搜索功能 -->
            <div class="log-search-container">
              <el-input
                v-model="searchKeyword"
                placeholder="搜索日志内容"
                size="small"
                style="width: 200px; margin-right: 8px"
                @keyup.enter="() => performSearch(true)"
              >
                <template #append>
                  <el-button size="small" @click="() => performSearch(true)">
                    搜索
                  </el-button>
                </template>
              </el-input>
              <el-button
                size="small"
                :type="isFilterMode ? 'primary' : 'default'"
                :disabled="!searchKeyword.trim() || totalMatches === 0"
                @click="toggleFilterMode"
              >
                {{ isFilterMode ? "取消筛选" : "筛选" }}
              </el-button>
              <span v-if="totalMatches > 0" class="search-info">
                {{ currentMatchIndex + 1 }}/{{ totalMatches }}
              </span>
              <el-button
                size="small"
                :disabled="totalMatches === 0"
                @click="goToPreviousMatch"
              >
                上一个
              </el-button>
              <el-button
                size="small"
                :disabled="totalMatches === 0"
                @click="goToNextMatch"
              >
                下一个
              </el-button>
              <el-button size="small" type="warning" @click="getPreviousLogs">
                重启前日志
              </el-button>
            </div>
          </div>
          <span class="dialog-title"
            >Pod日志: {{ currentPodInfo.env }}【{{
              currentPodInfo.namespace
            }}】{{ currentPodInfo.name }}</span
          >
        </div>
      </template>
      <div class="log-container">
        <div
          ref="logContentRef"
          v-loading="logConnecting"
          class="log-content"
          element-loading-text="正在连接日志流..."
          @scroll="handleScroll"
        >
          <div v-if="logMessages.length === 0" class="no-logs">
            暂无日志数据
          </div>
          <div
            v-for="(message, index) in filteredLogMessages"
            :key="getLogKey(message, index)"
            class="log-line"
            :class="{
              'log-error':
                message.includes('ERROR') || message.includes('Exception'),
              'log-warn': message.includes('WARN'),
              'log-info': message.includes('INFO')
            }"
            v-html="
              highlightSearchKeyword(message, getOriginalIndex(message, index))
            "
          />
        </div>
      </div>
    </el-dialog>

    <div class="mt-2">
      <el-card v-loading="loading">
        <el-table
          class="hide-expand"
          :data="filteredTableData"
          style="width: 100%"
          stripe
          border
          :default-sort="{ prop: 'podCount', order: 'descending' }"
          row-key="id"
          :expand-row-keys="expandedRowKeys"
        >
          <el-table-column
            prop="env"
            label="K8S"
            min-width="100"
            show-overflow-tooltip
          />
          <el-table-column
            prop="namespace"
            label="命名空间"
            min-width="80"
            show-overflow-tooltip
          />
          <el-table-column
            prop="deployment"
            label="微服务"
            min-width="140"
            show-overflow-tooltip
          />
          <el-table-column
            prop="podCount"
            label="POD"
            min-width="80"
            align="center"
            sortable
          >
            <template #header>
              <span style="color: #409eff">POD</span>
            </template>
            <template #default="scope">
              <span style="font-weight: bold; color: #409eff">{{
                scope.row.podCount
              }}</span>
            </template>
          </el-table-column>

          <el-table-column label="明细" min-width="80" align="center">
            <template #default="scope">
              <el-button
                type="primary"
                size="small"
                plain
                @click.stop="handlePodDetail(scope.row)"
              >
                明细
              </el-button>
            </template>
          </el-table-column>

          <el-table-column type="expand" width="1">
            <template #default="scope">
              <div
                v-loading="scope.row.podsLoading"
                class="pod-detail-container"
              >
                <el-table
                  v-if="scope.row.pods && scope.row.pods.length > 0"
                  :data="scope.row.pods"
                  border
                  style="width: 100%"
                >
                  <el-table-column
                    prop="name"
                    label="名称"
                    min-width="200"
                    show-overflow-tooltip
                    align="center"
                  >
                    <template #default="podScope">
                      <div
                        style="
                          overflow: hidden;
                          text-align: left;
                          text-overflow: ellipsis;
                          white-space: nowrap;
                          direction: rtl;
                        "
                      >
                        {{ podScope.row.name }}
                      </div>
                    </template>
                  </el-table-column>

                  <el-table-column
                    prop="status"
                    label="状态"
                    min-width="80"
                    align="center"
                  >
                    <template #default="podScope">
                      <el-tag
                        :type="
                          podScope.row.status === 'Running'
                            ? 'success'
                            : 'danger'
                        "
                      >
                        {{ podScope.row.status }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column
                    prop="ready"
                    label="就绪"
                    min-width="60"
                    align="center"
                  >
                    <template #default="podScope">
                      <el-tag
                        :type="podScope.row.ready ? 'success' : 'warning'"
                      >
                        {{ podScope.row.ready ? "是" : "否" }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column
                    prop="pod_ip"
                    label="Pod IP"
                    min-width="120"
                    align="center"
                    show-overflow-tooltip
                  />
                  <el-table-column
                    prop="cpu"
                    label="CPU"
                    min-width="80"
                    align="center"
                    sortable
                  />
                  <el-table-column
                    prop="memory"
                    label="内存"
                    min-width="80"
                    align="center"
                    sortable
                  />
                  <el-table-column
                    prop="created_at"
                    label="创建时间"
                    min-width="160"
                    align="center"
                    sortable
                  />
                  <el-table-column
                    prop="node_name"
                    label="节点名称"
                    min-width="110"
                    show-overflow-tooltip
                    align="center"
                    sortable
                  />
                  <el-table-column
                    prop="app_label"
                    label="应用标签"
                    min-width="150"
                    align="center"
                    show-overflow-tooltip
                    sortable
                  >
                    <template #default="podScope">
                      <div
                        style="
                          overflow: hidden;
                          text-align: left;
                          text-overflow: ellipsis;
                          white-space: nowrap;
                          direction: rtl;
                        "
                      >
                        {{ podScope.row.app_label }}
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column
                    prop="image"
                    label="镜像标签"
                    min-width="300"
                    show-overflow-tooltip
                    align="center"
                    sortable
                  >
                    <template #default="podScope">
                      <div
                        style="
                          overflow: hidden;
                          text-align: left;
                          text-overflow: ellipsis;
                          white-space: nowrap;
                          direction: rtl;
                        "
                      >
                        {{ podScope.row.image }}
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column
                    prop="restart_count"
                    label="重启"
                    min-width="60"
                    align="center"
                  />
                  <el-table-column
                    prop="restart_reason"
                    label="重启原因"
                    min-width="130"
                    align="center"
                    show-overflow-tooltip
                  />
                  <el-table-column
                    prop="exception_reason"
                    label="异常状态原因"
                    min-width="150"
                    show-overflow-tooltip
                  />
                  <el-table-column
                    label="操作"
                    width="80"
                    align="center"
                    fixed="right"
                  >
                    <template #default="podScope">
                      <el-dropdown>
                        <el-button type="primary" size="small">
                          操作
                        </el-button>
                        <template #dropdown>
                          <el-dropdown-menu>
                            <el-dropdown-item
                              @click="
                                handleViewLogs(
                                  scope.row.env,
                                  scope.row.namespace,
                                  podScope.row.name
                                )
                              "
                              >日志</el-dropdown-item
                            >
                            <el-dropdown-item
                              @click="
                                handleModifyPod(
                                  scope.row.env,
                                  scope.row.namespace,
                                  podScope.row.name
                                )
                              "
                              >隔离</el-dropdown-item
                            >
                            <el-dropdown-item
                              @click="
                                handleDeletePod(
                                  scope.row.env,
                                  scope.row.namespace,
                                  podScope.row.name
                                )
                              "
                              >删除</el-dropdown-item
                            >
                            <el-dropdown-item
                              @click="
                                handleAutoDump(
                                  scope.row.env,
                                  scope.row.namespace,
                                  podScope.row.name
                                )
                              "
                              >Dump</el-dropdown-item
                            >
                            <el-dropdown-item
                              @click="
                                handleAutoJstack(
                                  scope.row.env,
                                  scope.row.namespace,
                                  podScope.row.name
                                )
                              "
                              >Jstack</el-dropdown-item
                            >
                            <el-dropdown-item
                              @click="
                                handleAutoJfr(
                                  scope.row.env,
                                  scope.row.namespace,
                                  podScope.row.name
                                )
                              "
                              >JFR</el-dropdown-item
                            >
                            <el-dropdown-item
                              @click="
                                handleAutoJvmMem(
                                  scope.row.env,
                                  scope.row.namespace,
                                  podScope.row.name
                                )
                              "
                              >JVM</el-dropdown-item
                            >
                          </el-dropdown-menu>
                        </template>
                      </el-dropdown>
                    </template>
                  </el-table-column>
                </el-table>
                <div v-else-if="!scope.row.podsLoading" class="no-data">
                  暂无Pod数据
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column
            prop="avgCpu"
            label="平均CPU"
            min-width="110"
            align="center"
            sortable
          >
            <template #default="scope"> {{ scope.row.avgCpu }}m </template>
          </el-table-column>
          <el-table-column
            prop="maxCpu"
            label="最大CPU"
            min-width="110"
            align="center"
            sortable
          >
            <template #header>
              <span style="color: #f56c6c">最大CPU</span>
            </template>
            <template #default="scope">
              <span style="font-weight: bold; color: #f56c6c"
                >{{ scope.row.maxCpu }}m</span
              >
            </template>
          </el-table-column>
          <el-table-column
            prop="requestCpu"
            label="需求CPU"
            min-width="110"
            align="center"
            sortable
          >
            <template #default="scope"> {{ scope.row.requestCpu }}m </template>
          </el-table-column>
          <el-table-column
            prop="limitCpu"
            label="限制CPU"
            min-width="110"
            align="center"
            sortable
          >
            <template #header>
              <span style="color: #409eff">限制CPU</span>
            </template>
            <template #default="scope">
              <span style="font-weight: bold; color: #409eff"
                >{{ scope.row.limitCpu }}m</span
              >
            </template>
          </el-table-column>
          <el-table-column
            prop="avgMem"
            label="平均MEM"
            min-width="110"
            align="center"
            sortable
          >
            <template #default="scope"> {{ scope.row.avgMem }}MB </template>
          </el-table-column>

          <el-table-column
            prop="maxMem"
            label="最大MEM"
            min-width="110"
            align="center"
            sortable
          >
            <template #header>
              <span style="color: #f56c6c">最大MEM</span>
            </template>
            <template #default="scope">
              <span style="font-weight: bold; color: #f56c6c"
                >{{ scope.row.maxMem }}MB</span
              >
            </template>
          </el-table-column>

          <el-table-column
            prop="requestMem"
            label="需求MEM"
            min-width="110"
            align="center"
            sortable
          >
            <template #default="scope"> {{ scope.row.requestMem }}MB </template>
          </el-table-column>

          <el-table-column
            prop="limitMem"
            label="限制MEM"
            min-width="110"
            align="center"
            sortable
          >
            <template #header>
              <span style="color: #409eff">限制MEM</span>
            </template>
            <template #default="scope">
              <span style="font-weight: bold; color: #409eff">
                {{ scope.row.limitMem }}MB
              </span>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="80" align="center">
            <template #default="scope">
              <el-dropdown>
                <el-button type="primary" size="small" plain>
                  操作
                  <el-icon class="el-icon--right"><arrow-down /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item @click="handleCapacity(scope.row)"
                      >扩缩容</el-dropdown-item
                    >
                    <el-dropdown-item @click="onReboot(scope.row)"
                      >重启</el-dropdown-item
                    >
                    <el-dropdown-item @click="openUpdateDialog(scope.row)"
                      >更新</el-dropdown-item
                    >
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
    <el-dialog
      v-model="resultDialogVisible"
      title="操作结果"
      class="alarm-result-dialog"
      :width="
        currentOperation === 'jstack' || currentOperation === 'dump'
          ? '95%'
          : '700px'
      "
      :top="
        currentOperation === 'jstack' || currentOperation === 'dump'
          ? '2.5vh'
          : '15vh'
      "
      destroy-on-close
    >
      <pre
        class="result-content"
        :style="
          currentOperation === 'jstack' || currentOperation === 'dump'
            ? { 'max-height': '82vh', 'overflow-y': 'auto' }
            : { 'max-height': '600px', 'overflow-y': 'auto' }
        "
        v-html="resultMessage"
      />
      <template #footer>
        <el-button type="primary" @click="handleCopyAndClose">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import {
  ref,
  reactive,
  computed,
  onMounted,
  nextTick,
  h,
  watch,
  onBeforeUnmount
} from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  modifyPod,
  deletePod,
  autoDump,
  autoJstack,
  autoJfr,
  autoJvmMem,
  updateOperate
} from "@/api/alarm";
import { ArrowDown } from "@element-plus/icons-vue";
import {
  getPromEnv,
  getPromNamespace,
  getPromQueryData,
  getPodData,
  showAddLabel,
  getPodPreviousLogs,
  createPodLogStreamUrl
} from "@/api/monit";
import { useResource } from "./utils/hook";
import { useSearchStoreHook } from "@/store/modules/search";
import { AnsiUp } from "ansi_up";

const { onChangeCapacity, onReboot, onUpdateImage } = useResource();
const searchStore = useSearchStoreHook();

// 定义表单数据
const searchForm = reactive({
  env: searchStore.env,
  ns: searchStore.namespace,
  keyword: ""
});

// 定义选项数据
const envOptions = ref<string[]>([]);
const nsOptions = ref<string[]>([]);

// 表格数据
const tableData = ref<any[]>([]);
const filteredTableData = ref<any[]>([]);
// const filteredTableData = computed(() => {
//   if (!searchForm.keyword) {
//     return tableData.value;
//   }

//   const keyword = searchForm.keyword.toLowerCase();
//   return tableData.value.filter(
//     item =>
//       item.env.toLowerCase().includes(keyword) ||
//       (item.namespace && item.namespace.toLowerCase().includes(keyword)) ||
//       (item.deployment && item.deployment.toLowerCase().includes(keyword))
//   );
// });

// 展开行相关
const expandedRowKeys = ref<string[]>([]);

// 处理Pod详情
const handlePodDetail = async (row: any) => {
  // 如果已经加载过Pod数据，直接展开/收起行
  if (expandedRowKeys.value.includes(row.id)) {
    expandedRowKeys.value = expandedRowKeys.value.filter(id => id !== row.id);
    return;
  }

  // 设置唯一ID用于展开行
  if (!row.id) {
    row.id = `${row.env}-${row.namespace}-${row.deployment}`;
  }

  // 设置加载状态
  row.podsLoading = true;

  try {
    const res = await getPodData(row.env, row.namespace, row.deployment);
    if (res.pods) {
      row.pods = res.pods;
    } else {
      row.pods = [];
    }
    // 展开行
    expandedRowKeys.value.push(row.id);
  } catch (error) {
    console.error("获取Pod数据失败:", error);
    ElMessage.error("获取Pod数据失败");
    row.pods = [];
  } finally {
    row.podsLoading = false;
  }
};

// 加载状态
const loading = ref(false);

// 更新弹窗相关
const updateDialogVisible = ref(false);
const updateLoading = ref(false);
const selectedDeployment = ref<any>(null);
const updateForm = reactive({
  imageTag: ""
});

const openUpdateDialog = (row: any) => {
  selectedDeployment.value = row;
  updateForm.imageTag = "";
  updateDialogVisible.value = true;
};

const handleUpdate = async () => {
  if (!updateForm.imageTag) {
    ElMessage.warning("请输入镜像标签");
    return;
  }

  updateLoading.value = true;
  try {
    await onUpdateImage(selectedDeployment.value.env, {
      deployment: selectedDeployment.value.deployment,
      namespace: selectedDeployment.value.namespace,
      image_tag: updateForm.imageTag
    });
    updateDialogVisible.value = false;
    handleSearch();
  } finally {
    updateLoading.value = false;
  }
};

// 获取K8S环境列表
const getEnvOptions = async (): Promise<void> => {
  try {
    const res = await getPromEnv();
    if (res.data && res.data.length > 0) {
      envOptions.value = res.data.map(item => item);
      // 如果 store 中有值且存在于选项中，则使用 store 中的值
      if (searchStore.env && envOptions.value.includes(searchStore.env)) {
        searchForm.env = searchStore.env;
        await getNsOptions(searchStore.env);
      } else {
        searchForm.env = res.data[0];
        await getNsOptions(res.data[0]);
      }
    }
    return Promise.resolve();
  } catch (error) {
    console.error("获取K8S环境列表失败:", error);
    ElMessage.error("获取K8S环境列表失败");
    return Promise.reject(error);
  }
};

// 处理环境变化
const handleEnvChange = async (val: string) => {
  searchForm.ns = "";
  searchStore.setEnv(val);
  if (val) {
    await getNsOptions(val);
    handleSearch();
  } else {
    tableData.value = [];
  }
};

// 获取命名空间列表
const getNsOptions = async (env: string): Promise<void> => {
  if (!env) {
    nsOptions.value = [];
    return Promise.resolve();
  }

  try {
    const res = await getPromNamespace(env);
    if (res.data) {
      nsOptions.value = res.data.map(item => item);
      if (
        searchStore.namespace &&
        nsOptions.value.includes(searchStore.namespace)
      ) {
        searchForm.ns = searchStore.namespace;
      } else {
        searchForm.ns = res.data[0];
        searchStore.setNamespace(res.data[0]);
      }
    }
    return Promise.resolve();
  } catch (error) {
    console.error("获取命名空间列表失败:", error);
    ElMessage.error("获取命名空间列表失败");
    return Promise.reject(error);
  }
};

// 处理搜索
const handleSearch = async () => {
  if (!searchForm.env) {
    ElMessage.warning("请选择K8S环境");
    return;
  }
  searchStore.setNamespace(searchForm.ns);

  loading.value = true;
  try {
    const res = await getPromQueryData(searchForm.env, searchForm.ns);
    if (res.data) {
      tableData.value = res.data.map(item => {
        const env = item[0] || "-";
        const namespace = item[1] || "-";
        const deployment = item[2] || "-";

        return {
          id: `${env}-${namespace}-${deployment}`,
          env,
          namespace,
          deployment,
          podCount: item[3] || 0,
          avgCpu: item[4] ? Math.round(item[4]) : 0,
          maxCpu: item[5] ? Math.round(item[5]) : 0,
          requestCpu: item[6] ? Math.round(item[6]) : 0,
          limitCpu: item[7] ? Math.round(item[7]) : 0,
          avgMem: item[8] ? Math.round(item[8]) : 0,
          maxMem: item[9] ? Math.round(item[9]) : 0,
          requestMem: item[10] ? Math.round(item[10]) : 0,
          limitMem: item[11] ? Math.round(item[11]) : 0,
          pods: [],
          podsLoading: false
        };
      });
    } else {
      tableData.value = [];
    }

    const keyword = searchForm.keyword.toLowerCase();

    if (!searchForm.keyword) {
      filteredTableData.value = tableData.value;
    } else {
      filteredTableData.value = tableData.value.filter(
        item =>
          item.env.toLowerCase().includes(keyword) ||
          (item.namespace && item.namespace.toLowerCase().includes(keyword)) ||
          (item.deployment && item.deployment.toLowerCase().includes(keyword))
      );
    }
  } catch (error) {
    console.error("获取监控数据失败:", error);
    ElMessage.error("获取监控数据失败");
    tableData.value = [];
  } finally {
    loading.value = false;
  }
};

// 处理重置
const handleReset = async () => {
  searchForm.env = envOptions.value[0] || "";
  searchForm.keyword = "";
  searchStore.clearStorage();
  await handleEnvChange(envOptions.value[0]);
};

const handleCapacity = async (row: any) => {
  await onChangeCapacity(row);
  // handleSearch();
};

const resultDialogVisible = ref(false);
const resultMessage = ref("");
const currentOperation = ref(""); // 当前操作类型

// 日志查看相关
const logDialogVisible = ref(false);
const logMessages = ref<string[]>([]);
const isLogConnected = ref(false);
const logConnecting = ref(false);
const logSocket = ref<WebSocket | null>(null);
const logContentRef = ref<HTMLElement | null>(null);
const isUserScrolling = ref(false); // 用户是否在手动滚动
const currentPodInfo = ref({
  name: "",
  env: "",
  namespace: ""
});

// 日志搜索相关
const searchKeyword = ref("");
const searchMatches = ref<number[]>([]);
const currentMatchIndex = ref(-1);
const totalMatches = ref(0);
const isFilterMode = ref(false); // 筛选模式状态

// 筛选后的日志消息
const filteredLogMessages = computed(() => {
  if (!isFilterMode.value || !searchKeyword.value.trim()) {
    return logMessages.value;
  }

  const keyword = searchKeyword.value.toLowerCase();
  return logMessages.value.filter(message =>
    message.toLowerCase().includes(keyword)
  );
});

// 获取日志的唯一key
const getLogKey = (message: string, index: number) => {
  if (isFilterMode.value) {
    // 筛选模式下，使用消息内容的hash作为key
    return `${message.slice(0, 50)}-${index}`;
  }
  return index;
};

// 获取原始索引（用于高亮显示）
const getOriginalIndex = (message: string, filteredIndex: number) => {
  if (!isFilterMode.value) {
    return filteredIndex;
  }

  // 在筛选模式下，找到该消息在原始数组中的索引
  return logMessages.value.findIndex(msg => msg === message);
};

// 获取筛选后的索引（用于DOM定位）
const getFilteredIndex = (originalIndex: number) => {
  if (!isFilterMode.value) {
    return originalIndex;
  }

  // 在筛选模式下，找到原始索引对应的消息在筛选数组中的位置
  const targetMessage = logMessages.value[originalIndex];
  return filteredLogMessages.value.findIndex(msg => msg === targetMessage);
};

// 切换筛选模式
const toggleFilterMode = () => {
  isFilterMode.value = !isFilterMode.value;

  // 如果开启筛选模式，重新执行搜索以更新匹配项
  if (isFilterMode.value && searchKeyword.value.trim()) {
    performSearch(true);
  }
};

const showResultDialog = (message: string, operation: string = "") => {
  resultMessage.value = `<div style="white-space: pre-wrap; word-break: break-all;">${message}</div>`;
  currentOperation.value = operation;
  resultDialogVisible.value = true;
};

// Pod操作相关函数
const handleModifyPod = async (env: string, namespace: string, pod: string) => {
  try {
    const scalePodRef = ref(false);
    const addLabelRef = ref(false);
    const shouldShowAddLabel = ref(false);
    const scaleStrategyRef = ref("cpu"); // 默认选择CPU策略

    // 检查是否需要显示已开启固定节点均衡模式选项
    try {
      const labelResult = await showAddLabel(env, namespace);
      shouldShowAddLabel.value =
        labelResult.data && labelResult.data.length > 0;
      if (shouldShowAddLabel.value) {
        addLabelRef.value = true; // 如果需要显示，默认勾选
      }
    } catch (error) {
      console.error("检查固定节点均衡模式失败:", error);
      shouldShowAddLabel.value = false;
    }

    // 创建固定节点均衡模式选项的容器
    const addLabelContainer = h(
      "div",
      {
        id: "addLabelContainer",
        style: "display: none; margin-left: 24px; flex-direction: column;"
      },
      [
        h(
          "div",
          { style: "margin-bottom: 8px; display: flex; align-items: center;" },
          [
            h("input", {
              type: "checkbox",
              id: "addLabelCheckbox",
              checked: true,
              style: "margin-right: 8px;",
              onChange: (e: Event) => {
                addLabelRef.value = (e.target as HTMLInputElement).checked;
                // 动态显示/隐藏扩缩容策略选项
                const strategyContainer =
                  document.getElementById("strategyContainer");
                if (strategyContainer) {
                  strategyContainer.style.display = addLabelRef.value
                    ? "block"
                    : "none";
                }
              }
            }),
            h(
              "label",
              { for: "addLabelCheckbox", style: "color: #f56c6c;" },
              "已开启固定节点均衡模式"
            )
          ]
        ),
        h(
          "div",
          {
            id: "strategyContainer",
            style: "margin-left: 0px; margin-top: 8px; display: block;"
          },
          [
            h(
              "div",
              { style: "margin-bottom: 4px; font-size: 14px; color: #606266;" },
              "扩缩容策略:"
            ),
            h("div", { style: "display: flex; gap: 16px;" }, [
              h(
                "label",
                {
                  style: "display: flex; align-items: center; cursor: pointer;"
                },
                [
                  h("input", {
                    type: "radio",
                    name: "scaleStrategy",
                    value: "cpu",
                    checked: true,
                    style: "margin-right: 4px;",
                    onChange: () => {
                      scaleStrategyRef.value = "cpu";
                    }
                  }),
                  h("span", "节点CPU")
                ]
              ),
              h(
                "label",
                {
                  style: "display: flex; align-items: center; cursor: pointer;"
                },
                [
                  h("input", {
                    type: "radio",
                    name: "scaleStrategy",
                    value: "mem",
                    style: "margin-right: 4px;",
                    onChange: () => {
                      scaleStrategyRef.value = "mem";
                    }
                  }),
                  h("span", "节点内存")
                ]
              )
            ])
          ]
        )
      ]
    );

    const messageElements = [
      h("p", { style: "margin-bottom: 16px;" }, "确认要隔离该Pod吗？"),
      h(
        "div",
        { style: "display: flex; align-items: center; margin-bottom: 12px;" },
        [
          h("input", {
            type: "checkbox",
            id: "scalePodCheckbox",
            style: "margin-right: 8px;",
            onChange: (e: Event) => {
              scalePodRef.value = (e.target as HTMLInputElement).checked;
              // 动态显示/隐藏固定节点均衡模式选项
              const container = document.getElementById("addLabelContainer");
              if (container) {
                container.style.display =
                  scalePodRef.value && shouldShowAddLabel.value
                    ? "flex"
                    : "none";
              }
            }
          }),
          h("label", { for: "scalePodCheckbox" }, "临时扩容1个Pod")
        ]
      ),
      addLabelContainer
    ];

    await ElMessageBox({
      title: "提示",
      message: h("div", messageElements),
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      type: "warning",
      showCancelButton: true
    });

    const params: any = {
      env: env,
      ns: namespace,
      pod_name: pod
    };

    if (scalePodRef.value) {
      params.scale_pod = true;
      // 如果勾选了临时扩容且需要显示固定节点均衡模式，则传递add_label参数
      if (shouldShowAddLabel.value && addLabelRef.value) {
        params.add_label = true;
        params.type = scaleStrategyRef.value; // 传递扩缩容策略类型
      }
    }

    const res = await modifyPod(params);
    if (res.success) {
      ElMessage.success("操作成功");
      showResultDialog(res.message, "modify");
      handleSearch(); // 刷新数据
    } else {
      ElMessage.error("操作失败");
    }
  } catch (error) {
    console.error(error);
  }
};

const handleDeletePod = async (env: string, namespace: string, pod: string) => {
  try {
    await ElMessageBox.confirm("确认要删除该Pod吗？", "提示", {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      type: "warning"
    });
    const res = await deletePod({
      env: env,
      ns: namespace,
      pod_name: pod
    });
    if (res.success) {
      ElMessage.success("操作成功");
      handleSearch(); // 刷新数据
    } else {
      ElMessage.error("操作失败");
    }
  } catch (error) {
    console.error(error);
  }
};

const handleAutoDump = async (env: string, namespace: string, pod: string) => {
  try {
    await ElMessageBox.confirm("确认要对该Pod执行Dump吗？", "提示", {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      type: "warning"
    });
    const res = await autoDump({
      env: env,
      ns: namespace,
      pod_name: pod
    });
    if (res.success) {
      showResultDialog(res.message, "dump");
      ElMessage.success("操作成功");
    } else {
      ElMessage.error("操作失败");
    }
  } catch (error) {
    console.error(error);
  }
};

const handleAutoJstack = async (
  env: string,
  namespace: string,
  pod: string
) => {
  try {
    await ElMessageBox.confirm("确认要对该Pod执行Jstack吗？", "提示", {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      type: "warning"
    });
    const res = await autoJstack({
      env: env,
      ns: namespace,
      pod_name: pod
    });
    if (res.success) {
      showResultDialog(res.message, "jstack");
      ElMessage.success("操作成功");
    } else {
      ElMessage.error("操作失败");
    }
  } catch (error) {
    console.error(error);
  }
};

const handleAutoJfr = async (env: string, namespace: string, pod: string) => {
  try {
    await ElMessageBox.confirm("确认要对该Pod执行JFR吗？", "提示", {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      type: "warning"
    });
    const res = await autoJfr({
      env: env,
      ns: namespace,
      pod_name: pod
    });
    if (res.success) {
      showResultDialog(res.message, "jfr");
      ElMessage.success("操作成功");
    } else {
      ElMessage.error("操作失败");
    }
  } catch (error) {
    console.error(error);
  }
};

const handleCopyAndClose = () => {
  resultDialogVisible.value = false;
  // try {
  //   // 移除HTML标签，只复制纯文本
  //   const tempDiv = document.createElement("div");
  //   tempDiv.innerHTML = resultMessage.value;
  //   const textContent = tempDiv.textContent || tempDiv.innerText;
  //   await navigator.clipboard.writeText(textContent);
  //   ElMessage.success("复制成功");
  // } catch (err) {
  //   ElMessage.error("复制失败");
  //   console.error("复制失败:", err);
  // }
};

const handleAutoJvmMem = async (
  env: string,
  namespace: string,
  pod: string
) => {
  try {
    await ElMessageBox.confirm("确认要对该Pod执行JVM吗？", "提示", {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      type: "warning"
    });
    const res = await autoJvmMem({
      env: env,
      ns: namespace,
      pod_name: pod
    });
    if (res.success) {
      showResultDialog(res.message, "jvm");
      ElMessage.success("操作成功");
    } else {
      ElMessage.error("操作失败");
    }
  } catch (error) {
    console.error(error);
  }
};

// 日志查看相关函数
const handleViewLogs = (env: string, namespace: string, pod: string) => {
  currentPodInfo.value = {
    name: pod,
    env: env,
    namespace: namespace
  };
  logMessages.value = [];
  logDialogVisible.value = true;
  // 禁用body滚动，防止最外层滚动条滚动
  document.body.style.overflow = "hidden";
};

const startLogStream = () => {
  if (logSocket.value) {
    logSocket.value.close();
  }

  logConnecting.value = true;
  logMessages.value = [];

  // 使用API函数构建WebSocket URL
  const wsUrl = createPodLogStreamUrl(
    currentPodInfo.value.env,
    currentPodInfo.value.namespace,
    currentPodInfo.value.name
  );

  logSocket.value = new WebSocket(wsUrl);

  logSocket.value.onopen = () => {
    logConnecting.value = false;
    isLogConnected.value = true;
    ElMessage.success("日志连接成功");
  };

  logSocket.value.onmessage = event => {
    // 直接处理纯文本日志消息
    if (event.data && event.data.trim()) {
      logMessages.value.push(event.data);
    }

    // 限制日志条数，避免内存溢出
    if (logMessages.value.length > 1000) {
      logMessages.value = logMessages.value.slice(-800);
    }

    // 只有当用户没有手动滚动或已经在底部时才自动滚动
    nextTick(() => {
      if (!isUserScrolling.value || isAtBottom()) {
        scrollToBottom();
      }
    });
  };

  logSocket.value.onerror = error => {
    console.error("WebSocket错误:", error);
    logConnecting.value = false;
    isLogConnected.value = false;
    ElMessage.error("日志连接失败");
  };

  logSocket.value.onclose = () => {
    logConnecting.value = false;
    isLogConnected.value = false;
  };
};

const stopLogStream = () => {
  if (logSocket.value) {
    logSocket.value.close();
    logSocket.value = null;
  }
  isLogConnected.value = false;
};

const clearLogs = () => {
  logMessages.value = [];
};

const scrollToBottom = () => {
  if (logContentRef.value) {
    logContentRef.value.scrollTop = logContentRef.value.scrollHeight;
    isUserScrolling.value = false; // 手动点击滚动到底部时重置状态
  }
};

// 检查是否在底部
const isAtBottom = () => {
  if (!logContentRef.value) return false;
  const { scrollTop, scrollHeight, clientHeight } = logContentRef.value;
  return scrollTop + clientHeight >= scrollHeight - 10; // 10px 容差
};

// 监听滚动事件
const handleScroll = () => {
  if (!logContentRef.value) return;

  // 如果用户向上滚动，标记为手动滚动状态
  if (!isAtBottom()) {
    isUserScrolling.value = true;
  } else {
    // 如果滚动到底部，重置手动滚动状态
    isUserScrolling.value = false;
  }
};

// 日志搜索相关方法
const performSearch = (forceFirstMatch = false) => {
  if (!searchKeyword.value.trim()) {
    searchMatches.value = [];
    currentMatchIndex.value = -1;
    totalMatches.value = 0;
    return;
  }

  // 记住当前匹配的日志内容，用于在重新搜索后保持位置
  let currentMatchContent = "";
  if (currentMatchIndex.value >= 0 && searchMatches.value.length > 0) {
    const currentLineIndex = searchMatches.value[currentMatchIndex.value];
    const targetMessages = isFilterMode.value
      ? filteredLogMessages.value
      : logMessages.value;
    if (currentLineIndex < targetMessages.length) {
      currentMatchContent = targetMessages[currentLineIndex];
    }
  }

  const matches: number[] = [];
  const keyword = searchKeyword.value.toLowerCase();
  const targetMessages = isFilterMode.value
    ? filteredLogMessages.value
    : logMessages.value;

  targetMessages.forEach((message, index) => {
    if (message.toLowerCase().includes(keyword)) {
      matches.push(index);
    }
  });

  searchMatches.value = matches;
  totalMatches.value = matches.length;

  // 尝试保持当前匹配位置
  let newMatchIndex = 0;
  if (matches.length > 0) {
    if (forceFirstMatch) {
      // 强制定位到第一个匹配项
      newMatchIndex = 0;
    } else if (currentMatchContent) {
      // 尝试找到相同内容的匹配项
      const sameContentIndex = matches.findIndex(
        matchIndex => targetMessages[matchIndex] === currentMatchContent
      );

      if (sameContentIndex >= 0) {
        // 找到相同内容，保持在该位置
        newMatchIndex = sameContentIndex;
      } else {
        // 找不到相同内容，尝试找到最接近的位置
        const oldLineIndex = searchMatches.value[currentMatchIndex.value] || 0;
        let closestIndex = 0;
        let minDistance = Math.abs(matches[0] - oldLineIndex);

        for (let i = 1; i < matches.length; i++) {
          const distance = Math.abs(matches[i] - oldLineIndex);
          if (distance < minDistance) {
            minDistance = distance;
            closestIndex = i;
          }
        }
        newMatchIndex = closestIndex;
      }
    }

    currentMatchIndex.value = newMatchIndex;
    // 如果强制定位到第一个匹配项，或者是首次搜索，或者没有找到相同内容时才自动滚动
    if (forceFirstMatch || !currentMatchContent) {
      scrollToMatch(matches[newMatchIndex]);
    }
  } else {
    currentMatchIndex.value = -1;
  }
};

// 初始化ANSI转HTML转换器
const ansiUp = new AnsiUp();
// 配置为适合深色背景
ansiUp.escape_html = true;
ansiUp.use_classes = false;

// ANSI颜色代码转换为HTML样式
const convertAnsiToHtml = (message: string) => {
  return ansiUp.ansi_to_html(message);
};

const highlightSearchKeyword = (message: string, index: number) => {
  // 首先转换ANSI颜色代码
  let processedMessage = convertAnsiToHtml(message);

  if (!searchKeyword.value.trim()) {
    return processedMessage;
  }

  const keyword = searchKeyword.value;
  // 在筛选模式下，传入的index是原始索引，需要转换为筛选后索引再比较
  // 在搜索模式下，传入的index就是原始索引，直接比较
  let isCurrentMatch = false;
  if (isFilterMode.value) {
    // 筛选模式：将原始索引转换为筛选后索引再比较
    const filteredIndex = getFilteredIndex(index);
    isCurrentMatch =
      searchMatches.value[currentMatchIndex.value] === filteredIndex;
  } else {
    // 搜索模式：直接比较原始索引
    isCurrentMatch = searchMatches.value[currentMatchIndex.value] === index;
  }

  // 检查原始消息内容是否包含关键字（不区分大小写）
  if (!message.toLowerCase().includes(keyword.toLowerCase())) {
    return processedMessage;
  }

  const regex = new RegExp(
    `(${keyword.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`,
    "gi"
  );
  const highlightClass = isCurrentMatch
    ? "search-highlight-current"
    : "search-highlight";

  return processedMessage.replace(
    regex,
    `<span class="${highlightClass}">$1</span>`
  );
};

const goToPreviousMatch = () => {
  if (searchMatches.value.length === 0) return;

  currentMatchIndex.value =
    currentMatchIndex.value > 0
      ? currentMatchIndex.value - 1
      : searchMatches.value.length - 1;

  scrollToMatch(searchMatches.value[currentMatchIndex.value]);
};

const goToNextMatch = () => {
  if (searchMatches.value.length === 0) return;

  currentMatchIndex.value =
    currentMatchIndex.value < searchMatches.value.length - 1
      ? currentMatchIndex.value + 1
      : 0;

  scrollToMatch(searchMatches.value[currentMatchIndex.value]);
};

// 获取重启前日志
const getPreviousLogs = async () => {
  if (
    !currentPodInfo.value.name ||
    !currentPodInfo.value.env ||
    !currentPodInfo.value.namespace
  ) {
    ElMessage.warning("缺少Pod信息，无法获取重启前日志");
    return;
  }

  try {
    // 停止实时日志流
    stopLogStream();

    // 清空当前日志
    clearLogs();

    // 显示加载状态
    logConnecting.value = true;

    // 调用重启前日志API
    const data = await getPodPreviousLogs(
      currentPodInfo.value.env,
      currentPodInfo.value.namespace,
      currentPodInfo.value.name,
      400
    );

    if (data.success && data.message) {
      // 将日志内容按行分割并添加到日志消息中
      const logLines = data.message
        .split("\n")
        .filter(line => line.trim() !== "");
      logMessages.value = logLines;

      ElMessage.success("重启前日志获取成功");

      // 滚动到底部
      nextTick(() => {
        scrollToBottom();
      });
    } else {
      ElMessage.warning(data.message || "获取重启前日志失败");
    }
  } catch (error) {
    console.error("获取重启前日志失败:", error);
    ElMessage.error(`获取重启前日志失败: ${error.message}`);
  } finally {
    logConnecting.value = false;
  }
};

const scrollToMatch = (lineIndex: number) => {
  if (!logContentRef.value) return;

  // 在筛选模式下，lineIndex已经是筛选后的索引，直接使用
  // 在搜索模式下，lineIndex是原始索引，也直接使用
  const logLines = logContentRef.value.querySelectorAll(".log-line");

  if (logLines[lineIndex]) {
    // 计算目标元素的位置
    const targetElement = logLines[lineIndex] as HTMLElement;
    const containerHeight = logContentRef.value.clientHeight;
    const elementTop = targetElement.offsetTop;
    const elementHeight = targetElement.offsetHeight;

    // 计算滚动位置，使目标元素在容器中央显示
    const scrollTop = elementTop - containerHeight / 2 + elementHeight / 2;

    // 使用容器的scrollTop进行滚动，避免影响外层页面
    logContentRef.value.scrollTo({
      top: Math.max(0, scrollTop),
      behavior: "smooth"
    });
  }
};

const closeLogDialog = () => {
  stopLogStream();
  logDialogVisible.value = false;
  logMessages.value = [];
  isUserScrolling.value = false; // 重置滚动状态
  // 重置搜索状态
  searchKeyword.value = "";
  searchMatches.value = [];
  currentMatchIndex.value = -1;
  totalMatches.value = 0;
  isFilterMode.value = false; // 重置筛选模式
  // 恢复body滚动
  document.body.style.overflow = "";
};

// 监听日志容器的滚动事件
watch(
  logContentRef,
  newRef => {
    if (newRef) {
      newRef.addEventListener("scroll", handleScroll);
    }
  },
  { immediate: true }
);

// 监听日志消息变化，自动重新搜索
watch(
  logMessages,
  () => {
    if (searchKeyword.value.trim()) {
      performSearch();
    }
  },
  { deep: true }
);

// 清理事件监听器
onBeforeUnmount(() => {
  if (logContentRef.value) {
    logContentRef.value.removeEventListener("scroll", handleScroll);
  }
  // 确保在组件卸载时恢复body滚动
  document.body.style.overflow = "";
});

// 页面加载时获取环境列表
onMounted(async () => {
  await getEnvOptions();
  // 如果已经有环境值，则执行搜索
  if (searchForm.env) {
    handleSearch();
  }
});
</script>

<style scoped>
.search-section {
  padding: 16px;
  background-color: #fff;
  border-radius: 8px;
}

.el-form-item {
  margin-bottom: 18px;
}

.dialog-footer {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.pod-detail-container {
  padding: 5px;
  background-color: #f5f7fa;
  border-radius: 0;
}

.no-data {
  padding: 20px 0;
  font-size: 14px;
  color: #909399;
  text-align: center;
}

.log-container {
  display: flex;
  flex-direction: column;
  height: 92vh;
}

.log-dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;

  /* 与外层标题栏保持一致 */
  min-height: 28px;
  padding: 4px 0;

  /* 与外层标题栏高度一致 */
  margin: 0;
}

.dialog-title {
  font-size: 12px;

  /* 进一步减小字体 */
  font-weight: 600;
  color: #303133;
}

.log-controls-header {
  display: flex;
  gap: 4px;
  align-items: center;

  /* 进一步减少按钮间距 */
}

.log-controls-header .el-button {
  /* 减小按钮字体 */
  height: 24px !important;
  padding: 4px 8px !important;

  /* 减小按钮内边距 */
  font-size: 11px !important;

  /* 减小按钮高度 */
}

.log-status {
  margin-left: 12px;
}

.status-connected {
  font-weight: bold;
  color: #67c23a;
}

.status-disconnected {
  font-weight: bold;
  color: #f56c6c;
}

.log-content {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
  font-family: Consolas, Monaco, "Courier New", monospace;
  font-size: 13px;
  line-height: 1.4;
  color: #d4d4d4;
  word-break: break-all;
  white-space: pre-wrap;
  background-color: #1e1e1e;
  border-radius: 4px;
}

.no-logs {
  padding: 40px 0;
  font-size: 14px;
  color: #909399;
  text-align: center;
}

.log-line {
  padding: 2px 0;
  margin-bottom: 2px;
}

.log-error {
  padding: 2px 4px;
  color: #f56c6c;
  background-color: rgb(245 108 108 / 10%);
  border-radius: 2px;
}

.log-warn {
  padding: 2px 4px;
  color: #e6a23c;
  background-color: rgb(230 162 60 / 10%);
  border-radius: 2px;
}

.log-info {
  color: #409eff;
}

/* 日志搜索相关样式 */
.log-search-container {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-left: 16px;
}

.log-search-container .el-button {
  height: 24px !important;
  padding: 4px 8px !important;
  font-size: 11px !important;
}

.search-info {
  font-size: 12px;
  color: #606266;
  white-space: nowrap;
}
</style>

<style>
.hide-expand {
  .el-table__expand-icon {
    display: none;
  }
}

/* 搜索高亮样式 - 针对黑色背景优化，必须在非scoped样式中定义 */
.search-highlight {
  padding: 1px 3px;
  color: #000 !important;
  background-color: #ffff00 !important;
  border-radius: 3px;
  font-weight: bold;
  box-shadow: 0 0 2px rgba(255, 255, 0, 0.5);
}

.search-highlight-current {
  padding: 1px 3px;
  font-weight: bold;
  color: #fff !important;
  background-color: #ff6600 !important;
  border-radius: 3px;
  box-shadow: 0 0 4px rgba(255, 102, 0, 0.8);
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 4px rgba(255, 102, 0, 0.8);
  }

  50% {
    box-shadow: 0 0 8px rgba(255, 102, 0, 1);
  }

  100% {
    box-shadow: 0 0 4px rgba(255, 102, 0, 0.8);
  }
}

/* 优化日志弹窗的标题栏样式 */
.el-dialog__header {
  /* 稍微增加高度确保垂直居中 */
  position: relative !important;
  display: flex !important;
  align-items: center !important;
  min-height: 28px !important;
  padding: 0 40px 1px 10px !important;

  /* 减少上下padding，增加右侧空间 */
  margin: 0 !important;

  /* 垂直居中对齐 */
}

/* 禁用对话框遮罩层的滚动条*/
.el-overlay-dialog {
  overflow: hidden !important;
}

.el-dialog__headerbtn {
  position: absolute !important;
  top: 50% !important;

  /* 垂直居中 */
  right: 5px !important;

  /* 完全垂直居中 */
  z-index: 10 !important;
  width: 24px !important;
  height: 24px !important;

  /* 将X按钮更靠右 */
  transform: translateY(-50%) !important;
}

.el-dialog__title {
  flex: 1 !important;
  padding: 0 !important;
  margin: 0 !important;
  font-size: 12px !important;
  line-height: 1.2 !important;

  /* 占据剩余空间 */
}
</style>
