async function uploadDocument(file) {
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/documents/upload', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        if (data.success) {
            showNotification('Document uploaded successfully', 'success');
            location.reload();
        } else {
            showNotification('Error uploading document', 'error');
        }
    } catch (error) {
        console.error('Error uploading document:', error);
        showNotification('Error uploading document', 'error');
    }
}

async function addUrl(url, category) {
    try {
        const response = await fetch('/api/urls/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                url,
                category: category || 'uncategorized'
            })
        });
        const data = await response.json();
        if (data.success) {
            showNotification('URL added successfully', 'success');
            location.reload();
        } else {
            showNotification(data.error || 'Error adding URL', 'error');
        }
    } catch (error) {
        console.error('Error adding URL:', error);
        showNotification('Error adding URL', 'error');
    }
}

async function startTraining() {
    try {
        updateConsoleMessage('Starting training process...', 'INFO');
        const response = await fetch('/api/training/start', {
            method: 'POST'
        });
        const data = await response.json();
        
        if (data.success) {
            showNotification('Training started successfully', 'success');
            pollTrainingStatus();
        } else {
            showNotification('Error starting training', 'error');
        }
    } catch (error) {
        console.error('Error starting training:', error);
        showNotification('Error starting training', 'error');
    }
}

async function pollTrainingStatus() {
    const pollInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/training/status');
            const data = await response.json();
            
            if (data.success) {
                if (data.logs && data.logs.length > 0) {
                    data.logs.forEach(log => {
                        updateConsoleMessage(log);
                    });
                }
                
                if (!data.is_training) {
                    clearInterval(pollInterval);
                    showNotification('Training completed', 'success');
                }
            }
        } catch (error) {
            console.error('Error checking training status:', error);
            clearInterval(pollInterval);
        }
    }, 2000);
}

function updateConsoleMessage(message, type = 'INFO') {
    const console = document.getElementById('consoleOutput');
    if (console) {
        const div = document.createElement('div');
        const timestamp = new Date().toLocaleTimeString();
        div.textContent = `[${timestamp}] [${type}] ${message}`;
        div.className = 'text-green-400';
        console.appendChild(div);
        console.scrollTop = console.scrollHeight;
    }
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `fixed bottom-4 right-4 p-4 rounded-lg shadow-lg transform transition-all duration-300 z-50 ${
        type === 'success' ? 'bg-green-500' :
        type === 'error' ? 'bg-red-500' :
        'bg-blue-500'
    } text-white`;
    
    notification.innerHTML = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.add('opacity-0');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

async function checkDocumentStatus() {
    try {
        const response = await fetch('/api/documents/status');
        const data = await response.json();
        
        if (data.success) {
            updateDocumentsList(data.documents);
        }
    } catch (error) {
        console.error('Error checking document status:', error);
    }
}

function updateDocumentsList(documents) {
    const documentsList = document.getElementById('documentsList');
    if (!documentsList) return;

    documentsList.innerHTML = documents.map(doc => `
        <div class="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div class="flex items-center space-x-4">
                <span class="text-sm font-medium">${doc.filename}</span>
                <span class="px-2 py-1 text-xs rounded-full ${
                    doc.processed ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
                }">
                    ${doc.processed ? 'Processed' : 'Pending'}
                </span>
            </div>
            <div class="text-sm text-gray-500">
                Added: ${new Date(doc.added_date).toLocaleString()}
            </div>
        </div>
    `).join('');
}

document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const file = e.target.querySelector('input[type="file"]').files[0];
            if (file) {
                uploadDocument(file);
            }
        });
    }

    const urlForm = document.getElementById('urlForm');
    if (urlForm) {
        urlForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const url = e.target.querySelector('#videoUrl').value;
            const category = e.target.querySelector('#category').value;
            if (url) {
                addUrl(url, category);
            }
        });
    }

    const trainButton = document.getElementById('trainButton');
    if (trainButton) {
        trainButton.addEventListener('click', startTraining);
    }

    updateConsoleMessage('System initialized');
    updateConsoleMessage('Ready to process documents and training requests');
});
