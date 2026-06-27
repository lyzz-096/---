# 高考志愿全自动咨询系统

这是开源版本地原型，目标是把下面这条链路跑通：

家长输入考生信息 -> 自动初筛候选 -> 生成冲稳保建议 -> 联网补证据 -> 导出正式 HTML 报告

这份仓库默认以“可公开、可演示、可二次开发”为目标整理：

- 默认使用仓库内置的样例数据运行
- 不包含私有录取数据库与历史打包分发文件
- 可以在你自己的环境里接入真实数据库或官方 Excel 数据继续增强

## 当前能力

- 对话/表单共用的考生画像结构
- 省份 + 科类/选科 + 分数/位次筛选
- 基于样例数据的冲、稳、保推荐
- 分数自动匹配样例位次
- 本地 HTTP 页面
- 联网取证入口
- 正式 HTML 报告导出

## 目录说明

- `main.py`：本地 CLI / HTTP 入口
- `gaokao_tool/`：推荐逻辑、数据加载、联网取证、报告导出
- `data/sample_admissions.json`：样例录取数据
- `data/sample_score_ranks.json`：样例一分一段
- `report_template/index.html`：正式报告模板
- `scripts/`：资源维护和辅助脚本

## 快速开始

### 1. 启动页面

```bash
python main.py --api --port 8765
```

然后打开：

```text
http://127.0.0.1:8765/
```

### 2. 命令行模式

```bash
python main.py
```

### 3. API 模式

```bash
python main.py --api --port 8765
```

页面会向 `/recommend`、`/research`、`/export-report` 发请求，也可以手动调用。

示例请求：

```json
{
  "province": "湖北",
  "subject_type": "物理类",
  "score": "580",
  "rank": "",
  "preferred_majors": "计算机,电子",
  "excluded_majors": "土木",
  "preferred_regions": "武汉,宜昌",
  "career_goal": "就业",
  "family_background": "普通家庭",
  "accept_postgraduate": "n"
}
```

## 关于真实数据

仓库默认不附带 `admission_clean.db`。如果你有自己的真实库，可以放到：

```text
assets/app/data/admission_clean.db
```

程序会优先读取它；如果没有，就自动退回样例数据。

## 当前边界

- 内置位次表和录取数据是样例级，不代表真实填报依据
- 联网取证用于补公开来源，不替代省考试院和高校招生网
- 学校特色、专业组明细、就业出口等正式交付前仍建议人工复核

## 后续增强方向

- 接入真实录取数据库
- 补多省一分一段和官方投档线
- 增加学校/专业对比
- 增加多轮状态保存
- 增加家长版/学生版双输出
