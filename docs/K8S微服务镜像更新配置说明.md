# K8S微服务镜像更新配置说明

## 功能介绍
- 支持针对**指定用户**，**指定时间段**授权操作。
- 支持根据微服务的镜像地址，**自动**从相应的**镜像仓库**获取微服务的**镜像标签**。

## 权限配置说明

注意：该权限仅控制**只读用户**的权限，读写用户默认已有权限操作，会忽略该文件的配置。

configmap：``kubedoor-config`

- `UPDATE_IMAGE`

  ```
  {
    "default": {
      "isOperationAllowed": false
    },
    "saas-prod": {
      "isOperationAllowed": true,
      "allowedOperationPeriod": "20:00-08:00",
      "user": [
        "a0111",
        "a0222"
      ]
    },
    "saas-prod-hw": {
      "isOperationAllowed": true,
      "allowedOperationPeriod": "20:00-08:00",
      "user": [
        "a0333",
        "a0444"
      ]
    }
  }
  
  ```
- `default`表示未匹配到的K8S是禁止操作的。
  
  ```bash
  "default": {
    "isOperationAllowed": false
  }
  ```
- `saas-prod`，`saas-prod-hw` 表示指定的K8S环境
- `allowedOperationPeriod` 表示可操作的时间段
- `user` 表示可操作的只读用户列表

## 镜像仓库配置

配置镜像仓库的信息是**为了自动从镜像仓库获取微服务的镜像标签**

目前支持**华为云镜像仓库，阿里云镜像仓库**，以及自建的**Harbor**

**匹配逻辑**：微服务点击更新后，获取**微服务镜像地址**，然后从`REGISTRY_SECRET`中找**对应的仓库地址**（找不到则无法获取，需要手动填写需要部署的镜像标签），找到则再找**匹配的K8S名称**（找不到取`default`），再取到`ak`，`sk`信息，然后连接相应的仓库获取该微服务的最新的20个镜像标签。

configmap：``kubedoor-config`

- `REGISTRY_SECRET`

  ```bash
  {
    "swr.cn-south-1.myhuaweicloud.com": {
      "default": {
        "ak": "xxxxxxxx",
        "sk": "xxxxxxxxxxxxxxxxxxx"
      }
    },
    "registry.cn-shenzhen.aliyuncs.com": {
      "default": {
        "ak": "xxxxxxxxx",
        "sk": "xxxxxxxxxxxxxxxxxxx"
      },
      "myk8s-1": {
        "ak": "xxxxxxxxx",
        "sk": "xxxxxxxxxxxxxxxxxxx"
      }
    },
    "harbor.xxxxx.com": {
      "default": {
        "ak": "username",
        "sk": "password"
      }
    }
  }
  
  ```

- `swr.cn-south-1.myhuaweicloud.com` ，`registry.cn-shenzhen.aliyuncs.com`，`harbor.xxxxx.com` 表示镜像仓库的地址，与微服务的`image`地址匹配。

- `default` 表示未匹配到的K8S，则从`default`中获取连接镜像仓库的`ak`，`sk`信息。

- `myk8s-1` 表示匹配到的K8S，则从该字段中获取连接镜像仓库的`ak`，`sk`信息。