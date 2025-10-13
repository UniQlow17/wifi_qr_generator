document.addEventListener('DOMContentLoaded', () => {
    loadSSIDs();
    const ssidSelect = document.getElementById('ssid');
    const newSsidInput = document.getElementById('newSsid');

    ssidSelect.addEventListener('change', () => {
        if (ssidSelect.value === '') {
            newSsidInput.style.display = 'block';
            newSsidInput.setAttribute('required', 'required');
            newSsidInput.focus();
        } else {
            newSsidInput.style.display = 'none';
            newSsidInput.removeAttribute('required');
            newSsidInput.value = ''; // Clear new SSID input when selecting an existing one
        }
    });
});

document.getElementById('qrForm').addEventListener('submit', async function(event) {
    event.preventDefault();

    const ssidSelect = document.getElementById('ssid');
    const newSsidInput = document.getElementById('newSsid');
    let ssid = ssidSelect.value;

    if (ssid === '') { // If "Select or type a new SSID" is chosen
        ssid = newSsidInput.value;
    }

    const password = document.getElementById('password').value;
    const encryption = document.getElementById('encryption').value;

    if (!ssid) {
        alert('SSID is required!');
        return;
    }

    // Save SSID to local storage
    saveSSID(ssid);

    const formData = new FormData();
    formData.append('ssid', ssid);
    formData.append('password', password);
    formData.append('encryption', encryption);

    try {
        const response = await fetch('/generate_qr', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json();
            alert('Error: ' + errorData.error);
            return;
        }

        const data = await response.json();
        const qrCodeImage = document.getElementById('qrCodeImage');
        const downloadLink = document.getElementById('downloadLink');

        qrCodeImage.src = data.qr_code;
        qrCodeImage.style.display = 'block';
        downloadLink.href = data.qr_code;
        downloadLink.style.display = 'block';

    } catch (error) {
        console.error('Error generating QR code:', error);
        alert('An error occurred while generating the QR code.');
    }
});

function togglePasswordVisibility() {
    const passwordField = document.getElementById('password');
    const toggleButton = document.querySelector('.toggle-password');
    if (passwordField.type === 'password') {
        passwordField.type = 'text';
        toggleButton.textContent = 'Hide';
    } else {
        passwordField.type = 'password';
        toggleButton.textContent = 'Show';
    }
}

function saveSSID(ssid) {
    let ssids = JSON.parse(localStorage.getItem('savedSSIDs')) || [];
    if (!ssids.includes(ssid)) {
        ssids.push(ssid);
        localStorage.setItem('savedSSIDs', JSON.stringify(ssids));
        loadSSIDs(); // Reload select with new SSID
    }
}

function loadSSIDs() {
    const ssids = JSON.parse(localStorage.getItem('savedSSIDs')) || [];
    const ssidSelect = document.getElementById('ssid');
    ssidSelect.innerHTML = '<option value="">--Select or type a new SSID--</option>'; // Clear existing options and add default

    ssids.forEach(ssid => {
        const option = document.createElement('option');
        option.value = ssid;
        option.textContent = ssid;
        ssidSelect.appendChild(option);
    });
}