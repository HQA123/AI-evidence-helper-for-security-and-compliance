from flask import Flask, request, jsonify, send_file
import os
import json
import threading
import tempfile
import shutil
import time
import hmac
import hashlib
import base64
import uuid
import urllib.parse

# URL signing secret (set via env for production)
URL_SIGN_SECRET = os.environ.get('URL_SIGN_SECRET', 'dev-sign-secret')
URL_SIGN_TTL = int(os.environ.get('URL_SIGN_TTL', '300'))  # seconds

# import the single-file converter
from tools.pdf_to_png import pdf_to_png_file

file_lock = threading.Lock()
# map token -> temp_dir (short-lived). Use in-memory mapping; tokens are UUID4 strings.
token_map = {}
token_map_lock = threading.Lock()

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
        GET /evidence?file_name=<filename-without-extension-or-part>
        Accept a `file_name` that may omit the file extension. Matching ignores
        the file suffix and is case-insensitive; partial (substring) matches
        are supported. Exact match on the name-without-extension is preferred.

        Behavior:
        - If a single exact (name without ext) match is found -> return the file.
        - If multiple exact matches -> return JSON with candidate filenames.
        - Else if single fuzzy (substring) match -> return the file.
        - Else if multiple fuzzy matches -> return JSON with candidate filenames.
        - Else -> 404 JSON.
        """
        print("Entered /evidence route")
        print(f"Request path: {request.path}, full_path: {request.full_path}")
        file_name = request.args.get('file_name')
        if not file_name:
            return jsonify({'error': 'Missing required query parameter: file_name'}), 400

        # Reject any path separators to avoid traversal
        if '/' in file_name or '\\' in file_name or os.path.basename(file_name) != file_name:
            return jsonify({'error': 'Invalid file_name'}), 400

        # Normalize the incoming query: strip, lower, and drop extension if provided
        query_base = os.path.splitext(file_name.strip())[0].lower()
        if not query_base:
            return jsonify({'error': 'Invalid file_name'}), 400

        base_dir = os.path.join(os.path.dirname(__file__), 'evidence_source_file')
        if not os.path.isdir(base_dir):
            return jsonify({'error': 'evidence directory not found'}), 500

        # Gather candidate files (only files, ignore subdirs)
        all_files = [f for f in os.listdir(base_dir) if os.path.isfile(os.path.join(base_dir, f))]
        exact_matches = []
        fuzzy_matches = []

        for fname in all_files:
            name_no_ext = os.path.splitext(fname)[0]
            lower_name = name_no_ext.lower()
            if lower_name == query_base:
                exact_matches.append(fname)
            elif query_base in lower_name:
                fuzzy_matches.append(fname)

        # Prefer exact matches
        if len(exact_matches) == 1:
            candidate_path = os.path.join(base_dir, exact_matches[0])
            try:
                return send_file(candidate_path, as_attachment=True)
            except Exception as e:
                return jsonify({'error': f'Failed to send file: {str(e)}'}), 500
        elif len(exact_matches) > 1:
            return jsonify({'error': 'Multiple exact matches found', 'candidates': exact_matches}), 300

        # Fall back to fuzzy matches
        if len(fuzzy_matches) == 1:
            candidate_path = os.path.join(base_dir, fuzzy_matches[0])
            try:
                return send_file(candidate_path, as_attachment=True)
            except Exception as e:
                return jsonify({'error': f'Failed to send file: {str(e)}'}), 500
        elif len(fuzzy_matches) > 1:
            return jsonify({'error': 'Multiple fuzzy matches found', 'candidates': fuzzy_matches}), 300

        return jsonify({'error': 'File not found'}), 404

    @app.route('/pdf_to_png', methods=['POST'])
    def pdf_to_png_route():
        """Convert a PDF to PNG(s).

        Accepts multipart/form-data with a file field named 'pdf', or a form/json
        parameter 'pdf' that names a file present in the server's
        `evidence_source_file/` directory. Optional parameters:
          - dpi (int)
          - no_sharpen (flag, present to disable sharpening)

        Returns:
          - If single PNG produced: attachment of that PNG.
          - If multiple PNGs produced: JSON with short-lived token, list of PNG basenames
            and per-file URLs that can be fetched with `/png?token=...&name=...`.
        """
        print("Entered /pdf_to_png route")

        # Determine source PDF: support file upload or a server-side filename
        uploaded = request.files.get('pdf')

        temp_dir = tempfile.mkdtemp(prefix='pdf2png_')
        try:
            if uploaded:
                # Handle uploaded PDF file
                upload_name = uploaded.filename or 'uploaded.pdf'
                upload_name = os.path.basename(upload_name)
                if not upload_name.lower().endswith('.pdf'):
                    shutil.rmtree(temp_dir)
                    return jsonify({'error': 'Uploaded file must have .pdf extension'}), 400
                pdf_path = os.path.join(temp_dir, upload_name)
                uploaded.save(pdf_path)

                # read options from form (multipart)
                try:
                    dpi = int(request.form.get('dpi', 300))
                except Exception:
                    dpi = 300
                no_sharpen = request.form.get('no_sharpen') is not None
                sharpen = not no_sharpen

                outputs = pdf_to_png_file(pdf_path, dst_dir=temp_dir, dpi=dpi, sharpen=sharpen)
            else:
                # No upload: expect a filename parameter referencing evidence_source_file
                # Accept form, JSON or query param for compatibility
                pdf_param = None
                if request.form and 'pdf' in request.form:
                    pdf_param = request.form.get('pdf')
                elif request.is_json:
                    json_body = request.get_json(silent=True) or {}
                    pdf_param = json_body.get('pdf')
                else:
                    pdf_param = request.args.get('pdf')

                if not pdf_param:
                    shutil.rmtree(temp_dir)
                    return jsonify({'error': 'Missing required parameter: pdf (or upload a file)'}), 400

                # prevent path traversal: only allow basename
                if '/' in pdf_param or '\\' in pdf_param or os.path.basename(pdf_param) != pdf_param:
                    shutil.rmtree(temp_dir)
                    return jsonify({'error': 'Invalid pdf parameter'}), 400

                base_dir = os.path.join(os.path.dirname(__file__), 'evidence_source_file')
                src_pdf_path = os.path.join(base_dir, pdf_param)
                if not os.path.isfile(src_pdf_path):
                    shutil.rmtree(temp_dir)
                    return jsonify({'error': 'PDF file not found'}), 404

                try:
                    dpi = int(request.form.get('dpi', request.args.get('dpi', 300)))
                except Exception:
                    dpi = 300
                no_sharpen = (request.form.get('no_sharpen') is not None) or (request.args.get('no_sharpen') is not None)
                sharpen = not no_sharpen

                # Generate outputs into our temp_dir
                outputs = pdf_to_png_file(src_pdf_path, dst_dir=temp_dir, dpi=dpi, sharpen=sharpen)
        except Exception as e:
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass
            return jsonify({'error': f'Conversion failed: {str(e)}'}), 500

        if not outputs:
            shutil.rmtree(temp_dir)
            return jsonify({'error': 'No PNGs were produced'}), 500

        if len(outputs) == 1:
            # return single PNG file
            out_path = outputs[0]
            # schedule cleanup of temp_dir after response
            def _cleanup():
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass
            threading.Timer(30.0, _cleanup).start()
            try:
                return send_file(out_path, as_attachment=True)
            except Exception as e:
                return jsonify({'error': f'Failed to send PNG: {str(e)}'}), 500

        if len(outputs) > 1:
            # Create a short-lived token and return signed URLs for each PNG
            token = uuid.uuid4().hex
            with token_map_lock:
                token_map[token] = temp_dir

            # schedule cleanup of temp_dir and token after TTL
            def _cleanup_token():
                try:
                    with token_map_lock:
                        token_map.pop(token, None)
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass
            threading.Timer(URL_SIGN_TTL, _cleanup_token).start()

            host = request.url_root.rstrip('/')
            files = []
            now_ts = int(time.time())
            for p in outputs:
                name = os.path.basename(p)
                ts = now_ts
                nonce = uuid.uuid4().hex
                msg = f"{token}:{name}:{ts}:{nonce}".encode('utf-8')
                digest = hmac.new(URL_SIGN_SECRET.encode('utf-8'), msg, hashlib.sha256).digest()
                sign = base64.urlsafe_b64encode(digest).decode('utf-8')
                q = urllib.parse.urlencode({'token': token, 'name': name, 'timestamp': str(ts), 'nonce': nonce, 'sign': sign})
                url = f"{host}/png?{q}"
                # include the file basename along with the url so callers can map names
                files.append({'name': name, 'url': url})

            # debug: log the files we will return (useful when files appears empty)
            print(f"pdf_to_png: returning {len(files)} file(s): {[f['name'] for f in files]}")

            return jsonify({'status': 'success', 'files': files}), 200

    @app.route('/png', methods=['GET'])
    def serve_png():
        # Serve a single PNG using token+name and validate optional signature/timestamp
        token = request.args.get('token')
        name = request.args.get('name')
        if not token or not name:
            return jsonify({'error': 'Missing token or name'}), 400
        with token_map_lock:
            temp_dir_lookup = token_map.get(token)
        if not temp_dir_lookup:
            return jsonify({'error': 'Invalid or expired token'}), 404
        # security: ensure name is a basename
        if '/' in name or '\\' in name or os.path.basename(name) != name:
            return jsonify({'error': 'Invalid name'}), 400
        file_path = os.path.join(temp_dir_lookup, name)
        if not os.path.isfile(file_path):
            return jsonify({'error': 'File not found'}), 404

        # validate signature and timestamp if provided
        sign = request.args.get('sign')
        timestamp = request.args.get('timestamp')
        nonce = request.args.get('nonce')
        if sign and timestamp and nonce:
            try:
                ts = int(timestamp)
            except Exception:
                return jsonify({'error': 'Invalid timestamp'}), 400
            now = int(time.time())
            if abs(now - ts) > URL_SIGN_TTL:
                return jsonify({'error': 'URL expired'}), 403
            expected_msg = f"{token}:{name}:{timestamp}:{nonce}".encode('utf-8')
            expected_digest = hmac.new(URL_SIGN_SECRET.encode('utf-8'), expected_msg, hashlib.sha256).digest()
            expected_sign = base64.urlsafe_b64encode(expected_digest).decode('utf-8')
            if not hmac.compare_digest(sign, expected_sign):
                return jsonify({'error': 'Invalid sign'}), 403

        try:
            return send_file(file_path, as_attachment=True)
        except Exception as e:
            return jsonify({'error': f'Failed to send file: {str(e)}'}), 500

    return app


if __name__ == '__main__':
    # Create and run the app for manual testing / development
    app = create_app("metadata.txt")
    app.run(host='0.0.0.0', port=5000, debug=True)
