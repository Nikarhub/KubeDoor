FROM registry.cn-shenzhen.aliyuncs.com/starsl/python:3.12-alpine
ADD . /
WORKDIR /
RUN sed -i 's/dl-cdn.alpinelinux.org/repo.huaweicloud.com/g' /etc/apk/repositories && \
    apk add gcc musl-dev --no-cache && \
    pip3 install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --no-cache-dir
EXPOSE 80
CMD ["python3", "/kubedoor-master.py"]
