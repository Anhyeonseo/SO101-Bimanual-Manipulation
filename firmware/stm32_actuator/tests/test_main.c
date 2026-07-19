#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "actuator_core/cobs.h"
#include "actuator_core/calibration.h"
#include "actuator_core/crc32c.h"
#include "actuator_core/protocol.h"
#include "actuator_core/safety.h"
#include "actuator_core/setpoint_queue.h"

static int failures = 0;

#define CHECK(condition)                                                               \
    do {                                                                               \
        if (!(condition)) {                                                            \
            fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #condition);      \
            ++failures;                                                                \
            return;                                                                    \
        }                                                                              \
    } while (0)

static void test_crc32c_known_vector(void) {
    static const uint8_t vector[] = "123456789";
    CHECK(actuator_crc32c(vector, sizeof(vector) - 1u) == UINT32_C(0xE3069283));
}

static void test_cobs_round_trip(void) {
    uint8_t input[260];
    uint8_t encoded[264];
    uint8_t decoded[260];
    size_t encoded_length = 0u;
    size_t decoded_length = 0u;
    size_t index;

    for (index = 0u; index < sizeof(input); ++index) {
        input[index] = (uint8_t)(index & 0xFFu);
    }
    input[1] = 0u;
    input[100] = 0u;
    input[259] = 0u;

    CHECK(actuator_cobs_encode(input, sizeof(input), encoded, sizeof(encoded), &encoded_length));
    CHECK(actuator_cobs_decode(encoded, encoded_length, decoded, sizeof(decoded), &decoded_length));
    CHECK(decoded_length == sizeof(input));
    CHECK(memcmp(input, decoded, sizeof(input)) == 0);
}

static void test_calibration_conversion_and_limits(void) {
    const actuator_joint_calibration_t increasing = {2048u, 2048u, 2389u, 1};
    const actuator_joint_calibration_t decreasing = {2048u, 1934u, 2048u, -1};
    uint16_t raw = 0u;
    int32_t urad = 0;

    CHECK(actuator_urad_to_raw(&increasing, 0, &raw) == ACTUATOR_CALIBRATION_OK);
    CHECK(raw == 2048u);
    CHECK(actuator_urad_to_raw(&increasing, 52155, &raw) == ACTUATOR_CALIBRATION_OK);
    CHECK(raw == 2082u);
    CHECK(actuator_urad_to_raw(&decreasing, 52155, &raw) == ACTUATOR_CALIBRATION_OK);
    CHECK(raw == 2014u);
    CHECK(actuator_raw_to_urad(&decreasing, 2014u, &urad) == ACTUATOR_CALIBRATION_OK);
    CHECK(urad == 52155);
    CHECK(actuator_urad_to_raw(&decreasing, 1000000, &raw) ==
          ACTUATOR_CALIBRATION_LIMIT_VIOLATION);
}

static actuator_frame_t make_heartbeat_frame(void) {
    actuator_frame_t frame;
    memset(&frame, 0, sizeof(frame));
    frame.message_type = ACTUATOR_MSG_HEARTBEAT;
    frame.flags = UINT16_C(0x0102);
    frame.sequence = UINT32_C(0x10203040);
    frame.sender_time_ms = 1234u;
    frame.payload_length = 4u;
    frame.payload[0] = 0u;
    frame.payload[1] = 1u;
    frame.payload[2] = 0u;
    frame.payload[3] = 2u;
    return frame;
}

static void test_protocol_round_trip(void) {
    actuator_frame_t source = make_heartbeat_frame();
    actuator_frame_t decoded;
    uint8_t encoded[ACTUATOR_PROTOCOL_MAX_ENCODED_SIZE];
    size_t encoded_length = 0u;

    CHECK(actuator_frame_encode(&source, encoded, sizeof(encoded), &encoded_length) ==
          ACTUATOR_PROTOCOL_OK);
    CHECK(encoded_length > 1u);
    CHECK(encoded[encoded_length - 1u] == 0u);
    CHECK(actuator_frame_decode(encoded, encoded_length - 1u, &decoded) == ACTUATOR_PROTOCOL_OK);
    CHECK(decoded.message_type == source.message_type);
    CHECK(decoded.flags == source.flags);
    CHECK(decoded.sequence == source.sequence);
    CHECK(decoded.sender_time_ms == source.sender_time_ms);
    CHECK(decoded.payload_length == source.payload_length);
    CHECK(memcmp(decoded.payload, source.payload, source.payload_length) == 0);
}

static void test_protocol_rejects_corruption(void) {
    actuator_frame_t source = make_heartbeat_frame();
    actuator_frame_t decoded;
    uint8_t encoded[ACTUATOR_PROTOCOL_MAX_ENCODED_SIZE];
    size_t encoded_length = 0u;

    CHECK(actuator_frame_encode(&source, encoded, sizeof(encoded), &encoded_length) ==
          ACTUATOR_PROTOCOL_OK);
    encoded[encoded_length / 2u] ^= 1u;
    CHECK(actuator_frame_decode(encoded, encoded_length - 1u, &decoded) != ACTUATOR_PROTOCOL_OK);
}

static void test_protocol_accepts_maximum_payload(void) {
    actuator_frame_t source;
    actuator_frame_t decoded;
    uint8_t encoded[ACTUATOR_PROTOCOL_MAX_ENCODED_SIZE];
    size_t encoded_length = 0u;
    size_t index;

    memset(&source, 0, sizeof(source));
    memset(&decoded, 0, sizeof(decoded));
    source.message_type = ACTUATOR_MSG_DIAGNOSTICS;
    source.payload_length = ACTUATOR_PROTOCOL_MAX_PAYLOAD;
    for (index = 0u; index < source.payload_length; ++index) {
        source.payload[index] = (uint8_t)(index & 0xFFu);
    }
    CHECK(actuator_frame_encode(&source, encoded, sizeof(encoded), &encoded_length) ==
          ACTUATOR_PROTOCOL_OK);
    CHECK(encoded_length <= sizeof(encoded));
    CHECK(actuator_frame_decode(encoded, encoded_length - 1u, &decoded) == ACTUATOR_PROTOCOL_OK);
    CHECK(decoded.payload_length == ACTUATOR_PROTOCOL_MAX_PAYLOAD);
    CHECK(memcmp(source.payload, decoded.payload, source.payload_length) == 0);
}

static void test_stream_parser_delivers_complete_frame(void) {
    actuator_frame_t source = make_heartbeat_frame();
    actuator_frame_t decoded;
    actuator_stream_parser_t parser;
    uint8_t encoded[ACTUATOR_PROTOCOL_MAX_ENCODED_SIZE];
    size_t encoded_length = 0u;
    size_t index;
    actuator_protocol_result_t result = ACTUATOR_PROTOCOL_NO_FRAME;

    memset(&decoded, 0, sizeof(decoded));
    actuator_stream_parser_init(&parser);
    CHECK(actuator_frame_encode(&source, encoded, sizeof(encoded), &encoded_length) ==
          ACTUATOR_PROTOCOL_OK);
    for (index = 0u; index < encoded_length; ++index) {
        result = actuator_stream_parser_push(&parser, encoded[index], &decoded);
        if (index + 1u < encoded_length) {
            CHECK(result == ACTUATOR_PROTOCOL_NO_FRAME);
        }
    }
    CHECK(result == ACTUATOR_PROTOCOL_OK);
    CHECK(decoded.sequence == source.sequence);
}

static void test_safety_requires_explicit_arm_and_fresh_heartbeat(void) {
    actuator_safety_t safety;

    actuator_safety_init(&safety, 100u);
    CHECK(safety.state == ACTUATOR_STATE_BOOT);
    CHECK(safety.torque_disable_requested);
    CHECK(actuator_safety_complete_boot(&safety, true) == ACTUATOR_SAFETY_OK);
    CHECK(safety.state == ACTUATOR_STATE_SAFE_DISABLED);
    CHECK(actuator_safety_request_enable(&safety, 0u) == ACTUATOR_SAFETY_BAD_STATE);
    CHECK(actuator_safety_request_arm(&safety, true, true) == ACTUATOR_SAFETY_OK);
    CHECK(actuator_safety_request_enable(&safety, 10u) == ACTUATOR_SAFETY_HEARTBEAT_MISSING);
    actuator_safety_on_heartbeat(&safety, 10u);
    CHECK(actuator_safety_request_enable(&safety, 11u) == ACTUATOR_SAFETY_OK);
    CHECK(actuator_safety_accepts_setpoint(&safety));
}

static void test_safety_heartbeat_timeout_requests_hold(void) {
    actuator_safety_t safety;

    actuator_safety_init(&safety, 50u);
    CHECK(actuator_safety_complete_boot(&safety, true) == ACTUATOR_SAFETY_OK);
    actuator_safety_on_heartbeat(&safety, 100u);
    CHECK(actuator_safety_request_arm(&safety, true, true) == ACTUATOR_SAFETY_OK);
    CHECK(actuator_safety_request_enable(&safety, 100u) == ACTUATOR_SAFETY_OK);
    actuator_safety_tick(&safety, 151u);
    CHECK(safety.state == ACTUATOR_STATE_HOLD);
    CHECK(safety.hold_requested);
    CHECK(!actuator_safety_accepts_setpoint(&safety));
}

static void test_safety_estop_is_latched(void) {
    actuator_safety_t safety;

    actuator_safety_init(&safety, 50u);
    CHECK(actuator_safety_complete_boot(&safety, true) == ACTUATOR_SAFETY_OK);
    actuator_safety_set_estop(&safety, true);
    CHECK(safety.state == ACTUATOR_STATE_ESTOPPED);
    CHECK(safety.torque_disable_requested);
    CHECK(actuator_safety_clear_latched_stop(&safety, true) == ACTUATOR_SAFETY_ESTOP_ASSERTED);
    actuator_safety_set_estop(&safety, false);
    CHECK(actuator_safety_clear_latched_stop(&safety, true) == ACTUATOR_SAFETY_OK);
    CHECK(safety.state == ACTUATOR_STATE_SAFE_DISABLED);
}

static void test_safety_fault_cannot_be_bypassed_by_disable(void) {
    actuator_safety_t safety;

    actuator_safety_init(&safety, 50u);
    CHECK(actuator_safety_complete_boot(&safety, true) == ACTUATOR_SAFETY_OK);
    actuator_safety_report_fault(&safety, UINT16_C(0x0501));
    CHECK(safety.state == ACTUATOR_STATE_FAULT);
    CHECK(actuator_safety_request_disable(&safety) == ACTUATOR_SAFETY_BAD_STATE);
    CHECK(safety.state == ACTUATOR_STATE_FAULT);
    CHECK(actuator_safety_clear_latched_stop(&safety, true) == ACTUATOR_SAFETY_OK);
    CHECK(safety.state == ACTUATOR_STATE_SAFE_DISABLED);
}

static void fill_limits(actuator_joint_limit_t limits[ACTUATOR_JOINT_COUNT]) {
    size_t joint;
    for (joint = 0u; joint < ACTUATOR_JOINT_COUNT; ++joint) {
        limits[joint].minimum_urad = -1000;
        limits[joint].maximum_urad = 1000;
    }
}

static actuator_setpoint_t make_setpoint(uint32_t tick, int32_t position) {
    actuator_setpoint_t sample;
    size_t joint;
    sample.apply_tick = tick;
    for (joint = 0u; joint < ACTUATOR_JOINT_COUNT; ++joint) {
        sample.position_urad[joint] = position;
    }
    return sample;
}

static void test_setpoint_batch_is_atomic(void) {
    actuator_setpoint_queue_t queue;
    actuator_joint_limit_t limits[ACTUATOR_JOINT_COUNT];
    actuator_setpoint_t samples[2];

    actuator_setpoint_queue_init(&queue);
    fill_limits(limits);
    samples[0] = make_setpoint(12u, 0);
    samples[1] = make_setpoint(13u, 2000);
    CHECK(actuator_setpoint_queue_push_batch(&queue, samples, 2u, 10u, 2u, 10u, limits) ==
          ACTUATOR_QUEUE_LIMIT_VIOLATION);
    CHECK(queue.count == 0u);
}

static void test_setpoint_queue_enforces_order_and_due_tick(void) {
    actuator_setpoint_queue_t queue;
    actuator_joint_limit_t limits[ACTUATOR_JOINT_COUNT];
    actuator_setpoint_t samples[2];
    actuator_setpoint_t output;

    actuator_setpoint_queue_init(&queue);
    fill_limits(limits);
    samples[0] = make_setpoint(12u, 100);
    samples[1] = make_setpoint(13u, 200);
    CHECK(actuator_setpoint_queue_push_batch(&queue, samples, 2u, 10u, 2u, 10u, limits) ==
          ACTUATOR_QUEUE_OK);
    CHECK(actuator_setpoint_queue_take_due(&queue, 11u, &output) == ACTUATOR_QUEUE_NOT_DUE);
    CHECK(actuator_setpoint_queue_take_due(&queue, 12u, &output) == ACTUATOR_QUEUE_OK);
    CHECK(output.position_urad[0] == 100);
    CHECK(queue.count == 1u);
}

static void run_test(const char *name, void (*test)(void)) {
    const int failures_before = failures;
    test();
    if (failures == failures_before) {
        printf("PASS %s\n", name);
    }
}

int main(void) {
    run_test("crc32c_known_vector", test_crc32c_known_vector);
    run_test("cobs_round_trip", test_cobs_round_trip);
    run_test("calibration_conversion_and_limits", test_calibration_conversion_and_limits);
    run_test("protocol_round_trip", test_protocol_round_trip);
    run_test("protocol_rejects_corruption", test_protocol_rejects_corruption);
    run_test("protocol_accepts_maximum_payload", test_protocol_accepts_maximum_payload);
    run_test("stream_parser_delivers_complete_frame", test_stream_parser_delivers_complete_frame);
    run_test("safety_requires_explicit_arm_and_fresh_heartbeat",
             test_safety_requires_explicit_arm_and_fresh_heartbeat);
    run_test("safety_heartbeat_timeout_requests_hold", test_safety_heartbeat_timeout_requests_hold);
    run_test("safety_estop_is_latched", test_safety_estop_is_latched);
    run_test("safety_fault_cannot_be_bypassed_by_disable",
             test_safety_fault_cannot_be_bypassed_by_disable);
    run_test("setpoint_batch_is_atomic", test_setpoint_batch_is_atomic);
    run_test("setpoint_queue_enforces_order_and_due_tick",
             test_setpoint_queue_enforces_order_and_due_tick);

    if (failures != 0) {
        fprintf(stderr, "%d test(s) failed\n", failures);
        return 1;
    }
    printf("All actuator core tests passed.\n");
    return 0;
}
