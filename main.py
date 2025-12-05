from flask import Flask, request, jsonify, send_file, Response
import os
import json
import threading
import io
import uuid
from werkzeug.utils import secure_filename

# Add imports for PDF processing (dynamic to avoid static linter issues)
import importlib
pymupdf = None
Image = None
try:
    pymupdf = importlib.import_module('pymupdf')
except Exception:
    pymupdf = None
try:
    pil_image = importlib.import_module('PIL.Image')
    Image = pil_image
except Exception:
    Image = None

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

    @app.route('/pdf_to_png', methods=['POST']) # unfinished
    def pdf_to_png_route():
        """
        Convert an uploaded PDF to PNG images.
        Accepts multipart/form-data with field 'pdf' (file) and optional 'zoom' (int).
        Returns a single PNG if the PDF has one page, otherwise a ZIP of PNGs.
        """
        if pymupdf is None or Image is None:
            return jsonify({'error': 'Server missing dependencies for PDF processing (pymupdf, Pillow)'}), 500

        if not request.content_type or not request.content_type.startswith('multipart/form-data'):
            return jsonify({'error': 'Content-Type must be multipart/form-data with a "pdf" file field'}), 400

        pdf_file = request.files.get('pdf')
        if not pdf_file or not pdf_file.filename:
            return jsonify({'error': 'No PDF file uploaded under field "pdf"'}), 400

        # Read zoom parameter (optional)
        zoom_param = request.form.get('zoom')
        try:
            zoom = 4 if zoom_param is None or zoom_param == '' else int(zoom_param)
        except Exception:
            return jsonify({'error': 'zoom must be an integer'}), 400

        # Read file bytes
        pdf_bytes = pdf_file.read()
        if not pdf_bytes:
            return jsonify({'error': 'Uploaded PDF is empty'}), 400

        try:
            # Open PDF with PyMuPDF
            doc = pymupdf.open(stream=io.BytesIO(pdf_bytes), filetype='pdf')
        except Exception as e:
            return jsonify({'error': f'Invalid PDF file: {str(e)}'}), 400

        try:
            total_pages = doc.page_count
            if total_pages == 0:
                return jsonify({'error': 'The PDF file contains no pages.'}), 400

            images = []  # list of tuples (filename, bytes)
            original_name = secure_filename(pdf_file.filename)
            base_name = original_name.rsplit('.', 1)[0]

            for i in range(total_pages):
                page = doc.load_page(i)
                mat = pymupdf.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)

                buf = io.BytesIO()
                img.save(buf, format='PNG')
                buf.seek(0)
                fname = f"{base_name}_page{i+1}.png"
                images.append((fname, buf.read()))

            # If single image, return directly
            if len(images) == 1:
                img_bytes = images[0][1]
                return send_file(io.BytesIO(img_bytes), mimetype='image/png', as_attachment=True,
                                 download_name=images[0][0])

            # Multiple images -> return multipart/mixed response with each image as a part
            # Use a random boundary to separate parts
            boundary = '=====' + uuid.uuid4().hex
            CRLF = '\r\n'

            def generate_parts(img_list, bdr):
                for fname, b in img_list:
                    # part header
                    yield (f'--{bdr}{CRLF}').encode('utf-8')
                    yield (f'Content-Type: image/png{CRLF}').encode('utf-8')
                    # Use simple Content-Disposition with filename; if clients need RFC5987, adapt accordingly
                    yield (f'Content-Disposition: attachment; filename="{fname}"{CRLF}{CRLF}').encode('utf-8')
                    # image bytes
                    yield b
                    yield CRLF.encode('utf-8')
                # final boundary
                yield (f'--{bdr}--{CRLF}').encode('utf-8')

            return Response(generate_parts(images, boundary),
                            mimetype=f'multipart/mixed; boundary={boundary}')
        finally:
            try:
                doc.close()
            except Exception:
                pass

    return app


if __name__ == '__main__':
    # Create and run the app for manual testing / development
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
