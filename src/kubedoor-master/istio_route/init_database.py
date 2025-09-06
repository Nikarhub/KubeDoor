#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Istio VirtualService 数据库表结构初始化脚本

设计说明:
1. vs_global: 存储VirtualService的全局配置
2. vs_http_routes: 存储HTTP路由规则，每条记录是一条规则
3. k8s_cluster: 存储K8S集群与VirtualService的关联关系
"""

import mysql.connector
import sys


class VirtualServiceDB:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 3306,
        user: str = "root",
        password: str = "",
        database: str = "virtualservice",
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.conn = None

    def connect(self):
        """连接数据库"""
        try:
            self.conn = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset='utf8mb4',
                autocommit=False,
            )
            return self.conn
        except mysql.connector.Error as e:
            if e.errno == mysql.connector.errorcode.ER_BAD_DB_ERROR:
                # 数据库不存在，先创建数据库
                temp_conn = mysql.connector.connect(
                    host=self.host, port=self.port, user=self.user, password=self.password, charset='utf8mb4'
                )
                cursor = temp_conn.cursor()
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS {self.database} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
                temp_conn.commit()
                cursor.close()
                temp_conn.close()

                # 重新连接到新创建的数据库
                self.conn = mysql.connector.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    database=self.database,
                    charset='utf8mb4',
                    autocommit=False,
                )
                return self.conn
            else:
                raise e

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

    def init_tables(self):
        """初始化数据库表结构"""
        if not self.conn:
            self.connect()

        cursor = self.conn.cursor(dictionary=True)

        # 创建全局配置表
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS vs_global (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            namespace VARCHAR(255) NOT NULL DEFAULT 'default',
            gateways TEXT,  -- JSON数组: ["gateway1", "gateway2"]
            hosts TEXT NOT NULL,  -- JSON数组: ["host1.com", "host2.com"]
            protocol VARCHAR(50) DEFAULT 'http',
            df_forward_type VARCHAR(20),  -- 默认路由类型: 'route' 或 'delegate'
            df_forward_detail TEXT,  -- 默认路由详情: JSON格式
            df_forward_timeout VARCHAR(50),  -- 默认路由超时设置
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY unique_name_namespace (name, namespace),
            CHECK (df_forward_type IS NULL OR df_forward_type IN ('route', 'delegate'))
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
        )

        # 创建HTTP路由规则表
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS vs_http_routes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            vs_global_id INT NOT NULL,
            name VARCHAR(255),  -- 路由规则名称(可选)
            priority INT DEFAULT 0,  -- 路由优先级，数字越小优先级越高
            match_rules TEXT,  -- JSON: [{"uri": {"prefix": "/api"}, "authority": {"exact": "api.example.com"}}]
            rewrite_rules TEXT,  -- JSON: {"uri": "/new-path"}
            forward_type VARCHAR(20) NOT NULL,
            forward_detail TEXT NOT NULL,  -- JSON: route时存储destination和headers，delegate时存储name和namespace
            timeout VARCHAR(50),  -- 路由级别的超时设置
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (vs_global_id) REFERENCES vs_global(id) ON DELETE CASCADE,
            CHECK (forward_type IN ('route', 'delegate'))
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
        )

        # 创建K8S集群关联表
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS k8s_cluster (
            id INT AUTO_INCREMENT PRIMARY KEY,
            k8s_name VARCHAR(255) NOT NULL COMMENT 'K8S集群名称',
            vs_id INT NOT NULL COMMENT 'VirtualService ID',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (vs_id) REFERENCES vs_global(id) ON DELETE CASCADE,
            INDEX idx_k8s_name (k8s_name),
            INDEX idx_vs_id (vs_id),
            UNIQUE KEY unique_k8s_vs (k8s_name, vs_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='K8S集群与VirtualService关联表'
        """
        )

        # 创建索引（MySQL 不支持 IF NOT EXISTS，需要先检查是否存在）
        try:
            cursor.execute("CREATE INDEX idx_vs_global_name_namespace ON vs_global(name, namespace)")
        except mysql.connector.Error as e:
            if e.errno != mysql.connector.errorcode.ER_DUP_KEYNAME:
                raise e

        try:
            cursor.execute("CREATE INDEX idx_vs_http_routes_vs_global_id ON vs_http_routes(vs_global_id)")
        except mysql.connector.Error as e:
            if e.errno != mysql.connector.errorcode.ER_DUP_KEYNAME:
                raise e

        try:
            cursor.execute("CREATE INDEX idx_vs_http_routes_priority ON vs_http_routes(vs_global_id, priority)")
        except mysql.connector.Error as e:
            if e.errno != mysql.connector.errorcode.ER_DUP_KEYNAME:
                raise e

        self.conn.commit()
        
        # 验证表是否创建成功
        cursor.execute("SHOW TABLES")
        table_results = cursor.fetchall()
        # 获取表名，处理字典格式的结果
        if table_results:
            # 获取第一个键名（通常是 'Tables_in_数据库名'）
            table_key = list(table_results[0].keys())[0]
            tables = [table[table_key] for table in table_results]
        else:
            tables = []
            
        expected_tables = ['vs_global', 'vs_http_routes', 'k8s_cluster']
        
        missing_tables = [table for table in expected_tables if table not in tables]
        if missing_tables:
            raise Exception(f"以下表创建失败: {missing_tables}")
        
        print("数据库表结构初始化完成！")
        print(f"已创建的表: {', '.join(tables)}")
        cursor.close()


def main():
    """主函数"""
    # 数据库配置
    try:
        from dotenv import load_dotenv
        import os
        
        # 尝试加载.env文件
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        load_dotenv(env_path)
        
        DB_HOST = os.environ.get('DB_HOST')
        DB_PORT = os.environ.get('DB_PORT')
        DB_USER = os.environ.get('DB_USER')
        DB_PASSWORD = os.environ.get('DB_PASSWORD')
        DB_NAME = os.environ.get('DB_NAME')
        
        # 检查必要的环境变量
        if not all([DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME]):
            raise ImportError("Environment variables not found in .env")
        
        print("使用.env文件中的数据库配置")
        
    except (ImportError, FileNotFoundError):
        # 如果没有.env文件或python-dotenv库，使用默认配置或从utils导入
        try:
            from utils import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
            print("使用utils模块中的数据库配置")
        except ImportError:
            # 使用默认配置
            DB_HOST = "localhost"
            DB_PORT = "3306"
            DB_USER = "root"
            DB_PASSWORD = ""
            DB_NAME = "virtualservice"
            print("使用默认数据库配置")
    
    # 创建数据库实例
    db = VirtualServiceDB(
        host=DB_HOST,
        port=int(DB_PORT or '3306'),
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )
    
    try:
        print(f"正在连接数据库: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
        db.connect()
        print("数据库连接成功！")
        
        print("开始初始化数据库表结构...")
        db.init_tables()
        
        print("\n数据库初始化完成！")
        print(f"数据库连接: {db.user}@{db.host}:{db.port}/{db.database}")
        
    except Exception as e:
        import traceback
        print(f"初始化失败: {type(e).__name__}: {e}")
        print("详细错误信息:")
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
