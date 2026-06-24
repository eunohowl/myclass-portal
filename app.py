from flask import Flask, render_template, request, redirect, url_for, session, Response
import os, io, csv
import pandas as pd
from dotenv import load_dotenv
from flask_mail import Mail, Message

# Load file .env biar kebaca sistem
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'unpam_ti_secret_key_super_gaib')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

# Konfigurasi Mail Server pakai .env (Default: SendGrid SMTP)
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.sendgrid.net')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', 'apikey')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', '')
app.config['MAIL_SUPPRESS_SEND'] = not bool(os.getenv('MAIL_PASSWORD'))
mail = Mail(app)

def kirim_notifikasi(to_email, subject, body):
    try:
        sender_email = os.getenv('MAIL_DEFAULT_SENDER', 'khlazieeed@gmail.com')
        msg = Message(subject, sender=sender_email, recipients=[to_email])
        msg.body = body
        mail.send(msg)
        print(f"✅ Email sukses terkirim ke {to_email}")
    except Exception as e:
        print(f"❌ Error kirim email: {e}")
        import traceback
        traceback.print_exc()

# DATABASE (Sudah ditambahkan field 'email')
users_db = {os.getenv('ADMIN_EMAIL', 'khlazieeed@gmail.com'): "admin"}
students_db = [
    {"name": "Zidan Achilla Muhammad Azka", "nim": "241011450306", "ipk": 3.43, "hadir": 12, "status": "Aktif", "jurusan": "Teknik Informatika", "email": "zidanachilla@gmail.com"},
    {"name": "M. Rafli", "nim": "241011450112", "ipk": 3.20, "hadir": 14, "status": "Aktif", "jurusan": "Teknik Informatika", "email": "mrafli@gmail.com"}
]
jadwal_db = [
    {"kode": "22TIF0103", "matkul": "STRUKTUR DATA", "dosen": "INES HEIDIANI IKASARI", "sks": 3, "hari": "Senin", "jam": "07.10 - 08.50", "ruang": "V.208A", "periode": 1, "tgl_mulai": "2 Mar 2026", "tgl_selesai": "4 Jul 2026"},
    {"kode": "22TIF0093", "matkul": "STATISTIKA DAN PROBABILITAS", "dosen": "TUKIYAT", "sks": 2, "hari": "Senin", "jam": "08.50 - 10.30", "ruang": "V.208A", "periode": 1, "tgl_mulai": "2 Mar 2026", "tgl_selesai": "4 Jul 2026"},
    {"kode": "22TIF0122", "matkul": "GRAPH TERAPAN", "dosen": "SUSANNA DWI YULIANTI KUSUMA", "sks": 3, "hari": "Selasa", "jam": "07.10 - 08.50", "ruang": "V.208A", "periode": 1, "tgl_mulai": "2 Mar 2026", "tgl_selesai": "4 Jul 2026"},
    {"kode": "22TIF0142", "matkul": "MATEMATIKA DISKRIT", "dosen": "HERWIS GULTOM", "sks": 2, "hari": "Selasa", "jam": "08.50 - 10.30", "ruang": "V.208A", "periode": 1, "tgl_mulai": "2 Mar 2026", "tgl_selesai": "4 Jul 2026"},
    {"kode": "22ILK0042", "matkul": "ALJABAR LINIER DAN MATRIKS", "dosen": "INDAH PERTIWI", "sks": 2, "hari": "Selasa", "jam": "10.30 - 12.10", "ruang": "V.208A", "periode": 1, "tgl_mulai": "2 Mar 2026", "tgl_selesai": "4 Jul 2026"},
    {"kode": "22TIF0152", "matkul": "SISTEM BERKAS", "dosen": "DANI RAMDANI", "sks": 3, "hari": "Selasa", "jam": "13.00 - 14.40", "ruang": "V.208A", "periode": 1, "tgl_mulai": "2 Mar 2026", "tgl_selesai": "4 Jul 2026"},
    {"kode": "22TIF0113", "matkul": "ALGORITMA DAN PEMROGRAMAN II", "dosen": "EKA SRI RAHAYU", "sks": 3, "hari": "Rabu", "jam": "07.10 - 08.50", "ruang": "V.208A", "periode": 1, "tgl_mulai": "2 Mar 2026", "tgl_selesai": "4 Jul 2026"},
    {"kode": "22TIF0133", "matkul": "JARINGAN KOMPUTER", "dosen": "EKA SRI RAHAYU", "sks": 3, "hari": "Rabu", "jam": "08.50 - 10.30", "ruang": "V.208A", "periode": 1, "tgl_mulai": "2 Mar 2026", "tgl_selesai": "4 Jul 2026"}
]

# ─── COLUMN ALIAS MAP ───
COL_ALIASES = {
    'name':    ['name', 'nama', 'nama lengkap', 'nama_lengkap', 'full name'],
    'nim':     ['nim', 'nomor_induk', 'student_id', 'no induk', 'id mahasiswa'],
    'ipk':     ['ipk', 'gpa', 'grade', 'nilai'],
    'hadir':   ['hadir', 'kehadiran', 'attendance', 'total_hadir', 'total hadir', 'absensi'],
    'status':  ['status', 'status mahasiswa'],
    'jurusan': ['jurusan', 'prodi', 'major', 'program studi', 'program_studi'],
    'email':   ['email', 'e-mail', 'mail', 'alamat email', 'alamat_email']
}

def resolve_columns(df_columns):
    col_lower = {c.strip().lower(): c for c in df_columns}
    mapping = {}
    for field, aliases in COL_ALIASES.items():
        for alias in aliases:
            if alias in col_lower:
                mapping[field] = col_lower[alias]
                break
    return mapping

def parse_upload(file):
    global students_db
    filename = file.filename.lower()
    added, skipped = 0, 0
    errors = []
    existing_nims = {str(m['nim']) for m in students_db}

    try:
        if filename.endswith('.csv'):
            content = file.stream.read().decode('utf-8-sig')
            df = pd.read_csv(io.StringIO(content), dtype=str)
        elif filename.endswith(('.xlsx', '.xls')):
            file.stream.seek(0)
            df = pd.read_excel(file.stream, dtype=str, engine='openpyxl' if filename.endswith('.xlsx') else None)
        else:
            return 0, 0, ['Format tidak didukung. Gunakan .csv atau .xlsx/.xls']
    except Exception as e:
        return 0, 0, [f'Gagal membaca file: {str(e)}']

    df.columns = [str(c).strip() for c in df.columns]
    col_map = resolve_columns(df.columns)

    if 'name' not in col_map or 'nim' not in col_map:
        return 0, 0, [f'Kolom wajib tidak ditemukan. Pastikan ada kolom: name/nama dan nim. Kolom terdeteksi: {list(df.columns)}']

    for i, row in df.iterrows():
        lineno = i + 2
        try:
            name = str(row[col_map['name']]).strip()
            nim  = str(row[col_map['nim']]).strip()

            if nim.endswith('.0'):
                nim = nim[:-2]

            if not name or name.lower() in ('nan', '') or not nim or nim.lower() in ('nan', ''):
                skipped += 1
                errors.append(f'Baris {lineno}: Nama/NIM kosong, dilewati.')
                continue

            if nim in existing_nims:
                skipped += 1
                errors.append(f'Baris {lineno}: NIM {nim} sudah ada, dilewati.')
                continue

            # IPK
            try:
                ipk_raw = str(row[col_map['ipk']]).replace(',', '.').strip() if 'ipk' in col_map else '0'
                ipk = float(ipk_raw) if ipk_raw.lower() not in ('nan', '', 'none') else 0.0
                ipk = max(0.0, min(4.0, round(ipk, 2)))
            except:
                ipk = 0.0

            # Kehadiran
            try:
                hadir_raw = str(row[col_map['hadir']]).strip() if 'hadir' in col_map else '0'
                hadir = int(float(hadir_raw)) if hadir_raw.lower() not in ('nan', '', 'none') else 0
                hadir = max(0, min(14, hadir))
            except:
                hadir = 0

            # Status
            status_raw = str(row[col_map['status']]).strip() if 'status' in col_map else ''
            status = status_raw if status_raw.lower() not in ('nan', '', 'none') else 'Aktif'

            # Jurusan
            jurusan_raw = str(row[col_map['jurusan']]).strip() if 'jurusan' in col_map else ''
            jurusan = jurusan_raw if jurusan_raw.lower() not in ('nan', '', 'none') else 'Teknik Informatika'

            # Email parsing
            email_raw = str(row[col_map['email']]).strip() if 'email' in col_map else ''
            email = email_raw if email_raw.lower() not in ('nan', '', 'none') else f"{nim}@student.unpam.ac.id"

            students_db.append({
                'name': name, 'nim': nim, 'ipk': ipk,
                'hadir': hadir, 'status': status, 'jurusan': jurusan, 'email': email
            })
            existing_nims.add(nim)
            added += 1

        except Exception as e:
            skipped += 1
            errors.append(f'Baris {lineno}: Error — {str(e)}')

    return added, skipped, errors


# ═══════════════════════════════════════════════
#  ALGORITMA SEARCH
# ═══════════════════════════════════════════════

def linear_search(query):
    result = []
    for mhs in students_db:
        if query.lower() in mhs['name'].lower():
            result.append(mhs)
    return result

def binary_search(target_nim):
    sorted_mhs = sorted(students_db, key=lambda x: str(x['nim']))
    low, high = 0, len(sorted_mhs) - 1
    while low <= high:
        mid = (low + high) // 2
        mid_nim = str(sorted_mhs[mid]['nim'])
        if mid_nim == target_nim:
            return [sorted_mhs[mid]]
        elif mid_nim < target_nim:
            low = mid + 1
        else:
            high = mid - 1
    return []

def sequential_search(target_status):
    result = []
    for mhs in students_db:
        if mhs['status'].lower() == target_status.lower():
            result.append(mhs)
    return result


# ═══════════════════════════════════════════════
#  ALGORITMA SORT
# ═══════════════════════════════════════════════

def bubble_sort_ipk(data):
    arr = [dict(m) for m in data]
    n = len(arr)
    for i in range(n):
        swapped = False
        for j in range(0, n - i - 1):
            if arr[j]['ipk'] < arr[j + 1]['ipk']:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True
        if not swapped:
            break
    return arr

def insertion_sort_hadir(data):
    arr = [dict(m) for m in data]
    for i in range(1, len(arr)):
        key = arr[i]
        j = i - 1
        while j >= 0 and arr[j]['hadir'] < key['hadir']:
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = key
    return arr


# ═══════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if email in users_db and users_db[email] == password:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        return render_template('login.html', error="Email/Password salah!")
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if email not in users_db:
            users_db[email] = password
            return render_template('login.html', success="Akun berhasil dibuat!")
        return render_template('signup.html', error="Email sudah terdaftar!")
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    if 'logged_in' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html', students=students_db)

@app.route('/presensi')
def presensi():
    return render_template('presensi.html', students=students_db)

@app.route('/data_kelas', methods=['GET'])
def data_kelas():
    if 'logged_in' not in session: return redirect(url_for('login'))
    search_type  = request.args.get('search_type', 'linear')
    query        = request.args.get('search_query', '').strip()
    sort_type    = request.args.get('sort_type', '')
    toast_type   = request.args.get('toast_type', '')
    toast_msg_p  = request.args.get('toast_msg', '')
    data = list(students_db)
    algo_log = ""

    # ── SEARCH ──
    if query:
        if search_type == 'linear':
            data = linear_search(query)
            algo_log = f"🔍 Linear Search selesai — memeriksa {len(students_db)} data satu per satu. Ditemukan {len(data)} hasil untuk nama '{query}'."
        elif search_type == 'binary':
            data = binary_search(query)
            algo_log = f"🔎 Binary Search selesai — NIM diurutkan lalu dibagi dua secara rekursif. {'Ditemukan 1 data' if data else 'Tidak ditemukan'} untuk NIM '{query}'."
        elif search_type == 'sequential':
            data = sequential_search(query)
            algo_log = f"📋 Sequential Search selesai — menelusuri seluruh data dari indeks 0 hingga {len(students_db)-1}. Ditemukan {len(data)} mahasiswa berstatus '{query}'."

    # ── SORT ──
    if sort_type == 'bubble_ipk':
        data = bubble_sort_ipk(data)
        algo_log += f"  |  🫧 Bubble Sort — {len(data)} elemen diurutkan berdasarkan IPK tertinggi."
    elif sort_type == 'insertion_hadir':
        data = insertion_sort_hadir(data)
        algo_log += f"  |  📥 Insertion Sort — {len(data)} elemen diurutkan berdasarkan kehadiran terbanyak."

    return render_template('data_kelas.html',
        students=data,
        algo_log=algo_log,
        search_type=search_type,
        search_query=query,
        sort_type=sort_type,
        toast_type=toast_type,
        toast_msg_param=toast_msg_p
    )

@app.route('/jadwal')
def jadwal():
    if 'logged_in' not in session: return redirect(url_for('login'))
    total_sks = sum(item['sks'] for item in jadwal_db)
    info_kelas = {
        "kelas": "03TPLP002",
        "fakultas": "Ilmu Komputer / Teknik Informatika S1",
        "shift": "Reguler A",
        "semester": "Genap 2025/2026"
    }
    return render_template('jadwal.html', jadwal=jadwal_db, total_sks=total_sks, info_kelas=info_kelas)

@app.route('/add_student', methods=['POST'])
def add_student():
    if 'logged_in' not in session: return redirect(url_for('login'))
    global students_db
    new_mhs = {
        "name":    request.form.get('name'),
        "nim":     request.form.get('nim'),
        "ipk":     float(request.form.get('ipk', 0)),
        "hadir":   int(request.form.get('hadir', 0)),
        "status":  request.form.get('status', 'Aktif'),
        "email":   request.form.get('email', f"{request.form.get('nim')}@student.unpam.ac.id"),
        "jurusan": "Teknik Informatika"
    }
    students_db.append(new_mhs)
    # FIX: hanya kirim notifikasi jika email dikonfigurasi
    if os.getenv('MAIL_PASSWORD'):
        kirim_notifikasi(os.getenv('ADMIN_EMAIL', 'khlazieeed@gmail.com'), 'Update Database Portal', 'Data mahasiswa baru berhasil ditambahkan ke kelas 03TPLP002.')
    return redirect(url_for('dashboard', toast_type='success', toast_msg=f"✅ {new_mhs['name']} berhasil ditambahkan!"))

@app.route('/delete_student/<nim>')
def delete_student(nim):
    if 'logged_in' not in session: return redirect(url_for('login'))
    global students_db
    students_db = [mhs for mhs in students_db if str(mhs['nim']) != str(nim)]
    return redirect(url_for('data_kelas', toast_type='success', toast_msg="✅ Data berhasil dihapus!"))

@app.route('/reset_students', methods=['POST'])
def reset_students():
    if 'logged_in' not in session: return redirect(url_for('login'))
    global students_db
    students_db = []
    return redirect(url_for('data_kelas', toast_type='warning', toast_msg='🗑️ Seluruh data mahasiswa telah dihapus!'))

@app.route('/edit_student/<nim>', methods=['GET', 'POST'])
def edit_student(nim):
    if 'logged_in' not in session: return redirect(url_for('login'))
    global students_db
    mhs = next((m for m in students_db if str(m['nim']) == str(nim)), None)
    if not mhs:
        return redirect(url_for('data_kelas', toast_type='error', toast_msg='❌ Data tidak ditemukan.'))
    if request.method == 'POST':
        mhs['name']    = request.form.get('name', mhs['name'])
        mhs['nim']     = request.form.get('nim', mhs['nim'])
        mhs['ipk']     = float(request.form.get('ipk', mhs['ipk']))
        mhs['hadir']   = int(request.form.get('hadir', mhs['hadir']))
        mhs['status']  = request.form.get('status', mhs['status'])
        mhs['email']   = request.form.get('email', mhs.get('email', ''))
        mhs['jurusan'] = request.form.get('jurusan', mhs['jurusan'])
        return redirect(url_for('data_kelas', toast_type='success', toast_msg=f"✅ Data {mhs['name']} berhasil diperbarui!"))
    return render_template('edit_student.html', mhs=mhs)

@app.route('/profile/<nim>')
def profile(nim):
    if 'logged_in' not in session: return redirect(url_for('login'))
    mhs = next((m for m in students_db if str(m['nim']) == str(nim)), None)
    if not mhs:
        return redirect(url_for('data_kelas', toast_type='error', toast_msg='❌ Data tidak ditemukan.'))
    return render_template('profile.html', mhs=mhs)

# ── FEATURE: KIRIM EMAIL KE MAHASISWA PERSONAL ──
@app.route('/send_email_student/<nim>', methods=['POST'])
def send_email_student(nim):
    if 'logged_in' not in session: return redirect(url_for('login'))
    global students_db
    mhs = next((m for m in students_db if str(m['nim']) == str(nim)), None)

    if not mhs:
        return redirect(url_for('data_kelas', toast_type='error', toast_msg='❌ Mahasiswa tidak ditemukan!'))

    target_email = mhs.get('email')
    if not target_email or "@" not in target_email:
        return redirect(url_for('data_kelas', toast_type='error', toast_msg=f'❌ Alamat email {mhs["name"]} tidak valid!'))

    # FIX: cek dulu apakah MAIL_PASSWORD sudah diset di server
    if not os.getenv('MAIL_PASSWORD'):
        return redirect(url_for('data_kelas', toast_type='error', toast_msg='❌ Fitur email belum dikonfigurasi di server!'))

    subject = f"Data Profil Mahasiswa - {mhs['name']}"
    body = f"Halo, Mahasiswa/i {mhs['name']},\n\n" \
           f"Berikut adalah data anda:\n" \
           f"Nama      : {mhs['name']}\n" \
           f"NIM       : {mhs['nim']}\n" \
           f"IPK       : {mhs['ipk']}\n" \
           f"Kehadiran : {mhs['hadir']} / 14 Pertemuan\n" \
           f"Status    : {mhs['status']}\n" \
           f"Jurusan   : {mhs['jurusan']}\n" \
           f"Email     : {mhs['email']}\n\n" \
           f"Pesan ini dikirim otomatis oleh Admin Portal Kelas."

    try:
        sender_identity = os.getenv('MAIL_DEFAULT_SENDER', 'khlazieeed@gmail.com')
        msg = Message(subject, sender=sender_identity, recipients=[target_email])
        msg.body = body
        mail.send(msg)
        return redirect(url_for('data_kelas', toast_type='success', toast_msg=f"📩 Sukses kirim email ke {mhs['name']}!"))
    except Exception as e:
        return redirect(url_for('data_kelas', toast_type='error', toast_msg=f"❌ Gagal kirim email: {str(e)}"))

@app.route('/upload_students', methods=['POST'])
def upload_students():
    if 'logged_in' not in session: return redirect(url_for('login'))
    file = request.files.get('file')
    if not file or file.filename == '':
        return redirect(url_for('dashboard', toast_type='error', toast_msg='❌ Tidak ada file yang dipilih!'))

    added, skipped, errors = parse_upload(file)

    if added == 0 and errors:
        return redirect(url_for('dashboard', toast_type='error', toast_msg=f"❌ Import gagal: {errors[0]}"))

    # FIX: hanya kirim notifikasi jika MAIL_PASSWORD sudah diset
    if added > 0 and os.getenv('MAIL_PASSWORD'):
        kirim_notifikasi(os.getenv('ADMIN_EMAIL', 'khlazieeed@gmail.com'), f'Import Massal: {added} Mahasiswa Baru',
            f'{added} data mahasiswa baru berhasil diimport ke kelas 03TPLP002. {skipped} data dilewati.')

    if skipped == 0:
        msg, ttype = f"✅ {added} mahasiswa berhasil diimport!", 'success'
    else:
        msg, ttype = f"✅ {added} diimport, ⚠️ {skipped} dilewati (duplikat/kosong)", 'warning'

    return redirect(url_for('dashboard', toast_type=ttype, toast_msg=msg))

@app.route('/download_template')
def download_template():
    if 'logged_in' not in session: return redirect(url_for('login'))
    csv_content  = "name,nim,ipk,hadir,status,jurusan,email\n"
    csv_content += "Budi Santoso,241011450010,3.55,13,Aktif,Teknik Informatika,budi@example.com\n"
    csv_content += "Siti Rahayu,241011450011,3.80,14,Aktif,Teknik Informatika,siti@example.com\n"
    csv_content += "Andi Prasetyo,241011450012,2.90,10,Nonaktif,Teknik Informatika,andi@example.com\n"
    return Response(csv_content, mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=template_import_mahasiswa.csv'})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
