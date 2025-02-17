from flask import Flask, render_template, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename
import os
import sys
import json
from threading import Thread
from datetime import datetime

# Add root directory to path to import bot modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
  
from build_knowledge_base import main as rebuild_kb

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

# Ensure the docs directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Global variable for logs
training_logs = []

def count_videos_recursive(data):
    """
    Count videos and extract categories recursively from the video JSON,
    ignoring the flat video_list
    """
    total = 0
    categories = set()
    
    def process_item(item, parent_key=None):
        nonlocal total
        # Ignore the flat video_list
        if parent_key == 'video_list':
            return
            
        if isinstance(item, list):
            # It's a list of videos
            total += len(item)
            for video in item:
                if isinstance(video, dict):
                    if 'category' in video:
                        categories.add(video['category'])
        elif isinstance(item, dict):
            # It's a dictionary of categories or subcategories
            for key, value in item.items():
                if key != 'video_list':  # Ignore the flat video_list
                    categories.add(key)
                    process_item(value, key)
    
    # Process only the tutorials section
    if 'tutorials' in data:
        process_item(data['tutorials'])
    
    return total, categories

def get_last_training_time():
    kb_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'knowledge_base')
    if os.path.exists(kb_path):
        try:
            files = [f for f in os.listdir(kb_path) if os.path.isfile(os.path.join(kb_path, f))]
            if files:
                return datetime.fromtimestamp(max(
                    os.path.getmtime(os.path.join(kb_path, f)) for f in files
                ))
        except Exception as e:
            print(f"Error getting last training time: {e}")
    return None

def check_new_content(last_training_time):
    if not last_training_time:
        return True
    
    has_new_content = False
    
    # Check for new PDFs
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs')
    if os.path.exists(docs_dir):
        for file in os.listdir(docs_dir):
            if file.endswith('.pdf'):
                file_path = os.path.join(docs_dir, file)
                if datetime.fromtimestamp(os.path.getmtime(file_path)) > last_training_time:
                    has_new_content = True
                    break
    
    # Check for new videos
    videos_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'youtube_videos.json')
    if os.path.exists(videos_file) and datetime.fromtimestamp(os.path.getmtime(videos_file)) > last_training_time:
        has_new_content = True
    
    return has_new_content

@app.route('/')
def dashboard():
    stats = {
        'total_docs': 0,
        'total_videos': 0,
        'categories': set(),
        'last_training': None,
        'needs_training': False
    }
    
    # Get PDF documents
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs')
    if os.path.exists(docs_dir):
        pdfs = [f for f in os.listdir(docs_dir) if f.endswith('.pdf')]
        stats['total_docs'] = len(pdfs)
        if pdfs:
            stats['categories'].add('documentation')

    # Get YouTube videos and their categories
    videos_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'youtube_videos.json')
    if os.path.exists(videos_file):
        try:
            with open(videos_file, 'r', encoding='utf-8-sig') as f:
                videos_data = json.load(f)
                total_videos, video_categories = count_videos_recursive(videos_data)
                stats['total_videos'] = total_videos
                stats['categories'].update(video_categories)
                
                print(f"Videos encontrados: {total_videos}")
                print(f"Categorías encontradas: {video_categories}")
        except Exception as e:
            print(f"Error loading videos: {e}")
            import traceback
            print(traceback.format_exc())
    
    # Get last training date
    kb_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'knowledge_base')
    if os.path.exists(kb_path):
        try:
            files = [f for f in os.listdir(kb_path) if os.path.isfile(os.path.join(kb_path, f))]
            if files:
                latest_file = max(
                    [os.path.join(kb_path, f) for f in files],
                    key=os.path.getmtime
                )
                stats['last_training'] = datetime.fromtimestamp(os.path.getmtime(latest_file)).strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print(f"Error getting last training date: {e}")
            stats['last_training'] = None

    # Check if there's new content since the last training
    last_training_time = get_last_training_time()
    stats['needs_training'] = check_new_content(last_training_time)
    
    print("Stats finales:", stats)  # Debug print

    return render_template('dashboard.html', 
                         stats=stats, 
                         initial_logs=[
                             f"System initialized successfully",
                             f"Knowledge base loaded: {stats['total_docs'] + stats['total_videos']} documents",
                             f"Categories found: {', '.join(sorted(stats['categories']))}",
                             f"Last training: {stats['last_training'] if stats['last_training'] else 'Never'}"
                         ],
                         has_documents=(stats['total_docs'] + stats['total_videos']) > 0)

@app.route('/api/training/start', methods=['POST'])
def start_training():
    try:
        global training_logs
        training_logs = []
        
        def training_callback(message):
            global training_logs
            training_logs.append(message)

        thread = Thread(target=rebuild_kb, args=(training_callback,))
        thread.start()
        
        return jsonify({'success': True, 'message': 'Training started'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/training/status')
def get_training_status():
    global training_logs
    return jsonify({
        'success': True,
        'logs': training_logs,
        'is_training': len(training_logs) > 0 and not any('completed' in log.lower() for log in training_logs)
    })

@app.route('/docs')
def documents():
    docs = []
    # Get PDF documents
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs')
    if os.path.exists(docs_dir):
        for file in os.listdir(docs_dir):
            if file.endswith('.pdf'):
                docs.append({
                    'name': file,
                    'type': 'pdf'
                })
    
    # Get YouTube videos
    videos_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'youtube_videos.json')
    if os.path.exists(videos_file):
        try:
            with open(videos_file, 'r', encoding='utf-8-sig') as f:
                videos_data = json.load(f)
                
                def process_videos(data, parent_category=None):
                    if isinstance(data, dict):
                        for category, content in data.items():
                            if isinstance(content, list):
                                # It's a list of videos
                                for video in content:
                                    if isinstance(video, dict) and 'url' in video:
                                        docs.append({
                                            'name': video.get('title', video['url']),
                                            'type': 'youtube',
                                            'url': video['url'],
                                            'category': parent_category or category
                                        })
                            elif isinstance(content, dict):
                                # It's a category with subcategories
                                process_videos(content, category)
                
                # Process the tutorials section
                if 'tutorials' in videos_data:
                    process_videos(videos_data['tutorials'])
                
        except Exception as e:
            print(f"Error loading videos: {e}")
            import traceback
            print(traceback.format_exc())

    # Sort documents: first PDFs, then videos, sorted alphabetically by name
    docs.sort(key=lambda x: (x['type'] != 'pdf', x['name'].lower()))
    
    return render_template('documents.html', documents=docs)

@app.route('/training')
def training():
    # Check if there are documents
    has_documents = False
    docs_count = 0
    videos_count = 0
    
    # Count PDFs
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs')
    if os.path.exists(docs_dir):
        docs_count = len([f for f in os.listdir(docs_dir) if f.endswith('.pdf')])
    
    # Count videos
    videos_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'youtube_videos.json')
    if os.path.exists(videos_file):
        try:
            with open(videos_file, 'r', encoding='utf-8-sig') as f:
                videos_data = json.load(f)
                total_videos, _ = count_videos_recursive(videos_data)
                videos_count = total_videos
        except Exception as e:
            print(f"Error loading videos: {e}")
    
    has_documents = (docs_count + videos_count) > 0
    
    # Check if there's new content since the last training
    last_training_time = get_last_training_time()
    needs_training = check_new_content(last_training_time)
    
    # Get training history
    history = []
    if last_training_time:
        history.append({
            'date': last_training_time.strftime('%Y-%m-%d %H:%M:%S'),
            'model': 'gpt-3.5-turbo',
            'docs': f'{docs_count} PDFs, {videos_count} Videos',
            'status': 'success'
        })
    
    return render_template('training.html', 
                         has_documents=has_documents,
                         needs_training=needs_training,
                         docs_count=docs_count,
                         videos_count=videos_count,
                         last_training=last_training_time,
                         history=history)

@app.route('/api/documents/upload', methods=['POST'])
def upload_document():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file part'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No selected file'}), 400
        
        if file and file.filename.endswith('.pdf'):
            filename = secure_filename(file.filename)
            # Ensure the docs directory exists
            docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs')
            os.makedirs(docs_dir, exist_ok=True)
            
            # Save the file
            file_path = os.path.join(docs_dir, filename)
            file.save(file_path)
            
            print(f"File saved successfully at: {file_path}")
            
            return jsonify({
                'success': True,
                'message': 'File uploaded successfully',
                'filename': filename
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid file type. Only PDF files are allowed.'
            }), 400
            
    except Exception as e:
        print(f"Error uploading file: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/documents/delete/<filename>', methods=['DELETE'])
def delete_document(filename):
    try:
        docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs')
        file_path = os.path.join(docs_dir, secure_filename(filename))
        
        if os.path.exists(file_path):
            os.remove(file_path)
            return jsonify({
                'success': True,
                'message': 'File deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'File not found'
            }), 404
            
    except Exception as e:
        print(f"Error deleting file: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
