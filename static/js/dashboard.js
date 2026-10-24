const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const ws = new WebSocket(wsProtocol + "//" + window.location.host + "/ws/dashboard");

// Elements
const homeView = document.getElementById("home-view");
const patientView = document.getElementById("patient-view");
const patientGrid = document.getElementById("patient-grid");
const backBtn = document.getElementById("back-btn");
const riskBadge = document.getElementById("risk-badge");
const currentPatientName = document.getElementById("current-patient-name");
const initiateCallBtn = document.getElementById("initiate-call-btn");

let currentPatientId = null;
let currentChart = null;

// Initialize
async function loadPatients() {
    try {
        const response = await fetch('/api/patients');
        const patients = await response.json();
        
        patientGrid.innerHTML = "";
        patients.forEach(patient => {
            const card = document.createElement("div");
            card.className = "patient-card";
            const conds = (patient.conditions && patient.conditions.length > 0) ? patient.conditions.join(', ') : 'Unknown';
            card.innerHTML = `
                <h3>${patient.name}</h3>
                <p style="font-size: 0.85em; color: var(--text-secondary); margin-bottom: 0.5rem;">Conditions: ${conds}</p>
                <p style="font-size: 0.9em; opacity: 0.8;">${patient.details.substring(0, 80)}...</p>
            `;
            card.onclick = () => openPatientView(patient);
            patientGrid.appendChild(card);
        });
    } catch (e) {
        console.error("Failed to load patients", e);
    }
}

function openPatientView(patient) {
    currentPatientId = patient.id;
    homeView.style.display = "none";
    patientView.style.display = "block";
    backBtn.style.display = "inline-flex";
    riskBadge.style.display = "inline-flex";
    
    currentPatientName.innerText = patient.name;
    const conds = (patient.conditions && patient.conditions.length > 0) ? patient.conditions.join(', ') : 'Unknown';
    document.getElementById("current-patient-illness").innerText = `Conditions: ${conds}`;
    document.getElementById("transcript-box").innerHTML = `<div class="empty-state"><i class="ph-bold ph-microphone"></i><span>Awaiting audio stream...</span></div>`;
    riskBadge.className = "badge large green";
    riskBadge.innerHTML = `<i class="ph-fill ph-circle"></i><span>Risk: Green</span>`;
    document.getElementById("action-taken").innerText = "None";
    document.getElementById("case-status").innerText = "Unknown";
    document.getElementById("symptoms-list").innerHTML = "<li>None</li>";
    
    initChart();
}

function initChart() {
    const ctx = document.getElementById('medical-chart').getContext('2d');
    if (currentChart) {
        currentChart.destroy();
    }
    
    // Mock 7 days data
    const labels = [];
    const dataPoints = [];
    for (let i = 6; i >= 0; i--) {
        const d = new Date();
        d.setDate(d.getDate() - i);
        labels.push(`${d.getMonth() + 1}/${d.getDate()}`);
        // Random glucose between 80 and 140
        dataPoints.push(Math.floor(Math.random() * (140 - 80 + 1)) + 80);
    }

    currentChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Blood Glucose (mg/dL)',
                data: dataPoints,
                borderColor: '#111',
                backgroundColor: 'rgba(17,17,17,0.1)',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { min: 60, max: 200 }
            }
        }
    });
}

function closePatientView() {
    currentPatientId = null;
    patientView.style.display = "none";
    backBtn.style.display = "none";
    riskBadge.style.display = "none";
    homeView.style.display = "block";
}

backBtn.addEventListener("click", closePatientView);

initiateCallBtn.addEventListener("click", async () => {
    if (!currentPatientId) return;
    try {
        await fetch(`/api/call/ring?patient_id=${currentPatientId}`, { method: "POST" });
        initiateCallBtn.innerHTML = `<i class="ph-fill ph-phone-ring"></i><span>Ringing...</span>`;
        setTimeout(() => {
            initiateCallBtn.innerHTML = `<i class="ph-fill ph-phone"></i><span>Initiate Call</span>`;
        }, 3000);
    } catch (e) {
        console.error("Failed to ring patient", e);
    }
});

// WebSocket for live updates
ws.onopen = () => console.log("Connected to dashboard WebSocket");

ws.onmessage = (event) => {
    try {
        const data = JSON.parse(event.data);
        
        // Update Transcript
        const transcriptBox = document.getElementById("transcript-box");
        
        if (data.type === "patient_transcript" || data.type === "ai_transcript") {
            if (transcriptBox.querySelector('.empty-state')) {
                transcriptBox.innerHTML = "";
            }
            const msgDiv = document.createElement("div");
            msgDiv.className = `message ${data.type === "ai_transcript" ? "ai" : "patient"}`;
            msgDiv.innerText = `${data.type === "ai_transcript" ? "AI: " : "Patient: "} ${data.text}`;
            transcriptBox.appendChild(msgDiv);
            transcriptBox.scrollTop = transcriptBox.scrollHeight;
        }

        // Update Clinical Data
        if (data.risk_status) {
            let rs = data.risk_status.toUpperCase();
            let icon = rs === 'RED' ? 'ph-warning-circle' : 'ph-circle';
            riskBadge.innerHTML = `<i class="ph-fill ${icon}"></i><span>Risk: ${rs}</span>`;
            riskBadge.className = "badge large " + rs.toLowerCase();

            document.getElementById("action-taken").innerText = data.action_taken || "None";
            document.getElementById("case-status").innerText = data.case_status || "Unknown";

            const list = document.getElementById("symptoms-list");
            list.innerHTML = "";
            if (data.symptoms && data.symptoms.length > 0) {
                data.symptoms.forEach(symp => {
                    const li = document.createElement("li");
                    if (typeof symp === 'object' && symp.name) {
                        const date = new Date(symp.timestamp);
                        const timeString = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                        li.innerText = `${symp.name} (${date.getMonth() + 1}/${date.getDate()} ${timeString})`;
                    } else {
                        li.innerText = symp;
                    }
                    list.appendChild(li);
                });
            } else {
                list.innerHTML = "<li>None</li>";
            }

            if (data.blood_glucose !== undefined && data.blood_glucose !== null && currentChart) {
                const labels = currentChart.data.labels;
                const dataPoints = currentChart.data.datasets[0].data;
                const d = new Date();
                const todayLabel = `${d.getMonth() + 1}/${d.getDate()}`;
                
                if (labels[labels.length - 1] === todayLabel) {
                    dataPoints[dataPoints.length - 1] = data.blood_glucose;
                } else {
                    labels.push(todayLabel);
                    dataPoints.push(data.blood_glucose);
                }
                currentChart.update();
            }
        }
    } catch (e) {
        console.error("Error parsing message", e);
    }
};

loadPatients();

const modelSelect = document.getElementById("model-select");
if (modelSelect) {
    modelSelect.addEventListener("change", async (e) => {
        const modelName = e.target.value;
        try {
            await fetch('/api/settings/model', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_name: modelName })
            });
            console.log("Model updated to " + modelName);
        } catch (err) {
            console.error("Failed to update model", err);
        }
    });
}
