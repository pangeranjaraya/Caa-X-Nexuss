from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import requests
from PIL import Image
import uuid
import yt_dlp # Import library yt-dlp

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- KONFIGURASI API ---
# Masukkan API Key Pexels kamu di sini
PEXELS_API_KEY = 'x1tjBD9smQLMmeBvnEGMZjzJTH3iFwS9IU7iNdCy2jbAn5Mdrdoi4Uvm' 

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/video')
def video_page():
    return render_template('video_editor.html')

@app.route('/photo')
def photo_page():
    return render_template('photo_booth.html')

@app.route('/history')
def history_page():
    return render_template('history.html')

@app.route('/info')
def info_page():
    return render_template('info.html')

# --- API SEARCH VIDEO (PEXELS) ---
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

# --- API SEARCH AUDIO (YOUTUBE via yt-dlp) ---
@app.route('/api/search_audio')
def search_audio():
    query = request.args.get('q', 'lofi hip hop')
    
    # Opsi yt-dlp untuk mencari video (kita ambil judul dan ID saja)
    ydl_opts = {
        'extract_flat': True, # Hanya ambil metadata, jangan download dulu
        'default_search': 'ytsearch5', # Cari 5 hasil teratas
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            results = []
            if 'entries' in info:
                for entry in info['entries']:
                    results.append({
                        'title': entry['title'],
                        'id': entry['id'],
                        'url': f"https://www.youtube.com/watch?v={entry['id']}"
                    })
            return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- API DOWNLOAD AUDIO ---
@app.route('/api/download_audio', methods=['POST'])
def download_audio():
    video_url = request.json.get('url')
    if not video_url:
        return jsonify({'error': 'No URL provided'}), 400

    filename = f"{uuid.uuid4()}.mp3"
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': output_path.replace('.mp3', ''), # yt-dlp akan tambahin .mp3 sendiri
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        return jsonify({'status': 'success', 'filename': filename})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- API PROCESS PHOTO BOOTH ---
@app.route('/api/process_photo', methods=['POST'])
def process_photo():
    if 'photos' not in request.files:
        return jsonify({'error': 'No files'}), 400
    
    files = request.files.getlist('photos')
    images = [Image.open(f).convert('RGB').resize((300, 300)) for f in files]
    
    total_height = sum(img.height for img in images) + (10 * len(images))
    result = Image.new('RGB', (300, total_height), (20, 20, 20))
    
    y_offset = 0
    for img in images:
        result.paste(img, (0, y_offset))
        y_offset += img.height + 10
        
    filename = f"{uuid.uuid4()}.jpg"
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    result.save(path)
    
    return jsonify({'url': f'/static/uploads/{filename}'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
