#!/usr/bin/env python3
import os
import secrets
import base64
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, send_from_directory
)
import sqlite3
from datetime import datetime
import re
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ----------------- CONFIG -----------------
from dotenv import load_dotenv
load_dotenv()

DB_FOLDER          = os.path.join(os.path.dirname(__file__), "database")
UPLOAD_FOLDER      = os.path.join(os.path.dirname(__file__), "static", "uploads")
ATTACH_FOLDER      = os.path.join(os.path.dirname(__file__), "static", "attachments")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 MB

os.makedirs(DB_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ATTACH_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["ATTACH_FOLDER"] = ATTACH_FOLDER

# ----------------- HELPERS -----------------

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def connect_db(db_name="mail"):
    db_path = os.path.join(DB_FOLDER, f"{db_name}.db")
    con = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    con.row_factory = sqlite3.Row
    return con

def validate_user_id(user_id: str) -> bool:
    # Only block characters that would break files/databases
    return len(user_id) >= 1 and len(user_id) <= 50 and '`' not in user_id and '/' not in user_id and '\\' not in user_id

def current_user_id():
    return session.get("user_id")

def current_user_name():
    return session.get("user_name")

def is_logged_in():
    return "user_id" in session

def get_user_profile(uid):
    """Fetch full profile row from mail.db"""
    try:
        con = connect_db()
        cur = con.cursor()
        cur.execute("SELECT * FROM userdetails WHERE user_ID = ?", (uid,))
        row = cur.fetchone()
        if not row: return None
        d = dict(row)
        if isinstance(d.get('created_at'), str):
            try: d['created_at'] = datetime.strptime(d['created_at'], '%Y-%m-%d %H:%M:%S')
            except ValueError: pass
        return d
    except:
        return None
    finally:
        try: cur.close(); con.close()
        except: pass

@app.before_request
def check_stale_session():
    if is_logged_in() and not get_user_profile(current_user_id()):
        session.clear()
        flash("Your session expired because the server restarted.", "error")

@app.context_processor
def inject_globals():
    profile = None
    if is_logged_in():
        profile = get_user_profile(current_user_id())
    return {"profile": profile}

# ----------------- DB INIT -----------------

def initialize_system():
    try:
        con = connect_db("mail")
        cur = con.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS userdetails (
                user_ID       VARCHAR(30)  PRIMARY KEY,
                name          VARCHAR(60)  NOT NULL,
                display_name  VARCHAR(60)  DEFAULT NULL,
                mobile_no     VARCHAR(20)  DEFAULT NULL,
                password_hash VARCHAR(255) NOT NULL,
                avatar        VARCHAR(255) DEFAULT NULL,
                created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP
            )
        """)
        con.commit()
        cur.close()
        con.close()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"DB init error: {e}")

def create_user_db(uid):
    try:
        con = connect_db(uid)
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS messages_sent(
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                date         DATETIME,
                sent_to      VARCHAR(50),
                sent_message TEXT,
                attachment   VARCHAR(255) DEFAULT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS messages_received(
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                date              DATETIME,
                received_from     VARCHAR(50),
                received_message  TEXT,
                attachment        VARCHAR(255) DEFAULT NULL
            )
        """)
        con.commit()
    finally:
        try: cur.close(); con.close()
        except: pass

initialize_system()

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

        try:
            con = connect_db()
            cur = con.cursor()
            
            cur.execute("SELECT user_ID FROM userdetails WHERE user_ID = ?", (user_id,))
            if cur.fetchone():
                flash("That User ID is already taken.", "error")
                return redirect(url_for("signup"))

            pw_hash = generate_password_hash(password)
            cur.execute(
                "INSERT INTO userdetails (user_ID, name, display_name, mobile_no, password_hash) VALUES (?,?,?,?,?)",
                (user_id, name, name, phone or None, pw_hash)
            )
            con.commit()
            create_user_db(user_id)
            # Auto-login after signup
            session["user_id"]   = user_id
            session["user_name"] = name
            flash(f"Welcome to Mini Mail, {name}!", "success")
            return redirect(url_for("dashboard"))
        except Exception as e:
            flash(f"Error creating account: {e}", "error")
        finally:
            try: cur.close(); con.close()
            except: pass

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

        try:
            con = connect_db()
            cur = con.cursor()
            
            cur.execute("SELECT name, password_hash FROM userdetails WHERE user_ID = ?", (u_id,))
            row = cur.fetchone()
        except Exception as e:
            flash(f"Database error: {e}", "error")
            return redirect(url_for("login"))
        finally:
            try: cur.close(); con.close()
            except: pass

        if not row or not check_password_hash(row[1], password):
            flash("Invalid User ID or password.", "error")
            return redirect(url_for("login"))

        session["user_id"]   = u_id
        session["user_name"] = row[0]
        flash(f"Welcome back, {row[0]}!", "success")
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

    # Fetch recent messages for preview
    received_count = 0
    sent_count = 0
    recent = []
    try:
        con = connect_db(uid)
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM messages_received")
        received_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM messages_sent")
        sent_count = cur.fetchone()[0]
        cur.execute("SELECT date, received_from, received_message FROM messages_received ORDER BY date DESC LIMIT 5")
        for row in cur.fetchall():
            date_str = row[0].strftime("%b %d, %H:%M") if hasattr(row[0], "strftime") else str(row[0])
            recent.append({"date": date_str, "from": row[1], "preview": (row[2] or "")[:60]})
    except:
        pass
    finally:
        try: cur.close(); con.close()
        except: pass

    return render_template("dashboard.html",
        received_count=received_count,
        sent_count=sent_count,
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
                try:
                    con = connect_db(); cur = con.cursor()
                    
                    cur.execute("UPDATE userdetails SET display_name=? WHERE user_ID=?", (display_name, uid))
                    con.commit()
                    session["user_name"] = display_name
                    flash("Display name updated.", "success")
                except Exception as e:
                    flash(f"Error: {e}", "error")
                finally:
                    try: cur.close(); con.close()
                    except: pass

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
                try:
                    con = connect_db(); cur = con.cursor()
                    
                    cur.execute("UPDATE userdetails SET password_hash=? WHERE user_ID=?",
                                (generate_password_hash(new_pw), uid))
                    con.commit()
                    flash("Password changed successfully.", "success")
                except Exception as e:
                    flash(f"Error: {e}", "error")
                finally:
                    try: cur.close(); con.close()
                    except: pass

        # --- Upload avatar ---
        elif action == "upload_avatar":
            file = request.files.get("avatar")
            if not file or file.filename == "":
                flash("No file selected.", "error")
            elif not allowed_file(file.filename):
                flash("Allowed types: png, jpg, jpeg, gif, webp.", "error")
            else:
                ext      = file.filename.rsplit(".", 1)[1].lower()
                filename = secure_filename(f"{uid}_avatar.{ext}")
                save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                
                try:
                    con = connect_db(); cur = con.cursor()
                    
                    
                    # Remove old avatar if it exists (in case extension is different)
                    cur.execute("SELECT avatar FROM userdetails WHERE user_ID=?", (uid,))
                    row = cur.fetchone()
                    if row and row['avatar'] and row['avatar'] != filename:
                        old_path = os.path.join(app.config["UPLOAD_FOLDER"], row['avatar'])
                        if os.path.exists(old_path):
                            os.remove(old_path)

                    file.save(save_path)
                    cur.execute("UPDATE userdetails SET avatar=? WHERE user_ID=?", (filename, uid))
                    con.commit()
                    flash("Profile picture updated.", "success")
                except Exception as e:
                    flash(f"Error saving avatar: {e}", "error")
                finally:
                    try: cur.close(); con.close()
                    except: pass

        # --- Delete avatar ---
        elif action == "delete_avatar":
            try:
                con = connect_db(); cur = con.cursor()
                
                
                # Fetch current avatar to delete from disk
                cur.execute("SELECT avatar FROM userdetails WHERE user_ID=?", (uid,))
                row = cur.fetchone()
                if row and row['avatar']:
                    old_path = os.path.join(app.config["UPLOAD_FOLDER"], row['avatar'])
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                cur.execute("UPDATE userdetails SET avatar=NULL WHERE user_ID=?", (uid,))
                con.commit()
                flash("Profile picture removed.", "success")
            except Exception as e:
                flash(f"Error removing avatar: {e}", "error")
            finally:
                try: cur.close(); con.close()
                except: pass

        return redirect(url_for("profile"))

    return render_template("profile.html")

@app.route("/static/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/attachments/<filename>")
def download_attachment(filename):
    if not is_logged_in():
        return redirect(url_for("login"))
    return send_from_directory(app.config["ATTACH_FOLDER"], filename, as_attachment=True)

# --- Send Message ---
@app.route("/send", methods=["GET", "POST"])
def send_message():
    if not is_logged_in():
        return redirect(url_for("login"))

    if request.method == "POST":
        receiver = request.form.get("receiver", "").strip()
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
        try:
            con = connect_db(); cur = con.cursor()
            
            cur.execute("SELECT user_ID FROM userdetails WHERE user_ID = ?", (receiver,))
            if not cur.fetchone():
                flash(f"User '{receiver}' not found.", "error")
                return redirect(url_for("send_message"))
        except Exception as e:
            flash(f"Error: {e}", "error")
            return redirect(url_for("send_message"))
        finally:
            try: cur.close(); con.close()
            except: pass

        # Handle attachment
        attachment_filename = None
        attach_file = request.files.get("attachment")
        if attach_file and attach_file.filename:
            ext = attach_file.filename.rsplit(".", 1)[-1].lower() if "." in attach_file.filename else "bin"
            safe_name = secure_filename(attach_file.filename)
            unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{sender_id}_{safe_name}"
            save_path = os.path.join(app.config["ATTACH_FOLDER"], unique_name)
            attach_file.save(save_path)
            attachment_filename = unique_name

        now = datetime.now()

        # Save to sender DB
        try:
            con = connect_db(sender_id)
            cur = con.cursor()
            cur.execute("INSERT INTO messages_sent (date, sent_to, sent_message, attachment) VALUES (?,?,?,?)",
                        (now, receiver, message, attachment_filename))
            con.commit()
        except Exception as e:
            flash(f"Failed to save sent message: {e}", "error")
            return redirect(url_for("send_message"))
        finally:
            try: cur.close(); con.close()
            except: pass

        # Save to receiver DB
        try:
            con = connect_db(receiver)
            cur = con.cursor()
            cur.execute("INSERT INTO messages_received (date, received_from, received_message, attachment) VALUES (?,?,?,?)",
                        (now, sender_id, message, attachment_filename))
            con.commit()
        except Exception as e:
            flash(f"Failed to deliver message: {e}", "error")
            return redirect(url_for("send_message"))
        finally:
            try: cur.close(); con.close()
            except: pass

        flash("Message sent!", "success")
        return redirect(url_for("view_messages"))

    return render_template("send_message.html")

# --- View Messages ---
@app.route("/messages")
def view_messages():
    if not is_logged_in():
        return redirect(url_for("login"))

    uid = current_user_id()
    received, sent = [], []

    try:
        con = connect_db(uid)
        cur = con.cursor()
        cur.execute("SELECT id, date, received_from, received_message, attachment FROM messages_received ORDER BY date DESC")
        for row in cur.fetchall():
            full = row[3] or ""
            date_str = row[1].strftime("%b %d, %Y · %H:%M") if hasattr(row[1], "strftime") else str(row[1])
            received.append({"id": row[0], "date": date_str, "from": row[2],
                             "preview": full[:80] + ("…" if len(full) > 80 else ""), "full": full,
                             "attachment": row[4]})

        cur.execute("SELECT id, date, sent_to, sent_message, attachment FROM messages_sent ORDER BY date DESC")
        for row in cur.fetchall():
            full = row[3] or ""
            date_str = row[1].strftime("%b %d, %Y · %H:%M") if hasattr(row[1], "strftime") else str(row[1])
            sent.append({"id": row[0], "date": date_str, "to": row[2],
                        "preview": full[:80] + ("…" if len(full) > 80 else ""), "full": full,
                        "attachment": row[4]})
    except Exception as e:
        flash(f"Failed to load messages: {e}", "error")
    finally:
        try: cur.close(); con.close()
        except: pass

    return render_template("messages.html", received=received, sent=sent)

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

    try:
        con = connect_db(uid)
        cur = con.cursor()

        if box_type == "received":
            cur.execute("DELETE FROM messages_received WHERE id = ?", (msg_id,))
            con.commit()
            flash("Message deleted.", "success")

        elif box_type == "sent":
            cur.execute("SELECT date, sent_to, sent_message FROM messages_sent WHERE id = ?", (msg_id,))
            row = cur.fetchone()
            if row:
                cur.execute("DELETE FROM messages_sent WHERE id = ?", (msg_id,))
                con.commit()
                date_val, receiver_id, msg_body = row
                try:
                    con2 = connect_db(receiver_id)
                    cur2 = con2.cursor()
                    cur2.execute("DELETE FROM messages_received WHERE date=? AND received_from=? AND received_message=?",
                                 (date_val, uid, msg_body))
                    con2.commit()
                    cur2.close(); con2.close()
                except:
                    pass
                flash("Message deleted.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    finally:
        try: cur.close(); con.close()
        except: pass

    return redirect(url_for("view_messages"))

# --- Delete Account ---
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

    try:
        con = connect_db(); cur = con.cursor()
        
        cur.execute("DELETE FROM userdetails WHERE user_ID = ?", (uid,))
        con.commit()
        try: os.remove(os.path.join(DB_FOLDER, f"{uid}.db"))
        except: pass
        con.commit()
        session.clear()
        flash("Your account has been permanently deleted.", "success")
    except Exception as e:
        flash(f"Failed to delete account: {e}", "error")
        return redirect(url_for("profile"))
    finally:
        try: cur.close(); con.close()
        except: pass

    return redirect(url_for("home"))

# --- Lookup user display name (AJAX helper) ---
@app.route("/api/user/<uid>")
def api_user(uid):
    from flask import jsonify
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