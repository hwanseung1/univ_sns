from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_mysqldb import MySQL
import bcrypt
from db import mysql, init_db
from dotenv import load_dotenv
import os
from werkzeug.utils import secure_filename
from flask import send_file
from flask import send_from_directory

# 환경 변수 로드
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')  # .env에서 비밀 키 가져오기

# 파일 업로드 설정
UPLOAD_FOLDER = 'uploads/'  # 파일을 저장할 폴더 (서버의 'uploads' 폴더)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx', 'txt', 'zip'}  # 허용된 파일 확장자

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 파일 확장자 확인 함수
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# DB 설정 내용 호출
init_db(app)

# 홈
@app.route('/')
def home():
    return render_template('index.html')

# 회원가입
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        id = request.form['id']
        password = request.form['password'].encode('utf-8')
        password_check = request.form['pwcheck'].encode('utf-8')
        name = request.form['name']
        school = request.form['school']
        birthdate = request.form['birthdate']
        email = request.form['email']
        
        # 비밀번호 해싱
        hashed_pw = bcrypt.hashpw(password, bcrypt.gensalt())
        
        if password==password_check:
            # DB에 데이터 삽입
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO student (id, password, name, school, birthdate, email) VALUES (%s, %s, %s, %s, %s, %s)",
                        (id, hashed_pw, name, school, birthdate, email))
            mysql.connection.commit()
            cur.close()
            flash('회원가입되었습니다.')
            return redirect('/login')
        else:
            flash('비밀번호가 일치하지 않습니다.')
    return render_template('register.html')

# 로그인
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        id = request.form['id']
        password = request.form['password'].encode('utf-8')
        
        # DB에서 사용자 정보 가져오기
        cur = mysql.connection.cursor()
        cur.execute("SELECT password, name FROM student WHERE id = %s", (id,))
        user = cur.fetchone()
        cur.close()
        
        if user and bcrypt.checkpw(password, user[0].encode('utf-8')):
            session['user_id'] = id  # 세션 저장
            session['user_name'] = user[1]  # 세션에 사용자 이름 저장
            flash(f'{user[1]}님, 환영합니다!')
            return redirect('/')
        else:
            flash('로그인 실패. 아이디나 비밀번호를 확인해주세요.')  # 경고 메시지 추가
            return redirect('/login')  # 로그인 페이지로 리디렉션
    
    return render_template('login.html')

# 로그아웃
@app.route('/logout')
def logout():
    if 'user_id' not in session:  # 로그인하지 않은 사용자라면 로그아웃 불가
        return redirect('/login')  # 로그인 페이지로 리디렉션
    
    session.pop('user_id', None)  # 세션에서 user_id 제거
    session.pop('user_name', None)  # 세션에서 user_name 제거
    flash('로그아웃되었습니다.')
    return redirect('/login')  # 로그인 페이지로 리디렉션


# 게시판 목록
@app.route('/board')
def board():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM board ORDER BY created_at DESC")
    posts = cur.fetchall()
    cur.close()
    return render_template('board.html', posts=posts)

# 파일 경로 생성 함수
def create_user_folder(user_id):
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(user_id))
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)  # 사용자 폴더가 없으면 생성
    return user_folder

#게시글 작성
@app.route('/board/create', methods=['GET', 'POST'])
def create_post():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        user_id = session['user_id']
        is_private = 'is_private' in request.form
        password = request.form['password'] if is_private else None
        file = request.files.get('file')

        # 파일 크기 검사 (MAX_CONTENT_LENGTH 대신 수동 검사)
        MAX_FILE_SIZE = 200 * 1024  # 200KB

        if file:
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            if file_size > MAX_FILE_SIZE:
                flash("파일 크기가 200KB를 초과할 수 없습니다.")
                return redirect(request.referrer or '/board/create')

        # 비밀글 비밀번호 해싱
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()) if password else None

        # 사용자별 폴더 경로 생성
        user_folder = create_user_folder(user_id)
        
        file_path = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(user_folder, filename)
            file.save(file_path)

        # 데이터베이스에 게시글 저장
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO board (title, content, user_id, file_path, is_private, private_password) VALUES (%s, %s, %s, %s, %s, %s)",
                    (title, content, user_id, file_path, is_private, hashed_password))
        mysql.connection.commit()
        cur.close()

        flash('게시글이 작성되었습니다.')
        return redirect('/board')

    return render_template('create_post.html')

#게시판 상세 Read
@app.route('/board/read/<int:post_id>', methods=['GET', 'POST'])
def read_post(post_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM board WHERE no = %s", (post_id,))
    post = cur.fetchone()
    cur.close()

    if not post:
        flash('게시글을 찾을 수 없습니다.')
        return redirect('/board')

    # 로그인하지 않았을 경우
    if 'user_id' not in session:
        flash('로그인을 해주세요.')
        return redirect('/board')

    # 비밀글인 경우 비밀번호 확인 필요
    if post[7]:  # post[7] == is_private
        if request.method == 'POST':
            password = request.form['password'].encode('utf-8')
            stored_hashed_password = post[8]  # private_password

            if bcrypt.checkpw(password, stored_hashed_password.encode('utf-8')):
                return render_template('read_post.html', post=post)  # 비밀번호 확인 후 게시글 표시
            else:
                flash('비밀번호가 올바르지 않습니다.')
                return redirect(f'/board/read/{post_id}')

        return render_template('password_prompt.html', post_id=post_id)  # 비밀번호 입력 폼 페이지

    return render_template('read_post.html', post=post)

#파일 다운로드
@app.route('/board/download/<int:post_id>')
def download_file(post_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT file_path FROM board WHERE no = %s", (post_id,))
    file_data = cur.fetchone()
    cur.close()

    if file_data and file_data[0]:  # 파일이 존재하면
        file_path = file_data[0]
        return send_file(file_path, as_attachment=True)  # 파일 다운로드
    else:
        flash('파일이 존재하지 않습니다.')
        return redirect('/board')


# 게시글 수정
@app.route('/board/edit/<int:post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    if 'user_id' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM board WHERE no = %s", (post_id,))
    post = cur.fetchone()

    if not post or post[3] != session['user_id']:  # 작성자 본인이 아닌 경우
        flash('이 게시글은 수정할 수 없습니다.')
        return redirect('/board')

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        is_private = 'is_private' in request.form  # 비밀글 체크 여부
        file = request.files.get('file')  # 업로드된 파일

        file_path = post[6]  # 기존 파일 경로 유지
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)  # 파일 저장

        cur.execute("UPDATE board SET title = %s, content = %s, updated_at = CURRENT_TIMESTAMP, file_path = %s, is_private = %s WHERE no = %s",
                    (title, content, file_path, is_private, post_id))
        mysql.connection.commit()
        cur.close()

        flash('게시글이 수정되었습니다.')
        return redirect('/board')

    cur.close()
    return render_template('edit_post.html', post=post)

# 게시글 삭제
@app.route('/board/delete/<int:post_id>')
def delete_post(post_id):
    if 'user_id' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM board WHERE no = %s", (post_id,))
    post = cur.fetchone()

    if not post or post[3] != session['user_id']:  # 작성자 본인이 아닌 경우
        flash('이 게시글은 삭제할 수 없습니다.')
        return redirect('/board')

    cur.execute("DELETE FROM board WHERE no = %s", (post_id,))
    mysql.connection.commit()
    cur.close()

    flash('게시글이 삭제되었습니다.')
    return redirect('/board')


# 게시글 검색
@app.route('/board/search')
def search_board():
    query = request.args.get('query', '').strip()
    filter_type = request.args.get('filter', 'all')

    if not query:
        return redirect('/board')  # 검색어가 없으면 게시판으로 리디렉트

    cur = mysql.connection.cursor()

    # 검색 조건 설정
    if filter_type == 'title':
        cur.execute("SELECT * FROM board WHERE title LIKE %s ORDER BY created_at DESC", ('%' + query + '%',))
    elif filter_type == 'content':
        cur.execute("SELECT * FROM board WHERE content LIKE %s ORDER BY created_at DESC", ('%' + query + '%',))
    else:  # 'all' (제목 + 내용 검색)
        cur.execute("SELECT * FROM board WHERE title LIKE %s OR content LIKE %s ORDER BY created_at DESC", 
                    ('%' + query + '%', '%' + query + '%'))

    search_results = cur.fetchall()
    cur.close()

    return render_template('search_results.html', posts=search_results, query=query)

# 아이디 찾기
@app.route('/find_id', methods=['GET', 'POST'])
def find_id():
    if request.method == 'POST':
        name = request.form['name']
        birthdate = request.form['birthdate']

        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM student WHERE name = %s AND birthdate = %s", (name, birthdate))
        user = cur.fetchone()
        cur.close()

        if user:
            flash(f"회원님의 아이디는 '{user[0]}'입니다.", 'info')
            return redirect('/login')
        else:
            flash("입력한 정보와 일치하는 아이디가 없습니다.")
            return redirect('/find_id')

    return render_template('find_id.html')


# 비밀번호 찾기(사용자 확인 단계)
@app.route('/find_password', methods=['GET', 'POST'])
def find_password():
    if request.method == 'POST':
        id = request.form['id']
        email = request.form['email']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM student WHERE id = %s AND email = %s", (id, email))
        user = cur.fetchone()
        cur.close()

        if user:
            session['reset_id'] = id  # 세션에 저장하여 비밀번호 변경 시 사용
            return redirect('/reset_password')
        else:
            flash("입력한 정보와 일치하는 계정이 없습니다.")
            return redirect('/find_password')

    return render_template('find_password.html')

# 비밀번호 변경(재설정)
@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if 'reset_id' not in session:
        return redirect('/find_password')  # 보안 강화: 직접 접근 방지

    if request.method == 'POST':
        new_password = request.form['new_password'].encode('utf-8')
        hashed_pw = bcrypt.hashpw(new_password, bcrypt.gensalt())

        cur = mysql.connection.cursor()
        cur.execute("UPDATE student SET password = %s WHERE id = %s", (hashed_pw, session['reset_id']))
        mysql.connection.commit()
        cur.close()

        session.pop('reset_id', None)  # 세션에서 삭제
        flash("비밀번호가 성공적으로 변경되었습니다. 다시 로그인하세요.")
        return redirect('/login')

    return render_template('reset_password.html')

# 프로필 이미지 파일 경로 생성 함수
def create_profile_folder():
    profile_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'profile_img')
    if not os.path.exists(profile_folder):
        os.makedirs(profile_folder)  # 'profile_img' 폴더가 없으면 생성
    return profile_folder

#프로필 보기
@app.route('/profile/<user_id>')
def view_profile(user_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name, school, birthdate, email, mypicture FROM student WHERE id = %s", (user_id,))
    student = cur.fetchone()
    cur.close()

    if student:
        # mypicture 경로 수정
        profile_img = student[5]
        if profile_img:
            profile_img = profile_img.replace("\\", "/")  # 역슬래시를 슬래시로 변환

        return render_template('profile.html', student=student, profile_img=profile_img)
    else:
        flash('해당 사용자를 찾을 수 없습니다.')
        return redirect('/students')


@app.route('/uploads/<filename>')
def upload_file(filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], 'profile_img'), filename)

#프로필 수정
@app.route('/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect('/login')  # 로그인되지 않은 사용자는 로그인 페이지로 리디렉션

    user_id = session['user_id']

    # 사용자 정보 가져오기 (mySQL 쿼리)
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name, school, birthdate, mypicture FROM student WHERE id = %s", (user_id,))
    user = cur.fetchone()  # 한 명의 사용자 정보 가져오기
    cur.close()

    if user is None:
        flash('사용자 정보를 찾을 수 없습니다.')
        return redirect('/board')  # 사용자 정보가 없으면 게시판 페이지로 리디렉션

    # 프로필 수정 페이지에서 본인만 수정 가능하도록 하기 위해, 다른 사람의 프로필을 수정하려고 하면 접근을 거부
    if user_id != user[0]:  # user[0]은 id 값
        flash('본인만 프로필을 수정할 수 있습니다.')
        return redirect('/profile')  # 본인이 아닌 경우 프로필 페이지로 리디렉션

    # GET 요청 처리 (프로필 정보 보여주기)
    if request.method == 'GET':
        return render_template('edit_profile.html', name=user[1], school=user[2], birthdate=user[3], mypicture=user[4])

    # POST 요청 처리 (프로필 수정)
    if request.method == 'POST':
        # 수정할 데이터 받아오기
        name = request.form['name']
        school = request.form['school']
        birthdate = request.form['birthdate']

        # 파일 업로드 처리
        file = request.files.get('mypicture')
        mypicture = None

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            # 'profile_img' 폴더에 파일을 저장
            profile_folder = create_profile_folder()
            mypicture = os.path.join('uploads/profile_img', filename)  # 'uploads/profile_img' 폴더에 저장
            file.save(os.path.join(profile_folder, filename))  # 파일 저장

        # 데이터베이스 업데이트
        cur = mysql.connection.cursor()
        cur.execute(""" 
            UPDATE student 
            SET name = %s, school = %s, birthdate = %s, mypicture = %s 
            WHERE id = %s 
        """, (name, school, birthdate, mypicture, user_id))
        mysql.connection.commit()
        cur.close()

        flash('프로필이 수정되었습니다.')
        return redirect('/')  # 수정 후 프로필 페이지로 리디렉션

#학생 리스트
@app.route('/students')
def students_list():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name, school, birthdate, email FROM student ORDER BY name ASC")  # 학생 목록을 가져옴
    students = cur.fetchall()  # 모든 학생 데이터를 가져옴
    cur.close()

    return render_template('students.html', students=students)




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)