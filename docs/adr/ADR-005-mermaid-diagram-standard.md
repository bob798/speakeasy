# ADR-005：使用 Mermaid 作为架构图与流程图标准格式

**状态**：已采纳
**日期**：2025-03-10
**决策者**：Human

## 背景

随着 Speakeasy 代码量增长，需要为架构图、流程图、时序图选择统一的格式标准。
候选方案：Mermaid（文本语法）、Draw.io（图形工具）、Figma（设计工具）、PlantUML（文本语法）。

## 决策

所有架构图和流程图使用 Mermaid 语法，以 .md 文件存储在 docs/ 目录下，与代码一起做版本控制。

使用场景对应的图表类型：

| 使用场景 | Mermaid 图表类型 |
|---|---|
| 系统模块组成（C4 Level 2/3） | `graph` / `flowchart` |
| 跨模块调用时序（Flow 文档） | `sequenceDiagram` |
| 状态转换（如卡片状态机） | `stateDiagram-v2` |
| 流程分支决策 | `flowchart TD` |

## 原因

- 纯文本，Git diff 可读，不产生二进制文件
- GitHub / Obsidian / VS Code（装插件后）原生渲染
- Claude 可以直接生成和修改，不依赖人工画图
- 图表和说明文字在同一文件，不需要管理外部图片资源

## 后果

- 正面：文档与代码在同一仓库，不会出现图在本地找不到的问题
- 负面：节点超过 20 个时可读性下降，此时拆分为多张子图
- 工具要求：VS Code 需安装 Markdown Preview Mermaid Support 插件

## 参考

GitHub 官方图表创建指南（包含图表类型判断标准）：
https://docs.github.com/en/contributing/writing-for-github-docs/creating-diagrams-for-github-docs

## 被此决策取代

无
