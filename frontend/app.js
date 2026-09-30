const chatContainer = document.getElementById('chatContainer');
const textInput = document.getElementById('textInput');
const sendBtn = document.getElementById('sendBtn');
const micBtn = document.getElementById('micBtn');
const recordingIndicator = document.getElementById('recordingIndicator');
const chunkInspector = document.getElementById('chunkInspector');
const inspectorContent = document.getElementById('inspectorContent');

const BACKEND_URL = 'http://127.0.0.1:8000';

// Web Speech API setup
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition;

if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
        micBtn.classList.add('recording');
        recordingIndicator.classList.remove('hidden');
        textInput.placeholder = '';
        textInput.disabled = true;
    };

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        textInput.value = transcript;
        sendMessage();
    };

    recognition.onerror = (event) => {
        console.error('Speech recognition error', event.error);
        stopRecording();
    };

    recognition.onend = () => {
        stopRecording();
    };
} else {
    micBtn.style.display = 'none';
    textInput.placeholder = 'Speech recognition not supported. Type your query...';
}

micBtn.addEventListener('click', () => {
    if (micBtn.classList.contains('recording')) {
        recognition.stop();
    } else {
        textInput.value = '';
        recognition.start();
    }
});

function stopRecording() {
    micBtn.classList.remove('recording');
    recordingIndicator.classList.add('hidden');
    textInput.placeholder = 'Speak or type your query (Fallback)...';
    textInput.disabled = false;
}

sendBtn.addEventListener('click', sendMessage);
textInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

async function sendMessage() {
    const text = textInput.value.trim();
    if (!text) return;

    appendMessage('user', text);
    textInput.value = '';
    
    // Add loading indicator
    const loadingId = appendLoading();
    
    try {
        const response = await fetch(`${BACKEND_URL}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: text })
        });
        
        const data = await response.json();
        
        removeLoading(loadingId);
        
        // Show the chunk inspector
        updateChunkInspector(data);
        
        // Append response
        appendMessage(data.is_refused ? 'error' : 'system', data.answer);
        
    } catch (error) {
        removeLoading(loadingId);
        appendMessage('error', 'Failed to connect to the backend server. Is it running?');
        console.error(error);
    }
}

function appendMessage(role, content) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}-message`;
    
    let icon = role === 'user' ? 'fa-user' : (role === 'error' ? 'fa-triangle-exclamation' : 'fa-robot');
    
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    msgDiv.innerHTML = `
        <div class="avatar"><i class="fa-solid ${icon}"></i></div>
        <div class="content">
            <p>${content}</p>
            <span class="timestamp">${time}</span>
        </div>
    `;
    
    chatContainer.appendChild(msgDiv);
    scrollToBottom();
}

function appendLoading() {
    const id = 'loading-' + Date.now();
    const msgDiv = document.createElement('div');
    msgDiv.className = `message system-message`;
    msgDiv.id = id;
    
    msgDiv.innerHTML = `
        <div class="avatar"><i class="fa-solid fa-robot"></i></div>
        <div class="content">
            <div class="typing-indicator">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;
    
    chatContainer.appendChild(msgDiv);
    scrollToBottom();
    return id;
}

function removeLoading(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function updateChunkInspector(data) {
    if (!data.retrieved_chunks || data.retrieved_chunks.length === 0) {
        chunkInspector.classList.add('hidden');
        return;
    }
    
    chunkInspector.classList.remove('hidden');
    
    let html = `<div style="margin-bottom: 10px; font-size: 0.85rem;">
        <strong>Query Injection Score:</strong> 
        <span class="score-badge ${data.query_injection_score.label === 'SAFE' ? 'safe' : 'unsafe'}">
            ${data.query_injection_score.label} (${(data.query_injection_score.score * 100).toFixed(1)}%)
        </span>
    </div>`;
    
    data.retrieved_chunks.forEach(chunk => {
        const isSafe = chunk.included;
        html += `
            <div class="chunk-card ${isSafe ? 'safe' : 'unsafe'}">
                <div class="chunk-meta">
                    <span>Chunk #${chunk.id + 1} | Length: ${chunk.text.length} chars</span>
                    <span class="score-badge ${isSafe ? 'safe' : 'unsafe'}">
                        ${chunk.injection_score.label} (${(chunk.injection_score.score * 100).toFixed(1)}%)
                    </span>
                </div>
                <div>${chunk.text}</div>
            </div>
        `;
    });
    
    inspectorContent.innerHTML = html;
}
