# ADR-003：通过 OpenRouter 接入多模型而非直连各厂商 API

**状态**：已采纳
**日期**：2025-03-01
**决策者**：Human

## 背景

Speakeasy 需要接入多个 LLM 提供商（Claude、DeepSeek、Doubao、Zhipu）。

## 决策

所有 LLM 调用通过 OpenRouter 统一代理，不直连各厂商 API。

## 原因

- 统一的 API 格式，无需为每个厂商写适配代码
- 单一 API Key 管理，降低密钥管理复杂度
- 方便切换和对比不同模型

## 后果

- 正面：模型切换成本极低，一行配置即可
- 负面：依赖 OpenRouter 服务可用性，存在单点风险
- 成本：OpenRouter 有少量中间商加价

## 被此决策取代

无
