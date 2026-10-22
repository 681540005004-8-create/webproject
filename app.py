import os
import json
import uuid
import datetime
import base64
import re
import io
import numpy as np
from PIL import Image
from flask import Flask, render_template, request, jsonify, send_file, Response, session
from werkzeug.security import generate_password_hash, check_password_hash
import pypdf
import requests
ocr_engine = None
try:
    from rapidocr_onnxruntime import RapidOCR
    ocr_engine = RapidOCR()
except Exception as _ocr_init_err:
    print(f"[Notice] RapidOCR offline engine not pre-loaded: {_ocr_init_err}")
    ocr_engine = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static'),
    static_url_path='/static'
)
app.secret_key = os.environ.get('SECRET_KEY', 'taskflow-ai-cpe-secret-key-2026')

# Support Vercel / serverless environment (where root fs is read-only)
IS_VERCEL = bool(os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))
DEFAULT_DATA_FILE = os.path.join(BASE_DIR, 'data', 'db.json')

if IS_VERCEL:
    DATA_FILE = '/tmp/db.json'
    if not os.path.exists(DATA_FILE) and os.path.exists(DEFAULT_DATA_FILE):
        try:
            import shutil
            shutil.copyfile(DEFAULT_DATA_FILE, DATA_FILE)
        except Exception as _e:
            print(f"[Notice] Could not initialize /tmp/db.json: {_e}")
else:
    DATA_FILE = DEFAULT_DATA_FILE

def get_default_cpe_classes():
    return [
        {
            "id": "c1",
            "code": "CPE312",
            "name": "Computer Networks (Lecture)",
            "day": "Monday",
            "day_idx": 1,
            "start": "09:00",
            "end": "12:00",
            "room": "ENG-402",
            "instructor": "ดร. สมชาย เครือข่าย",
            "color": "indigo"
        },
        {
            "id": "c2",
            "code": "CPE312L",
            "name": "Computer Networks Lab",
            "day": "Monday",
            "day_idx": 1,
            "start": "13:00",
            "end": "16:00",
            "room": "LAB-501",
            "instructor": "อ. ปาริฉัตร มั่นคง",
            "color": "indigo"
        },
        {
            "id": "c3",
            "code": "CPE324",
            "name": "Database Systems & Design",
            "day": "Tuesday",
            "day_idx": 2,
            "start": "09:30",
            "end": "12:00",
            "room": "ENG-305",
            "instructor": "ผศ.ดร. นฤมล ฐานข้อมูล",
            "color": "sky"
        },
        {
            "id": "c4",
            "code": "CPE381",
            "name": "Technical Communication",
            "day": "Tuesday",
            "day_idx": 2,
            "start": "13:30",
            "end": "15:30",
            "room": "LIB-201",
            "instructor": "Aj. Michael Brooks",
            "color": "amber"
        },
        {
            "id": "c5",
            "code": "CPE223",
            "name": "Data Structures & Algorithms",
            "day": "Wednesday",
            "day_idx": 3,
            "start": "09:00",
            "end": "12:00",
            "room": "ENG-502",
            "instructor": "รศ.ดร. ชาญวิทย์ โค้ดดิ้ง",
            "color": "purple"
        },
        {
            "id": "c6",
            "code": "CPE342L",
            "name": "Operating Systems Lab",
            "day": "Wednesday",
            "day_idx": 3,
            "start": "14:00",
            "end": "17:00",
            "room": "LAB-404",
            "instructor": "ดร. อนันต์ ซิสเต็ม",
            "color": "emerald"
        },
        {
            "id": "c7",
            "code": "CPE491",
            "name": "Senior Project Seminar",
            "day": "Thursday",
            "day_idx": 4,
            "start": "10:00",
            "end": "12:00",
            "room": "SEMINAR-1",
            "instructor": "คณะกรรมการโครงงาน",
            "color": "rose"
        },
        {
            "id": "c8",
            "code": "CPE355",
            "name": "Software Engineering & Agile",
            "day": "Thursday",
            "day_idx": 4,
            "start": "13:00",
            "end": "16:00",
            "room": "ENG-408",
            "instructor": "อ. ธนกฤต อไจล์",
            "color": "indigo"
        },
        {
            "id": "c9",
            "code": "CPE361",
            "name": "Embedded Systems & IoT",
            "day": "Friday",
            "day_idx": 5,
            "start": "09:00",
            "end": "12:00",
            "room": "IOT-LAB",
            "instructor": "ผศ. สุรชัย ไมโคร",
            "color": "teal"
        }
    ]

def load_db():
    if not os.path.exists(DATA_FILE):
        if os.path.exists(DEFAULT_DATA_FILE):
            try:
                with open(DEFAULT_DATA_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"users": {}}
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {"users": {}}
    
    if "users" not in data:
        u = data.get('user', {})
        user_demo = {
            "id": "user_demo",
            "email": "student@cpe.eng.ac.th",
            "student_id": u.get("student_id", "65010999"),
            "password_hash": generate_password_hash("123456"),
            "name": u.get("name", "กิตติพงษ์ วิศวะคอม (ปี 3)"),
            "department": u.get("department", "Computer Engineering"),
            "faculty": u.get("faculty", "Faculty of Engineering"),
            "streak_days": u.get("streak_days", 12),
            "completed_subtasks": u.get("completed_subtasks", 53),
            "current_energy": u.get("current_energy", "high"),
            "current_mood": u.get("current_mood", "energized"),
            "burnout_score": u.get("burnout_score", 5),
            "last_checkin": u.get("last_checkin", "2026-10-21"),
            "classes": data.get("classes", get_default_cpe_classes()),
            "assignments": data.get("assignments", []),
            "checkin_history": data.get("checkin_history", [])
        }
        data = {
            "active_user_id": "user_demo",
            "users": {"user_demo": user_demo}
        }
        save_db(data)
    
    return data

def save_db(data):
    try:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Warning] Could not save db: {e}")

def get_current_user(db):
    uid = session.get('user_id')
    if uid and uid in db.get('users', {}):
        return db['users'][uid]
    if 'user_demo' in db.get('users', {}):
        return db['users']['user_demo']
    if db.get('users'):
        first_uid = list(db['users'].keys())[0]
        return db['users'][first_uid]
    return None

def calculate_burnout(user, current_energy=None, current_mood=None, sleep_hours=7.0):
    history = user.get('checkin_history', [])
    energy = current_energy or user.get('current_energy', 'medium')
    mood = current_mood or user.get('current_mood', 'focused')

    score = 30
    if energy == 'low':
        score += 25
    elif energy == 'high':
        score -= 15

    mood_penalties = {
        'exhausted': 25,
        'anxious': 20,
        'neutral': 5,
        'focused': -10,
        'energized': -20
    }
    score += mood_penalties.get(mood, 0)

    if sleep_hours < 6.0:
        score += 15
    elif sleep_hours >= 7.5:
        score -= 10

    low_days = 0
    for h in reversed(history[-5:]):
        if h.get('energy') == 'low':
            low_days += 1
        else:
            break
    if low_days >= 2:
        score += low_days * 8

    score = max(5, min(95, score))

    if score < 35:
        risk_level = "ระดับต่ำ (Safe & Healthy)"
        advice = "สุขภาพจิตและพลังงานอยู่ในเกณฑ์ยอดเยี่ยม! มีพลังโฟกัสสูง เหมาะสำหรับลุยงาน High-Cognitive Tasks เช่น เขียนโค้ดหรือวิเคราะห์ระบบ"
        color = "emerald"
    elif score < 65:
        risk_level = "ระดับปานกลาง (Moderate Load)"
        advice = "เริ่มมีความเหนื่อยล้าสะสม แนะนำให้จัดงานหนักสลับงานเบา พักสายตา 5-10 นาทีหลังจบแต่ละ Subtask เพื่อรักษาสมดุล"
        color = "amber"
    else:
        risk_level = "ระดับเฝ้าระวังหมดไฟ (High Burnout Risk)"
        advice = "⚠️ ตรวจพบสัญญาณความเครียดสะสมสูง! ระบบ TaskFlow AI แนะนำให้เลื่อนงาน High-Cognitive Tasks ออกไป และทำเพียง Subtask ง่ายๆ 1 ชิ้น หรือพักผ่อนเต็มที่ในวันนี้"
        color = "rose"

    return {
        "score": score,
        "risk_level": risk_level,
        "advice": advice,
        "color": color
    }

def csp_schedule_optimizer(classes, assignments, energy_level='medium'):
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    pending_subtasks = []
    for asg in assignments:
        for st in asg.get('subtasks', []):
            if not st.get('completed', False):
                pending_subtasks.append({
                    'asg_id': asg.get('id'),
                    'course': asg.get('course'),
                    'asg_title': asg.get('title'),
                    'deadline': asg.get('deadline'),
                    'subtask': st
                })

    pending_subtasks.sort(key=lambda x: x.get('deadline', '9999'))

    adjusted_subtasks = []
    for item in pending_subtasks:
        st = item['subtask']
        cog = st.get('cognitive_load', 'medium')
        
        if energy_level == 'low':
            if cog == 'high':
                st['scheduled_day'] = 'Saturday'
                st['scheduled_time'] = '10:00 - 10:45'
                st['adjustment_note'] = 'ย้ายจากวันนี้ไปวันเสาร์ เนื่องจากระดับพลังงานต่ำ (Low-Cognitive Mode)'
            elif cog == 'medium':
                st['scheduled_day'] = 'Friday'
                st['scheduled_time'] = '16:00 - 16:40'
                st['adjustment_note'] = 'ปรับเวลาให้ทำช่วงบ่ายของวันศุกร์'
            else:
                st['scheduled_day'] = 'Wednesday'
                st['scheduled_time'] = '19:00 - 19:30'
                st['adjustment_note'] = 'จัดให้ทำวันนี้ เพราะเป็นงานที่ไม่หนักสมอง ทำเสร็จได้ใน 30 นาที'
        elif energy_level == 'high':
            if cog == 'high':
                st['scheduled_day'] = 'Wednesday'
                st['scheduled_time'] = '18:00 - 18:45'
                st['adjustment_note'] = 'จัดคิวให้ทำวันนี้ทันที เพราะพลังงานเต็มที่ (High Focus Zone)'
            elif cog == 'medium':
                st['scheduled_day'] = 'Thursday'
                st['scheduled_time'] = '17:00 - 17:40'
                st['adjustment_note'] = 'จัดลงช่วงเย็นหลังเลิกเรียน'
            else:
                st['scheduled_day'] = 'Friday'
                st['scheduled_time'] = '14:00 - 14:30'
                st['adjustment_note'] = 'จัดลงช่วงบ่ายวันศุกร์ก่อนหยุดสุดสัปดาห์'
        else:
            if cog == 'high':
                st['scheduled_day'] = 'Thursday'
                st['scheduled_time'] = '18:00 - 18:45'
                st['adjustment_note'] = 'จัดลงวันพฤหัสบดีช่วงเย็น'
            elif cog == 'medium':
                st['scheduled_day'] = 'Wednesday'
                st['scheduled_time'] = '18:30 - 19:10'
                st['adjustment_note'] = 'จัดให้ทำวันนี้หลังพักผ่อน'
            else:
                st['scheduled_day'] = 'Friday'
                st['scheduled_time'] = '15:00 - 15:30'
                st['adjustment_note'] = 'จัดลงวันศุกร์'

        adjusted_subtasks.append(st)

    return {
        "status": "success",
        "energy_level": energy_level,
        "scheduled_count": len(adjusted_subtasks),
        "adjusted_subtasks": adjusted_subtasks
    }

def smart_deconstruct_text(title, text, course_name="CPE", gemini_api_key=None):
    if gemini_api_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_api_key}"
            prompt = f"""
            You are TaskFlow AI, an expert academic assistant for Computer Engineering students.
            Analyze this assignment instruction and break it down into 4-6 bite-sized subtasks that can be completed in 30-45 minutes each.
            Assignment Title: {title}
            Course: {course_name}
            Content: {text}

            Respond ONLY with a valid JSON object matching this schema:
            {{
              "assignment_title": "{title}",
              "course": "{course_name}",
              "deadline_recommendation": "7 days",
              "criteria_summary": "Summary of grading criteria",
              "subtasks": [
                {{
                  "title": "Subtask title in Thai",
                  "duration": 35,
                  "cognitive_load": "high | medium | low",
                  "recommended_energy": "high | medium | low",
                  "guidance": "Actionable step-by-step guidance in Thai"
                }}
              ]
            }}
            """
            resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
            if resp.status_code == 200:
                resp_json = resp.json()
                raw_reply = resp_json['candidates'][0]['content']['parts'][0]['text']
                if "```json" in raw_reply:
                    raw_reply = raw_reply.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_reply:
                    raw_reply = raw_reply.split("```")[1].split("```")[0].strip()
                return json.loads(raw_reply)
        except Exception as e:
            print("Gemini API fallback:", e)

    text_lower = (title + " " + text).lower()
    
    if any(k in text_lower for k in ['socket', 'network', 'tcp', 'udp', 'wireshark', 'packet']):
        subtasks = [
            {"title": "ศึกษา Socket Architecture & กำหนด Packet Protocol Specification", "duration": 35, "cognitive_load": "medium", "recommended_energy": "medium", "guidance": "สรุปรูปแบบ Header และ Body ของข้อความแชท วาดโฟลว์การส่งข้อมูลแบบง่าย"},
            {"title": "เขียนโค้ด Core TCP Socket Server (Bind, Listen, Accept Loop)", "duration": 45, "cognitive_load": "high", "recommended_energy": "high", "guidance": "สร้าง Server Socket ทดสอบกับโปรแกรม Telnet หรือ Netcat ให้สามารถเชื่อมต่อได้"},
            {"title": "สร้างระบบ Multi-threading หรือ Non-blocking I/O รองรับหลายไคลเอนต์", "duration": 45, "cognitive_load": "high", "recommended_energy": "high", "guidance": "ใช้ Thread หรือ Asyncio และใส่ Mutex Lock เพื่อป้องกัน Race Condition ระหว่างส่งแชท"},
            {"title": "เขียนโค้ดไคลเอนต์ CLI & ทดสอบการรับ-ส่ง Broadcast ข้อความ", "duration": 40, "cognitive_load": "medium", "recommended_energy": "medium", "guidance": "ทดสอบเปิด 3-4 Terminal พร้อมกันแล้วพิมพ์คุยกัน ตรวจสอบว่าข้อความกระจายครบทุกหน้าต่าง"},
            {"title": "ดักจับ Packet ด้วย Wireshark และบันทึกภาพ 3-Way Handshake", "duration": 30, "cognitive_load": "low", "recommended_energy": "low", "guidance": "เปิด Wireshark กรองพอร์ตแอปพลิเคชัน บันทึกภาพจังหวะ SYN, ACK และ FIN"},
            {"title": "จัดทำเล่มรายงานแล็บ สรุปผลการทดลอง และตรวจเช็คไฟล์เตรียมส่ง", "duration": 35, "cognitive_load": "low", "recommended_energy": "low", "guidance": "ตรวจความเรียบร้อยของ Readme.md โค้ดคอมเมนต์ และแปลงรายงานเป็น PDF"}
        ]
        criteria_summary = "ความถูกต้องของ TCP Protocol (40%), ความปลอดภัยของ Threads (30%), ผลวิเคราะห์ Wireshark & รายงาน (30%)"
    elif any(k in text_lower for k in ['database', 'sql', 'erd', 'normalization', '3nf', 'schema']):
        subtasks = [
            {"title": "วิเคราะห์ Business Requirements & ออกแบบ Conceptual ER Diagram", "duration": 40, "cognitive_load": "medium", "recommended_energy": "medium", "guidance": "ระบุ Entities หลัก, Attributes, และ Cardinality (1:N, M:N) ให้ครบถ้วน"},
            {"title": "ทำ Database Normalization จาก Unnormalized ถึง 3NF", "duration": 45, "cognitive_load": "high", "recommended_energy": "high", "guidance": "แยกตารางเพื่อแก้ Partial และ Transitive Functional Dependencies จดคำอธิบายแต่ละขั้น"},
            {"title": "เขียนสคริปต์ SQL DDL สร้าง Tables, Primary Keys และ Foreign Keys", "duration": 35, "cognitive_load": "medium", "recommended_energy": "medium", "guidance": "กำหนด Datatypes ให้เหมาะสม (เช่น VARCHAR, TIMESTAMP, DECIMAL) และใส่ Index บน Foreign Keys"},
            {"title": "เพิ่ม Mock Data 10-20 รายการ และทดสอบ Query ด้วย JOIN 3 ตาราง", "duration": 30, "cognitive_load": "low", "recommended_energy": "low", "guidance": "รันคำสั่ง SELECT เพื่อทดสอบว่า Relationship ถูกต้องและไม่มี Null pointer"},
            {"title": "สรุปรายงานการออกแบบและ Export รูป Diagram ส่งอาจารย์", "duration": 30, "cognitive_load": "low", "recommended_energy": "low", "guidance": "แนบไฟล์ SQL Script และบันทึกรูปภาพ ER Diagram คมชัดสูงลงในเล่มรายงาน"}
        ]
        criteria_summary = "ความสมบูรณ์ของ ER Diagram (35%), ความถูกต้องตามหลัก 3NF (35%), สคริปต์ SQL ใช้งานได้จริง (30%)"
    elif any(k in text_lower for k in ['operating', 'os', 'scheduler', 'round robin', 'process', 'thread', 'cpu']):
        subtasks = [
            {"title": "ออกแบบ Data Structure สำหรับ PCB (Process Control Block)", "duration": 35, "cognitive_load": "medium", "recommended_energy": "medium", "guidance": "สร้าง Class หรือ Struct เก็บ PID, Arrival Time, Burst Time, Remaining Time และ Priority"},
            {"title": "อิมพลีเมนต์อัลกอริทึม FCFS และ Shortest Job First (SJF)", "duration": 45, "cognitive_load": "high", "recommended_energy": "high", "guidance": "เขียนฟังก์ชันคำนวณ Ready Queue และเรียงลำดับ Process ตาม Burst Time ที่น้อยที่สุด"},
            {"title": "อิมพลีเมนต์ Round Robin พร้อม Time Quantum และ Context Switch", "duration": 45, "cognitive_load": "high", "recommended_energy": "high", "guidance": "ใช้ Circular Queue สลับ Process เมื่อครบ Quantum บันทึกจังหวะ Context Switch"},
            {"title": "เขียนฟังก์ชันพิมพ์ Gantt Chart และคำนวณ Average Waiting Time", "duration": 35, "cognitive_load": "medium", "recommended_energy": "medium", "guidance": "คำนวณ Turnaround Time และ Waiting Time พร้อมพิมพ์ Gantt Chart ใน Terminal"},
            {"title": "รันการทดลองเปรียบเทียบผลและเขียนสรุปบทวิเคราะห์", "duration": 30, "cognitive_load": "low", "recommended_energy": "low", "guidance": "เปรียบเทียบผลลัพธ์ของแต่ละอัลกอริทึมผ่านตารางและกราฟในรายงาน"}
        ]
        criteria_summary = "ความถูกต้องของอัลกอริทึม (45%), การคำนวณและแสดง Gantt Chart (30%), รายงานเปรียบเทียบผล (25%)"
    else:
        subtasks = [
            {"title": "ทำความเข้าใจโจทย์ ศึกษาเอกสารอ้างอิง และร่างขอบเขตงาน", "duration": 35, "cognitive_load": "medium", "recommended_energy": "medium", "guidance": "ไฮไลต์หัวข้อสำคัญและเกณฑ์การให้คะแนน ลิสต์เครื่องมือหรือไลบรารีที่ต้องใช้"},
            {"title": "ออกแบบโครงสร้างระบบหรือโมเดลการทำงานหลัก (Core Architecture)", "duration": 45, "cognitive_load": "high", "recommended_energy": "high", "guidance": "วาง Flowchart หรือไดอะแกรมจำลองการทำงานก่อนเริ่มลงมือจริง"},
            {"title": "ลงมือพัฒนาฟังก์ชันหลักส่วนที่ 1 และทดสอบยูนิตพื้นฐาน", "duration": 45, "cognitive_load": "high", "recommended_energy": "high", "guidance": "โฟกัสที่แกนหลักของงานให้ทำงานได้แบบ Minimal Viable Product"},
            {"title": "พัฒนาฟังก์ชันเสริมและตรวจสอบจัดการข้อผิดพลาด (Edge Cases)", "duration": 40, "cognitive_load": "medium", "recommended_energy": "medium", "guidance": "ทดสอบกรณีข้อมูลผิดพลาดและเขียนคอมเมนต์อธิบายโค้ดให้เข้าใจง่าย"},
            {"title": "ทดสอบระบบรวมทั้งหมด (Integration Test) และจับภาพหลักฐานผลการทำงาน", "duration": 30, "cognitive_load": "low", "recommended_energy": "low", "guidance": "บันทึกผลการรันโปรแกรมเพื่อนำมาประกอบในเล่มรายงาน"},
            {"title": "เรียบเรียงรายงาน สรุปผล และตรวจสอบความถูกต้องก่อนส่ง", "duration": 30, "cognitive_load": "low", "recommended_energy": "low", "guidance": "ตรวจทานความเรียบร้อยตามเกณฑ์และจัดไฟล์ส่งตามรูปแบบที่กำหนด"}
        ]
        criteria_summary = "ความถูกต้องตามสเปกโจทย์ (40%), ความสมบูรณ์ของระบบ (30%), คุณภาพรายงานและเอกสาร (30%)"

    for idx, s in enumerate(subtasks, start=1):
        s['id'] = f"sub-{uuid.uuid4().hex[:6]}"
        s['completed'] = False
        s['scheduled_day'] = "Thursday" if idx % 2 == 0 else "Wednesday"
        s['scheduled_time'] = "18:00 - 18:40"

    return {
        "assignment_title": title,
        "course": course_name,
        "deadline_recommendation": "7 วัน",
        "criteria_summary": criteria_summary,
        "subtasks": subtasks
    }

# ================= AUTHENTICATION ROUTES =================

@app.route('/api/auth/me', methods=['GET'])
def auth_me():
    db = load_db()
    uid = session.get('user_id')
    if uid and uid in db.get('users', {}):
        u = db['users'][uid]
        return jsonify({
            "logged_in": True,
            "user": {
                "id": u["id"],
                "name": u["name"],
                "email": u["email"],
                "student_id": u["student_id"],
                "department": u.get("department", "Computer Engineering"),
                "faculty": u.get("faculty", "Faculty of Engineering")
            }
        })
    demo = db.get('users', {}).get('user_demo')
    if demo:
        return jsonify({
            "logged_in": False,
            "user": {
                "id": demo["id"],
                "name": demo["name"],
                "email": demo["email"],
                "student_id": demo["student_id"],
                "department": demo.get("department", "Computer Engineering"),
                "faculty": demo.get("faculty", "Faculty of Engineering")
            }
        })
    return jsonify({"logged_in": False, "user": None})

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    data = request.json or {}
    identifier = (data.get('identifier') or '').strip().lower()
    password = data.get('password', '')

    if not identifier or not password:
        return jsonify({"status": "error", "message": "กรุณากรอกรหัสนักศึกษา/อีเมล และรหัสผ่าน"}), 400

    db = load_db()
    matched_user = None

    for u in db.get('users', {}).values():
        if u.get('email', '').lower() == identifier or u.get('student_id', '').lower() == identifier:
            matched_user = u
            break

    if not matched_user or not check_password_hash(matched_user.get('password_hash', ''), password):
        return jsonify({"status": "error", "message": "รหัสนักศึกษา/อีเมล หรือรหัสผ่านไม่ถูกต้อง"}), 401

    session['user_id'] = matched_user['id']
    return jsonify({
        "status": "success",
        "message": f"เข้าสู่ระบบสำเร็จ ยินดีต้อนรับคุณ {matched_user['name']}",
        "user": {
            "id": matched_user["id"],
            "name": matched_user["name"],
            "email": matched_user["email"],
            "student_id": matched_user["student_id"],
            "department": matched_user.get("department", "Computer Engineering")
        }
    })

@app.route('/api/auth/register', methods=['POST'])
def auth_register():
    data = request.json or {}
    name = (data.get('name') or '').strip()
    student_id = (data.get('student_id') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password', '')
    department = (data.get('department') or 'Computer Engineering').strip()
    prefill_classes = data.get('prefill_classes', True)

    if not name or not student_id or not email or not password:
        return jsonify({"status": "error", "message": "กรุณากรอกข้อมูลให้ครบทุกช่อง"}), 400

    db = load_db()
    for u in db.get('users', {}).values():
        if u.get('email', '').lower() == email:
            return jsonify({"status": "error", "message": "อีเมลนี้มีผู้ใช้งานแล้ว"}), 400
        if u.get('student_id', '').lower() == student_id.lower():
            return jsonify({"status": "error", "message": "รหัสนักศึกษานี้มีผู้ใช้งานแล้ว"}), 400

    new_uid = f"user_{uuid.uuid4().hex[:8]}"
    initial_classes = get_default_cpe_classes() if prefill_classes else []

    new_user = {
        "id": new_uid,
        "name": name,
        "student_id": student_id,
        "email": email,
        "password_hash": generate_password_hash(password),
        "department": department,
        "faculty": "Faculty of Engineering",
        "streak_days": 1,
        "completed_subtasks": 0,
        "current_energy": "medium",
        "current_mood": "focused",
        "burnout_score": 25,
        "last_checkin": datetime.date.today().isoformat(),
        "classes": initial_classes,
        "assignments": [],
        "checkin_history": [
            {
                "date": datetime.date.today().isoformat(),
                "day": "วันนี้",
                "energy": "medium",
                "mood": "focused",
                "stress": 25,
                "sleep_hours": 7.5,
                "tasks_done": 0
            }
        ]
    }

    db.setdefault('users', {})[new_uid] = new_user
    save_db(db)
    session['user_id'] = new_uid

    return jsonify({
        "status": "success",
        "message": "สมัครสมาชิกและเข้าสู่ระบบสำเร็จ!",
        "user": {
            "id": new_user["id"],
            "name": new_user["name"],
            "email": new_user["email"],
            "student_id": new_user["student_id"],
            "department": new_user["department"]
        }
    })

@app.route('/api/auth/demo', methods=['POST'])
def auth_demo():
    db = load_db()
    session['user_id'] = 'user_demo'
    u = db.get('users', {}).get('user_demo')
    return jsonify({
        "status": "success",
        "message": "เข้าสู่ระบบด้วยบัญชีตัวอย่างสำเร็จ!",
        "user": {
            "id": u["id"],
            "name": u["name"],
            "email": u["email"],
            "student_id": u["student_id"],
            "department": u.get("department", "Computer Engineering")
        }
    })

@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    session.pop('user_id', None)
    return jsonify({"status": "success", "message": "ออกจากระบบเรียบร้อยแล้ว"})

# ================= CUSTOM CLASS SCHEDULE ROUTES =================

@app.route('/api/classes/add', methods=['POST'])
def add_custom_class():
    data = request.json or {}
    code = (data.get('code') or '').strip().upper()
    name = (data.get('name') or '').strip()
    day = data.get('day', 'Monday')
    start = data.get('start', '09:00').strip()
    end = data.get('end', '12:00').strip()
    room = (data.get('room') or 'ENG Lab').strip()
    instructor = (data.get('instructor') or 'อาจารย์ผู้สอน').strip()
    color = data.get('color', 'indigo')

    if not code or not name or not start or not end:
        return jsonify({"status": "error", "message": "กรุณากรอกรหัสวิชา ชื่อวิชา และเวลาเรียนให้ครบถ้วน"}), 400

    try:
        sh, sm = [int(p) for p in start.split(':')]
        eh, em = [int(p) for p in end.split(':')]
        if (sh * 60 + sm) >= (eh * 60 + em):
            return jsonify({"status": "error", "message": "เวลาสิ้นสุดต้องมากกว่าเวลาเริ่มต้น"}), 400
    except Exception:
        return jsonify({"status": "error", "message": "รูปแบบเวลาไม่ถูกต้อง (ต้องเป็น HH:MM)"}), 400

    day_idx_map = {
        "Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4,
        "Friday": 5, "Saturday": 6, "Sunday": 7
    }

    db = load_db()
    user = get_current_user(db)
    if not user:
        return jsonify({"status": "error", "message": "ไม่พบข้อมูลผู้ใช้"}), 401

    new_class = {
        "id": f"c_{uuid.uuid4().hex[:6]}",
        "code": code,
        "name": name,
        "day": day,
        "day_idx": day_idx_map.get(day, 1),
        "start": start,
        "end": end,
        "room": room,
        "instructor": instructor,
        "color": color
    }

    user.setdefault('classes', []).append(new_class)
    csp_schedule_optimizer(user['classes'], user.get('assignments', []), user.get('current_energy', 'medium'))
    save_db(db)
    
    return jsonify({
        "status": "success",
        "message": f"เพิ่มวิชา {code} {name} ในตารางเรียนเรียบร้อยแล้ว",
        "class": new_class,
        "classes": user['classes']
    })

@app.route('/api/classes/<class_id>', methods=['DELETE'])
def delete_custom_class(class_id):
    db = load_db()
    user = get_current_user(db)
    if not user:
        return jsonify({"status": "error", "message": "ไม่พบข้อมูลผู้ใช้"}), 401

    classes = user.get('classes', [])
    initial_len = len(classes)
    user['classes'] = [c for c in classes if c.get('id') != class_id]

    if len(user['classes']) == initial_len:
        return jsonify({"status": "error", "message": "ไม่พบรหัสวิชานี้ในตารางเรียน"}), 404

    csp_schedule_optimizer(user['classes'], user.get('assignments', []), user.get('current_energy', 'medium'))
    save_db(db)
    return jsonify({
        "status": "success",
        "message": "ลบวิชาเรียนออกจากตารางเรียบร้อยแล้ว",
        "classes": user['classes']
    })

@app.route('/api/classes/reset-defaults', methods=['POST'])
def reset_default_classes():
    db = load_db()
    user = get_current_user(db)
    if not user:
        return jsonify({"status": "error", "message": "ไม่พบข้อมูลผู้ใช้"}), 401

    user['classes'] = get_default_cpe_classes()
    csp_schedule_optimizer(user['classes'], user.get('assignments', []), user.get('current_energy', 'medium'))
    save_db(db)
    return jsonify({
        "status": "success",
        "message": "รีเซ็ตตารางเรียนวิศวะคอมกลับเป็นค่าเริ่มต้นเรียบร้อยแล้ว",
        "classes": user['classes']
    })

# ================= SCHEDULE PARSER & UPLOAD TIMETABLE =================

SCHEDULE_DAY_MAP = {
    'พฤหัสบดี': 'Thursday', 'พฤหัส': 'Thursday', 'พฤ.': 'Thursday', 'พฤ': 'Thursday',
    'จันทร์': 'Monday', 'จ.': 'Monday', 'จ': 'Monday',
    'อังคาร': 'Tuesday', 'อ.': 'Tuesday', 'อ': 'Tuesday',
    'พุธ': 'Wednesday', 'พ.': 'Wednesday', 'พ': 'Wednesday',
    'ศุกร์': 'Friday', 'ศ.': 'Friday', 'ศ': 'Friday',
    'เสาร์': 'Saturday', 'ส.': 'Saturday', 'ส': 'Saturday',
    'อาทิตย์': 'Sunday', 'อา.': 'Sunday', 'อา': 'Sunday',
    'thursday': 'Thursday', 'wednesday': 'Wednesday', 'tuesday': 'Tuesday', 'monday': 'Monday',
    'friday': 'Friday', 'saturday': 'Saturday', 'sunday': 'Sunday',
    'thu': 'Thursday', 'wed': 'Wednesday', 'tue': 'Tuesday', 'mon': 'Monday',
    'fri': 'Friday', 'sat': 'Saturday', 'sun': 'Sunday',
    'th': 'Thursday', 'we': 'Wednesday', 'tu': 'Tuesday', 'mo': 'Monday',
    'fr': 'Friday', 'sa': 'Saturday', 'su': 'Sunday'
}

SCHEDULE_COLORS = ['indigo', 'sky', 'emerald', 'amber', 'purple', 'rose', 'teal']

def parse_schedule_text(text):
    """
    Parses unstructured text from PDF, OCR, or SIS portal copy-paste into structured class list.
    Supports single-line format, multi-line table formats, Thai and English abbreviations.
    """
    if not text:
        return []

    lines = [l.strip() for l in text.split('\n') if l.strip()]
    extracted = []
    current_day = 'Monday'

    for i, line in enumerate(lines):
        # Update current_day if line is a day header
        for k, v in SCHEDULE_DAY_MAP.items():
            if re.search(r'^(วัน)?' + re.escape(k) + r'(:|\s|$)', line, re.IGNORECASE):
                current_day = v
                break

        time_match = re.search(r'(\d{1,2}[:.]\d{2})\s*[-–~ถึงto]\s*(\d{1,2}[:.]\d{2})', line)
        if time_match:
            s_time = time_match.group(1).replace('.', ':')
            e_time = time_match.group(2).replace('.', ':')
            if len(s_time.split(':')[0]) == 1: s_time = '0' + s_time
            if len(e_time.split(':')[0]) == 1: e_time = '0' + e_time

            prev_lines = lines[max(0, i-3):i]
            next_lines = lines[i+1:min(len(lines), i+6)]

            # 1. Day determination
            line_day = current_day
            for pl in reversed(prev_lines):
                for k, v in SCHEDULE_DAY_MAP.items():
                    if re.search(r'(^|[\s,.\t])' + re.escape(k) + r'([\s,.\t:]|$)', pl, re.IGNORECASE):
                        line_day = v
                        break
            for k, v in SCHEDULE_DAY_MAP.items():
                if re.search(r'(^|[\s,.\t])' + re.escape(k) + r'([\s,.\t:]|$)', line, re.IGNORECASE):
                    line_day = v
                    break

            # 2. Course Code determination
            code = None
            code_pattern = r'([A-Za-z]{2,5}\s*\d{3,4}[A-Za-z]?|\b\d{6,8}\b)'
            code_match = re.search(code_pattern, line)
            if code_match:
                code = code_match.group(1).replace(' ', '').upper()
            else:
                for nl in next_lines:
                    cm = re.search(code_pattern, nl)
                    if cm:
                        code = cm.group(1).replace(' ', '').upper()
                        break
                if not code:
                    for pl in reversed(prev_lines):
                        cm = re.search(code_pattern, pl)
                        if cm:
                            code = cm.group(1).replace(' ', '').upper()
                            break
            if not code:
                code = f"COURSE{len(extracted)+1}"

            # 3. Room determination
            room = None
            room_pattern = r'(ENG[-\s]?\d+|LAB[-\s]?\d+|ROOM[-\s]?\d+|LIB[-\s]?\d+|IOT[-\s]?LAB|SEMINAR[-\s]?\d+|ห้อง\s*[\w\d]+|\b\d{3,4}\b|Online|Zoom)'
            rm = re.search(room_pattern, line, re.IGNORECASE)
            if rm:
                room = rm.group(1).strip()
            else:
                for nl in next_lines:
                    rm = re.search(room_pattern, nl, re.IGNORECASE)
                    if rm:
                        room = rm.group(1).strip()
                        break
            if not room:
                room = 'ห้องเรียน'

            # 4. Name determination
            name = ''
            temp = line
            temp = re.sub(r'(\d{1,2}[:.]\d{2})\s*[-–~ถึงto]\s*(\d{1,2}[:.]\d{2})', '', temp)
            if code_match:
                temp = temp.replace(code_match.group(0), '')
            for k in SCHEDULE_DAY_MAP.keys():
                temp = re.sub(r'(วัน)?' + re.escape(k), '', temp, flags=re.IGNORECASE)
            temp = re.sub(r'\d\(\d+-\d+-\d+\)', '', temp)
            temp = re.sub(r'(น\.|ห้อง|Room|Online|Zoom|[:|\-,])', ' ', temp, flags=re.IGNORECASE)
            if rm and room != 'ห้องเรียน':
                temp = temp.replace(room, '')
            clean_same_line = re.sub(r'\s+', ' ', temp).strip()

            if len(clean_same_line) >= 3:
                name = clean_same_line
            else:
                for nl in next_lines:
                    if code and (code in nl.replace(' ', '') or nl.replace(' ', '').startswith(code[:3])):
                        continue
                    if room and room in nl:
                        continue
                    if re.search(r'(\d{1,2}[:.]\d{2})', nl):
                        break
                    if any(k in nl.lower() for k in SCHEDULE_DAY_MAP.keys()):
                        continue
                    if re.search(r'^(Dr\.|Aj\.|ผศ\.|รศ\.|อ\.|อาจารย์|Committee)', nl):
                        continue
                    if len(nl) >= 3:
                        name = nl
                        break
            if not name:
                name = f'วิชา {code}'

            extracted.append({
                'id': f'c_up_{uuid.uuid4().hex[:6]}',
                'code': code,
                'name': name,
                'day': line_day,
                'start': s_time,
                'end': e_time,
                'room': room,
                'instructor': 'อาจารย์ผู้สอน',
                'color': SCHEDULE_COLORS[len(extracted) % len(SCHEDULE_COLORS)]
            })

    return extracted


def extract_classes_from_image_bytes(img_bytes):
    """
    Extracts university course schedule directly from image bytes using RapidOCR ONNX.
    Supports both grid timetables (column/row headers) and list/table views.
    """
    global ocr_engine
    if ocr_engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            ocr_engine = RapidOCR()
        except Exception as e:
            print("RapidOCR unavailable in this environment:", e)
            return []

    try:
        img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        img_np = np.array(img)
        result, _ = ocr_engine(img_np)
    except Exception as e:
        print("RapidOCR image read exception:", e)
        return []

    if not result:
        return []

    # Clean text in each box: fix split codes like 'C PE381' -> 'CPE381', 'CPE 312' -> 'CPE312'
    cleaned_boxes = []
    for box, text, score in result:
        t = re.sub(r'\b([A-Za-z]{1,2})\s+([A-Za-z]{1,3}\d{3,4})\b', r'\1\2', text)
        t = re.sub(r'\b([A-Za-z]{2,5})\s+(\d{3,4}[A-Za-z]?)\b', r'\1\2', t)
        t = re.sub(r'\b(\d{3})\s+(\d{3,4})\b', r'\1\2', t)
        cx = (box[0][0] + box[2][0]) / 2
        cy = (box[0][1] + box[2][1]) / 2
        cleaned_boxes.append({'box': box, 'text': t, 'cx': cx, 'cy': cy})

    # 1. Check for day headers (Grid Timetable Detection)
    day_headers = []
    for item in cleaned_boxes:
        clean = re.sub(r'[^a-zA-Z\u0E00-\u0E7F]', '', item['text']).lower()
        for k, v in SCHEDULE_DAY_MAP.items():
            k_clean = re.sub(r'[^a-zA-Z\u0E00-\u0E7F]', '', k).lower()
            if k_clean and (clean == k_clean or (len(k_clean) >= 3 and clean.startswith(k_clean))):
                day_headers.append({'day': v, 'cx': item['cx'], 'cy': item['cy']})
                break

    distinct_days = set(d['day'] for d in day_headers)
    extracted = []

    # If at least 2 distinct days found as headers along X axis (Grid table where columns are days)
    if len(distinct_days) >= 2:
        columns = {d['day']: [] for d in day_headers}
        min_header_y = min(d['cy'] for d in day_headers)

        for item in cleaned_boxes:
            cx, cy, text = item['cx'], item['cy'], item['text']
            if cy < min_header_y - 20:
                continue
            if any(abs(cx - d['cx']) < 35 and abs(cy - d['cy']) < 25 for d in day_headers):
                continue
            closest = min(day_headers, key=lambda d: abs(cx - d['cx']))
            columns[closest['day']].append((cy, text))

        for day, col_items in columns.items():
            col_items.sort(key=lambda x: x[0])
            col_classes = parse_column_ocr_blocks(col_items, day)
            extracted.extend(col_classes)

    # 2. If grid parsing found nothing, try sequential line parser
    if len(extracted) == 0:
        cleaned_boxes.sort(key=lambda b: (round(b['cy'] / 25) * 25, b['cx']))
        flat_lines = [b['text'] for b in cleaned_boxes]
        extracted = parse_schedule_text("\n".join(flat_lines))

    # 3. Final safety net: if still 0 classes, extract any course codes found in image
    if len(extracted) == 0:
        seen_codes = set()
        code_pat = r'([A-Za-z]{2,5}\d{3,4}[A-Za-z]?|\b\d{6,8}\b)'
        for item in cleaned_boxes:
            cm = re.search(code_pat, item['text'])
            if cm:
                c_code = cm.group(1).upper()
                if c_code not in seen_codes:
                    seen_codes.add(c_code)
                    rem_name = item['text'].replace(cm.group(0), '')
                    rem_name = re.sub(r'[:|\-,()]', ' ', rem_name).strip()
                    extracted.append({
                        'id': f'c_up_{uuid.uuid4().hex[:6]}',
                        'code': c_code,
                        'name': rem_name if len(rem_name) >= 3 else f"วิชา {c_code}",
                        'day': 'Monday',
                        'start': '09:00',
                        'end': '12:00',
                        'room': 'ห้องเรียน',
                        'instructor': 'อาจารย์ผู้สอน',
                        'color': SCHEDULE_COLORS[len(extracted) % len(SCHEDULE_COLORS)]
                    })

    return extracted


def parse_column_ocr_blocks(col_items, day):
    """
    Parses sequential text lines under a specific day column in a grid timetable.
    """
    code_pat = r'([A-Za-z]{2,5}\d{3,4}[A-Za-z]?|\b\d{6,8}\b)'
    room_pat = r'(ENG[-\s]?\d+|LAB[-\s]?\d+|ROOM[-\s]?\d+|LIB[-\s]?\d+|IOT[-\s]?LAB|SEMINAR[-\s]?\d+|ห้อง\s*[\w\d]+|\b\d{3,4}\b|Online|Zoom)'

    # Segment into course blocks starting with code
    blocks = []
    current_block = []
    for cy, text in col_items:
        if re.search(code_pat, text) and current_block:
            blocks.append(current_block)
            current_block = [(cy, text)]
        else:
            current_block.append((cy, text))
    if current_block:
        blocks.append(current_block)

    classes = []
    for block_idx, block in enumerate(blocks):
        block_text = " ".join(t[1] for t in block)
        cm = re.search(code_pat, block_text)
        if not cm:
            continue
        code = cm.group(1).upper()

        # Find time
        s_time, e_time = None, None
        for cy, text in block:
            tm = re.search(r'(\d{1,2}[:.]\d{2})\s*[-–~ถึงto]\s*(\d{1,2}[:.]\d{2})', text)
            if tm:
                s_time = tm.group(1).replace('.', ':')
                e_time = tm.group(2).replace('.', ':')
                if len(s_time.split(':')[0]) == 1: s_time = '0' + s_time
                if len(e_time.split(':')[0]) == 1: e_time = '0' + e_time
                break

        # If no explicit time inside block, assign sensible default based on vertical position
        if not s_time or not e_time:
            first_cy = block[0][0]
            if first_cy < 220:
                s_time, e_time = "09:00", "12:00"
            elif first_cy < 350:
                s_time, e_time = "13:00", "16:00"
            else:
                s_time, e_time = "16:30", "19:30"

        # Find room
        room = 'ห้องเรียน'
        for cy, text in block:
            rm = re.search(room_pat, text, re.IGNORECASE)
            if rm:
                room = rm.group(1).strip()
                break

        # Find name
        name = ''
        for cy, text in block:
            temp = text
            if code in temp:
                temp = temp.replace(code, '')
            temp = re.sub(r'(\d{1,2}[:.]\d{2})\s*[-–~ถึงto]\s*(\d{1,2}[:.]\d{2})', '', temp)
            if room != 'ห้องเรียน' and room in temp:
                temp = temp.replace(room, '')
            temp = re.sub(r'[:|\-,()]', ' ', temp).strip()
            if len(temp) >= 2 and not name:
                name = temp

        if not name:
            name = f"วิชา {code}"

        classes.append({
            'id': f'c_up_{uuid.uuid4().hex[:6]}',
            'code': code,
            'name': name,
            'day': day,
            'start': s_time,
            'end': e_time,
            'room': room,
            'instructor': 'อาจารย์ผู้สอน',
            'color': SCHEDULE_COLORS[len(classes) % len(SCHEDULE_COLORS)]
        })

    return classes


@app.route('/api/classes/upload-timetable', methods=['POST'])
def upload_timetable_file():
    """
    Extracts classes from an uploaded timetable image, PDF document, or pasted SIS text.
    Uses RapidOCR locally on server for any image, or Gemini Vision if key provided.
    """
    api_key = request.form.get('api_key', '').strip()
    raw_text = request.form.get('raw_text', '').strip()

    # 1. Direct text parse (from SIS Paste Tab)
    if raw_text:
        parsed = parse_schedule_text(raw_text)
        if parsed:
            return jsonify({
                "status": "success",
                "source": "SIS Portal Text Parser",
                "classes": parsed
            })

    # 2. File upload handling
    if 'file' in request.files:
        file = request.files['file']
        if file.filename != '':
            fname = file.filename.lower()
            file_bytes = file.read()
            
            # PDF Document
            if fname.endswith('.pdf'):
                try:
                    pdf_reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                    extracted = [p.extract_text() or '' for p in pdf_reader.pages]
                    pdf_text = "\n".join(extracted)
                    parsed = parse_schedule_text(pdf_text)
                    if parsed:
                        return jsonify({
                            "status": "success",
                            "source": "PDF Timetable Parser",
                            "classes": parsed
                        })
                except Exception as e:
                    print("PDF parse error:", e)

            # Plain Text Document
            elif fname.endswith('.txt'):
                txt_content = file_bytes.decode('utf-8', errors='ignore')
                parsed = parse_schedule_text(txt_content)
                if parsed:
                    return jsonify({
                        "status": "success",
                        "source": "Text File Parser",
                        "classes": parsed
                    })

            # Image (PNG, JPG, JPEG, WEBP, BMP)
            elif any(fname.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.bmp']):
                # 2a. If user supplied Gemini API key, try Gemini Vision first
                if api_key:
                    try:
                        image_mime = "image/png" if fname.endswith('.png') else "image/jpeg"
                        image_base64 = base64.b64encode(file_bytes).decode('utf-8')
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
                        prompt = """
                        Analyze this university timetable/schedule image.
                        Extract all scheduled classes into a JSON array of objects with the exact schema:
                        [
                          {
                            "code": "CPE312",
                            "name": "Course Title",
                            "day": "Monday | Tuesday | Wednesday | Thursday | Friday | Saturday | Sunday",
                            "start": "09:00",
                            "end": "12:00",
                            "room": "Room or Online",
                            "instructor": "Instructor name or TBA",
                            "color": "indigo | sky | emerald | amber | purple | rose | teal"
                          }
                        ]
                        Output ONLY valid JSON.
                        """
                        payload = {
                            "contents": [{
                                "parts": [
                                    {"text": prompt},
                                    {"inline_data": {"mime_type": image_mime, "data": image_base64}}
                                ]
                            }]
                        }
                        resp = requests.post(url, json=payload, timeout=15)
                        if resp.status_code == 200:
                            resp_json = resp.json()
                            raw_reply = resp_json['candidates'][0]['content']['parts'][0]['text']
                            if "```json" in raw_reply:
                                raw_reply = raw_reply.split("```json")[1].split("```")[0].strip()
                            elif "```" in raw_reply:
                                raw_reply = raw_reply.split("```")[1].split("```")[0].strip()
                            extracted_list = json.loads(raw_reply)
                            for idx, c in enumerate(extracted_list):
                                c['id'] = f"c_up_{uuid.uuid4().hex[:6]}"
                                if 'color' not in c or not c['color']:
                                    c['color'] = SCHEDULE_COLORS[idx % len(SCHEDULE_COLORS)]
                            return jsonify({
                                "status": "success",
                                "source": "Gemini 1.5 Flash Vision AI",
                                "classes": extracted_list
                            })
                    except Exception as e:
                        print("Gemini Vision Timetable failed:", e)

                # 2b. Server-Side RapidOCR (Fast, Offline, Accurate)
                try:
                    ocr_classes = extract_classes_from_image_bytes(file_bytes)
                    if ocr_classes:
                        return jsonify({
                            "status": "success",
                            "source": "Server-Side RapidOCR Vision",
                            "classes": ocr_classes
                        })
                except Exception as e:
                    print("RapidOCR processing exception:", e)

    # 3. If nothing was extracted, return error with clear instruction
    return jsonify({
        "status": "error",
        "message": "ไม่สามารถตรวจจับรายวิชาได้โดยอัตโนมัติ กรุณาลองใช้แท็บ 'วางข้อความจากเว็บลงทะเบียน' เพื่อวางตารางเรียนโดยตรง หรือตรวจสอบว่ารูปภาพมีความคมชัด"
    }), 400

@app.route('/api/classes/batch-save', methods=['POST'])
def batch_save_classes():
    """
    Saves a batch of extracted classes into the current user's timetable.
    """
    data = request.json or {}
    new_classes = data.get('classes', [])
    replace_all = data.get('replace_all', True)

    db = load_db()
    user = get_current_user(db)
    if not user:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    if replace_all:
        user['classes'] = new_classes
    else:
        user.setdefault('classes', []).extend(new_classes)

    csp_schedule_optimizer(user['classes'], user.get('assignments', []), user.get('current_energy', 'medium'))
    save_db(db)

    return jsonify({
        "status": "success",
        "message": f"บันทึกรายวิชา {len(new_classes)} รายการลงในตารางเรียนเรียบร้อยแล้ว!",
        "classes": user['classes']
    })

# ================= APP WORKSPACE DATA ROUTES =================

@app.route('/')
@app.route('/index')
@app.route('/api/index')
def index():
    return render_template('index.html')

@app.route('/api/data', methods=['GET'])
def get_data():
    db = load_db()
    user = get_current_user(db)
    if not user:
        return jsonify({"error": "No user"}), 404
        
    burnout = calculate_burnout(user)
    
    return jsonify({
        "user": {
            "id": user.get("id"),
            "name": user.get("name"),
            "email": user.get("email"),
            "student_id": user.get("student_id"),
            "department": user.get("department"),
            "faculty": user.get("faculty"),
            "streak_days": user.get("streak_days", 1),
            "completed_subtasks": user.get("completed_subtasks", 0),
            "current_energy": user.get("current_energy", "medium"),
            "current_mood": user.get("current_mood", "focused"),
            "burnout_score": burnout["score"],
            "last_checkin": user.get("last_checkin", "")
        },
        "classes": user.get("classes", []),
        "assignments": user.get("assignments", []),
        "checkin_history": user.get("checkin_history", []),
        "burnout_indicators": burnout,
        "is_authenticated": bool(session.get('user_id'))
    })

@app.route('/api/checkin', methods=['POST'])
def handle_checkin():
    data = request.json or {}
    energy = data.get('energy', 'medium')
    mood = data.get('mood', 'focused')
    sleep = float(data.get('sleep_hours', 7.0))
    notes = data.get('notes', '')

    db = load_db()
    user = get_current_user(db)
    if not user:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    today_str = datetime.date.today().isoformat()
    day_thai = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"][datetime.date.today().weekday()]

    user['current_energy'] = energy
    user['current_mood'] = mood
    user['last_checkin'] = today_str

    burnout = calculate_burnout(user, energy, mood, sleep)
    user['burnout_score'] = burnout['score']

    user.setdefault('checkin_history', []).append({
        "date": today_str,
        "day": f"{day_thai} (วันนี้)",
        "energy": energy,
        "mood": mood,
        "stress": burnout['score'],
        "sleep_hours": sleep,
        "notes": notes,
        "tasks_done": 0
    })

    adjustment_result = csp_schedule_optimizer(user.get('classes', []), user.get('assignments', []), energy)
    save_db(db)

    return jsonify({
        "status": "success",
        "burnout": burnout,
        "user": user,
        "adjustment": adjustment_result
    })

@app.route('/api/upload-assignment', methods=['POST'])
def upload_assignment():
    title = request.form.get('title', 'Computer Engineering Assignment')
    course = request.form.get('course', 'CPE Core Course')
    deadline = request.form.get('deadline', '2026-10-31 23:59')
    api_key = request.form.get('api_key', '').strip()
    raw_text = request.form.get('raw_text', '')

    if 'file' in request.files:
        file = request.files['file']
        if file.filename != '':
            if file.filename.lower().endswith('.pdf'):
                try:
                    pdf_reader = pypdf.PdfReader(file.stream)
                    extracted_pages = []
                    for page in pdf_reader.pages:
                        extracted_pages.append(page.extract_text() or '')
                    raw_text = "\n".join(extracted_pages)
                except Exception as e:
                    raw_text = f"Error reading PDF: {e}"
            else:
                raw_text = file.read().decode('utf-8', errors='ignore')

    if not raw_text.strip():
        raw_text = "โปรเจกต์งานวิศวกรรมคอมพิวเตอร์ ออกแบบและพัฒนาระบบตามที่ได้รับมอบหมาย"

    deconstruction = smart_deconstruct_text(title, raw_text, course, gemini_api_key=api_key or None)

    db = load_db()
    user = get_current_user(db)
    if not user:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    new_asg = {
        "id": f"asg-{uuid.uuid4().hex[:6]}",
        "course": course,
        "title": title,
        "source_file": "Uploaded Document",
        "deadline": deadline,
        "days_left": 6,
        "raw_text": raw_text[:300] + "...",
        "criteria": deconstruction.get('criteria_summary', 'เกณฑ์มาตรฐาน'),
        "status": "in_progress",
        "subtasks": deconstruction.get('subtasks', [])
    }
    user.setdefault('assignments', []).append(new_asg)
    
    csp_schedule_optimizer(user.get('classes', []), user['assignments'], user.get('current_energy', 'medium'))
    save_db(db)

    return jsonify({
        "status": "success",
        "assignment": new_asg
    })

@app.route('/api/tasks/toggle', methods=['POST'])
def toggle_task():
    data = request.json or {}
    subtask_id = data.get('subtask_id')
    completed = data.get('completed', True)

    db = load_db()
    user = get_current_user(db)
    if not user:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    found = False
    for asg in user.get('assignments', []):
        for st in asg.get('subtasks', []):
            if st.get('id') == subtask_id:
                st['completed'] = completed
                found = True
                break
        if found:
            break

    if found and completed:
        user['completed_subtasks'] = user.get('completed_subtasks', 0) + 1
        user['burnout_score'] = max(5, user.get('burnout_score', 28) - 3)
    elif found and not completed:
        user['completed_subtasks'] = max(0, user.get('completed_subtasks', 1) - 1)
    
    save_db(db)
    return jsonify({"status": "success", "user": user})

@app.route('/api/schedule/solve', methods=['POST'])
def solve_schedule():
    data = request.json or {}
    energy = data.get('energy', 'medium')
    db = load_db()
    user = get_current_user(db)
    if not user:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    res = csp_schedule_optimizer(user.get('classes', []), user.get('assignments', []), energy)
    save_db(db)
    return jsonify(res)

@app.route('/api/export/calendar', methods=['GET'])
def export_calendar():
    db = load_db()
    user = get_current_user(db)
    if not user:
        return "User not found", 404

    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//TaskFlow AI//Computer Engineering Timetable//TH",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:TaskFlow AI - {user.get('name', 'CE Schedule')}"
    ]

    day_offsets = {
        "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
        "Friday": 4, "Saturday": 5, "Sunday": 6
    }
    today = datetime.date.today()
    start_of_week = today - datetime.timedelta(days=today.weekday())

    for c in user.get('classes', []):
        day_name = c.get('day', 'Monday')
        offset = day_offsets.get(day_name, 0)
        target_date = start_of_week + datetime.timedelta(days=offset)
        
        s_h, s_m = [int(x) for x in c['start'].split(':')]
        e_h, e_m = [int(x) for x in c['end'].split(':')]

        dt_start = f"{target_date.strftime('%Y%m%d')}T{s_h:02d}{s_m:02d}00"
        dt_end = f"{target_date.strftime('%Y%m%d')}T{e_h:02d}{e_m:02d}00"

        ics_lines.extend([
            "BEGIN:VEVENT",
            f"UID:class-{c['id']}-{target_date}@taskflow.ai",
            f"DTSTAMP:{today.strftime('%Y%m%d')}T000000Z",
            f"DTSTART:{dt_start}",
            f"DTEND:{dt_end}",
            f"SUMMARY:[CE Class] {c['code']} {c['name']}",
            f"LOCATION:{c.get('room', 'ENG Lab')}",
            f"DESCRIPTION:Instructor: {c.get('instructor', 'CE Dept')}",
            "STATUS:CONFIRMED",
            "END:VEVENT"
        ])

    for asg in user.get('assignments', []):
        for st in asg.get('subtasks', []):
            if not st.get('completed', False):
                day_name = st.get('scheduled_day', 'Wednesday')
                offset = day_offsets.get(day_name, 2)
                target_date = start_of_week + datetime.timedelta(days=offset)
                
                time_range = st.get('scheduled_time', '18:00 - 18:45').split(' - ')
                s_h, s_m = [int(x) for x in time_range[0].split(':')]
                e_h, e_m = [int(x) for x in time_range[1].split(':')]

                dt_start = f"{target_date.strftime('%Y%m%d')}T{s_h:02d}{s_m:02d}00"
                dt_end = f"{target_date.strftime('%Y%m%d')}T{e_h:02d}{e_m:02d}00"

                ics_lines.extend([
                    "BEGIN:VEVENT",
                    f"UID:subtask-{st['id']}-{target_date}@taskflow.ai",
                    f"DTSTAMP:{today.strftime('%Y%m%d')}T000000Z",
                    f"DTSTART:{dt_start}",
                    f"DTEND:{dt_end}",
                    f"SUMMARY:⚡ TaskFlow AI: {st['title']}",
                    f"DESCRIPTION:Cognitive Load: {st.get('cognitive_load')}\\nDuration: {st.get('duration')} min\\nGuidance: {st.get('guidance')}",
                    "STATUS:CONFIRMED",
                    "END:VEVENT"
                ])

    ics_lines.append("END:VCALENDAR")
    ics_content = "\r\n".join(ics_lines)

    return Response(
        ics_content,
        mimetype="text/calendar",
        headers={"Content-Disposition": "attachment;filename=taskflow_schedule.ics"}
    )

if __name__ == '__main__':
    print("TaskFlow AI Server running at http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
