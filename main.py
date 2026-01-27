from flask import Flask, request, jsonify, send_file
import os
import json
import threading

file_lock = threading.Lock()

def create_app(file_path: str = None):
    """Create and return the Flask application.

    If file_path is provided, use it as the metadata output file. Otherwise
    read the METADATA_FILE environment variable (or default to metadata.txt
    next to this module). Reading the env at call-time allows tests to set
    the env before creating the app.
    """
    app = Flask(__name__)

    @app.route('/', methods=['GET'])
    def index():
        # If an external service (or a client) sends requests to `/` but
        # includes a `file_name` query param (as Dify sometimes does), forward
        # the call to the evidence handler so it behaves as expected.
        print(f"Request to index path: {request.path}, full_path: {request.full_path}")
        if request.args.get('file_name'):
            # call the evidence handler directly so the same logic is reused
            return get_evidence()
        return 'Dify Webhook Receiver is running.', 200

    @app.route('/webhook', methods=['POST'])
    def dify_webhook():
        """
        支持两种请求：
        1) multipart/form-data:
           - form field 'metadata' : JSON 字符串 (可选)
           - file field 'evidence' : 单个或多个文件 (至少一个)
        2) application/json (原来行为)：整个 body 为 metadata JSON
        保存 evidence 到 evidence_source_file 目录，metadata 中附加 saved_files 列表并写入 metadata 文件。
        """
        # 先判断是否 multipart/form-data（包含文件上传）
        content_type = request.content_type or ''
        metadata = {}
        saved_files = []

        if content_type.startswith('multipart/form-data'):
            # 解析 metadata 字段（可选）
            metadata_str = request.form.get('metadata', '')
            if metadata_str:
                try:
                    metadata = json.loads(metadata_str)
                except Exception:
                    return jsonify({'error': 'metadata must be valid JSON'}), 400
            else:
                metadata = {}

            # 获取上传的文件列表（支持多个）
            files = request.files.getlist('evidence')
            if not files:
                return jsonify({'error': 'No evidence files uploaded under field "evidence"'}), 400

            base_dir = os.path.join(os.path.dirname(__file__), 'evidence_source_file')
            os.makedirs(base_dir, exist_ok=True)

            for f in files:
                if not f or not f.filename:
                    continue
                safe_name = f.filename
                if not safe_name:
                    continue
                save_path = os.path.join(base_dir, safe_name)
                # 如果存在同名文件，自动添加序号避免覆盖
                if os.path.exists(save_path):
                    name, ext = os.path.splitext(safe_name)
                    i = 1
                    while True:
                        candidate = f"{name}_{i}{ext}"
                        candidate_path = os.path.join(base_dir, candidate)
                        if not os.path.exists(candidate_path):
                            save_path = candidate_path
                            safe_name = candidate
                            break
                        i += 1
                try:
                    f.save(save_path)
                    saved_files.append(safe_name)
                except Exception as e:
                    return jsonify({'error': f'Failed to save file {safe_name}: {str(e)}'}), 500

            # 把保存的文件名写入 metadata 以便记录
            if saved_files:
                metadata.setdefault('saved_files', [])
                metadata['saved_files'].extend(saved_files)

        else:
            # 维持原本的 JSON 行为
            try:
                if request.is_json:
                    payload = request.get_json()
                else:
                    body_text = request.get_data(as_text=True)
                    payload = json.loads(body_text) if body_text else {}
            except Exception:
                return jsonify({'error': 'Request body must be valid JSON'}), 400

            metadata = payload
            saved_files = []

        # Serialize metadata to a compact JSON string and append to file with newline
        entry = json.dumps(metadata, ensure_ascii=False)
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with file_lock:
                with open(file_path, 'a', encoding='utf-8') as f:
                    f.write('\n' + entry + '\n')
        except Exception as e:
            return jsonify({'error': str(e)}), 500

        return jsonify({'status': 'ok', 'saved_files': saved_files}), 200

    # 新增：根据 query 参数 file_name 精确检索并返回 evidence 文件
    @app.route('/evidence', methods=['GET'])
    def get_evidence():
        """
        GET /evidence?file_name=<exact filename>
        如果在 evidence_source_file 目录下找到与 file_name 完全相同的文件名，则返回该文件；
        否则返回 404 JSON。

        为防止路径穿越，仅允许简单文件名（不包含路径分隔符），并使用安全检查。
        """
        print("Entered /evidence route")
        print(f"Request path: {request.path}, full_path: {request.full_path}")
        file_name = request.args.get('file_name')
        if not file_name:
            return jsonify({'error': 'Missing required query parameter: file_name'}), 400

        # Reject any path separators to avoid traversal
        if '/' in file_name or '\\' in file_name or os.path.basename(file_name) != file_name:
            return jsonify({'error': 'Invalid file_name'}), 400

        base_dir = os.path.join(os.path.dirname(__file__), 'evidence_source_file')
        if not os.path.isdir(base_dir):
            return jsonify({'error': 'evidence directory not found'}), 500

        # 精确匹配目录中的文件名（区分大小写，取决于文件系统）
        candidate_path = os.path.join(base_dir, file_name)
        if not os.path.isfile(candidate_path):
            # 如果没有精确匹配，则返回 404
            return jsonify({'error': 'File not found'}), 404

        try:
            # 使用 send_file 返回文件，作为附件下载
            return send_file(candidate_path, as_attachment=True)
        except Exception as e:
            return jsonify({'error': f'Failed to send file: {str(e)}'}), 500
    return app


if __name__ == '__main__':
    # Create and run the app for manual testing / development
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
