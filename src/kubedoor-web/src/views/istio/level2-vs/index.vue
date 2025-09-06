<template>
  <div class="main">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>二级VirtualService 管理</span>
        </div>
      </template>
      <div class="content">
        <p>二级VirtualService 管理页面正在开发中...</p>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
defineOptions({
  name: "Level2VirtualService"
});
</script>

<style scoped>
.main {
  margin: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.content {
  padding: 20px;
  text-align: center;
  color: #666;
}
</style>
