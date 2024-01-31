from app import app, socketio  # assuming your Flask app is in a file named 'app'

if __name__ == '__main__':
    socketio.run(app, debug=True)
