import os
import librosa
import noisereduce as nr
import mysql.connector
import numpy as np
from transformers import pipeline
import torch
import whisper
import soundfile as sf  # Using soundfile to write WAV files
from gtts import gTTS  # For TTS

# Warn if CUDA is not available
if not torch.cuda.is_available():
    print("Warning: CUDA is not available. Running Whisper on CPU.")

# Load the Whisper model (load once for efficiency)
model = whisper.load_model("base")

# MySQL configuration – update these values if needed
DB_CONFIG = {
    'host': 'localhost',      # Use your MySQL host
    'port': 3307,             # Use your MySQL port
    'user': 'root',
    'password': 'password',
    'database': 'Meeting_Assistant',
}

def process_audio(file_path):
    """
    Preprocesses audio by loading it, reducing noise, and resampling to 16kHz.
    """
    try:
        y, sr = librosa.load(file_path, sr=None)
        print(f"Original sample rate: {sr}, Audio duration: {len(y)/sr:.2f}s")
        reduced_noise = nr.reduce_noise(y=y, sr=sr)
        reduced_noise = np.nan_to_num(reduced_noise, nan=0.0, posinf=0.0, neginf=0.0)
        target_sr = 16000
        resampled_audio = librosa.resample(reduced_noise, orig_sr=sr, target_sr=target_sr)
        output_path = os.path.splitext(file_path)[0] + "_processed.wav"
        sf.write(output_path, resampled_audio, target_sr)
        return output_path
    except Exception as e:
        raise RuntimeError(f"Error processing audio: {str(e)}")

def transcribe_audio(file_path):
    """
    Transcribes audio using Whisper.
    """
    try:
        result = model.transcribe(file_path)
        transcription = result['text']
        return transcription
    except Exception as e:
        raise RuntimeError(f"Error transcribing audio: {str(e)}")

def summarize_text(text):
    """
    Summarizes text and extracts key points using Hugging Face transformers.
    If text is less than 50 words, returns it as is.
    If text is very long (>1024 characters), truncates it.
    """
    try:
        words = text.split()
        if len(words) < 50:
            return text, [text]
        if len(text) > 1024:
            text = text[:1024]
        summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
        summary_output = summarizer(text, max_length=500, min_length=500, do_sample=False, truncation=True)
        summary = summary_output[0]['summary_text']
        key_points = summary.split(". ")
        return summary, key_points
    except Exception as e:
        raise RuntimeError(f"Error summarizing text: {str(e)}")

def text_to_speech(summary_text, output_file="audio_summary.mp3"):
    """
    Converts summary text to speech and saves it as an MP3 file.
    """
    try:
        tts = gTTS(text=summary_text, lang='en')
        tts.save(output_file)
        return output_file
    except Exception as e:
        raise RuntimeError(f"Error generating audio summary: {str(e)}")

def save_to_database(filename, transcription, summary, key_points):
    """
    Saves transcription, summary, and key points to a MySQL database.
    """
    connection = None
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audio_data (
                id INT AUTO_INCREMENT PRIMARY KEY,
                filename VARCHAR(255),
                transcription TEXT,
                summary TEXT,
                key_points TEXT,
                upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        key_points_str = "; ".join(key_points)
        query = """
            INSERT INTO audio_data (filename, transcription, summary, key_points)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (filename, transcription, summary, key_points_str))
        connection.commit()
        print("Data saved successfully to the database.")
    except mysql.connector.Error as err:
        raise RuntimeError(f"Error connecting to MySQL: {err}")
    finally:
        if connection is not None and connection.is_connected():
            cursor.close()
            connection.close()

def process_and_summarize_audio(file_path):
    """
    Integrates the full workflow: process audio, transcribe, summarize, TTS, and save to DB.
    """
    try:
        processed_audio_path = process_audio(file_path)
        transcription = transcribe_audio(processed_audio_path)
        summary, key_points = summarize_text(transcription)
        tts_file = text_to_speech(summary)
        save_to_database(os.path.basename(file_path), transcription, summary, key_points)
        return {
            "processed_audio": processed_audio_path,
            "transcription": transcription,
            "summary": summary,
            "key_points": key_points,
            "tts_file": tts_file
        }
    except Exception as e:
        raise RuntimeError(f"Error processing and summarizing audio: {str(e)}")