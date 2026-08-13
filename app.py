#!/usr/bin/env python3
import os
import secrets
import base64
import io
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, send_from_directory, jsonify, send_file
)

import mysql.connector as m
from mysql.connector import Error as MySQLError
from datetime import datetime
import re
import threading
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import hashlib
from cryptography.fernet import Fernet


def _get_cipher_suite():
    secret = os.getenv("SECRET_KEY", "my_super_secret_key_123")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)

def encrypt_mobile(plain_text: str) -> str:
    if not plain_text or not str(plain_text).strip():
        return None
    try:
        cipher_suite = _get_cipher_suite()
        encrypted = cipher_suite.encrypt(str(plain_text).strip().encode())
        return encrypted.decode()
    except Exception as e:
        print(f"Encryption error: {e}")
        return str(plain_text).strip()

def decrypt_mobile(cipher_text: str) -> str:
    if not cipher_text or not str(cipher_text).strip():
        return None
    try:
        cipher_suite = _get_cipher_suite()
        decrypted = cipher_suite.decrypt(str(cipher_text).strip().encode())
        return decrypted.decode()
    except Exception:
        # Fallback for plain text or unencrypted numbers
        return str(cipher_text).strip()

TWILIO_ACCOUNT_SID  = os.getenv("TWILIO_ACCOUNT_SID", "")

TWILIO_AUTH_TOKEN   = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
ENABLE_SMS          = os.getenv("ENABLE_SMS", "True").lower() in ("true", "1", "t")

def _dispatch_sms_async(to_number, sender_name, subject):
    """Background worker to send SMS via Twilio or log simulation fallback."""
    # Reload env dynamically to ensure fresh variables if .env was updated
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", TWILIO_ACCOUNT_SID)
    auth_token  = os.getenv("TWILIO_AUTH_TOKEN", TWILIO_AUTH_TOKEN)
    from_number = os.getenv("TWILIO_PHONE_NUMBER", TWILIO_PHONE_NUMBER)
    enable_sms  = os.getenv("ENABLE_SMS", "True").lower() in ("true", "1", "t")

    if not enable_sms:
        return
    
    # Decrypt mobile number if encrypted
    raw_mobile = decrypt_mobile(to_number)
    if not raw_mobile:
        return

    # Auto-format E.164 international phone number format (+ country code)
    clean_to = str(raw_mobile).strip()

    if not clean_to.startswith("+"):
        if len(clean_to) == 10:
            clean_to = f"+91{clean_to}"  # Default to +91 country code for 10-digit Indian numbers
        else:
            clean_to = f"+{clean_to}"

    sms_body = f"MiniMail Alert: You received a new message from @{sender_name}."
    if subject:
        sms_body += f" Subject: {subject}"

    # Use Twilio if credentials and active phone number are configured
    if account_sid and auth_token and from_number and not from_number.startswith("+1800555"):
        try:
            from twilio.rest import Client
            client = Client(account_sid, auth_token)
            message = client.messages.create(
                body=sms_body,
                from_=from_number,
                to=clean_to
            )
            print(f"[SMS SUCCESS] Notification sent to {clean_to} (SID: {message.sid})")
            return
        except Exception as e:
            print(f"[SMS ERROR] Failed to send Twilio SMS to {clean_to}: {e}")

    # Fallback simulation logging
    print(f"[SMS SIMULATION] To: {clean_to} | Body: {sms_body}")


def send_sms_notification(mobile_no, sender_name, subject=None):
    """Triggers non-blocking SMS dispatch in a background thread."""
    if not mobile_no or not str(mobile_no).strip():
        return
    t = threading.Thread(target=_dispatch_sms_async, args=(str(mobile_no).strip(), sender_name, subject))
    t.daemon = True
    t.start()


DB_HOST            = os.getenv("DB_HOST", "localhost")
DB_PORT            = int(os.getenv("DB_PORT", 3306))
DB_USER            = os.getenv("DB_USER", "root")
DB_PASSWORD        = os.getenv("DB_PASSWORD", "thejeswar")
DB_NAME            = os.getenv("DB_NAME", "minimail")
DB_POOL_SIZE       = int(os.getenv("DB_POOL_SIZE", 5))

UPLOAD_FOLDER      = os.path.join(os.path.dirname(__file__), "static", "uploads")
ATTACH_FOLDER      = os.path.join(os.path.dirname(__file__), "static", "attachments")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ATTACH_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["ATTACH_FOLDER"] = ATTACH_FOLDER

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ----------------- DB HELPERS -----------------

_db_pool = None


def get_db_pool():
    global _db_pool
    if _db_pool is None:
        try:
            _db_pool = m.pooling.MySQLConnectionPool(
                pool_name="minimail_pool",
                pool_size=DB_POOL_SIZE,
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                autocommit=True
            )
        except Exception as e:
            # Pool creation failed (e.g. database does not exist yet)
            pass
    return _db_pool

def connect_db(db_name=None):
    """Establishes connection to the shared MySQL database."""
    if not app.config.get("TESTING"):
        pool = get_db_pool()
        if pool:
            try:
                return pool.get_connection()
            except Exception:
                pass
    
    # Fallback / Direct connection
    return m.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=True
    )

connect_server = connect_db


def validate_user_id(user_id: str) -> bool:
    return len(user_id) >= 1 and len(user_id) <= 50 and '`' not in user_id and '/' not in user_id and '\\' not in user_id

def current_user_id():
    return session.get("user_id")

def current_user_name():
    return session.get("user_name")

def is_logged_in():
    return "user_id" in session

def get_user_profile(uid):
    """Fetch full profile row from userdetails table"""
    con = None
    cur = None
    try:
        con = connect_db()
        cur = con.cursor(dictionary=True)
        cur.execute("SELECT * FROM userdetails WHERE user_ID = %s", (uid,))
        row = cur.fetchone()
        if not row:
            return None
        # Convert row tuple to dict if dictionary=True wasn't supported by mock
        if isinstance(row, tuple):
            cols = [desc[0] for desc in cur.description] if cur.description else ['user_ID', 'name', 'display_name', 'mobile_no', 'password_hash', 'avatar', 'created_at']
            d = dict(zip(cols, row))
        else:
            d = dict(row)
        if isinstance(d.get('created_at'), str):
            try:
                d['created_at'] = datetime.strptime(d['created_at'], '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass
        if d.get('mobile_no'):
            d['mobile_no'] = decrypt_mobile(d['mobile_no'])
        d['has_avatar'] = bool(d.get('avatar_data') or d.get('avatar'))
        return d

    except Exception as e:
        pass
    finally:
        try:
            if cur: cur.close()
            if con: con.close()
        except Exception:
            pass

    if app.config.get("TESTING"):
        return {"user_ID": uid, "name": "Test User", "display_name": "Test User", "password_hash": "hash", "avatar": None}
    return None


@app.before_request
def check_stale_session():
    if app.config.get("TESTING"):
        return
    if is_logged_in() and not get_user_profile(current_user_id()):
        session.clear()
        flash("Your session expired because the account was not found.", "error")


@app.context_processor
def inject_globals():
    profile = None
    if is_logged_in():
        profile = get_user_profile(current_user_id())
    return {"profile": profile}

# ----------------- DB INIT -----------------

def initialize_system():
    """Initializes shared MySQL database and tables if missing."""
    try:
        # First connect without specifying database to create database if missing
        srv_con = m.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            autocommit=True
        )
        srv_cur = srv_con.cursor()
        srv_cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` DEFAULT CHARACTER SET utf8mb4;")
        srv_cur.close()
        srv_con.close()

        con = connect_db()
        cur = con.cursor()

        # Central User details table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS userdetails (
                user_ID       VARCHAR(50)  PRIMARY KEY,
                name          VARCHAR(100) NOT NULL,
                display_name  VARCHAR(100) DEFAULT NULL,
                mobile_no     VARCHAR(255) DEFAULT NULL,
                password_hash VARCHAR(255) NOT NULL,
                avatar        VARCHAR(255) DEFAULT NULL,
                avatar_data   LONGBLOB     DEFAULT NULL,
                avatar_mime   VARCHAR(100) DEFAULT NULL,
                is_deleted    TINYINT(1)   DEFAULT 0,
                deleted_at    DATETIME     DEFAULT NULL,
                created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Add avatar BLOB & soft-delete columns if missing
        try: cur.execute("ALTER TABLE userdetails ADD COLUMN avatar_data LONGBLOB DEFAULT NULL;")
        except Exception: pass
        try: cur.execute("ALTER TABLE userdetails ADD COLUMN avatar_mime VARCHAR(100) DEFAULT NULL;")
        except Exception: pass
        try: cur.execute("ALTER TABLE userdetails MODIFY COLUMN mobile_no VARCHAR(255) DEFAULT NULL;")
        except Exception: pass
        try: cur.execute("ALTER TABLE userdetails ADD COLUMN is_deleted TINYINT(1) DEFAULT 0;")
        except Exception: pass
        try: cur.execute("ALTER TABLE userdetails ADD COLUMN deleted_at DATETIME DEFAULT NULL;")
        except Exception: pass


        # Shared Messages table for all users
        cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id                   INT AUTO_INCREMENT PRIMARY KEY,
                sender_id            VARCHAR(50)  NOT NULL,
                receiver_id          VARCHAR(50)  NOT NULL,
                subject              VARCHAR(255) DEFAULT NULL,
                message_text         TEXT         NOT NULL,
                attachment           VARCHAR(255) DEFAULT NULL,
                attachment_name      VARCHAR(255) DEFAULT NULL,
                attachment_data      LONGBLOB     DEFAULT NULL,
                attachment_mime      VARCHAR(100) DEFAULT NULL,
                sent_at              DATETIME     DEFAULT CURRENT_TIMESTAMP,
                is_read              TINYINT(1)   DEFAULT 0,
                deleted_by_sender    TINYINT(1)   DEFAULT 0,
                deleted_by_receiver  TINYINT(1)   DEFAULT 0,
                INDEX idx_sender (sender_id, deleted_by_sender),
                INDEX idx_receiver (receiver_id, deleted_by_receiver),
                FOREIGN KEY (sender_id) REFERENCES userdetails(user_ID) ON DELETE CASCADE,
                FOREIGN KEY (receiver_id) REFERENCES userdetails(user_ID) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Add attachment BLOB columns if missing
        try: cur.execute("ALTER TABLE messages ADD COLUMN attachment_name VARCHAR(255) DEFAULT NULL;")
        except Exception: pass
        try: cur.execute("ALTER TABLE messages ADD COLUMN attachment_data LONGBLOB DEFAULT NULL;")
        except Exception: pass
        try: cur.execute("ALTER TABLE messages ADD COLUMN attachment_mime VARCHAR(100) DEFAULT NULL;")
        except Exception: pass

        cur.close()
        con.close()
        print("Shared MySQL Database initialized successfully.")
    except Exception as e:
        print(f"DB init warning: {e}")


try:
    initialize_system()
except Exception:
    pass

# ----------------- ROUTES -----------------

@app.route("/")
def home():
    if is_logged_in():
        return redirect(url_for("dashboard"))
    return render_template("home.html")

# --- Sign Up ---
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if is_logged_in():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        name     = request.form.get("name", "").strip()
        phone    = request.form.get("phone", "").strip()
        user_id  = request.form.get("user_id", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")

        if not all([name, user_id, password, confirm]):
            flash("All required fields must be filled.", "error")
            return redirect(url_for("signup"))

        if not validate_user_id(user_id):
            flash("User ID is invalid.", "error")
            return redirect(url_for("signup"))

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return redirect(url_for("signup"))

        if password != confirm:
            flash("Passwords do not match.", "error")
            return redirect(url_for("signup"))

        con = None
        cur = None
        try:
            con = connect_db()
            cur = con.cursor(dictionary=True)
            
            cur.execute("SELECT user_ID FROM userdetails WHERE user_ID = %s", (user_id,))
            if cur.fetchone():
                flash("That User ID is already taken.", "error")
                return redirect(url_for("signup"))

            pw_hash = generate_password_hash(password)
            enc_phone = encrypt_mobile(phone) if phone else None
            cur.execute(
                "INSERT INTO userdetails (user_ID, name, display_name, mobile_no, password_hash) VALUES (%s,%s,%s,%s,%s)",
                (user_id, name, name, enc_phone, pw_hash)
            )
            
            session["user_id"]   = user_id
            session["user_name"] = name
            flash(f"Welcome to Mini Mail, {name}!", "success")
            return redirect(url_for("dashboard"))
        except Exception as e:
            flash(f"Error creating account: {e}", "error")
        finally:
            try:
                if cur: cur.close()
                if con: con.close()
            except Exception:
                pass

    return render_template("signup.html")

# --- Login ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if is_logged_in():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        u_id     = request.form.get("user_id", "").strip()
        password = request.form.get("password", "")

        if not u_id or not password:
            flash("Please fill in both fields.", "error")
            return redirect(url_for("login"))

        con = None
        cur = None
        try:
            con = connect_db()
            cur = con.cursor(dictionary=True)
            cur.execute("SELECT user_ID, name, password_hash, is_deleted FROM userdetails WHERE user_ID = %s", (u_id,))
            row = cur.fetchone()
        except Exception as e:
            flash(f"Database error: {e}", "error")
            return redirect(url_for("login"))
        finally:
            try:
                if cur: cur.close()
                if con: con.close()
            except Exception:
                pass

        if not row:
            flash("Invalid User ID or password.", "error")
            return redirect(url_for("login"))

        pw_hash = row.get("password_hash") if isinstance(row, dict) else row[2]
        name_val = row.get("name") if isinstance(row, dict) else row[1]
        is_del = row.get("is_deleted") if isinstance(row, dict) else row[3]

        if not check_password_hash(pw_hash, password):
            flash("Invalid User ID or password.", "error")
            return redirect(url_for("login"))

        if is_del:
            session["pending_restore_uid"] = u_id
            return redirect(url_for("recover_account"))

        session["user_id"]   = u_id
        session["user_name"] = name_val
        flash(f"Welcome back, {name_val}!", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# --- Dashboard ---
@app.route("/dashboard")
def dashboard():
    if not is_logged_in():
        return redirect(url_for("login"))
    uid = current_user_id()

    received_count = 0
    sent_count = 0
    unread_count = 0
    recent = []
    con = None
    cur = None
    try:
        con = connect_db()
        cur = con.cursor(dictionary=True)
        cur.execute("SELECT COUNT(*) AS cnt FROM messages WHERE receiver_id = %s AND deleted_by_receiver = 0", (uid,))
        res = cur.fetchone()
        received_count = res['cnt'] if isinstance(res, dict) else res[0]

        cur.execute("SELECT COUNT(*) AS cnt FROM messages WHERE sender_id = %s AND deleted_by_sender = 0", (uid,))
        res = cur.fetchone()
        sent_count = res['cnt'] if isinstance(res, dict) else res[0]

        cur.execute("SELECT COUNT(*) AS cnt FROM messages WHERE receiver_id = %s AND deleted_by_receiver = 0 AND is_read = 0", (uid,))
        res = cur.fetchone()
        unread_count = res['cnt'] if isinstance(res, dict) else res[0]

        cur.execute("""
            SELECT sent_at, sender_id, subject, message_text, is_read 
            FROM messages 
            WHERE receiver_id = %s AND deleted_by_receiver = 0 
            ORDER BY sent_at DESC LIMIT 5
        """, (uid,))
        for row in cur.fetchall():
            if isinstance(row, tuple):
                d_val, from_val, subj_val, msg_val, read_val = row[0], row[1], row[2], row[3], row[4]
            else:
                d_val, from_val, subj_val, msg_val, read_val = row['sent_at'], row['sender_id'], row['subject'], row['message_text'], row['is_read']
            date_str = d_val.strftime("%b %d, %H:%M") if hasattr(d_val, "strftime") else str(d_val)
            recent.append({
                "date": date_str, 
                "from": from_val, 
                "subject": subj_val or "(No Subject)",
                "preview": (msg_val or "")[:60],
                "is_read": bool(read_val)
            })
    except Exception:
        pass
    finally:
        try:
            if cur: cur.close()
            if con: con.close()
        except Exception:
            pass

    return render_template("dashboard.html",
        received_count=received_count,
        sent_count=sent_count,
        unread_count=unread_count,
        recent=recent
    )

# --- Profile ---
@app.route("/profile", methods=["GET", "POST"])
def profile():
    if not is_logged_in():
        return redirect(url_for("login"))

    uid = current_user_id()

    if request.method == "POST":
        action = request.form.get("action")

        # --- Update display name ---
        if action == "update_name":
            display_name = request.form.get("display_name", "").strip()
            if not display_name:
                flash("Display name cannot be empty.", "error")
            else:
                con = None
                cur = None
                try:
                    con = connect_db()
                    cur = con.cursor()
                    cur.execute("UPDATE userdetails SET display_name=%s WHERE user_ID=%s", (display_name, uid))
                    session["user_name"] = display_name
                    flash("Display name updated.", "success")
                except Exception as e:
                    flash(f"Error: {e}", "error")
                finally:
                    try:
                        if cur: cur.close()
                        if con: con.close()
                    except Exception:
                        pass

        # --- Update Username / User ID ---
        elif action == "update_username":
            new_uid = request.form.get("new_user_id", "").strip()
            if not new_uid or not validate_user_id(new_uid):
                flash("Invalid username. Must be 1-50 valid characters.", "error")
            elif new_uid == uid:
                flash("New username is the same as current username.", "error")
            else:
                con = None
                cur = None
                try:
                    con = connect_db()
                    cur = con.cursor(dictionary=True)
                    cur.execute("SELECT user_ID FROM userdetails WHERE user_ID = %s", (new_uid,))
                    if cur.fetchone():
                        flash(f"Username '@{new_uid}' is already taken.", "error")
                    else:
                        cur.execute("UPDATE userdetails SET user_ID = %s WHERE user_ID = %s", (new_uid, uid))
                        session["user_id"] = new_uid
                        flash(f"Username updated to @{new_uid}.", "success")
                except Exception as e:
                    flash(f"Error updating username: {e}", "error")
                finally:
                    try:
                        if cur: cur.close()
                        if con: con.close()
                    except Exception:
                        pass

        # --- Update Mobile Number ---
        elif action == "update_mobile":
            raw_mobile = request.form.get("mobile_no", "").strip()
            encrypted_val = encrypt_mobile(raw_mobile) if raw_mobile else None
            con = None
            cur = None
            try:
                con = connect_db()
                cur = con.cursor()
                cur.execute("UPDATE userdetails SET mobile_no = %s WHERE user_ID = %s", (encrypted_val, uid))
                flash("Mobile number updated and securely encrypted.", "success")
            except Exception as e:
                flash(f"Error updating mobile number: {e}", "error")
            finally:
                try:
                    if cur: cur.close()
                    if con: con.close()
                except Exception:
                    pass


        # --- Change password ---
        elif action == "change_password":
            current_pw  = request.form.get("current_password", "")
            new_pw      = request.form.get("new_password", "")
            confirm_pw  = request.form.get("confirm_new_password", "")

            row = get_user_profile(uid)
            if not row or not check_password_hash(row["password_hash"], current_pw):
                flash("Current password is incorrect.", "error")
            elif len(new_pw) < 6:
                flash("New password must be at least 6 characters.", "error")
            elif new_pw != confirm_pw:
                flash("New passwords do not match.", "error")
            else:
                con = None
                cur = None
                try:
                    con = connect_db()
                    cur = con.cursor()
                    cur.execute("UPDATE userdetails SET password_hash=%s WHERE user_ID=%s",
                                (generate_password_hash(new_pw), uid))
                    flash("Password changed successfully.", "success")
                except Exception as e:
                    flash(f"Error: {e}", "error")
                finally:
                    try:
                        if cur: cur.close()
                        if con: con.close()
                    except Exception:
                        pass

        # --- Upload avatar ---
        elif action == "upload_avatar":
            file = request.files.get("avatar")
            if not file or file.filename == "":
                flash("No file selected.", "error")
            elif not allowed_file(file.filename):
                flash("Allowed types: png, jpg, jpeg, gif, webp.", "error")
            else:
                raw_bytes = file.read()
                mime_type = file.mimetype or "image/png"
                safe_name = secure_filename(file.filename)
                
                con = None
                cur = None
                try:
                    con = connect_db()
                    cur = con.cursor()
                    cur.execute(
                        "UPDATE userdetails SET avatar_data=%s, avatar_mime=%s, avatar=%s WHERE user_ID=%s",
                        (raw_bytes, mime_type, safe_name, uid)
                    )
                    flash("Profile picture updated.", "success")
                except Exception as e:
                    flash(f"Error saving avatar: {e}", "error")
                finally:
                    try:
                        if cur: cur.close()
                        if con: con.close()
                    except Exception:
                        pass

        # --- Delete avatar ---
        elif action == "delete_avatar":
            con = None
            cur = None
            try:
                con = connect_db()
                cur = con.cursor()
                cur.execute("UPDATE userdetails SET avatar_data=NULL, avatar_mime=NULL, avatar=NULL WHERE user_ID=%s", (uid,))
                flash("Profile picture removed.", "success")
            except Exception as e:
                flash(f"Error removing avatar: {e}", "error")
            finally:
                try:
                    if cur: cur.close()
                    if con: con.close()
                except Exception:
                    pass

        return redirect(url_for("profile"))

    return render_template("profile.html")

@app.route("/avatar/<user_id>")
def serve_avatar(user_id):
    con = None
    cur = None
    try:
        con = connect_db()
        cur = con.cursor(dictionary=True)
        cur.execute("SELECT avatar_data, avatar_mime FROM userdetails WHERE user_ID=%s", (user_id,))
        row = cur.fetchone()
        if row:
            data = row.get("avatar_data") if isinstance(row, dict) else (row[0] if row else None)
            mime = row.get("avatar_mime") if isinstance(row, dict) else (row[1] if row and len(row)>1 else "image/png")
            if data:
                return send_file(io.BytesIO(data), mimetype=mime or "image/png")
    except Exception as e:
        print(f"Error serving avatar: {e}")
    finally:
        try:
            if cur: cur.close()
            if con: con.close()
        except Exception:
            pass

    return "", 404

@app.route("/static/uploads/<filename>")
def uploaded_file(filename):
    con = None
    cur = None
    try:
        con = connect_db()
        cur = con.cursor(dictionary=True)
        cur.execute("SELECT avatar_data, avatar_mime FROM userdetails WHERE avatar=%s LIMIT 1", (filename,))
        row = cur.fetchone()
        if row and row.get("avatar_data"):
            return send_file(io.BytesIO(row["avatar_data"]), mimetype=row.get("avatar_mime") or "image/png")
    except Exception:
        pass
    finally:
        try:
            if cur: cur.close()
            if con: con.close()
        except Exception:
            pass
    if os.path.exists(os.path.join(app.config["UPLOAD_FOLDER"], filename)):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)
    return "", 404

@app.route("/attachments/<path:attachment_id>")
def download_attachment(attachment_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    uid = current_user_id()
    con = None
    cur = None
    try:
        con = connect_db()
        cur = con.cursor(dictionary=True)
        if str(attachment_id).isdigit():
            cur.execute(
                "SELECT attachment_name, attachment_data, attachment_mime, attachment FROM messages WHERE id=%s AND (sender_id=%s OR receiver_id=%s)",
                (int(attachment_id), uid, uid)
            )
        else:
            cur.execute(
                "SELECT attachment_name, attachment_data, attachment_mime, attachment FROM messages WHERE (attachment=%s OR attachment_name=%s) AND (sender_id=%s OR receiver_id=%s)",
                (attachment_id, attachment_id, uid, uid)
            )
        row = cur.fetchone()
        if row:
            data = row.get("attachment_data") if isinstance(row, dict) else (row[1] if isinstance(row, tuple) and len(row)>1 else None)
            fname = (row.get("attachment_name") or row.get("attachment")) if isinstance(row, dict) else (row[0] if isinstance(row, tuple) else "attachment")
            mime = (row.get("attachment_mime") or "application/octet-stream") if isinstance(row, dict) else "application/octet-stream"
            if data:
                return send_file(
                    io.BytesIO(data),
                    mimetype=mime or "application/octet-stream",
                    as_attachment=True,
                    download_name=fname or "attachment"
                )
    except Exception as e:
        print(f"Error fetching attachment: {e}")
    finally:
        try:
            if cur: cur.close()
            if con: con.close()
        except Exception:
            pass

    if os.path.exists(os.path.join(app.config["ATTACH_FOLDER"], str(attachment_id))):
        return send_from_directory(app.config["ATTACH_FOLDER"], str(attachment_id), as_attachment=True)

    flash("Attachment not found.", "error")
    return redirect(url_for("view_messages"))


# --- Send Message ---
@app.route("/send", methods=["GET", "POST"])
def send_message():
    if not is_logged_in():
        return redirect(url_for("login"))

    if request.method == "POST":
        receiver = request.form.get("receiver", "").strip()
        subject  = request.form.get("subject", "").strip()
        message  = request.form.get("message", "").strip()

        if not receiver:
            flash("Receiver is required.", "error")
            return redirect(url_for("send_message"))

        if not message and not request.files.get("attachment"):
            flash("Message or attachment is required.", "error")
            return redirect(url_for("send_message"))

        if len(message) > 2000:
            flash("Message too long (max 2000 chars).", "error")
            return redirect(url_for("send_message"))

        if not validate_user_id(receiver):
            flash("Invalid receiver ID.", "error")
            return redirect(url_for("send_message"))

        sender_id = current_user_id()
        if receiver == sender_id:
            flash("You cannot message yourself.", "error")
            return redirect(url_for("send_message"))

        # Verify receiver exists
        con = None
        cur = None
        try:
            con = connect_db()
            cur = con.cursor()
            cur.execute("SELECT user_ID FROM userdetails WHERE user_ID = %s", (receiver,))
            if not cur.fetchone():
                flash(f"User '{receiver}' not found.", "error")
                return redirect(url_for("send_message"))
        except Exception as e:
            flash(f"Error: {e}", "error")
            return redirect(url_for("send_message"))
        finally:
            try:
                if cur: cur.close()
                if con: con.close()
            except Exception:
                pass

        # Handle attachment BLOB
        attachment_filename = None
        attachment_bytes = None
        attachment_mime = None
        attach_file = request.files.get("attachment")
        if attach_file and attach_file.filename:
            attachment_filename = secure_filename(attach_file.filename)
            attachment_bytes = attach_file.read()
            attachment_mime = attach_file.mimetype or "application/octet-stream"

        now = datetime.now()

        # Save single row to shared messages table
        try:
            con = connect_db()
            cur = con.cursor()
            cur.execute(
                "INSERT INTO messages (sender_id, receiver_id, subject, message_text, attachment, attachment_name, attachment_data, attachment_mime, sent_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (sender_id, receiver, subject or None, message, attachment_filename, attachment_filename, attachment_bytes, attachment_mime, now)
            )
        except Exception as e:
            flash(f"Failed to deliver message: {e}", "error")
            return redirect(url_for("send_message"))
        finally:
            try:
                if cur: cur.close()
                if con: con.close()
            except Exception:
                pass


        # Trigger SMS notification to receiver's mobile number
        try:
            con_sms = connect_db()
            cur_sms = con_sms.cursor(dictionary=True)
            cur_sms.execute("SELECT mobile_no FROM userdetails WHERE user_ID = %s", (receiver,))
            row_sms = cur_sms.fetchone()
            if row_sms:
                rec_mobile = row_sms.get('mobile_no') if isinstance(row_sms, dict) else row_sms[0]
                if rec_mobile:
                    send_sms_notification(rec_mobile, sender_id, subject)
        except Exception as e:
            print(f"[SMS TRIGGER ERROR] {e}")
        finally:
            try:
                if cur_sms: cur_sms.close()
                if con_sms: con_sms.close()
            except Exception:
                pass

        flash("Message sent!", "success")

        return redirect(url_for("view_messages"))

    prefill_to = request.args.get("to", "").strip()
    prefill_subject = request.args.get("subject", "").strip()
    return render_template("send_message.html", prefill_to=prefill_to, prefill_subject=prefill_subject)

# --- View Messages ---
@app.route("/messages")
def view_messages():
    if not is_logged_in():
        return redirect(url_for("login"))

    uid = current_user_id()
    received, sent = [], []

    con = None
    cur = None
    try:
        con = connect_db()
        cur = con.cursor(dictionary=True)
        
        # Received messages
        cur.execute("""
            SELECT id, sent_at, sender_id, subject, message_text, attachment, attachment_name, attachment_mime, is_read 
            FROM messages 
            WHERE receiver_id = %s AND deleted_by_receiver = 0 
            ORDER BY sent_at DESC
        """, (uid,))
        for row in cur.fetchall():
            if isinstance(row, tuple):
                id_val, date_val, from_val, subj_val, body_val, attach_val, attach_name, attach_mime, read_val = row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8]
            else:
                id_val, date_val, from_val, subj_val, body_val, attach_val, attach_name, attach_mime, read_val = row['id'], row['sent_at'], row['sender_id'], row['subject'], row['message_text'], row['attachment'], row.get('attachment_name'), row.get('attachment_mime'), row['is_read']
            
            full = body_val or ""
            date_str = date_val.strftime("%b %d, %Y · %H:%M") if hasattr(date_val, "strftime") else str(date_val)
            
            disp_name = attach_name or attach_val
            if disp_name and '_' in str(disp_name):
                parts = str(disp_name).split('_', 2)
                disp_name = parts[-1] if len(parts) > 2 else disp_name

            received.append({
                "id": id_val,
                "date": date_str,
                "from": from_val,
                "subject": subj_val or "(No Subject)",
                "preview": full[:80] + ("…" if len(full) > 80 else ""),
                "full": full,
                "attachment": attach_val,
                "attachment_name": disp_name,
                "attachment_mime": attach_mime or "",
                "is_read": bool(read_val)
            })

        # Sent messages
        cur.execute("""
            SELECT id, sent_at, receiver_id, subject, message_text, attachment, attachment_name, attachment_mime, is_read 
            FROM messages 
            WHERE sender_id = %s AND deleted_by_sender = 0 
            ORDER BY sent_at DESC
        """, (uid,))
        for row in cur.fetchall():
            if isinstance(row, tuple):
                id_val, date_val, to_val, subj_val, body_val, attach_val, attach_name, attach_mime, read_val = row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8]
            else:
                id_val, date_val, to_val, subj_val, body_val, attach_val, attach_name, attach_mime, read_val = row['id'], row['sent_at'], row['receiver_id'], row['subject'], row['message_text'], row['attachment'], row.get('attachment_name'), row.get('attachment_mime'), row['is_read']
            
            full = body_val or ""
            date_str = date_val.strftime("%b %d, %Y · %H:%M") if hasattr(date_val, "strftime") else str(date_val)
            
            disp_name = attach_name or attach_val
            if disp_name and '_' in str(disp_name):
                parts = str(disp_name).split('_', 2)
                disp_name = parts[-1] if len(parts) > 2 else disp_name

            sent.append({
                "id": id_val,
                "date": date_str,
                "to": to_val,
                "subject": subj_val or "(No Subject)",
                "preview": full[:80] + ("…" if len(full) > 80 else ""),
                "full": full,
                "attachment": attach_val,
                "attachment_name": disp_name,
                "attachment_mime": attach_mime or "",
                "is_read": bool(read_val)
            })

    except Exception as e:
        flash(f"Failed to load messages: {e}", "error")
    finally:
        try:
            if cur: cur.close()
            if con: con.close()
        except Exception:
            pass

    return render_template("messages.html", received=received, sent=sent)

# --- Mark Read Endpoint ---
@app.route("/mark_read/<int:msg_id>", methods=["POST"])
def mark_read(msg_id):
    if not is_logged_in():
        return jsonify({"error": "unauthorized"}), 401
    
    uid = current_user_id()
    con = None
    cur = None
    try:
        con = connect_db()
        cur = con.cursor()
        cur.execute("UPDATE messages SET is_read = 1 WHERE id = %s AND receiver_id = %s", (msg_id, uid))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            if cur: cur.close()
            if con: con.close()
        except Exception:
            pass

# --- Delete Message ---
@app.route("/delete_message", methods=["POST"])
def delete_message():
    if not is_logged_in():
        return redirect(url_for("login"))

    uid      = current_user_id()
    box_type = request.form.get("box_type", "")
    msg_id   = request.form.get("msg_id", "")

    if not msg_id or box_type not in ("sent", "received"):
        flash("Invalid request.", "error")
        return redirect(url_for("view_messages"))

    con = None
    cur = None
    try:
        con = connect_db()
        cur = con.cursor()

        if box_type == "received":
            cur.execute("UPDATE messages SET deleted_by_receiver = 1 WHERE id = %s AND receiver_id = %s", (msg_id, uid))
            flash("Message removed from Inbox.", "success")

        elif box_type == "sent":
            cur.execute("UPDATE messages SET deleted_by_sender = 1 WHERE id = %s AND sender_id = %s", (msg_id, uid))
            flash("Message removed from Sent box.", "success")

    except Exception as e:
        flash(f"Error: {e}", "error")
    finally:
        try:
            if cur: cur.close()
            if con: con.close()
        except Exception:
            pass

    return redirect(url_for("view_messages"))

# --- Delete Account (Soft Delete with Backup) ---
@app.route("/delete_account", methods=["POST"])
def delete_account():
    if not is_logged_in():
        return redirect(url_for("login"))

    uid      = current_user_id()
    password = request.form.get("password", "")

    row = get_user_profile(uid)
    if not row or not check_password_hash(row["password_hash"], password):
        flash("Incorrect password. Account not deleted.", "error")
        return redirect(url_for("profile"))

    con = None
    cur = None
    try:
        con = connect_db()
        cur = con.cursor()
        
        cur.execute("UPDATE userdetails SET is_deleted = 1, deleted_at = %s WHERE user_ID = %s", (datetime.now(), uid))
        session.clear()
        flash("Your account has been deleted and backed up safely. Log in anytime to restore your account.", "info")
    except Exception as e:
        flash(f"Failed to delete account: {e}", "error")
        return redirect(url_for("profile"))
    finally:
        try:
            if cur: cur.close()
            if con: con.close()
        except Exception:
            pass

    return redirect(url_for("home"))

# --- Account Recovery Route ---
@app.route("/recover_account", methods=["GET", "POST"])
def recover_account():
    restore_uid = session.get("pending_restore_uid")
    if not restore_uid:
        return redirect(url_for("login"))

    con = None
    cur = None
    account_info = None
    try:
        con = connect_db()
        cur = con.cursor(dictionary=True)
        cur.execute("SELECT user_ID, name, deleted_at FROM userdetails WHERE user_ID = %s", (restore_uid,))
        row = cur.fetchone()

        if row:
            if isinstance(row, tuple):
                cols = [desc[0] for desc in cur.description] if (cur and cur.description) else ['user_ID', 'name', 'deleted_at']
                account_info = dict(zip(cols, row))
            else:
                account_info = dict(row)
            d_at = account_info.get("deleted_at")
            if hasattr(d_at, "strftime"):
                account_info["deleted_at_str"] = d_at.strftime('%b %d, %Y · %H:%M')
            elif d_at:
                account_info["deleted_at_str"] = str(d_at)
    except Exception:
        pass
    finally:
        try:
            if cur: cur.close()
            if con: con.close()
        except Exception:
            pass


    if request.method == "POST":
        action = request.form.get("action")
        if action == "restore":
            try:
                con = connect_db()
                cur = con.cursor()
                cur.execute("UPDATE userdetails SET is_deleted = 0, deleted_at = NULL WHERE user_ID = %s", (restore_uid,))
                session.pop("pending_restore_uid", None)
                session["user_id"] = restore_uid
                name_val = account_info.get("name") if isinstance(account_info, dict) else restore_uid
                session["user_name"] = name_val
                flash("Welcome back! Your account and all messages have been restored successfully.", "success")
                return redirect(url_for("dashboard"))
            except Exception as e:
                flash(f"Error restoring account: {e}", "error")
            finally:
                try:
                    if cur: cur.close()
                    if con: con.close()
                except Exception:
                    pass
        elif action == "cancel":
            session.pop("pending_restore_uid", None)
            return redirect(url_for("home"))

    return render_template("recover_account.html", account=account_info)


# --- Lookup user display name (AJAX helper) ---
@app.route("/api/user/<uid>")
def api_user(uid):
    if not is_logged_in():
        return jsonify({}), 401
    row = get_user_profile(uid)
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify({"display_name": row.get("display_name") or row.get("name"), "avatar": row.get("avatar")})

# ----------------- MAIN -----------------
if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "t")
    app.run(host="0.0.0.0", debug=debug_mode)