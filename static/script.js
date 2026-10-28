// script.js
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const chatBox = document.getElementById('chat-box');

const aboutBtn = document.getElementById('aboutBtn');
const aboutModal = document.getElementById('aboutModal');
const closeModalBtn = document.getElementById('closeModalBtn');

aboutBtn.addEventListener('click', () => {
    aboutModal.style.display = 'flex';
});

closeModalBtn.addEventListener('click', () => {
    aboutModal.style.display = 'none';
});

window.addEventListener('click', (e) => {
    if (e.target === aboutModal) {
        aboutModal.style.display = 'none';
    }
});

chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = userInput.value.trim();
    if (!message) return;

    appendMessage(message, 'user-message');
    userInput.value = '';

    await sendMessageToServer(message);
});

async function sendChoice(val, label) {
    appendMessage(label || `View details for #${val}`, 'user-message');
    await sendMessageToServer(val);
}

async function sendMessageToServer(messageText) {
    const typingIndicator = showTypingIndicator();

    try {
        const response = await fetch('/get_response', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: messageText })
        });
        const data = await response.json();
        
        removeTypingIndicator(typingIndicator);
        appendMessage(data.reply, 'bot-message');
    } catch (error) {
        removeTypingIndicator(typingIndicator);
        appendMessage("Error: Could not process request.", 'bot-message');
    }
}

function appendMessage(text, className) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', className);
    
    let formattedText = text
        .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')
        .replace(/\n/g, '<br>')
        .replace(/---/g, '<hr style="border: 0; border-top: 1px solid rgba(255,255,255,0.1); margin: 10px 0;">');

    messageDiv.innerHTML = `<div class="message-content">${formattedText}</div>`;
    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function showTypingIndicator() {
    const indicatorDiv = document.createElement('div');
    indicatorDiv.classList.add('message', 'bot-message', 'typing-indicator');
    indicatorDiv.innerHTML = `
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
    `;
    chatBox.appendChild(indicatorDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
    return indicatorDiv;
}

function removeTypingIndicator(element) {
    if (element && element.parentNode) {
        element.parentNode.removeChild(element);
    }
}

/* ==========================================================================
   WEATHER FEATURE (Open-Meteo API - Free, No API Key, No ML Models)
   ========================================================================== */

const MUNICIPALITY_COORDINATES = {
    "laoag": { lat: 18.1960, lon: 120.5927, name: "Laoag City" },
    "batac": { lat: 18.0556, lon: 120.5650, name: "Batac City" },
    "pagudpud": { lat: 18.5583, lon: 120.7861, name: "Pagudpud" },
    "paoay": { lat: 18.0617, lon: 120.5211, name: "Paoay" },
    "bacarra": { lat: 18.2511, lon: 120.6128, name: "Bacarra" },
    "burgos": { lat: 18.5144, lon: 120.6458, name: "Burgos" },
    "bangui": { lat: 18.5378, lon: 120.7678, name: "Bangui" },
    "badoc": { lat: 17.9264, lon: 120.4725, name: "Badoc" },
    "sarrat": { lat: 18.1672, lon: 120.6542, name: "Sarrat" },
    "vintar": { lat: 18.2300, lon: 120.6400, name: "Vintar" },
    "san nicolas": { lat: 18.1725, lon: 120.5958, name: "San Nicolas" },
    "dingras": { lat: 18.1000, lon: 120.7000, name: "Dingras" },
    "solsona": { lat: 18.0933, lon: 120.7719, name: "Solsona" },
    "piddig": { lat: 18.1644, lon: 120.7078, name: "Piddig" },
    "pasuquin": { lat: 18.3333, lon: 120.6167, name: "Pasuquin" },
    "adams": { lat: 18.4617, lon: 120.8931, name: "Adams" },
    "banna": { lat: 17.9833, lon: 120.6500, name: "Banna" },
    "marcos": { lat: 18.0333, lon: 120.6833, name: "Marcos" },
    "nueva era": { lat: 17.9167, lon: 120.6667, name: "Nueva Era" },
    "pinili": { lat: 17.9500, lon: 120.5333, name: "Pinili" }
};

const WEATHER_CODES = {
    0: "☀️ Clear Sky", 1: "🌤️ Mainly Clear", 2: "⛅ Partly Cloudy", 3: "☁️ Overcast",
    45: "🌫️ Foggy", 48: "🌫️ Depositing Rime Fog", 51: "🌦️ Light Drizzle", 53: "🌦️ Moderate Drizzle",
    55: "🌧️ Dense Drizzle", 61: "🌧️ Slight Rain", 63: "🌧️ Moderate Rain", 65: "🌧️ Heavy Rain",
    80: "🌦️ Slight Rain Showers", 81: "🌧️ Moderate Rain Showers", 82: "⛈️ Violent Rain Showers",
    95: "⛈️ Thunderstorm"
};

async function fetchWeather(locationKey) {
    const loc = MUNICIPALITY_COORDINATES[locationKey];
    if (!loc) return;

    try {
        const url = `https://api.open-meteo.com/v1/forecast?latitude=${loc.lat}&longitude=${loc.lon}&current_weather=true`;
        const response = await fetch(url);
        const data = await response.json();

        if (data && data.current_weather) {
            const temp = Math.round(data.current_weather.temperature);
            const code = data.current_weather.weathercode;
            const wind = data.current_weather.windspeed;
            const condition = WEATHER_CODES[code] || "🌤️ Fair";

            displayWeatherCard(loc.name, temp, condition, wind);
        }
    } catch (error) {
        console.error("Error fetching weather:", error);
    }

    // Reset dropdown selection placeholder
    document.getElementById("weatherLocationSelect").value = "";
}

function displayWeatherCard(cityName, temp, condition, wind) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', 'bot-message');
    
    messageDiv.innerHTML = `
        <div class="weather-card">
            <div class="weather-header">📍 Current Weather in <b>${cityName}</b></div>
            <div class="weather-temp">${temp}°C <span class="weather-cond">${condition}</span></div>
            <div class="weather-details">💨 Wind Speed: ${wind} km/h</div>
        </div>
    `;

    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}