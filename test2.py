import requests
import os
import mimetypes
import json

def upload_file(file_path, user):
    upload_url = "http://127.0.0.1/v1/files/upload"
    headers = {
        "Authorization": "Bearer app-P2ggG1fc5X7Kx4T76xd8cwZ1",
    }

    try:
        print("📤 上传文件中...")
        with open(file_path, 'rb') as file:
            filename = os.path.basename(file_path)
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type is None:
                mime_type = "application/octet-stream"

            files = {
                'file': (filename, file, mime_type)
            }
            data = {
                "user": user
            }

            response = requests.post(upload_url, headers=headers, files=files, data=data)

            if response.status_code in (200, 201):
                print("✅ 文件上传成功")
                return response.json().get("id")
            else:
                print(f"❌ 文件上传失败: {response.status_code} {response.text}")
                return None

    except Exception as e:
        print(f"❌ 发生错误: {str(e)}")
        return None

def run_workflow(file_id, user, response_mode="blocking"):
    workflow_url = "http://127.0.0.1/v1/workflows/run"
    headers = {
        "Authorization": "Bearer app-P2ggG1fc5X7Kx4T76xd8cwZ1",
        "Content-Type": "application/json"
    }

    data = {
        "inputs": {
            "myfiles": [{
                "transfer_method": "local_file",
                "upload_file_id": file_id,
                "type": "image"
            }],
            "text": f"如果你看得到，请在file_name字段返回我看到了"  # 示例文本
        },
        "response_mode": response_mode,
        "user": user
    }

    try:
        print("运行工作流...")
        response = requests.post(workflow_url, headers=headers, json=data)
        if response.status_code == 200:
            print("工作流执行成功")
            return response.json()
        else:
            print(f"工作流执行失败，状态码: {response.status_code}")
            return {"status": "error", "message": f"Failed to execute workflow, status code: {response.status_code}"}
    except Exception as e:
        print(f"发生错误: {str(e)}")
        return {"status": "error", "message": str(e)}

# 使用示例
file_path = "test_file.png"
user = "difyuser"

# 上传文件
file_id = upload_file(file_path, user)
if file_id:
    # 文件上传成功，继续运行工作流
    result = run_workflow(file_id, user)
    print(result)
else:
    print("文件上传失败，无法执行工作流")