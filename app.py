
import os, sqlite3, uuid, smtplib
from datetime import datetime
from email.message import EmailMessage
from flask import Flask, render_template, request, redirect, url_for, abort, send_file
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
PDF_DIR = os.path.join(DATA_DIR, "pdfs")
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret")

SUPERVISORS = {
    "saud": {"name":"سعود مسفر", "signature":"saud.png", "role":"مشرف أمن"},
    "abdulrahman": {"name":"عبدالرحمن عبدالله", "signature":"abdulrahman.png", "role":"مشرف أمن"},
    "abdulaziz": {"name":"عبدالعزيز سعيد", "signature":"abdulaziz.png", "role":"مشرف أمن"},
    "salman": {"name":"سلمان صالح", "signature":"salman.png", "role":"مشرف أمن"},
    "khaled": {"name":"خالد صالح", "signature":"khaled.png", "role":"مشرف أمن"},
    "ali": {"name":"علي سعد", "signature":"ali.png", "role":"رئيس المشرفين"},
}

def db():
    con = sqlite3.connect(os.path.join(DATA_DIR, "reports.db"))
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.execute("""CREATE TABLE IF NOT EXISTS reports(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT UNIQUE,
        supervisor_key TEXT,
        supervisor_name TEXT,
        role TEXT,
        report_date TEXT,
        shift TEXT,
        assaults INTEGER DEFAULT 0,
        power_outages INTEGER DEFAULT 0,
        visitors INTEGER DEFAULT 0,
        elevator_failures INTEGER DEFAULT 0,
        supervisor_minutes INTEGER DEFAULT 0,
        notes TEXT,
        created_at TEXT
    )""")
    con.commit()
    con.close()

def arabic_text(s):
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(str(s or "")))
    except Exception:
        return str(s or "")

def make_pdf(row):
    font_path = os.path.join(APP_DIR, "static", "fonts", "DejaVuSans.ttf")
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont("Arabic", font_path))
            font = "Arabic"
        except Exception:
            font = "Helvetica"
    else:
        font = "Helvetica"
    filename = f"report_{row['id']}_{row['token']}.pdf"
    path = os.path.join(PDF_DIR, filename)
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    c.setTitle("تقرير إدارة الأمن والسلامة")
    c.setFont(font, 16)
    c.drawRightString(w-20*mm, h-20*mm, arabic_text("إدارة الأمن والسلامة - تقرير المشرف"))
    c.setFont(font, 11)
    y = h-40*mm
    lines = [
        ("اسم المشرف", row["supervisor_name"]),
        ("الصفة", row["role"]),
        ("التاريخ", row["report_date"]),
        ("الوردية", row["shift"]),
        ("عدد الاعتداءات", row["assaults"]),
        ("عطل في التيار", row["power_outages"]),
        ("عدد الزوار", row["visitors"]),
        ("تعطل المصاعد", row["elevator_failures"]),
        ("محاضر المشرفين", row["supervisor_minutes"]),
        ("ملاحظات", row["notes"] or "-"),
    ]
    for label, value in lines:
        c.drawRightString(w-20*mm, y, arabic_text(f"{label}: {value}"))
        y -= 12*mm
        if y < 35*mm:
            c.showPage(); c.setFont(font, 11); y = h-25*mm
    sig = SUPERVISORS[row["supervisor_key"]]["signature"]
    sig_path = os.path.join(APP_DIR, "static", "signatures", sig)
    if os.path.exists(sig_path):
        try:
            c.drawImage(sig_path, w-75*mm, 15*mm, width=55*mm, height=25*mm, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass
    c.setFont(font, 9)
    c.drawRightString(w-20*mm, 10*mm, arabic_text(f"تم إنشاء التقرير: {row['created_at']}"))
    c.save()
    return path

def send_email(pdf_path, row):
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    recipients = [x.strip() for x in os.environ.get(
        "REPORT_RECIPIENTS", "3bu.3lazz@gmail.com,abt-kfh-sec@moh.gov.sa").split(",") if x.strip()]
    if not (host and user and password and recipients):
        return False, "إعدادات البريد غير مفعلة"
    msg = EmailMessage()
    msg["Subject"] = f"تقرير مشرف الأمن - {row['supervisor_name']} - {row['report_date']}"
    msg["From"] = user
    msg["To"] = ", ".join(recipients)
    msg.set_content("مرفق تقرير المشرف بصيغة PDF.")
    with open(pdf_path, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename=os.path.basename(pdf_path))
    port = int(os.environ.get("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port) as s:
        s.starttls(); s.login(user, password); s.send_message(msg)
    return True, "تم الإرسال"

@app.route("/")
def home():
    return render_template("home.html", supervisors=SUPERVISORS)

@app.route("/report/<key>", methods=["GET","POST"])
def report(key):
    if key not in SUPERVISORS: abort(404)
    sup = SUPERVISORS[key]
    if request.method == "POST":
        def n(name):
            try: return max(0, int(request.form.get(name, 0) or 0))
            except: return 0
        token = uuid.uuid4().hex[:12]
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        con = db()
        cur = con.execute("""INSERT INTO reports
        (token,supervisor_key,supervisor_name,role,report_date,shift,assaults,power_outages,visitors,elevator_failures,supervisor_minutes,notes,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            token,key,sup["name"],sup["role"],
            request.form.get("report_date") or datetime.now().strftime("%Y-%m-%d"),
            request.form.get("shift",""),
            n("assaults"),n("power_outages"),n("visitors"),n("elevator_failures"),n("supervisor_minutes"),
            request.form.get("notes",""),now))
        report_id = cur.lastrowid
        con.commit()
        row = con.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
        con.close()
        pdf_path = make_pdf(row)
        email_ok, email_msg = send_email(pdf_path, row)
        return redirect(url_for("success", token=token, email_ok=int(email_ok), msg=email_msg))
    return render_template("report.html", sup=sup, key=key, today=datetime.now().strftime("%Y-%m-%d"))

@app.route("/success/<token>")
def success(token):
    return render_template("success.html", token=token, email_ok=request.args.get("email_ok")=="1", msg=request.args.get("msg",""))

@app.route("/pdf/<token>")
def pdf(token):
    con = db(); row = con.execute("SELECT * FROM reports WHERE token=?", (token,)).fetchone(); con.close()
    if not row: abort(404)
    path = make_pdf(row)
    return send_file(path, mimetype="application/pdf", as_attachment=True, download_name=f"report-{row['supervisor_name']}-{row['report_date']}.pdf")

@app.route("/manager")
def manager():
    password = request.args.get("password","")
    required = os.environ.get("MANAGER_PASSWORD", "123456")
    if password != required:
        return render_template("login.html")
    con = db()
    reports = con.execute("SELECT * FROM reports ORDER BY id DESC LIMIT 100").fetchall()
    totals = con.execute("""SELECT COUNT(*) c, COALESCE(SUM(assaults),0) assaults,
        COALESCE(SUM(power_outages),0) power, COALESCE(SUM(visitors),0) visitors,
        COALESCE(SUM(elevator_failures),0) elevators, COALESCE(SUM(supervisor_minutes),0) minutes FROM reports""").fetchone()
    con.close()
    return render_template("manager.html", reports=reports, totals=totals, password=password)

@app.route("/manager-login", methods=["POST"])
def manager_login():
    return redirect(url_for("manager", password=request.form.get("password","")))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
else:
    init_db()
