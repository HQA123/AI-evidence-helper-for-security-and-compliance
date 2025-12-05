from flask import Flask, request, jsonify, send_file
import os
import json
import threading
import io
import zipfile
import mimetypes

file_lock = threading.Lock()

def create_app(file_path: str = None):
    """Create and return the Flask application.

    If file_path is provided, use it as the metadata output file. Otherwise
    read the METADATA_FILE environment variable (or default to metadata.txt
    next to this module). Reading the env at call-time allows tests to set
    the env before creating the app.
    """
    app = Flask(__name__)

    # Determine file path at app creation time so tests can override via env
    if file_path is None:
        file_path = os.environ.get(
            'METADATA_FILE', os.path.join(os.path.dirname(__file__), 'metadata.txt')
        )

    @app.route('/', methods=['GET'])
    def index():
        return 'Dify Webhook Receiver is running.', 200

    @app.route('/webhook', methods=['POST'])
    def dify_webhook():
        """
        支持两种请求：
        1) multipart/form-data:
           - form field 'metadata' : JSON 字符串 (可选)
           - file field 'evidence' : 单个或多个文件 (至少一个)
        2) application/json (原来行为)：整个 body 为 metadata JSON
        保存 evidence 到 evidece_source_file 目录，metadata 中附加 saved_files 列表并写入 metadata 文件。
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

            base_dir = os.path.join(os.path.dirname(__file__), 'evidece_source_file')
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

    @app.route('/get_evidence', methods=['POST'])
    def get_evidence():
        """
        Accept JSON body: {"file_names": ["a.png", "b.pdf", ...]}
        Search in evidece_source_file directory (same dir as this module) and return files.
        If multiple files requested, return a zip archive. If any requested file missing, return 404 with details.
        """
        try:
            if request.is_json:
                payload = request.get_json()
            else:
                body_text = request.get_data(as_text=True)
                payload = json.loads(body_text) if body_text else {}
        except Exception:
            return jsonify({'error': 'Request body must be valid JSON'}), 400

        file_names = payload.get('file_names')
        if not isinstance(file_names, list) or not all(isinstance(n, str) for n in file_names):
            return jsonify({'error': 'file_names must be a list of strings'}), 400

        # Evidence directory (relative to this file)
        base_dir = os.path.join(os.path.dirname(__file__), 'evidece_source_file')

        found_files = []
        missing = []
        for name in file_names:
            # Security checks: no absolute paths, no path traversal, only basename allowed
            if not name or os.path.isabs(name) or '..' in name or '/' in name or '\\' in name:
                missing.append(name)
                continue
            candidate = os.path.join(base_dir, name)
            if os.path.isfile(candidate):
                found_files.append(candidate)
            else:
                missing.append(name)

        if missing:
            return jsonify({'error': 'Some files not found', 'missing': missing}), 404

        if len(found_files) == 1:
            file_path = found_files[0]
            # Guess mimetype, fallback to octet-stream
            mime_type, _ = mimetypes.guess_type(file_path)
            return send_file(file_path, mimetype=mime_type or 'application/octet-stream',
                             as_attachment=True, download_name=os.path.basename(file_path))
        else:
            # Multiple files -> create in-memory zip
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                for fp in found_files:
                    zf.write(fp, arcname=os.path.basename(fp))
            buf.seek(0)
            return send_file(buf, mimetype='application/zip', as_attachment=True,
                             download_name='evidence_files.zip')

    return app


if __name__ == '__main__':
    # Create and run the app for manual testing / development
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
