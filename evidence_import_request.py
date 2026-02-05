import requests
import json
import os


class DifyAPIClient:
    """通用Dify API客户端"""

    def __init__(self, api_key="app-EcNwTuK7C7O76Hr9VGbuk2P3", base_url="http://127.0.0.1"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

        """这里的user填你的dify用户名"""

    def upload_file(self, file_path, user="xxx"):
        """上传文件到Dify"""
        upload_url = f"{self.base_url}/v1/files/upload"

        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'text/plain')}
            data = {'user': user}

            response = requests.post(upload_url, headers={'Authorization': f'Bearer {self.api_key}'},
                                   files=files, data=data, timeout=300)

        if response.status_code in [200, 201]:
            result = response.json()
            print(f"✅ 文件上传成功: {result['name']}")
            return result['id']
        else:
            print(f"❌ 文件上传失败: {response.status_code}")
            return None

    # 新增：触发工作流的方法
    def run_workflow(self, inputs, file_id=None, file_path=None, timeout=300, workflow_id=None):
        """
        触发 Dify 工作流。
        - inputs: dict, 工作流原有输入参数
        - file_id: 上传后返回的文件 id（可选）
        - file_path: 本地文件路径，用于从文件名生成 text 字段（可选）
        - workflow_id: 要触发的工作流 ID（必填）
        """
        if workflow_id is None:
            print("❌ 未指定工作流ID (workflow_id)。请在 main 中设置 WORKFLOW_ID。")
            return None

        # run_url = f"{self.base_url}/v1/workflows/run"
        run_url = f"{self.base_url}/v1/chat-messages"

        # 构造输入 payload，保留原有 inputs
        payload = {
            # "user": "api-script-hqa",  # 👈 必填
            "inputs": dict(inputs or {})
        }

        # 如果有文件，附带 file_id，并生成文本 "这是{文件名}证据"
        if file_id:
            payload['inputs']['file_id'] = file_id
            if file_path:
                filename = os.path.basename(file_path)
                payload['inputs']['text'] = f"这是{filename}证据"
            else:
                payload['inputs']['text'] = "这是上传的证据"

        try:
            payload = {
                "inputs": {},
                "query": "这是test_file.png证据",
                "user": "aaa",
                "response_mode": "blocking"
            }

            # 看着一条
            resp = requests.post(run_url, headers=self.headers, json=payload, timeout=60)
        except Exception as e:
            print(f"❌ 请求触发工作流时出错: {e}")
            return None

        if resp.status_code in (200, 201):
            try:
                result = resp.json()
            except Exception:
                result = resp.text
            print("✅ 工作流触发成功:", result)
            return result
        else:
            print(f"❌ 工作流触发失败: {resp.status_code} {resp.text}")
            return None


def main():
    # ========== 配置区域 ==========
    API_KEY = "app-EcNwTuK7C7O76Hr9VGbuk2P3"
    # API_KEY = "app-P2ggG1fc5X7Kx4T76xd8cwZ1"
    BASE_URL = "http://127.0.0.1"  # Dify服务地址
    FILE_PATH = "./黄麒安的简历.pdf"  # 文件路径


    # 工作流ID：请替换为你在 Dify 控制台对应的工作流 ID
    WORKFLOW_ID = "ef419c81-03af-4e66-88b7-829106cb3ea6"
    # WORKFLOW_ID = "4be219eb-36a9-4960-a77c-d29ffc871fcf"


    # 工作流输入参数 - 根据你的工作流配置修改
    WORKFLOW_INPUTS = {"query": "1"}

    # 是否使用文件
    USE_FILE = True
    TIMEOUT = 300  # 超时时间（秒）

    # 创建客户端
    client = DifyAPIClient(API_KEY, BASE_URL)

    # 上传文件（如果需要）
    file_id = None
    if USE_FILE and FILE_PATH:
        if not os.path.exists(FILE_PATH):
            print(f"❌ 文件不存在: {FILE_PATH}")
            return

        print(f"📤 上传文件: {FILE_PATH}")
        file_id = client.upload_file(FILE_PATH)
        # if file_id is None:
        #     return

    # 执行工作流（将 file_path 传入以生成 "这是{文件名}证据" 文本）
    print(f"🚀 执行工作流...")
    result = client.run_workflow(WORKFLOW_INPUTS, file_id=file_id, file_path=FILE_PATH, timeout=TIMEOUT, workflow_id=WORKFLOW_ID)

if __name__ == "__main__":
    main()
