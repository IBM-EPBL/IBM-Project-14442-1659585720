from flask import Flask, app, request, render_template
import os
import flask
import re
import flask_login
import base64
from PIL import Image
from io import BytesIO
import datetime
import cv2
import numpy as np
from tensorflow.keras.models import load_model
from cloudant.client import Cloudant
from cloudant.error import CloudantException
from cloudant.result import Result, ResultByKey


model1 = load_model('Model/level.h5')
model2 = load_model('Model/body.h5')


def detect(frame,model1,f):
    img = cv2.resize(frame,(244,244))
    img = cv2.cvtColor(img,cv2.COLOR_BGR2RGB)
    if(np.max(img)>1):
        img=img/255.0
    img = np.array([img])

    prediction = model1.predict(img)
    if(f):
        label= ['front','rear','side']
    else:
        label =['minor','moderate','severe']
    preds = label[np.argmax(prediction)]
    return preds



client = Cloudant.iam('862d725c-4fb3-4619-bfcb-083c11c6a979-bluemix','QM5pS9ePdxMpe6Lh-8yIvNYoZ3SXtoIdQQKnyIRYlwFb',connect=True)
name = 'name'
email = 'a@b.c'
password = '123'

user_database = client.create_database('user_database')
user_image_database = client.create_database('user_image_database')

def image_database_updation(name,email,imagestr):
    global user_image_database
    now = datetime.datetime.now()
    json_image_document={
        'name':name,
        'email':email,
        'image':imagestr,
        'datetime':now.strftime("%m/%d/%Y, %H:%M:%S") 
    }
    new_image_document  = user_image_database.create_document(json_image_document)
    if(new_image_document.exists()):
        print('database updated')
    else:
        print('database couldn\'t be edited')
    return

def image_database_retrieval():
    global user_image_database
    image_result_retrieved = Result(user_image_database.all_docs,include_docs=True)
    image_result ={}
    for i in image_result_retrieved:
        if(i['doc']['email'] in image_result.keys()):
            # like current date> rx date('str')
            n = datetime.datetime.strptime(i['doc']['datetime'],'%m/%d/%Y, %H:%M:%S')  
            o = datetime.datetime.strptime(image_result[i['doc']['email']]['date'],'%m/%d/%Y, %H:%M:%S')  
            if(n>o):

                image_result[i['doc']['email']] = {'name':i['doc']['name'],'image':i['doc']['image'],'date':i['doc']['datetime']}
        else:
            image_result[i['doc']['email']] = {'name':i['doc']['name'],'image':i['doc']['image'],'date':i['doc']['datetime']}
    return(image_result)

def database_updation(name,email,password):
    global user_database
    jsonDocument = {
        'name':name,
        'email':email,
        'password':password
    }
    newDocument = user_database.create_document(jsonDocument)
    if(newDocument.exists()):
        print('database updated')
    else:
        print('database couldn\'t be edited')
    return
#database_updation(name,email,password)

def database_retrieval():
    global user_database
    result_retrieved = Result(user_database.all_docs,include_docs=True)
    #print(list(result_retrieved))
    result = {}
    for i in list(result_retrieved):
        result[i['doc']['email']]={'name':i['doc']['name'],'password':i['doc']['password']}
    return result
#print(database_retrieval())
app = Flask(__name__)
app.secret_key = 'apple'
login_manager = flask_login.LoginManager()

login_manager.init_app(app)
users = {'a@b.c': {'password': '123'}}
class User(flask_login.UserMixin):
    pass


@login_manager.user_loader
def user_loader(email):
    data = database_retrieval()
    if email not in data:
        return

    user = User()
    user.id = email
    user.name = data[email]['name']
    return user


@login_manager.request_loader
def request_loader(request):
    email = request.form.get('email')
    data = database_retrieval()
    if email not in data:
        return

    user = User()
    user.id = email
    user.name = data[email]['name']
    return user
@app.route('/')
def index():
    if(flask_login.current_user.is_authenticated):
        return render_template('dashboard.html')
    else:
        return flask.redirect(flask.url_for('login'))

@app.route('/register',methods = ['GET','POST'])
def register():
    data = database_retrieval()
    if(flask.request.method == 'GET'):
        return render_template('register.html')
    email = flask.request.form['email']
    if(email in data):
        return render_template('register.html',flash_message='True')
    else:
        database_updation(flask.request.form['name'],email,flask.request.form['password'])
        #users[email]={'password':flask.request.form['password']}
        user  = User()
        user.id = email
        user.name = flask.request.form['name']
        flask_login.login_user(user)
        return render_template('dashboard.html',flash_message='True')



@app.route('/login',methods =['GET','POST'])
def login():
    data = database_retrieval()
    if(flask.request.method == 'GET'):
        
        return render_template('login.html',flash_message='False')
    email = flask.request.form['email']
    if(email in data and flask.request.form['password']==data[email]['password']):
        user  = User()
        user.id = email
        flask_login.login_user(user)
        return render_template('dashboard.html',flash_message='Fal')
    #flask.flash('invalid credentials !!!')
    return render_template('login.html',flash_message="True")
    #error = 'inavlid credentials')


@app.route('/dashboard',methods = ['GET','POST'])
@flask_login.login_required
def dashboard():
    if(flask.request.method == 'GET'):
        return render_template('dashboard.html',flash_message='False')
    email = flask.request.form['email']
    if(email in users and flask.request.form['password']==users[email]['password']):
        user  = User()
        user.id = email
        flask_login.login_user(user)
        return render_template('dashboard.html',flash_message="Fal")
    return render_template('dashboard.html',flash_message="Fals")


@app.route('/logout')
@flask_login.login_required
def logout():
    flask_login.logout_user()
    return render_template('logout.html')


@app.route('/prediction',methods = ['GET','POST'])
@flask_login.login_required
def prediction():
    from tensorflow.keras.models import load_model


    model1 = load_model('Model/level.h5')
    model2 = load_model('Model/body.h5')

    if(flask.request.method=='POST'):
        img = flask.request.files['myFile']
        try:
            os.remove('static\imagedata\save.png')
        except:
            pass
        imgstr = base64.b64encode(img.read()).decode('utf-8')
        image_database_updation(flask_login.current_user.name,flask_login.current_user.id,imgstr)
        data = image_database_retrieval()
        print(flask_login.current_user.id)
        #print(len(base64.b64decode(data[flask_login.current_user.id]['image'].strip())))
        image = Image.open(BytesIO(base64.b64decode(data[flask_login.current_user.id]['image'])))
        img_retrived = np.array(image)
        '''img_retrived = np.asarray(base64.b64decode(data[flask_login.current_user.id]['image']))
        print(data[flask_login.current_user.id]['image'])
        print(img_retrived.shape)'''
        #img_retrived = np.resize(img_retrived,(244,244))
        img_retrive = Image.fromarray(img_retrived)
        img_retrive.save('static\imagedata\save.png')
        '''img_retrived = np.frombuffer(
            BytesIO(
                base64.b64decode(data[flask_login.current_user.id]['image'])
                )
            )'''
        print('################################')
        result1=detect(img_retrived,model1=model2,f=True)
        result2 = detect(img_retrived,model1=model1,f=False)
        value=''
        if(result1 == 'front' and result2 == 'minor'):
            value = '3000 - 5000 INR'
        elif(result1 == 'front' and result2 == 'moderate'):
            value = '6000 - 8000 INR'
        elif(result1 == 'front' and result2 == 'severe'):
            value = '9000 - 11000 INR'
        elif(result1 == 'rear' and result2 == 'minor'):
            value = '4000 - 6000 INR'
        elif(result1 == 'rear' and result2 == 'moderate'):
            value = '7000 - 9000 INR'
        elif(result1 == 'rear' and result2 == 'severe'):
            value = '11000 - 13000 INR'
        elif(result1 == 'side' and result2 == 'minor'):
            value = '6000 - 8000 INR'
        elif(result1 == 'side' and result2 == 'moderate'):
            value = '900 - 11000 INR'
        elif(result1 == 'side' and result2 == 'severe'):
            value = '12000 - 15000 INR'
        else:
            value = '16000 - 50000 INR'
        print(result1,result2,value)
        print('################################')
        img_retrived = Image.fromarray(img_retrived)
        img_retrived.save('static\imagedata\save.png')
        print('image uploaded and retrieved')
        return render_template('prediction.html',prediction_text='{}'.format(value),flash_message='False')

    return render_template('prediction.html',flash_message='True')

if __name__ == '__main__':
    app.run(debug=True)