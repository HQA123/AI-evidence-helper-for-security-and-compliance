import requests
import os
import mimetypes
from tools.pdf_to_png import pdf_to_png_file

def upload_file(file_path, user, api_key):
    upload_url = "http://127.0.0.1/v1/files/upload"
    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    try:
        print("📤 上传文件中...", file_path)
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
                print("✅ 文件上传成功", filename)
                return response.json().get("id")
            else:
                print(f"❌ 文件上传失败: {response.status_code} {response.text}")
                return None

    except Exception as e:
        print(f"❌ 发生错误: {str(e)}")
        return None

def upload_files(file_paths, user, api_key):
    """Upload multiple files and return a list of upload IDs.

    Args:
        file_paths (list[str]): local paths to files to upload
        user (str): user identifier to include in upload metadata
        api_key (str): Bearer API key for authentication

    Returns:
        list[str]: list of upload IDs for successful uploads (order preserved)
    """
    ids = []
    for p in file_paths:
        fid = upload_file(p, user, api_key)
        if fid:
            ids.append(fid)
        else:
            print(f"⚠️ 上传失败，跳过: {p}")
    return ids


def run_workflow(file_ids, original_file_ids, user, api_key, response_mode="blocking"):
    """Run a workflow once with multiple uploaded files.

    The Dify workflow `inputs.myfiles` expects a list of file descriptors; this function
    builds that list from `file_ids` so a single workflow run can consume multiple images.
    """
    workflow_url = "http://127.0.0.1/v1/workflows/run"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "inputs": {
            "myfiles": [{
                "transfer_method": "local_file",
                "upload_file_id": fid,
                "type": "image"
            } for fid in file_ids],
            "original_file": [{
                "transfer_method": "local_file",
                "upload_file_id": fid,
                "type": "image"
            } for fid in original_file_ids],
        },
        "response_mode": response_mode,
        "user": user
    }

    try:
        print("运行工作流...", file_ids)
        response = requests.post(workflow_url, headers=headers, json=data)
        if response.status_code == 200:
            print("工作流执行成功")
            return response.json()
        else:
            print(f"工作流执行失败，状态码: {response.status_code} {response.text}")
            return {"status": "error", "message": f"Failed to execute workflow, status code: {response.status_code}"}
    except Exception as e:
        print(f"发生错误: {str(e)}")
        return {"status": "error", "message": str(e)}


def prepare_file_paths(file_paths, dst_dir='evidence_source_file2', dpi=300, sharpen=True):
    """Given a list of file paths, convert any PDF files to PNG(s) and return
    a flattened list of file paths (PNG or original non-PDF files).

    The generated PNGs are written under `dst_dir` (relative to project root)
    when a relative path is provided.
    """
    processed = []
    for p in file_paths:
        if not p:
            continue
        # treat both absolute and relative paths
        lower = p.lower()
        if lower.endswith('.pdf'):
            try:
                print(f"🔁 检测到 PDF，转换为 PNG: {p}")
                outputs = pdf_to_png_file(p, dst_dir=dst_dir, dpi=dpi, sharpen=sharpen)
                if outputs:
                    processed.extend(outputs)
                else:
                    print(f"⚠️ PDF 转换没有输出: {p}")
            except Exception as e:
                print(f"❌ 转换 PDF 失败 {p}: {e}")
        else:
            # if the file path is already a PNG or other image, keep it
            processed.append(p)
    return processed


if __name__ == "__main__":
    user = "difyuser"
    api_key = "app-P2ggG1fc5X7Kx4T76xd8cwZ1"

    # 要上传的多张图片
    file_paths = ["evidence_source_file/KU_培训内容截图.pdf"]
    original_path = file_paths
    # Convert any PDFs to PNG(s) and get a flattened list of file paths
    file_paths = prepare_file_paths(file_paths, dst_dir='evidence_source_file2')

    for p in original_path:
        if not p:
            continue
        # treat both absolute and relative paths
        lower = p.lower()
        if lower.endswith('.pdf'):
            # 批量上传
            file_ids = upload_files(file_paths, user, api_key)
            original_file_ids = upload_files(original_path, user, api_key)
        else:
            # 批量上传
            file_ids = upload_files(file_paths, user, api_key)
            original_file_ids = file_ids

    if file_ids:
        # 上传成功后，调用一次工作流，传入所有文件 id
        result = run_workflow(file_ids, original_file_ids, user, api_key)
        print(result)
    else:
        print("文件上传失败，无法执行工作流")