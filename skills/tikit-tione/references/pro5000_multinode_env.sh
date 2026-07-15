# Non-secret runtime environment for pro5000 multi-node TI-ONE training.
# Source this inside the training container before launching the training command.

export LD_LIBRARY_PATH="/usr/local/lib/:${LD_LIBRARY_PATH:-}"
export NCCL_DEBUG=INFO
export NCCL_SOCKET_IFNAME=eth0
export NCCL_PROTO=^LL128
export FI_VRDMA_FORK_SAFE=1
export FI_VRDMA_DUP_INFO=1
export FI_VRDMA_MR_CACHE_ENABLE=0
export ENV_VRDMA_PROVIDER_RNR_REFILL_SQE=1
