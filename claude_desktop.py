from mitmproxy import http
from datetime import datetime
import json
import os
import re
import hashlib

OUTPUT_DIR = "claude_web_output"
FILES_DIR = os.path.join(OUTPUT_DIR, "files")

CLEAN_FILE = os.path.join(OUTPUT_DIR, "web_prompts.json")
RAW_FILE = os.path.join(OUTPUT_DIR, "raw_web_logs.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(FILES_DIR, exist_ok=True)

pending_attachments = []

VALID_EXTENSIONS = [
    ".pdf", ".doc", ".docx", ".txt", ".csv",
    ".xls", ".xlsx", ".ppt", ".pptx",
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"
]

VALID_MIME_TYPES = [
    "application/pdf",
    "text/plain",
    "text/csv",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
    "image/bmp",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
]


def load_json_file(path):
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def safe_get_request_text(flow):
    try:
        return flow.request.get_text(strict=False)
    except:
        try:
            return flow.request.content.decode("utf-8", errors="ignore")
        except:
            return ""


def safe_get_response_text(flow):
    try:
        return flow.response.get_text(strict=False)
    except:
        try:
            return flow.response.content.decode("utf-8", errors="ignore")
        except:
            return ""


def is_claude(flow):
    host = flow.request.pretty_host.lower()

    return (
        "claude.ai" in host
        or "anthropic.com" in host
        or "claudeusercontent.com" in host
    )


def is_completion(flow):
    url = flow.request.pretty_url.lower()

    return (
        is_claude(flow)
        and flow.request.method == "POST"
        and "/cdn-cgi/" not in url
        and (
            "/completion" in url
            or "/chat_conversations/" in url
            or "/messages" in url
            or "/chat" in url
        )
    )


def is_upload_or_file_request(flow):
    url = flow.request.pretty_url.lower()
    content_type = flow.request.headers.get("content-type", "").lower()

    return (
        is_claude(flow)
        and flow.request.method in ["POST", "PUT"]
        and "/cdn-cgi/" not in url
        and (
            "upload" in url
            or "file" in url
            or "files" in url
            or "attachment" in url
            or "document" in url
            or "multipart/form-data" in content_type
            or any(mime in content_type for mime in VALID_MIME_TYPES)
        )
    )


def extract_conversation_id(url):
    match = re.search(r"chat_conversations/([a-zA-Z0-9-]+)", url)
    return match.group(1) if match else None


def file_type_from_name(file_name):
    if not file_name:
        return None

    ext = os.path.splitext(file_name.lower())[1]

    mime_map = {
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain",
        ".csv": "text/csv",
        ".xls": "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".ppt": "application/vnd.ms-powerpoint",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp"
    }

    return mime_map.get(ext)


def is_real_file(file_name=None, file_type=None):
    if file_type:
        for mime in VALID_MIME_TYPES:
            if mime in file_type:
                return True

    if file_name:
        ext = os.path.splitext(file_name.lower())[1]
        if ext in VALID_EXTENSIONS:
            return True

    return False


def add_attachment(file_name=None, file_type=None, file_id=None, source="unknown", saved_path=None):
    global pending_attachments

    if not file_type:
        file_type = file_type_from_name(file_name)

    if not is_real_file(file_name, file_type):
        return

    item = {
        "file_name": file_name,
        "file_type": file_type,
        "file_id": file_id,
        "saved_path": saved_path
    }

    # If saved file exists, remove metadata-only duplicate
    if saved_path:
        pending_attachments = [
            existing for existing in pending_attachments
            if existing.get("file_name") != file_name
        ]
        pending_attachments.append(item)
        return

    # If saved file already exists, don't add metadata-only duplicate
    for existing in pending_attachments:
        if existing.get("file_name") == file_name and existing.get("saved_path"):
            return

    # Avoid exact duplicate
    for existing in pending_attachments:
        if existing == item:
            return

    pending_attachments.append(item)

def merge_files(files):
    merged = {}

    for f in files:
        name = f.get("file_name")

        if name:
            name = re.sub(
                r"_[0-9a-f]{12,36}(?=\.)",
                "",
                name,
                flags=re.IGNORECASE
            )

        if not name:
            continue

        key = name.lower()

        if key not in merged:
            merged[key] = {
                "file_name": name,
                "file_type": f.get("file_type"),
                "file_id": f.get("file_id"),
                "saved_path": f.get("saved_path")
            }
        else:
            if f.get("file_id"):
                merged[key]["file_id"] = f.get("file_id")

            if f.get("saved_path"):
                merged[key]["saved_path"] = f.get("saved_path")

            if f.get("file_type"):
                merged[key]["file_type"] = f.get("file_type")

    return list(merged.values())


def extract_files_from_json(data, source):
    def walk(obj):
        if isinstance(obj, dict):
            file_name = (
                obj.get("file_name")
                or obj.get("filename")
                or obj.get("name")
                or obj.get("display_name")
                or obj.get("title")
            )

            file_type = (
                obj.get("mime_type")
                or obj.get("mimeType")
                or obj.get("content_type")
                or obj.get("contentType")
            )

            file_id = (
                obj.get("file_id")
                or obj.get("file_uuid")
                or obj.get("uuid")
                or obj.get("id")
                or obj.get("document_id")
            )

            add_attachment(file_name, file_type, file_id, source)

            for value in obj.values():
                walk(value)

        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)


def extract_files_from_text(text, source):
    if not text:
        return

    pattern = r'([A-Za-z0-9_\-\s().]+(?:\.pdf|\.docx|\.doc|\.txt|\.csv|\.xlsx|\.xls|\.pptx|\.ppt|\.png|\.jpg|\.jpeg|\.webp|\.gif|\.bmp))'

    matches = re.findall(pattern, text, flags=re.IGNORECASE)

    for file_name in matches:
        add_attachment(file_name=file_name.strip(), source=source)


def extract_file_from_multipart(content):
    # PDF
    start = content.find(b"%PDF")
    if start != -1:
        end = content.rfind(b"%%EOF")
        if end != -1:
            return content[start:end + 5], ".pdf"
        return content[start:], ".pdf"

    # PNG
    start = content.find(b"\x89PNG\r\n\x1a\n")
    if start != -1:
        return content[start:], ".png"

    # JPG
    start = content.find(b"\xff\xd8\xff")
    if start != -1:
        end = content.rfind(b"\xff\xd9")
        if end != -1:
            return content[start:end + 2], ".jpg"
        return content[start:], ".jpg"

    # GIF
    for sig in [b"GIF87a", b"GIF89a"]:
        start = content.find(sig)
        if start != -1:
            return content[start:], ".gif"

    # WEBP
    start = content.find(b"RIFF")
    if start != -1 and b"WEBP" in content[start:start + 30]:
        return content[start:], ".webp"

    # DOCX/XLSX/PPTX are ZIP-based
    start = content.find(b"PK\x03\x04")
    if start != -1:
        return content[start:], ".zip"

    return content, ".bin"


def clean_filename(name):
    name = os.path.basename(name)
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    return name.strip()


def get_original_filename(raw_content):
    match = re.search(
        rb'filename="([^"]+)"',
        raw_content,
        re.IGNORECASE
    )

    if match:
        return match.group(1).decode("utf-8", errors="ignore")

    match = re.search(
        rb"filename\*=UTF-8''([^;\r\n]+)",
        raw_content,
        re.IGNORECASE
    )

    if match:
        return match.group(1).decode("utf-8", errors="ignore")

    return None


def save_binary_if_file(flow, source):
    raw_content = flow.request.content

    if not raw_content:
        return None

    content_type = flow.request.headers.get("content-type", "").lower()

    file_bytes, extension = extract_file_from_multipart(raw_content)

    if extension == ".bin":
        if "application/pdf" in content_type:
            extension = ".pdf"
        elif "image/png" in content_type:
            extension = ".png"
        elif "image/jpeg" in content_type or "image/jpg" in content_type:
            extension = ".jpg"
        elif "image/webp" in content_type:
            extension = ".webp"
        elif "image/gif" in content_type:
            extension = ".gif"
        elif "image/bmp" in content_type:
            extension = ".bmp"
        elif "text/plain" in content_type:
            extension = ".txt"
        elif "text/csv" in content_type:
            extension = ".csv"

    original_name = get_original_filename(raw_content)
    file_hash = hashlib.sha256(file_bytes).hexdigest()[:12]

    if original_name:
        filename = clean_filename(original_name)
    else:
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file_hash}{extension}"

    path = os.path.join(FILES_DIR, filename)

    # Avoid overwrite if same filename uploaded again
    if os.path.exists(path):
        name, ext = os.path.splitext(filename)
        filename = f"{name}_{file_hash}{ext}"
        path = os.path.join(FILES_DIR, filename)

    with open(path, "wb") as f:
        f.write(file_bytes)

    add_attachment(
        file_name=original_name if original_name else filename,
        file_type=file_type_from_name(filename),
        file_id=file_hash,
        source=source,
        saved_path=path
    )

    print("\n========== FILE SAVED ==========")
    print("Original filename:", original_name)
    print("Saved path:", path)
    print("Extension:", extension)
    print("Size:", len(file_bytes))
    print("================================\n")

    return path


def extract_prompt_from_request(request_text):
    if not request_text:
        return ""

    try:
        data = json.loads(request_text)
    except:
        return request_text.strip()

    texts = []

    def walk(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                key_lower = str(key).lower()

                if key_lower in ["text", "content", "prompt", "message"]:
                    if isinstance(value, str) and value.strip():
                        texts.append(value.strip())

                walk(value)

        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)

    unique = []
    for text in texts:
        if text not in unique:
            unique.append(text)

    return "\n".join(unique).strip()


def extract_response_from_sse(response_text):
    if not response_text:
        return ""

    final_text = []

    for line in response_text.splitlines():
        line = line.strip()

        if not line.startswith("data:"):
            continue

        json_part = line.replace("data:", "", 1).strip()

        if not json_part or json_part == "[DONE]":
            continue

        try:
            event_data = json.loads(json_part)
        except:
            continue

        if event_data.get("type") == "content_block_delta":
            delta = event_data.get("delta", {})
            if delta.get("type") == "text_delta":
                final_text.append(delta.get("text", ""))

        if "completion" in event_data and isinstance(event_data["completion"], str):
            final_text.append(event_data["completion"])

        if "text" in event_data and isinstance(event_data["text"], str):
            final_text.append(event_data["text"])

    return "".join(final_text).strip()


def request(flow: http.HTTPFlow):
    global pending_attachments

    if not is_claude(flow):
        return

    request_text = safe_get_request_text(flow)

    if flow.request.method == "POST":
        print("CLAUDE POST:", flow.request.pretty_url)

    if is_upload_or_file_request(flow):
        saved_path = save_binary_if_file(flow, "upload_request_binary")

        try:
            data = json.loads(request_text)
            extract_files_from_json(data, "upload_request_json")
        except:
            extract_files_from_text(request_text, "upload_request_text")

        if pending_attachments:
            print("\n========== CLAUDE FILE DETECTED ==========")
            print(json.dumps(pending_attachments, indent=2, ensure_ascii=False))
            if saved_path:
                print("Saved file:", saved_path)
            print("=========================================\n")

    if is_completion(flow):
        try:
            data = json.loads(request_text)
            extract_files_from_json(data, "completion_request_json")
        except:
            extract_files_from_text(request_text, "completion_request_text")

        user_prompt = extract_prompt_from_request(request_text)

        flow.metadata["user_prompt"] = user_prompt
        flow.metadata["request_text"] = request_text
        flow.metadata["attachments"] = list(pending_attachments)


def response(flow: http.HTTPFlow):
    global pending_attachments

    if not is_claude(flow):
        return

    response_text = safe_get_response_text(flow)

    if is_upload_or_file_request(flow):
        try:
            data = json.loads(response_text)
            extract_files_from_json(data, "upload_response_json")
        except:
            extract_files_from_text(response_text, "upload_response_text")

        if pending_attachments:
            print("\n========== CLAUDE FILE RESPONSE DETECTED ==========")
            print(json.dumps(pending_attachments, indent=2, ensure_ascii=False))
            print("==================================================\n")

        return

    if not is_completion(flow):
        return

    url = flow.request.pretty_url

    user_prompt = flow.metadata.get("user_prompt", "")
    request_text = flow.metadata.get("request_text", "")
    attachments = merge_files(flow.metadata.get("attachments", []))
    assistant_response = extract_response_from_sse(response_text)

    if not user_prompt and not assistant_response and not attachments:
        return

    clean_entry = {
        "platform": "Claude Website",
        "capture_time": datetime.now().isoformat(),
        "conversation_id": extract_conversation_id(url),
        "method": flow.request.method,
        "request_url": url,
        "user_prompt": user_prompt,
        "assistant_response": assistant_response,
        "attachments": attachments,
        "status": "captured"
    }

    raw_entry = {
        "capture_time": datetime.now().isoformat(),
        "platform": "Claude Website",
        "conversation_id": extract_conversation_id(url),
        "request_url": url,
        "request_raw": request_text,
        "response_raw": response_text,
        "attachments": attachments
    }

    clean_logs = load_json_file(CLEAN_FILE)
    clean_logs.append(clean_entry)
    save_json_file(CLEAN_FILE, clean_logs)

    raw_logs = load_json_file(RAW_FILE)
    raw_logs.append(raw_entry)
    save_json_file(RAW_FILE, raw_logs)

    print("\n========== CLAUDE WEBSITE CAPTURED ==========")
    print("Prompt:", user_prompt)
    print("Response:", assistant_response[:500])

    if attachments:
        print("Attachments:", json.dumps(attachments, indent=2, ensure_ascii=False))

    print("============================================\n")

    pending_attachments = []