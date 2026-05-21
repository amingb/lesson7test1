import os
import io
import base64
from html import escape

from flask import Flask, request, Response, render_template_string
import qrcode
from qrcode.constants import (
    ERROR_CORRECT_L,
    ERROR_CORRECT_M,
    ERROR_CORRECT_Q,
    ERROR_CORRECT_H,
)


app = Flask(__name__)

MAX_TEXT_LENGTH = 500
MAX_SIZE = 1024
MIN_SIZE = 128
MAX_BORDER = 20
MIN_BORDER = 0

ERROR_LEVELS = {
    "L": ERROR_CORRECT_L,
    "M": ERROR_CORRECT_M,
    "Q": ERROR_CORRECT_Q,
    "H": ERROR_CORRECT_H,
}


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="utf-8">
    <title>QRコード生成ツール</title>
    <style>
        body {
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: #f5f5f5;
            color: #222;
            margin: 0;
            padding: 32px;
        }
        .container {
            max-width: 760px;
            margin: 0 auto;
            background: #fff;
            padding: 28px;
            border-radius: 14px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
        }
        h1 {
            margin-top: 0;
            padding: 16px;
            background: #222;
            color: #fff;
            border-radius: 10px;
            font-size: 26px;
        }
        label {
            display: block;
            margin-top: 16px;
            font-weight: bold;
        }
        input, select, textarea {
            width: 100%;
            box-sizing: border-box;
            margin-top: 6px;
            padding: 10px;
            font-size: 16px;
        }
        textarea {
            min-height: 120px;
        }
        .row {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 12px;
        }
        button {
            margin-top: 20px;
            padding: 12px 18px;
            font-size: 16px;
            font-weight: bold;
            background: #222;
            color: #fff;
            border: none;
            border-radius: 8px;
            cursor: pointer;
        }
        button:hover {
            opacity: 0.85;
        }
        .error {
            margin-top: 18px;
            padding: 12px;
            background: #ffecec;
            color: #b00020;
            border: 1px solid #ffb3b3;
            border-radius: 8px;
        }
        .preview {
            margin-top: 28px;
            padding: 20px;
            background: #fafafa;
            border: 1px solid #ddd;
            border-radius: 12px;
            text-align: center;
        }
        .preview img {
            max-width: 100%;
            height: auto;
            background: #fff;
            padding: 8px;
            border: 1px solid #ddd;
        }
        .download {
            display: inline-block;
            margin-top: 16px;
            padding: 10px 14px;
            background: #0070f3;
            color: #fff;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
        }
        .note {
            color: #666;
            font-size: 14px;
            margin-top: 8px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>QRコード生成ツール</h1>

        <form method="post" action="/">
            <label for="text">QRコードにするテキスト</label>
            <textarea id="text" name="text" required maxlength="{{ max_text_length }}">{{ text }}</textarea>
            <div class="note">最大 {{ max_text_length }} 文字まで入力できます。</div>

            <div class="row">
                <div>
                    <label for="size">サイズ(px)</label>
                    <input id="size" name="size" type="number" min="{{ min_size }}" max="{{ max_size }}" value="{{ size }}">
                </div>

                <div>
                    <label for="border">余白(border)</label>
                    <input id="border" name="border" type="number" min="{{ min_border }}" max="{{ max_border }}" value="{{ border }}">
                </div>

                <div>
                    <label for="error_level">誤り訂正</label>
                    <select id="error_level" name="error_level">
                        {% for level in ["L", "M", "Q", "H"] %}
                            <option value="{{ level }}" {% if error_level == level %}selected{% endif %}>{{ level }}</option>
                        {% endfor %}
                    </select>
                </div>
            </div>

            <button type="submit">QRコードを生成</button>
        </form>

        {% if error %}
            <div class="error">{{ error }}</div>
        {% endif %}

        {% if qr_data_url %}
            <div class="preview">
                <h2>プレビュー</h2>
                <img src="{{ qr_data_url }}" alt="生成されたQRコード">
                <br>
                <a class="download" href="{{ qr_data_url }}" download="qrcode.png">PNGをダウンロード</a>
            </div>
        {% endif %}
    </div>
</body>
</html>
"""


def to_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def generate_qr_png_data_url(text, size, border, error_level):
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_LEVELS[error_level],
        box_size=10,
        border=border,
    )
    qr.add_data(text)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((size, size))

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    png_base64 = base64.b64encode(buffer.getvalue()).decode("ascii")

    return f"data:image/png;base64,{png_base64}"


@app.route("/", methods=["GET", "POST"])
def index():
    text = ""
    size = 512
    border = 4
    error_level = "M"
    error = ""
    qr_data_url = ""

    if request.method == "POST":
        text = request.form.get("text", "").strip()
        size = to_int(request.form.get("size"), 512)
        border = to_int(request.form.get("border"), 4)
        error_level = request.form.get("error_level", "M").upper()

        if not text:
            error = "テキストを入力してください。"
        elif len(text) > MAX_TEXT_LENGTH:
            error = f"テキストは最大{MAX_TEXT_LENGTH}文字までです。"
        elif size < MIN_SIZE or size > MAX_SIZE:
            error = f"サイズは{MIN_SIZE}px以上、{MAX_SIZE}px以下で指定してください。"
        elif border < MIN_BORDER or border > MAX_BORDER:
            error = f"余白は{MIN_BORDER}以上、{MAX_BORDER}以下で指定してください。"
        elif error_level not in ERROR_LEVELS:
            error = "誤り訂正レベルは L / M / Q / H から選んでください。"
        else:
            try:
                qr_data_url = generate_qr_png_data_url(text, size, border, error_level)
            except Exception:
                error = "QRコードの生成中にエラーが発生しました。入力内容を確認してください。"

    html = render_template_string(
        HTML_TEMPLATE,
        text=escape(text),
        size=size,
        border=border,
        error_level=error_level,
        error=error,
        qr_data_url=qr_data_url,
        max_text_length=MAX_TEXT_LENGTH,
        max_size=MAX_SIZE,
        min_size=MIN_SIZE,
        max_border=MAX_BORDER,
        min_border=MIN_BORDER,
    )

    return Response(html, content_type="text/html; charset=utf-8")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    debug = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes", "on")
    app.run(host="0.0.0.0", port=port, debug=debug)