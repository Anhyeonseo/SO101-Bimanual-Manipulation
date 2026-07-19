# ADR-0005: 카메라와 정책 구현 순서

- 상태: Accepted
- 날짜: 2026-07-12

## 결정

카메라 관리는 초기 Pi 성능 검증 단계에 구현하지만, 정책 학습은 deterministic Pick and Place 이후 진행한다.

순서:

1. 3-camera capture와 latest-frame scheduler
2. dummy consumer로 Pi/USB 성능 측정
3. Top 카메라 평면 perception
4. 오른팔 deterministic Pick and Place
5. Wrist Visual Servo
6. 양팔 deterministic baseline
7. Isaac Lab structured-state policy
8. shadow mode와 bounded residual

raw image policy가 안전한 하위 제어 계층을 우회하지 않도록 한다.

