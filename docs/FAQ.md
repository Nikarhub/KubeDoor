场景一： Prometheus, Node_exporter, kube-state-metrics与KubeDoor处于不同命名空间，如何实现跨命名空间访问采集指标
>修改configmap资源 -> vmagent-config -> node_exporter采集项配置:

```markdown
data:  - job_name: 'k8s-node-exporter'\n
    \   scheme: https\n    tls_config:\n      insecure_skip_verify: true \n    bearer_token_file:
    /var/run/secrets/kubernetes.io/serviceaccount/token\n    kubernetes_sd_configs:\n
    \   - role: node\n      namespaces:\n        names: [monitoring]\n    relabel_configs:\n
    \   - action: replace\n      source_labels: [__address__]\n      regex: '(.*):10250'\n
    \     replacement: '${1}:9100'\n      target_label: __address__\n    - action:
    replace\n      regex: (.*)\n      replacement: $1\n      source_labels: [__meta_kubernetes_node_name]\n
    \     target_label: kubernetes_node\n    - source_labels: []\n      target_label:
    __scheme__\n      replacement: https\n\n  
```
>即可采集认证过https的node-exporter与跨命名空间访问。

>vmagent 配置文件内容示例:
```markdown
[root@test01 ~]# kubectl exec -it -n kubedoor vmagent-7f4dd4dbbd-b5knx -- cat /config/scrape.yml
global:
  scrape_interval: 30s
  scrape_timeout: 30s
  external_labels:
    origin_prometheus: my-test-k8s

scrape_configs:
  - job_name: 'vmagent'
    static_configs:
    - targets: ['localhost:8429']

  - job_name: 'k8s-node-exporter'
    scheme: https
    tls_config:
      insecure_skip_verify: true 
    bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token
    kubernetes_sd_configs:
    - role: node
      namespaces:
        names: [monitoring]
    relabel_configs:
    - action: replace
      source_labels: [__address__]
      regex: '(.*):10250'
      replacement: '${1}:9100'
      target_label: __address__
    - action: replace
      regex: (.*)
      replacement: $1
      source_labels: [__meta_kubernetes_node_name]
      target_label: kubernetes_node
    - source_labels: []
      target_label: __scheme__
      replacement: https
```