# Cipher Mail

A dark, sleek private messaging web app built with Flask + MySQL.

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set environment variables
```bash
export DB_HOST=localhost
export DB_USER=root
export DB_PASSWORD=your_mysql_password
export SECRET_KEY=your_random_secret_key_here
```

On Windows (PowerShell):
```powershell
$env:DB_HOST="localhost"
$env:DB_USER="root"
$env:DB_PASSWORD="your_mysql_password"
$env:SECRET_KEY="your_random_secret_key_here"
```

Generate a secure SECRET_KEY:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Run
```bash
python app.py
```

Visit `http://localhost:5000`

### 4. Run on local network (accessible from other devices)
```bash
flask run --host=0.0.0.0 --port=5000
```

## Project Structure
```
minimail/
├── app.py                  # Main Flask application
├── requirements.txt
├── static/
│   ├── css/style.css       # All styles
│   ├── js/main.js          # Frontend JS
│   └── uploads/            # Profile pictures (auto-created)
└── templates/
    ├── base.html           # Base layout with sidebar
    ├── home.html           # Landing page
    ├── login.html
    ├── signup.html
    ├── dashboard.html
    ├── messages.html
    ├── send_message.html
    └── profile.html
```

## Changes from original

| Feature | Before | After |
|---|---|---|
| Secret key | Hardcoded string | `SECRET_KEY` env var (random fallback) |
| Passwords | 4-digit PIN, plaintext | Bcrypt-hashed, no length limit (min 6) |
| Profile image | None | Upload to `static/uploads/` |
| Display name | Not supported | Editable, visible to others |
| Change password | Not supported | Supported (requires current password) |
| Delete account | No password confirm | Requires password confirmation |
| Frontend | Bootstrap default | Custom dark design system |
| Receiver lookup | None | Live AJAX user lookup on compose |
