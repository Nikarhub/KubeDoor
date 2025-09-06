import { $t } from "@/plugins/i18n";

export default {
  path: "/istio",
  redirect: "/istio/level1-vs",
  meta: {
    icon: "ep:connection",
    title: $t("menus.istioManagement"),
    rank: 40
  },
  children: [
    {
      path: "/istio/level1-vs",
      name: "Level1VirtualService",
      component: () => import("@/views/istio/level1-vs/index.vue"),
      meta: {
        title: $t("menus.level1VirtualService"),
        icon: "ep:share"
      }
    },
    {
      path: "/istio/level1-vs/detail/:id",
      name: "Level1VirtualServiceDetail",
      component: () => import("@/views/istio/level1-vs/detail.vue"),
      meta: {
        title: "VirtualService详情",
        showLink: false,
        activePath: "/istio/level1-vs"
      }
    },
    {
      path: "/istio/level2-vs",
      name: "Level2VirtualService",
      component: () => import("@/views/istio/level2-vs/index.vue"),
      meta: {
        title: $t("menus.level2VirtualService"),
        icon: "ep:place"
      }
    }
  ]
} satisfies RouteConfigsTable;
