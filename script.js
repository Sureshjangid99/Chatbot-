// script.js
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const savedList = document.getElementById('saved-list');
const logoutButton = document.getElementById('logout-button');

let token = null; // Google auth token

// Google Sign-In Initialization
function onSignIn(googleUser) {
    token = googleUser.getAuthResponse().id_token;
    document.getElementById('google-signin-button').style.display = 'none';
    logoutButton.style.display = 'block';
    loadSavedEvents();
}

function signOut() {
    const auth2 = gapi.auth2.getAuthInstance();
    auth2.signOut().then(() => {
        token = null;
        document.getElementById('google-signin-button').style.display = 'block';
        logoutButton.style.display = 'none';
        savedList.innerHTML = '';
    });
}

window.onLoadCallback = function() {
    gapi.load('auth2', () => {
        gapi.auth2.init({
            client_id: 'YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com' // Replace with your Google Client ID
        });
    });

    // Render Google Sign-In button
    gapi.signin2.render('google-signin-button', {
        'scope': 'profile email https://www.googleapis.com/auth/calendar.events', // For Calendar API
        'width': 240,
        'height': 50,
        'longtitle': true,
        'theme': 'dark',
        'onsuccess': onSignIn,
        'onfailure': (error) => console.error(error)
    });
};

// Load Google API
(function() {
    const script = document.createElement('script');
    script.src = 'https://apis.google.com/js/platform.js?onload=onLoadCallback';
    script.async = true;
    script.defer = true;
    document.body.appendChild(script);
})();

logoutButton.addEventListener('click', signOut);

sendButton.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    addMessage('user', message);
    userInput.value = '';

    try {
        const response = await axios.post('/api/chat', { message }, {
            headers: { Authorization: `Bearer ${token}` }
        });
        addMessage('bot', response.data.reply);

        // If the response includes events, allow saving
        if (response.data.events) {
            response.data.events.forEach(event => {
                addMessage('bot', `Event: ${event.name} - ${event.date} <button onclick="saveEvent('${event.id}')">Save</button>`);
            });
        }
    } catch (error) {
        addMessage('bot', 'Error: Could not get response.');
    }
}

function addMessage(sender, text) {
    const div = document.createElement('div');
    div.classList.add('message', `${sender}-message`);
    div.innerHTML = text; // Use innerHTML for buttons
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function saveEvent(eventId) {
    if (!token) {
        alert('Please sign in to save events.');
        return;
    }
    try {
        await axios.post('/api/save-event', { eventId }, {
            headers: { Authorization: `Bearer ${token}` }
        });
        loadSavedEvents();
        alert('Event saved!');
    } catch (error) {
        alert('Error saving event.');
    }
}

async function loadSavedEvents() {
    if (!token) return;
    try {
        const response = await axios.get('/api/saved-events', {
            headers: { Authorization: `Bearer ${token}` }
        });
        savedList.innerHTML = '';
        response.data.forEach(event => {
            const li = document.createElement('li');
            li.innerHTML = `${event.name} - ${event.date} <button onclick="shareEvent('${event.id}')">Share</button> <button onclick="setReminder('${event.id}')">Set Reminder</button>`;
            savedList.appendChild(li);
        });
    } catch (error) {
        console.error('Error loading saved events.');
    }
}

function shareEvent(eventId) {
    // Implement sharing logic, e.g., copy link to clipboard
    alert(`Share link for event ${eventId}`);
}

async function setReminder(eventId) {
    if (!token) return;
    try {
        await axios.post('/api/set-reminder', { eventId }, {
            headers: { Authorization: `Bearer ${token}` }
        });
        alert('Reminder set!');
    } catch (error) {
        alert('Error setting reminder.');
    }
}