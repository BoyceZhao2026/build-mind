# MultiMath-300K 数据集下载说明

论文：[MultiMath: Bridging Visual and Mathematical Reasoning for Large Language Models](https://arxiv.org/abs/2409.00147)

论文中构建的数据集为 **MultiMath-300K**。作者已经将数据集上传到 Hugging Face：

- [MultiMath-300K 数据集](https://huggingface.co/datasets/pengshuai-rin/multimath-300k)
- [作者 GitHub 仓库](https://github.com/pengshuai-rin/MultiMath)

Hugging Face 上的完整数据仓库约为 **5.94 GB**，其中：

- `images.zip`：约 3 GB
- `data.json`：约 980 MB
- `caption/`：图像描述相关训练数据
- `solution/`：数学解题过程相关训练数据

## 推荐方式：使用 Hugging Face CLI

首先安装或升级 `huggingface_hub`：

```bash
pip install -U huggingface_hub
```

下载完整数据集：

```bash
hf download pengshuai-rin/multimath-300k \
  --repo-type dataset \
  --local-dir ./playground/MultiMath
```

该方法支持缓存和断点续传，并会保留数据集原有的目录结构。

下载完成后解压图片：

```bash
unzip ./playground/MultiMath/images.zip \
  -d ./playground/MultiMath
```

## 只下载核心数据和图片

如果不需要额外的 caption 和 solution 文件，可以只下载 `data.json` 与 `images.zip`：

```bash
hf download pengshuai-rin/multimath-300k \
  data.json images.zip \
  --repo-type dataset \
  --local-dir ./playground/MultiMath
```

## 使用 wget 直接下载

也可以使用 `wget` 分别下载文件：

```bash
wget -c 'https://huggingface.co/datasets/pengshuai-rin/multimath-300k/resolve/main/data.json?download=true'

wget -c 'https://huggingface.co/datasets/pengshuai-rin/multimath-300k/resolve/main/images.zip?download=true'
```

参数 `-c` 表示在下载中断后可以继续下载。

## 作者训练代码期望的目录结构

如果需要使用作者代码训练或复现实验，数据目录大致应整理为：

```text
playground/MultiMath/
├── caption/
│   ├── chat_train_en.json
│   └── chat_train_zh.json
├── solution/
│   ├── chat_train_en.json
│   └── chat_train_zh.json
└── RGB_images/
```

作者代码中的具体路径配置可以参考：

- [数据准备说明](https://github.com/pengshuai-rin/MultiMath#data-preparation)
- [dataset_config.py](https://github.com/pengshuai-rin/MultiMath/blob/main/llava/config/dataset_config.py)

其中图片路径被配置为：

```text
./playground/MultiMath/RGB_images
```

因此解压 `images.zip` 后，需要确认图片最终位于上述目录。如果压缩包生成了不同名称的图片目录，应将其移动或重命名为 `RGB_images`，或者修改 `dataset_config.py` 中的路径。

## 国内网络下载较慢时

如果直接连接 Hugging Face 较慢，可以临时设置社区镜像地址，然后重新执行 `hf download`：

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

设置只对当前终端会话有效。若镜像同步不完整或下载失败，请切换回 Hugging Face 官方地址：

```bash
unset HF_ENDPOINT
```

## 参考资料

- [论文页面](https://arxiv.org/abs/2409.00147)
- [MultiMath-300K 数据集](https://huggingface.co/datasets/pengshuai-rin/multimath-300k)
- [MultiMath GitHub 仓库](https://github.com/pengshuai-rin/MultiMath)
- [Hugging Face 官方下载文档](https://huggingface.co/docs/huggingface_hub/en/guides/download)
