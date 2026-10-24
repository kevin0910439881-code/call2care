const incomingActions = document.getElementById('incoming-actions');
const activeActions = document.getElementById('active-actions');
const recordBtn = document.getElementById('record-btn');
const answerBtn = document.getElementById('answer-btn');
const endBtn = document.getElementById('end-btn');
const statusText = document.getElementById('status-text');
const audioPlayer = document.getElementById('audio-player');

let mediaRecorder;
let audioChunks = [];
let patientId = "patient_001"; // Hardcoded for demo

const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const ws = new WebSocket(wsProtocol + "//" + window.location.host + "/ws/patient");

ws.onmessage = (event) => {
    try {
        const data = JSON.parse(event.data);
        if (data.type === "incoming_call" && data.patient_id === patientId) {
            statusText.innerText = "calling mobile...";
            incomingActions.style.display = 'flex';
            activeActions.style.display = 'none';
        }
    } catch (e) {
        console.error("WS parse error", e);
    }
};

async function setupAudio() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        
        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) audioChunks.push(e.data);
        };

        mediaRecorder.onstop = async () => {
            statusText.innerText = "Processing...";
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            audioChunks = [];
            
            const formData = new FormData();
            formData.append('audio_file', audioBlob, 'recording.wav');

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    body: formData
                });
                
                if (response.ok) {
                    const callEnded = response.headers.get("x-call-ended") === "true";
                    
                    const blob = await response.blob();
                    const audioUrl = URL.createObjectURL(blob);
                    audioPlayer.src = audioUrl;
                    audioPlayer.play();
                    
                    audioPlayer.onended = () => {
                        if (callEnded) {
                            endCallUI();
                        } else {
                            statusText.innerText = "00:00"; // Fake duration or idle text
                        }
                    };
                    statusText.innerText = callEnded ? "Ending Call..." : "Listening...";
                } else {
                    statusText.innerText = "Error, please try again";
                }
            } catch (err) {
                console.error("Upload error", err);
                statusText.innerText = "Network error";
            }
        };
    } catch (err) {
        console.error("Microphone access denied", err);
        statusText.innerText = "Microphone access denied";
    }
}

function endCallUI() {
    statusText.innerText = "Call Ended";
    activeActions.style.display = 'none';
    incomingActions.style.display = 'none';
    
    // Reset back to waiting screen after a few seconds
    setTimeout(() => {
        statusText.innerText = "Waiting for incoming call...";
    }, 3000);
}

const startRecording = (e) => {
    e.preventDefault();
    if (!mediaRecorder) return;
    audioPlayer.pause();
    audioChunks = [];
    mediaRecorder.start();
    recordBtn.classList.add('active');
    recordBtn.classList.add('recording-pulse');
    statusText.innerText = "Recording...";
};

const stopRecording = (e) => {
    e.preventDefault();
    if (!mediaRecorder || mediaRecorder.state === 'inactive') return;
    mediaRecorder.stop();
    recordBtn.classList.remove('active');
    recordBtn.classList.remove('recording-pulse');
};

recordBtn.addEventListener('mousedown', startRecording);
recordBtn.addEventListener('mouseup', stopRecording);
recordBtn.addEventListener('mouseleave', stopRecording);

recordBtn.addEventListener('touchstart', startRecording, {passive: false});
recordBtn.addEventListener('touchend', stopRecording, {passive: false});
recordBtn.addEventListener('touchcancel', stopRecording, {passive: false});

answerBtn.addEventListener('click', async () => {
    statusText.innerText = "Connecting...";
    try {
        const response = await fetch(`/api/call/start?patient_id=${patientId}`, { method: 'POST' });
        if (response.ok) {
            const blob = await response.blob();
            const audioUrl = URL.createObjectURL(blob);
            audioPlayer.src = audioUrl;
            audioPlayer.play();
            
            audioPlayer.onended = () => {
                statusText.innerText = "00:00";
            };
            statusText.innerText = "Listening...";
            
            // Switch UI
            incomingActions.style.display = 'none';
            activeActions.style.display = 'flex';
        } else {
            statusText.innerText = "Error, please try again";
        }
    } catch (err) {
        console.error("Start call error", err);
        statusText.innerText = "Network error";
    }
});

endBtn.addEventListener('click', () => {
    // End the call manually from patient side
    audioPlayer.pause();
    endCallUI();
});

setupAudio();
