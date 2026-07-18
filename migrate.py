import os

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("connect_server()", "connect_db()")
content = content.replace("cur.execute(\"USE mail\")", "")
content = content.replace("con.cursor(dictionary=True)", "con.cursor()")
content = content.replace("m.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=uid)", "connect_db(uid)")
content = content.replace("m.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=receiver_id)", "connect_db(receiver_id)")
content = content.replace("m.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=receiver)", "connect_db(receiver)")
content = content.replace("m.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=sender_id)", "connect_db(sender_id)")
content = content.replace("cur.execute(f\"DROP DATABASE IF EXISTS `{uid}`\")", "try: os.remove(os.path.join(DB_FOLDER, f\"{uid}.db\"))\n        except: pass")
content = content.replace("%s", "?")

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)
