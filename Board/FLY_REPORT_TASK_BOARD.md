# FlyReport Task Board

## Done

### 会话主链路 API 已落地（创建会话、发消息、确认、取消、查询会话、查询历史）


### 流式消息接口已落地（SSE）


### 会话列表与过滤已落地（keyword/state）


### 指标快照接口已落地


### 预览 HTML 接口已落地


### Artifact 下载与路径穿越防护已落地


### PG 持久化（session/turn/artifact/audit）已落地


### 权限抽象与审计查询已落地


### Clarifier 冲突检测与 follow-up 流程已落地


### 关键测试集已存在并持续维护


## Doing

### SSE 前端联动与进度可视化（后端基础已在，前端对接未完成）


### 真实权限校验接入（当前抽象可用，具体 IdentityGate 未完成）


### 运维侧定时清理接入（能力已实现，调度未接）


### 文档补齐（README 快速上手/API cheatsheet）


## Todo

### 真实 Dikong 联调（替换 Fake client，完善 live 集成）


### 偏好系统（被动学习）


### FlyReport 轻量 LM Chat 接入（替代旧方案）


### Tracing/OTel 贯通


### 下载限流与网关层统一限流


### 了解数据库migration

  - due: 2026-05-08
  - priority: high
  - workload: Easy
  - defaultExpanded: false
  - steps:
      - [ ] 梳理当前迁移链路（Alembic 配置、版本目录、命令入口）
      - [ ] 阅读现有 migration 脚本并整理版本依赖关系
      - [ ] 在本地空库执行 upgrade head 验证可初始化
      - [ ] 本地新增一次 migration（模拟字段变更）
      - [ ] 执行 downgrade 回滚验证可逆性
      - [ ] 记录常见失败场景与处理办法（冲突、重复 revision、脏状态）
      - [ ] 输出团队约定（命名规范、评审要求、上线前检查项）
      - [ ] 补充 FlyReport migration 操作手册文档

### 前端体验优化（格式选择、进度条、预览 iframe）


### 模板美化（docx/pdf/markdown 打包体验）


### 异常熔断与降级策略完善


## Notes

### 本看板基于仓库当前实现与 DESIGN-3 状态说明整理。


### 如果后续你希望插件更好识别列，可把列名改为 Todo / In Progress / Done。


### 若希望按迭代管理，可增加 Sprint 字段或按 M1/M2/M3 再拆一层文件。


