from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import requests
from PIL import Image
import uuid
import yt_dlp
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip
import tempfile

# --- KONFIGURASI APLIKASI ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # Max 100MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- MASUKKAN API KEY PEXELS KAMU DI SINI ---
PEXELS_API_KEY = 'x1tjBD9smQLMmeBvnEGMZjzJTH3iFwS9IU7iNdCy2jbAn5Mdrdoi4Uvm' 

# --- ROUTING HALAMAN ---
@app.route('/')
def home(): return render_template('index.html')

@app.route('/video')
def video_page(): return render_template('video_editor.html')

@app.route('/photo')
def photo_page(): return render_template('photo_booth.html')

@app.route('/history')
def history_page(): return render_template('history.html')

@app.route('/info')
def info_page(): return render_template('info.html')

# --- API 1: SEARCH VIDEO (PEXELS) ---
@app.route('/api/search_video')
def search_video():
    query = request.args.get('q', 'aesthetic')
    headers = {'Authorization': PEXELS_API_KEY}
    url = f'https://api.pexels.com/videos/search?query={query}&per_page=12&orientation=portrait'
    try:
        response = requests.get(url, headers=headers)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- API 2: SEARCH AUDIO (YOUTUBE) ---
@app.route('/api/search_audio')
def search_audio():
    query = request.args.get('q', 'lofi')
    ydl_opts = {'extract_flat': True, 'default_search': 'ytsearch5', 'quiet': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            results = [{'title': e['title'], 'id': e['id'], 'url': f"https://www.youtube.com/watch?v={e['id']}"} for e in info.get('entries', [])]
            return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- API 3: DOWNLOAD AUDIO ---
@app.route('/api/download_audio', methods=['POST'])
def download_audio():
    video_url = request.json.get('url')
    if not video_url: return jsonify({'error': 'No URL'}), 400

    filename = f"{uuid.uuid4()}.mp3"
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'outtmpl': output_path.replace('.mp3', ''),
        'quiet': True
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        return jsonify({'status': 'success', 'filename': filename})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- API 4: RENDER VIDEO FINAL (MOVIEPY) ---
@app.route('/api/render_video', methods=['POST'])
def render_video():
    data = request.json
    video_url = data.get('video_url')
    audio_filename = data.get('audio_filename')
    text_overlay = data.get('text', '')

    if not video_url: return jsonify({'error': 'No video'}), 400

    try:
        # 1. Download Video Mentahan Sementara
        temp_video_name = f"temp_{uuid.uuid4()}.mp4"
        temp_video_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_video_name)
        
        with open(temp_video_path, 'wb') as f:
            f.write(requests.get(video_url).content)

        # 2. Load Clips
        video_clip = VideoFileClip(temp_video_path)
        
        # Potong durasi video jadi 15 detik biar ringan (opsional)
        if video_clip.duration > 15:
            video_clip = video_clip.subclip(0, 15)

        final_clips = [video_clip]

        # 3. Tambahkan Audio jika ada
        if audio_filename:
            audio_path = os.path.join(app.config['UPLOAD_FOLDER'], audio_filename)
            if os.path.exists(audio_path):
                audio_clip = AudioFileClip(audio_path)
                # Sesuaikan durasi audio dengan video
                if audio_clip.duration > video_clip.duration:
                    audio_clip = audio_clip.subclip(0, video_clip.duration)
                video_clip = video_clip.set_audio(audio_clip)

        # 4. Tambahkan Teks Overlay
        if text_overlay:
            txt_clip = TextClip(text_overlay, fontsize=40, color='white', font='Arial-Bold')
            txt_clip = txt_clip.set_pos('center').set_duration(video_clip.duration)
            final_clips = CompositeVideoClip([video_clip, txt_clip])
        else:
            final_clips = video_clip

        # 5. Export File Akhir
        final_filename = f"final_{uuid.uuid4()}.mp4"
        final_path = os.path.join(app.config['UPLOAD_FOLDER'], final_filename)
        
        final_clips.write_videofile(final_path, codec="libx264", audio_codec="aac", temp_audiofile='temp-audio.m4a', remove_temp=True)

        # Bersihkan file sementara
        if os.path.exists(temp_video_path): os.remove(temp_video_path)
        video_clip.close()

        return jsonify({'status': 'success', 'download_url': f'/static/uploads/{final_filename}'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- API 5: PROCESS PHOTO BOOTH ---
@app.route('/api/process_photo', methods=['POST'])
def process_photo():
    if 'photos' not in request.files: return jsonify({'error': 'No files'}), 400
    files = request.files.getlist('photos')
    try:
        images = [Image.open(f).convert('RGB').resize((300, 300)) for f in files]
        total_height = sum(img.height for img in images) + (10 * len(images))
        result = Image.new('RGB', (300, total_height), (20, 20, 20))
        y_offset = 0
        for img in images:
            result.paste(img, (0, y_offset)); y_offset += img.height + 10
        filename = f"booth_{uuid.uuid4()}.jpg"
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        result.save(path)
        return jsonify({'url': f'/static/uploads/{filename}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
