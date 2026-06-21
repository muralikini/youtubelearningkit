# YouTube Learning Toolkit
## Web Application for Processing YouTube Videos for Learning & Reference

A powerful, local-first Streamlit web app to download, trim, enhance, merge, split, and transcribe YouTube videos — designed specifically for students, researchers, and lifelong learners.

### ✨ Key Features

| Feature | Description |
|---------|-------------|
| **1. Download** | High-quality download using yt-dlp (best video + audio, metadata, thumbnail) |
| **2. Trim / Clip** | Extract precise segments with start & end time inputs |
| **3. Enhance** | Audio normalization, noise reduction, video sharpening, stabilization, contrast boost |
| **4. Merge** | Combine multiple clips into one video |
| **5. Split** | Split long videos into equal parts or custom segments |
| **6. Convert to Text** | Extract transcript (YouTube auto-captions preferred + optional Whisper fallback) with timestamps |

### 🚀 Quick Start (Local Machine)

```bash
# 1. Clone or download this folder

# 2. Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate   # Linux/Mac
# venv\Scripts\activate    # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional but recommended) Install FFmpeg
# Ubuntu/Debian: sudo apt install ffmpeg
# macOS: brew install ffmpeg
# Windows: https://ffmpeg.org/download.html

# 5. Run the app
streamlit run app.py
```

Then open the URL shown in terminal (usually http://localhost:8501)

### 📁 Folder Structure

```
youtube_learning_tool/
├── app.py                 # Main Streamlit application
├── requirements.txt
├── README.md
├── downloads/             # Downloaded original videos (auto-created)
├── processed/             # All trimmed/enhanced/merged/split outputs
└── transcripts/           # .srt and .txt transcripts
```

### 🔧 How to Use

1. Paste any YouTube URL
2. Click **Download Video**
3. Preview the video
4. Use the tabs or sections to:
   - Trim specific parts
   - Enhance quality
   - Merge with other clips
   - Split into smaller parts
   - Generate transcript + notes

All processed files are saved with clear naming and can be re-used in merge/split operations.

### 🛠️ Advanced / Future Ideas (Roadmap)

- AI summary of transcript using local LLM (Ollama / llama.cpp)
- Auto chapter detection
- Generate Anki flashcards from transcript
- Batch process entire playlists
- Export to Notion / Obsidian
- Voice cloning for dubbed versions
- Real-time progress with better UI

### ⚠️ Notes

- This app runs **locally** on your machine. Your videos and transcripts never leave your computer.
- You need a working FFmpeg installation.
- For best transcript quality, many videos have good YouTube auto-captions.
- Large videos will take time and disk space during processing.

---

Built for learning. Made with ❤️ using Streamlit + yt-dlp + FFmpeg.

If you want new features or improvements, just tell me!
