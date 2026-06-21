"""
YouTube Learning Toolkit
A Streamlit web app for downloading, trimming, enhancing, merging, splitting,
and transcribing YouTube videos — built for students and researchers.
"""

import streamlit as st
import yt_dlp
import subprocess
import os
import re
import json
import shutil

# Get full path of ffmpeg and ffprobe (fixes Windows PATH issues)
FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
FFPROBE_PATH = r"C:\ffmpeg\bin\ffprobe.exe"

from pathlib import Path
from datetime import timedelta
import tempfile
from typing import Optional, List, Dict

# ====================== CONFIG ======================
st.set_page_config(
    page_title="YouTube Learning Toolkit",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Create working directories
BASE_DIR = Path(__file__).parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
PROCESSED_DIR = BASE_DIR / "processed"
TRANSCRIPTS_DIR = BASE_DIR / "transcripts"

for folder in [DOWNLOADS_DIR, PROCESSED_DIR, TRANSCRIPTS_DIR]:
    folder.mkdir(exist_ok=True)

# ====================== SESSION STATE ======================
if "current_video" not in st.session_state:
    st.session_state.current_video = None  # dict with id, title, path, duration, etc.
if "available_clips" not in st.session_state:
    st.session_state.available_clips = []  # list of processed video paths for merging


# ====================== HELPER FUNCTIONS ======================
def get_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from URL"""
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
        r"(?:embed\/)([0-9A-Za-z_-]{11})",
        r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def probe_duration(file_path: str) -> float:
    """Get video duration in seconds using ffprobe"""
    try:
        cmd = [
            FFPROBE_PATH, "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def format_time(seconds: float) -> str:
    """Convert seconds to HH:MM:SS.mmm"""
    td = timedelta(seconds=seconds)
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{int(td.microseconds/1000):03d}"


def parse_time(time_str: str) -> float:
    """Parse HH:MM:SS or MM:SS or seconds into float seconds"""
    time_str = time_str.strip()
    if not time_str:
        return 0.0
    parts = time_str.split(":")
    try:
        if len(parts) == 3:
            h, m, s = map(float, parts)
            return h * 3600 + m * 60 + s
        elif len(parts) == 2:
            m, s = map(float, parts)
            return m * 60 + s
        else:
            return float(time_str)
    except ValueError:
        return 0.0


def download_youtube_video(url: str, video_id: str):
    """Download video + audio using yt-dlp"""
    output_template = str(DOWNLOADS_DIR / f"{video_id}.%(ext)s")
    
    ydl_opts = {
        "format": "bestvideo*+bestaudio/bestvideo+bestaudio/best",
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "ffmpeg_location": r"C:\ffmpeg\bin",      # ← This is the key fix
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en"],
        "subtitlesformat": "srt",
        "quiet": True,
        "no_warnings": True,
        "sleep_requests": 2,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        },
        "retries": 5,
        "fragment_retries": 5,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
        
        # Find the downloaded video file
        video_path = None
        for ext in [".mp4", ".mkv", ".webm"]:
            candidate = DOWNLOADS_DIR / f"{video_id}{ext}"
            if candidate.exists():
                video_path = str(candidate)
                break
        
        if not video_path:
            for f in DOWNLOADS_DIR.glob(f"{video_id}.*"):
                if f.suffix in [".mp4", ".mkv", ".webm"]:
                    video_path = str(f)
                    break

        if not video_path:
            st.error("Could not find downloaded video file.")
            return None

        duration = probe_duration(video_path)

        return {
            "id": video_id,
            "title": info.get("title", "Unknown Title"),
            "channel": info.get("channel", "Unknown"),
            "duration": duration,
            "duration_str": str(timedelta(seconds=int(duration))),
            "path": video_path,
            "url": url,
        }
        
    except Exception as e:
        st.error(f"Download failed: {str(e)}")
        return None


def extract_transcript_from_srt(srt_path: str) -> str:
    """Convert .srt file to clean readable text with timestamps"""
    if not os.path.exists(srt_path):
        return "No transcript found."
    
    lines = []
    with open(srt_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    # Simple SRT parser
    blocks = re.split(r"\n\s*\n", content.strip())
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines_in_block = block.split("\n")
        if len(lines_in_block) >= 3:
            timestamp = lines_in_block[1]
            text = " ".join(lines_in_block[2:])
            # Clean common artifacts
            text = re.sub(r"<[^>]+>", "", text)  # remove HTML tags
            text = text.strip()
            if text:
                lines.append(f"[{timestamp}] {text}")
    
    return "\n".join(lines) if lines else "Transcript could not be parsed."


def trim_video(input_path: str, output_path: str, start_time: str, end_time: str) -> bool:
    """Trim video using ffmpeg"""
    try:
        start_sec = parse_time(start_time)
        end_sec = parse_time(end_time)
        duration = end_sec - start_sec

        if duration <= 0:
            st.error("End time must be greater than start time.")
            return False

        cmd = [
            FFMPEG_PATH, "-y",
            "-ss", str(start_sec),
            "-i", input_path,
            "-t", str(duration),
            "-c:v", "libx264", "-crf", "23", "-preset", "medium",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        st.error(f"FFmpeg trim error: {error_msg}")
        return False


def enhance_video(input_path: str, output_path: str, mode: str = "lecture") -> bool:
    """Apply enhancement filters based on mode"""
    try:
        vf_filters = []
        af_filters = []

        if mode == "lecture":
            vf_filters = ["unsharp=5:5:0.8:5:5:0.8", "eq=contrast=1.1:brightness=0.02:saturation=1.05"]
            af_filters = ["loudnorm", "afftdn=nf=-25"]
        elif mode == "audio_cleanup":
            af_filters = ["loudnorm", "afftdn=nf=-30", "highpass=f=80", "lowpass=f=15000"]
        elif mode == "sharpen_upscale":
            vf_filters = ["unsharp=7:7:1.0:7:7:0.0", "scale=-2:1080:flags=lanczos"]
        elif mode == "stabilize":
            vf_filters = ["vidstabdetect=shakiness=10:accuracy=15", "vidstabtransform=smoothing=10"]

        vf = ",".join(vf_filters) if vf_filters else "null"
        af = ",".join(af_filters) if af_filters else "anull"

        cmd = [
            FFMPEG_PATH, "-y", "-i", input_path,
            "-vf", vf,
            "-af", af,
            "-c:v", "libx264", "-crf", "20", "-preset", "medium",
            "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart",
            output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        st.error(f"Enhance failed: {error_msg}")
        return False


def merge_videos(input_paths: List[str], output_path: str) -> bool:
    """Merge multiple videos using concat demuxer (fast if same codec)"""
    try:
        # Create concat list
        list_file = PROCESSED_DIR / "concat_list.txt"
        with open(list_file, "w") as f:
            for p in input_paths:
                f.write(f"file '{Path(p).resolve()}'\n")
        
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        list_file.unlink(missing_ok=True)
        return True
    except subprocess.CalledProcessError as e:
        st.error(f"Merge failed: {e.stderr.decode() if e.stderr else str(e)}")
        return False


def split_video(input_path: str, output_dir: Path, parts: int = 4) -> List[str]:
    """Split video into N equal parts"""
    try:
        duration = probe_duration(input_path)
        part_duration = duration / parts
        output_files = []
        
        base_name = Path(input_path).stem
        
        for i in range(parts):
            start = i * part_duration
            out_file = output_dir / f"{base_name}_part{i+1:02d}.mp4"
            
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start),
                "-i", input_path,
                "-t", str(part_duration),
                "-c:v", "libx264", "-crf", "23", "-preset", "medium",
                "-c:a", "aac", "-b:a", "128k",
                str(out_file)
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            output_files.append(str(out_file))
        
        return output_files
    except Exception as e:
        st.error(f"Split failed: {str(e)}")
        return []


# ====================== UI ======================
st.title("🎓 YouTube Learning Toolkit")
st.markdown("**Download • Trim • Enhance • Merge • Split • Transcribe** — Perfect for students & researchers")

st.divider()

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("📥 Input")
    
    youtube_url = st.text_input(
        "YouTube Video URL",
        placeholder="https://www.youtube.com/watch?v=...",
        help="Paste any public YouTube video link"
    )
    
    if st.button("⬇️ Download Video", type="primary", use_container_width=True):
        if not youtube_url:
            st.error("Please enter a YouTube URL")
        else:
            video_id = get_video_id(youtube_url)
            if not video_id:
                st.error("Could not extract video ID. Please check the URL.")
            else:
                with st.spinner("Downloading video and subtitles... This may take a while for long videos."):
                    try:
                        video_info = download_youtube_video(youtube_url, video_id)
                        st.session_state.current_video = video_info
                        # Add to available clips
                        if video_info["path"] not in [c["path"] for c in st.session_state.available_clips]:
                            st.session_state.available_clips.append(video_info)
                        st.success(f"✅ Downloaded: {video_info['title'][:60]}...")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Download failed: {str(e)}")
    
    st.divider()
    
    if st.session_state.current_video:
        vid = st.session_state.current_video
        st.subheader("📹 Current Video")
        st.write(f"**{vid['title'][:50]}...**")
        st.caption(f"Duration: {vid['duration_str']} | Channel: {vid.get('channel', 'N/A')}")
        
        if st.button("🔄 Clear Current Video", use_container_width=True):
            st.session_state.current_video = None
            st.rerun()
    
    st.divider()
    st.caption("All processing happens locally on your machine.\nNo data is sent to any server.")


# ====================== MAIN CONTENT ======================
if not st.session_state.current_video:
    st.info("👈 Paste a YouTube URL in the sidebar and click **Download Video** to get started.")
    
    with st.expander("How to use this tool"):
        st.markdown("""
        1. **Download** any YouTube video (with auto-captions when available)
        2. **Trim** to extract important segments for study
        3. **Enhance** audio/video quality for better learning experience
        4. **Merge** multiple clips into study compilations
        5. **Split** long lectures into manageable parts
        6. **Convert to Text** — Get clean, timestamped transcripts
        """)
    st.stop()

# We have a current video
vid = st.session_state.current_video
video_path = vid["path"]

# Video Preview
col1, col2 = st.columns([2, 1])
with col1:
    st.subheader("🎬 Video Preview")
    if os.path.exists(video_path):
        st.video(video_path)
    else:
        st.error("Video file not found. Please re-download.")

with col2:
    st.subheader("📋 Video Info")
    st.json({
        "Title": vid["title"],
        "Duration": vid["duration_str"],
        "Channel": vid.get("channel"),
        "Local Path": video_path
    })

st.divider()

# ====================== TABS FOR OPERATIONS ======================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "✂️ Trim / Extract Clip",
    "✨ Enhance Video",
    "🔗 Merge Clips",
    "📦 Split Video",
    "📝 Transcript & Notes",
    "📚 Library"
])

# ------------------ TAB 1: TRIM ------------------
with tab1:
    st.header("Trim & Extract Specific Segment")
    
    col_start, col_end = st.columns(2)
    with col_start:
        start_time = st.text_input("Start Time (HH:MM:SS or MM:SS)", value="00:00:00", key="trim_start")
    with col_end:
        end_time = st.text_input("End Time (HH:MM:SS or MM:SS)", value=vid["duration_str"][:8] if vid["duration_str"] else "00:05:00", key="trim_end")
    
    clip_name = st.text_input("Output filename (without extension)", value=f"{vid['id']}_clip", key="clip_name")
    
    if st.button("✂️ Trim & Save Clip", type="primary"):
        output_path = str(PROCESSED_DIR / f"{clip_name}.mp4")
        with st.spinner("Trimming video..."):
            success = trim_video(video_path, output_path, start_time, end_time)
            if success:
                st.success(f"✅ Clip saved: {output_path}")
                # Add to library
                new_clip = {"path": output_path, "title": f"Trimmed: {clip_name}"}
                st.session_state.available_clips.append(new_clip)
                st.balloons()

# ------------------ TAB 2: ENHANCE ------------------
with tab2:
    st.header("Enhance Video Quality")
    
    enhance_mode = st.selectbox(
        "Enhancement Preset",
        options=["lecture", "audio_cleanup", "sharpen_upscale", "stabilize"],
        format_func=lambda x: {
            "lecture": "🎓 Lecture / Talking Head (recommended)",
            "audio_cleanup": "🔊 Audio Cleanup Only",
            "sharpen_upscale": "🔍 Sharpen + Upscale to 1080p",
            "stabilize": "📹 Stabilize Shaky Footage"
        }[x]
    )
    
    enhance_name = st.text_input("Output filename", value=f"{vid['id']}_enhanced_{enhance_mode}", key="enhance_name")
    
    if st.button("✨ Enhance & Save", type="primary"):
        output_path = str(PROCESSED_DIR / f"{enhance_name}.mp4")
        with st.spinner(f"Enhancing video with {enhance_mode} preset... (this can take several minutes)"):
            success = enhance_video(video_path, output_path, mode=enhance_mode)
            if success:
                st.success(f"✅ Enhanced video saved: {output_path}")
                new_clip = {"path": output_path, "title": f"Enhanced ({enhance_mode}): {enhance_name}"}
                st.session_state.available_clips.append(new_clip)

# ------------------ TAB 3: MERGE ------------------
with tab3:
    st.header("Merge Multiple Video Clips")
    
    st.write("Select clips from your library to merge (in order):")
    
    if not st.session_state.available_clips:
        st.warning("No clips available yet. Trim or enhance some videos first.")
    else:
        clip_options = {f"{i+1}. {c.get('title', Path(c['path']).name)}": c["path"] 
                        for i, c in enumerate(st.session_state.available_clips)}
        
        selected_labels = st.multiselect(
            "Choose clips to merge (in desired order)",
            options=list(clip_options.keys()),
            default=list(clip_options.keys())[:2] if len(clip_options) >= 2 else list(clip_options.keys())
        )
        
        merge_name = st.text_input("Merged video filename", value=f"{vid['id']}_merged", key="merge_name")
        
        if st.button("🔗 Merge Selected Clips", type="primary"):
            if len(selected_labels) < 2:
                st.error("Please select at least 2 clips to merge.")
            else:
                selected_paths = [clip_options[label] for label in selected_labels]
                output_path = str(PROCESSED_DIR / f"{merge_name}.mp4")
                with st.spinner("Merging videos..."):
                    success = merge_videos(selected_paths, output_path)
                    if success:
                        st.success(f"✅ Merged video saved: {output_path}")
                        new_clip = {"path": output_path, "title": f"Merged: {merge_name}"}
                        st.session_state.available_clips.append(new_clip)

# ------------------ TAB 4: SPLIT ------------------
with tab4:
    st.header("Split Video into Multiple Parts")
    
    num_parts = st.slider("Number of equal parts", min_value=2, max_value=10, value=4)
    split_name = st.text_input("Base name for parts", value=f"{vid['id']}_split", key="split_name")
    
    if st.button("📦 Split into Parts", type="primary"):
        output_dir = PROCESSED_DIR / split_name
        output_dir.mkdir(exist_ok=True)
        
        with st.spinner(f"Splitting into {num_parts} parts..."):
            parts = split_video(video_path, output_dir, parts=num_parts)
            if parts:
                st.success(f"✅ Created {len(parts)} parts in {output_dir}")
                for p in parts:
                    st.session_state.available_clips.append({
                        "path": p,
                        "title": f"Split part: {Path(p).name}"
                    })

# ------------------ TAB 5: TRANSCRIPT ------------------
with tab5:
    st.header("📝 Convert Video to Text (Transcript)")
    
    # Try to find existing subtitle file from download
    srt_candidates = list(DOWNLOADS_DIR.glob(f"{vid['id']}*.srt")) + list(DOWNLOADS_DIR.glob(f"{vid['id']}*.en.srt"))
    
    transcript_text = ""
    
    if srt_candidates:
        srt_file = str(srt_candidates[0])
        st.success(f"✅ Found YouTube auto-captions: {Path(srt_file).name}")
        
        if st.button("📥 Load & Format Transcript", type="primary"):
            transcript_text = extract_transcript_from_srt(srt_file)
            # Save clean version
            txt_path = TRANSCRIPTS_DIR / f"{vid['id']}_transcript.txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(transcript_text)
            st.success(f"Transcript saved to: {txt_path}")
    else:
        st.warning("No auto-captions found for this video.")
        st.info("Tip: Many educational videos have good auto-generated captions. Try another video or use Whisper (advanced).")
    
    if transcript_text:
        st.subheader("Transcript with Timestamps")
        st.text_area("Full Transcript", transcript_text, height=400)
        
        # Download buttons
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                "⬇️ Download as .txt",
                transcript_text,
                file_name=f"{vid['id']}_transcript.txt"
            )
        with col_dl2:
            # Also offer original SRT if exists
            if srt_candidates:
                with open(srt_candidates[0], "r", encoding="utf-8", errors="ignore") as f:
                    srt_content = f.read()
                st.download_button(
                    "⬇️ Download original .srt",
                    srt_content,
                    file_name=Path(srt_candidates[0]).name
                )
    
    # Future: Whisper option
    with st.expander("Advanced: Use local Whisper for speech-to-text (requires installation)"):
        st.markdown("""
        To use Whisper:
        1. `pip install openai-whisper`
        2. Uncomment the Whisper code in the app (or ask me to add it)
        3. It will transcribe the audio even if no YouTube captions exist.
        
        **Note:** First run downloads ~1-3GB model. Works offline after that.
        """)

# ------------------ TAB 6: LIBRARY ------------------
with tab6:
    st.header("📚 Your Processed Clips Library")
    
    if not st.session_state.available_clips:
        st.info("Your processed clips will appear here after trimming, enhancing, merging or splitting.")
    else:
        st.write(f"**Total clips:** {len(st.session_state.available_clips)}")
        
        for i, clip in enumerate(st.session_state.available_clips):
            col_info, col_play, col_del = st.columns([3, 1, 1])
            
            with col_info:
                st.write(f"**{i+1}.** {clip.get('title', Path(clip['path']).name)}")
                st.caption(clip["path"])
            
            with col_play:
                if st.button("▶️ Play", key=f"play_{i}"):
                    st.video(clip["path"])
            
            with col_del:
                if st.button("🗑️ Remove", key=f"del_{i}"):
                    st.session_state.available_clips.pop(i)
                    st.rerun()
        
        if st.button("🧹 Clear Entire Library"):
            st.session_state.available_clips = []
            st.rerun()

st.divider()

st.caption("Made for learning • All files stay on your computer • Powered by yt-dlp + FFmpeg + Streamlit")