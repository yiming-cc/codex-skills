# Non-secret runtime environment for pro5000 multi-node TI-ONE training.
# Source this inside the training container before launching the training command.

export LD_LIBRARY_PATH="/usr/local/lib/:${LD_LIBRARY_PATH:-}"
NCCL_PRELOAD_LIB=/lib/x86_64-linux-gnu/libnccl.so.2
case ":${LD_PRELOAD:-}:" in
  *":${NCCL_PRELOAD_LIB}:"*) ;;
  *) export LD_PRELOAD="${NCCL_PRELOAD_LIB}${LD_PRELOAD:+:${LD_PRELOAD}}" ;;
esac
export NCCL_DEBUG=INFO
export NCCL_MONITOR_ENABLE=0
export NCCL_SOCKET_IFNAME=eth0
export NCCL_PROTO="^LL128"
export NCCL_COMM_SPLIT_SHARE_RESOURCES=1
export FI_VRDMA_FORK_SAFE=1
export FI_VRDMA_DUP_INFO=1
export FI_VRDMA_MR_CACHE_ENABLE=0
export ENV_VRDMA_PROVIDER_RNR_REFILL_SQE=1
