from proglog import ProgressBarLogger
import os
from flask import Flask, jsonify, request, render_template, redirect, url_for,send_file
from moviepy.editor import VideoFileClip, concatenate_videoclips
from flask_cors import CORS,cross_origin
from flask_socketio import SocketIO
import asyncio
import eventlet
import subprocess

app = Flask(__name__)
#socketio = SocketIO(app, cors_allowed_origins='*')
socketio = SocketIO(app, cors_allowed_origins='*',async_mode='eventlet')  # <-- Add async_mode='eventlet'

class MyBarLogger(ProgressBarLogger):
    def callback(self, **changes):
        # Every time the logger message is updated, this function is called with
        # the `changes` dictionary of the form `parameter: new value`.
        for (parameter, value) in changes.items():
            print ('Parameter %s is now %s' % (parameter, value))
    
    def bars_callback(self, bar, attr, value,old_value=None):
        # Every time the logger progress is updated, this function is called        
        percentage = "{:.2f}".format((value / self.bars[bar]['total']) * 100)
        self.sendProgress(percentage,bar)
        #print(percentage)
        print(bar,attr,percentage)
    def sendProgress(self,percentage,bar):
        socketio.emit('progress', {'progress': percentage,'bar':bar})
        eventlet.sleep(0)

logger = MyBarLogger()




# #===============MOVIEPY=====================================================================
# def write_video_with_progress(final_clip, output_path, codec='libx264'):
#     total_frames = int(final_clip.fps * final_clip.duration)
#     final_clip.write_videofile(output_path, codec=codec, verbose=False,logger=logger)
# #==================end moviepy============================================================

#=================FFMPEG==================================================================
def write_video_with_progress(final_clip, output_path, codec='libx264'):
    total_frames = int(final_clip.fps * final_clip.duration)

    # Replace moviepy write_videofile with ffmpeg command
    command = [
        'ffmpeg',
        '-y',  # Overwrite output file if it exists
        '-f', 'rawvideo',
        '-s', f'{final_clip.size[0]}x{final_clip.size[1]}',
        '-pix_fmt', 'rgb24',
        '-r', str(final_clip.fps),
        '-i', '-',
        '-c:v', codec,
        '-preset', 'medium',  # Adjust the preset based on your needs
        output_path
    ]

    process = subprocess.Popen(command, stdin=subprocess.PIPE)

    for i, frame in enumerate(final_clip.iter_frames(fps=final_clip.fps, dtype='uint8')):
        process.stdin.write(frame.tobytes())
        
        # Send progress every 10 frames (adjust as needed)
        if i % 10 == 0 and socketio:
            progress = (i / total_frames) * 100
            progress="{:.2f}".format(progress)
            print("Progress===:",progress)
            socketio.emit('progress', {'progress': progress})
            eventlet.sleep(0)

    process.stdin.close()
    process.wait()

    if socketio:
        socketio.emit('process_complete')
#==================================END FFMPEG===============================================




CORS(app, origins=["*"], supports_credentials=True)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'video' not in request.files:
        return "No file part"

    file = request.files['video']

    if file.filename == '':
        return "No selected file"

    if file:
        filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filename)
        return 'File uploaded successfully'


@app.route('/download')
def download_file():
    output_path = 'output.mp4'
    return send_file(output_path, as_attachment=True)








@cross_origin(origin="*", headers=["Content-Type", "Authorization"], methods=["POST"])
@app.route('/join', methods=['POST'])
def join_videos():
    data = request.get_json()
    filenames = data.get('filenames', [])

    if len(filenames) < 2:
        return jsonify({'error': 'At least two filenames are required for joining.'})
    

    

    video_clips = [VideoFileClip(f"uploads/{filename}") for filename in filenames]

    # Concatenate the video clips
    final_clip = concatenate_videoclips(video_clips,method="compose")

    # Save the final video
    output_path = 'output.mp4'
    write_video_with_progress(final_clip, output_path,'h264_nvenc')
    socketio.emit('process_complete')
    return jsonify({'message': f'Video joined successfully. Output saved at {output_path}'})

if __name__ == '__main__':
    #app.run(debug=True)
    #socketio.run(app, debug=True)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
