# miniodk

**一个真的能跑起来的极简 ReAct Agent。**

一个循环,零框架,不需要显卡。Windows、Linux、macOS 都能跑 —— 包括 2013 年的双核 i3。

```bash
python miniodk.py "这个目录有多少个 py 文件?哪个最大?"
```

```
  [1] thought  先数 .py 文件
        action   count({"path": ".", "pattern": "*.py"})
        observe  . matches *.py: 1 file(s)
  [2] thought  看一下大小
        action   run({"cmd": "ls -la *.py"})
        observe  -rw-r--r-- 1 user 11340 miniodk.py
  [3] thought  信息够了

  === 答案 ===
  只有 1 个 Python 文件:miniodk.py,11340 字节。
  3 步 | 1.9 秒 | 云端大脑
```

---

## 为什么要做这个

大多数 Agent 框架默认你有两样东西:

| 它们假设你有 | 很多人的实际情况 |
|:-------------|:-----------------|
| Linux / macOS | **Windows 用户很多** |
| 显卡 or 大内存 | 2013 年的**双核 CPU + 12G** 照样是台能用的电脑 |

我是因为想在 Windows 上编译一个流行的 Go Agent 运行时,结果撞上 `syscall.Kill`、
`Setpgid` 这些**只有 Unix 才有的系统调用** —— 文档明明写着支持 Windows,实际根本编译不过。

于是我写了这个。它能在**我真正拥有的机器**上跑。

---

## 特点

- **单文件实现 ReAct 循环** —— 思考 → 行动 → 观察 → 再思考,约 300 行,只用标准库
- **一套代码,两种大脑**
  - 本地:[Ollama](https://ollama.com) 任意模型(`qwen3:1.7b`、`llama3.2`…)**免费、离线、数据不出本机**
  - 云端:任意 OpenAI 兼容接口(DeepSeek、OpenAI…)**快、准**
- **7 个内置工具** —— `ls` `read` `write` `run` `calc` `count` `search`
- **Windows 原生友好** —— 路径自动转换、终端色彩兼容、无 POSIX 专属调用
- **步数有上限** —— 循环自己会停,不会跑飞
- **JSON 解析容错** —— markdown 代码块、多余逗号、小模型的随意格式都能吃下

---

## 安装

不用装任何东西。Python 3.9+ 加标准库即可。

```bash
git clone https://github.com/13178383603/miniodk.git
cd miniodk
```

选一个大脑:

```bash
# 本地(免费、离线)—— 需要 Ollama 在跑
ollama pull qwen3:1.7b

# 云端(快、准)—— 任意 OpenAI 兼容的 key
export DEEPSEEK_API_KEY=sk-...
```

---

## 用法

```bash
# 自动使用云端大脑(检测到 key 时)
python miniodk.py "找出这个仓库里所有 TODO 并总结"

# 使用本地大脑
python miniodk.py -m qwen3:1.7b "列出这里最大的 5 个文件"

# 自定义步数 / 模型
python miniodk.py --max-steps 12 --api-model deepseek-chat "把 notes.md 改成 changelog"

# 指向任意 OpenAI 兼容端点
export MINIODK_API_BASE=http://localhost:8000/v1/chat/completions
export MINIODK_API_MODEL=my-model
```

### 环境变量

| 变量 | 默认值 | 作用 |
|:-----|:-------|:-----|
| `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` | — | 启用云端大脑 |
| `MINIODK_API_BASE` | `https://api.deepseek.com/chat/completions` | 任意 OpenAI 兼容端点 |
| `MINIODK_API_MODEL` | `deepseek-chat` | 云端模型名 |
| `MINIODK_MODEL` | `qwen3:1.7b` | 本地 Ollama 模型 |
| `OLLAMA_URL` | `http://localhost:11434/api/chat` | Ollama 地址 |
| `MINIODK_MAX_STEPS` | `8` | 步数上限 |

---

## 原理

```
        ┌──────────────┐
        │    任务      │
        └──────┬───────┘
               ▼
      ┌─────────────────┐
      │   模型(思考)   │◄──────────────┐
      └────────┬────────┘               │
               ▼                        │
          一个 JSON 对象                │
       ┌────────┴────────┐              │
       ▼                 ▼              │
  {"answer": ...}   {"action": ...}     │
       │                 │              │
       ▼                 ▼              │
     结束          执行工具             │
                         │              │
                         ▼              │
                    观察结果 ───────────┘
```

每一轮模型只输出**一个 JSON 对象**:含 `answer` 就结束,含 `action` 就执行工具、
把观察结果喂回去。整个设计就这些。

---

## 本地 vs 云端(实测)

同一份代码、同一台机器(**i3-4170 双核 / 12G 内存 / 无显卡**),任务:*数出目录里的 .py 文件*。

| 大脑 | 结果 | 耗时 | 步数 |
|:-----|:-----|:----:|:----:|
| `qwen3:1.7b`(本地) | ⚠️ 工具调对了,但最终答案是空的 | 77 秒 | 3 |
| `deepseek-chat`(云端) | ✅ 答案正确 | **1.9 秒** | 3 |

**结论:瓶颈不在循环,而在模型。** 1.7B 的小模型会"动手",但不会"总结"。
要准确性时用云端,数据不能出本机时用本地。

---

## 适用场景

| 适合 | 不适合 |
|:-----|:-------|
| 用自然语言快速查文件/看仓库 | 长时间自主的大项目 |
| 教学/演示 ReAct 到底怎么跑 | 替代完整框架(LangGraph 等) |
| 内网 / 隐私敏感环境 | 高吞吐的生产流水线 |
| **Windows** 上(多数 Agent 工具跑不了) | 需要显卡级算力的推理 |

---

## 许可

MIT —— 随便用。

---

*如果它帮你省掉了一次框架安装,点个 star 能让更多人看到。*
