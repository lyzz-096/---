# 资源接入说明

这个开源仓库默认只附带样例数据，方便直接运行和演示。

如果你准备接入真实数据，建议按下面方式逐步增强：

## 1. 真实录取库

把你自己的 `admission_clean.db` 放到：

```text
assets/app/data/admission_clean.db
```

程序会优先读取这份数据库；如果没有，就自动回退到样例数据。

## 2. 官方原始文件

建议把各省官方 Excel / PDF / HTML 原始文件放到：

```text
assets/app/data/official_sources/
```

可按省份分目录整理，例如：

```text
assets/app/data/official_sources/浙江/
assets/app/data/official_sources/湖北/
```

## 3. 检查覆盖情况

```powershell
python scripts\resource_progress.py
python scripts\update_2025_resources.py --inspect
```

## 4. 增量更新建议

这个开源版保留了资源更新脚本接口，但默认不附带完整全国清洗流水线和私有源数据。

更稳妥的做法是：

- 先准备某个省的官方源文件
- 先 dry-run 检查
- 再把清洗后的结果合并回你自己的数据库

示例：

```powershell
python scripts\update_2025_resources.py --source-dir ".\\data\\official_sources\\浙江" --merge-provinces 浙江 --dry-run
```

## 5. 开源版边界

- 仓库不附带私有数据库
- 仓库不附带私有分发资源
- 仓库不保证全国 2025 全量覆盖
- 正式志愿填报前，仍要回到省考试院和高校招生网复核
