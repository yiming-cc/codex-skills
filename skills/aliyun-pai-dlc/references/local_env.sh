# Non-secret defaults for the current PAI DSW environment.
# Do not put AccessKey, Secret, STS tokens, registry passwords, or cookies here.
#
# Credentials may be provided by the current process environment, by a private
# shell env file named in ALIYUN_PAI_CREDENTIAL_ENV_FILE, or by a private JSON
# file named in ALIYUN_PAI_CREDENTIAL_JSON_FILE.

export PAI_REGION=cn-beijing
export PAI_WORKSPACE_ID=433673
export ALIYUN_DLC_RESOURCE_ID=quota1uieq2yh4ie
export ALIYUN_PAI_CREDENTIAL_ENV_FILE=/mnt/netdata/Team/Personal/ymc/.config/aliyun-pai/accesskey.env
export PAI_CLI_BIN=/mnt/netdata/Team/Personal/ymc/.local/bin/pai
export PAI_CONFIG_DIR=/mnt/netdata/Team/Personal/ymc/.config/aliyun-pai/cli

export ALIYUN_DLC_DEFAULT_JOB_TYPE=PyTorchJob
export ALIYUN_DLC_DEFAULT_IMAGE=dsw-registry-vpc.cn-beijing.cr.aliyuncs.com/pai/torcheasyrec:1.3.0-pytorch2.12.1-gpu-py311-cu130-ubuntu22.04

# The foundation-compute template has 1/2/4/8-GPU profiles. The smallest
# profile is the default for previews and one-worker smoke submissions.
export ALIYUN_DLC_DEFAULT_WORKER_COUNT=1
export ALIYUN_DLC_DEFAULT_CPU=23
export ALIYUN_DLC_DEFAULT_MEMORY=225Gi
export ALIYUN_DLC_DEFAULT_GPU=1
export ALIYUN_DLC_DEFAULT_SHARED_MEMORY=225Gi

# Optional override. Leave the default path above when using the personal
# AccessKey file created for this skill.
# export ALIYUN_PAI_CREDENTIAL_JSON_FILE=

# Optional local receipt default.
# export ALIYUN_DLC_RECEIPT_DIR=$HOME/.local/state/aliyun-pai-dlc/receipts
