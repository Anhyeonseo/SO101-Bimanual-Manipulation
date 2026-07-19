# STM32 단일 팔 실기 Bring-up 체크리스트

## A. 도구와 보드 식별

- [ ] STM32CubeIDE 설치
- [ ] STM32CubeG4 package 설치 확인
- [ ] NUCLEO PCB의 MB1367 revision 기록
- [ ] ST-LINK firmware version 기록
- [ ] ST-LINK SWD 연결 확인
- [ ] Virtual COM Port 번호 기록
- [ ] 빈 firmware build/flash/debug 확인

## B. 전원 차단 상태 배선

- [ ] NUCLEO USB 분리
- [ ] Servo 12 V 전원 분리
- [ ] Waveshare adapter 점퍼 `A` 확인
- [ ] NUCLEO–adapter 공통 GND 연결
- [ ] adapter RX–MCU RX 연결 확인
- [ ] adapter TX–MCU TX 연결 확인
- [ ] 12 V가 NUCLEO 3V3/5V/VIN에 연결되지 않았음을 확인
- [ ] servo adapter UART idle voltage 확인
- [ ] servo power 극성과 정격 확인

## C. 무동작 NUCLEO 시험

- [ ] servo adapter를 분리한 상태로 firmware boot
- [ ] reset 후 `SAFE_DISABLED`
- [ ] VCP diagnostics 수신
- [ ] ARM/ENABLE 없이 actuator output 없음
- [ ] 잘못된 CRC/version/message 거부
- [ ] VCP 분리·재연결 후 `SAFE_DISABLED` 유지

## D. Read-only servo bus

- [ ] 팔 주변 충돌 물체 제거
- [ ] 즉시 전원 차단 가능한 위치 확보
- [ ] torque write 경로가 compile-time 또는 runtime으로 비활성인지 확인
- [ ] servo 전원 인가 시 비명령 동작 없음
- [ ] ID 1~6 ping
- [ ] ID 0, 7 등 잘못된 ID가 silent인지 확인
- [ ] position feedback 100회 반복
- [ ] speed/load/voltage feedback 확인
- [ ] timeout/checksum error 수 기록
- [ ] UART transaction p50/p95/max 기록

## E. 제한 동작 전 게이트

- [ ] ID–joint mapping 기록
- [ ] joint별 sign 기록
- [ ] current raw 기록
- [ ] 보수적 raw min/max 기록
- [ ] calibration hash 생성
- [ ] firmware와 host configuration hash 일치
- [ ] target clamp와 out-of-range reject 시험
- [ ] heartbeat loss 시험 계획 준비

이 체크리스트 E까지 완료되기 전에는 여섯 servo의 전체 팔 trajectory를 실행하지 않는다.
