# Non-secret local TI-ONE defaults for this Codex installation.
# Do not put SecretId, SecretKey, tokens, registry passwords, or cookies here.
#
# Usage:
#   TIONE_SKILL_DIR="$HOME/.agents/skills/tikit-tione"
#   set -a
#   . "$TIONE_SKILL_DIR/references/local_env.sh"
#   set +a

export TENCENTCLOUD_REGION=ap-shanghai

export TIONE_CONTROL_PYTHON=/usr/bin/python3
export TIONE_TIKIT_CLI=/usr/local/bin/tikit

export TIONE_RESOURCE_GROUP_NAME="vrdma-pro5000-训练"
export TIONE_RESOURCE_GROUP_ID=rsg-clk2krr9
export TIONE_VPC_ID=vpc-jsyugafc
export TIONE_SUBNET_ID=subnet-ia45fepf

export TIONE_CFS_NAME=cfs-zone9-new
export TIONE_CFS_ID=cfs-4b4499054
export TIONE_CFS_SOURCE=/
export TIONE_CFS_MOUNT=/cfs
export TIONE_DEFAULT_INPUT_CFS=cfs-4b4499054:/:/cfs

export TIONE_DEFAULT_FRAMEWORK_NAME=PYTORCH
export TIONE_DEFAULT_FRAMEWORK_ENV=torch1.9-py3.8-cuda11.1-gpu
export TIONE_DEFAULT_MODE=DDP
export TIONE_DEFAULT_WORKERS=1
export TIONE_DEFAULT_GPU_TYPE=HCC-N50p-72G-vr
export TIONE_DEFAULT_RUN_USER=root

export TIONE_WBC_IMAGE_TYPE=TCR
export TIONE_WBC_IMAGE_URL=shanghai-tcr.tencentcloudcr.com/sys1/wbc:v20260701141602
export TIONE_WBC_REGISTRY_REGION=ap-shanghai
export TIONE_WBC_REGISTRY_ID=tcr-604jlabg

export TIONE_TACTILE_IMAGE_TYPE=TCR
export TIONE_TACTILE_IMAGE_URL=shanghai-tcr.tencentcloudcr.com/sys1/tactile_train:v20260714203836
export TIONE_TACTILE_REGISTRY_REGION=ap-shanghai
export TIONE_TACTILE_REGISTRY_ID=tcr-604jlabg

export TIONE_DEFAULT_IMAGE_TYPE=TCR
export TIONE_DEFAULT_IMAGE_URL=shanghai-tcr.tencentcloudcr.com/taco/taco-train:ngc26.02-vrdma-hccgc50se-hccl2.0.0-tiprofiler-v1.0
export TIONE_DEFAULT_REGISTRY_REGION=ap-shanghai
export TIONE_DEFAULT_REGISTRY_ID=tcr-604jlabg

export TIONE_N50P_8GPU_GPU=8
export TIONE_N50P_8GPU_CPU=252
export TIONE_N50P_8GPU_MEMORY=720

export TIONE_HCC_N50P_8GPU_GPU=8
export TIONE_HCC_N50P_8GPU_CPU=250
export TIONE_HCC_N50P_8GPU_MEMORY=720

export TIONE_HCCPNV6_8GPU_GPU=8
export TIONE_HCCPNV6_8GPU_CPU=120
export TIONE_HCCPNV6_8GPU_MEMORY=1200

export TIONE_COS_BUCKET=phymi-cos-1438869198
