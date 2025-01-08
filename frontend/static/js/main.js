// Global state
let botState = {
    isRunning: true,
    isTraining: false
};

// API functions
async function toggleBot() {
    try {
        const response = await fetch('/api/bot/toggle', {
            method: 'POST'
        });
        const data = await response.json();
        botState.isRunning = data.is_running;
        updateBotStatus();
    } catch (error) {
        console.error('Error toggling bot:', error);
    }
}

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
            location.reload();
        }
    } catch (error) {
        console.error('Error uploading document:', error);
    }
}

async function addUrl(url) {
    try {
        const response = await fetch('/api/urls/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url })
        });
        const data = await response.json();
        if (data.success) {
            location.reload();
        }
    } catch (error) {
        console.error('Error adding URL:', error);
    }
}

async function startTraining() {
    try {
        const response = await fetch('/api/training/start', {
            method: 'POST'
        });
        const data = await response.json();
        if (data.success) {
            botState.isTraining = true;
            updateTrainingStatus();
        }
    } catch (error) {
        console.error('Error starting training:', error);
    }
}

// UI functions
function updateBotStatus() {
    const toggle = document.getElementById('botToggle');
    if (toggle) {
        toggle.textContent = botState.isRunning ? 'Detener Bot' : 'Iniciar Bot';
        toggle.className = `px-4 py-2 rounded-md ${
            botState.isRunning ? 'bg-red-500 hover:bg-red-600' : 'bg-green-500 hover:bg-green-600'
        } text-white`;
    }
}

function updateTrainingStatus() {
    const status = document.getElementById('trainingStatus');
    if (status) {
        status.textContent = botState.isTraining ? 'Training...' : 'Ready to train';
    }
}

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    const botToggle = document.getElementById('botToggle');
    if (botToggle) {
        botToggle.addEventListener('click', toggleBot);
    }

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
            const url = e.target.querySelector('input[type="url"]').value;
            if (url) {
                addUrl(url);
            }
        });
    }
});
