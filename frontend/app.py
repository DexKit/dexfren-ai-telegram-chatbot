from flask import Flask, render_template, jsonify, request
from werkzeug.utils import secure_filename
import os
import sys
import json
from threading import Thread
import signal
from datetime import datetime

# Add root directory to path to import bot modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge.data_ingestion import DexKitKnowledgeBase
from build_knowledge_base import clean_previous_training, main as rebuild_kb

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '../docs'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Global variable to control bot status
bot_status = {
    "is_running": True,
    "training": False
}

@app.route('/')
def dashboard():
    stats = {
        'total_docs': 0,
        'total_videos': 0,
        'categories': set(),
        'last_training': None
    }
    
    docs = get_training_documents()
    for doc in docs:
        if doc['type'] == 'pdf':
            stats['total_docs'] += 1
        elif doc['type'] == 'youtube':
            stats['total_videos'] += 1
            stats['categories'].add(doc.get('category', 'sin categoría'))
    
    # Try to get last training date
    kb_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'knowledge_base')
    if os.path.exists(kb_path):
        stats['last_training'] = datetime.fromtimestamp(os.path.getmtime(kb_path)).strftime('%Y-%m-%d %H:%M:%S')
    
    return render_template('dashboard.html', stats=stats, bot_status=bot_status)

@app.route('/documents')
def documents():
    # Get list of documents and URLs
    docs = get_training_documents()
    return render_template('documents.html', documents=docs)

@app.route('/training')
def training():
    return render_template('training.html')

@app.route('/api/bot/toggle', methods=['POST'])
def toggle_bot():
    bot_status['is_running'] = not bot_status['is_running']
    return jsonify({'status': 'success', 'is_running': bot_status['is_running']})

@app.route('/api/documents/upload', methods=['POST'])
def upload_document():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return jsonify({'success': True, 'filename': filename})
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/api/urls/add', methods=['POST'])
def add_url():
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
        
    # Add URL to configuration file
    add_url_to_config(url)
    return jsonify({'success': True})

@app.route('/api/training/start', methods=['POST'])
def start_training():
    if bot_status['training']:
        return jsonify({'error': 'Training already in progress'}), 400
        
    bot_status['training'] = True
    Thread(target=train_bot).start()
    return jsonify({'success': True})

def train_bot():
    try:
        rebuild_kb()
    finally:
        bot_status['training'] = False

def get_training_documents():
    docs = []
    try:
        # Get PDF documents
        docs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs')
        if os.path.exists(docs_path):
            for file in os.listdir(docs_path):
                if file.endswith('.pdf'):
                    docs.append({
                        'type': 'pdf',
                        'name': file,
                        'path': os.path.join(docs_path, file)
                    })
    
        # Get URLs from configuration
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'youtube_videos.json')
        if not os.path.exists(config_path):
            print(f"File not found: {config_path}")
            return docs
            
        # Read file with explicit encoding and BOM handling
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            # Debug: print first characters
            print(f"First 10 characters of file: {repr(content[:10])}")
            
            try:
                data = json.loads(content)
                # Get videos from hierarchical structure
                for category, content in data.get('tutorials', {}).items():
                    if isinstance(content, list):
                        for video in content:
                            docs.append({
                                'type': 'youtube',
                                'name': video.get('title', 'Sin título'),
                                'url': video.get('url', ''),
                                'category': video.get('category', ''),
                                'priority': video.get('priority', 0)
                            })
                    else:
                        for subcategory, videos in content.items():
                            for video in videos:
                                docs.append({
                                    'type': 'youtube',
                                    'name': video.get('title', 'Sin título'),
                                    'url': video.get('url', ''),
                                    'category': video.get('category', ''),
                                    'priority': video.get('priority', 0)
                                })
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {str(e)}")
                print(f"File content: {repr(content)}")
                
    except Exception as e:
        print(f"Error in get_training_documents: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return docs

def allowed_file(filename):
    return filename.endswith('.pdf')

def add_url_to_config(url):
    config_file = '../config/youtube_videos.json'
    with open(config_file, 'r+') as f:
        data = json.load(f)
        if url not in data['video_list']:
            data['video_list'].append(url)
        f.seek(0)
        json.dump(data, f, indent=2)
        f.truncate()

def shutdown():
    """Function to close frontend gracefully"""
    print("Frontend stopped correctly")

if __name__ == '__main__':
    try:
        # Register signal handler
        signal.signal(signal.SIGTERM, lambda signum, frame: shutdown())
        signal.signal(signal.SIGINT, lambda signum, frame: shutdown())
        
        # Start frontend
        app.run(debug=True, port=5001)
    except KeyboardInterrupt:
        shutdown()
