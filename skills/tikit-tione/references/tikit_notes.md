# Tikit TI-ONE Notes

These notes summarize Tencent Cloud TI-ONE Tikit docs for Codex usage. Prefer the current official docs when exact parameters matter.

Official entry and related pages:

- Python SDK operation guide: https://cloud.tencent.com/document/product/851/74120
- SDK installation: https://cloud.tencent.com/document/product/851/74133
- Dataset management: https://cloud.tencent.com/document/product/851/74135
- Data upload/download: https://cloud.tencent.com/document/product/851/74136
- Training task APIs: https://cloud.tencent.com/document/product/851/74137
- Development machine/notebook APIs: https://cloud.tencent.com/document/product/851/108256
- Model service APIs: https://cloud.tencent.com/document/product/851/82301
- Batch task APIs: https://cloud.tencent.com/document/product/851/82302
- Model acceleration APIs: https://cloud.tencent.com/document/product/851/82399

## Mental Model

Tikit is a Python SDK for operating TI-ONE platform resources from Notebook, training containers, or local Python environments. It is not a training framework. Use it to automate platform actions: datasets, COS/HDFS/Hive data movement, training jobs, development machines, model acceleration, online services, and batch jobs.

## Installation

TI-ONE Notebook and training containers generally include `tikit`. Outside the platform, install or update with:

```bash
pip3 install -U tikit
```

Create a client:

```python
from tikit.client import Client
client = Client(secret_id, secret_key, region)
```

On public-cloud TI-ONE platform environments, the region may already come from environment variables.

## API Areas

### Data

Datasets support image, table, text, and other data. Image datasets can include annotation metadata such as classification, detection, segmentation, OCR, and annotation formats such as TI-ONE, Pascal VOC, COCO, or directory structure.

Data movement covers COS, HDFS, Hive import/export, and WeData/EMR Hive initialization. Tikit COS paths in the docs commonly use:

```text
<bucket>/<cos path>/
```

### Training

Training task creation usually needs:

- task name
- framework or custom image
- code package COS path
- startup command
- input data configuration
- output COS path
- worker/resource configuration
- resource group when applicable
- log/VPC/subnet/restart settings when applicable

After creation, typical follow-up operations are listing tasks, getting task detail, getting pods/events/logs, reporting/querying custom metrics, stopping, and deleting tasks.

### Development Machines

Tencent docs note that Notebook product APIs may still be named `notebook` after the UI/product module changed to development machines on 2025-02-25. Expect names like `create_notebook`, `start_notebook`, `stop_notebook`, `delete_notebook`, and `describe_notebooks`.

### Model Acceleration

Model acceleration tasks usually need source model info, model format, model name/version, input COS path, output COS path, tensor shape/config, optimization level such as no-loss or FP16, and target GPU type.

### Online Services

Online service creation/version creation needs service name, framework/image/model path or model config, resource config, instance count or autoscaling config, environment variables, logs, authentication, VPC/subnet when needed, and optional traffic weights.

### Batch Tasks

Batch tasks support one-off or scheduled offline processing/inference. Creation usually needs resource config, input/output data source, model info or image/code package, startup command, schedule info, logs, and network config.

## Discovery Pattern

Because Tikit versions can drift, inspect installed symbols before executing unfamiliar operations:

```bash
TIONE_SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/tikit-tione"
python3 "$TIONE_SKILL_DIR/scripts/tikit_helper.py" methods training
python3 "$TIONE_SKILL_DIR/scripts/tikit_helper.py" methods notebook
python3 "$TIONE_SKILL_DIR/scripts/tikit_helper.py" methods service
```
