
# ProxyGuard: A Liveness-Aware Face Recognition System for Proxy Attendance Detection

## Group Members

- **MOHAMAD AMIR IZZAT BIN ROSDI** — 2025394889
- **MUHAMMAD ADLI FADHLAN BIN AZAME** — 2025180775
- **MUHAMMAD IZZUDDIN BIN IZAD EMI** — 2025181293

## 1. Background

Universities are increasingly adopting face recognition-based attendance systems to replace manual roll calls. However, many existing systems verify identity only at a single point in time. This creates an opportunity for proxy attendance, where a student may use a photo, video, or facial data belonging to a registered classmate to check in on their behalf.

This weakness reduces the reliability of automated attendance systems and is a common concern in lecture halls and laboratory sessions.

## 2. Problem Statement

Existing face recognition attendance systems often lack mechanisms to confirm that the person being captured is physically present and actively participating in the check-in process.

Proxy attendance may still occur through:

- Static photographs
- Pre-recorded videos
- Repeated or identical facial poses
- Replay-based spoofing attempts

As a result, the recorded attendance may not accurately reflect the actual presence of students.

## 3. Objectives

1. To design a face recognition module capable of identifying registered students from a live camera feed.
2. To implement a multi-factor liveness detection mechanism that combines:
   - Blink detection
   - Head movement tracking
   - A randomized audio response challenge
3. To flag and log suspicious check-in patterns, such as repeated facial angles, failed liveness checks, or insufficient micro-movement across multiple attendance attempts.

## 4. Proposed Method

The system will use OpenCV to localize faces using a pre-trained face detector such as Haar Cascade or MTCNN. A pre-trained face recognition model, such as FaceNet or dlib, will then be used to verify the identity of registered students.

For liveness detection, MediaPipe Face Mesh will analyze:

- Eye-blink patterns
- Head-pose changes
- Facial movement across video frames

The system will also generate a short randomized audio challenge that students must read aloud to verify real-time presence and response.

A simple rule-based or machine learning classifier will evaluate the check-in attempt. Any attempt that fails the liveness criteria or shows suspicious repeated patterns will be flagged for lecturer review.

## 5. Expected Outcome

The expected outcome is a working prototype of an attendance system with a webcam-based interface that integrates:

- Face recognition
- Multi-factor liveness verification
- Suspicious attempt detection
- Attendance logging

The system is expected to reduce proxy attendance by identifying invalid or suspicious check-in attempts and alerting lecturers for review. This will provide more reliable attendance records than traditional face recognition systems.