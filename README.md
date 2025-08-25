<img width="1024" height="1536" alt="ChatGPT Image 2025年8月25日 23_24_36" src="https://github.com/user-attachments/assets/0ad44c0c-8b1f-4e71-a943-a3ebbdf0b77b" />

---  

## EchoScribe 项目指南（新手友好）

本项目是一个面向本地与云端混合流程的语音转写与文本生成系统，包含三条主要能力链：
- 语音分片转写（ASR）→ 结果缓冲与合并 → 归档
- 事件提取（基于文本与 LLM）→ 结构化 JSON 输出 → 用户档案索引
- 周期性信件生成（基于事件与用户画像）→ 文本信件产出

### 三大 Runner（可独立运行，组合为完整功能）
- transcription_processor_runner.py：监控 `input_chunks/` 的音频分片，转写为 `archive/*.txt`，并按配置进行文本润色到 `polished_results/`。
  - 运行：`python transcription_processor_runner.py`
- event_processor_runner.py：将 `archive/*.txt`（优先 `polished_results/`）解析为结构化事件，写入 `dataset/*.json`，并更新 `user_profile.json`。
  - 运行：`python event_processor_runner.py`
- letter_generator_runner.py：聚合 `dataset/*.json` 与 `user_profile.json`，当事件数达阈值时生成信件到 `letter_output/`。
  - 运行：`python letter_generator_runner.py`

以上三个可分别启动；同时运行可实现端到端流水线。

### 目录结构总览

```
EchoScribe/
  config/                 # 系统与模型配置（包含示例）
  dataset/                # 事件 JSON 数据集输出目录
  json_template/          # 事件与用户模板
  letter_examples/        # 信件示例（用于风格学习）
  letter_output/          # 信件输出目录
  src/                    # 核心源码
    buffer.py             # 内存缓冲（分片转写结果暂存）
    config_loader.py      # 配置加载（统一入口）
    engine.py             # 系统管理器（文件监视、任务分发、合并协调）
    event_processor.py    # 事件生成（LLM 将文本转结构化 JSON）
    job.py                # 单文件转写作业封装
    letter_generator.py   # 根据信息生成信件
    main.py               # 程序入口（日志、系统管理器、润色进程）
    merge.py              # 合并管理器（缓冲 → 全文文件）
    model_manager.py      # 模型实例管理与缓存
    logs/                 # 运行日志
  transcription_processor_runner.py  # 启动器（环境与 GPU 状态检查）
  event_processor_runner.py          # 事件抽取的独立运行脚本
  letter_generator_runner.py         # 信件生成的独立运行脚本
  requirements.txt        # 依赖
```

### 整体运行逻辑
- 输入目录 `input_chunks/` 放置待转写的 `.wav` 音频切片。
- `src/main.py` 启动后创建 `SystemManager`：
  - 监视输入目录 → 发现新 `.wav` → 送入任务队列。
  - 工作线程使用 `ModelManager` 提供的 ASR 模型执行转写（见 `job.py`）。
  - 成功的转写片段写入 `MemoryBuffer`（见 `buffer.py`）。
  - `MergeManager` 定期从缓冲区取出分片，按序合并为 `full_XXX_to_YYY.txt` 存入 `archive/`。
- 后台事件处理（`event_processor.py`）可按配置定期运行：
  - 读取 `polished_results/` 优先或 `archive/` 文本，调用 LLM 生成结构化事件 JSON，写入 `dataset/` 并更新 `user_profile.json` 索引。
- 信件生成（`letter_generator.py`）可按配置定期运行：
  - 当事件数量达阈值时，综合用户档案、事件数据和示例信件风格，调用 LLM 生成新信件，保存到 `letter_output/`。

### 快速开始
1) 安装依赖
```bash
pip install -r requirements.txt
```

2) 配置文件
- 切勿将真实密钥提交到公共仓库！请基于下述示例创建私有配置：
  - `config/model_config.sample.json`
  - `config/system_config.sample.json`

将示例复制为实际文件名：
```bash
cp config/model_config.sample.json config/model_config.json
cp config/system_config.sample.json config/system_config.json
```
并用你自己的环境变量或私密字符串替换示例中的占位符（建议使用环境变量或本地密钥管理）。

3) 单独运行各 Runner（推荐分别开终端运行）
```bash
python transcription_processor_runner.py      # 音频 → archive/*.txt & polished_results/
python event_processor_runner.py              # 文本 → dataset/*.json & 更新用户档案
python letter_generator_runner.py             # 事件+用户 → letter_output/*.txt
```
或直接在 `src` 目录内（仅语音转写主程序）：
```bash
python src/main.py
```

4) 手动运行一次事件处理/信件生成（用于验证）
```bash
python -m EchoScribe.src.event_processor
python -m EchoScribe.src.letter_generator
```

### 配置说明（敏感信息已去标识）
- `config/model_config.json`
  - `default_model`: 默认 ASR 模型标识
  - `models`: 可选模型列表（设备、是否禁用更新等）
  - `llm_config`: 事件与信件模块可能共用的 LLM 访问参数（请使用占位或环境变量注入）

- `config/system_config.json`
  - `input_dir`/`archive_dir`/`failed_dir`/`polished_dir`: 目录配置
  - `transcription`: 并发数、缓冲上限、合并间隔、是否归档原始音频
  - `polishing`: 润色服务配置（如启用，注意 API Key 走占位）
  - `event_processing`: 事件处理开关与 LLM 配置（Key 走占位/环境变量）
  - `letter_generation`: 信件生成策略与 LLM 配置
  - `disk_threshold_gb`: 最低剩余磁盘空间阈值

### 隐私与安全（务必遵循）
- 不要在仓库内提交任何真实 `api_key`；本仓库提供 `*.sample.json` 作为模板。
- 在 README、注释、示例中统一使用占位符如：`<YOUR_API_KEY>`、`<YOUR_BASE_URL>`。
- 如需在生产使用，推荐：
  - 使用环境变量注入密钥（`os.getenv` 读取）。
  - 使用密钥管理工具（如 GitHub Actions Secrets、本地 .env 不入库）。

### 典型数据流
1) 放置 `*.wav` 到 `input_chunks/`
2) `SystemManager` 监测 → 入队 → `TranscriptionJob` 调用 ASR → 文本分片
3) `MemoryBuffer` 暂存 → `MergeManager` 定期合并 → `archive/full_*.txt`
4) 事件处理器读取文本 → LLM → `dataset/YYYYMMDD-NNN.json`，并更新 `user_profile.json`
5) 信件生成器达阈值后运行 → 输出 `letter_output/letter_YYYYMMDD_HHMMSS.txt`

### 重启与清理建议（重要）
- 当前未对“开关重启/断点续跑/去重清理”做优化。为避免重复或脏数据：
  - 重启前建议清理本次产生的中间/输出：`archive/`、`polished_results/`、`dataset/`、`letter_output/` 中与本轮相关的文件。
  - 若使用同一批输入多次重跑，务必确认 `user_profile.json` 中的 `event_index` 是否需要回滚或去重。
  - 生产环境可在后续增加“去重标记/断点记录/幂等写入”以提升可恢复性。

### 日志位置
- 系统日志：`src/logs/*.log` 与根目录 `logs/system.log`（按模块而定）

### 测试/开发建议
- 将 `transcription.concurrency` 设置低一些以减少显存占用。
- 开发环境 GPU 不足时，选择 CPU 或更小模型；或将并发限制为 1。
- 事件与信件模块在未配置密钥时会回退为“未初始化客户端”的提示，不会崩溃。

### 常见问题
- 未检测到 GPU：属正常，系统会自动回退到 CPU 或调低并发。
- 输出为空：检查输入音频有效性、模型是否可用、日志中的错误。
- JSON 无法解析：LLM 响应可能非严格 JSON，代码已做异常处理并打印原始返回供排查。

### 许可证
本仓库未附带明确许可证，请在公开或商用前确认版权与第三方模型/接口条款。




