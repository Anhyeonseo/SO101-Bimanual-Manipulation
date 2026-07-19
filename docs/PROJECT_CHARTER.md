# 프로젝트 헌장

## 1. 목표

제한된 ARM Linux 플랫폼에서 멀티카메라 인식, MoveIt 기반 경로 계획, ROS 2 프로세스 운영과 STM32 실시간 서보 제어를 통합하고, CPU·메모리·지연·장애 복구·장시간 안정성을 정량적으로 검증한다.

## 2. 포트폴리오 포지셔닝

이 프로젝트의 중심은 단순한 AI 데모가 아니다.

- Embedded firmware: FreeRTOS, UART/DMA, binary protocol, CRC, trajectory buffer, watchdog, fault injection
- Embedded Linux: Headless boot, systemd, udev, bounded camera pipeline, diagnostics, recovery, soak test
- Robotics: URDF, TF, ros2_control, MoveIt, calibration, visual servo, dual-arm scheduling
- Edge AI: ONNX Runtime, inference scheduling, Isaac Lab policy export, bounded policy execution

## 3. 기능 범위

### 1차 범위

- 오른팔 5DOF + gripper
- 고정 작업대의 검은색 마커펜 검출
- Top 카메라 기반 평면 `x, y, yaw` 추정
- 넓은 펜꽂이로 Pick and Place
- 정확도와 안정성 우선

### 단계적 확장

1. Wrist 카메라 기반 마지막 정렬
2. Raspberry Pi Headless 통합
3. 독립 작업 영역의 양팔 병렬 작업
4. 공유 영역의 양팔 충돌 검사와 coordinated stop
5. Isaac Lab structured-state 정책과 Edge 추론
6. 수건 접기

### 초기 비범위

- raw multi-camera end-to-end policy
- Pi에서의 정책 학습
- 고속 동적 장애물 회피
- 안전 인증이 필요한 산업용 운전
- deterministic baseline 없는 정책 직접 제어

## 4. 시스템 경계

```text
Camera → Perception → Structured State → Task/Policy
       → MoveIt or Visual Servo → Command Arbitration
       → JointTrajectoryController → STM32 → Dual Arm
```

Raspberry Pi는 무엇을 할지 결정한다. STM32는 정해진 명령을 시간과 안전 조건에 맞게 실행한다.

## 5. 단계 통과 원칙

각 단계는 다음 다섯 항목을 갖는다.

1. 목표
2. 구현 항목
3. 검증 방법
4. 완료 조건
5. 실패 시 조사 항목

완료 조건을 충족하지 못하면 다음 단계의 실제 하드웨어 동작을 활성화하지 않는다.

## 6. 안전 원칙

- 자동 부팅 후 기본 상태는 `STANDBY`다.
- 동작 전 `ARMING` 검사를 통과해야 한다.
- 장애 복구 후 자동 재활성화하지 않는다.
- 통신 단절은 감속 정지 후 제한 시간 Hold를 기본으로 한다.
- 심각한 fault와 E-stop은 Torque Disable 및 fault latch로 처리한다.
- 한 팔의 심각한 fault는 양팔 coordinated stop으로 연결한다.
- 물리 E-stop 설치 전에는 저속 벤치 시험만 허용한다.

