# Non-secret local qzcli defaults for this Codex installation.
# Do not put passwords, cookies, tokens, or other credentials here.
#
# These values are operator defaults. qzcli does not source this file itself;
# Codex should load it and pass the selected values as explicit CLI arguments.
# Explicit user choices always take precedence.

export QZCLI_DEFAULT_WORKSPACE_NAME="分布式训练空间"
export QZCLI_DEFAULT_WORKSPACE_ID="ws-9dcc0e1f-80a4-4af2-bc2f-0e352e7b17e6"

export QZCLI_DEFAULT_PROJECT_EN_NAME="robot3d"
export QZCLI_DEFAULT_PROJECT_NAME="面向通用具身机器人的世界模型&灵巧操控与运动泛化"
export QZCLI_DEFAULT_PROJECT_ID="project-97ab58cb-3162-4d0e-9137-1299d6cdea25"

export QZCLI_DEFAULT_IMAGE="docker.sii.shaipower.online/inspire-studio/base:v2.0"
export QZCLI_DEFAULT_IMAGE_TYPE="SOURCE_PRIVATE"

export QZCLI_DEFAULT_TRAINING_LAUNCH_MODE="direct-formal"

export QZCLI_GPU_POOL_SELECTION="available-first"
export QZCLI_FALLBACK_H100_COMPUTE_GROUP_NAME="开发区-H100-cuda13.2版本-183核"
export QZCLI_FALLBACK_H100_COMPUTE_GROUP_ID="lcg-71b971a7-5bdd-4798-b5ba-08f1eabde49e"
