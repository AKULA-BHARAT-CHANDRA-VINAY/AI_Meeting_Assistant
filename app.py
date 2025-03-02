from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from utilities import process_audio, transcribe_audio, summarize_text, save_to_database, text_to_speech
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './app/audio_files'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/api/upload_audio', methods=['POST'])
def upload_audio_api():
    try:
        if 'audio_file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files['audio_file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        # Save the original audio file
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # Process the audio (noise reduction, resampling, etc.)
        clean_audio_path = process_audio(file_path)
        
        # Transcribe the processed audio
        transcription = transcribe_audio(clean_audio_path)
        
        # Summarize the transcription text
        summary, key_points = summarize_text(transcription)
        
        # Generate a TTS audio summary from the text summary
        audio_summary_file = text_to_speech(summary)
        
        # Save the transcription and summary data to the database
        save_to_database(filename, transcription, summary, key_points)

        return jsonify({
            "filename": filename,
            "transcription": transcription,
            "summary": summary,
            "key_points": key_points,
            "audio_summary_file": audio_summary_file
        }), 200

    except Exception as e:
        # Log your error (if needed) and return a 500 status code.
        return jsonify({"error": str(e)}), 500

@app.route('/api/process_text', methods=['POST'])
def process_text_api():
    try:
        data = request.json
        text = data.get("text", "")
        if not text:
            return jsonify({"error": "Empty text"}), 400

        summary, key_points = summarize_text(text)
        return jsonify({"summary": summary, "key_points": key_points}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
    # app.run(debug=True)
