# نظام تقارير إدارة الأمن والسلامة

## التشغيل محليًا
pip install -r requirements.txt
python app.py

## النشر على Render
1. ارفع جميع ملفات هذا المجلد إلى GitHub.
2. في Render اختر New Web Service.
3. اختر المستودع.
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `gunicorn app:app`

## إعداد البريد
أضف Environment Variables في Render:
- SMTP_HOST
- SMTP_PORT
- SMTP_USER
- SMTP_PASSWORD
- REPORT_RECIPIENTS
- MANAGER_PASSWORD

بدون إعداد SMTP سيستمر حفظ التقرير وإنشاء PDF، لكن لن يتم إرسال البريد تلقائيًا.
