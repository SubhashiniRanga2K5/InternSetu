from flask import Flask, render_template, request, jsonify
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from bson import ObjectId

app = Flask(__name__)

# ── CONFIG ──────────────────────────────────────────────────
import os
app.config["MONGO_URI"] = os.environ.get("MONGO_URI", "mongodb+srv://subhashiniranga16_db_user:subhashini2k5@cluster0.yyy3eyj.mongodb.net/internsetu?appName=Cluster0")
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "internsetu_secret_2026")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = False

mongo = PyMongo(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)

def fix_id(doc):
    if doc and '_id' in doc:
        doc['_id'] = str(doc['_id'])
    return doc

# ── PAGES ───────────────────────────────────────────────────
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/register')
def register_page():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# ── AUTH ────────────────────────────────────────────────────
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    college = data.get('college', '')
    domain = data.get('domain', '')
    skills = data.get('skills', [])

    if not all([name, email, password]):
        return jsonify({'message': 'All fields required'}), 400
    if len(password) < 6:
        return jsonify({'message': 'Password must be at least 6 characters'}), 400
    if mongo.db.users.find_one({'email': email}):
        return jsonify({'message': 'Email already registered'}), 409

    hashed = bcrypt.generate_password_hash(password).decode('utf-8')
    mongo.db.users.insert_one({
        'name': name, 'email': email, 'password': hashed,
        'college': college, 'domain': domain, 'skills': skills,
        'bookmarks': [], 'applications': []
    })
    return jsonify({'message': 'Registered successfully!'}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    user = mongo.db.users.find_one({'email': email})
    if not user or not bcrypt.check_password_hash(user['password'], password):
        return jsonify({'message': 'Invalid email or password'}), 401
    token = create_access_token(identity=str(user['_id']))
    return jsonify({
        'token': token, 'name': user['name'],
        'email': user['email'], 'skills': user.get('skills', []),
        'domain': user.get('domain', ''), 'college': user.get('college', '')
    }), 200

# ── PROFILE ─────────────────────────────────────────────────
@app.route('/api/user/profile', methods=['GET'])
@jwt_required()
def get_profile():
    uid = get_jwt_identity()
    user = mongo.db.users.find_one({'_id': ObjectId(uid)}, {'password': 0})
    if not user:
        return jsonify({'message': 'User not found'}), 404
    return jsonify(fix_id(user)), 200

@app.route('/api/user/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    uid = get_jwt_identity()
    data = request.get_json()
    update = {}
    for field in ['name', 'college', 'domain', 'skills', 'location', 'about']:
        if field in data:
            update[field] = data[field]
    mongo.db.users.update_one({'_id': ObjectId(uid)}, {'$set': update})
    return jsonify({'message': 'Profile updated!'}), 200

# ── INTERNSHIPS ─────────────────────────────────────────────
@app.route('/api/internships', methods=['GET'])
def get_internships():
    internships = list(mongo.db.internships.find({}, {'_id': 0}))
    return jsonify(internships), 200

# get_matched moved to enhanced version below

# ── BOOKMARKS ───────────────────────────────────────────────
@app.route('/api/bookmark/<intern_id>', methods=['POST'])
@jwt_required()
def bookmark(intern_id):
    uid = get_jwt_identity()
    user = mongo.db.users.find_one({'_id': ObjectId(uid)})
    bookmarks = user.get('bookmarks', [])
    if intern_id in bookmarks:
        mongo.db.users.update_one({'_id': ObjectId(uid)}, {'$pull': {'bookmarks': intern_id}})
        return jsonify({'message': 'Removed', 'saved': False}), 200
    else:
        mongo.db.users.update_one({'_id': ObjectId(uid)}, {'$push': {'bookmarks': intern_id}})
        return jsonify({'message': 'Saved!', 'saved': True}), 200

@app.route('/api/bookmarks', methods=['GET'])
@jwt_required()
def get_bookmarks():
    uid = get_jwt_identity()
    user = mongo.db.users.find_one({'_id': ObjectId(uid)})
    bookmarks = user.get('bookmarks', [])
    saved = list(mongo.db.internships.find({'id': {'$in': bookmarks}}, {'_id': 0}))
    return jsonify(saved), 200

# ── APPLICATIONS ─────────────────────────────────────────────
@app.route('/api/apply/<intern_id>', methods=['POST'])
@jwt_required()
def apply(intern_id):
    uid = get_jwt_identity()
    user = mongo.db.users.find_one({'_id': ObjectId(uid)})
    apps = user.get('applications', [])
    if any(a.get('intern_id') == intern_id for a in apps):
        return jsonify({'message': 'Already applied!'}), 409
    intern = mongo.db.internships.find_one({'id': intern_id}, {'_id': 0})
    if not intern:
        return jsonify({'message': 'Internship not found'}), 404
    mongo.db.users.update_one(
        {'_id': ObjectId(uid)},
        {'$push': {'applications': {
            'intern_id': intern_id,
            'company': intern.get('company'),
            'role': intern.get('role'),
            'status': 'Applied'
        }}}
    )
    return jsonify({'message': f"Applied to {intern.get('company')}!"}), 200

@app.route('/api/applications', methods=['GET'])
@jwt_required()
def get_applications():
    uid = get_jwt_identity()
    user = mongo.db.users.find_one({'_id': ObjectId(uid)})
    return jsonify(user.get('applications', [])), 200

# ── SEED DATA ───────────────────────────────────────────────
@app.route('/api/seed', methods=['POST'])
def seed():
    if mongo.db.internships.count_documents({}) > 0:
        return jsonify({'message': 'Already seeded!'}), 200
    internships = [
        {'id':'rzp1','company':'Razorpay','logo':'R','role':'Product Intern','location':'Bangalore','mode':'Remote OK','stipend':25000,'domain':'Full Stack Development','skills':['React','Node.js','SQL','Product Thinking'],'deadline':'3 days','tags':['React','Node.js','Remote OK']},
        {'id':'zmt1','company':'Zomato','logo':'Z','role':'Data Science Intern','location':'Gurugram','mode':'Hybrid','stipend':30000,'domain':'Data Science','skills':['Python','ML','SQL','Pandas'],'deadline':'5 days','tags':['Python','ML','SQL']},
        {'id':'crd1','company':'CRED','logo':'C','role':'UI/UX Design Intern','location':'Bangalore','mode':'Hybrid','stipend':20000,'domain':'UI/UX Design','skills':['Figma','Prototyping','User Research'],'deadline':'7 days','tags':['Figma','Prototyping','Hybrid']},
        {'id':'mes1','company':'Meesho','logo':'M','role':'SDE Intern','location':'Bangalore','mode':'On-site','stipend':35000,'domain':'Backend Development','skills':['Java','Spring Boot','MySQL'],'deadline':'1 day','tags':['Java','Spring Boot','On-site']},
        {'id':'swg1','company':'Swiggy','logo':'S','role':'Backend Engineering Intern','location':'Bangalore','mode':'Remote','stipend':40000,'domain':'Backend Development','skills':['Go','Kafka','Docker','Redis'],'deadline':'10 days','tags':['Go','Kafka','Remote']},
        {'id':'ntn1','company':'Notion','logo':'N','role':'Marketing Intern','location':'Remote','mode':'Remote','stipend':15000,'domain':'Marketing','skills':['SEO','Content Writing','Analytics','Canva'],'deadline':'8 days','tags':['SEO','Content','Analytics']},
        {'id':'grw1','company':'Groww','logo':'G','role':'Frontend Intern','location':'Bangalore','mode':'Hybrid','stipend':28000,'domain':'Frontend Development','skills':['React','TypeScript','CSS','JavaScript'],'deadline':'4 days','tags':['React','TypeScript','Hybrid']},
        {'id':'ola1','company':'Ola','logo':'O','role':'ML Research Intern','location':'Bangalore','mode':'On-site','stipend':45000,'domain':'Machine Learning','skills':['PyTorch','Computer Vision','Python','TensorFlow'],'deadline':'12 days','tags':['PyTorch','CV','On-site']},
        {'id':'pep1','company':'PhonePe','logo':'P','role':'Product Analytics Intern','location':'Bangalore','mode':'Remote','stipend':22000,'domain':'Data Analyst','skills':['SQL','Tableau','Excel','Python'],'deadline':'6 days','tags':['SQL','Tableau','Remote']},
        {'id':'dnz1','company':'Dunzo','logo':'D','role':'Operations Intern','location':'Mumbai','mode':'On-site','stipend':12000,'domain':'Business Analytics','skills':['Excel','Operations','Data Analysis'],'deadline':'14 days','tags':['Excel','Ops','On-site']},
        {'id':'brs1','company':'BrowserStack','logo':'B','role':'QA Automation Intern','location':'Mumbai','mode':'Hybrid','stipend':18000,'domain':'Software Testing','skills':['Selenium','Python','TestNG','JIRA'],'deadline':'9 days','tags':['Selenium','Python','Hybrid']},
        {'id':'frw1','company':'Freshworks','logo':'F','role':'SDE Intern','location':'Chennai','mode':'Remote','stipend':32000,'domain':'Full Stack Development','skills':['Ruby','Rails','JavaScript','PostgreSQL'],'deadline':'5 days','tags':['Ruby','Rails','Remote']},
        {'id':'ggl1','company':'Google','logo':'G','role':'STEP Intern','location':'Hyderabad','mode':'Hybrid','stipend':60000,'domain':'Software Development','skills':['Data Structures','Algorithms','Python','Java'],'deadline':'15 days','tags':['DSA','Python','Hybrid']},
        {'id':'amz1','company':'Amazon','logo':'A','role':'SDE Intern','location':'Bangalore','mode':'On-site','stipend':55000,'domain':'Backend Development','skills':['Java','AWS','System Design','DSA'],'deadline':'20 days','tags':['Java','AWS','On-site']},
        {'id':'mcs1','company':'Microsoft','logo':'M','role':'Software Engineering Intern','location':'Hyderabad','mode':'Hybrid','stipend':50000,'domain':'Software Development','skills':['C#','.NET','Azure','JavaScript'],'deadline':'18 days','tags':['C#','Azure','Hybrid']},
    ]
    mongo.db.internships.insert_many(internships)
    return jsonify({'message': f'Seeded {len(internships)} internships!'}), 201


# ── RESUME UPLOAD ────────────────────────────────────────────
from flask import send_from_directory
import base64

@app.route('/api/resume/upload', methods=['POST'])
@jwt_required()
def upload_resume():
    uid = get_jwt_identity()
    data = request.get_json()
    resume_name = data.get('resume_name', '')
    resume_data = data.get('resume_data', '')  # base64
    mongo.db.users.update_one(
        {'_id': ObjectId(uid)},
        {'$set': {'resume_name': resume_name, 'has_resume': True}}
    )
    return jsonify({'message': 'Resume saved!', 'name': resume_name}), 200

# ── COMPANY AUTH ──────────────────────────────────────────────
@app.route('/api/company/register', methods=['POST'])
def company_register():
    data = request.get_json()
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    company_name = data.get('company_name', '').strip()
    if not all([name, email, password, company_name]):
        return jsonify({'message': 'All fields required'}), 400
    if mongo.db.companies.find_one({'email': email}):
        return jsonify({'message': 'Email already registered'}), 409
    hashed = bcrypt.generate_password_hash(password).decode('utf-8')
    mongo.db.companies.insert_one({'name': name, 'email': email, 'password': hashed, 'company_name': company_name})
    return jsonify({'message': 'Company registered!'}), 201

@app.route('/api/company/login', methods=['POST'])
def company_login():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    company = mongo.db.companies.find_one({'email': email})
    if not company or not bcrypt.check_password_hash(company['password'], password):
        return jsonify({'message': 'Invalid credentials'}), 401
    token = create_access_token(identity='company_'+str(company['_id']))
    return jsonify({'token': token, 'company_name': company['company_name'], 'name': company['name']}), 200

@app.route('/api/company/post', methods=['POST'])
@jwt_required()
def post_internship():
    uid = get_jwt_identity()
    if not uid.startswith('company_'):
        return jsonify({'message': 'Company login required'}), 403
    data = request.get_json()
    required = ['role', 'location', 'stipend', 'domain', 'skills', 'deadline']
    if not all(data.get(f) for f in required):
        return jsonify({'message': 'Fill all required fields'}), 400
    company_id = uid.replace('company_', '')
    company = mongo.db.companies.find_one({'_id': ObjectId(company_id)})
    import random, string
    new_id = ''.join(random.choices(string.ascii_lowercase+string.digits, k=6))
    internship = {
        'id': new_id,
        'company': company['company_name'] if company else 'Company',
        'logo': (company['company_name'][0] if company else 'C'),
        'role': data['role'],
        'location': data['location'],
        'mode': data.get('mode', 'Hybrid'),
        'stipend': int(data['stipend']),
        'domain': data['domain'],
        'skills': data['skills'] if isinstance(data['skills'], list) else data['skills'].split(','),
        'deadline': data.get('deadline', '30 days'),
        'tags': data['skills'][:3] if isinstance(data['skills'], list) else data['skills'].split(',')[:3],
        'posted_by': company_id
    }
    mongo.db.internships.insert_one(internship)
    return jsonify({'message': f'Internship posted!', 'id': new_id}), 201

# ── ENHANCED AI MATCHING ──────────────────────────────────────
@app.route('/api/internships/matched', methods=['GET'])
@jwt_required()
def get_matched():
    uid = get_jwt_identity()
    user = mongo.db.users.find_one({'_id': ObjectId(uid)})
    user_skills = set(s.lower() for s in user.get('skills', []))
    user_domain = user.get('domain', '').lower()
    user_location = user.get('location', '').lower()
    internships = list(mongo.db.internships.find({}, {'_id': 0}))
    for intern in internships:
        req_skills = set(s.lower() for s in intern.get('skills', []))
        score = 30
        # Skills (40%)
        if req_skills:
            matched = len(user_skills & req_skills)
            score += int((matched / len(req_skills)) * 40)
        # Domain (20%)
        intern_domain = intern.get('domain', '').lower()
        if user_domain and (user_domain in intern_domain or intern_domain in user_domain):
            score += 20
        # Location/Remote (10%)
        if intern.get('mode') == 'Remote':
            score += 10
        elif user_location and user_location in intern.get('location', '').lower():
            score += 10
        intern['match_score'] = min(score, 99)
    internships.sort(key=lambda x: x['match_score'], reverse=True)
    return jsonify(internships), 200

# ── EMAIL NOTIFICATIONS (SendGrid) ───────────────────────────
@app.route('/api/notify/deadline', methods=['POST'])
@jwt_required()
def send_deadline_notification():
    # Requires SENDGRID_API_KEY env var
    sendgrid_key = os.environ.get('SENDGRID_API_KEY')
    if not sendgrid_key:
        return jsonify({'message': 'Email notifications not configured'}), 200
    uid = get_jwt_identity()
    user = mongo.db.users.find_one({'_id': ObjectId(uid)})
    # Get internships closing in 3 days
    internships = list(mongo.db.internships.find({}, {'_id': 0}))
    closing_soon = [i for i in internships if '1 day' in i.get('deadline','') or '2 day' in i.get('deadline','') or '3 day' in i.get('deadline','')]
    if not closing_soon:
        return jsonify({'message': 'No deadlines soon!'}), 200
    try:
        import urllib.request, json as json_lib
        email_data = {
            "personalizations": [{"to": [{"email": user['email']}]}],
            "from": {"email": "noreply@internsetu.app", "name": "InternSetu"},
            "subject": f"⏰ {len(closing_soon)} internship(s) closing soon!",
            "content": [{"type": "text/plain", "value": f"Hi {user['name']},\n\nThese internships are closing soon:\n" + "\n"\n".join([f"- {i['company']} - {i['role']} ({i['deadline']} left)" for i in closing_soon]) + "\n\nApply now: https://internsetu-production.up.railway.app\n\nTeam InternSetu"}]

These internships are closing soon:
" + "
"\n".join([f"- {i['company']} - {i['role']} ({i['deadline']} left)" for i in closing_soon]) + "

Apply now: https://internsetu-production.up.railway.app

Team InternSetu"}]
        }
        req = urllib.request.Request('https://api.sendgrid.com/v3/mail/send',
            data=json_lib.dumps(email_data).encode(),
            headers={'Authorization': f'Bearer {sendgrid_key}', 'Content-Type': 'application/json'},
            method='POST')
        urllib.request.urlopen(req)
        return jsonify({'message': f'Email sent to {user["email"]}!'}), 200
    except Exception as e:
        return jsonify({'message': 'Email failed: ' + str(e)}), 500

# ── MANIFEST (PWA) ───────────────────────────────────────────
@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "InternSetu",
        "short_name": "InternSetu",
        "description": "AI-powered internship matching platform",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#f8f9ff",
        "theme_color": "#2461e8",
        "icons": [
            {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png"}
        ]
    })

# ── SERVICE WORKER (PWA) ─────────────────────────────────────
@app.route('/sw.js')
def service_worker():
    sw_code = """
const CACHE = 'internsetu-v1';
const ASSETS = ['/', '/manifest.json'];
self.addEventListener('install', e => e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS))));
self.addEventListener('fetch', e => {
  if(e.request.url.includes('/api/')) return;
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
"""
    from flask import Response
    return Response(sw_code, mimetype='application/javascript')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)