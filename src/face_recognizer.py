import face_recognition
import os
import numpy as np
from PIL import Image, ImageOps

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_KNOWN_FACES_DIR = os.path.join(SCRIPT_DIR, "..", "data", "known_faces")

def load_image_with_correct_orientation(path):
    image = Image.open(path)
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")
    return np.array(image)

import re

def load_known_faces(known_faces_dir=DEFAULT_KNOWN_FACES_DIR):
    known_encodings = []
    known_names = []

    for filename in os.listdir(known_faces_dir):
        if filename.lower().endswith((".jpg", ".jpeg", ".png")):
            path = os.path.join(known_faces_dir, filename)
            image = load_image_with_correct_orientation(path)
            encodings = face_recognition.face_encodings(image)

            if encodings:
                name = os.path.splitext(filename)[0]
                name = re.sub(r"[\s_-]*\d+$", "", name)
                known_encodings.append(encodings[0])
                known_names.append(name)
            else:
                print(f"Warning: no face found in {filename}, skipping.")

    return known_encodings, known_names

def locate_faces(frame):
    return face_recognition.face_locations(frame)

def recognize_face(frame, known_encodings, known_names, tolerance=0.45, min_margin=0.1):
    face_locations = face_recognition.face_locations(frame)
    face_encodings = face_recognition.face_encodings(frame, face_locations)

    names = []
    for encoding in face_encodings:
        name = "Unknown"
        face_distances = face_recognition.face_distance(known_encodings, encoding)

        if len(face_distances) > 0:
            sorted_indices = face_distances.argsort()
            best_index = sorted_indices[0]
            best_distance = face_distances[best_index]

            if best_distance <= tolerance:
                if len(sorted_indices) > 1:
                    second_distance = face_distances[sorted_indices[1]]
                    margin = second_distance - best_distance
                    if margin >= min_margin or known_names[best_index] == known_names[sorted_indices[1]]:
                        name = known_names[best_index]
                else:
                    name = known_names[best_index]

        names.append(name)

    return names, face_locations

if __name__ == "__main__":
    import cv2

    known_encodings, known_names = load_known_faces()
    print(f"Loaded {len(known_names)} known faces: {known_names}")

    cap = cv2.VideoCapture(0)

    frame_count = 0
    process_every_n_frames = 3
    last_names = []
    last_face_locations = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        if frame_count % process_every_n_frames == 0:
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)

            names, face_locations = recognize_face(small_frame, known_encodings, known_names)

            scaled_locations = []
            for (top, right, bottom, left) in face_locations:
                scaled_locations.append((top * 4, right * 4, bottom * 4, left * 4))

            last_names = names
            last_face_locations = scaled_locations

        for (top, right, bottom, left), name in zip(last_face_locations, last_names):
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 255, 0), 2)

        cv2.imshow("ProxyGuard - Face Recognition Test", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()