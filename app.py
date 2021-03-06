from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc, func
import os
import models
import forms
import sys
from numpy import dot
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from itsdangerous import URLSafeTimedSerializer
import traceback
import datetime
from datetime import timedelta
import random
import string
import urllib.request
import requests
import base64
import json
import imghdr

app = Flask(__name__)
app.secret_key = 's3cr3t'
app.config.from_object('config')
db = SQLAlchemy(app, session_options={'autocommit': False})

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

categories = ['Lecture Recordings', 'Handouts', 'Study Guides', 'Projects']
levels = ['First Grade', 'Second Grade', 'Third Grade', 'Fourth Grade', 'Fifth Grade', 'Sixth Grade', 'Seventh Grade', 'Eigth Grade', 'Ninth Grade', 'Tenth Grade', 'Eleventh Grade', 'Twelfth Grade', 'Undergraduate', 'Graduate']


@app.route('/')
@login_required
def home():
    resources = {}

    for category in categories:
        resources[category] = db.session.query(models.Resources).filter(models.Resources.category == category).all()

    return render_template('home.html', resources=resources, form=forms.SearchFormFactory.form(), levels=levels)

@app.route('/resource/<resource_id>')
@login_required
def resource(resource_id):
    resource = db.session.query(models.Resources)\
        .filter(models.Resources.resource_id == resource_id).all()
    return render_template('resource.html', resource=resource)

@app.route('/edit-resource/<resource_id>', methods=['GET', 'POST'])
@login_required
def edit_resource(resource_id):
    try:
        resource = db.session.query(models.Resources).filter(models.Resources.resource_id == resource_id).filter(models.Resources.teacher_id == current_user.username).one()
        form = forms.ResourceEditFormFactory.form(resource)
        if form.validate_on_submit():
            form.errors.pop('database', None)

            if request.method == 'POST':
                file = request.files['file']
                stream = file.stream
                header = stream.read(512)
                stream.seek(0)
                format = imghdr.what(None, header)
                if (format == 'jpg' or format == 'png' or format == 'jpeg'):
                    apiUrl = 'https://api.imgur.com/3/file'
                    b64_image = base64.standard_b64encode(file.read())
                    params = {'file' : b64_image}
                    headers = {'Authorization' : 'Client-ID 12aa250c79dba8d'}
                    #client_id = '12aa250c79dba8d'
                    #client_secret = '0e132c4d82850eda1d2a172903f5a85bcea10a0b'
                    response = requests.post(apiUrl, headers=headers, data=params)
                    result = json.loads(response.text)
                    edit_posting = models.Resources()
                    edit_posting.file = result['data']['link']
                    models.Resources.edit(resource_id, current_user.username, form.resource_name.data, form.category.data, form.subject.data, form.education_level.data, edit_posting.file, form.description.data, form.date_posted.data)
                else:
                    models.Resources.edit(resource_id, current_user.username, form.resource_name.data, form.category.data, form.subject.data, form.education_level.data, resource.file, form.description.data, form.date_posted.data)

                    flash('Resource been modified successfully')
                    return redirect(url_for('profile', username=current_user.username))
    except:
        flash('You are not posting this resource or this is not a valid resource.')
    return render_template('edit_resource.html', resource=resource, form=form)

@app.route('/post_resource', methods=['GET', 'POST'])
@login_required
def post_resource():
    form = forms.PostingFormFactory.form()
    if form.validate_on_submit():
        randomString = ''.join(random.choices(string.ascii_uppercase +
                         string.digits, k = 30))
        new_posting = models.Resources()
        new_posting.resource_id = randomString
        new_posting.teacher_id = current_user.username
        new_posting.resource_name = form.resource_name.data
        new_posting.category = form.category.data
        new_posting.subject = form.subject.data
        new_posting.education_level = form.education_level.data
        new_posting.description = form.description.data
        if request.method == 'POST':
            file = request.files['file']
            stream = file.stream
            header = stream.read(512)
            stream.seek(0)
            format = imghdr.what(None, header)
            if (format == 'jpg' or format == 'png' or format == 'jpeg'):
                apiUrl = 'https://api.imgur.com/3/file'
                b64_image = base64.standard_b64encode(file.read())
                params = {'file' : b64_image}
                headers = {'Authorization' : 'Client-ID 12aa250c79dba8d'}
                #client_id = '12aa250c79dba8d'
                #client_secret = '0e132c4d82850eda1d2a172903f5a85bcea10a0b'
                response = requests.post(apiUrl, headers=headers, data=params)
                result = json.loads(response.text)
                new_posting.file = result['data']['link']
            else:
                new_posting.file = form.file.data.filename

            new_posting.date_posted = str(datetime.date.today())
            db.session.add(new_posting)
            db.session.commit()
            db.session.close()

            flash('Resource posted successfully')
            return redirect(url_for('post_resource'))

    return render_template('post_resource.html', form=form)

@app.route('/resource/<resource_id>/reviews', methods=['GET', 'POST'])
@login_required
def review(resource_id):
    resource = db.session.query(models.Resources) \
        .filter(models.Resources.resource_id == resource_id).first()

    reviews = db.session.query(models.Reviews) \
        .filter(models.Reviews.resource_id == resource_id) \
        .group_by(models.Reviews.review_id).all()

    form = forms.ReviewFormFactory.form()
    if form.validate_on_submit():
        num_reviews = len([r for r in reviews if r.teacher_id == current_user.username])

        if num_reviews > 1:
            flash('You can only review a resource once')
            return redirect(url_for('review', resource_id=resource_id))

        if current_user.username == resource.teacher_id:
            flash('You cannot review your own item!')
            return redirect(url_for('review', resource_id=resource_id))

        try:
            new_review = models.Reviews()
            new_review.item_rating = form.item_rating.data
            new_review.comments = form.comments.data
            new_review.resource_id = resource_id
            new_review.teacher_id = resource.teacher_id
            new_review.reviewer_username = current_user.username
            print(new_review)

            db.session.add(new_review)
            db.session.commit()
            db.session.close()

            return redirect(url_for('review', resource_id=resource_id))
        except BaseException as e:
            form.errors['database'] = str(e)

    avg_rating = 0
    if len(reviews):
        for review in reviews:
            avg_rating += review.item_rating
        avg_rating /= len(reviews)
        avg_rating = round(avg_rating, 2)

    return render_template('reviews.html', resource=resource, reviews=reviews, avg_rating=avg_rating, form=form)

@app.route('/search', methods=['GET'])
@login_required
def search_page(resources=None):
    resources = [] if resources is None else resources
    return render_template('search-resources.html', resources=resources, form=forms.SearchFormFactory.form(), categories=categories, levels=levels)

@app.route('/delete/<resource_id>', methods=['POST', 'GET'])
@login_required
def delete(resource_id):
    user = current_user.username
    db.session.execute('DELETE FROM Resources WHERE teacher_id = :user AND resource_id = :resource_id', dict(resource_id=resource_id, user=user))
    db.session.commit()
    db.session.close()
    flash('Resource deleted successfully')
    return render_template('profile.html')


@app.route('/search', methods=['POST'])
@login_required
def search():
    resources = []

    form = forms.SearchFormFactory.form()
    if form.validate_on_submit():
        try:
            if form.category.data == 'Category' or form.category.data is None:
                resources = db.session.query(models.Resources) \
                    .filter(models.Resources.resource_name.like('%{}%'.format(form.query.data))).limit(10).all()

            elif form.education_level.data == 'Education Level' or form.education_level.data is None:
                resources = db.session.query(models.Resources) \
                    .filter(models.Resources.resource_name.like('%{}%'.format(form.query.data))).limit(10).all()
            else:
                resources = db.session.query(models.Resources) \
                    .filter(models.Resources.resource_name.like('%{}%'.format(form.query.data))) \
                    .filter(models.Resources.category == form.category.data).filter(models.Resources.education_level == form.education_level.data).limit(10).all()

        except BaseException as e:
            form.errors['database'] = str(e)
            return redirect(url_for('home'))

    return render_template('search-resources.html', resources=resources, form=form, categories=categories, levels=levels)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user =  db.session.query(models.Teachers)\
        .filter(models.Teachers.username == current_user.username).one()

    rating = db.session.execute('SELECT AVG(item_rating) FROM reviews WHERE teacher_id=:teacher_id', dict(teacher_id=current_user.username)).first()[0]

    resources_provided = db.session.query(models.Resources)\
        .filter(models.Resources.teacher_id == current_user.username).all()

    return render_template('profile.html', user=user, resources_provided=resources_provided, rating=rating)

@app.route('/edit-user', methods=['GET', 'POST'])
@login_required
def edit_user():
    form = forms.UserEditFormFactory.form(current_user)

    if form.validate_on_submit():
        form.errors.pop('database', None)
        models.Teachers.edit(current_user.username, form.name.data, form.location.data, form.subjects.data, form.education_level.data, form.bio.data)
        return redirect(url_for('profile'))
    return render_template('edit-user.html', user=current_user, form=form)

@login_manager.user_loader
def load_user(user_id):
    return models.Teachers.query.get(user_id) #check this later for bugs

@app.route('/register', methods = ['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        name = request.form.get('name')
        location = request.form.get('location')
        subjects = request.form.get('subjects')
        education_level = request.form.get('education level')
        bio = request.form.get('bio')
        maiden = request.form.get('maiden')

        existing = models.Teachers.query.filter_by(username=username).first()
        if existing:
         flash('There already exists an account with this username. Please register with a different username.')
         return redirect(url_for('register')) # username already in use
        else:
            new_teacher = models.Teachers(username=username, password=password, name=name, location=location, subjects=subjects, education_level=education_level, bio=bio, maiden=maiden)
            db.session.add(new_teacher)
            db.session.commit()
            db.session.close()
            return redirect(url_for('login'))
    else:
        return render_template("register.html")

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        teacher = models.Teachers.query.filter_by(username=username).first()
        # take the user-supplied password, hash it, and compare it to hashed password in the database
        if (teacher is None) or (teacher.password != password):
            flash('Incorrect username/password combination.')
            return redirect(url_for('login'))
        else:
            print('WE DA BEST')
            # if the above check passes, then we know the user has the right credentials
            login_user(teacher, remember=remember)
            return redirect(url_for('profile'))
    else:
        return render_template('login.html')

@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        username = request.form.get('username')
        maiden = request.form.get('maiden')
        teacher = models.Teachers.query.filter_by(username=username).first()

        # take the user-supplied password, hash it, and compare it to hashed password in the database
        if (teacher is None) or (teacher.maiden != maiden):
            flash('Incorrect username/security answer combination.')
            return redirect(url_for('forgot')) # user doesn't exist or password is wrong, reload the page

        # if the above check passes, then we know the user has the right credentials
        else:
            password_reset_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
            password_reset_url = url_for(
            'reset_with_token',
            token = password_reset_serializer.dumps(username, salt='password-reset-salt'),
            _external=True)
            return redirect(password_reset_url) #redirects to password reset page
    else:
        return render_template("forgot.html")

@app.route('/reset/<token>')
def reset_with_token(token):
    password_reset_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    try:
        password_reset_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        username = password_reset_serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except:
        flash('The password reset link is invalid or has expired.', 'error')
        return redirect(url_for('login'))

    return render_template('reset_with_token.html', token=token)

@app.route('/reset/<token>', methods=['POST'])
def reset_post(token):
    password_reset_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    password = request.form.get('password')

    try:
        username = password_reset_serializer.loads(token, salt='password-reset-salt', max_age=3600)
        teacher = models.Teachers.query.filter_by(username=username).first()
    except:
        traceback.print_exc()
        flash('Invalid username!', 'error')
        return redirect(url_for('login'))

    updatedPassword = password
    print("TEACHER", teacher)
    db.session.execute('UPDATE teachers SET password=:password WHERE username=:username', dict(password=updatedPassword, username=username))
    db.session.commit()
    db.session.close()
    flash('Your password has been updated!', 'success')
    return redirect(url_for('login'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.template_filter('pluralize')
def pluralize(number, singular='', plural='s'):
    return singular if number == 1 else plural

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
