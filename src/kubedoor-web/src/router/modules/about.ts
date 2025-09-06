export default {
  path: "/about",
  name: "about",
  component: () => import("@/views/workbench/about.vue"),
  meta: {
    title: "关于",
    icon: "ep:info-filled",
    rank: 999, // 设置为最大值，确保显示在菜单最后
    showLink: true
  }
} satisfies RouteConfigsTable;
