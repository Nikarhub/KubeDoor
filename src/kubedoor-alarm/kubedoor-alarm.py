#!/usr/bin/python3
import json, requests, utils
from flask import Flask, Response, request, jsonify
from clickhouse_pool import ChPool
from datetime import datetime, UTC
import pytz
import logging
import hashlib

logging.basicConfig(
    level=getattr(logging, utils.LOG_LEVEL), format='%(asctime)s - %(levelname)s - %(message)s'
)
pool = ChPool(
    host=utils.CK_HOST,
    port=utils.CK_PORT,
    user=utils.CK_USER,
    password=utils.CK_PASSWORD,
    database=utils.CK_DATABASE,
    connections_min=1,
    connections_max=10,
)

MSG_TOKEN = utils.MSG_TOKEN
MSG_TYPE = utils.MSG_TYPE
DEFAULT_AT = utils.DEFAULT_AT
ALERTMANAGER_EXTURL = utils.ALERTMANAGER_EXTURL
PROM_K8S_TAG_KEY = utils.PROM_K8S_TAG_KEY


def wecom(webhook, content, at):
    webhook = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=' + webhook
    headers = {'Content-Type': 'application/json'}
    params = {'msgtype': 'markdown', 'markdown': {'content': f"{content}<@{at}>"}}
    data = bytes(json.dumps(params), 'utf-8')
    response = requests.post(webhook, headers=headers, data=data)
    print(f'【wecom】{response.json()}', flush=True)


def dingding(webhook, content, at):
    webhook = 'https://oapi.dingtalk.com/robot/send?access_token=' + webhook
    headers = {'Content-Type': 'application/json'}
    params = {
        "msgtype": "markdown",
        "markdown": {"title": "告警", "text": content},
        "at": {"atMobiles": [at]},
    }
    data = bytes(json.dumps(params), 'utf-8')
    response = requests.post(webhook, headers=headers, data=data)
    print(f'【dingding】{response.json()}', flush=True)


def feishu(webhook, content, at):
    title = "告警通知"
    webhook = f'https://open.feishu.cn/open-apis/bot/v2/hook/{webhook}'
    headers = {'Content-Type': 'application/json'}
    params = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": title}, "template": "red"},
            "elements": [
                {
                    "tag": "markdown",
                    "content": f"{content}\n<at id={at}></at>",
                }
            ],
        },
    }
    data = json.dumps(params)
    response = requests.post(webhook, headers=headers, data=data)
    print(f'【feishu】{response.json()}')


def parse_alert_time(time_str):
    """将Alertmanager的时间字符串转换为上海时区的DateTime对象"""
    time_str = time_str[:19] + 'Z'
    utc_time = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ")
    utc_time = utc_time.replace(tzinfo=pytz.UTC)
    return utc_time.astimezone(pytz.timezone('Asia/Shanghai'))


def extract_container_from_pod(pod_name):
    """从pod名称中提取container名称"""
    try:
        import re

        # Kubernetes pod命名规则:
        # 1. Deployment: <deployment-name>-<replicaset-hash>-<pod-hash>
        # 2. ReplicaSet: <replicaset-name>-<pod-hash>
        # hash通常是5-10位的随机字符串（字母数字组合）

        # 使用正则表达式匹配末尾的hash模式
        # 匹配最后一个或两个hash（5-10位字母数字）
        pattern = r'^(.+?)-[a-z0-9]{5,10}(-[a-z0-9]{5,10})?$'
        match = re.match(pattern, pod_name)

        if match:
            return match.group(1)

        # 如果正则匹配失败，使用备用方案
        # 去掉最后1-2个看起来像hash的部分
        parts = pod_name.split('-')
        if len(parts) >= 2:
            # 检查最后一部分是否像hash（5-10位字母数字）
            if len(parts[-1]) >= 5 and len(parts[-1]) <= 10 and parts[-1].isalnum():
                # 检查倒数第二部分是否也像hash
                if (
                    len(parts) >= 3
                    and len(parts[-2]) >= 5
                    and len(parts[-2]) <= 10
                    and parts[-2].isalnum()
                ):
                    return '-'.join(parts[:-2])
                else:
                    return '-'.join(parts[:-1])

        # 如果所有解析方法都失败，强制去掉最后两部分
        parts = pod_name.split('-')
        if len(parts) >= 3:
            return '-'.join(parts[:-2])
        elif len(parts) >= 2:
            return '-'.join(parts[:-1])
        else:
            return ''
    except:
        return ''


def process_single_alert(alert):
    try:
        # 解析时间
        starts_at = parse_alert_time(alert['startsAt'])
        ends_at = parse_alert_time(alert['endsAt'])

        # 格式化时间字符串
        start_time_str = starts_at.strftime("%Y-%m-%d %H:%M:%S")
        end_time_str = ends_at.strftime("%Y-%m-%d %H:%M:%S")

        # 解析标签和注解
        labels = alert.get('labels', {})
        annotations = alert.get('annotations', {})
        description = annotations.get('description', '').split('\n- ')[-1]

        # 提取K8s相关字段，支持备用字段
        namespace = labels.get('namespace', '') or labels.get('k8s_ns', '')
        pod = labels.get('pod', '') or labels.get('k8s_pod', '')
        container = labels.get('container', '') or labels.get('k8s_app', '')
        env = labels.get(PROM_K8S_TAG_KEY, '')
        alert_name = labels.get('alertname', '')

        # 生成指纹
        fingerprint_str = env + namespace + pod + alert_name
        fingerprint = hashlib.md5(fingerprint_str.encode(encoding='UTF-8')).hexdigest()
        promfinger = alert['fingerprint']

        alert_data = {
            'promfinger': promfinger,
            'fingerprint': fingerprint,
            'start_time': start_time_str,
            'end_time': end_time_str,
            'severity': labels.get('severity', ''),
            'alert_group': labels.get('alertgroup', ''),
            'alert_name': alert_name,
            'env': env,
            'namespace': namespace,
            'container': container,
            'pod': pod,
            'description': description,
        }
        send_resolved = False if labels.get('send_resolved', True) == 'false' else True

        if alert['status'] == 'firing':
            handle_firing_alert(alert_data, send_resolved)
        else:
            handle_resolved_alert(alert_data, send_resolved)

    except Exception as e:
        logging.error(f"处理告警失败: {str(e)}", exc_info=True)


def handle_firing_alert(alert_data, send_resolved):
    check_query = f"""
        SELECT 1 FROM kubedoor.k8s_pod_alert_days
        WHERE toDate(start_time) = '{alert_data['start_time'].split()[0]}' and 
        fingerprint = '{alert_data['fingerprint']}'
        LIMIT 1
    """

    with pool.get_client() as client:
        existing = client.execute(check_query)

    if existing:
        # 获取当前时间并格式化为字符串
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        update_query = f"""
            ALTER TABLE kubedoor.k8s_pod_alert_days
            UPDATE count_firing = count_firing + 1, end_time = '{current_time}', 
            alert_status = 'firing', operate = '未处理', description = '{alert_data['description']}'
            WHERE toDate(start_time) = '{alert_data['start_time'].split()[0]}' and 
            fingerprint = '{alert_data['fingerprint']}'
        """

        with pool.get_client() as client:
            client.execute(update_query)
        logging.info(f"更新告警计数: {alert_data['fingerprint']}: {alert_data['alert_name']}")
    else:
        # 插入新记录
        count_resolved = 0 if send_resolved else -1
        insert_query = f"""
            INSERT INTO kubedoor.k8s_pod_alert_days (
                fingerprint, alert_status, send_resolved, operate, 
                start_time,count_firing,count_resolved,
                severity, alert_group, alert_name,
                env, namespace,
                container, pod, description
            ) VALUES (
                '{alert_data['fingerprint']}', 'firing', {send_resolved}, '未处理',
                '{alert_data['start_time']}', 1, {count_resolved},
                '{alert_data['severity']}', '{alert_data['alert_group']}', '{alert_data['alert_name']}',
                '{alert_data['env']}', '{alert_data['namespace']}',
                '{alert_data['container']}', '{alert_data['pod']}', '{alert_data['description']}'
            )
        """
        with pool.get_client() as client:
            client.execute(insert_query)
        logging.info(f"新建告警记录: {alert_data['fingerprint']}: {alert_data['alert_name']}")
    return True, ''


def handle_resolved_alert(alert_data, send_resolved):
    if not send_resolved:
        err = f"告警 {alert_data['fingerprint']}: {alert_data['alert_name']} 的 send_resolved 为 false，不入库"
        logging.warning(err)
        return False, err

    check_query = f"""
        SELECT 1 FROM kubedoor.k8s_pod_alert_days
        WHERE toDate(start_time) = '{alert_data['start_time'].split()[0]}' and fingerprint = '{alert_data['fingerprint']}'
        LIMIT 1
    """
    with pool.get_client() as client:
        existing = client.execute(check_query)

    if existing:
        update_query = f"""
            ALTER TABLE kubedoor.k8s_pod_alert_days
            UPDATE alert_status = 'resolved', end_time = '{alert_data['end_time']}', 
            count_resolved = count_resolved + 1, description = '{alert_data['description']}'
            WHERE toDate(start_time) = '{alert_data['start_time'].split()[0]}' AND 
            fingerprint = '{alert_data['fingerprint']}'
        """
        with pool.get_client() as client:
            client.execute(update_query)

        logging.info(f"标记告警解决: {alert_data['fingerprint']}: {alert_data['alert_name']}")
        return True, ''
    else:
        err = f"未找到对应告警记录: {alert_data['fingerprint']}: {alert_data['alert_name']}"
        logging.error(err)
        return False, err


app = Flask(__name__)


@app.route('/clickhouse', methods=['POST'])
def handle_alert():
    try:
        data = request.get_json()
        if not data or 'alerts' not in data:
            return jsonify({'status': 'error', 'message': '无效的请求格式'}), 400

        for alert in data['alerts']:
            logging.debug(str(alert))
            process_single_alert(alert)

        return jsonify({'status': 'success', 'message': '告警处理完成'}), 200

    except Exception as e:
        logging.error(f"处理请求时发生异常: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/custom_alert', methods=['POST'])
def handle_custom_alert():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': '无效的请求格式'}), 400

        # 验证必需字段
        required_fields = [
            'start_time',
            'end_time',
            'severity',
            'alert_group',
            'alert_name',
            'env',
            'namespace',
            'pod',
            'description',
            'send_resolved',
            'alert_status',
        ]

        for field in required_fields:
            if field not in data:
                return jsonify({'status': 'error', 'message': f'缺少必需字段: {field}'}), 400

        # 验证severity值
        valid_severities = ['Critical', 'Info', 'Notice', 'Warning']
        if data['severity'] not in valid_severities:
            return (
                jsonify(
                    {'status': 'error', 'message': f'severity必须是以下值之一: {valid_severities}'}
                ),
                400,
            )

        # 验证alert_status值
        valid_statuses = ['firing', 'resolved']
        if data['alert_status'] not in valid_statuses:
            return (
                jsonify(
                    {
                        'status': 'error',
                        'message': f'alert_status必须是以下值之一: {valid_statuses}',
                    }
                ),
                400,
            )

        # 验证时间格式
        try:
            datetime.strptime(data['start_time'], "%Y-%m-%d %H:%M:%S")
            datetime.strptime(data['end_time'], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return jsonify({'status': 'error', 'message': '时间格式必须为: %Y-%m-%d %H:%M:%S'}), 400

        # 处理container字段：如果用户传了就用用户传的，如果没传就从pod名称中截取
        if 'container' in data and data['container']:
            container = data['container']
        else:
            container = extract_container_from_pod(data['pod'])

        # 生成指纹
        fingerprint_str = data['env'] + data['namespace'] + data['pod'] + data['alert_name']
        fingerprint = hashlib.md5(fingerprint_str.encode(encoding='UTF-8')).hexdigest()

        # 构造alert_data
        alert_data = {
            'fingerprint': fingerprint,
            'start_time': data['start_time'],
            'end_time': data['end_time'],
            'severity': data['severity'],
            'alert_group': data['alert_group'],
            'alert_name': data['alert_name'],
            'env': data['env'],
            'namespace': data['namespace'],
            'container': container,
            'pod': data['pod'],
            'description': data['description'],
        }

        send_resolved = data['send_resolved']
        alert_status = data['alert_status']

        # 根据alert_status调用相应的处理函数
        if alert_status == 'firing':
            result, msg = handle_firing_alert(alert_data, send_resolved)
        else:
            result, msg = handle_resolved_alert(alert_data, send_resolved)
        if result:
            return jsonify({'status': 'success', 'message': '自定义告警处理完成'}), 200
        else:
            return jsonify({'status': 'error', 'message': msg}), 400
    except Exception as e:
        logging.error(f"处理自定义告警时发生异常: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route("/msg/<token>", methods=['POST'])
def alertnode(token):
    req = request.get_json()
    print('↓↓↓↓↓↓↓↓↓↓↓↓↓↓node↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓', flush=True)
    print(json.dumps(req, indent=2, ensure_ascii=False), flush=True)
    print('↑↑↑↑↑↑↑↑↑↑↑↑↑↑node↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑', flush=True)
    now_utc = datetime.now(UTC).replace(tzinfo=None)
    now_cn = datetime.now()

    # time1830 = datetime.strptime(str(now_cn.date()) + '18:30', '%Y-%m-%d%H:%M')
    # time0830 = datetime.strptime(str(now_cn.date()) + '08:30', '%Y-%m-%d%H:%M')

    # if (now_cn > time1830 or now_cn < time0830):
    #    return Response(status=204)
    allmd = ''
    for i in req["alerts"]:
        status = "故障" if i['status'] == "firing" else "恢复"
        try:
            firstime = datetime.strptime(i['startsAt'], '%Y-%m-%dT%H:%M:%SZ')
            durn_s = (now_utc - firstime).total_seconds()
        except:
            try:
                firstime = datetime.strptime(i['startsAt'], '%Y-%m-%dT%H:%M:%S.%fZ')
                durn_s = (now_utc - firstime).total_seconds()
            except:
                firstime = datetime.strptime(i['startsAt'].split(".")[0], '%Y-%m-%dT%H:%M:%S+08:00')
                durn_s = (now_cn - firstime).total_seconds()
        if durn_s < 60:
            durninfo = '小于1分钟'
        elif durn_s < 3600:
            durn = round(durn_s / 60, 1)
            durninfo = f"已持续{durn}分钟"
        else:
            durn = round(durn_s / 3600, 1)
            durninfo = f"已持续{durn}小时"

        summary = f"{i['labels']['alertname']},{durninfo}"
        message = i['annotations']['description']
        at = i['annotations'].get('at', DEFAULT_AT)

        url = f"{ALERTMANAGER_EXTURL}/#/alerts?silenced=false&inhibited=false&active=true&filter=%7Balertname%3D%22{i['labels']['alertname']}%22%7D"

        if status == '恢复':
            info = f"### {status}<font color=\"#6aa84f\">{summary}</font>\n- {message}\n\n"
        else:
            info = f"### {status}<font color=\"#ff0000\">{summary}</font>\n- {message}[【屏蔽】]({url})\n\n"
        allmd = allmd + info

    im, key = token.split('=', 1)
    if im == 'wecom':
        wecom(key, allmd, at)
    elif im == 'dingding':
        dingding(key, allmd, at)
    elif im == 'feishu':
        feishu(key, allmd, at)
    return Response(status=200)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
