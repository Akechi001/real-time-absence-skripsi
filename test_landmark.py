import cv2
import insightface
import numpy as np

app = insightface.app.FaceAnalysis(
    name='buffalo_l',
    allowed_modules=['detection', 'landmark_2d_106']
)
app.prepare(ctx_id=-1, det_size=(320, 320))

cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    faces = app.get(frame)

    for face in faces:
        landmarks = face.landmark_2d_106
        if landmarks is None:
            continue

        # Gambar SEMUA landmark dengan nomor
        for i, point in enumerate(landmarks):
            x, y = int(point[0]), int(point[1])
            cv2.circle(frame, (x, y), 1, (0, 255, 0), -1)
            cv2.putText(frame, str(i), (x+2, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.25, (255, 255, 255), 1)

    cv2.imshow("Landmark Test", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()