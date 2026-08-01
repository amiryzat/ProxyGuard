
import random
import speech_recognition as sr

WORD_TO_DIGIT = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"
}


def generate_challenge_number():
    return str(random.randint(100, 999))


def extract_digits(text):
    digits = ""
    for word in text.lower().split():
        if word.isdigit():
            digits += word
        elif word in WORD_TO_DIGIT:
            digits += WORD_TO_DIGIT[word]
    return digits


def get_digit_matches(expected_number, transcript):
    """
    Compares each digit of expected_number against the digit at the same
    position in the spoken transcript, so the caller can highlight
    individual digits (e.g. green/red on screen) instead of only a single
    pass/fail for the whole number.
    """
    spoken_digits = extract_digits(transcript)
    return [
        i < len(spoken_digits) and spoken_digits[i] == digit
        for i, digit in enumerate(expected_number)
    ]


def listen_for_number(expected_number, timeout=5, phrase_time_limit=5):
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        except sr.WaitTimeoutError:
            return False, "no speech detected"

    try:
        transcript = recognizer.recognize_google(audio)
    except sr.UnknownValueError:
        return False, "could not understand"
    except sr.RequestError:
        return False, "speech service error"

    spoken_digits = extract_digits(transcript)
    return spoken_digits == expected_number, transcript