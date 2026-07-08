# src/test_face_continuity.py
# ponytail: single runnable self-check for the face-continuity guard added to
# fix the identity/liveness proxy-swap loophole (see docs/bugs.md). Not a full
# test suite -- just enough to catch a broken distance threshold.

from main import _face_box_close

FRAME_WIDTH = 640


def _box(center_x, center_y, size=100):
    half = size / 2
    return (center_y - half, center_x + half, center_y + half, center_x - half)  # (top, right, bottom, left)


if __name__ == "__main__":
    same_spot = _box(300, 200)
    nearby = _box(320, 210)
    far_away = _box(550, 200)

    assert _face_box_close(same_spot, same_spot, FRAME_WIDTH) is True
    assert _face_box_close(same_spot, nearby, FRAME_WIDTH) is True
    assert _face_box_close(same_spot, far_away, FRAME_WIDTH) is False
    assert _face_box_close(None, same_spot, FRAME_WIDTH) is False

    print("face continuity self-check passed")
