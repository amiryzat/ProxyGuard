# src/face_detector.py
# Handles face detection using OpenCV Haar Cascade.
# This only detects face locations, it does not identify who the face belongs to.
# Identity matching happens later in face_recognizer.py.

import os

import cv2


def initialize_face_detector():
    """
    Loads OpenCV's pretrained Haar Cascade classifier for frontal face detection.
    Returns a CascadeClassifier object ready to use for detection.
    """
    # Resolve relative to the project root (not the current working directory),
    # since run configurations may launch this script with src/ as the cwd.
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cascade_path = os.path.join(project_root, 'data', 'haarcascade_frontalface_default.xml')
    face_cascade = cv2.CascadeClassifier(cascade_path)
    return face_cascade


def detect_faces(frame, face_cascade):
    """
    Detects faces in a given frame.
    Converts the frame to grayscale first since Haar Cascade works on grayscale images.
    Returns a list of face coordinates in the form (x, y, width, height).
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(60, 60)
    )
    return faces


def draw_faces(frame, faces):
    """
    Draws a plain green bounding box around each detected face.
    Name labels are not added here, that will be handled later in main.py
    once face recognition is combined with detection.
    """
    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
    return frame


if __name__ == "__main__":
    # Simple test block to confirm face detection works on your webcam.
    cap = cv2.VideoCapture(0)
    face_cascade = initialize_face_detector()

    if not cap.isOpened():
        print("Error: could not access the webcam.")
    else:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error: failed to grab frame.")
                break

            faces = detect_faces(frame, face_cascade)
            frame = draw_faces(frame, faces)

            cv2.imshow("ProxyGuard - Face Detection Test", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cap.release()
    cv2.destroyAllWindows()