#!/usr/bin/python3
# coding=utf-8

import sys
import requests
import urllib3
import uvicorn

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from kubernetes import client
from kubernetes.client import Configuration
from kubernetes.client.rest import ApiException
from kubernetes.stream import stream
from loguru import logger
import utils
import uuid

logger.remove()
logger.add(
    sys.stderr,
    format='<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> [<level>{level}</level>] <level>{message}</level>',
    level='INFO',
)
TASK_RESULTS = {}
app = FastAPI()


def load_incluster_config():
    with open('/var/run/secrets/kubernetes.io/serviceaccount/token', 'r') as token_file:
        token = token_file.read()
    configuration = Configuration()
    configuration.host = "https://kubernetes.default.svc"
    configuration.verify_ssl = True
    configuration.ssl_ca_cert = '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt'
    configuration.api_key = {"authorization": f"Bearer {token}"}

    return configuration


def get_pod_isolate_label(pod_name: str):
    return 'app'


async def jfr_upload(env, ns, v1, pod_name, file_name, task_id):
    try:
        logger.info("【JFR-TASK】等待文件生成中...")
        TASK_RESULTS[task_id] = {"status": "等待中"}
        total_wait_time = 310
        interval = 10
        for i in range(0, total_wait_time, interval):
            progress = min(100, int((i / total_wait_time) * 100))
            TASK_RESULTS[task_id] = {"status": f"等待中 - {progress}% 完成"}
            await asyncio.sleep(interval)
            if i + interval >= total_wait_time:
                break
        TASK_RESULTS[task_id] = {"status": "上传中"}
        dlurl = f'{utils.OSS_URL}/{env}/jfr/{file_name}'
        command = f'curl -s -T /{file_name} {dlurl}'
        status, message = await execute_command(command, v1, pod_name, ns)
        if status:
            message = f"jfr文件上传成功，下载地址：\n{dlurl}"
            TASK_RESULTS[task_id] = {"status": "已完成", "message": message}
            await execute_command(f"rm -rf /{file_name}", v1, pod_name, ns)
        else:
            message = message + '\n' + f"jfr成功, 文件上传失败"
            TASK_RESULTS[task_id] = {"status": "失败", "message": message}
        send_md(message, env, ns, pod_name)
    except Exception as e:
        logger.exception(f"任务失败: {e}")
        TASK_RESULTS[task_id] = {"status": "失败", "error": str(e)}


async def get_deployment_info(ns: str, pod_name: str):
    """
    根据pod名和命名空间找到对应的deployment名称和当前副本数
    """
    try:
        config = load_incluster_config()
        client.Configuration.set_default(config)
        v1 = client.CoreV1Api()
        apps_v1 = client.AppsV1Api()

        # 获取pod信息
        pod_data = v1.read_namespaced_pod(name=pod_name, namespace=ns, _request_timeout=30)

        # 从pod的ownerReferences中找到ReplicaSet
        owner_refs = pod_data.metadata.owner_references or []
        replicaset_name = None

        for owner in owner_refs:
            if owner.kind == "ReplicaSet":
                replicaset_name = owner.name
                break

        if not replicaset_name:
            return False, None, 0, "Pod没有找到对应的ReplicaSet"

        # 获取ReplicaSet信息
        rs_data = apps_v1.read_namespaced_replica_set(
            name=replicaset_name, namespace=ns, _request_timeout=30
        )

        # 从ReplicaSet的ownerReferences中找到Deployment
        rs_owner_refs = rs_data.metadata.owner_references or []
        deployment_name = None

        for owner in rs_owner_refs:
            if owner.kind == "Deployment":
                deployment_name = owner.name
                break

        if not deployment_name:
            return False, None, 0, "ReplicaSet没有找到对应的Deployment"

        # 获取Deployment当前副本数
        deployment_data = apps_v1.read_namespaced_deployment(
            name=deployment_name, namespace=ns, _request_timeout=30
        )
        current_replicas = deployment_data.spec.replicas or 0

        return True, deployment_name, current_replicas, ""

    except ApiException as e:
        logger.exception(f"获取deployment信息时发生异常: {e}")
        return False, None, 0, f"获取deployment信息失败: {str(e)}"


async def scale_deployment_via_api(
    ns: str, deployment_name: str, new_replicas: int, add_label: bool = False, body_data: list = []
):
    """
    通过调用kubedoor-agent的scale接口来扩容deployment

    Args:
        ns: 命名空间
        deployment_name: deployment名称
        new_replicas: 新的副本数
        add_label: 是否在扩容时给节点添加标签，默认为False

    Returns:
        tuple: (成功标志, 错误信息)
    """
    try:
        # 构造请求数据，格式与kubedoor-agent.py中scale函数期望的格式一致
        request_data = [
            {
                "namespace": ns,
                "deployment_name": deployment_name,
                "num": new_replicas,
                "node_cpu_list": body_data,
            }
        ]

        # 调用kubedoor-agent的scale接口
        # kubedoor-agent运行在443端口（HTTPS）
        # 添加query参数
        scale_url = f"https://localhost:443/api/scale?add_label={'true' if add_label else 'false'}&temp=true&isolate=true"

        headers = {"Content-Type": "application/json"}

        # 使用requests发送POST请求
        # 由于是HTTPS且可能使用自签名证书，禁用SSL验证
        response = requests.post(
            scale_url,
            json=request_data,
            headers=headers,
            timeout=30,
            verify=False,  # 禁用SSL证书验证
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("success", False):
                logger.info(
                    f"通过API成功将Deployment {deployment_name} 临时扩容到 {new_replicas} 个副本"
                )
                return True, ""
            else:
                error_msg = result.get("message", "扩容失败")
                logger.error(f"扩容API返回错误: {error_msg}")
                return False, error_msg
        else:
            try:
                error_detail = response.text or response.json().get('message', '未知错误')
            except:
                error_detail = '无法解析错误详情'
            error_msg = f"扩容API返回状态码: {response.status_code}, 错误详情: {error_detail}"
            logger.error(error_msg)
            return False, error_msg

    except requests.exceptions.RequestException as e:
        logger.exception(f"调用扩容API时发生异常: {e}")
        return False, f"调用扩容API失败: {str(e)}"
    except Exception as e:
        logger.exception(f"扩容deployment时发生意外异常: {e}")
        return False, f"扩容deployment失败: {str(e)}"


async def modify_pod_label(ns: str, pod_name: str):
    try:
        logger.info(f"===开始修改标签 {ns} {pod_name}")
        config = load_incluster_config()
        client.Configuration.set_default(config)
        v1 = client.CoreV1Api()

        # Get the current pod
        pod_data = v1.read_namespaced_pod(name=pod_name, namespace=ns, _request_timeout=30)
        current_labels = pod_data.metadata.labels or {}

        # Modify the label
        isolate_label = get_pod_isolate_label(pod_name)
        labels_app = current_labels.get(isolate_label, False)
        if not labels_app:
            return False, '===未找到app标签'
        new_label_value = labels_app + '-ALERT'
        current_labels[isolate_label] = new_label_value

        # Update the pod with the new label
        pod_data.metadata.labels = current_labels
        v1.patch_namespaced_pod(name=pod_name, namespace=ns, body=pod_data, _request_timeout=30)
        return True, ''
    except ApiException as e:
        logger.exception(f"修改pod标签时发生异常: {e}")
        return False, '===修改标签失败'


async def delete_pod_fun(ns: str, pod_name: str):
    # await asyncio.sleep(300)
    try:
        config = load_incluster_config()
        client.Configuration.set_default(config)
        v1 = client.CoreV1Api()
        v1.delete_namespaced_pod(name=pod_name, namespace=ns, _request_timeout=30)
        logger.info(f"Pod {pod_name} 删除成功")
        return True
    except ApiException as e:
        logger.exception(f"删除pod时发生异常: {e}")
        return False


@app.post("/api/pod/modify_pod")
async def modify_pod(
    request: Request,
    env: str,
    ns: str,
    pod_name: str,
    scale_pod: bool = False,
    add_label: bool = False,
):
    deployment_name = None
    current_replicas = 0
    new_replicas = 0

    # 是否扩容--->是否固定节点均衡模式--->临时扩容(开启管控模式)
    # 1. 如果需要扩容，先获取deployment信息并执行扩容
    if scale_pod:
        success, deployment_name, current_replicas, error_msg = await get_deployment_info(
            ns, pod_name
        )
        if not success:
            return JSONResponse(status_code=500, content={"message": error_msg})

        # 获取body数据（如果add_label为True）
        if add_label:
            try:
                body_data = await request.json()
                if not isinstance(body_data, list):
                    return JSONResponse(
                        status_code=400,
                        content={"message": "当add_label为True时，body必须是一个list"},
                    )
            except Exception as e:
                return JSONResponse(status_code=400, content={"message": f"解析body失败: {str(e)}"})
        else:
            body_data = []

        # 2. 扩容deployment（增加一个pod）
        new_replicas = current_replicas + 1
        scale_success, scale_error = await scale_deployment_via_api(
            ns, deployment_name, new_replicas, add_label, body_data
        )
        if not scale_success:
            return JSONResponse(status_code=500, content={"message": scale_error})

        logger.info(
            f"Deployment {deployment_name} 从 {current_replicas} 个副本临时扩容到 {new_replicas} 个副本"
        )

    # 3. 修改pod标签
    success, status = await modify_pod_label(ns, pod_name)
    if not success:
        return JSONResponse(status_code=500, content={"message": status})
        # raise HTTPException(status_code=500, detail=status)
    # await asyncio.sleep(300)  # Wait for 5 minutes
    # Schedule the pod deletion after 5 minutes without blocking the request
    # asyncio.create_task(delete_pod(ns, pod_name))

    if scale_pod:
        success_msg = (
            f"Deployment {deployment_name} 临时扩容到 {new_replicas} 个副本并成功修改app标签"
        )
    else:
        success_msg = "app标签修改成功"

    send_md(success_msg, env, ns, pod_name)
    return {"message": f"【{ns}】【{pod_name}】{success_msg}", "success": True}


@app.get("/api/pod/delete_pod")
async def delete_pod(env: str, ns: str, pod_name: str):
    # Delete the pod label
    success = await delete_pod_fun(ns, pod_name)
    if not success:
        return JSONResponse(status_code=500, content={"message": "删除pod失败"})
    send_md("pod删除成功", env, ns, pod_name)
    return {"message": f"【{ns}】【{pod_name}】pod删除成功", "success": True}


async def get_pod_info(ns, pod_name, v1, type, tail):
    # 返回pod信息
    try:
        v1.read_namespaced_pod(name=pod_name, namespace=ns, _request_timeout=30)
        now = datetime.now()
        formatted_time = now.strftime("%Y%m%d%H%M")
        file_name = f"{type}-{pod_name}-{formatted_time}.{tail}"
        logger.info(f"文件名{file_name}")
        return file_name, None
    except Exception as e:
        logger.error(f"在命名空间 [{ns}] 中未找到pod [{pod_name}]")
        logger.exception(str(e))
        return "error", f"在命名空间 [{ns}] 中未找到pod [{pod_name}]"


async def execute_command(command, v1, pod_name, ns):
    logger.info(f"执行命令：{command}")
    exec_command = ['/bin/sh', '-c', f"{command}; echo $?"]
    try:
        resp = stream(
            v1.connect_get_namespaced_pod_exec,
            pod_name,
            ns,
            command=exec_command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
        )
        # 分割输出，最后一行是状态码
        lines = resp.strip().split('\n')
        status_code = lines[-1]
        output = '\n'.join(lines[:-1])
        if status_code != '0':
            message = f"命令 {command} 执行失败，状态码: {status_code}，输出信息: {output}"
            logger.error(message)
            return False, message
        return True, output
    except client.exceptions.ApiException as e:
        logger.exception(str(e))
        return False, str(e)


async def execute_in_pod(env, ns, v1, pod_name, type, file_name="not_found"):
    status, message = await execute_command(
        "curl -V || (sed -i 's/dl-cdn.alpinelinux.org/repo.huaweicloud.com/g' /etc/apk/repositories && apk add -q curl)",
        v1,
        pod_name,
        ns,
    )
    if not status:
        return status, message
    if type == "dump":
        command = f"env -u JAVA_TOOL_OPTIONS jmap -dump:format=b,file=/{file_name} `pidof -s java`"
        status, message = await execute_command(command, v1, pod_name, ns)
        if status:
            dlurl = f'{utils.OSS_URL}/{env}/dump/{file_name}'
            command = f'curl -s -T /{file_name} {dlurl}'
            status2, message = await execute_command(command, v1, pod_name, ns)
            if status2:
                message = f"dump文件上传成功，下载地址：\n{dlurl}"
                await execute_command(f"rm -rf /{file_name}", v1, pod_name, ns)
            else:
                message = f"dump成功, 文件上传失败"
        else:
            message = f"dump失败"
    if type == "jfr":
        # 解锁JFR功能
        command_unlock = (
            f"env -u JAVA_TOOL_OPTIONS jcmd `pidof -s java` VM.unlock\_commercial\_features"
        )
        status, message = await execute_command(command_unlock, v1, pod_name, ns)
        if not status:
            return status, message + '\n' + "jfr解锁失败"
        command = f"env -u JAVA_TOOL_OPTIONS jcmd `pidof -s java` JFR.start duration=5m filename=/{file_name}"
        status, message = await execute_command(command, v1, pod_name, ns)
        if not status:
            return status, message + '\n' + "开启jfr飞行记录失败"
    if type == "jstack":
        command = f"env -u JAVA_TOOL_OPTIONS jstack -l `pidof -s java` |tee /{file_name}"
        status, jstack_msg = await execute_command(command, v1, pod_name, ns)
        if status:
            dlurl = f'{utils.OSS_URL}/{env}/jstack/{file_name}'
            command = f'curl -s -T /{file_name} {dlurl}'
            status2, message = await execute_command(command, v1, pod_name, ns)
            if status2:
                dlmsg = f"jstack文件上传成功，下载地址：\n{dlurl}"
                await execute_command(f"rm -rf /{file_name}", v1, pod_name, ns)
            else:
                dlmsg = "jstack成功, 文件上传失败"
            message = jstack_msg + '\n' + dlmsg
            send_md(dlmsg, env, ns, pod_name)
        else:
            message = f"jstack失败"
    if type == "jvm_mem":
        # 查询jvm内存
        command = "env -u JAVA_TOOL_OPTIONS jmap -heap `pidof -s java`"
        # command = "ls arthas-boot.jar || curl -s -O https://arthas.aliyun.com/arthas-boot.jar && env -u JAVA_TOOL_OPTIONS java -jar arthas-boot.jar 1 -c 'memory;stop'|sed -n '/memory | plaintext/,/stop | plaintext/{/memory | plaintext/b;/stop | plaintext/b;p}'"
        status, message = await execute_command(command, v1, pod_name, ns)
    return status, message


def send_md(msg, env, ns, pod_name):
    text = f"# 【<font color=\"#5bcc85\">{env}</font>】{ns}\n## {pod_name}\n"
    text += f"{msg}\n"
    utils.send_msg(text)


@app.get("/api/pod/auto_dump")
async def auto_dump(env: str, ns: str, pod_name: str):
    config = load_incluster_config()
    client.Configuration.set_default(config)
    v1 = client.CoreV1Api()
    file_name, err_msg = await get_pod_info(ns, pod_name, v1, "dump", "hprof")
    if file_name == "error":
        return JSONResponse(status_code=500, content={"message": err_msg})
    # 生成 Java 进程对象统计信息直方图
    status, message = await execute_command(
        "env -u JAVA_TOOL_OPTIONS jmap -histo `pidof -s java` |head -n 30", v1, pod_name, ns
    )
    if status:
        all_msg = "Java 进程对象统计信息直方图:" + '\n' + message
    else:
        all_msg = message + '\n' + "生成 Java 进程对象统计信息直方图失败"
    status, message = await execute_in_pod(env, ns, v1, pod_name, "dump", file_name)
    all_msg = all_msg + '\n' + message
    if status:
        dlurl = f'{utils.OSS_URL}/{env}/dump/{file_name}'
        send_md(all_msg, env, ns, pod_name)
        return {"message": all_msg, "success": True, "link": dlurl}
    return JSONResponse(status_code=500, content={"message": all_msg})


@app.get("/api/pod/auto_jstack")
async def auto_jstack(env: str, ns: str, pod_name: str):
    config = load_incluster_config()
    client.Configuration.set_default(config)
    v1 = client.CoreV1Api()
    file_name, err_msg = await get_pod_info(ns, pod_name, v1, "jstack", "jstack")
    if file_name == "error":
        return JSONResponse(status_code=500, content={"message": err_msg})
    status, message = await execute_in_pod(env, ns, v1, pod_name, "jstack", file_name)
    if status:
        return {"message": message, "success": True}
    else:
        return JSONResponse(status_code=500, content={"message": message})


@app.get("/api/pod/auto_jfr")
async def auto_jfr(env: str, ns: str, pod_name: str, background_tasks: BackgroundTasks):
    config = load_incluster_config()
    client.Configuration.set_default(config)
    v1 = client.CoreV1Api()
    file_name, err_msg = await get_pod_info(ns, pod_name, v1, "jfr", "jfr")
    if file_name == "error":
        return JSONResponse(status_code=500, content={"message": err_msg})
    status, message = await execute_in_pod(env, ns, v1, pod_name, "jfr", file_name)
    if status:
        task_id = str(uuid.uuid4())
        TASK_RESULTS[task_id] = {"status": "处理中"}
        background_tasks.add_task(jfr_upload, env, ns, v1, pod_name, file_name, task_id)
        now = datetime.now()
        finish_time = now + timedelta(minutes=6)
        formatted_now = now.strftime("%H:%M:%S")
        formatted_finish = finish_time.strftime("%H:%M:%S")
        link = f'{utils.OSS_URL}/{env}/jfr/{file_name}'
        message = f"飞行记录后台执行需要5分钟，任务ID：{task_id}\n（/api/pod/task_status/{task_id}?env={env}）\n请于{formatted_finish}后，访问以下链接下载:\n{link}"
        send_md(message, env, ns, pod_name)
        return {"message": message, "success": True, 'link': link}
    return JSONResponse(status_code=500, content={"message": message})


@app.get("/api/pod/auto_jvm_mem")
async def auto_jvm_mem(env: str, ns: str, pod_name: str):
    config = load_incluster_config()
    client.Configuration.set_default(config)
    v1 = client.CoreV1Api()
    status, message = await execute_in_pod(env, ns, v1, pod_name, "jvm_mem")
    if status:
        send_md(message, env, ns, pod_name)
        return {"message": message, "success": True}
    return JSONResponse(status_code=500, content={"message": message})


@app.get("/api/pod/task_status/{task_id}")
async def get_task_status(task_id: str):
    if task_id in TASK_RESULTS:
        return TASK_RESULTS[task_id]
    else:
        return {"status": "未找到"}


@app.get("/api/pod/get_logs")
async def get_pod_logs(env: str, ns: str, pod: str, lines: int = 100):
    try:
        config = load_incluster_config()
        client.Configuration.set_default(config)
        v1 = client.CoreV1Api()

        # 检查pod是否存在
        try:
            v1.read_namespaced_pod(name=pod, namespace=ns, _request_timeout=30)
        except Exception as e:
            error_msg = f"在命名空间 [{ns}] 中未找到pod [{pod}]"
            logger.error(error_msg)
            return JSONResponse(status_code=500, content={"message": error_msg})

        # 获取pod日志
        logs = v1.read_namespaced_pod_log(
            name=pod, namespace=ns, tail_lines=lines, _request_timeout=30
        )
        return {"message": logs, "success": True}
    except ApiException as e:
        logger.exception(f"获取Pod日志时出现异常: {e}")
        return JSONResponse(status_code=500, content={"message": f"获取Pod日志失败: {str(e)}"})


if __name__ == "__main__":
    uvicorn.run("pod-mgr:app", host="0.0.0.0", workers=1, port=81)
