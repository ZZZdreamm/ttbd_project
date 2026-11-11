# Optional Kafka lab toggle (stretch, Task 17). Resources go here with
# `count = var.enable_kafka ? 1 : 0`; local.kafka_resource_count is what tests check.
locals {
  kafka_resource_count = 0
}
