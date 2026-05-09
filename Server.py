
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import or_

import threading 
from os import path
import os
import time
import glob

import pygame.mixer
import queue
import subprocess

import uyts
from pytube import YouTube

# commands for pi deployment
# path="/home/raspberry/Desktop/Code/"
# os.chdir(path)




app = Flask(__name__)
app.config['SECRET_KEY'] = 'G^TG£$DFOUH*Y_£T*Q(_&F*YG&£Q_())'
CORS(app)  
socketio = SocketIO(app, cors_allowed_origins="*")
engine = create_engine('sqlite:///app_database.db')


dbSession = sessionmaker(bind=engine)
dbsession = dbSession()
Base = declarative_base()

# Define the Album model, currently unused but planned future implementation
class Album(Base):
    __tablename__ = 'albums'
    id = Column(String, primary_key=True)
    name = Column(String)
    author = Column(String)
    artwork = Column(String)

# Define the Song model
class Song(Base):
    __tablename__ = 'songs'
    id = Column(String, primary_key=True)
    name = Column(String)
    author = Column(String)
    duration = Column(Integer)
    album = Column(String)
    # Establish a many-to-one relationship with albums

    status = Column(String, default="") #local, global
    favourite = Column(String, default="no") 

    def serialize(self, user_id=None):
        return {
            'id': self.id,
            'name': self.name,
            'author': self.author,
            'duration': self.duration,
            'album': self.album,
            'status': self.status,
            'favourite': self.is_favorited_by_user(user_id) if user_id else False
        }
    def is_favorited_by_user(self, user_id):
        # Assuming you have a relationship between Song and Favorite
        # and the user_id parameter is the ID of the current user
        favorite = dbsession.query(Favorite).filter_by(userid=user_id, songid=self.id).first()
        return favorite is not None

class User(Base, UserMixin):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True) # primary key
    email = Column(String, unique=True) # unique email
    password = Column(String)
    username = Column(String)
    user_status = Column(String, default="User") #user, admin, staff

    def serialize(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'user_status': self.user_status,
            # 'favourite': self.is_favorited_by_user(user_id) if user_id else False
        }

class Favorite(Base):
    __tablename__ = 'favorites'

    userid = Column(Integer, ForeignKey('users.id'), primary_key=True)
    songid = Column(Integer, ForeignKey('songs.id'), primary_key=True)
    
    user = relationship('User', back_populates='favorites')
    song = relationship('Song', back_populates='favorites')

User.favorites = relationship('Favorite', back_populates='user')
Song.favorites = relationship('Favorite', back_populates='song')

# Create the tables in the database
Base.metadata.create_all(engine)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password1 = request.form.get('password1')
        #user = User.query.filter_by(email=email).first()
        user = dbsession.query(User).filter_by(email=email).first()
        if user:
            if check_password_hash(user.password, password1):
            #if user.password == password1:
                print("---------------------------------logged in")
                flash('Logged in successfully!', category='success')
                login_user(user, remember=True)
                return redirect('/')
            else:
                flash('Incorrect password, try again.', category='error')
        else:
            flash('Email does not exist.', category='error')
    return render_template("Login.html", user=current_user)

@app.route('/logout')
@login_required
def logout():
    print("---------------------------------logged out")
    logout_user()
    session.pop('_flashes', None)
    #session['_flashes'].clear()
    return redirect('/')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        session.pop('_flashes', None)
        username = request.form.get('username')
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')
        print("---------------------------------------------", username, password1, password2, "details recieved")
        if username:
            current_user.username = username
            dbsession.commit()
            flash('Username changed!', category='success')
        if password1:
            if password1 != password2:
                flash('Passwords do not match.', category='error')
            else:
                current_user.password = generate_password_hash(password1, method='sha256')
                dbsession.commit()
                flash('Password changed!', category='success')

        return redirect('/profile') 
    elif request.method == 'GET':
        if current_user.user_status == "Admin":
            return render_template("profile.html", logged_in=current_user.is_authenticated, user_status = 2, username = current_user.username, user = current_user) # Render and return the HTML template for an admin
        else:
            return render_template("profile.html", logged_in=current_user.is_authenticated, user_status = 1, username = current_user.username, user = current_user)  # Render and return the HTML template for a user



@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if current_user.user_status == "Admin":
        return render_template("admin_page.html", userid=current_user.id, logged_in=current_user.is_authenticated, user_status = 2, username = current_user.username) # Render and return the HTML template for an admin
    else:
        return redirect('/')

@socketio.on('adminrefresh')
def adminrefresh():
    print("-------------------------------------------- refreshing admin")
    if current_user.user_status == "Admin":
        songs = dbsession.query(Song).all()
        serialized_songs = [song.serialize() for song in songs]
        socketio.emit('songs_data', {'songs': serialized_songs}, room=request.sid)
               
        users = dbsession.query(User).all()
        serialized_users = [user.serialize() for user in users]
        socketio.emit('users_data', {'users': serialized_users}, room=request.sid)

        print("-------------------------------------------- admin refreshed", serialized_songs, serialized_users)
    
    
@app.route('/register', methods=['GET', 'POST'])
def sign_up():
    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')
        admin=request.form.get('admin') #'on or off
        if admin == "on":
            admin = "Admin"
        else:
            admin = "User"
        user = dbsession.query(User).filter_by(email=email).first()
        
        if user:
            flash('Email already exists.', category='error')
        elif password1 != password2:
            flash('Passwords do not match.', category='error')
        else:
            print(email,username,password1,password2)
            new_user = User(email=email, username=username, password=generate_password_hash(password1, method='sha256'), user_status=admin)

            #new_user = User(email=email, username=username, password=password1, user_status=admin)
            dbsession.add(new_user)
            dbsession.commit()
            login_user(new_user, remember=True)
            flash('Account created!', category='success')
            # next_page = session.pop('next_page', None)
            # if next_page:
            #     return redirect(next_page)
            # else:
            return redirect('/') 
            
    return render_template("Sign_Up.html", user=current_user)

@app.route('/consolepage', methods=['GET'])  # Define a route for the root URL
def consolepage():
    print("-------------------------------------------------- sending page")
    return render_template("console.html")  # Render and return the HTML template for a guest

@app.route('/', methods=['GET'])  # Define a route for the root URL
def adminreturn():
    print("-------------------------------------------------- sending page")
    if current_user.is_authenticated:
        if current_user.user_status == "Admin":
            return render_template("index.html", logged_in=current_user.is_authenticated, user_status = 2, username = current_user.username) # Render and return the HTML template for an admin
        else:
            return render_template("index.html", logged_in=current_user.is_authenticated, user_status = 1, username = current_user.username)  # Render and return the HTML template for a user
    else:
        return render_template("index.html", logged_in=current_user.is_authenticated, user_status = 0)  # Render and return the HTML template for a guest

@app.route('/stable', methods=['GET'])  # Define a route for the root URL
def userreturn():
    return render_template("admin_page.html")  # Render and return the HTML template

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('deletesongs')
def deletesongs():
    if current_user.user_status == "Admin":
        clear()
        stop()
        time.sleep(1)
        dbsession.query(Song).delete()
        # Commit the changes to the database
        dbsession.query(Favorite).delete()
        dbsession.commit()
        files = glob.glob('Song files/Audio/*')
        print(files)
        for f in files:
            os.remove(f)
        print("deleting songs")
  
@socketio.on('deletesong')
def deletesong(data):
    if current_user.user_status == "Admin":
        id = data.get('id')
        print("deleting song", id)
        dbsession.query(Song).filter(Song.id == id).delete()
        dbsession.commit()

@socketio.on('deleteusers')
def deleteusers():
    if current_user.user_status == "Admin":
        dbsession.query(User).filter(User.id != current_user.id).delete()
        dbsession.commit()
        print("deleting users")

@socketio.on('deleteuser')
def deleteuser(data):
    if current_user.user_status == "Admin":
        id = data.get('id')
        print("deleting user", id)
        dbsession.query(User).filter(User.id == id).delete()
        dbsession.commit()

@socketio.on('favourite')
def favourite(data):
    print("--------------------------- favourite")
    song_id = data.get('songId')
    user_id = current_user.id
    song = dbsession.query(Song).filter_by(id=song_id).first()
    user = dbsession.query(User).filter_by(id=current_user.id).first()

    is_favorited = (dbsession.query(Favorite).filter(Favorite.songid == song_id, Favorite.userid == user_id).first())
    if is_favorited:
        dbsession.delete(is_favorited)
        dbsession.commit()
        print("--------------------------- unfavourited")
    else:
        new_favorite = Favorite(userid=user_id, songid=song_id)
        dbsession.add(new_favorite)
        dbsession.commit()
        print("--------------------------- favourited")

    search(data)

@socketio.on('search')
def search(data):
    search_request = data.get('search').lower()
    if search_request:
        #local results
        results = dbsession.query(Song).filter((Song.name.like(f"%{search_request}%")) |(Song.author.like(f"%{search_request}%"))).all()
        if current_user.is_authenticated:
            serialized_results = [result.serialize(user_id=current_user.id) for result in results]
        else:
            serialized_results = [result.serialize() for result in results]
        for result in serialized_results:
            print("local result found", result['name'], "---------------------------------------", result['favourite'])
        socketio.emit('searchresult', serialized_results, room=request.sid)
        #youtube results MAY RETURN ERROR SO TRY, except
        try:
            search = uyts.Search(search_request, language="en") 
            print("--------------------------------------- results found:", search.resultsCount)

            for result in search.results:  

                if result.resultType == "video" and result.accountType == "music":
                    print("online song found", result.title, "---------------------------------------", result.id)
                    serialized_results.append({
                        'id': result.id,
                        'name': result.title,
                        'author':result.author,
                        'duration': result.duration,
                        'album': "none",
                        'status': "online",
                        'favourite': 'no'
                    })
            if len(serialized_results) == 0:
                print("--------------------------------------- no results found, adding all found")
                for result in search.results:  
                    if result.resultType == "video":
                        print("online song found", result.title, "---------------------------------------", result.id)
                        serialized_results.append({
                            'id': result.id,
                            'name': result.title,
                            'author':result.author,
                            'duration': result.duration,
                            'album': "none",
                            'status': "online",
                            'favourite': 'no'
                        })
                
        except:
            pass
        
        socketio.emit('searchresult', serialized_results, room=request.sid)
    
def download_song(song_id):
    print("creating new song")

    #song download logic:

    # Create a YouTube object from the URL
    yt = YouTube("https://www.youtube.com/watch?v=" + song_id)
    # Get the audio stream
    new_song = Song(id=song_id, name=yt.title, author=yt.author, duration = yt.length, album = None, status="downloading") #------------------------------------
    dbsession.add(new_song) 
    dbsession.commit()
    audio_stream = yt.streams.filter(only_audio=True).first()
    # Download the audio stream
    output_path = 'Song files'
    filename = song_id +"raw.mp3"
    audio_stream.download(output_path=output_path, filename=filename)

    print(f"Audio downloaded to {output_path}/{filename}")

    input_mp3 = "Song files/" + filename
    output_mp3 = "Song files/Audio/" + song_id + ".mp3"
    ffmpeg_path = r"C:/Users/henry/Downloads/ffmpeg-master-latest-win64-gpl/ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe"
    command = [ffmpeg_path, '-i', input_mp3, '-b:a', '192k', output_mp3]
    # command = ["ffmpeg", '-i', input_mp3, '-b:a', '192k', output_mp3]

    # Print the command being executed
    print("Executing command:", " ".join(command))

    subprocess.run(command)
    os.remove("Song files/" + filename)
    update_song = dbsession.query(Song).filter_by(id=song_id).first()
    update_song.status = "local"
    dbsession.commit()
    print("------------------------------------------------------------------------ downlaoded and record added")
    #add song to database:

    
@socketio.on('add_to_playlist')
def add_to_playlist(data):
    song_id = data.get('songId')
    song = dbsession.query(Song).filter_by(id=song_id).first()
    
    if not song:
        # if song is global
        thread3 = threading.Thread(target=download_song, args=(song_id,))
        thread3.daemon = True
        thread3.start()

        # Wait for the thread to complete with a timeout (adjust as needed)
        thread3.join()  # Timeout set to 60 seconds

        # Check if the thread is still alive (not completed)
        if thread3.is_alive():
            print("Download thread is still running. Consider handling this case.")

    # Fetch the updated song from the database
    song = dbsession.query(Song).filter_by(id=song_id).first()

    if song:
        playlist.put(song)
        print("playlist updated:", playlist.queue)
    else:
        print("Song is None. Not adding to the playlist.")
    search(data)

@socketio.on('volume')
def volume(data):
    if data.get('volume') == "up":
        for i in range(10):
            pygame.mixer.music.set_volume(pygame.mixer.music.get_volume() + 0.02)
            time.sleep(0.05)
        print("volume up", pygame.mixer.music.get_volume())

    elif data.get('volume') == "down":
        for i in range(10):
            pygame.mixer.music.set_volume(pygame.mixer.music.get_volume() - 0.02)
            time.sleep(0.05)
        print("volume down", pygame.mixer.music.get_volume())

@socketio.on('remove_from_playlist')
def remove_from_playlist(data):
    print("recieved delete")
    song = data.get('remove_from_playlist')
    # Remove the song from the playlist at the specified index
    playlist_copy = list(playlist.queue)

    removed_song = playlist_copy.pop(int(song))
    playlist.queue.clear()
    for item in playlist_copy:
        playlist.put(item)

    print(f"Removed song from playlist at index {song}: {removed_song.serialize()}")
    



global paused
paused = False
@socketio.on('pause')
def pause():
    global paused
    if paused == False:
        paused = True
        print("pause")
        pygame.mixer.music.pause()
    else:
        paused = False
        print("resume")
        pygame.mixer.music.unpause()

@socketio.on('resume')
def resume():
    global paused
    paused = False
    print("resume")
    pygame.mixer.music.unpause()

@socketio.on('stop')
def stop():
    print("stop")
    # pygame.mixer.music.stop()
    pygame.mixer.music.fadeout(1000)
    pygame.mixer.stop()
    print("fadeout done")
    while not current_song.empty():
        current_song.get()

@socketio.on('clear')
def clear():
    print("clear")
    while not playlist.empty():
        playlist.get()

pygame.init()
SONG_END = pygame.USEREVENT + 1
pygame.mixer.pre_init(44100, -16, 2, 2048)
pygame.mixer.init()
pygame.mixer.music.set_volume(0.5)

current_song = queue.Queue()
playlist = queue.Queue()
# playlist.put(session.query(Song).filter_by(id=1).first())


def play_song(song):
    pygame.mixer.music.set_endevent(SONG_END)
    pygame.mixer.music.load("Song files/Audio/" + song.id + ".mp3")
    pygame.mixer.music.play()
    while True:
        for event in pygame.event.get():
            if event.type == SONG_END:
                while not current_song.empty():
                    current_song.get()
                return  # Song has finished, exit the loop 
    
def play_playlist():
    while True:
        try:
            #time.sleep(2)
            song = playlist.get(block=False)  # Get the next song ID without blocking
            current_song.put(song)
            play_song(song)  # Play the song without creating a new thread
        except queue.Empty:
            time.sleep(1)

def emit_queue():
    global paused
    while True:
        volume = int(pygame.mixer.music.get_volume() * 100)
        if volume == 100:
            volume = 99
        elif volume < 10:
            volume = "0" + str(volume)
        volume = str(volume) + "%"
        socketio.emit('volume', volume)

        socketio.emit('paused', paused)

        queue_copy = list(playlist.queue)
        song_dicts = []
        for song in queue_copy:
            if song is not None:
                song_dicts.append(song.serialize())
        socketio.emit('Queue', song_dicts)

        current_song_copy = list(current_song.queue)
        # if pygame.mixer.music.get_busy() == False:
        #     socketio.emit('currentsong', None)
        if current_song_copy:
            # If the queue is not empty, get and serialize the current song
            current_song_copy = current_song_copy[0]
            current_time = pygame.mixer.music.get_pos() / 1000
            percentage_completetion = current_time / current_song_copy.duration *100
            socketio.emit('currenttime', int(percentage_completetion))
            current_song_copy = current_song_copy.serialize()
            socketio.emit('currentsong', current_song_copy)
        else:
            # If the queue is empty, emit "none" and print a message
            socketio.emit('currentsong', None)
            socketio.emit('currenttime', 0)

        #socketio.emit('remaining time', remaining_time)
        time.sleep(0.1)
        
import serial
try:
    arduino = serial.Serial(port='COM4', baudrate=115200, timeout=.1)
    ser = serial.Serial('COM3', 9600)
    ser = serial.Serial('/dev/ttyACM0', 9600) # Establish the connection on a specific port with the baud rate of 9600
except:
    pass


def console_controls():
    while True:
        try:
    #         ser.timeout = 0.1
    #         raw_data = ser.read_until(b'>').decode('latin-1').strip()
    #         if raw_data.startswith('<') and raw_data.endswith('>'):
    #         decoded_data = raw_data[1:-1].split(',')
              if ser.in_waiting > 0:
                decoded_data = ser.readline().decode('utf-8').rstrip() # Read the incoming data and decode it

                if decoded_data == "d":
                    socketio.emit('tabdown', 'tabdown')

                elif decoded_data == "u":
                    socketio.emit('tabup', 'tabup')

                elif decoded_data == "c":
                    socketio.emit('click', 'click')

        except ValueError as e:
            print("Error:", e)

        time.sleep(0.05)
                
if __name__ == '__main__':
    thread1 = threading.Thread(target=play_playlist)
    thread1.daemon = True
    thread1.start()
    thread2 = threading.Thread(target=emit_queue)
    thread2.daemon = True
    thread2.start() 
    # thread3 = threading.Thread(target=console_controls)
    # thread3.daemon = True
    # thread3.start() 
    
    login_manager = LoginManager()
    login_manager.login_view = 'login'
    login_manager.init_app(app)

    @login_manager.user_loader # decorator
    def load_user(id):
        return dbsession.query(User).filter_by(id=int(id)).first()
    

    socketio.run(app, debug=True, host='0.0.0.0', port=5000, use_reloader=False)#0.0.0.0





