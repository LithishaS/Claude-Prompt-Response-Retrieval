# 🔍 Claude-Prompt-Response-Retrieval

A Python-based MITM Proxy tool for capturing AI interactions from **Claude Website** and **Claude Desktop**. The project intercepts network traffic to retrieve user prompts, assistant responses, conversation metadata, uploaded file information, and downloaded file content for analysis.

---

## 📌 Project Overview

This project was developed to capture and analyze runtime interactions with Claude AI applications.

Using **MITM Proxy**, the application intercepts HTTP traffic between the client and Claude services, extracts prompts and responses, detects uploaded files, downloads supported files, and stores the captured information in structured JSON format.

The project supports both:

- Claude Website
- Claude Desktop

---

## ✨ Features

- Capture user prompts
- Capture assistant responses
- Extract conversation IDs
- Detect uploaded files
- Download uploaded documents and images
- Extract file metadata
- Save structured JSON logs
- Save raw request and response logs
- Capture runtime AI interactions

---

## 🛠 Technologies Used

- Python
- MITM Proxy
- JSON
- HTTP Traffic Analysis
- Regular Expressions
- File Handling

---

# ⚙️ Data Retrieval Workflow

```text
Claude Website / Claude Desktop
                │
                ▼
          MITM Proxy
                │
                ▼
      Intercept HTTP Requests
                │
                ▼
Extract

• User Prompt
• Assistant Response
• Conversation ID
• Uploaded Files
• File Metadata

                │
                ▼
Download Uploaded Files
                │
                ▼
Generate JSON Logs
```

---

## 📂 Project Structure

```text
claude-data-retrieval/

│── claude_web.py
│── claude_desktop.py
│── README.md
```

---

## 🌐 claude_web.py

Captures runtime interactions from the Claude web application.

Features include:

- Prompt retrieval
- Response retrieval
- Conversation ID extraction
- Uploaded file detection
- Automatic file download
- JSON logging
- Raw request and response logging

---

## 💻 claude_desktop.py

Captures runtime interactions from the Claude Desktop application.

Features include:

- Prompt retrieval
- Response retrieval
- Conversation ID extraction
- Uploaded file detection
- Automatic file download
- JSON logging
- Raw request and response logging

---

## 📁 Supported File Types

The project detects and downloads supported files including:

- PDF
- DOC / DOCX
- TXT
- CSV
- XLS / XLSX
- PPT / PPTX
- PNG
- JPG / JPEG
- WEBP
- GIF
- BMP

---

## 📊 Captured Information

The tool extracts:

- User Prompt
- Assistant Response
- Conversation ID
- Request URL
- Timestamp
- Uploaded File Name
- File Type
- File ID
- Saved File Path

---

## 🚀 How It Works

1. Configure MITM Proxy.
2. Route Claude traffic through the proxy.
3. Intercept HTTP requests and responses.
4. Detect AI conversations.
5. Capture prompts and responses.
6. Detect uploaded files.
7. Download supported files.
8. Save structured JSON logs.

---

