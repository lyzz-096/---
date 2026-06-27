# 高考志愿全自动咨询系统

面向高考志愿咨询场景的开源 Skill 与本地 Web 原型。

这个项目尝试把真实志愿咨询中的关键动作产品化、结构化，而不只是提供一段“会聊天”的提示词。它关注的不是单轮回答，而是一整条可复用链路：

- 主动追问考生与家长的关键约束
- 基于分数、位次、专业偏好、地域偏好和家庭目标建立候选池
- 形成冲、稳、保三档推荐与路线对比
- 联网补充公开证据与学校特征
- 输出适合给家长查看的正式 HTML 报告

## 项目目标

`高考志愿全自动咨询系统` 的目标不是替代正式填报依据，而是提供一个可继续开发的开源底座，让开发者可以快速搭建：

- 更像真人咨询老师的对话式志愿顾问
- 可本地运行的志愿推荐与报告生成工具
- 可以接入真实录取数据库和公开招生资料的咨询工作台

它适合拿来做产品原型、技能工程、演示系统和二次开发。

## 核心能力

- 对话式引导，而不是上来就丢一张大表
- 基于样例数据的冲、稳、保推荐逻辑
- 支持考生画像、专业偏好、城市偏好和目标导向筛选
- 支持公开信息补查与学校证据整理
- 支持导出正式 HTML 报告
- 支持从样例数据平滑切换到真实录取数据库

## 适用场景

- 想把高考志愿咨询流程做成 agent / skill 的开发者
- 想快速搭一个本地可演示的志愿咨询网页原型的人
- 想在现有录取数据库基础上继续做推荐、报告和咨询流程产品的人
- 想研究“对话式咨询 + 数据筛选 + 报告生成”工作流的人

## 项目结构

```text
.
├─ SKILL.md                     # Skill 主说明，定义咨询节奏、追问规则和输出阈值
├─ agents/openai.yaml           # Skill 展示元数据
├─ references/                  # 对话、推荐、学校调研、风格等参考文档
├─ assets/app/                  # 本地 Web 原型与推荐引擎
│  ├─ gaokao_tool/              # 核心逻辑：数据加载、推荐、联网取证、报告生成
│  ├─ data/                     # 样例数据与资源说明
│  ├─ report_template/          # HTML 报告模板
│  └─ scripts/                  # 数据维护与辅助脚本
├─ docs/screenshots/            # 项目截图
└─ scripts/run_web.ps1          # 本地启动脚本
```

## 功能预览

### 对话式学校分析

![对话式学校分析](docs/screenshots/01-consulting-school-analysis.png)

### 路线对比

![路线对比](docs/screenshots/02-route-comparison.png)

### 冲稳保总览

![冲稳保总览](docs/screenshots/03-tier-overview.png)

### 单校详情卡片

![单校详情卡片](docs/screenshots/04-school-card-detail.png)

### 暗色对话示例一

![暗色对话示例一](docs/screenshots/05-dark-chat-example-1.jpg)

### 暗色对话示例二

![暗色对话示例二](docs/screenshots/06-dark-chat-example-2.jpg)

## 快速开始

### 1. 运行本地 Web 原型

方式一：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_web.ps1
```

方式二：

```bash
cd assets/app
python main.py --api --port 8765
```

启动后打开：

```text
http://127.0.0.1:8765/
```

### 2. 作为 Skill 使用

把这个目录放进你的 Codex skills 目录后，可以这样触发：

```text
Use $gaokao-volunteer-advisor 帮一个湖北物理类考生做志愿咨询，先主动问家长和学生问题。
```

## 数据接入说明

仓库默认只附带样例数据，方便直接运行、演示和二次开发，不附带私有录取数据库。

如果你有自己的真实录取库，可以放到：

```text
assets/app/data/admission_clean.db
```

程序会优先读取这份数据库；如果不存在，就自动回退到仓库内置样例数据。

如果你还需要接入各省官方 Excel / PDF / HTML 原始文件，可以继续参考：

- `assets/app/data/RESOURCE_PROGRESS.md`
- `assets/app/scripts/update_2025_resources.py`
- `assets/app/scripts/resource_progress.py`

## 开源版本边界

为了适合公开发布，这个仓库已经移除了以下内容：

- 私有录取数据库
- 历史打包产物与私有分发资源
- 运行日志、缓存和本机路径绑定内容
- 大体积私有二进制依赖

因此，这个仓库更适合作为开源底座和演示原型，而不是“开箱即用的全国正式填报系统”。

正式志愿填报前，仍应回到：

- 各省教育考试院 / 招生考试机构
- 高校本科招生网
- 阳光高考等权威公开来源

对录取位次、专业组、招生计划、选科要求和政策口径做最终复核。

## 开发建议

如果你准备继续扩展这个项目，建议优先做这几件事：

- 接入真实录取数据库
- 增加学校 / 专业对比页
- 增加多轮会话状态保存
- 增加家长版 / 学生版双报告
- 增加更多真实咨询案例和学校特征词条
- 增强不同省份的一分一段与招生计划接入能力

## License

本项目基于 [MIT License](LICENSE) 开源。
