# Tenant / User / Auth 架构设计

> 这份文档专门说明 SwarmMind 平台里的租户、用户、认证、授权应该怎么设计，以及它们和 Gateway、Memory、Sandbox、Task Execution System 的关系。

当前阶段目标不是实现代码，而是先把身份边界设计清楚，避免后面网关、记忆、任务执行各自长出一套不兼容的身份模型。

---

## 1. 结论先说

SwarmMind 如果要走平台化，而不是单用户 demo，必须尽早确立下面四层身份架构：

1. **Tenant**
   组织隔离边界。

2. **User**
   实际调用主体。

3. **Authentication**
   解决“你是谁”。

4. **Authorization**
   解决“你能做什么”。

这四层不是附加功能，而是平台基础设施。

因为一旦系统开始支持：

- 多团队
- 多用户
- 长期记忆
- 配额
- 审计
- 沙箱权限控制

身份体系就会变成所有子系统的共同底座。

---

## 2. 为什么必须单独设计这一层

如果不单独设计，后面通常会出现这些问题：

1. Gateway 自己维护一套 `user_id`
2. Memory 自己维护一套 `owner_id`
3. Sandbox 自己维护一套 `requester`
4. Task 系统自己维护一套 `created_by`

最后会变成：

- 一次请求到底属于哪个 tenant 不清楚
- 一条 memory 到底挂在哪个 user 下不清楚
- 某个 sandbox 到底是谁开的不清楚
- 某个 tool 调用到底有没有授权不清楚

所以正确做法是：

**先定义统一身份模型，再让 Gateway、Memory、Sandbox、Orchestrator 全部消费同一套身份上下文。**

---

## 3. 核心设计目标

1. 支持多 tenant 数据隔离。
2. 支持 tenant 内多 user 协作。
3. 支持 API / CLI / UI / internal service 多种调用来源。
4. 支持细粒度权限控制到 tool group / sandbox profile / memory scope。
5. 支持用户级、租户级、组织级 memory 和配置。
6. 支持完整审计：谁提交了什么任务，谁调用了什么资源。
7. 支持后续扩展到 SSO、RBAC、SCIM、组织策略。

---

## 4. 核心概念定义

### 4.1 Tenant

Tenant 是平台里的组织隔离边界。

可以理解成：

- 一个公司
- 一个团队
- 一个组织空间
- 一个客户实例

Tenant 决定：

- 数据归属
- 配额和预算
- 可用模型范围
- 可用 sandbox profiles
- 可用 tool groups
- org-level memory / knowledge
- 审计与计费边界

### 4.2 User

User 是 tenant 下的实际调用主体。

User 决定：

- 用户级身份
- 用户会话
- 用户偏好和长期记忆
- 用户权限
- 操作审计归属

### 4.3 Service Principal

除了人类用户，还建议支持服务身份。

典型场景：

- CI 触发任务
- 内部 worker 调度请求
- 第三方系统 webhook 回调

因此身份主体不应只支持 `User`，还应支持 `ServicePrincipal`。

### 4.4 Session

Session 是一次连续交互上下文，不等于 user 本身。

Session 应绑定：

- `tenant_id`
- `user_id` 或 `principal_id`
- 活跃任务列表
- transcript 引用
- memory scope

### 4.5 Run

Run 是一次具体执行实例。

同一个 task 可以有多个 run，例如：

- 首次执行
- 重试执行
- repair run

---

## 5. 推荐身份架构分层

```text
External Caller
   -> Authentication Layer
   -> Identity Resolver
   -> Authorization Policy Engine
   -> Gateway
   -> Orchestrator / Runtime
```

每层职责不同：

### 5.1 Authentication Layer

负责验证凭证真伪。

输入：

- API Key
- JWT
- OAuth Token
- Internal Service Token

输出：

- 一个可信的主体 identity

### 5.2 Identity Resolver

负责把认证结果映射成内部统一身份上下文。

输出建议结构：

```json
{
  "principal_type": "user",
  "principal_id": "usr_123",
  "tenant_id": "tenant_001",
  "user_id": "usr_123",
  "roles": ["developer"],
  "scopes": ["tasks:create", "tasks:read"],
  "attributes": {
    "department": "engineering"
  }
}
```

### 5.3 Authorization Policy Engine

负责判断这个主体是否可以做某件事。

它应该回答：

- 能否创建任务
- 能否访问某个 task
- 能否使用某个 tool group
- 能否使用某个 sandbox profile
- 能否访问某个 memory scope

---

## 6. 推荐的数据模型

### 6.1 Tenant

建议字段：

- `tenant_id`
- `name`
- `slug`
- `status`
- `plan`
- `quota_policy_id`
- `security_policy_id`
- `default_model_policy_id`
- `created_at`
- `updated_at`

### 6.2 User

建议字段：

- `user_id`
- `tenant_id`
- `email`
- `display_name`
- `status`
- `roles`
- `preferences`
- `created_at`
- `updated_at`

### 6.3 ServicePrincipal

建议字段：

- `principal_id`
- `tenant_id`
- `name`
- `type`
- `roles`
- `scopes`
- `status`
- `created_at`

### 6.4 IdentityContext

这是建议在系统内部统一传递的身份对象。

建议字段：

- `request_id`
- `principal_type`
- `principal_id`
- `tenant_id`
- `user_id`
- `roles`
- `scopes`
- `session_id`
- `auth_method`
- `attributes`

这应该成为 Gateway、Memory、Sandbox、Task 系统共用的身份入口。

---

## 7. Authentication 方案建议

### 7.1 MVP 建议

MVP 不要一开始就做过重的身份体系。

建议从下面三类凭证开始：

1. **API Key**
   用于服务端调用、脚本、CLI、本地集成。

2. **Bearer Token / JWT**
   用于未来 UI 或外部接入。

3. **Internal Service Token**
   用于 worker、webhook、内部服务调用。

### 7.2 API Key 设计建议

每个 API Key 至少绑定：

- `tenant_id`
- `principal_id`
- `scopes`
- `status`
- `expires_at`

MVP 最简单的方式是：

- API Key 查数据库或配置表
- 映射到 tenant + user
- 生成 `IdentityContext`

### 7.3 JWT / OIDC 设计建议

二期建议引入：

- OIDC issuer
- JWKS 校验
- claim mapping

把外部 token 映射为内部 `IdentityContext`。

推荐映射：

- `sub` -> `principal_id`
- `email` -> `user.email`
- `org` / `tenant` claim -> `tenant_id`
- `roles` -> 内部角色

---

## 8. Authorization 方案建议

### 8.1 为什么 AuthN 不够

认证只告诉你“是谁”，但平台真正需要的是：

- 能不能创建任务
- 能不能读某个 task
- 能不能用某个 tool group
- 能不能开外网 sandbox

这些都属于授权问题。

### 8.2 推荐两层授权

建议做两层：

1. **Role-based Access Control, RBAC**
   决定大权限范围。

2. **Policy-based Control**
   决定细粒度资源权限。

### 8.3 RBAC 示例

建议角色：

- `tenant_admin`
- `developer`
- `analyst`
- `viewer`
- `service`

示例：

- `viewer` 只能读任务状态和结果
- `developer` 可以创建和执行代码任务
- `analyst` 可以创建搜索/报告类任务
- `tenant_admin` 可以管理密钥、策略、配额

### 8.4 Policy Control 示例

策略控制范围建议包括：

- 哪些 `sandbox_profile` 可用
- 哪些 `tool_groups` 可用
- 哪些 `model classes` 可用
- 哪些 `memory scopes` 可读写
- 是否允许外网访问
- 单次任务最大预算

---

## 9. Tenant 和 User 对各子系统的影响

### 9.1 对 Gateway

Gateway 需要基于 `tenant_id` 和 `user_id`：

- 做 admission control
- 做 rate limit
- 做 task/session 归属
- 做回调和查询鉴权

### 9.2 对 Memory

Memory 至少要支持这些作用域：

- `tenant_id`
- `user_id`
- `session_id`
- `agent_id`
- `task_id`

否则：

- 用户记忆无法归属
- 组织知识无法隔离
- 多租户数据会串

### 9.3 对 Sandbox

Sandbox 也要拿到身份上下文，用于：

- profile 权限判断
- 审计记录
- 成本归属
- 资源配额统计

### 9.4 对 Task Execution

Task 和 Run 必须绑定：

- `tenant_id`
- `created_by`
- `submitted_by`
- `run_owner`

否则无法做审计和查询鉴权。

---

## 10. 推荐的权限控制粒度

建议权限至少覆盖到这几层：

### 10.1 API 级

- `tasks:create`
- `tasks:read`
- `tasks:cancel`
- `tasks:list`

### 10.2 Resource 级

- `task:read:own`
- `task:read:tenant`
- `artifact:read:own`
- `memory:read:user`
- `memory:write:user`

### 10.3 Capability 级

- `tool_group:project_write`
- `tool_group:sandbox_exec`
- `tool_group:web_search`
- `sandbox_profile:research-net`
- `sandbox_profile:secure-offline`

### 10.4 Policy 级

- 最大 token 预算
- 最大并发任务数
- 最大活跃 sandbox 数
- 最大附件大小

---

## 11. 审计设计

身份体系和审计必须一起设计。

每条关键日志都建议带上：

- `request_id`
- `tenant_id`
- `principal_id`
- `user_id`
- `session_id`
- `task_id`
- `run_id`
- `subtask_id`
- `agent_id`
- `sandbox_id`
- `tool_name`

这样后续才能回答：

- 谁提交了这个任务
- 谁触发了这个 run
- 谁使用了外网 sandbox
- 谁调用了某个敏感 tool

---

## 12. 推荐最小落地方案

如果你现在还处于设计阶段，建议 MVP 按下面方式定义：

### 12.1 Identity MVP

1. 支持 API Key
2. API Key 绑定 `tenant_id + user_id`
3. 固定一组基础 roles
4. 固定一组基础 scopes
5. Gateway 内做 basic authorization

### 12.2 Tenant MVP

1. 定义 `tenant_id`
2. 所有 task/session/memory 绑定 tenant
3. 所有 query 默认 tenant 隔离
4. 做基础 quota 设计

### 12.3 User MVP

1. 定义 `user_id`
2. task/session/memory 绑定 user
3. transcript 记录 submitted_by
4. query 接口支持 own / tenant 视角

这是最少但必须有的身份骨架。

---

## 13. 与后续代码实现的映射建议

虽然这阶段不改代码，但后续建议至少会落成这些模块：

```text
swarmmind/identity/
  models.py          # Tenant/User/IdentityContext
  auth.py            # API key / JWT 校验
  resolver.py        # claim -> internal identity
  policy.py          # 授权与细粒度策略
  repository.py      # tenant/user/key 存储
```

Gateway 则消费这套身份层：

```text
swarmmind/gateway/
  gateway.py
  admission.py
  session_manager.py
  dispatcher.py
```

关系应当是：

- identity 提供身份与权限结果
- gateway 消费身份与权限结果
- orchestrator 消费 gateway 归一化后的任务上下文

---

## 14. 最终建议

对于 SwarmMind 来说，租户、用户、认证、授权不是后期再补的“平台功能”，而是现在就应该定义边界的基础系统。

建议优先级如下：

1. 先完成 Gateway 设计
2. 再完成 Tenant / User / Auth 架构设计
3. 再把这两者的统一身份上下文喂给 Memory / Sandbox / Task 系统

一句话总结：

**Gateway 负责入口控制，Identity System 负责入口身份，二者必须一起设计。**
