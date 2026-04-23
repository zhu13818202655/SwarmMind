# System API

## 基本信息

| 属性 | 值 |
|------|------|
| Host | `http://61.169.171.82:50001` |
| Base Path | `/system` |

## 认证信息

### 公共请求头

| Header | 值 | 说明 |
|--------|------|------|
| `back-token` | `{your_token}` | 登录后获取的访问令牌，所有受保护接口必须携带 |

### 管理员账号

| 属性 | 值 |
|------|------|
| 账号 | `admin` |
| 密码 | `1qazXSW@4321` |

> 使用管理员账号调用 `/system/user/login` 接口获取 `back-token`，后续请求在 Header 中携带该 Token。

---

## API概览

共 **162** 个接口，分为 **15** 个模块：

- **用户信息控制层**: 40 个接口
- **角色信息控制层**: 15 个接口
- **浙政钉接口**: 3 个接口
- **场景标签管理**: 6 个接口
- **岗位信息控制层**: 9 个接口
- **操作日志记录接口**: 8 个接口
- **菜单信息控制层**: 10 个接口
- **字典类型表接口**: 9 个接口
- **字典数据表接口**: 9 个接口
- **部门信息控制层**: 24 个接口
- **参数配置表接口**: 7 个接口
- **通用接口**: 1 个接口
- **全国地区表接口**: 5 个接口
- **应用表控制层**: 15 个接口
- **短信接口**: 1 个接口

---

## 接口详情

### 用户信息控制层

#### 状态修改

| 属性 | 值 |
|------|------|
| 请求方法 | `PUT` |
| 请求路径 | `/system/user/changeStatus` |
| OperationId | `changeStatus` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysUserDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "userId": 1,
  "deptId": 1,
  "dept": {
    "beginTime": "string_value",
    "endTime": "string_value",
    "params": {},
    "deptId": 1,
    "parentId": 1,
    "parentName": "示例名称",
    "deptCode": "string_value",
    "parentCode": "string_value",
    "levelType": 1,
    "ancestors": "string_value",
    "deptName": "示例名称",
    "shortName": "string_value",
    "orderNum": 1,
    "userSortNum": 1,
    "leader": "string_value",
    "contact": "string_value",
    "position": "string_value",
    "phone": "13800138000",
    "email": "user@example.com",
    "status": true,
    "isCommandSystem": true,
    "delFlag": true,
    "createBy": "string_value",
    "createTime": "2024-01-01T00:00:00",
    "updateBy": "string_value",
    "updateTime": "2024-01-01T00:00:00",
    "typeCode": "string_value",
    "typeName": "string_value",
    "address": "string_value",
    "divisionCode": "string_value",
    "institutionCode": "string_value",
    "unifiedSocialCreditCode": "string_value",
    "institutionLevelCode": "string_value",
    "isSync": true,
    "sourceType": 1,
    "zzdStatus": "string_value",
    "children": [
      "<SysDeptDO>"
    ],
    "parent": "<SysDeptDO>",
    "posJob": "string_value",
    "leaderName": "string_value",
    "streetName": "string_value",
    "hasChildren": true
  },
  "deptList": [
    {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "deptId": 1,
      "parentId": 1,
      "parentName": "示例名称",
      "deptCode": "string_value",
      "parentCode": "string_value",
      "levelType": 1,
      "ancestors": "string_value",
      "deptName": "示例名称",
      "shortName": "string_value",
      "orderNum": 1,
      "userSortNum": 1,
      "leader": "string_value",
      "contact": "string_value",
      "position": "string_value",
      "phone": "13800138000",
      "email": "user@example.com",
      "status": true,
      "isCommandSystem": true,
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "typeCode": "string_value",
      "typeName": "string_value",
      "address": "string_value",
      "divisionCode": "string_value",
      "institutionCode": "string_value",
      "unifiedSocialCreditCode": "string_value",
      "institutionLevelCode": "string_value",
      "isSync": true,
      "sourceType": 1,
      "zzdStatus": "string_value",
      "children": [
        "<SysDeptDO>"
      ],
      "parent": "<SysDeptDO>",
      "posJob": "string_value",
      "leaderName": "string_value",
      "streetName": "string_value",
      "hasChildren": true
    }
  ],
  "authUserIds": [
    1
  ],
  "authDeptIds": [
    1
  ],
  "selectDeptId": 1,
  "userDeptList": [
    {
      "userId": 1,
      "deptId": 1,
      "orderInOrganization": 1,
      "posJobRankCode": "string_value",
      "mainJob": true,
      "status": "1",
      "govEmpPosJob": "string_value",
      "govEmpPosPhoneNo": "string_value",
      "sourceType": 1,
      "deptCode": "CODE001",
      "deptName": "示例名称",
      "parentName": "示例名称"
    }
  ],
  "account": "string_value",
  "userName": "示例名称",
  "employeeCode": "CODE001",
  "empPoliticalStatusCode": "string_value",
  "empJobLevelCode": "string_value",
  "empBudgetedPostCode": "string_value",
  "nickName": "string_value",
  "email": "user@example.com",
  "phoneNum": "13800138000",
  "sex": "string_value",
  "avatar": "http://example.com",
  "password": "password123",
  "passwordTime": "2024-01-01T00:00:00",
  "smsCodeTime": "2024-01-01T00:00:00",
  "loginFailCount": 1,
  "loginLockTime": "2024-01-01T00:00:00",
  "isSmsLogin": true,
  "status": 1,
  "isSync": true,
  "sourceType": 1,
  "zzdStatus": "string_value",
  "loginIp": "string_value",
  "loginTime": "2024-01-01T00:00:00",
  "expireTime": "2024-01-01T00:00:00",
  "delFlag": true,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "idCard": "string_value",
  "remark": "string_value",
  "dhUserCode": "CODE001",
  "dhUserName": "string_value",
  "dhUserPassword": "password123",
  "token": "string_value",
  "phoneNotNull": true,
  "keyword": "string_value",
  "deptName": "string_value",
  "roles": [
    {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "roleId": 1,
      "roleName": "示例名称",
      "roleGroup": "string_value",
      "roleKey": "string_value",
      "roleSort": 1,
      "dataScope": "string_value",
      "status": true,
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "remark": "string_value",
      "isApprover": true,
      "flag": true,
      "appKeys": [
        "string_value"
      ],
      "menuIds": [
        1
      ],
      "deptIds": [
        1
      ],
      "permissions": [
        "string_value"
      ],
      "admin": true
    }
  ],
  "apps": [
    {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "appId": 1,
      "appName": "示例名称",
      "type": 1,
      "types": [
        1
      ],
      "appKey": "string_value",
      "appSecret": "string_value",
      "pcUrl": "http://example.com",
      "iconUrl": "string_value",
      "sort": 1,
      "status": 1,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "remark": "string_value"
    }
  ],
  "roleId": 1,
  "roleIds": [
    1
  ],
  "postIds": [
    1
  ],
  "roleNames": "string_value",
  "appPerms": {},
  "permissions": [
    "string_value"
  ],
  "postNames": "string_value",
  "posJob": "string_value",
  "deptNames": "string_value",
  "streetDeptId": 1,
  "streetCode": "string_value",
  "streetName": "string_value",
  "gpsX": 1.0,
  "gpsY": 1.0,
  "passwordRemind": true,
  "admin": true
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 用户授权角色

| 属性 | 值 |
|------|------|
| 请求方法 | `PUT` |
| 请求路径 | `/system/user/authRole` |
| OperationId | `insertAuthRole` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `userId` | query | integer(int64) | 是 |  |
| `roleIds` | query | array<integer(int64)> | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `Response`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {}
  }
  ```

---

#### 修改保存用户信息

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/user/update` |
| OperationId | `edit` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysUserDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "userId": 1,
  "deptId": 1,
  "dept": {
    "beginTime": "string_value",
    "endTime": "string_value",
    "params": {},
    "deptId": 1,
    "parentId": 1,
    "parentName": "示例名称",
    "deptCode": "string_value",
    "parentCode": "string_value",
    "levelType": 1,
    "ancestors": "string_value",
    "deptName": "示例名称",
    "shortName": "string_value",
    "orderNum": 1,
    "userSortNum": 1,
    "leader": "string_value",
    "contact": "string_value",
    "position": "string_value",
    "phone": "13800138000",
    "email": "user@example.com",
    "status": true,
    "isCommandSystem": true,
    "delFlag": true,
    "createBy": "string_value",
    "createTime": "2024-01-01T00:00:00",
    "updateBy": "string_value",
    "updateTime": "2024-01-01T00:00:00",
    "typeCode": "string_value",
    "typeName": "string_value",
    "address": "string_value",
    "divisionCode": "string_value",
    "institutionCode": "string_value",
    "unifiedSocialCreditCode": "string_value",
    "institutionLevelCode": "string_value",
    "isSync": true,
    "sourceType": 1,
    "zzdStatus": "string_value",
    "children": [
      "<SysDeptDO>"
    ],
    "parent": "<SysDeptDO>",
    "posJob": "string_value",
    "leaderName": "string_value",
    "streetName": "string_value",
    "hasChildren": true
  },
  "deptList": [
    {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "deptId": 1,
      "parentId": 1,
      "parentName": "示例名称",
      "deptCode": "string_value",
      "parentCode": "string_value",
      "levelType": 1,
      "ancestors": "string_value",
      "deptName": "示例名称",
      "shortName": "string_value",
      "orderNum": 1,
      "userSortNum": 1,
      "leader": "string_value",
      "contact": "string_value",
      "position": "string_value",
      "phone": "13800138000",
      "email": "user@example.com",
      "status": true,
      "isCommandSystem": true,
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "typeCode": "string_value",
      "typeName": "string_value",
      "address": "string_value",
      "divisionCode": "string_value",
      "institutionCode": "string_value",
      "unifiedSocialCreditCode": "string_value",
      "institutionLevelCode": "string_value",
      "isSync": true,
      "sourceType": 1,
      "zzdStatus": "string_value",
      "children": [
        "<SysDeptDO>"
      ],
      "parent": "<SysDeptDO>",
      "posJob": "string_value",
      "leaderName": "string_value",
      "streetName": "string_value",
      "hasChildren": true
    }
  ],
  "authUserIds": [
    1
  ],
  "authDeptIds": [
    1
  ],
  "selectDeptId": 1,
  "userDeptList": [
    {
      "userId": 1,
      "deptId": 1,
      "orderInOrganization": 1,
      "posJobRankCode": "string_value",
      "mainJob": true,
      "status": "1",
      "govEmpPosJob": "string_value",
      "govEmpPosPhoneNo": "string_value",
      "sourceType": 1,
      "deptCode": "CODE001",
      "deptName": "示例名称",
      "parentName": "示例名称"
    }
  ],
  "account": "string_value",
  "userName": "示例名称",
  "employeeCode": "CODE001",
  "empPoliticalStatusCode": "string_value",
  "empJobLevelCode": "string_value",
  "empBudgetedPostCode": "string_value",
  "nickName": "string_value",
  "email": "user@example.com",
  "phoneNum": "13800138000",
  "sex": "string_value",
  "avatar": "http://example.com",
  "password": "password123",
  "passwordTime": "2024-01-01T00:00:00",
  "smsCodeTime": "2024-01-01T00:00:00",
  "loginFailCount": 1,
  "loginLockTime": "2024-01-01T00:00:00",
  "isSmsLogin": true,
  "status": 1,
  "isSync": true,
  "sourceType": 1,
  "zzdStatus": "string_value",
  "loginIp": "string_value",
  "loginTime": "2024-01-01T00:00:00",
  "expireTime": "2024-01-01T00:00:00",
  "delFlag": true,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "idCard": "string_value",
  "remark": "string_value",
  "dhUserCode": "CODE001",
  "dhUserName": "string_value",
  "dhUserPassword": "password123",
  "token": "string_value",
  "phoneNotNull": true,
  "keyword": "string_value",
  "deptName": "string_value",
  "roles": [
    {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "roleId": 1,
      "roleName": "示例名称",
      "roleGroup": "string_value",
      "roleKey": "string_value",
      "roleSort": 1,
      "dataScope": "string_value",
      "status": true,
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "remark": "string_value",
      "isApprover": true,
      "flag": true,
      "appKeys": [
        "string_value"
      ],
      "menuIds": [
        1
      ],
      "deptIds": [
        1
      ],
      "permissions": [
        "string_value"
      ],
      "admin": true
    }
  ],
  "apps": [
    {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "appId": 1,
      "appName": "示例名称",
      "type": 1,
      "types": [
        1
      ],
      "appKey": "string_value",
      "appSecret": "string_value",
      "pcUrl": "http://example.com",
      "iconUrl": "string_value",
      "sort": 1,
      "status": 1,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "remark": "string_value"
    }
  ],
  "roleId": 1,
  "roleIds": [
    1
  ],
  "postIds": [
    1
  ],
  "roleNames": "string_value",
  "appPerms": {},
  "permissions": [
    "string_value"
  ],
  "postNames": "string_value",
  "posJob": "string_value",
  "deptNames": "string_value",
  "streetDeptId": 1,
  "streetCode": "string_value",
  "streetName": "string_value",
  "gpsX": 1.0,
  "gpsY": 1.0,
  "passwordRemind": true,
  "admin": true
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 保存大华用户编码

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/user/updateUserByDh` |
| OperationId | `updateUserByDh` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysUserDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "userId": 1,
  "deptId": 1,
  "dept": {
    "beginTime": "string_value",
    "endTime": "string_value",
    "params": {},
    "deptId": 1,
    "parentId": 1,
    "parentName": "示例名称",
    "deptCode": "string_value",
    "parentCode": "string_value",
    "levelType": 1,
    "ancestors": "string_value",
    "deptName": "示例名称",
    "shortName": "string_value",
    "orderNum": 1,
    "userSortNum": 1,
    "leader": "string_value",
    "contact": "string_value",
    "position": "string_value",
    "phone": "13800138000",
    "email": "user@example.com",
    "status": true,
    "isCommandSystem": true,
    "delFlag": true,
    "createBy": "string_value",
    "createTime": "2024-01-01T00:00:00",
    "updateBy": "string_value",
    "updateTime": "2024-01-01T00:00:00",
    "typeCode": "string_value",
    "typeName": "string_value",
    "address": "string_value",
    "divisionCode": "string_value",
    "institutionCode": "string_value",
    "unifiedSocialCreditCode": "string_value",
    "institutionLevelCode": "string_value",
    "isSync": true,
    "sourceType": 1,
    "zzdStatus": "string_value",
    "children": [
      "<SysDeptDO>"
    ],
    "parent": "<SysDeptDO>",
    "posJob": "string_value",
    "leaderName": "string_value",
    "streetName": "string_value",
    "hasChildren": true
  },
  "deptList": [
    {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "deptId": 1,
      "parentId": 1,
      "parentName": "示例名称",
      "deptCode": "string_value",
      "parentCode": "string_value",
      "levelType": 1,
      "ancestors": "string_value",
      "deptName": "示例名称",
      "shortName": "string_value",
      "orderNum": 1,
      "userSortNum": 1,
      "leader": "string_value",
      "contact": "string_value",
      "position": "string_value",
      "phone": "13800138000",
      "email": "user@example.com",
      "status": true,
      "isCommandSystem": true,
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "typeCode": "string_value",
      "typeName": "string_value",
      "address": "string_value",
      "divisionCode": "string_value",
      "institutionCode": "string_value",
      "unifiedSocialCreditCode": "string_value",
      "institutionLevelCode": "string_value",
      "isSync": true,
      "sourceType": 1,
      "zzdStatus": "string_value",
      "children": [
        "<SysDeptDO>"
      ],
      "parent": "<SysDeptDO>",
      "posJob": "string_value",
      "leaderName": "string_value",
      "streetName": "string_value",
      "hasChildren": true
    }
  ],
  "authUserIds": [
    1
  ],
  "authDeptIds": [
    1
  ],
  "selectDeptId": 1,
  "userDeptList": [
    {
      "userId": 1,
      "deptId": 1,
      "orderInOrganization": 1,
      "posJobRankCode": "string_value",
      "mainJob": true,
      "status": "1",
      "govEmpPosJob": "string_value",
      "govEmpPosPhoneNo": "string_value",
      "sourceType": 1,
      "deptCode": "CODE001",
      "deptName": "示例名称",
      "parentName": "示例名称"
    }
  ],
  "account": "string_value",
  "userName": "示例名称",
  "employeeCode": "CODE001",
  "empPoliticalStatusCode": "string_value",
  "empJobLevelCode": "string_value",
  "empBudgetedPostCode": "string_value",
  "nickName": "string_value",
  "email": "user@example.com",
  "phoneNum": "13800138000",
  "sex": "string_value",
  "avatar": "http://example.com",
  "password": "password123",
  "passwordTime": "2024-01-01T00:00:00",
  "smsCodeTime": "2024-01-01T00:00:00",
  "loginFailCount": 1,
  "loginLockTime": "2024-01-01T00:00:00",
  "isSmsLogin": true,
  "status": 1,
  "isSync": true,
  "sourceType": 1,
  "zzdStatus": "string_value",
  "loginIp": "string_value",
  "loginTime": "2024-01-01T00:00:00",
  "expireTime": "2024-01-01T00:00:00",
  "delFlag": true,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "idCard": "string_value",
  "remark": "string_value",
  "dhUserCode": "CODE001",
  "dhUserName": "string_value",
  "dhUserPassword": "password123",
  "token": "string_value",
  "phoneNotNull": true,
  "keyword": "string_value",
  "deptName": "string_value",
  "roles": [
    {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "roleId": 1,
      "roleName": "示例名称",
      "roleGroup": "string_value",
      "roleKey": "string_value",
      "roleSort": 1,
      "dataScope": "string_value",
      "status": true,
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "remark": "string_value",
      "isApprover": true,
      "flag": true,
      "appKeys": [
        "string_value"
      ],
      "menuIds": [
        1
      ],
      "deptIds": [
        1
      ],
      "permissions": [
        "string_value"
      ],
      "admin": true
    }
  ],
  "apps": [
    {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "appId": 1,
      "appName": "示例名称",
      "type": 1,
      "types": [
        1
      ],
      "appKey": "string_value",
      "appSecret": "string_value",
      "pcUrl": "http://example.com",
      "iconUrl": "string_value",
      "sort": 1,
      "status": 1,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "remark": "string_value"
    }
  ],
  "roleId": 1,
  "roleIds": [
    1
  ],
  "postIds": [
    1
  ],
  "roleNames": "string_value",
  "appPerms": {},
  "permissions": [
    "string_value"
  ],
  "postNames": "string_value",
  "posJob": "string_value",
  "deptNames": "string_value",
  "streetDeptId": 1,
  "streetCode": "string_value",
  "streetName": "string_value",
  "gpsX": 1.0,
  "gpsY": 1.0,
  "passwordRemind": true,
  "admin": true
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 系统用户中更新大华用户信息

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/user/updateSysUserByDh` |
| OperationId | `updateSysUserByDh` |

**请求体：**

- Content-Type: `application/json`
- Schema: `JSONArray`

**请求示例：**
```json
{
  "empty": true,
  "componentType": {
    "typeName": "string_value"
  },
  "relatedArray": {},
  "first": {},
  "last": {}
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### /user/updateManageDept

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/user/updateManageDept` |
| OperationId | `updateManageDept` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysUserPostDO`

**请求示例：**
```json
{
  "userId": 1,
  "postId": 1,
  "manageDept": "100",
  "manageDeptName": "示例名称",
  "createTime": "2024-01-01T00:00:00"
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 新增用户

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/user/save` |
| OperationId | `addUser` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysUserDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "userId": 1,
  "deptId": 1,
  "dept": {
    "beginTime": "string_value",
    "endTime": "string_value",
    "params": {},
    "deptId": 1,
    "parentId": 1,
    "parentName": "示例名称",
    "deptCode": "string_value",
    "parentCode": "string_value",
    "levelType": 1,
    "ancestors": "string_value",
    "deptName": "示例名称",
    "shortName": "string_value",
    "orderNum": 1,
    "userSortNum": 1,
    "leader": "string_value",
    "contact": "string_value",
    "position": "string_value",
    "phone": "13800138000",
    "email": "user@example.com",
    "status": true,
    "isCommandSystem": true,
    "delFlag": true,
    "createBy": "string_value",
    "createTime": "2024-01-01T00:00:00",
    "updateBy": "string_value",
    "updateTime": "2024-01-01T00:00:00",
    "typeCode": "string_value",
    "typeName": "string_value",
    "address": "string_value",
    "divisionCode": "string_value",
    "institutionCode": "string_value",
    "unifiedSocialCreditCode": "string_value",
    "institutionLevelCode": "string_value",
    "isSync": true,
    "sourceType": 1,
    "zzdStatus": "string_value",
    "children": [
      "<SysDeptDO>"
    ],
    "parent": "<SysDeptDO>",
    "posJob": "string_value",
    "leaderName": "string_value",
    "streetName": "string_value",
    "hasChildren": true
  },
  "deptList": [
    {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "deptId": 1,
      "parentId": 1,
      "parentName": "示例名称",
      "deptCode": "string_value",
      "parentCode": "string_value",
      "levelType": 1,
      "ancestors": "string_value",
      "deptName": "示例名称",
      "shortName": "string_value",
      "orderNum": 1,
      "userSortNum": 1,
      "leader": "string_value",
      "contact": "string_value",
      "position": "string_value",
      "phone": "13800138000",
      "email": "user@example.com",
      "status": true,
      "isCommandSystem": true,
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "typeCode": "string_value",
      "typeName": "string_value",
      "address": "string_value",
      "divisionCode": "string_value",
      "institutionCode": "string_value",
      "unifiedSocialCreditCode": "string_value",
      "institutionLevelCode": "string_value",
      "isSync": true,
      "sourceType": 1,
      "zzdStatus": "string_value",
      "children": [
        "<SysDeptDO>"
      ],
      "parent": "<SysDeptDO>",
      "posJob": "string_value",
      "leaderName": "string_value",
      "streetName": "string_value",
      "hasChildren": true
    }
  ],
  "authUserIds": [
    1
  ],
  "authDeptIds": [
    1
  ],
  "selectDeptId": 1,
  "userDeptList": [
    {
      "userId": 1,
      "deptId": 1,
      "orderInOrganization": 1,
      "posJobRankCode": "string_value",
      "mainJob": true,
      "status": "1",
      "govEmpPosJob": "string_value",
      "govEmpPosPhoneNo": "string_value",
      "sourceType": 1,
      "deptCode": "CODE001",
      "deptName": "示例名称",
      "parentName": "示例名称"
    }
  ],
  "account": "string_value",
  "userName": "示例名称",
  "employeeCode": "CODE001",
  "empPoliticalStatusCode": "string_value",
  "empJobLevelCode": "string_value",
  "empBudgetedPostCode": "string_value",
  "nickName": "string_value",
  "email": "user@example.com",
  "phoneNum": "13800138000",
  "sex": "string_value",
  "avatar": "http://example.com",
  "password": "password123",
  "passwordTime": "2024-01-01T00:00:00",
  "smsCodeTime": "2024-01-01T00:00:00",
  "loginFailCount": 1,
  "loginLockTime": "2024-01-01T00:00:00",
  "isSmsLogin": true,
  "status": 1,
  "isSync": true,
  "sourceType": 1,
  "zzdStatus": "string_value",
  "loginIp": "string_value",
  "loginTime": "2024-01-01T00:00:00",
  "expireTime": "2024-01-01T00:00:00",
  "delFlag": true,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "idCard": "string_value",
  "remark": "string_value",
  "dhUserCode": "CODE001",
  "dhUserName": "string_value",
  "dhUserPassword": "password123",
  "token": "string_value",
  "phoneNotNull": true,
  "keyword": "string_value",
  "deptName": "string_value",
  "roles": [
    {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "roleId": 1,
      "roleName": "示例名称",
      "roleGroup": "string_value",
      "roleKey": "string_value",
      "roleSort": 1,
      "dataScope": "string_value",
      "status": true,
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "remark": "string_value",
      "isApprover": true,
      "flag": true,
      "appKeys": [
        "string_value"
      ],
      "menuIds": [
        1
      ],
      "deptIds": [
        1
      ],
      "permissions": [
        "string_value"
      ],
      "admin": true
    }
  ],
  "apps": [
    {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "appId": 1,
      "appName": "示例名称",
      "type": 1,
      "types": [
        1
      ],
      "appKey": "string_value",
      "appSecret": "string_value",
      "pcUrl": "http://example.com",
      "iconUrl": "string_value",
      "sort": 1,
      "status": 1,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "remark": "string_value"
    }
  ],
  "roleId": 1,
  "roleIds": [
    1
  ],
  "postIds": [
    1
  ],
  "roleNames": "string_value",
  "appPerms": {},
  "permissions": [
    "string_value"
  ],
  "postNames": "string_value",
  "posJob": "string_value",
  "deptNames": "string_value",
  "streetDeptId": 1,
  "streetCode": "string_value",
  "streetName": "string_value",
  "gpsX": 1.0,
  "gpsY": 1.0,
  "passwordRemind": true,
  "admin": true
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 重置密码

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/user/resetPwd` |
| OperationId | `restPassword` |

**请求体：**

- Content-Type: `application/json`
- Schema: `UserRestPwdRequest`

**请求示例：**
```json
{
  "id": 1,
  "account": "string_value",
  "password": "password123"
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 用户直接修改密码

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/user/modify-pass` |
| OperationId | `modifyPass` |

**请求体：**

- Content-Type: `application/json`
- Schema: `UserPwdRequest`

**请求示例：**
```json
{
  "oldPassword": "password123",
  "newPassword": "password123"
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### /user/logout

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/user/logout` |
| OperationId | `logout` |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### /user/logoutApproval

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/user/logoutApproval` |
| OperationId | `logoutApproval` |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 账号密码登录

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/user/login` |
| OperationId | `login` |

**请求体：**

- Content-Type: `application/json`
- Schema: `UserLoginRequest`

**请求示例：**
```json
{
  "account": "string_value",
  "password": "password123",
  "phoneNum": "string_value",
  "code": "string_value",
  "employeeCode": "string_value",
  "appId": "string_value"
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseAccessTokenVO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "accessToken": "string_value",
      "expiresIn": 1,
      "iotToken": "string_value"
    }
  }
  ```

---

#### 账号密码登录

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/user/loginApproval` |
| OperationId | `loginApproval` |

**请求体：**

- Content-Type: `application/json`
- Schema: `UserLoginRequest`

**请求示例：**
```json
{
  "account": "string_value",
  "password": "password123",
  "phoneNum": "string_value",
  "code": "string_value",
  "employeeCode": "string_value",
  "appId": "string_value"
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseAccessTokenVO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "accessToken": "string_value",
      "expiresIn": 1,
      "iotToken": "string_value"
    }
  }
  ```

---

#### 一网统管跳转

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/user/getAcessToken` |
| OperationId | `getAcessToken` |

**请求体：**

- Content-Type: `application/json`
- Schema: `UserLoginRequest`

**请求示例：**
```json
{
  "account": "string_value",
  "password": "password123",
  "phoneNum": "string_value",
  "code": "string_value",
  "employeeCode": "string_value",
  "appId": "string_value"
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseAccessTokenVO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "accessToken": "string_value",
      "expiresIn": 1,
      "iotToken": "string_value"
    }
  }
  ```

---

#### 电子政务登录

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/user/getAcessTokenByDzzw` |
| OperationId | `getAcessTokenByDzzw` |

**请求体：**

- Content-Type: `application/json`
- Schema: `UserLoginRequest`

**请求示例：**
```json
{
  "account": "string_value",
  "password": "password123",
  "phoneNum": "string_value",
  "code": "string_value",
  "employeeCode": "string_value",
  "appId": "string_value"
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseAccessTokenVO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "accessToken": "string_value",
      "expiresIn": 1,
      "iotToken": "string_value"
    }
  }
  ```

---

#### 用户列表导出

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/user/export` |
| OperationId | `export` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysUserDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "userId": 1,
  "deptId": 1,
  "dept": {
    "beginTime": "string_value",
    "endTime": "string_value",
    "params": {},
    "deptId": 1,
    "parentId": 1,
    "parentName": "示例名称",
    "deptCode": "string_value",
    "parentCode": "string_value",
    "levelType": 1,
    "ancestors": "string_value",
    "deptName": "示例名称",
    "shortName": "string_value",
    "orderNum": 1,
    "userSortNum": 1,
    "leader": "string_value",
    "contact": "string_value",
    "position": "string_value",
    "phone": "13800138000",
    "email": "user@example.com",
    "status": true,
    "isCommandSystem": true,
    "delFlag": true,
    "createBy": "string_value",
    "createTime": "2024-01-01T00:00:00",
    "updateBy": "string_value",
    "updateTime": "2024-01-01T00:00:00",
    "typeCode": "string_value",
    "typeName": "string_value",
    "address": "string_value",
    "divisionCode": "string_value",
    "institutionCode": "string_value",
    "unifiedSocialCreditCode": "string_value",
    "institutionLevelCode": "string_value",
    "isSync": true,
    "sourceType": 1,
    "zzdStatus": "string_value",
    "children": [
      "<SysDeptDO>"
    ],
    "parent": "<SysDeptDO>",
    "posJob": "string_value",
    "leaderName": "string_value",
    "streetName": "string_value",
    "hasChildren": true
  },
  "deptList": [
    {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "deptId": 1,
      "parentId": 1,
      "parentName": "示例名称",
      "deptCode": "string_value",
      "parentCode": "string_value",
      "levelType": 1,
      "ancestors": "string_value",
      "deptName": "示例名称",
      "shortName": "string_value",
      "orderNum": 1,
      "userSortNum": 1,
      "leader": "string_value",
      "contact": "string_value",
      "position": "string_value",
      "phone": "13800138000",
      "email": "user@example.com",
      "status": true,
      "isCommandSystem": true,
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "typeCode": "string_value",
      "typeName": "string_value",
      "address": "string_value",
      "divisionCode": "string_value",
      "institutionCode": "string_value",
      "unifiedSocialCreditCode": "string_value",
      "institutionLevelCode": "string_value",
      "isSync": true,
      "sourceType": 1,
      "zzdStatus": "string_value",
      "children": [
        "<SysDeptDO>"
      ],
      "parent": "<SysDeptDO>",
      "posJob": "string_value",
      "leaderName": "string_value",
      "streetName": "string_value",
      "hasChildren": true
    }
  ],
  "authUserIds": [
    1
  ],
  "authDeptIds": [
    1
  ],
  "selectDeptId": 1,
  "userDeptList": [
    {
      "userId": 1,
      "deptId": 1,
      "orderInOrganization": 1,
      "posJobRankCode": "string_value",
      "mainJob": true,
      "status": "1",
      "govEmpPosJob": "string_value",
      "govEmpPosPhoneNo": "string_value",
      "sourceType": 1,
      "deptCode": "CODE001",
      "deptName": "示例名称",
      "parentName": "示例名称"
    }
  ],
  "account": "string_value",
  "userName": "示例名称",
  "employeeCode": "CODE001",
  "empPoliticalStatusCode": "string_value",
  "empJobLevelCode": "string_value",
  "empBudgetedPostCode": "string_value",
  "nickName": "string_value",
  "email": "user@example.com",
  "phoneNum": "13800138000",
  "sex": "string_value",
  "avatar": "http://example.com",
  "password": "password123",
  "passwordTime": "2024-01-01T00:00:00",
  "smsCodeTime": "2024-01-01T00:00:00",
  "loginFailCount": 1,
  "loginLockTime": "2024-01-01T00:00:00",
  "isSmsLogin": true,
  "status": 1,
  "isSync": true,
  "sourceType": 1,
  "zzdStatus": "string_value",
  "loginIp": "string_value",
  "loginTime": "2024-01-01T00:00:00",
  "expireTime": "2024-01-01T00:00:00",
  "delFlag": true,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "idCard": "string_value",
  "remark": "string_value",
  "dhUserCode": "CODE001",
  "dhUserName": "string_value",
  "dhUserPassword": "password123",
  "token": "string_value",
  "phoneNotNull": true,
  "keyword": "string_value",
  "deptName": "string_value",
  "roles": [
    {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "roleId": 1,
      "roleName": "示例名称",
      "roleGroup": "string_value",
      "roleKey": "string_value",
      "roleSort": 1,
      "dataScope": "string_value",
      "status": true,
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "remark": "string_value",
      "isApprover": true,
      "flag": true,
      "appKeys": [
        "string_value"
      ],
      "menuIds": [
        1
      ],
      "deptIds": [
        1
      ],
      "permissions": [
        "string_value"
      ],
      "admin": true
    }
  ],
  "apps": [
    {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "appId": 1,
      "appName": "示例名称",
      "type": 1,
      "types": [
        1
      ],
      "appKey": "string_value",
      "appSecret": "string_value",
      "pcUrl": "http://example.com",
      "iconUrl": "string_value",
      "sort": 1,
      "status": 1,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "remark": "string_value"
    }
  ],
  "roleId": 1,
  "roleIds": [
    1
  ],
  "postIds": [
    1
  ],
  "roleNames": "string_value",
  "appPerms": {},
  "permissions": [
    "string_value"
  ],
  "postNames": "string_value",
  "posJob": "string_value",
  "deptNames": "string_value",
  "streetDeptId": 1,
  "streetCode": "string_value",
  "streetName": "string_value",
  "gpsX": 1.0,
  "gpsY": 1.0,
  "passwordRemind": true,
  "admin": true
}
```

**响应：**

- **200**: OK

---

#### /user/edit

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/user/edit` |
| OperationId | `editUser` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysUserDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "userId": 1,
  "deptId": 1,
  "dept": {
    "beginTime": "string_value",
    "endTime": "string_value",
    "params": {},
    "deptId": 1,
    "parentId": 1,
    "parentName": "示例名称",
    "deptCode": "string_value",
    "parentCode": "string_value",
    "levelType": 1,
    "ancestors": "string_value",
    "deptName": "示例名称",
    "shortName": "string_value",
    "orderNum": 1,
    "userSortNum": 1,
    "leader": "string_value",
    "contact": "string_value",
    "position": "string_value",
    "phone": "13800138000",
    "email": "user@example.com",
    "status": true,
    "isCommandSystem": true,
    "delFlag": true,
    "createBy": "string_value",
    "createTime": "2024-01-01T00:00:00",
    "updateBy": "string_value",
    "updateTime": "2024-01-01T00:00:00",
    "typeCode": "string_value",
    "typeName": "string_value",
    "address": "string_value",
    "divisionCode": "string_value",
    "institutionCode": "string_value",
    "unifiedSocialCreditCode": "string_value",
    "institutionLevelCode": "string_value",
    "isSync": true,
    "sourceType": 1,
    "zzdStatus": "string_value",
    "children": [
      "<SysDeptDO>"
    ],
    "parent": "<SysDeptDO>",
    "posJob": "string_value",
    "leaderName": "string_value",
    "streetName": "string_value",
    "hasChildren": true
  },
  "deptList": [
    {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "deptId": 1,
      "parentId": 1,
      "parentName": "示例名称",
      "deptCode": "string_value",
      "parentCode": "string_value",
      "levelType": 1,
      "ancestors": "string_value",
      "deptName": "示例名称",
      "shortName": "string_value",
      "orderNum": 1,
      "userSortNum": 1,
      "leader": "string_value",
      "contact": "string_value",
      "position": "string_value",
      "phone": "13800138000",
      "email": "user@example.com",
      "status": true,
      "isCommandSystem": true,
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "typeCode": "string_value",
      "typeName": "string_value",
      "address": "string_value",
      "divisionCode": "string_value",
      "institutionCode": "string_value",
      "unifiedSocialCreditCode": "string_value",
      "institutionLevelCode": "string_value",
      "isSync": true,
      "sourceType": 1,
      "zzdStatus": "string_value",
      "children": [
        "<SysDeptDO>"
      ],
      "parent": "<SysDeptDO>",
      "posJob": "string_value",
      "leaderName": "string_value",
      "streetName": "string_value",
      "hasChildren": true
    }
  ],
  "authUserIds": [
    1
  ],
  "authDeptIds": [
    1
  ],
  "selectDeptId": 1,
  "userDeptList": [
    {
      "userId": 1,
      "deptId": 1,
      "orderInOrganization": 1,
      "posJobRankCode": "string_value",
      "mainJob": true,
      "status": "1",
      "govEmpPosJob": "string_value",
      "govEmpPosPhoneNo": "string_value",
      "sourceType": 1,
      "deptCode": "CODE001",
      "deptName": "示例名称",
      "parentName": "示例名称"
    }
  ],
  "account": "string_value",
  "userName": "示例名称",
  "employeeCode": "CODE001",
  "empPoliticalStatusCode": "string_value",
  "empJobLevelCode": "string_value",
  "empBudgetedPostCode": "string_value",
  "nickName": "string_value",
  "email": "user@example.com",
  "phoneNum": "13800138000",
  "sex": "string_value",
  "avatar": "http://example.com",
  "password": "password123",
  "passwordTime": "2024-01-01T00:00:00",
  "smsCodeTime": "2024-01-01T00:00:00",
  "loginFailCount": 1,
  "loginLockTime": "2024-01-01T00:00:00",
  "isSmsLogin": true,
  "status": 1,
  "isSync": true,
  "sourceType": 1,
  "zzdStatus": "string_value",
  "loginIp": "string_value",
  "loginTime": "2024-01-01T00:00:00",
  "expireTime": "2024-01-01T00:00:00",
  "delFlag": true,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "idCard": "string_value",
  "remark": "string_value",
  "dhUserCode": "CODE001",
  "dhUserName": "string_value",
  "dhUserPassword": "password123",
  "token": "string_value",
  "phoneNotNull": true,
  "keyword": "string_value",
  "deptName": "string_value",
  "roles": [
    {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "roleId": 1,
      "roleName": "示例名称",
      "roleGroup": "string_value",
      "roleKey": "string_value",
      "roleSort": 1,
      "dataScope": "string_value",
      "status": true,
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "remark": "string_value",
      "isApprover": true,
      "flag": true,
      "appKeys": [
        "string_value"
      ],
      "menuIds": [
        1
      ],
      "deptIds": [
        1
      ],
      "permissions": [
        "string_value"
      ],
      "admin": true
    }
  ],
  "apps": [
    {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "appId": 1,
      "appName": "示例名称",
      "type": 1,
      "types": [
        1
      ],
      "appKey": "string_value",
      "appSecret": "string_value",
      "pcUrl": "http://example.com",
      "iconUrl": "string_value",
      "sort": 1,
      "status": 1,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "remark": "string_value"
    }
  ],
  "roleId": 1,
  "roleIds": [
    1
  ],
  "postIds": [
    1
  ],
  "roleNames": "string_value",
  "appPerms": {},
  "permissions": [
    "string_value"
  ],
  "postNames": "string_value",
  "posJob": "string_value",
  "deptNames": "string_value",
  "streetDeptId": 1,
  "streetCode": "string_value",
  "streetName": "string_value",
  "gpsX": 1.0,
  "gpsY": 1.0,
  "passwordRemind": true,
  "admin": true
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 用户修改基本资料

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/user/editBasicInfo` |
| OperationId | `editBasicInfo` |

**请求体：**

- Content-Type: `application/json`
- Schema: `UserInfoRequest`

**请求示例：**
```json
{
  "nickName": "string_value",
  "phoneNum": "13800138000",
  "email": "user@example.com",
  "sex": "string_value",
  "avatar": "string_value",
  "smsCode": "string_value"
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 切换部门

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/user/switchDept` |
| OperationId | `switchDept` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `deptId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### /user/saveSyncUserAndDept

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/user/saveSyncUserAndDept` |
| OperationId | `saveSyncUserAndDept` |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseString`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": "string_value"
  }
  ```

---

#### /user/removeUserPost

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/user/removeUserPost` |
| OperationId | `removeUserPost` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `userIdList` | query | array<integer(int64)> | 是 |  |
| `postId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 用户分页列表

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/user/page` |
| OperationId | `getAdminListByPage` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `userId` | query | string | 否 | 用户ID |
| `deptId` | query | string | 是 | 部门ID |
| `dept.deptId` | query | string | 否 | 部门id |
| `dept.parentId` | query | string | 是 | 父部门id |
| `dept.parentName` | query | string | 否 | 父部门名称 |
| `dept.deptCode` | query | string | 否 | 部门编号 |
| `dept.parentCode` | query | string | 否 |  |
| `dept.levelType` | query | string | 否 | 部门级别：1-县级 2-乡镇级 3-县级部门 4-乡镇部门 |
| `dept.ancestors` | query | string | 否 | 祖级列表 |
| `dept.deptName` | query | string | 是 | 部门名称 |
| `dept.shortName` | query | string | 否 | 简称 |
| `dept.orderNum` | query | string | 否 | 显示顺序 |
| `dept.userSortNum` | query | string | 否 | 某用户在部门内的排序 |
| `dept.leader` | query | string | 否 | 负责人 |
| `dept.contact` | query | string | 否 |  |
| `dept.position` | query | string | 否 |  |
| `dept.phone` | query | string | 否 | 联系电话 |
| `dept.email` | query | string | 否 | 邮箱 |
| `dept.status` | query | string | 否 | 部门状态（1正常 0停用） |
| `dept.isCommandSystem` | query | string | 否 | 是否显示指挥体系 |
| `dept.delFlag` | query | string | 否 | 删除标志（0代表存在1代表删除） |
| `dept.createBy` | query | string | 否 | 创建者 |
| `dept.createTime` | query | string | 否 | 创建时间 |
| `dept.updateBy` | query | string | 否 | 更新者 |
| `dept.updateTime` | query | string | 否 | 更新时间 |
| `dept.typeCode` | query | string | 否 |  |
| `dept.typeName` | query | string | 否 |  |
| `dept.address` | query | string | 否 |  |
| `dept.divisionCode` | query | string | 否 |  |
| `dept.institutionCode` | query | string | 否 |  |
| `dept.unifiedSocialCreditCode` | query | string | 否 |  |
| `dept.institutionLevelCode` | query | string | 否 |  |
| `dept.isSync` | query | boolean | 否 |  |
| `dept.sourceType` | query | integer(int32) | 否 |  |
| `dept.zzdStatus` | query | string | 否 |  |
| `dept.children` | query | array<`SysDeptDO`> | 否 |  |
| `dept.posJob` | query | string | 否 |  |
| `dept.leaderName` | query | string | 否 |  |
| `dept.streetName` | query | string | 否 |  |
| `dept.hasChildren` | query | boolean | 否 |  |
| `dept.beginTime` | query | string | 否 |  |
| `dept.endTime` | query | string | 否 |  |
| `deptList` | query | string | 否 | 多个部门 |
| `authUserIds` | query | string | 否 | 当前授权的所有用户id |
| `authDeptIds` | query | string | 否 | 当前授权的所有部门id |
| `selectDeptId` | query | string | 否 | 当前选择部门id |
| `userDeptList` | query | string | 否 | 多个部门 |
| `account` | query | string | 是 | 用户账号 |
| `userName` | query | string | 是 | 用户名称 |
| `employeeCode` | query | string | 否 | 员工Code |
| `empPoliticalStatusCode` | query | string | 否 | 政治面貌，具体参见‘人员数据字典表’ |
| `empJobLevelCode` | query | string | 否 | 职级，具体参见‘人员数据字典表’ |
| `empBudgetedPostCode` | query | string | 否 | 编制，具体参见‘人员数据字典表’ |
| `nickName` | query | string | 是 | 昵称 |
| `email` | query | string | 否 | 用户邮箱 |
| `phoneNum` | query | string | 否 | 手机号码 |
| `sex` | query | string | 否 | 用户性别（0男 1女 2未知） |
| `avatar` | query | string | 否 | 头像地址 |
| `password` | query | string | 否 | 密码 |
| `passwordTime` | query | string | 否 | 上次设置密码时间 |
| `smsCodeTime` | query | string | 否 | 上次验证码登录时间 |
| `loginFailCount` | query | string | 否 | 登录失败次数计数 |
| `loginLockTime` | query | string | 否 | 登录失败锁定终止时间 |
| `isSmsLogin` | query | string | 否 | 是否需要验证码登录 |
| `status` | query | string | 是 | 帐号状态（1正常 0停用 2 注销） |
| `isSync` | query | boolean | 否 |  |
| `sourceType` | query | integer(int32) | 否 |  |
| `zzdStatus` | query | string | 否 |  |
| `loginIp` | query | string | 否 | 最后登陆IP |
| `loginTime` | query | string | 否 | 最后登陆时间 |
| `expireTime` | query | string(date-time) | 否 |  |
| `delFlag` | query | string | 否 | 删除标志：0-未删除，1-已删除 |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 更新者 |
| `updateTime` | query | string | 否 | 更新时间 |
| `idCard` | query | string | 否 | 身份证号 |
| `remark` | query | string | 否 | 备注 |
| `dhUserCode` | query | string | 否 | 大华用户编码 |
| `dhUserName` | query | string | 否 | 大华用户名 |
| `dhUserPassword` | query | string | 否 | 大华用户登录密码 |
| `token` | query | string | 否 |  |
| `phoneNotNull` | query | boolean | 否 |  |
| `keyword` | query | string | 否 |  |
| `deptName` | query | string | 否 |  |
| `roles` | query | array<`SysRoleDO`> | 否 |  |
| `apps` | query | array<`SysAppDO`> | 否 |  |
| `roleId` | query | integer(int64) | 否 |  |
| `roleIds` | query | array<integer(int64)> | 否 |  |
| `postIds` | query | array<integer(int64)> | 否 |  |
| `roleNames` | query | string | 否 |  |
| `permissions` | query | array<string> | 否 |  |
| `postNames` | query | string | 否 |  |
| `posJob` | query | string | 否 |  |
| `deptNames` | query | string | 否 |  |
| `streetDeptId` | query | integer(int64) | 否 |  |
| `streetCode` | query | string | 否 |  |
| `streetName` | query | string | 否 |  |
| `gpsX` | query | number(double) | 否 |  |
| `gpsY` | query | number(double) | 否 |  |
| `passwordRemind` | query | boolean | 否 |  |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseIPageSysUserDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "size": 1,
      "current": 1,
      "records": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "userId": "...",
          "deptId": "...",
          "dept": "...",
          "deptList": "...",
          "authUserIds": "...",
          "authDeptIds": "...",
          "selectDeptId": "...",
          "userDeptList": "...",
          "account": "...",
          "userName": "...",
          "employeeCode": "...",
          "empPoliticalStatusCode": "...",
          "empJobLevelCode": "...",
          "empBudgetedPostCode": "...",
          "nickName": "...",
          "email": "...",
          "phoneNum": "...",
          "sex": "...",
          "avatar": "...",
          "password": "...",
          "passwordTime": "...",
          "smsCodeTime": "...",
          "loginFailCount": "...",
          "loginLockTime": "...",
          "isSmsLogin": "...",
          "status": "...",
          "isSync": "...",
          "sourceType": "...",
          "zzdStatus": "...",
          "loginIp": "...",
          "loginTime": "...",
          "expireTime": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "idCard": "...",
          "remark": "...",
          "dhUserCode": "...",
          "dhUserName": "...",
          "dhUserPassword": "...",
          "token": "...",
          "phoneNotNull": "...",
          "keyword": "...",
          "deptName": "...",
          "roles": "...",
          "apps": "...",
          "roleId": "...",
          "roleIds": "...",
          "postIds": "...",
          "roleNames": "...",
          "appPerms": "...",
          "permissions": "...",
          "postNames": "...",
          "posJob": "...",
          "deptNames": "...",
          "streetDeptId": "...",
          "streetCode": "...",
          "streetName": "...",
          "gpsX": "...",
          "gpsY": "...",
          "passwordRemind": "...",
          "admin": "..."
        }
      ],
      "total": 1,
      "pages": 1
    }
  }
  ```

---

#### 浙政钉登录

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/user/loginByZzd` |
| OperationId | `loginByZzd` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `code` | query | string | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseAccessTokenVO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "accessToken": "string_value",
      "expiresIn": 1,
      "iotToken": "string_value"
    }
  }
  ```

---

#### 浙政钉登录

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/user/loginApprovalByZzd` |
| OperationId | `loginApprovalByZzd` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `code` | query | string | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseAccessTokenVO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "accessToken": "string_value",
      "expiresIn": 1,
      "iotToken": "string_value"
    }
  }
  ```

---

#### /user/insertUserPost

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/user/insertUserPost` |
| OperationId | `insertUserPost` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `userIdList` | query | array<integer(int64)> | 是 |  |
| `postId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 获取当前用户信息

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/user/info` |
| OperationId | `info` |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseSysUserDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "userId": 1,
      "deptId": 1,
      "dept": {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "deptId": 1,
        "parentId": 1,
        "parentName": "示例名称",
        "deptCode": "string_value",
        "parentCode": "string_value",
        "levelType": 1,
        "ancestors": "string_value",
        "deptName": "示例名称",
        "shortName": "string_value",
        "orderNum": 1,
        "userSortNum": 1,
        "leader": "string_value",
        "contact": "string_value",
        "position": "string_value",
        "phone": "13800138000",
        "email": "user@example.com",
        "status": true,
        "isCommandSystem": true,
        "delFlag": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "typeCode": "string_value",
        "typeName": "string_value",
        "address": "string_value",
        "divisionCode": "string_value",
        "institutionCode": "string_value",
        "unifiedSocialCreditCode": "string_value",
        "institutionLevelCode": "string_value",
        "isSync": true,
        "sourceType": 1,
        "zzdStatus": "string_value",
        "children": [
          "..."
        ],
        "parent": "<SysDeptDO>",
        "posJob": "string_value",
        "leaderName": "string_value",
        "streetName": "string_value",
        "hasChildren": true
      },
      "deptList": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "deptId": "...",
          "parentId": "...",
          "parentName": "...",
          "deptCode": "...",
          "parentCode": "...",
          "levelType": "...",
          "ancestors": "...",
          "deptName": "...",
          "shortName": "...",
          "orderNum": "...",
          "userSortNum": "...",
          "leader": "...",
          "contact": "...",
          "position": "...",
          "phone": "...",
          "email": "...",
          "status": "...",
          "isCommandSystem": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "typeCode": "...",
          "typeName": "...",
          "address": "...",
          "divisionCode": "...",
          "institutionCode": "...",
          "unifiedSocialCreditCode": "...",
          "institutionLevelCode": "...",
          "isSync": "...",
          "sourceType": "...",
          "zzdStatus": "...",
          "children": "...",
          "parent": "...",
          "posJob": "...",
          "leaderName": "...",
          "streetName": "...",
          "hasChildren": "..."
        }
      ],
      "authUserIds": [
        1
      ],
      "authDeptIds": [
        1
      ],
      "selectDeptId": 1,
      "userDeptList": [
        {
          "userId": "...",
          "deptId": "...",
          "orderInOrganization": "...",
          "posJobRankCode": "...",
          "mainJob": "...",
          "status": "...",
          "govEmpPosJob": "...",
          "govEmpPosPhoneNo": "...",
          "sourceType": "...",
          "deptCode": "...",
          "deptName": "...",
          "parentName": "..."
        }
      ],
      "account": "string_value",
      "userName": "示例名称",
      "employeeCode": "CODE001",
      "empPoliticalStatusCode": "string_value",
      "empJobLevelCode": "string_value",
      "empBudgetedPostCode": "string_value",
      "nickName": "string_value",
      "email": "user@example.com",
      "phoneNum": "13800138000",
      "sex": "string_value",
      "avatar": "http://example.com",
      "password": "password123",
      "passwordTime": "2024-01-01T00:00:00",
      "smsCodeTime": "2024-01-01T00:00:00",
      "loginFailCount": 1,
      "loginLockTime": "2024-01-01T00:00:00",
      "isSmsLogin": true,
      "status": 1,
      "isSync": true,
      "sourceType": 1,
      "zzdStatus": "string_value",
      "loginIp": "string_value",
      "loginTime": "2024-01-01T00:00:00",
      "expireTime": "2024-01-01T00:00:00",
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "idCard": "string_value",
      "remark": "string_value",
      "dhUserCode": "CODE001",
      "dhUserName": "string_value",
      "dhUserPassword": "password123",
      "token": "string_value",
      "phoneNotNull": true,
      "keyword": "string_value",
      "deptName": "string_value",
      "roles": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "roleId": "...",
          "roleName": "...",
          "roleGroup": "...",
          "roleKey": "...",
          "roleSort": "...",
          "dataScope": "...",
          "status": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "remark": "...",
          "isApprover": "...",
          "flag": "...",
          "appKeys": "...",
          "menuIds": "...",
          "deptIds": "...",
          "permissions": "...",
          "admin": "..."
        }
      ],
      "apps": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "appId": "...",
          "appName": "...",
          "type": "...",
          "types": "...",
          "appKey": "...",
          "appSecret": "...",
          "pcUrl": "...",
          "iconUrl": "...",
          "sort": "...",
          "status": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "remark": "..."
        }
      ],
      "roleId": 1,
      "roleIds": [
        1
      ],
      "postIds": [
        1
      ],
      "roleNames": "string_value",
      "appPerms": {},
      "permissions": [
        "string_value"
      ],
      "postNames": "string_value",
      "posJob": "string_value",
      "deptNames": "string_value",
      "streetDeptId": 1,
      "streetCode": "string_value",
      "streetName": "string_value",
      "gpsX": 1.0,
      "gpsY": 1.0,
      "passwordRemind": true,
      "admin": true
    }
  }
  ```

---

#### 根据角色ID查询用户列表-给算法中心事件推送角色时使用

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/user/getUsersByUserOrRole` |
| OperationId | `getUsersByUserOrRole` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `type` | query | integer(int32) | 是 |  |
| `ids` | query | string | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysUserDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "userId": 1,
        "deptId": 1,
        "dept": {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "deptId": "...",
          "parentId": "...",
          "parentName": "...",
          "deptCode": "...",
          "parentCode": "...",
          "levelType": "...",
          "ancestors": "...",
          "deptName": "...",
          "shortName": "...",
          "orderNum": "...",
          "userSortNum": "...",
          "leader": "...",
          "contact": "...",
          "position": "...",
          "phone": "...",
          "email": "...",
          "status": "...",
          "isCommandSystem": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "typeCode": "...",
          "typeName": "...",
          "address": "...",
          "divisionCode": "...",
          "institutionCode": "...",
          "unifiedSocialCreditCode": "...",
          "institutionLevelCode": "...",
          "isSync": "...",
          "sourceType": "...",
          "zzdStatus": "...",
          "children": "...",
          "parent": "...",
          "posJob": "...",
          "leaderName": "...",
          "streetName": "...",
          "hasChildren": "..."
        },
        "deptList": [
          "..."
        ],
        "authUserIds": [
          1
        ],
        "authDeptIds": [
          1
        ],
        "selectDeptId": 1,
        "userDeptList": [
          "..."
        ],
        "account": "string_value",
        "userName": "示例名称",
        "employeeCode": "CODE001",
        "empPoliticalStatusCode": "string_value",
        "empJobLevelCode": "string_value",
        "empBudgetedPostCode": "string_value",
        "nickName": "string_value",
        "email": "user@example.com",
        "phoneNum": "13800138000",
        "sex": "string_value",
        "avatar": "http://example.com",
        "password": "password123",
        "passwordTime": "2024-01-01T00:00:00",
        "smsCodeTime": "2024-01-01T00:00:00",
        "loginFailCount": 1,
        "loginLockTime": "2024-01-01T00:00:00",
        "isSmsLogin": true,
        "status": 1,
        "isSync": true,
        "sourceType": 1,
        "zzdStatus": "string_value",
        "loginIp": "string_value",
        "loginTime": "2024-01-01T00:00:00",
        "expireTime": "2024-01-01T00:00:00",
        "delFlag": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "idCard": "string_value",
        "remark": "string_value",
        "dhUserCode": "CODE001",
        "dhUserName": "string_value",
        "dhUserPassword": "password123",
        "token": "string_value",
        "phoneNotNull": true,
        "keyword": "string_value",
        "deptName": "string_value",
        "roles": [
          "..."
        ],
        "apps": [
          "..."
        ],
        "roleId": 1,
        "roleIds": [
          1
        ],
        "postIds": [
          1
        ],
        "roleNames": "string_value",
        "appPerms": {},
        "permissions": [
          "string_value"
        ],
        "postNames": "string_value",
        "posJob": "string_value",
        "deptNames": "string_value",
        "streetDeptId": 1,
        "streetCode": "string_value",
        "streetName": "string_value",
        "gpsX": 1.0,
        "gpsY": 1.0,
        "passwordRemind": true,
        "admin": true
      }
    ]
  }
  ```

---

#### 模糊查询用户信息

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/user/getUserByName` |
| OperationId | `getUserByName` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `userName` | query | string | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysUserDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "userId": 1,
        "deptId": 1,
        "dept": {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "deptId": "...",
          "parentId": "...",
          "parentName": "...",
          "deptCode": "...",
          "parentCode": "...",
          "levelType": "...",
          "ancestors": "...",
          "deptName": "...",
          "shortName": "...",
          "orderNum": "...",
          "userSortNum": "...",
          "leader": "...",
          "contact": "...",
          "position": "...",
          "phone": "...",
          "email": "...",
          "status": "...",
          "isCommandSystem": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "typeCode": "...",
          "typeName": "...",
          "address": "...",
          "divisionCode": "...",
          "institutionCode": "...",
          "unifiedSocialCreditCode": "...",
          "institutionLevelCode": "...",
          "isSync": "...",
          "sourceType": "...",
          "zzdStatus": "...",
          "children": "...",
          "parent": "...",
          "posJob": "...",
          "leaderName": "...",
          "streetName": "...",
          "hasChildren": "..."
        },
        "deptList": [
          "..."
        ],
        "authUserIds": [
          1
        ],
        "authDeptIds": [
          1
        ],
        "selectDeptId": 1,
        "userDeptList": [
          "..."
        ],
        "account": "string_value",
        "userName": "示例名称",
        "employeeCode": "CODE001",
        "empPoliticalStatusCode": "string_value",
        "empJobLevelCode": "string_value",
        "empBudgetedPostCode": "string_value",
        "nickName": "string_value",
        "email": "user@example.com",
        "phoneNum": "13800138000",
        "sex": "string_value",
        "avatar": "http://example.com",
        "password": "password123",
        "passwordTime": "2024-01-01T00:00:00",
        "smsCodeTime": "2024-01-01T00:00:00",
        "loginFailCount": 1,
        "loginLockTime": "2024-01-01T00:00:00",
        "isSmsLogin": true,
        "status": 1,
        "isSync": true,
        "sourceType": 1,
        "zzdStatus": "string_value",
        "loginIp": "string_value",
        "loginTime": "2024-01-01T00:00:00",
        "expireTime": "2024-01-01T00:00:00",
        "delFlag": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "idCard": "string_value",
        "remark": "string_value",
        "dhUserCode": "CODE001",
        "dhUserName": "string_value",
        "dhUserPassword": "password123",
        "token": "string_value",
        "phoneNotNull": true,
        "keyword": "string_value",
        "deptName": "string_value",
        "roles": [
          "..."
        ],
        "apps": [
          "..."
        ],
        "roleId": 1,
        "roleIds": [
          1
        ],
        "postIds": [
          1
        ],
        "roleNames": "string_value",
        "appPerms": {},
        "permissions": [
          "string_value"
        ],
        "postNames": "string_value",
        "posJob": "string_value",
        "deptNames": "string_value",
        "streetDeptId": 1,
        "streetCode": "string_value",
        "streetName": "string_value",
        "gpsX": 1.0,
        "gpsY": 1.0,
        "passwordRemind": true,
        "admin": true
      }
    ]
  }
  ```

---

#### /user/getUserByIds

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/user/getUserByIds` |
| OperationId | `getUserByIds` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `userIds` | query | array<integer(int64)> | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysUserDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "userId": 1,
        "deptId": 1,
        "dept": {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "deptId": "...",
          "parentId": "...",
          "parentName": "...",
          "deptCode": "...",
          "parentCode": "...",
          "levelType": "...",
          "ancestors": "...",
          "deptName": "...",
          "shortName": "...",
          "orderNum": "...",
          "userSortNum": "...",
          "leader": "...",
          "contact": "...",
          "position": "...",
          "phone": "...",
          "email": "...",
          "status": "...",
          "isCommandSystem": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "typeCode": "...",
          "typeName": "...",
          "address": "...",
          "divisionCode": "...",
          "institutionCode": "...",
          "unifiedSocialCreditCode": "...",
          "institutionLevelCode": "...",
          "isSync": "...",
          "sourceType": "...",
          "zzdStatus": "...",
          "children": "...",
          "parent": "...",
          "posJob": "...",
          "leaderName": "...",
          "streetName": "...",
          "hasChildren": "..."
        },
        "deptList": [
          "..."
        ],
        "authUserIds": [
          1
        ],
        "authDeptIds": [
          1
        ],
        "selectDeptId": 1,
        "userDeptList": [
          "..."
        ],
        "account": "string_value",
        "userName": "示例名称",
        "employeeCode": "CODE001",
        "empPoliticalStatusCode": "string_value",
        "empJobLevelCode": "string_value",
        "empBudgetedPostCode": "string_value",
        "nickName": "string_value",
        "email": "user@example.com",
        "phoneNum": "13800138000",
        "sex": "string_value",
        "avatar": "http://example.com",
        "password": "password123",
        "passwordTime": "2024-01-01T00:00:00",
        "smsCodeTime": "2024-01-01T00:00:00",
        "loginFailCount": 1,
        "loginLockTime": "2024-01-01T00:00:00",
        "isSmsLogin": true,
        "status": 1,
        "isSync": true,
        "sourceType": 1,
        "zzdStatus": "string_value",
        "loginIp": "string_value",
        "loginTime": "2024-01-01T00:00:00",
        "expireTime": "2024-01-01T00:00:00",
        "delFlag": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "idCard": "string_value",
        "remark": "string_value",
        "dhUserCode": "CODE001",
        "dhUserName": "string_value",
        "dhUserPassword": "password123",
        "token": "string_value",
        "phoneNotNull": true,
        "keyword": "string_value",
        "deptName": "string_value",
        "roles": [
          "..."
        ],
        "apps": [
          "..."
        ],
        "roleId": 1,
        "roleIds": [
          1
        ],
        "postIds": [
          1
        ],
        "roleNames": "string_value",
        "appPerms": {},
        "permissions": [
          "string_value"
        ],
        "postNames": "string_value",
        "posJob": "string_value",
        "deptNames": "string_value",
        "streetDeptId": 1,
        "streetCode": "string_value",
        "streetName": "string_value",
        "gpsX": 1.0,
        "gpsY": 1.0,
        "passwordRemind": true,
        "admin": true
      }
    ]
  }
  ```

---

#### /user/getUserById

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/user/getUserById` |
| OperationId | `getUserById` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `userId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseSysUserDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "userId": 1,
      "deptId": 1,
      "dept": {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "deptId": 1,
        "parentId": 1,
        "parentName": "示例名称",
        "deptCode": "string_value",
        "parentCode": "string_value",
        "levelType": 1,
        "ancestors": "string_value",
        "deptName": "示例名称",
        "shortName": "string_value",
        "orderNum": 1,
        "userSortNum": 1,
        "leader": "string_value",
        "contact": "string_value",
        "position": "string_value",
        "phone": "13800138000",
        "email": "user@example.com",
        "status": true,
        "isCommandSystem": true,
        "delFlag": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "typeCode": "string_value",
        "typeName": "string_value",
        "address": "string_value",
        "divisionCode": "string_value",
        "institutionCode": "string_value",
        "unifiedSocialCreditCode": "string_value",
        "institutionLevelCode": "string_value",
        "isSync": true,
        "sourceType": 1,
        "zzdStatus": "string_value",
        "children": [
          "..."
        ],
        "parent": "<SysDeptDO>",
        "posJob": "string_value",
        "leaderName": "string_value",
        "streetName": "string_value",
        "hasChildren": true
      },
      "deptList": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "deptId": "...",
          "parentId": "...",
          "parentName": "...",
          "deptCode": "...",
          "parentCode": "...",
          "levelType": "...",
          "ancestors": "...",
          "deptName": "...",
          "shortName": "...",
          "orderNum": "...",
          "userSortNum": "...",
          "leader": "...",
          "contact": "...",
          "position": "...",
          "phone": "...",
          "email": "...",
          "status": "...",
          "isCommandSystem": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "typeCode": "...",
          "typeName": "...",
          "address": "...",
          "divisionCode": "...",
          "institutionCode": "...",
          "unifiedSocialCreditCode": "...",
          "institutionLevelCode": "...",
          "isSync": "...",
          "sourceType": "...",
          "zzdStatus": "...",
          "children": "...",
          "parent": "...",
          "posJob": "...",
          "leaderName": "...",
          "streetName": "...",
          "hasChildren": "..."
        }
      ],
      "authUserIds": [
        1
      ],
      "authDeptIds": [
        1
      ],
      "selectDeptId": 1,
      "userDeptList": [
        {
          "userId": "...",
          "deptId": "...",
          "orderInOrganization": "...",
          "posJobRankCode": "...",
          "mainJob": "...",
          "status": "...",
          "govEmpPosJob": "...",
          "govEmpPosPhoneNo": "...",
          "sourceType": "...",
          "deptCode": "...",
          "deptName": "...",
          "parentName": "..."
        }
      ],
      "account": "string_value",
      "userName": "示例名称",
      "employeeCode": "CODE001",
      "empPoliticalStatusCode": "string_value",
      "empJobLevelCode": "string_value",
      "empBudgetedPostCode": "string_value",
      "nickName": "string_value",
      "email": "user@example.com",
      "phoneNum": "13800138000",
      "sex": "string_value",
      "avatar": "http://example.com",
      "password": "password123",
      "passwordTime": "2024-01-01T00:00:00",
      "smsCodeTime": "2024-01-01T00:00:00",
      "loginFailCount": 1,
      "loginLockTime": "2024-01-01T00:00:00",
      "isSmsLogin": true,
      "status": 1,
      "isSync": true,
      "sourceType": 1,
      "zzdStatus": "string_value",
      "loginIp": "string_value",
      "loginTime": "2024-01-01T00:00:00",
      "expireTime": "2024-01-01T00:00:00",
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "idCard": "string_value",
      "remark": "string_value",
      "dhUserCode": "CODE001",
      "dhUserName": "string_value",
      "dhUserPassword": "password123",
      "token": "string_value",
      "phoneNotNull": true,
      "keyword": "string_value",
      "deptName": "string_value",
      "roles": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "roleId": "...",
          "roleName": "...",
          "roleGroup": "...",
          "roleKey": "...",
          "roleSort": "...",
          "dataScope": "...",
          "status": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "remark": "...",
          "isApprover": "...",
          "flag": "...",
          "appKeys": "...",
          "menuIds": "...",
          "deptIds": "...",
          "permissions": "...",
          "admin": "..."
        }
      ],
      "apps": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "appId": "...",
          "appName": "...",
          "type": "...",
          "types": "...",
          "appKey": "...",
          "appSecret": "...",
          "pcUrl": "...",
          "iconUrl": "...",
          "sort": "...",
          "status": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "remark": "..."
        }
      ],
      "roleId": 1,
      "roleIds": [
        1
      ],
      "postIds": [
        1
      ],
      "roleNames": "string_value",
      "appPerms": {},
      "permissions": [
        "string_value"
      ],
      "postNames": "string_value",
      "posJob": "string_value",
      "deptNames": "string_value",
      "streetDeptId": 1,
      "streetCode": "string_value",
      "streetName": "string_value",
      "gpsX": 1.0,
      "gpsY": 1.0,
      "passwordRemind": true,
      "admin": true
    }
  }
  ```

---

#### 查询当前部门下的人员信息

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/user/getUserByDept` |
| OperationId | `getUserByDept` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `deptId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysUserDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "userId": 1,
        "deptId": 1,
        "dept": {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "deptId": "...",
          "parentId": "...",
          "parentName": "...",
          "deptCode": "...",
          "parentCode": "...",
          "levelType": "...",
          "ancestors": "...",
          "deptName": "...",
          "shortName": "...",
          "orderNum": "...",
          "userSortNum": "...",
          "leader": "...",
          "contact": "...",
          "position": "...",
          "phone": "...",
          "email": "...",
          "status": "...",
          "isCommandSystem": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "typeCode": "...",
          "typeName": "...",
          "address": "...",
          "divisionCode": "...",
          "institutionCode": "...",
          "unifiedSocialCreditCode": "...",
          "institutionLevelCode": "...",
          "isSync": "...",
          "sourceType": "...",
          "zzdStatus": "...",
          "children": "...",
          "parent": "...",
          "posJob": "...",
          "leaderName": "...",
          "streetName": "...",
          "hasChildren": "..."
        },
        "deptList": [
          "..."
        ],
        "authUserIds": [
          1
        ],
        "authDeptIds": [
          1
        ],
        "selectDeptId": 1,
        "userDeptList": [
          "..."
        ],
        "account": "string_value",
        "userName": "示例名称",
        "employeeCode": "CODE001",
        "empPoliticalStatusCode": "string_value",
        "empJobLevelCode": "string_value",
        "empBudgetedPostCode": "string_value",
        "nickName": "string_value",
        "email": "user@example.com",
        "phoneNum": "13800138000",
        "sex": "string_value",
        "avatar": "http://example.com",
        "password": "password123",
        "passwordTime": "2024-01-01T00:00:00",
        "smsCodeTime": "2024-01-01T00:00:00",
        "loginFailCount": 1,
        "loginLockTime": "2024-01-01T00:00:00",
        "isSmsLogin": true,
        "status": 1,
        "isSync": true,
        "sourceType": 1,
        "zzdStatus": "string_value",
        "loginIp": "string_value",
        "loginTime": "2024-01-01T00:00:00",
        "expireTime": "2024-01-01T00:00:00",
        "delFlag": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "idCard": "string_value",
        "remark": "string_value",
        "dhUserCode": "CODE001",
        "dhUserName": "string_value",
        "dhUserPassword": "password123",
        "token": "string_value",
        "phoneNotNull": true,
        "keyword": "string_value",
        "deptName": "string_value",
        "roles": [
          "..."
        ],
        "apps": [
          "..."
        ],
        "roleId": 1,
        "roleIds": [
          1
        ],
        "postIds": [
          1
        ],
        "roleNames": "string_value",
        "appPerms": {},
        "permissions": [
          "string_value"
        ],
        "postNames": "string_value",
        "posJob": "string_value",
        "deptNames": "string_value",
        "streetDeptId": 1,
        "streetCode": "string_value",
        "streetName": "string_value",
        "gpsX": 1.0,
        "gpsY": 1.0,
        "passwordRemind": true,
        "admin": true
      }
    ]
  }
  ```

---

#### /user/getUserAndDeptByUserIds

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/user/getUserAndDeptByUserIds` |
| OperationId | `getUserAndDeptByUserIds` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `userIds` | query | array<integer(int64)> | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysUserDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "userId": 1,
        "deptId": 1,
        "dept": {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "deptId": "...",
          "parentId": "...",
          "parentName": "...",
          "deptCode": "...",
          "parentCode": "...",
          "levelType": "...",
          "ancestors": "...",
          "deptName": "...",
          "shortName": "...",
          "orderNum": "...",
          "userSortNum": "...",
          "leader": "...",
          "contact": "...",
          "position": "...",
          "phone": "...",
          "email": "...",
          "status": "...",
          "isCommandSystem": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "typeCode": "...",
          "typeName": "...",
          "address": "...",
          "divisionCode": "...",
          "institutionCode": "...",
          "unifiedSocialCreditCode": "...",
          "institutionLevelCode": "...",
          "isSync": "...",
          "sourceType": "...",
          "zzdStatus": "...",
          "children": "...",
          "parent": "...",
          "posJob": "...",
          "leaderName": "...",
          "streetName": "...",
          "hasChildren": "..."
        },
        "deptList": [
          "..."
        ],
        "authUserIds": [
          1
        ],
        "authDeptIds": [
          1
        ],
        "selectDeptId": 1,
        "userDeptList": [
          "..."
        ],
        "account": "string_value",
        "userName": "示例名称",
        "employeeCode": "CODE001",
        "empPoliticalStatusCode": "string_value",
        "empJobLevelCode": "string_value",
        "empBudgetedPostCode": "string_value",
        "nickName": "string_value",
        "email": "user@example.com",
        "phoneNum": "13800138000",
        "sex": "string_value",
        "avatar": "http://example.com",
        "password": "password123",
        "passwordTime": "2024-01-01T00:00:00",
        "smsCodeTime": "2024-01-01T00:00:00",
        "loginFailCount": 1,
        "loginLockTime": "2024-01-01T00:00:00",
        "isSmsLogin": true,
        "status": 1,
        "isSync": true,
        "sourceType": 1,
        "zzdStatus": "string_value",
        "loginIp": "string_value",
        "loginTime": "2024-01-01T00:00:00",
        "expireTime": "2024-01-01T00:00:00",
        "delFlag": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "idCard": "string_value",
        "remark": "string_value",
        "dhUserCode": "CODE001",
        "dhUserName": "string_value",
        "dhUserPassword": "password123",
        "token": "string_value",
        "phoneNotNull": true,
        "keyword": "string_value",
        "deptName": "string_value",
        "roles": [
          "..."
        ],
        "apps": [
          "..."
        ],
        "roleId": 1,
        "roleIds": [
          1
        ],
        "postIds": [
          1
        ],
        "roleNames": "string_value",
        "appPerms": {},
        "permissions": [
          "string_value"
        ],
        "postNames": "string_value",
        "posJob": "string_value",
        "deptNames": "string_value",
        "streetDeptId": 1,
        "streetCode": "string_value",
        "streetName": "string_value",
        "gpsX": 1.0,
        "gpsY": 1.0,
        "passwordRemind": true,
        "admin": true
      }
    ]
  }
  ```

---

#### 根据账号查询是否需要验证码登录

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/user/getSmsInfoByAccount` |
| OperationId | `getSmsInfoByAccount` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `account` | query | string | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseSysUserDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "userId": 1,
      "deptId": 1,
      "dept": {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "deptId": 1,
        "parentId": 1,
        "parentName": "示例名称",
        "deptCode": "string_value",
        "parentCode": "string_value",
        "levelType": 1,
        "ancestors": "string_value",
        "deptName": "示例名称",
        "shortName": "string_value",
        "orderNum": 1,
        "userSortNum": 1,
        "leader": "string_value",
        "contact": "string_value",
        "position": "string_value",
        "phone": "13800138000",
        "email": "user@example.com",
        "status": true,
        "isCommandSystem": true,
        "delFlag": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "typeCode": "string_value",
        "typeName": "string_value",
        "address": "string_value",
        "divisionCode": "string_value",
        "institutionCode": "string_value",
        "unifiedSocialCreditCode": "string_value",
        "institutionLevelCode": "string_value",
        "isSync": true,
        "sourceType": 1,
        "zzdStatus": "string_value",
        "children": [
          "..."
        ],
        "parent": "<SysDeptDO>",
        "posJob": "string_value",
        "leaderName": "string_value",
        "streetName": "string_value",
        "hasChildren": true
      },
      "deptList": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "deptId": "...",
          "parentId": "...",
          "parentName": "...",
          "deptCode": "...",
          "parentCode": "...",
          "levelType": "...",
          "ancestors": "...",
          "deptName": "...",
          "shortName": "...",
          "orderNum": "...",
          "userSortNum": "...",
          "leader": "...",
          "contact": "...",
          "position": "...",
          "phone": "...",
          "email": "...",
          "status": "...",
          "isCommandSystem": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "typeCode": "...",
          "typeName": "...",
          "address": "...",
          "divisionCode": "...",
          "institutionCode": "...",
          "unifiedSocialCreditCode": "...",
          "institutionLevelCode": "...",
          "isSync": "...",
          "sourceType": "...",
          "zzdStatus": "...",
          "children": "...",
          "parent": "...",
          "posJob": "...",
          "leaderName": "...",
          "streetName": "...",
          "hasChildren": "..."
        }
      ],
      "authUserIds": [
        1
      ],
      "authDeptIds": [
        1
      ],
      "selectDeptId": 1,
      "userDeptList": [
        {
          "userId": "...",
          "deptId": "...",
          "orderInOrganization": "...",
          "posJobRankCode": "...",
          "mainJob": "...",
          "status": "...",
          "govEmpPosJob": "...",
          "govEmpPosPhoneNo": "...",
          "sourceType": "...",
          "deptCode": "...",
          "deptName": "...",
          "parentName": "..."
        }
      ],
      "account": "string_value",
      "userName": "示例名称",
      "employeeCode": "CODE001",
      "empPoliticalStatusCode": "string_value",
      "empJobLevelCode": "string_value",
      "empBudgetedPostCode": "string_value",
      "nickName": "string_value",
      "email": "user@example.com",
      "phoneNum": "13800138000",
      "sex": "string_value",
      "avatar": "http://example.com",
      "password": "password123",
      "passwordTime": "2024-01-01T00:00:00",
      "smsCodeTime": "2024-01-01T00:00:00",
      "loginFailCount": 1,
      "loginLockTime": "2024-01-01T00:00:00",
      "isSmsLogin": true,
      "status": 1,
      "isSync": true,
      "sourceType": 1,
      "zzdStatus": "string_value",
      "loginIp": "string_value",
      "loginTime": "2024-01-01T00:00:00",
      "expireTime": "2024-01-01T00:00:00",
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "idCard": "string_value",
      "remark": "string_value",
      "dhUserCode": "CODE001",
      "dhUserName": "string_value",
      "dhUserPassword": "password123",
      "token": "string_value",
      "phoneNotNull": true,
      "keyword": "string_value",
      "deptName": "string_value",
      "roles": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "roleId": "...",
          "roleName": "...",
          "roleGroup": "...",
          "roleKey": "...",
          "roleSort": "...",
          "dataScope": "...",
          "status": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "remark": "...",
          "isApprover": "...",
          "flag": "...",
          "appKeys": "...",
          "menuIds": "...",
          "deptIds": "...",
          "permissions": "...",
          "admin": "..."
        }
      ],
      "apps": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "appId": "...",
          "appName": "...",
          "type": "...",
          "types": "...",
          "appKey": "...",
          "appSecret": "...",
          "pcUrl": "...",
          "iconUrl": "...",
          "sort": "...",
          "status": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "remark": "..."
        }
      ],
      "roleId": 1,
      "roleIds": [
        1
      ],
      "postIds": [
        1
      ],
      "roleNames": "string_value",
      "appPerms": {},
      "permissions": [
        "string_value"
      ],
      "postNames": "string_value",
      "posJob": "string_value",
      "deptNames": "string_value",
      "streetDeptId": 1,
      "streetCode": "string_value",
      "streetName": "string_value",
      "gpsX": 1.0,
      "gpsY": 1.0,
      "passwordRemind": true,
      "admin": true
    }
  }
  ```

---

#### 新增编辑时回显-根据用户ID获取详情

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/user/getInfo` |
| OperationId | `getInfo` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `userId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseMapStringObject`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {}
  }
  ```

---

#### /user/getDeptByUserId

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/user/getDeptByUserId` |
| OperationId | `getDeptByUserId` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `userId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseSysDeptDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "deptId": 1,
      "parentId": 1,
      "parentName": "示例名称",
      "deptCode": "string_value",
      "parentCode": "string_value",
      "levelType": 1,
      "ancestors": "string_value",
      "deptName": "示例名称",
      "shortName": "string_value",
      "orderNum": 1,
      "userSortNum": 1,
      "leader": "string_value",
      "contact": "string_value",
      "position": "string_value",
      "phone": "13800138000",
      "email": "user@example.com",
      "status": true,
      "isCommandSystem": true,
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "typeCode": "string_value",
      "typeName": "string_value",
      "address": "string_value",
      "divisionCode": "string_value",
      "institutionCode": "string_value",
      "unifiedSocialCreditCode": "string_value",
      "institutionLevelCode": "string_value",
      "isSync": true,
      "sourceType": 1,
      "zzdStatus": "string_value",
      "children": [
        "<SysDeptDO>"
      ],
      "parent": "<SysDeptDO>",
      "posJob": "string_value",
      "leaderName": "string_value",
      "streetName": "string_value",
      "hasChildren": true
    }
  }
  ```

---

#### /user/delRedisKey

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/user/delRedisKey` |
| OperationId | `delRedisKey` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `key` | query | string | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### /user/cancellation

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/user/cancellation` |
| OperationId | `cancellation` |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 获取用户信息（给第三方调用，去掉不需要的字段）

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/user/auth` |
| OperationId | `auth` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `appKey` | query | string | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseSysUserDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "userId": 1,
      "deptId": 1,
      "dept": {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "deptId": 1,
        "parentId": 1,
        "parentName": "示例名称",
        "deptCode": "string_value",
        "parentCode": "string_value",
        "levelType": 1,
        "ancestors": "string_value",
        "deptName": "示例名称",
        "shortName": "string_value",
        "orderNum": 1,
        "userSortNum": 1,
        "leader": "string_value",
        "contact": "string_value",
        "position": "string_value",
        "phone": "13800138000",
        "email": "user@example.com",
        "status": true,
        "isCommandSystem": true,
        "delFlag": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "typeCode": "string_value",
        "typeName": "string_value",
        "address": "string_value",
        "divisionCode": "string_value",
        "institutionCode": "string_value",
        "unifiedSocialCreditCode": "string_value",
        "institutionLevelCode": "string_value",
        "isSync": true,
        "sourceType": 1,
        "zzdStatus": "string_value",
        "children": [
          "..."
        ],
        "parent": "<SysDeptDO>",
        "posJob": "string_value",
        "leaderName": "string_value",
        "streetName": "string_value",
        "hasChildren": true
      },
      "deptList": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "deptId": "...",
          "parentId": "...",
          "parentName": "...",
          "deptCode": "...",
          "parentCode": "...",
          "levelType": "...",
          "ancestors": "...",
          "deptName": "...",
          "shortName": "...",
          "orderNum": "...",
          "userSortNum": "...",
          "leader": "...",
          "contact": "...",
          "position": "...",
          "phone": "...",
          "email": "...",
          "status": "...",
          "isCommandSystem": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "typeCode": "...",
          "typeName": "...",
          "address": "...",
          "divisionCode": "...",
          "institutionCode": "...",
          "unifiedSocialCreditCode": "...",
          "institutionLevelCode": "...",
          "isSync": "...",
          "sourceType": "...",
          "zzdStatus": "...",
          "children": "...",
          "parent": "...",
          "posJob": "...",
          "leaderName": "...",
          "streetName": "...",
          "hasChildren": "..."
        }
      ],
      "authUserIds": [
        1
      ],
      "authDeptIds": [
        1
      ],
      "selectDeptId": 1,
      "userDeptList": [
        {
          "userId": "...",
          "deptId": "...",
          "orderInOrganization": "...",
          "posJobRankCode": "...",
          "mainJob": "...",
          "status": "...",
          "govEmpPosJob": "...",
          "govEmpPosPhoneNo": "...",
          "sourceType": "...",
          "deptCode": "...",
          "deptName": "...",
          "parentName": "..."
        }
      ],
      "account": "string_value",
      "userName": "示例名称",
      "employeeCode": "CODE001",
      "empPoliticalStatusCode": "string_value",
      "empJobLevelCode": "string_value",
      "empBudgetedPostCode": "string_value",
      "nickName": "string_value",
      "email": "user@example.com",
      "phoneNum": "13800138000",
      "sex": "string_value",
      "avatar": "http://example.com",
      "password": "password123",
      "passwordTime": "2024-01-01T00:00:00",
      "smsCodeTime": "2024-01-01T00:00:00",
      "loginFailCount": 1,
      "loginLockTime": "2024-01-01T00:00:00",
      "isSmsLogin": true,
      "status": 1,
      "isSync": true,
      "sourceType": 1,
      "zzdStatus": "string_value",
      "loginIp": "string_value",
      "loginTime": "2024-01-01T00:00:00",
      "expireTime": "2024-01-01T00:00:00",
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "idCard": "string_value",
      "remark": "string_value",
      "dhUserCode": "CODE001",
      "dhUserName": "string_value",
      "dhUserPassword": "password123",
      "token": "string_value",
      "phoneNotNull": true,
      "keyword": "string_value",
      "deptName": "string_value",
      "roles": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "roleId": "...",
          "roleName": "...",
          "roleGroup": "...",
          "roleKey": "...",
          "roleSort": "...",
          "dataScope": "...",
          "status": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "remark": "...",
          "isApprover": "...",
          "flag": "...",
          "appKeys": "...",
          "menuIds": "...",
          "deptIds": "...",
          "permissions": "...",
          "admin": "..."
        }
      ],
      "apps": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "appId": "...",
          "appName": "...",
          "type": "...",
          "types": "...",
          "appKey": "...",
          "appSecret": "...",
          "pcUrl": "...",
          "iconUrl": "...",
          "sort": "...",
          "status": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "remark": "..."
        }
      ],
      "roleId": 1,
      "roleIds": [
        1
      ],
      "postIds": [
        1
      ],
      "roleNames": "string_value",
      "appPerms": {},
      "permissions": [
        "string_value"
      ],
      "postNames": "string_value",
      "posJob": "string_value",
      "deptNames": "string_value",
      "streetDeptId": 1,
      "streetCode": "string_value",
      "streetName": "string_value",
      "gpsX": 1.0,
      "gpsY": 1.0,
      "passwordRemind": true,
      "admin": true
    }
  }
  ```

---

#### 根据用户编号获取授权角色

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/user/authRole/{userId}` |
| OperationId | `authRole` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `userId` | path | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseMapStringObject`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {}
  }
  ```

---

#### 删除用户

| 属性 | 值 |
|------|------|
| 请求方法 | `DELETE` |
| 请求路径 | `/system/user/{userIds}` |
| OperationId | `remove_6` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `userIds` | path | array<integer(int64)> | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseInteger`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": 1
  }
  ```

---

### 角色信息控制层

#### 修改保存角色数据权限

| 属性 | 值 |
|------|------|
| 请求方法 | `PUT` |
| 请求路径 | `/system/role/dataScope` |
| OperationId | `dataScope` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysRoleDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "roleId": 1,
  "roleName": "示例名称",
  "roleGroup": "string_value",
  "roleKey": "string_value",
  "roleSort": 1,
  "dataScope": "string_value",
  "status": true,
  "delFlag": true,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "remark": "string_value",
  "isApprover": true,
  "flag": true,
  "appKeys": [
    "string_value"
  ],
  "menuIds": [
    1
  ],
  "deptIds": [
    1
  ],
  "permissions": [
    "string_value"
  ],
  "admin": true
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseInteger`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": 1
  }
  ```

---

#### 批量选择角色用户授权

| 属性 | 值 |
|------|------|
| 请求方法 | `PUT` |
| 请求路径 | `/system/role/authUser/selectAll` |
| OperationId | `selectAuthUserAll` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `roleId` | query | integer(int64) | 是 |  |
| `userIds` | query | array<integer(int64)> | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseInteger`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": 1
  }
  ```

---

#### 取消角色授权用户

| 属性 | 值 |
|------|------|
| 请求方法 | `PUT` |
| 请求路径 | `/system/role/authUser/cancel` |
| OperationId | `cancelAuthUser` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysUserRoleDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "userId": 1,
  "roleId": 1
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseInteger`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": 1
  }
  ```

---

#### 批量取消角色授权用户

| 属性 | 值 |
|------|------|
| 请求方法 | `PUT` |
| 请求路径 | `/system/role/authUser/cancelAll` |
| OperationId | `cancelAuthUserAll` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `roleId` | query | integer(int64) | 是 |  |
| `userIds` | query | array<integer(int64)> | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseInteger`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": 1
  }
  ```

---

#### 角色数据导出

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/role/export` |
| OperationId | `export_1` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysRoleDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "roleId": 1,
  "roleName": "示例名称",
  "roleGroup": "string_value",
  "roleKey": "string_value",
  "roleSort": 1,
  "dataScope": "string_value",
  "status": true,
  "delFlag": true,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "remark": "string_value",
  "isApprover": true,
  "flag": true,
  "appKeys": [
    "string_value"
  ],
  "menuIds": [
    1
  ],
  "deptIds": [
    1
  ],
  "permissions": [
    "string_value"
  ],
  "admin": true
}
```

**响应：**

- **200**: OK

---

#### 修改保存角色

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/role/edit` |
| OperationId | `edit_1` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysRoleDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "roleId": 1,
  "roleName": "示例名称",
  "roleGroup": "string_value",
  "roleKey": "string_value",
  "roleSort": 1,
  "dataScope": "string_value",
  "status": true,
  "delFlag": true,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "remark": "string_value",
  "isApprover": true,
  "flag": true,
  "appKeys": [
    "string_value"
  ],
  "menuIds": [
    1
  ],
  "deptIds": [
    1
  ],
  "permissions": [
    "string_value"
  ],
  "admin": true
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 角色状态修改

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/role/changeStatus` |
| OperationId | `changeStatus_1` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysRoleDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "roleId": 1,
  "roleName": "示例名称",
  "roleGroup": "string_value",
  "roleKey": "string_value",
  "roleSort": 1,
  "dataScope": "string_value",
  "status": true,
  "delFlag": true,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "remark": "string_value",
  "isApprover": true,
  "flag": true,
  "appKeys": [
    "string_value"
  ],
  "menuIds": [
    1
  ],
  "deptIds": [
    1
  ],
  "permissions": [
    "string_value"
  ],
  "admin": true
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 新增角色

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/role/add` |
| OperationId | `add` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysRoleDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "roleId": 1,
  "roleName": "示例名称",
  "roleGroup": "string_value",
  "roleKey": "string_value",
  "roleSort": 1,
  "dataScope": "string_value",
  "status": true,
  "delFlag": true,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "remark": "string_value",
  "isApprover": true,
  "flag": true,
  "appKeys": [
    "string_value"
  ],
  "menuIds": [
    1
  ],
  "deptIds": [
    1
  ],
  "permissions": [
    "string_value"
  ],
  "admin": true
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 删除角色

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/role/remove` |
| OperationId | `remove` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `ids` | query | array<integer(int64)> | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 获取角色选择框列表

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/role/optionSelect` |
| OperationId | `optionSelect` |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysRoleDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "roleId": 1,
        "roleName": "示例名称",
        "roleGroup": "string_value",
        "roleKey": "string_value",
        "roleSort": 1,
        "dataScope": "string_value",
        "status": true,
        "delFlag": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "remark": "string_value",
        "isApprover": true,
        "flag": true,
        "appKeys": [
          "string_value"
        ],
        "menuIds": [
          1
        ],
        "deptIds": [
          1
        ],
        "permissions": [
          "string_value"
        ],
        "admin": true
      }
    ]
  }
  ```

---

#### 获取角色列表

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/role/list` |
| OperationId | `list` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `roleId` | query | string | 否 | 角色ID |
| `roleName` | query | string | 否 | 角色名称 |
| `roleGroup` | query | string | 否 | 角色组 |
| `roleKey` | query | string | 否 | 角色权限字符串 |
| `roleSort` | query | string | 否 | 显示顺序 |
| `dataScope` | query | string | 否 | 数据范围（1：全部数据权限 2：自定数据权限 3：本部门数据权限 4：本部门及以下数据权限） |
| `status` | query | string | 否 | 角色状态（1正常 0停用） |
| `delFlag` | query | string | 否 | 删除标志（0代表存在1代表删除） |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 更新者 |
| `updateTime` | query | string | 否 | 更新时间 |
| `remark` | query | string | 否 | 备注 |
| `isApprover` | query | string | 否 | 飞行任务审批权限 |
| `flag` | query | boolean | 否 |  |
| `appKeys` | query | string | 否 | 选中的应用 |
| `menuIds` | query | array<integer(int64)> | 否 |  |
| `deptIds` | query | array<integer(int64)> | 否 |  |
| `permissions` | query | array<string> | 否 |  |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseIPageSysRoleDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "size": 1,
      "current": 1,
      "records": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "roleId": "...",
          "roleName": "...",
          "roleGroup": "...",
          "roleKey": "...",
          "roleSort": "...",
          "dataScope": "...",
          "status": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "remark": "...",
          "isApprover": "...",
          "flag": "...",
          "appKeys": "...",
          "menuIds": "...",
          "deptIds": "...",
          "permissions": "...",
          "admin": "..."
        }
      ],
      "total": 1,
      "pages": 1
    }
  }
  ```

---

#### 根据角色编号获取详细信息

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/role/info` |
| OperationId | `getInfo_1` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `roleId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseSysRoleDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "roleId": 1,
      "roleName": "示例名称",
      "roleGroup": "string_value",
      "roleKey": "string_value",
      "roleSort": 1,
      "dataScope": "string_value",
      "status": true,
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "remark": "string_value",
      "isApprover": true,
      "flag": true,
      "appKeys": [
        "string_value"
      ],
      "menuIds": [
        1
      ],
      "deptIds": [
        1
      ],
      "permissions": [
        "string_value"
      ],
      "admin": true
    }
  }
  ```

---

#### 获取对应角色部门树列表

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/role/deptTree/{roleId}` |
| OperationId | `roleDeptTreeSelect` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `roleId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseJSONObject`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "empty": true,
      "innerMap": {}
    }
  }
  ```

---

#### 查询未分配角色用户列表

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/role/authUser/unallocatedList` |
| OperationId | `unallocatedList` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `userId` | query | string | 否 | 用户ID |
| `deptId` | query | string | 是 | 部门ID |
| `dept.deptId` | query | string | 否 | 部门id |
| `dept.parentId` | query | string | 是 | 父部门id |
| `dept.parentName` | query | string | 否 | 父部门名称 |
| `dept.deptCode` | query | string | 否 | 部门编号 |
| `dept.parentCode` | query | string | 否 |  |
| `dept.levelType` | query | string | 否 | 部门级别：1-县级 2-乡镇级 3-县级部门 4-乡镇部门 |
| `dept.ancestors` | query | string | 否 | 祖级列表 |
| `dept.deptName` | query | string | 是 | 部门名称 |
| `dept.shortName` | query | string | 否 | 简称 |
| `dept.orderNum` | query | string | 否 | 显示顺序 |
| `dept.userSortNum` | query | string | 否 | 某用户在部门内的排序 |
| `dept.leader` | query | string | 否 | 负责人 |
| `dept.contact` | query | string | 否 |  |
| `dept.position` | query | string | 否 |  |
| `dept.phone` | query | string | 否 | 联系电话 |
| `dept.email` | query | string | 否 | 邮箱 |
| `dept.status` | query | string | 否 | 部门状态（1正常 0停用） |
| `dept.isCommandSystem` | query | string | 否 | 是否显示指挥体系 |
| `dept.delFlag` | query | string | 否 | 删除标志（0代表存在1代表删除） |
| `dept.createBy` | query | string | 否 | 创建者 |
| `dept.createTime` | query | string | 否 | 创建时间 |
| `dept.updateBy` | query | string | 否 | 更新者 |
| `dept.updateTime` | query | string | 否 | 更新时间 |
| `dept.typeCode` | query | string | 否 |  |
| `dept.typeName` | query | string | 否 |  |
| `dept.address` | query | string | 否 |  |
| `dept.divisionCode` | query | string | 否 |  |
| `dept.institutionCode` | query | string | 否 |  |
| `dept.unifiedSocialCreditCode` | query | string | 否 |  |
| `dept.institutionLevelCode` | query | string | 否 |  |
| `dept.isSync` | query | boolean | 否 |  |
| `dept.sourceType` | query | integer(int32) | 否 |  |
| `dept.zzdStatus` | query | string | 否 |  |
| `dept.children` | query | array<`SysDeptDO`> | 否 |  |
| `dept.posJob` | query | string | 否 |  |
| `dept.leaderName` | query | string | 否 |  |
| `dept.streetName` | query | string | 否 |  |
| `dept.hasChildren` | query | boolean | 否 |  |
| `dept.beginTime` | query | string | 否 |  |
| `dept.endTime` | query | string | 否 |  |
| `deptList` | query | string | 否 | 多个部门 |
| `authUserIds` | query | string | 否 | 当前授权的所有用户id |
| `authDeptIds` | query | string | 否 | 当前授权的所有部门id |
| `selectDeptId` | query | string | 否 | 当前选择部门id |
| `userDeptList` | query | string | 否 | 多个部门 |
| `account` | query | string | 是 | 用户账号 |
| `userName` | query | string | 是 | 用户名称 |
| `employeeCode` | query | string | 否 | 员工Code |
| `empPoliticalStatusCode` | query | string | 否 | 政治面貌，具体参见‘人员数据字典表’ |
| `empJobLevelCode` | query | string | 否 | 职级，具体参见‘人员数据字典表’ |
| `empBudgetedPostCode` | query | string | 否 | 编制，具体参见‘人员数据字典表’ |
| `nickName` | query | string | 是 | 昵称 |
| `email` | query | string | 否 | 用户邮箱 |
| `phoneNum` | query | string | 否 | 手机号码 |
| `sex` | query | string | 否 | 用户性别（0男 1女 2未知） |
| `avatar` | query | string | 否 | 头像地址 |
| `password` | query | string | 否 | 密码 |
| `passwordTime` | query | string | 否 | 上次设置密码时间 |
| `smsCodeTime` | query | string | 否 | 上次验证码登录时间 |
| `loginFailCount` | query | string | 否 | 登录失败次数计数 |
| `loginLockTime` | query | string | 否 | 登录失败锁定终止时间 |
| `isSmsLogin` | query | string | 否 | 是否需要验证码登录 |
| `status` | query | string | 是 | 帐号状态（1正常 0停用 2 注销） |
| `isSync` | query | boolean | 否 |  |
| `sourceType` | query | integer(int32) | 否 |  |
| `zzdStatus` | query | string | 否 |  |
| `loginIp` | query | string | 否 | 最后登陆IP |
| `loginTime` | query | string | 否 | 最后登陆时间 |
| `expireTime` | query | string(date-time) | 否 |  |
| `delFlag` | query | string | 否 | 删除标志：0-未删除，1-已删除 |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 更新者 |
| `updateTime` | query | string | 否 | 更新时间 |
| `idCard` | query | string | 否 | 身份证号 |
| `remark` | query | string | 否 | 备注 |
| `dhUserCode` | query | string | 否 | 大华用户编码 |
| `dhUserName` | query | string | 否 | 大华用户名 |
| `dhUserPassword` | query | string | 否 | 大华用户登录密码 |
| `token` | query | string | 否 |  |
| `phoneNotNull` | query | boolean | 否 |  |
| `keyword` | query | string | 否 |  |
| `deptName` | query | string | 否 |  |
| `roles` | query | array<`SysRoleDO`> | 否 |  |
| `apps` | query | array<`SysAppDO`> | 否 |  |
| `roleId` | query | integer(int64) | 否 |  |
| `roleIds` | query | array<integer(int64)> | 否 |  |
| `postIds` | query | array<integer(int64)> | 否 |  |
| `roleNames` | query | string | 否 |  |
| `permissions` | query | array<string> | 否 |  |
| `postNames` | query | string | 否 |  |
| `posJob` | query | string | 否 |  |
| `deptNames` | query | string | 否 |  |
| `streetDeptId` | query | integer(int64) | 否 |  |
| `streetCode` | query | string | 否 |  |
| `streetName` | query | string | 否 |  |
| `gpsX` | query | number(double) | 否 |  |
| `gpsY` | query | number(double) | 否 |  |
| `passwordRemind` | query | boolean | 否 |  |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseIPageSysUserDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "size": 1,
      "current": 1,
      "records": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "userId": "...",
          "deptId": "...",
          "dept": "...",
          "deptList": "...",
          "authUserIds": "...",
          "authDeptIds": "...",
          "selectDeptId": "...",
          "userDeptList": "...",
          "account": "...",
          "userName": "...",
          "employeeCode": "...",
          "empPoliticalStatusCode": "...",
          "empJobLevelCode": "...",
          "empBudgetedPostCode": "...",
          "nickName": "...",
          "email": "...",
          "phoneNum": "...",
          "sex": "...",
          "avatar": "...",
          "password": "...",
          "passwordTime": "...",
          "smsCodeTime": "...",
          "loginFailCount": "...",
          "loginLockTime": "...",
          "isSmsLogin": "...",
          "status": "...",
          "isSync": "...",
          "sourceType": "...",
          "zzdStatus": "...",
          "loginIp": "...",
          "loginTime": "...",
          "expireTime": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "idCard": "...",
          "remark": "...",
          "dhUserCode": "...",
          "dhUserName": "...",
          "dhUserPassword": "...",
          "token": "...",
          "phoneNotNull": "...",
          "keyword": "...",
          "deptName": "...",
          "roles": "...",
          "apps": "...",
          "roleId": "...",
          "roleIds": "...",
          "postIds": "...",
          "roleNames": "...",
          "appPerms": "...",
          "permissions": "...",
          "postNames": "...",
          "posJob": "...",
          "deptNames": "...",
          "streetDeptId": "...",
          "streetCode": "...",
          "streetName": "...",
          "gpsX": "...",
          "gpsY": "...",
          "passwordRemind": "...",
          "admin": "..."
        }
      ],
      "total": 1,
      "pages": 1
    }
  }
  ```

---

#### 查询已分配角色用户列表

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/role/authUser/allocatedList` |
| OperationId | `allocatedList` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `userId` | query | string | 否 | 用户ID |
| `deptId` | query | string | 是 | 部门ID |
| `dept.deptId` | query | string | 否 | 部门id |
| `dept.parentId` | query | string | 是 | 父部门id |
| `dept.parentName` | query | string | 否 | 父部门名称 |
| `dept.deptCode` | query | string | 否 | 部门编号 |
| `dept.parentCode` | query | string | 否 |  |
| `dept.levelType` | query | string | 否 | 部门级别：1-县级 2-乡镇级 3-县级部门 4-乡镇部门 |
| `dept.ancestors` | query | string | 否 | 祖级列表 |
| `dept.deptName` | query | string | 是 | 部门名称 |
| `dept.shortName` | query | string | 否 | 简称 |
| `dept.orderNum` | query | string | 否 | 显示顺序 |
| `dept.userSortNum` | query | string | 否 | 某用户在部门内的排序 |
| `dept.leader` | query | string | 否 | 负责人 |
| `dept.contact` | query | string | 否 |  |
| `dept.position` | query | string | 否 |  |
| `dept.phone` | query | string | 否 | 联系电话 |
| `dept.email` | query | string | 否 | 邮箱 |
| `dept.status` | query | string | 否 | 部门状态（1正常 0停用） |
| `dept.isCommandSystem` | query | string | 否 | 是否显示指挥体系 |
| `dept.delFlag` | query | string | 否 | 删除标志（0代表存在1代表删除） |
| `dept.createBy` | query | string | 否 | 创建者 |
| `dept.createTime` | query | string | 否 | 创建时间 |
| `dept.updateBy` | query | string | 否 | 更新者 |
| `dept.updateTime` | query | string | 否 | 更新时间 |
| `dept.typeCode` | query | string | 否 |  |
| `dept.typeName` | query | string | 否 |  |
| `dept.address` | query | string | 否 |  |
| `dept.divisionCode` | query | string | 否 |  |
| `dept.institutionCode` | query | string | 否 |  |
| `dept.unifiedSocialCreditCode` | query | string | 否 |  |
| `dept.institutionLevelCode` | query | string | 否 |  |
| `dept.isSync` | query | boolean | 否 |  |
| `dept.sourceType` | query | integer(int32) | 否 |  |
| `dept.zzdStatus` | query | string | 否 |  |
| `dept.children` | query | array<`SysDeptDO`> | 否 |  |
| `dept.posJob` | query | string | 否 |  |
| `dept.leaderName` | query | string | 否 |  |
| `dept.streetName` | query | string | 否 |  |
| `dept.hasChildren` | query | boolean | 否 |  |
| `dept.beginTime` | query | string | 否 |  |
| `dept.endTime` | query | string | 否 |  |
| `deptList` | query | string | 否 | 多个部门 |
| `authUserIds` | query | string | 否 | 当前授权的所有用户id |
| `authDeptIds` | query | string | 否 | 当前授权的所有部门id |
| `selectDeptId` | query | string | 否 | 当前选择部门id |
| `userDeptList` | query | string | 否 | 多个部门 |
| `account` | query | string | 是 | 用户账号 |
| `userName` | query | string | 是 | 用户名称 |
| `employeeCode` | query | string | 否 | 员工Code |
| `empPoliticalStatusCode` | query | string | 否 | 政治面貌，具体参见‘人员数据字典表’ |
| `empJobLevelCode` | query | string | 否 | 职级，具体参见‘人员数据字典表’ |
| `empBudgetedPostCode` | query | string | 否 | 编制，具体参见‘人员数据字典表’ |
| `nickName` | query | string | 是 | 昵称 |
| `email` | query | string | 否 | 用户邮箱 |
| `phoneNum` | query | string | 否 | 手机号码 |
| `sex` | query | string | 否 | 用户性别（0男 1女 2未知） |
| `avatar` | query | string | 否 | 头像地址 |
| `password` | query | string | 否 | 密码 |
| `passwordTime` | query | string | 否 | 上次设置密码时间 |
| `smsCodeTime` | query | string | 否 | 上次验证码登录时间 |
| `loginFailCount` | query | string | 否 | 登录失败次数计数 |
| `loginLockTime` | query | string | 否 | 登录失败锁定终止时间 |
| `isSmsLogin` | query | string | 否 | 是否需要验证码登录 |
| `status` | query | string | 是 | 帐号状态（1正常 0停用 2 注销） |
| `isSync` | query | boolean | 否 |  |
| `sourceType` | query | integer(int32) | 否 |  |
| `zzdStatus` | query | string | 否 |  |
| `loginIp` | query | string | 否 | 最后登陆IP |
| `loginTime` | query | string | 否 | 最后登陆时间 |
| `expireTime` | query | string(date-time) | 否 |  |
| `delFlag` | query | string | 否 | 删除标志：0-未删除，1-已删除 |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 更新者 |
| `updateTime` | query | string | 否 | 更新时间 |
| `idCard` | query | string | 否 | 身份证号 |
| `remark` | query | string | 否 | 备注 |
| `dhUserCode` | query | string | 否 | 大华用户编码 |
| `dhUserName` | query | string | 否 | 大华用户名 |
| `dhUserPassword` | query | string | 否 | 大华用户登录密码 |
| `token` | query | string | 否 |  |
| `phoneNotNull` | query | boolean | 否 |  |
| `keyword` | query | string | 否 |  |
| `deptName` | query | string | 否 |  |
| `roles` | query | array<`SysRoleDO`> | 否 |  |
| `apps` | query | array<`SysAppDO`> | 否 |  |
| `roleId` | query | integer(int64) | 否 |  |
| `roleIds` | query | array<integer(int64)> | 否 |  |
| `postIds` | query | array<integer(int64)> | 否 |  |
| `roleNames` | query | string | 否 |  |
| `permissions` | query | array<string> | 否 |  |
| `postNames` | query | string | 否 |  |
| `posJob` | query | string | 否 |  |
| `deptNames` | query | string | 否 |  |
| `streetDeptId` | query | integer(int64) | 否 |  |
| `streetCode` | query | string | 否 |  |
| `streetName` | query | string | 否 |  |
| `gpsX` | query | number(double) | 否 |  |
| `gpsY` | query | number(double) | 否 |  |
| `passwordRemind` | query | boolean | 否 |  |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseIPageSysUserDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "size": 1,
      "current": 1,
      "records": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "userId": "...",
          "deptId": "...",
          "dept": "...",
          "deptList": "...",
          "authUserIds": "...",
          "authDeptIds": "...",
          "selectDeptId": "...",
          "userDeptList": "...",
          "account": "...",
          "userName": "...",
          "employeeCode": "...",
          "empPoliticalStatusCode": "...",
          "empJobLevelCode": "...",
          "empBudgetedPostCode": "...",
          "nickName": "...",
          "email": "...",
          "phoneNum": "...",
          "sex": "...",
          "avatar": "...",
          "password": "...",
          "passwordTime": "...",
          "smsCodeTime": "...",
          "loginFailCount": "...",
          "loginLockTime": "...",
          "isSmsLogin": "...",
          "status": "...",
          "isSync": "...",
          "sourceType": "...",
          "zzdStatus": "...",
          "loginIp": "...",
          "loginTime": "...",
          "expireTime": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "idCard": "...",
          "remark": "...",
          "dhUserCode": "...",
          "dhUserName": "...",
          "dhUserPassword": "...",
          "token": "...",
          "phoneNotNull": "...",
          "keyword": "...",
          "deptName": "...",
          "roles": "...",
          "apps": "...",
          "roleId": "...",
          "roleIds": "...",
          "postIds": "...",
          "roleNames": "...",
          "appPerms": "...",
          "permissions": "...",
          "postNames": "...",
          "posJob": "...",
          "deptNames": "...",
          "streetDeptId": "...",
          "streetCode": "...",
          "streetName": "...",
          "gpsX": "...",
          "gpsY": "...",
          "passwordRemind": "...",
          "admin": "..."
        }
      ],
      "total": 1,
      "pages": 1
    }
  }
  ```

---

### 浙政钉接口

#### 发送浙政钉工作通知

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/zwdd/sendWorkNotification` |
| OperationId | `sendWorkNotification` |

**请求体：**

- Content-Type: `application/json`
- Schema: `ZwddMsgRequest`

**请求示例：**
```json
{
  "userIdList": [
    1
  ],
  "content": "string_value"
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 同步浙政钉部门

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/zwdd/syncDept` |
| OperationId | `syncDept` |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 设置部门级别

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/zwdd/setDeptLevel` |
| OperationId | `setDeptLevel` |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

### 场景标签管理

#### 编辑场景标签

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/scene/tag/edit` |
| OperationId | `editTag` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SceneTagEditRequest`

**请求示例：**
```json
{
  "sceneId": 1,
  "sceneName": "示例名称",
  "deptIds": [
    1
  ]
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 新增场景标签

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/scene/tag/add` |
| OperationId | `addTag` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SceneTagSaveRequest`

**请求示例：**
```json
{
  "sceneName": "示例名称",
  "deptIds": [
    1
  ]
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 删除场景标签

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/scene/tag/remove` |
| OperationId | `removeTag` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `sceneIds` | query | array<integer(int64)> | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 分页查询场景标签

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/scene/tag/page` |
| OperationId | `tagPage` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `pageNum` | query | integer(int32) | 否 |  |
| `pageSize` | query | integer(int32) | 否 |  |
| `orderByColumn` | query | string | 否 |  |
| `asc` | query | string | 否 |  |
| `sceneName` | query | string | 否 |  |
| `deptName` | query | string | 否 |  |
| `deptId` | query | integer(int64) | 否 |  |
| `deptIds` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseIPageSceneTagPageVO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "size": 1,
      "current": 1,
      "records": [
        {
          "sceneId": "...",
          "sceneName": "...",
          "deptIds": "...",
          "deptNames": "...",
          "createTime": "...",
          "createBy": "..."
        }
      ],
      "total": 1,
      "pages": 1
    }
  }
  ```

---

#### 场景标签详情

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/scene/tag/info` |
| OperationId | `tagInfo` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `sceneId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseSceneTagInfoVO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "sceneId": 1,
      "sceneName": "示例名称",
      "deptIds": [
        1
      ]
    }
  }
  ```

---

#### 根据部门查询可用场景（支持多个部门并集）

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/scene/dept/list` |
| OperationId | `listByDeptIds` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `deptIds` | query | string | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysSceneDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "sceneId": 1,
        "sceneName": "示例名称",
        "sceneCode": "CODE001",
        "status": true,
        "delFlag": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "remark": "string_value"
      }
    ]
  }
  ```

---

### 岗位信息控制层

#### 导出岗位

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/post/export` |
| OperationId | `export_2` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysPostDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "postId": 1,
  "postCode": "CODE001",
  "postName": "示例名称",
  "postSort": 1,
  "status": true,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "remark": "string_value"
}
```

**响应：**

- **200**: OK

---

#### 修改岗位

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/post/edit` |
| OperationId | `edit_2` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysPostDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "postId": 1,
  "postCode": "CODE001",
  "postName": "示例名称",
  "postSort": 1,
  "status": true,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "remark": "string_value"
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 新增岗位

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/post/add` |
| OperationId | `add_1` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysPostDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "postId": 1,
  "postCode": "CODE001",
  "postName": "示例名称",
  "postSort": 1,
  "status": true,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "remark": "string_value"
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 删除岗位

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/post/remove` |
| OperationId | `remove_1` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `ids` | query | array<integer(int64)> | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 获取岗位选择框列表

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/post/optionSelect` |
| OperationId | `optionSelect_1` |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysPostDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "postId": 1,
        "postCode": "CODE001",
        "postName": "示例名称",
        "postSort": 1,
        "status": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "remark": "string_value"
      }
    ]
  }
  ```

---

#### 获取岗位列表

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/post/list` |
| OperationId | `list_1` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `postId` | query | string | 否 | 岗位ID |
| `postCode` | query | string | 否 | 岗位编码 |
| `postName` | query | string | 否 | 岗位名称 |
| `postSort` | query | string | 否 | 显示顺序 |
| `status` | query | string | 否 | 状态（1正常 0停用） |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 更新者 |
| `updateTime` | query | string | 否 | 更新时间 |
| `remark` | query | string | 否 | 备注 |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseIPageSysPostDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "size": 1,
      "current": 1,
      "records": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "postId": "...",
          "postCode": "...",
          "postName": "...",
          "postSort": "...",
          "status": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "remark": "..."
        }
      ],
      "total": 1,
      "pages": 1
    }
  }
  ```

---

#### 查询所有岗位

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/post/listAll` |
| OperationId | `listAll` |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysPostDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "postId": 1,
        "postCode": "CODE001",
        "postName": "示例名称",
        "postSort": 1,
        "status": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "remark": "string_value"
      }
    ]
  }
  ```

---

#### 根据岗位编号获取详细信息

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/post/info` |
| OperationId | `getInfo_2` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `postId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseSysPostDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "postId": 1,
      "postCode": "CODE001",
      "postName": "示例名称",
      "postSort": 1,
      "status": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "remark": "string_value"
    }
  }
  ```

---

#### 根据用户id获取用户岗位列表

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/post/getPostByUserId` |
| OperationId | `getPostByUserId` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `userId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysPostDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "postId": 1,
        "postCode": "CODE001",
        "postName": "示例名称",
        "postSort": 1,
        "status": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "remark": "string_value"
      }
    ]
  }
  ```

---

### 操作日志记录接口

#### 保存操作日志

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/operlog/save` |
| OperationId | `save` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysOperLogDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "operId": 1,
  "moduleName": "示例名称",
  "functionName": "示例名称",
  "businessType": 1,
  "method": "示例名称",
  "requestMethod": "string_value",
  "operatorType": 1,
  "operName": "string_value",
  "deptName": "示例名称",
  "operUrl": "http://example.com",
  "operIp": "http://example.com",
  "operLocation": "string_value",
  "operParam": "string_value",
  "jsonResult": "string_value",
  "status": 1,
  "errorMsg": "string_value",
  "operTime": "2024-01-01T00:00:00",
  "responseTime": 1,
  "businessTypes": [
    1
  ]
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 日志导出

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/operlog/export` |
| OperationId | `export_3` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysOperLogDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "operId": 1,
  "moduleName": "示例名称",
  "functionName": "示例名称",
  "businessType": 1,
  "method": "示例名称",
  "requestMethod": "string_value",
  "operatorType": 1,
  "operName": "string_value",
  "deptName": "示例名称",
  "operUrl": "http://example.com",
  "operIp": "http://example.com",
  "operLocation": "string_value",
  "operParam": "string_value",
  "jsonResult": "string_value",
  "status": 1,
  "errorMsg": "string_value",
  "operTime": "2024-01-01T00:00:00",
  "responseTime": 1,
  "businessTypes": [
    1
  ]
}
```

**响应：**

- **200**: OK

---

#### 删除数据

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/operlog/remove` |
| OperationId | `delete` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `ids` | query | array<integer(int64)> | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 根据时间删除日志

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/operlog/remove-by-time` |
| OperationId | `removeByTime` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `beginTime` | query | string | 是 |  |
| `endTime` | query | string | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 分页查询

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/operlog/pageLogin` |
| OperationId | `pageLogin` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `operId` | query | string | 否 | 日志主键 |
| `moduleName` | query | string | 否 | 模块名称 |
| `functionName` | query | string | 否 | 功能名称 |
| `businessType` | query | string | 否 | 业务类型（0其它 1新增 2修改 3删除） |
| `method` | query | string | 否 | 方法名称 |
| `requestMethod` | query | string | 否 | 请求方式 |
| `operatorType` | query | string | 否 | 操作类别（0审批 1后台用户 2手机端用户） |
| `operName` | query | string | 否 | 操作人员 |
| `deptName` | query | string | 否 | 部门名称 |
| `operUrl` | query | string | 否 | 请求URL |
| `operIp` | query | string | 否 | 主机地址 |
| `operLocation` | query | string | 否 | 操作地点 |
| `operParam` | query | string | 否 | 请求参数 |
| `jsonResult` | query | string | 否 | 返回参数 |
| `status` | query | string | 否 | 操作状态（0正常 1异常） |
| `errorMsg` | query | string | 否 | 错误消息 |
| `operTime` | query | string | 否 | 操作时间 |
| `responseTime` | query | string | 否 | 响应时长 |
| `businessTypes` | query | array<integer(int32)> | 否 |  |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |
| `pageNum` | query | integer(int32) | 否 |  |
| `pageSize` | query | integer(int32) | 否 |  |
| `orderByColumn` | query | string | 否 |  |
| `asc` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseIPageSysOperLogDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "size": 1,
      "current": 1,
      "records": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "operId": "...",
          "moduleName": "...",
          "functionName": "...",
          "businessType": "...",
          "method": "...",
          "requestMethod": "...",
          "operatorType": "...",
          "operName": "...",
          "deptName": "...",
          "operUrl": "...",
          "operIp": "...",
          "operLocation": "...",
          "operParam": "...",
          "jsonResult": "...",
          "status": "...",
          "errorMsg": "...",
          "operTime": "...",
          "responseTime": "...",
          "businessTypes": "..."
        }
      ],
      "total": 1,
      "pages": 1
    }
  }
  ```

---

#### 分页查询

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/operlog/list` |
| OperationId | `page` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `operId` | query | string | 否 | 日志主键 |
| `moduleName` | query | string | 否 | 模块名称 |
| `functionName` | query | string | 否 | 功能名称 |
| `businessType` | query | string | 否 | 业务类型（0其它 1新增 2修改 3删除） |
| `method` | query | string | 否 | 方法名称 |
| `requestMethod` | query | string | 否 | 请求方式 |
| `operatorType` | query | string | 否 | 操作类别（0审批 1后台用户 2手机端用户） |
| `operName` | query | string | 否 | 操作人员 |
| `deptName` | query | string | 否 | 部门名称 |
| `operUrl` | query | string | 否 | 请求URL |
| `operIp` | query | string | 否 | 主机地址 |
| `operLocation` | query | string | 否 | 操作地点 |
| `operParam` | query | string | 否 | 请求参数 |
| `jsonResult` | query | string | 否 | 返回参数 |
| `status` | query | string | 否 | 操作状态（0正常 1异常） |
| `errorMsg` | query | string | 否 | 错误消息 |
| `operTime` | query | string | 否 | 操作时间 |
| `responseTime` | query | string | 否 | 响应时长 |
| `businessTypes` | query | array<integer(int32)> | 否 |  |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |
| `pageNum` | query | integer(int32) | 否 |  |
| `pageSize` | query | integer(int32) | 否 |  |
| `orderByColumn` | query | string | 否 |  |
| `asc` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseIPageSysOperLogDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "size": 1,
      "current": 1,
      "records": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "operId": "...",
          "moduleName": "...",
          "functionName": "...",
          "businessType": "...",
          "method": "...",
          "requestMethod": "...",
          "operatorType": "...",
          "operName": "...",
          "deptName": "...",
          "operUrl": "...",
          "operIp": "...",
          "operLocation": "...",
          "operParam": "...",
          "jsonResult": "...",
          "status": "...",
          "errorMsg": "...",
          "operTime": "...",
          "responseTime": "...",
          "businessTypes": "..."
        }
      ],
      "total": 1,
      "pages": 1
    }
  }
  ```

---

#### 按ID查询

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/operlog/info` |
| OperationId | `info_1` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `id` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseSysOperLogDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "operId": 1,
      "moduleName": "示例名称",
      "functionName": "示例名称",
      "businessType": 1,
      "method": "示例名称",
      "requestMethod": "string_value",
      "operatorType": 1,
      "operName": "string_value",
      "deptName": "示例名称",
      "operUrl": "http://example.com",
      "operIp": "http://example.com",
      "operLocation": "string_value",
      "operParam": "string_value",
      "jsonResult": "string_value",
      "status": 1,
      "errorMsg": "string_value",
      "operTime": "2024-01-01T00:00:00",
      "responseTime": 1,
      "businessTypes": [
        1
      ]
    }
  }
  ```

---

#### 清空日志

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/operlog/clean` |
| OperationId | `cleanOperateLog` |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `Response`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {}
  }
  ```

---

### 菜单信息控制层

#### 修改菜单

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/menu/edit` |
| OperationId | `edit_3` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysMenuDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "menuId": 1,
  "menuName": "示例名称",
  "perms": "string_value",
  "parentId": 1,
  "parentPerms": "string_value",
  "orderNum": 1,
  "path": "http://example.com",
  "component": "string_value",
  "isFrame": true,
  "menuType": "string_value",
  "visible": true,
  "status": true,
  "icon": "string_value",
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "remark": "string_value",
  "appKey": "string_value",
  "query": "string_value",
  "roleId": 1
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 新增菜单

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/menu/add` |
| OperationId | `add_2` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysMenuDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "menuId": 1,
  "menuName": "示例名称",
  "perms": "string_value",
  "parentId": 1,
  "parentPerms": "string_value",
  "orderNum": 1,
  "path": "http://example.com",
  "component": "string_value",
  "isFrame": true,
  "menuType": "string_value",
  "visible": true,
  "status": true,
  "icon": "string_value",
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "remark": "string_value",
  "appKey": "string_value",
  "query": "string_value",
  "roleId": 1
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 获取菜单下拉树列表

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/menu/treeSelect` |
| OperationId | `treeSelect` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `menuId` | query | string | 否 | 菜单ID |
| `menuName` | query | string | 否 | 菜单名称 |
| `perms` | query | string | 否 | 权限标识 |
| `parentId` | query | string | 否 | 父菜单ID |
| `parentPerms` | query | string | 否 | 父权限标识 |
| `orderNum` | query | string | 否 | 显示顺序 |
| `path` | query | string | 否 | 路由地址 |
| `component` | query | string | 否 | 组件路径 |
| `isFrame` | query | string | 否 | 是否为外链（1是 0否） |
| `menuType` | query | string | 否 | 菜单类型（M目录 C菜单 F按钮） |
| `visible` | query | string | 否 | 菜单状态（1显示 0隐藏） |
| `status` | query | string | 否 | 菜单状态（1正常 0停用） |
| `icon` | query | string | 否 | 菜单图标 |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 更新者 |
| `updateTime` | query | string | 否 | 更新时间 |
| `remark` | query | string | 否 | 备注 |
| `appKey` | query | string | 否 | 应用appKey |
| `query` | query | string | 否 | 路由参数 |
| `roleId` | query | string | 否 | 角色ID |
| `children` | query | array<`SysMenuDO`> | 否 |  |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysMenuDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "menuId": 1,
        "menuName": "示例名称",
        "perms": "string_value",
        "parentId": 1,
        "parentPerms": "string_value",
        "orderNum": 1,
        "path": "http://example.com",
        "component": "string_value",
        "isFrame": true,
        "menuType": "string_value",
        "visible": true,
        "status": true,
        "icon": "string_value",
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "remark": "string_value",
        "appKey": "string_value",
        "query": "string_value",
        "roleId": 1
      }
    ]
  }
  ```

---

#### 加载对应角色菜单列表树

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/menu/roleMenuTreeSelect` |
| OperationId | `roleMenuTreeSelect` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `roleId` | query | integer(int64) | 是 |  |
| `appKey` | query | string | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseJSONObject`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "empty": true,
      "innerMap": {}
    }
  }
  ```

---

#### 加载对应角色菜单列表树，查询全部菜单无限制

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/menu/roleMenuTreeSelectAll` |
| OperationId | `roleMenuTreeSelectAll` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `roleId` | query | integer(int64) | 是 |  |
| `appKey` | query | string | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseJSONObject`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "empty": true,
      "innerMap": {}
    }
  }
  ```

---

#### 删除菜单

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/menu/remove` |
| OperationId | `remove_2` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `menuId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 获取菜单列表

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/menu/list` |
| OperationId | `list_2` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `menuId` | query | string | 否 | 菜单ID |
| `menuName` | query | string | 否 | 菜单名称 |
| `perms` | query | string | 否 | 权限标识 |
| `parentId` | query | string | 否 | 父菜单ID |
| `parentPerms` | query | string | 否 | 父权限标识 |
| `orderNum` | query | string | 否 | 显示顺序 |
| `path` | query | string | 否 | 路由地址 |
| `component` | query | string | 否 | 组件路径 |
| `isFrame` | query | string | 否 | 是否为外链（1是 0否） |
| `menuType` | query | string | 否 | 菜单类型（M目录 C菜单 F按钮） |
| `visible` | query | string | 否 | 菜单状态（1显示 0隐藏） |
| `status` | query | string | 否 | 菜单状态（1正常 0停用） |
| `icon` | query | string | 否 | 菜单图标 |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 更新者 |
| `updateTime` | query | string | 否 | 更新时间 |
| `remark` | query | string | 否 | 备注 |
| `appKey` | query | string | 否 | 应用appKey |
| `query` | query | string | 否 | 路由参数 |
| `roleId` | query | string | 否 | 角色ID |
| `children` | query | array<`SysMenuDO`> | 否 |  |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysMenuDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "menuId": 1,
        "menuName": "示例名称",
        "perms": "string_value",
        "parentId": 1,
        "parentPerms": "string_value",
        "orderNum": 1,
        "path": "http://example.com",
        "component": "string_value",
        "isFrame": true,
        "menuType": "string_value",
        "visible": true,
        "status": true,
        "icon": "string_value",
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "remark": "string_value",
        "appKey": "string_value",
        "query": "string_value",
        "roleId": 1
      }
    ]
  }
  ```

---

#### 获取菜单列表

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/menu/listAll` |
| OperationId | `listAll_1` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `menuId` | query | string | 否 | 菜单ID |
| `menuName` | query | string | 否 | 菜单名称 |
| `perms` | query | string | 否 | 权限标识 |
| `parentId` | query | string | 否 | 父菜单ID |
| `parentPerms` | query | string | 否 | 父权限标识 |
| `orderNum` | query | string | 否 | 显示顺序 |
| `path` | query | string | 否 | 路由地址 |
| `component` | query | string | 否 | 组件路径 |
| `isFrame` | query | string | 否 | 是否为外链（1是 0否） |
| `menuType` | query | string | 否 | 菜单类型（M目录 C菜单 F按钮） |
| `visible` | query | string | 否 | 菜单状态（1显示 0隐藏） |
| `status` | query | string | 否 | 菜单状态（1正常 0停用） |
| `icon` | query | string | 否 | 菜单图标 |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 更新者 |
| `updateTime` | query | string | 否 | 更新时间 |
| `remark` | query | string | 否 | 备注 |
| `appKey` | query | string | 否 | 应用appKey |
| `query` | query | string | 否 | 路由参数 |
| `roleId` | query | string | 否 | 角色ID |
| `children` | query | array<`SysMenuDO`> | 否 |  |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysMenuDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "menuId": 1,
        "menuName": "示例名称",
        "perms": "string_value",
        "parentId": 1,
        "parentPerms": "string_value",
        "orderNum": 1,
        "path": "http://example.com",
        "component": "string_value",
        "isFrame": true,
        "menuType": "string_value",
        "visible": true,
        "status": true,
        "icon": "string_value",
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "remark": "string_value",
        "appKey": "string_value",
        "query": "string_value",
        "roleId": 1
      }
    ]
  }
  ```

---

#### 根据菜单编号获取详细信息

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/menu/info` |
| OperationId | `getInfo_3` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `menuId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseSysMenuDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "menuId": 1,
      "menuName": "示例名称",
      "perms": "string_value",
      "parentId": 1,
      "parentPerms": "string_value",
      "orderNum": 1,
      "path": "http://example.com",
      "component": "string_value",
      "isFrame": true,
      "menuType": "string_value",
      "visible": true,
      "status": true,
      "icon": "string_value",
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "remark": "string_value",
      "appKey": "string_value",
      "query": "string_value",
      "roleId": 1
    }
  }
  ```

---

#### 获取路由信息

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/menu/getRouters` |
| OperationId | `getRouters` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `appKey` | query | string | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListRouterVO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "name": "string_value",
        "path": "string_value",
        "hidden": true,
        "redirect": "string_value",
        "component": "string_value",
        "alwaysShow": true,
        "meta": {
          "title": "...",
          "icon": "..."
        },
        "query": "string_value",
        "appKey": "string_value"
      }
    ]
  }
  ```

---

### 字典类型表接口

#### /dict/type/export

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/dict/type/export` |
| OperationId | `export_4` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysDictTypeDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "dictId": 1,
  "dictName": "示例名称",
  "dictType": "string_value",
  "status": true,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "remark": "string_value"
}
```

**响应：**

- **200**: OK

---

#### /dict/type/edit

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/dict/type/edit` |
| OperationId | `edit_4` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysDictTypeDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "dictId": 1,
  "dictName": "示例名称",
  "dictType": "string_value",
  "status": true,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "remark": "string_value"
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### /dict/type/add

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/dict/type/add` |
| OperationId | `add_3` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysDictTypeDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "dictId": 1,
  "dictName": "示例名称",
  "dictType": "string_value",
  "status": true,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "remark": "string_value"
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### /dict/type/remove

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dict/type/remove` |
| OperationId | `remove_3` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `ids` | query | array<integer(int64)> | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### /dict/type/optionSelect

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dict/type/optionSelect` |
| OperationId | `optionSelect_2` |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysDictTypeDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "dictId": 1,
        "dictName": "示例名称",
        "dictType": "string_value",
        "status": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "remark": "string_value"
      }
    ]
  }
  ```

---

#### /dict/type/list

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dict/type/list` |
| OperationId | `list_3` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `dictId` | query | string | 否 | 字典主键 |
| `dictName` | query | string | 否 | 字典名称 |
| `dictType` | query | string | 否 | 字典类型 |
| `status` | query | string | 否 | 状态（1正常 0停用） |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 更新者 |
| `updateTime` | query | string | 否 | 更新时间 |
| `remark` | query | string | 否 | 备注 |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseIPageSysDictTypeDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "size": 1,
      "current": 1,
      "records": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "dictId": "...",
          "dictName": "...",
          "dictType": "...",
          "status": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "remark": "..."
        }
      ],
      "total": 1,
      "pages": 1
    }
  }
  ```

---

#### /dict/type/listAll

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dict/type/listAll` |
| OperationId | `listAll_2` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `dictId` | query | string | 否 | 字典主键 |
| `dictName` | query | string | 否 | 字典名称 |
| `dictType` | query | string | 否 | 字典类型 |
| `status` | query | string | 否 | 状态（1正常 0停用） |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 更新者 |
| `updateTime` | query | string | 否 | 更新时间 |
| `remark` | query | string | 否 | 备注 |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysDictTypeDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "dictId": 1,
        "dictName": "示例名称",
        "dictType": "string_value",
        "status": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "remark": "string_value"
      }
    ]
  }
  ```

---

#### /dict/type/info

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dict/type/info` |
| OperationId | `getInfo_4` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `dictId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseSysDictTypeDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "dictId": 1,
      "dictName": "示例名称",
      "dictType": "string_value",
      "status": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "remark": "string_value"
    }
  }
  ```

---

#### /dict/type/clearCache

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dict/type/clearCache` |
| OperationId | `clearCache` |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `Response`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {}
  }
  ```

---

### 字典数据表接口

#### /dict/data/export

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/dict/data/export` |
| OperationId | `export_5` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysDictDataDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "dictCode": 1,
  "dictSort": 1,
  "dictLabel": "string_value",
  "dictValue": "string_value",
  "dictType": "string_value",
  "cssClass": "string_value",
  "listClass": "string_value",
  "isDefault": "string_value",
  "status": true,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "remark": "string_value"
}
```

**响应：**

- **200**: OK

---

#### /dict/data/edit

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/dict/data/edit` |
| OperationId | `edit_5` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysDictDataDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "dictCode": 1,
  "dictSort": 1,
  "dictLabel": "string_value",
  "dictValue": "string_value",
  "dictType": "string_value",
  "cssClass": "string_value",
  "listClass": "string_value",
  "isDefault": "string_value",
  "status": true,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "remark": "string_value"
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### /dict/data/add

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/dict/data/add` |
| OperationId | `add_4` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysDictDataDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "dictCode": 1,
  "dictSort": 1,
  "dictLabel": "string_value",
  "dictValue": "string_value",
  "dictType": "string_value",
  "cssClass": "string_value",
  "listClass": "string_value",
  "isDefault": "string_value",
  "status": true,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "remark": "string_value"
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### /dict/data/remove

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dict/data/remove` |
| OperationId | `remove_4` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `dictCodes` | query | array<integer(int64)> | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseSysDictDataDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "dictCode": 1,
      "dictSort": 1,
      "dictLabel": "string_value",
      "dictValue": "string_value",
      "dictType": "string_value",
      "cssClass": "string_value",
      "listClass": "string_value",
      "isDefault": "string_value",
      "status": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "remark": "string_value"
    }
  }
  ```

---

#### /dict/data/queryDictValue

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dict/data/queryDictValue` |
| OperationId | `queryDictValue` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `dictType` | query | string | 是 |  |
| `dictLabel` | query | string | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseSysDictDataDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "dictCode": 1,
      "dictSort": 1,
      "dictLabel": "string_value",
      "dictValue": "string_value",
      "dictType": "string_value",
      "cssClass": "string_value",
      "listClass": "string_value",
      "isDefault": "string_value",
      "status": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "remark": "string_value"
    }
  }
  ```

---

#### /dict/data/list

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dict/data/list` |
| OperationId | `list_4` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `dictCode` | query | string | 否 | 字典编码 |
| `dictSort` | query | string | 否 | 字典排序 |
| `dictLabel` | query | string | 否 | 字典标签 |
| `dictValue` | query | string | 否 | 字典键值 |
| `dictType` | query | string | 否 | 字典类型 |
| `cssClass` | query | string | 否 | 样式属性（其他样式扩展） |
| `listClass` | query | string | 否 | 表格回显样式 |
| `isDefault` | query | string | 否 | 是否默认（Y是 N否） |
| `status` | query | string | 否 | 状态（true正常 false停用） |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 更新者 |
| `updateTime` | query | string | 否 | 更新时间 |
| `remark` | query | string | 否 | 备注 |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseIPageSysDictDataDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "size": 1,
      "current": 1,
      "records": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "dictCode": "...",
          "dictSort": "...",
          "dictLabel": "...",
          "dictValue": "...",
          "dictType": "...",
          "cssClass": "...",
          "listClass": "...",
          "isDefault": "...",
          "status": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "remark": "..."
        }
      ],
      "total": 1,
      "pages": 1
    }
  }
  ```

---

#### /dict/data/info

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dict/data/info` |
| OperationId | `getInfo_5` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `dictCode` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseSysDictDataDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "dictCode": 1,
      "dictSort": 1,
      "dictLabel": "string_value",
      "dictValue": "string_value",
      "dictType": "string_value",
      "cssClass": "string_value",
      "listClass": "string_value",
      "isDefault": "string_value",
      "status": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "remark": "string_value"
    }
  }
  ```

---

#### /dict/data/getStreetDict

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dict/data/getStreetDict` |
| OperationId | `getStreetDict` |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseObject`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {}
  }
  ```

---

#### /dict/data/get-by-type

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dict/data/get-by-type` |
| OperationId | `getDictByType` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `dictType` | query | string | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysDictDataDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "dictCode": 1,
        "dictSort": 1,
        "dictLabel": "string_value",
        "dictValue": "string_value",
        "dictType": "string_value",
        "cssClass": "string_value",
        "listClass": "string_value",
        "isDefault": "string_value",
        "status": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "remark": "string_value"
      }
    ]
  }
  ```

---

### 部门信息控制层

#### 修改部门

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/dept/edit` |
| OperationId | `edit_6` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysDeptDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "deptId": 1,
  "parentId": 1,
  "parentName": "示例名称",
  "deptCode": "string_value",
  "parentCode": "string_value",
  "levelType": 1,
  "ancestors": "string_value",
  "deptName": "示例名称",
  "shortName": "string_value",
  "orderNum": 1,
  "userSortNum": 1,
  "leader": "string_value",
  "contact": "string_value",
  "position": "string_value",
  "phone": "13800138000",
  "email": "user@example.com",
  "status": true,
  "isCommandSystem": true,
  "delFlag": true,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "typeCode": "string_value",
  "typeName": "string_value",
  "address": "string_value",
  "divisionCode": "string_value",
  "institutionCode": "string_value",
  "unifiedSocialCreditCode": "string_value",
  "institutionLevelCode": "string_value",
  "isSync": true,
  "sourceType": 1,
  "zzdStatus": "string_value",
  "children": [
    {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "deptId": 1,
      "parentId": 1,
      "parentName": "示例名称",
      "deptCode": "string_value",
      "parentCode": "string_value",
      "levelType": 1,
      "ancestors": "string_value",
      "deptName": "示例名称",
      "shortName": "string_value",
      "orderNum": 1,
      "userSortNum": 1,
      "leader": "string_value",
      "contact": "string_value",
      "position": "string_value",
      "phone": "13800138000",
      "email": "user@example.com",
      "status": true,
      "isCommandSystem": true,
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "typeCode": "string_value",
      "typeName": "string_value",
      "address": "string_value",
      "divisionCode": "string_value",
      "institutionCode": "string_value",
      "unifiedSocialCreditCode": "string_value",
      "institutionLevelCode": "string_value",
      "isSync": true,
      "sourceType": 1,
      "zzdStatus": "string_value",
      "children": [
        "<SysDeptDO>"
      ],
      "parent": "<SysDeptDO>",
      "posJob": "string_value",
      "leaderName": "string_value",
      "streetName": "string_value",
      "hasChildren": true
    }
  ],
  "parent": {
    "beginTime": "string_value",
    "endTime": "string_value",
    "params": {},
    "deptId": 1,
    "parentId": 1,
    "parentName": "示例名称",
    "deptCode": "string_value",
    "parentCode": "string_value",
    "levelType": 1,
    "ancestors": "string_value",
    "deptName": "示例名称",
    "shortName": "string_value",
    "orderNum": 1,
    "userSortNum": 1,
    "leader": "string_value",
    "contact": "string_value",
    "position": "string_value",
    "phone": "13800138000",
    "email": "user@example.com",
    "status": true,
    "isCommandSystem": true,
    "delFlag": true,
    "createBy": "string_value",
    "createTime": "2024-01-01T00:00:00",
    "updateBy": "string_value",
    "updateTime": "2024-01-01T00:00:00",
    "typeCode": "string_value",
    "typeName": "string_value",
    "address": "string_value",
    "divisionCode": "string_value",
    "institutionCode": "string_value",
    "unifiedSocialCreditCode": "string_value",
    "institutionLevelCode": "string_value",
    "isSync": true,
    "sourceType": 1,
    "zzdStatus": "string_value",
    "children": [
      "<SysDeptDO>"
    ],
    "parent": "<SysDeptDO>",
    "posJob": "string_value",
    "leaderName": "string_value",
    "streetName": "string_value",
    "hasChildren": true
  },
  "posJob": "string_value",
  "leaderName": "string_value",
  "streetName": "string_value",
  "hasChildren": true
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 新增部门

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/dept/add` |
| OperationId | `add_5` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysDeptDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "deptId": 1,
  "parentId": 1,
  "parentName": "示例名称",
  "deptCode": "string_value",
  "parentCode": "string_value",
  "levelType": 1,
  "ancestors": "string_value",
  "deptName": "示例名称",
  "shortName": "string_value",
  "orderNum": 1,
  "userSortNum": 1,
  "leader": "string_value",
  "contact": "string_value",
  "position": "string_value",
  "phone": "13800138000",
  "email": "user@example.com",
  "status": true,
  "isCommandSystem": true,
  "delFlag": true,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "typeCode": "string_value",
  "typeName": "string_value",
  "address": "string_value",
  "divisionCode": "string_value",
  "institutionCode": "string_value",
  "unifiedSocialCreditCode": "string_value",
  "institutionLevelCode": "string_value",
  "isSync": true,
  "sourceType": 1,
  "zzdStatus": "string_value",
  "children": [
    {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "deptId": 1,
      "parentId": 1,
      "parentName": "示例名称",
      "deptCode": "string_value",
      "parentCode": "string_value",
      "levelType": 1,
      "ancestors": "string_value",
      "deptName": "示例名称",
      "shortName": "string_value",
      "orderNum": 1,
      "userSortNum": 1,
      "leader": "string_value",
      "contact": "string_value",
      "position": "string_value",
      "phone": "13800138000",
      "email": "user@example.com",
      "status": true,
      "isCommandSystem": true,
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "typeCode": "string_value",
      "typeName": "string_value",
      "address": "string_value",
      "divisionCode": "string_value",
      "institutionCode": "string_value",
      "unifiedSocialCreditCode": "string_value",
      "institutionLevelCode": "string_value",
      "isSync": true,
      "sourceType": 1,
      "zzdStatus": "string_value",
      "children": [
        "<SysDeptDO>"
      ],
      "parent": "<SysDeptDO>",
      "posJob": "string_value",
      "leaderName": "string_value",
      "streetName": "string_value",
      "hasChildren": true
    }
  ],
  "parent": {
    "beginTime": "string_value",
    "endTime": "string_value",
    "params": {},
    "deptId": 1,
    "parentId": 1,
    "parentName": "示例名称",
    "deptCode": "string_value",
    "parentCode": "string_value",
    "levelType": 1,
    "ancestors": "string_value",
    "deptName": "示例名称",
    "shortName": "string_value",
    "orderNum": 1,
    "userSortNum": 1,
    "leader": "string_value",
    "contact": "string_value",
    "position": "string_value",
    "phone": "13800138000",
    "email": "user@example.com",
    "status": true,
    "isCommandSystem": true,
    "delFlag": true,
    "createBy": "string_value",
    "createTime": "2024-01-01T00:00:00",
    "updateBy": "string_value",
    "updateTime": "2024-01-01T00:00:00",
    "typeCode": "string_value",
    "typeName": "string_value",
    "address": "string_value",
    "divisionCode": "string_value",
    "institutionCode": "string_value",
    "unifiedSocialCreditCode": "string_value",
    "institutionLevelCode": "string_value",
    "isSync": true,
    "sourceType": 1,
    "zzdStatus": "string_value",
    "children": [
      "<SysDeptDO>"
    ],
    "parent": "<SysDeptDO>",
    "posJob": "string_value",
    "leaderName": "string_value",
    "streetName": "string_value",
    "hasChildren": true
  },
  "posJob": "string_value",
  "leaderName": "string_value",
  "streetName": "string_value",
  "hasChildren": true
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 根据部门id查询本部门和所有上级部门

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dept/selectSelfAndParent` |
| OperationId | `selectSelfAndParent` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `deptId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseSysDeptDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "deptId": 1,
      "parentId": 1,
      "parentName": "示例名称",
      "deptCode": "string_value",
      "parentCode": "string_value",
      "levelType": 1,
      "ancestors": "string_value",
      "deptName": "示例名称",
      "shortName": "string_value",
      "orderNum": 1,
      "userSortNum": 1,
      "leader": "string_value",
      "contact": "string_value",
      "position": "string_value",
      "phone": "13800138000",
      "email": "user@example.com",
      "status": true,
      "isCommandSystem": true,
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "typeCode": "string_value",
      "typeName": "string_value",
      "address": "string_value",
      "divisionCode": "string_value",
      "institutionCode": "string_value",
      "unifiedSocialCreditCode": "string_value",
      "institutionLevelCode": "string_value",
      "isSync": true,
      "sourceType": 1,
      "zzdStatus": "string_value",
      "children": [
        "<SysDeptDO>"
      ],
      "parent": "<SysDeptDO>",
      "posJob": "string_value",
      "leaderName": "string_value",
      "streetName": "string_value",
      "hasChildren": true
    }
  }
  ```

---

#### 根据部门id查询本部门和所有上级部门

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dept/selectSelfAndParentIds` |
| OperationId | `selectSelfAndParentIds` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `deptId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListLong`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      1
    ]
  }
  ```

---

#### 根据部门id查询所有的子部门

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dept/selectAllChildrenDeptList` |
| OperationId | `selectAllChildrenDeptList` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `deptId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysDeptDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "deptId": 1,
        "parentId": 1,
        "parentName": "示例名称",
        "deptCode": "string_value",
        "parentCode": "string_value",
        "levelType": 1,
        "ancestors": "string_value",
        "deptName": "示例名称",
        "shortName": "string_value",
        "orderNum": 1,
        "userSortNum": 1,
        "leader": "string_value",
        "contact": "string_value",
        "position": "string_value",
        "phone": "13800138000",
        "email": "user@example.com",
        "status": true,
        "isCommandSystem": true,
        "delFlag": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "typeCode": "string_value",
        "typeName": "string_value",
        "address": "string_value",
        "divisionCode": "string_value",
        "institutionCode": "string_value",
        "unifiedSocialCreditCode": "string_value",
        "institutionLevelCode": "string_value",
        "isSync": true,
        "sourceType": 1,
        "zzdStatus": "string_value",
        "children": [
          "<SysDeptDO>"
        ],
        "parent": "<SysDeptDO>",
        "posJob": "string_value",
        "leaderName": "string_value",
        "streetName": "string_value",
        "hasChildren": true
      }
    ]
  }
  ```

---

#### 加载对应角色部门列表树

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dept/roleDeptTreeSelect` |
| OperationId | `roleDeptTreeSelect_1` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `roleId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseJSONObject`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "empty": true,
      "innerMap": {}
    }
  }
  ```

---

#### 删除部门

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dept/remove` |
| OperationId | `remove_5` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `deptId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 查询当前用户所在县级/乡镇级指挥体系

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dept/queryCommandSystem` |
| OperationId | `queryCommandSystem` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `pageNum` | query | integer(int32) | 否 |  |
| `pageSize` | query | integer(int32) | 否 |  |
| `orderByColumn` | query | string | 否 |  |
| `asc` | query | string | 否 |  |
| `deptId` | query | string | 否 | 部门id |
| `parentId` | query | string | 是 | 父部门id |
| `parentName` | query | string | 否 | 父部门名称 |
| `deptCode` | query | string | 否 | 部门编号 |
| `parentCode` | query | string | 否 |  |
| `levelType` | query | string | 否 | 部门级别：1-县级 2-乡镇级 3-县级部门 4-乡镇部门 |
| `ancestors` | query | string | 否 | 祖级列表 |
| `deptName` | query | string | 是 | 部门名称 |
| `shortName` | query | string | 否 | 简称 |
| `orderNum` | query | string | 否 | 显示顺序 |
| `userSortNum` | query | string | 否 | 某用户在部门内的排序 |
| `leader` | query | string | 否 | 负责人 |
| `contact` | query | string | 否 |  |
| `position` | query | string | 否 |  |
| `phone` | query | string | 否 | 联系电话 |
| `email` | query | string | 否 | 邮箱 |
| `status` | query | string | 否 | 部门状态（1正常 0停用） |
| `isCommandSystem` | query | string | 否 | 是否显示指挥体系 |
| `delFlag` | query | string | 否 | 删除标志（0代表存在1代表删除） |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 更新者 |
| `updateTime` | query | string | 否 | 更新时间 |
| `typeCode` | query | string | 否 |  |
| `typeName` | query | string | 否 |  |
| `address` | query | string | 否 |  |
| `divisionCode` | query | string | 否 |  |
| `institutionCode` | query | string | 否 |  |
| `unifiedSocialCreditCode` | query | string | 否 |  |
| `institutionLevelCode` | query | string | 否 |  |
| `isSync` | query | boolean | 否 |  |
| `sourceType` | query | integer(int32) | 否 |  |
| `zzdStatus` | query | string | 否 |  |
| `children` | query | array<`SysDeptDO`> | 否 |  |
| `posJob` | query | string | 否 |  |
| `leaderName` | query | string | 否 |  |
| `streetName` | query | string | 否 |  |
| `hasChildren` | query | boolean | 否 |  |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseIPageSysDeptDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "size": 1,
      "current": 1,
      "records": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "deptId": "...",
          "parentId": "...",
          "parentName": "...",
          "deptCode": "...",
          "parentCode": "...",
          "levelType": "...",
          "ancestors": "...",
          "deptName": "...",
          "shortName": "...",
          "orderNum": "...",
          "userSortNum": "...",
          "leader": "...",
          "contact": "...",
          "position": "...",
          "phone": "...",
          "email": "...",
          "status": "...",
          "isCommandSystem": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "typeCode": "...",
          "typeName": "...",
          "address": "...",
          "divisionCode": "...",
          "institutionCode": "...",
          "unifiedSocialCreditCode": "...",
          "institutionLevelCode": "...",
          "isSync": "...",
          "sourceType": "...",
          "zzdStatus": "...",
          "children": "...",
          "parent": "...",
          "posJob": "...",
          "leaderName": "...",
          "streetName": "...",
          "hasChildren": "..."
        }
      ],
      "total": 1,
      "pages": 1
    }
  }
  ```

---

#### 根据上一次查询时间增量查询部门列表

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dept/queryByLastTime` |
| OperationId | `queryByLastTime` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `tenantId` | query | string | 是 | 租户ID |
| `lastTime` | query | string | 是 | 上次查询时间 |
| `pageNum` | query | string | 是 | 页码 |
| `pageSize` | query | string | 是 | 每页大小 |
| `sign` | query | string | 是 | 签名 |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseIPageSysDeptDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "size": 1,
      "current": 1,
      "records": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "deptId": "...",
          "parentId": "...",
          "parentName": "...",
          "deptCode": "...",
          "parentCode": "...",
          "levelType": "...",
          "ancestors": "...",
          "deptName": "...",
          "shortName": "...",
          "orderNum": "...",
          "userSortNum": "...",
          "leader": "...",
          "contact": "...",
          "position": "...",
          "phone": "...",
          "email": "...",
          "status": "...",
          "isCommandSystem": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "typeCode": "...",
          "typeName": "...",
          "address": "...",
          "divisionCode": "...",
          "institutionCode": "...",
          "unifiedSocialCreditCode": "...",
          "institutionLevelCode": "...",
          "isSync": "...",
          "sourceType": "...",
          "zzdStatus": "...",
          "children": "...",
          "parent": "...",
          "posJob": "...",
          "leaderName": "...",
          "streetName": "...",
          "hasChildren": "..."
        }
      ],
      "total": 1,
      "pages": 1
    }
  }
  ```

---

#### 获取我的部门列表

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dept/myList` |
| OperationId | `myList` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `deptId` | query | string | 否 | 部门id |
| `parentId` | query | string | 是 | 父部门id |
| `parentName` | query | string | 否 | 父部门名称 |
| `deptCode` | query | string | 否 | 部门编号 |
| `parentCode` | query | string | 否 |  |
| `levelType` | query | string | 否 | 部门级别：1-县级 2-乡镇级 3-县级部门 4-乡镇部门 |
| `ancestors` | query | string | 否 | 祖级列表 |
| `deptName` | query | string | 是 | 部门名称 |
| `shortName` | query | string | 否 | 简称 |
| `orderNum` | query | string | 否 | 显示顺序 |
| `userSortNum` | query | string | 否 | 某用户在部门内的排序 |
| `leader` | query | string | 否 | 负责人 |
| `contact` | query | string | 否 |  |
| `position` | query | string | 否 |  |
| `phone` | query | string | 否 | 联系电话 |
| `email` | query | string | 否 | 邮箱 |
| `status` | query | string | 否 | 部门状态（1正常 0停用） |
| `isCommandSystem` | query | string | 否 | 是否显示指挥体系 |
| `delFlag` | query | string | 否 | 删除标志（0代表存在1代表删除） |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 更新者 |
| `updateTime` | query | string | 否 | 更新时间 |
| `typeCode` | query | string | 否 |  |
| `typeName` | query | string | 否 |  |
| `address` | query | string | 否 |  |
| `divisionCode` | query | string | 否 |  |
| `institutionCode` | query | string | 否 |  |
| `unifiedSocialCreditCode` | query | string | 否 |  |
| `institutionLevelCode` | query | string | 否 |  |
| `isSync` | query | boolean | 否 |  |
| `sourceType` | query | integer(int32) | 否 |  |
| `zzdStatus` | query | string | 否 |  |
| `children` | query | array<`SysDeptDO`> | 否 |  |
| `posJob` | query | string | 否 |  |
| `leaderName` | query | string | 否 |  |
| `streetName` | query | string | 否 |  |
| `hasChildren` | query | boolean | 否 |  |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysDeptDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "deptId": 1,
        "parentId": 1,
        "parentName": "示例名称",
        "deptCode": "string_value",
        "parentCode": "string_value",
        "levelType": 1,
        "ancestors": "string_value",
        "deptName": "示例名称",
        "shortName": "string_value",
        "orderNum": 1,
        "userSortNum": 1,
        "leader": "string_value",
        "contact": "string_value",
        "position": "string_value",
        "phone": "13800138000",
        "email": "user@example.com",
        "status": true,
        "isCommandSystem": true,
        "delFlag": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "typeCode": "string_value",
        "typeName": "string_value",
        "address": "string_value",
        "divisionCode": "string_value",
        "institutionCode": "string_value",
        "unifiedSocialCreditCode": "string_value",
        "institutionLevelCode": "string_value",
        "isSync": true,
        "sourceType": 1,
        "zzdStatus": "string_value",
        "children": [
          "<SysDeptDO>"
        ],
        "parent": "<SysDeptDO>",
        "posJob": "string_value",
        "leaderName": "string_value",
        "streetName": "string_value",
        "hasChildren": true
      }
    ]
  }
  ```

---

#### 获取我的部门树

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dept/myDeptTreeSelect` |
| OperationId | `myDeptTreeSelect` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `deptId` | query | string | 否 | 部门id |
| `parentId` | query | string | 是 | 父部门id |
| `parentName` | query | string | 否 | 父部门名称 |
| `deptCode` | query | string | 否 | 部门编号 |
| `parentCode` | query | string | 否 |  |
| `levelType` | query | string | 否 | 部门级别：1-县级 2-乡镇级 3-县级部门 4-乡镇部门 |
| `ancestors` | query | string | 否 | 祖级列表 |
| `deptName` | query | string | 是 | 部门名称 |
| `shortName` | query | string | 否 | 简称 |
| `orderNum` | query | string | 否 | 显示顺序 |
| `userSortNum` | query | string | 否 | 某用户在部门内的排序 |
| `leader` | query | string | 否 | 负责人 |
| `contact` | query | string | 否 |  |
| `position` | query | string | 否 |  |
| `phone` | query | string | 否 | 联系电话 |
| `email` | query | string | 否 | 邮箱 |
| `status` | query | string | 否 | 部门状态（1正常 0停用） |
| `isCommandSystem` | query | string | 否 | 是否显示指挥体系 |
| `delFlag` | query | string | 否 | 删除标志（0代表存在1代表删除） |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 更新者 |
| `updateTime` | query | string | 否 | 更新时间 |
| `typeCode` | query | string | 否 |  |
| `typeName` | query | string | 否 |  |
| `address` | query | string | 否 |  |
| `divisionCode` | query | string | 否 |  |
| `institutionCode` | query | string | 否 |  |
| `unifiedSocialCreditCode` | query | string | 否 |  |
| `institutionLevelCode` | query | string | 否 |  |
| `isSync` | query | boolean | 否 |  |
| `sourceType` | query | integer(int32) | 否 |  |
| `zzdStatus` | query | string | 否 |  |
| `children` | query | array<`SysDeptDO`> | 否 |  |
| `posJob` | query | string | 否 |  |
| `leaderName` | query | string | 否 |  |
| `streetName` | query | string | 否 |  |
| `hasChildren` | query | boolean | 否 |  |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysDeptDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "deptId": 1,
        "parentId": 1,
        "parentName": "示例名称",
        "deptCode": "string_value",
        "parentCode": "string_value",
        "levelType": 1,
        "ancestors": "string_value",
        "deptName": "示例名称",
        "shortName": "string_value",
        "orderNum": 1,
        "userSortNum": 1,
        "leader": "string_value",
        "contact": "string_value",
        "position": "string_value",
        "phone": "13800138000",
        "email": "user@example.com",
        "status": true,
        "isCommandSystem": true,
        "delFlag": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "typeCode": "string_value",
        "typeName": "string_value",
        "address": "string_value",
        "divisionCode": "string_value",
        "institutionCode": "string_value",
        "unifiedSocialCreditCode": "string_value",
        "institutionLevelCode": "string_value",
        "isSync": true,
        "sourceType": 1,
        "zzdStatus": "string_value",
        "children": [
          "<SysDeptDO>"
        ],
        "parent": "<SysDeptDO>",
        "posJob": "string_value",
        "leaderName": "string_value",
        "streetName": "string_value",
        "hasChildren": true
      }
    ]
  }
  ```

---

#### 获取部门列表

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dept/list` |
| OperationId | `list_5` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `deptId` | query | string | 否 | 部门id |
| `parentId` | query | string | 是 | 父部门id |
| `parentName` | query | string | 否 | 父部门名称 |
| `deptCode` | query | string | 否 | 部门编号 |
| `parentCode` | query | string | 否 |  |
| `levelType` | query | string | 否 | 部门级别：1-县级 2-乡镇级 3-县级部门 4-乡镇部门 |
| `ancestors` | query | string | 否 | 祖级列表 |
| `deptName` | query | string | 是 | 部门名称 |
| `shortName` | query | string | 否 | 简称 |
| `orderNum` | query | string | 否 | 显示顺序 |
| `userSortNum` | query | string | 否 | 某用户在部门内的排序 |
| `leader` | query | string | 否 | 负责人 |
| `contact` | query | string | 否 |  |
| `position` | query | string | 否 |  |
| `phone` | query | string | 否 | 联系电话 |
| `email` | query | string | 否 | 邮箱 |
| `status` | query | string | 否 | 部门状态（1正常 0停用） |
| `isCommandSystem` | query | string | 否 | 是否显示指挥体系 |
| `delFlag` | query | string | 否 | 删除标志（0代表存在1代表删除） |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 更新者 |
| `updateTime` | query | string | 否 | 更新时间 |
| `typeCode` | query | string | 否 |  |
| `typeName` | query | string | 否 |  |
| `address` | query | string | 否 |  |
| `divisionCode` | query | string | 否 |  |
| `institutionCode` | query | string | 否 |  |
| `unifiedSocialCreditCode` | query | string | 否 |  |
| `institutionLevelCode` | query | string | 否 |  |
| `isSync` | query | boolean | 否 |  |
| `sourceType` | query | integer(int32) | 否 |  |
| `zzdStatus` | query | string | 否 |  |
| `children` | query | array<`SysDeptDO`> | 否 |  |
| `posJob` | query | string | 否 |  |
| `leaderName` | query | string | 否 |  |
| `streetName` | query | string | 否 |  |
| `hasChildren` | query | boolean | 否 |  |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysDeptDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "deptId": 1,
        "parentId": 1,
        "parentName": "示例名称",
        "deptCode": "string_value",
        "parentCode": "string_value",
        "levelType": 1,
        "ancestors": "string_value",
        "deptName": "示例名称",
        "shortName": "string_value",
        "orderNum": 1,
        "userSortNum": 1,
        "leader": "string_value",
        "contact": "string_value",
        "position": "string_value",
        "phone": "13800138000",
        "email": "user@example.com",
        "status": true,
        "isCommandSystem": true,
        "delFlag": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "typeCode": "string_value",
        "typeName": "string_value",
        "address": "string_value",
        "divisionCode": "string_value",
        "institutionCode": "string_value",
        "unifiedSocialCreditCode": "string_value",
        "institutionLevelCode": "string_value",
        "isSync": true,
        "sourceType": 1,
        "zzdStatus": "string_value",
        "children": [
          "<SysDeptDO>"
        ],
        "parent": "<SysDeptDO>",
        "posJob": "string_value",
        "leaderName": "string_value",
        "streetName": "string_value",
        "hasChildren": true
      }
    ]
  }
  ```

---

#### 查询部门列表（排除节点）

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dept/list/exclude` |
| OperationId | `excludeChild` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `deptId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysDeptDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "deptId": 1,
        "parentId": 1,
        "parentName": "示例名称",
        "deptCode": "string_value",
        "parentCode": "string_value",
        "levelType": 1,
        "ancestors": "string_value",
        "deptName": "示例名称",
        "shortName": "string_value",
        "orderNum": 1,
        "userSortNum": 1,
        "leader": "string_value",
        "contact": "string_value",
        "position": "string_value",
        "phone": "13800138000",
        "email": "user@example.com",
        "status": true,
        "isCommandSystem": true,
        "delFlag": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "typeCode": "string_value",
        "typeName": "string_value",
        "address": "string_value",
        "divisionCode": "string_value",
        "institutionCode": "string_value",
        "unifiedSocialCreditCode": "string_value",
        "institutionLevelCode": "string_value",
        "isSync": true,
        "sourceType": 1,
        "zzdStatus": "string_value",
        "children": [
          "<SysDeptDO>"
        ],
        "parent": "<SysDeptDO>",
        "posJob": "string_value",
        "leaderName": "string_value",
        "streetName": "string_value",
        "hasChildren": true
      }
    ]
  }
  ```

---

#### 根据部门编号获取详细信息

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dept/info` |
| OperationId | `getInfo_6` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `deptId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseSysDeptDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "deptId": 1,
      "parentId": 1,
      "parentName": "示例名称",
      "deptCode": "string_value",
      "parentCode": "string_value",
      "levelType": 1,
      "ancestors": "string_value",
      "deptName": "示例名称",
      "shortName": "string_value",
      "orderNum": 1,
      "userSortNum": 1,
      "leader": "string_value",
      "contact": "string_value",
      "position": "string_value",
      "phone": "13800138000",
      "email": "user@example.com",
      "status": true,
      "isCommandSystem": true,
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "typeCode": "string_value",
      "typeName": "string_value",
      "address": "string_value",
      "divisionCode": "string_value",
      "institutionCode": "string_value",
      "unifiedSocialCreditCode": "string_value",
      "institutionLevelCode": "string_value",
      "isSync": true,
      "sourceType": 1,
      "zzdStatus": "string_value",
      "children": [
        "<SysDeptDO>"
      ],
      "parent": "<SysDeptDO>",
      "posJob": "string_value",
      "leaderName": "string_value",
      "streetName": "string_value",
      "hasChildren": true
    }
  }
  ```

---

#### 获取当前部门的所有用户id

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dept/getUseridsBydeptIds` |
| OperationId | `getUseridsBydeptIds` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `deptIds` | query | string | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListLong`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      1
    ]
  }
  ```

---

#### 获取当前用户的县级/乡镇级组织

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dept/getMyCountyOrTown` |
| OperationId | `getMyCountyOrTown` |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseSysDeptDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "deptId": 1,
      "parentId": 1,
      "parentName": "示例名称",
      "deptCode": "string_value",
      "parentCode": "string_value",
      "levelType": 1,
      "ancestors": "string_value",
      "deptName": "示例名称",
      "shortName": "string_value",
      "orderNum": 1,
      "userSortNum": 1,
      "leader": "string_value",
      "contact": "string_value",
      "position": "string_value",
      "phone": "13800138000",
      "email": "user@example.com",
      "status": true,
      "isCommandSystem": true,
      "delFlag": true,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "typeCode": "string_value",
      "typeName": "string_value",
      "address": "string_value",
      "divisionCode": "string_value",
      "institutionCode": "string_value",
      "unifiedSocialCreditCode": "string_value",
      "institutionLevelCode": "string_value",
      "isSync": true,
      "sourceType": 1,
      "zzdStatus": "string_value",
      "children": [
        "<SysDeptDO>"
      ],
      "parent": "<SysDeptDO>",
      "posJob": "string_value",
      "leaderName": "string_value",
      "streetName": "string_value",
      "hasChildren": true
    }
  }
  ```

---

#### 获取指定部门树列表

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dept/getDeptTreeByDeptId` |
| OperationId | `getDeptTreeByDeptId` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `deptId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysDeptDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "deptId": 1,
        "parentId": 1,
        "parentName": "示例名称",
        "deptCode": "string_value",
        "parentCode": "string_value",
        "levelType": 1,
        "ancestors": "string_value",
        "deptName": "示例名称",
        "shortName": "string_value",
        "orderNum": 1,
        "userSortNum": 1,
        "leader": "string_value",
        "contact": "string_value",
        "position": "string_value",
        "phone": "13800138000",
        "email": "user@example.com",
        "status": true,
        "isCommandSystem": true,
        "delFlag": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "typeCode": "string_value",
        "typeName": "string_value",
        "address": "string_value",
        "divisionCode": "string_value",
        "institutionCode": "string_value",
        "unifiedSocialCreditCode": "string_value",
        "institutionLevelCode": "string_value",
        "isSync": true,
        "sourceType": 1,
        "zzdStatus": "string_value",
        "children": [
          "<SysDeptDO>"
        ],
        "parent": "<SysDeptDO>",
        "posJob": "string_value",
        "leaderName": "string_value",
        "streetName": "string_value",
        "hasChildren": true
      }
    ]
  }
  ```

---

#### 根据上级部门id查询下级部门

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dept/getDeptByParentId` |
| OperationId | `getDeptByParentId` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `parentId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysDeptDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "deptId": 1,
        "parentId": 1,
        "parentName": "示例名称",
        "deptCode": "string_value",
        "parentCode": "string_value",
        "levelType": 1,
        "ancestors": "string_value",
        "deptName": "示例名称",
        "shortName": "string_value",
        "orderNum": 1,
        "userSortNum": 1,
        "leader": "string_value",
        "contact": "string_value",
        "position": "string_value",
        "phone": "13800138000",
        "email": "user@example.com",
        "status": true,
        "isCommandSystem": true,
        "delFlag": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "typeCode": "string_value",
        "typeName": "string_value",
        "address": "string_value",
        "divisionCode": "string_value",
        "institutionCode": "string_value",
        "unifiedSocialCreditCode": "string_value",
        "institutionLevelCode": "string_value",
        "isSync": true,
        "sourceType": 1,
        "zzdStatus": "string_value",
        "children": [
          "<SysDeptDO>"
        ],
        "parent": "<SysDeptDO>",
        "posJob": "string_value",
        "leaderName": "string_value",
        "streetName": "string_value",
        "hasChildren": true
      }
    ]
  }
  ```

---

#### 根据部门ids查询部门信息

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dept/getDeptByIds` |
| OperationId | `getDeptByIds` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `deptIds` | query | array<integer(int64)> | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysDeptDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "deptId": 1,
        "parentId": 1,
        "parentName": "示例名称",
        "deptCode": "string_value",
        "parentCode": "string_value",
        "levelType": 1,
        "ancestors": "string_value",
        "deptName": "示例名称",
        "shortName": "string_value",
        "orderNum": 1,
        "userSortNum": 1,
        "leader": "string_value",
        "contact": "string_value",
        "position": "string_value",
        "phone": "13800138000",
        "email": "user@example.com",
        "status": true,
        "isCommandSystem": true,
        "delFlag": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "typeCode": "string_value",
        "typeName": "string_value",
        "address": "string_value",
        "divisionCode": "string_value",
        "institutionCode": "string_value",
        "unifiedSocialCreditCode": "string_value",
        "institutionLevelCode": "string_value",
        "isSync": true,
        "sourceType": 1,
        "zzdStatus": "string_value",
        "children": [
          "<SysDeptDO>"
        ],
        "parent": "<SysDeptDO>",
        "posJob": "string_value",
        "leaderName": "string_value",
        "streetName": "string_value",
        "hasChildren": true
      }
    ]
  }
  ```

---

#### 根据parentId查询下级部门列表（懒加载）

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dept/getByParentId` |
| OperationId | `getByParentId` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `parentId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysDeptDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "deptId": 1,
        "parentId": 1,
        "parentName": "示例名称",
        "deptCode": "string_value",
        "parentCode": "string_value",
        "levelType": 1,
        "ancestors": "string_value",
        "deptName": "示例名称",
        "shortName": "string_value",
        "orderNum": 1,
        "userSortNum": 1,
        "leader": "string_value",
        "contact": "string_value",
        "position": "string_value",
        "phone": "13800138000",
        "email": "user@example.com",
        "status": true,
        "isCommandSystem": true,
        "delFlag": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "typeCode": "string_value",
        "typeName": "string_value",
        "address": "string_value",
        "divisionCode": "string_value",
        "institutionCode": "string_value",
        "unifiedSocialCreditCode": "string_value",
        "institutionLevelCode": "string_value",
        "isSync": true,
        "sourceType": 1,
        "zzdStatus": "string_value",
        "children": [
          "<SysDeptDO>"
        ],
        "parent": "<SysDeptDO>",
        "posJob": "string_value",
        "leaderName": "string_value",
        "streetName": "string_value",
        "hasChildren": true
      }
    ]
  }
  ```

---

#### 根据部门ID查询通讯录

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dept/getBookByDeptId` |
| OperationId | `getBookByDeptId` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `deptId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBookVO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "userList": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "userId": "...",
          "deptId": "...",
          "dept": "...",
          "deptList": "...",
          "authUserIds": "...",
          "authDeptIds": "...",
          "selectDeptId": "...",
          "userDeptList": "...",
          "account": "...",
          "userName": "...",
          "employeeCode": "...",
          "empPoliticalStatusCode": "...",
          "empJobLevelCode": "...",
          "empBudgetedPostCode": "...",
          "nickName": "...",
          "email": "...",
          "phoneNum": "...",
          "sex": "...",
          "avatar": "...",
          "password": "...",
          "passwordTime": "...",
          "smsCodeTime": "...",
          "loginFailCount": "...",
          "loginLockTime": "...",
          "isSmsLogin": "...",
          "status": "...",
          "isSync": "...",
          "sourceType": "...",
          "zzdStatus": "...",
          "loginIp": "...",
          "loginTime": "...",
          "expireTime": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "idCard": "...",
          "remark": "...",
          "dhUserCode": "...",
          "dhUserName": "...",
          "dhUserPassword": "...",
          "token": "...",
          "phoneNotNull": "...",
          "keyword": "...",
          "deptName": "...",
          "roles": "...",
          "apps": "...",
          "roleId": "...",
          "roleIds": "...",
          "postIds": "...",
          "roleNames": "...",
          "appPerms": "...",
          "permissions": "...",
          "postNames": "...",
          "posJob": "...",
          "deptNames": "...",
          "streetDeptId": "...",
          "streetCode": "...",
          "streetName": "...",
          "gpsX": "...",
          "gpsY": "...",
          "passwordRemind": "...",
          "admin": "..."
        }
      ],
      "childDeptList": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "deptId": "...",
          "parentId": "...",
          "parentName": "...",
          "deptCode": "...",
          "parentCode": "...",
          "levelType": "...",
          "ancestors": "...",
          "deptName": "...",
          "shortName": "...",
          "orderNum": "...",
          "userSortNum": "...",
          "leader": "...",
          "contact": "...",
          "position": "...",
          "phone": "...",
          "email": "...",
          "status": "...",
          "isCommandSystem": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "typeCode": "...",
          "typeName": "...",
          "address": "...",
          "divisionCode": "...",
          "institutionCode": "...",
          "unifiedSocialCreditCode": "...",
          "institutionLevelCode": "...",
          "isSync": "...",
          "sourceType": "...",
          "zzdStatus": "...",
          "children": "...",
          "parent": "...",
          "posJob": "...",
          "leaderName": "...",
          "streetName": "...",
          "hasChildren": "..."
        }
      ],
      "parentDeptList": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "deptId": "...",
          "parentId": "...",
          "parentName": "...",
          "deptCode": "...",
          "parentCode": "...",
          "levelType": "...",
          "ancestors": "...",
          "deptName": "...",
          "shortName": "...",
          "orderNum": "...",
          "userSortNum": "...",
          "leader": "...",
          "contact": "...",
          "position": "...",
          "phone": "...",
          "email": "...",
          "status": "...",
          "isCommandSystem": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "typeCode": "...",
          "typeName": "...",
          "address": "...",
          "divisionCode": "...",
          "institutionCode": "...",
          "unifiedSocialCreditCode": "...",
          "institutionLevelCode": "...",
          "isSync": "...",
          "sourceType": "...",
          "zzdStatus": "...",
          "children": "...",
          "parent": "...",
          "posJob": "...",
          "leaderName": "...",
          "streetName": "...",
          "hasChildren": "..."
        }
      ],
      "dept": {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "deptId": 1,
        "parentId": 1,
        "parentName": "示例名称",
        "deptCode": "string_value",
        "parentCode": "string_value",
        "levelType": 1,
        "ancestors": "string_value",
        "deptName": "示例名称",
        "shortName": "string_value",
        "orderNum": 1,
        "userSortNum": 1,
        "leader": "string_value",
        "contact": "string_value",
        "position": "string_value",
        "phone": "13800138000",
        "email": "user@example.com",
        "status": true,
        "isCommandSystem": true,
        "delFlag": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "typeCode": "string_value",
        "typeName": "string_value",
        "address": "string_value",
        "divisionCode": "string_value",
        "institutionCode": "string_value",
        "unifiedSocialCreditCode": "string_value",
        "institutionLevelCode": "string_value",
        "isSync": true,
        "sourceType": 1,
        "zzdStatus": "string_value",
        "children": [
          "..."
        ],
        "parent": "<SysDeptDO>",
        "posJob": "string_value",
        "leaderName": "string_value",
        "streetName": "string_value",
        "hasChildren": true
      }
    }
  }
  ```

---

#### 获取当前部门和子部门的所有用户id

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dept/getAuthUserIds` |
| OperationId | `getAuthUserIds` |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListLong`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      1
    ]
  }
  ```

---

#### 获取当前部门和子部门的所有用户id

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dept/getAuthDeptIds` |
| OperationId | `getAuthDeptIds` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `selectDept` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListLong`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      1
    ]
  }
  ```

---

#### 获取部门树

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/dept/deptTreeSelect` |
| OperationId | `deptTreeSelect` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `deptId` | query | string | 否 | 部门id |
| `parentId` | query | string | 是 | 父部门id |
| `parentName` | query | string | 否 | 父部门名称 |
| `deptCode` | query | string | 否 | 部门编号 |
| `parentCode` | query | string | 否 |  |
| `levelType` | query | string | 否 | 部门级别：1-县级 2-乡镇级 3-县级部门 4-乡镇部门 |
| `ancestors` | query | string | 否 | 祖级列表 |
| `deptName` | query | string | 是 | 部门名称 |
| `shortName` | query | string | 否 | 简称 |
| `orderNum` | query | string | 否 | 显示顺序 |
| `userSortNum` | query | string | 否 | 某用户在部门内的排序 |
| `leader` | query | string | 否 | 负责人 |
| `contact` | query | string | 否 |  |
| `position` | query | string | 否 |  |
| `phone` | query | string | 否 | 联系电话 |
| `email` | query | string | 否 | 邮箱 |
| `status` | query | string | 否 | 部门状态（1正常 0停用） |
| `isCommandSystem` | query | string | 否 | 是否显示指挥体系 |
| `delFlag` | query | string | 否 | 删除标志（0代表存在1代表删除） |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 更新者 |
| `updateTime` | query | string | 否 | 更新时间 |
| `typeCode` | query | string | 否 |  |
| `typeName` | query | string | 否 |  |
| `address` | query | string | 否 |  |
| `divisionCode` | query | string | 否 |  |
| `institutionCode` | query | string | 否 |  |
| `unifiedSocialCreditCode` | query | string | 否 |  |
| `institutionLevelCode` | query | string | 否 |  |
| `isSync` | query | boolean | 否 |  |
| `sourceType` | query | integer(int32) | 否 |  |
| `zzdStatus` | query | string | 否 |  |
| `children` | query | array<`SysDeptDO`> | 否 |  |
| `posJob` | query | string | 否 |  |
| `leaderName` | query | string | 否 |  |
| `streetName` | query | string | 否 |  |
| `hasChildren` | query | boolean | 否 |  |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysDeptDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "deptId": 1,
        "parentId": 1,
        "parentName": "示例名称",
        "deptCode": "string_value",
        "parentCode": "string_value",
        "levelType": 1,
        "ancestors": "string_value",
        "deptName": "示例名称",
        "shortName": "string_value",
        "orderNum": 1,
        "userSortNum": 1,
        "leader": "string_value",
        "contact": "string_value",
        "position": "string_value",
        "phone": "13800138000",
        "email": "user@example.com",
        "status": true,
        "isCommandSystem": true,
        "delFlag": true,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "typeCode": "string_value",
        "typeName": "string_value",
        "address": "string_value",
        "divisionCode": "string_value",
        "institutionCode": "string_value",
        "unifiedSocialCreditCode": "string_value",
        "institutionLevelCode": "string_value",
        "isSync": true,
        "sourceType": 1,
        "zzdStatus": "string_value",
        "children": [
          "<SysDeptDO>"
        ],
        "parent": "<SysDeptDO>",
        "posJob": "string_value",
        "leaderName": "string_value",
        "streetName": "string_value",
        "hasChildren": true
      }
    ]
  }
  ```

---

### 参数配置表接口

#### 修改系统配置

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/config/update` |
| OperationId | `updateSystemConfig` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysConfigDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "configId": 1,
  "configName": "示例名称",
  "configKey": "string_value",
  "configValue": "string_value",
  "configType": "string_value",
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "remark": "string_value"
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 添加系统配置

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/config/add` |
| OperationId | `addSystemConfig` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysConfigDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "configId": 1,
  "configName": "示例名称",
  "configKey": "string_value",
  "configValue": "string_value",
  "configType": "string_value",
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "remark": "string_value"
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 根据id批量删除配置信息

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/config/remove` |
| OperationId | `removeSystemConfig` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `ids` | query | array<integer(int64)> | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 获取配置列表

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/config/page` |
| OperationId | `getSystemConfigPage` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `configId` | query | string | 否 | 参数主键 |
| `configName` | query | string | 否 | 参数名称 |
| `configKey` | query | string | 否 | 参数键名 |
| `configValue` | query | string | 否 | 参数键值 |
| `configType` | query | string | 否 | 系统内置（Y是 N否） |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 更新者 |
| `updateTime` | query | string | 否 | 更新时间 |
| `remark` | query | string | 否 | 备注 |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |
| `pageNum` | query | integer(int32) | 否 |  |
| `pageSize` | query | integer(int32) | 否 |  |
| `orderByColumn` | query | string | 否 |  |
| `asc` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseIPageSysConfigDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "size": 1,
      "current": 1,
      "records": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "configId": "...",
          "configName": "...",
          "configKey": "...",
          "configValue": "...",
          "configType": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "remark": "..."
        }
      ],
      "total": 1,
      "pages": 1
    }
  }
  ```

---

#### 获取配置信息

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/config/info` |
| OperationId | `getSystemConfig` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `configKey` | query | string | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseSysConfigDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "configId": 1,
      "configName": "示例名称",
      "configKey": "string_value",
      "configValue": "string_value",
      "configType": "string_value",
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "remark": "string_value"
    }
  }
  ```

---

#### 根据键名查询参数配置信息

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/config/get-by-key` |
| OperationId | `getConfigKey` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `configKey` | query | string | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseString`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": "string_value"
  }
  ```

---

#### 根据键名查询参数配置信息

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/config/get-by-feign` |
| OperationId | `getByFeign` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `configKey` | query | string | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseString`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": "string_value"
  }
  ```

---

### 通用接口

#### 上传文件到OSS

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/base/uploadFile` |
| OperationId | `uploadFile` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `path` | query | string | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseString`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": "string_value"
  }
  ```

---

### 全国地区表接口

#### 管理员修改地区配置

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/area/update` |
| OperationId | `updateArea` |

**请求体：**

- Content-Type: `application/json`
- Schema: `AreaDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "id": 1,
  "areaCode": 1,
  "areaCodeFormat": 1,
  "areaLevel": 1,
  "areaName": "string_value",
  "cityCode": "CODE001",
  "center": "string_value",
  "parentId": 1,
  "updateTime": "2024-01-01T00:00:00",
  "isEnable": true,
  "firstPy": "string_value",
  "shortPy": "string_value",
  "fullPy": "string_value",
  "treePath": "string_value"
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 根据经纬度逆地理编码，获取省和城市(百度地图)

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/area/reverseGeoCoding` |
| OperationId | `reverseGeoCoding` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `lng` | query | number(double) | 是 |  |
| `lat` | query | number(double) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseMyLocationVO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "longitude": 1.0,
      "latitude": 1.0,
      "province": "string_value",
      "city": "string_value",
      "district": "string_value",
      "provinceId": 1,
      "cityId": 1,
      "districtId": 1,
      "address": "http://example.com",
      "town": "string_value",
      "street": "string_value",
      "streetNumber": "string_value"
    }
  }
  ```

---

#### 根据详细地址， 解析出省市区和ID

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/area/reverseByAddress` |
| OperationId | `reverseByAddress` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `address` | query | string | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseMyLocationVO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "longitude": 1.0,
      "latitude": 1.0,
      "province": "string_value",
      "city": "string_value",
      "district": "string_value",
      "provinceId": 1,
      "cityId": 1,
      "districtId": 1,
      "address": "http://example.com",
      "town": "string_value",
      "street": "string_value",
      "streetNumber": "string_value"
    }
  }
  ```

---

#### 地区下拉数据源列表

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/area/list` |
| OperationId | `areaSelect` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `id` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListAreaDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "id": 1,
        "areaCode": 1,
        "areaCodeFormat": 1,
        "areaLevel": 1,
        "areaName": "string_value",
        "cityCode": "CODE001",
        "center": "string_value",
        "parentId": 1,
        "updateTime": "2024-01-01T00:00:00",
        "isEnable": true,
        "firstPy": "string_value",
        "shortPy": "string_value",
        "fullPy": "string_value",
        "treePath": "string_value"
      }
    ]
  }
  ```

---

#### 根据IP转换地址

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/area/ip2Location` |
| OperationId | `ip2Location` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `ip` | query | string | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseMyLocationVO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "longitude": 1.0,
      "latitude": 1.0,
      "province": "string_value",
      "city": "string_value",
      "district": "string_value",
      "provinceId": 1,
      "cityId": 1,
      "districtId": 1,
      "address": "http://example.com",
      "town": "string_value",
      "street": "string_value",
      "streetNumber": "string_value"
    }
  }
  ```

---

### 应用表控制层

#### 修改应用

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/app/update` |
| OperationId | `updateApp` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysAppDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "appId": 1,
  "appName": "示例名称",
  "type": 1,
  "types": [
    1
  ],
  "appKey": "string_value",
  "appSecret": "string_value",
  "pcUrl": "http://example.com",
  "iconUrl": "string_value",
  "sort": 1,
  "status": 1,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "remark": "string_value"
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 上架或下架

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/app/updateStatus/{appId}` |
| OperationId | `updateStatus` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `appId` | path | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 第三方应用请求AccessToken

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/app/token` |
| OperationId | `token` |

**请求体：**

- Content-Type: `application/json`
- Schema: `AppTokenRequest`

**请求示例：**
```json
{
  "appKey": "string_value",
  "appSecret": "string_value"
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseAccessTokenVO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "accessToken": "string_value",
      "expiresIn": 1,
      "iotToken": "string_value"
    }
  }
  ```

---

#### 重置密钥

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/app/resetSecret/{appId}` |
| OperationId | `resetSecret` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `appId` | path | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 新增应用

| 属性 | 值 |
|------|------|
| 请求方法 | `POST` |
| 请求路径 | `/system/app/insert` |
| OperationId | `insertApp` |

**请求体：**

- Content-Type: `application/json`
- Schema: `SysAppDO`

**请求示例：**
```json
{
  "beginTime": "string_value",
  "endTime": "string_value",
  "params": {},
  "appId": 1,
  "appName": "示例名称",
  "type": 1,
  "types": [
    1
  ],
  "appKey": "string_value",
  "appSecret": "string_value",
  "pcUrl": "http://example.com",
  "iconUrl": "string_value",
  "sort": 1,
  "status": 1,
  "createBy": "string_value",
  "createTime": "2024-01-01T00:00:00",
  "updateBy": "string_value",
  "updateTime": "2024-01-01T00:00:00",
  "remark": "string_value"
}
```

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---

#### 查询角色已选中的appKey集合

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/app/selectCheckedApp` |
| OperationId | `selectCheckedApp` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `roleId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListString`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      "string_value"
    ]
  }
  ```

---

#### 应用集合{屏蔽第三方应用}

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/app/list` |
| OperationId | `selectList` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `appId` | query | string | 否 | 应用ID |
| `appName` | query | string | 否 | 应用名称 |
| `type` | query | string | 否 | 应用类型{1-内部子系统;2-外部子系统;3-第三方系统} |
| `types` | query | string | 否 | 查询多个类型 |
| `appKey` | query | string | 否 | app key |
| `appSecret` | query | string | 否 | 应用秘钥 |
| `pcUrl` | query | string | 否 | 应用地址 |
| `iconUrl` | query | string | 否 | 应用图标 |
| `sort` | query | string | 否 | 排序 |
| `status` | query | string | 否 | 应用状态:{1-上架;2-下架} |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 最后修改人 |
| `updateTime` | query | string | 否 | 最后修改时间 |
| `remark` | query | string | 否 | 备注 |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseListSysAppDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": [
      {
        "beginTime": "string_value",
        "endTime": "string_value",
        "params": {},
        "appId": 1,
        "appName": "示例名称",
        "type": 1,
        "types": [
          1
        ],
        "appKey": "string_value",
        "appSecret": "string_value",
        "pcUrl": "http://example.com",
        "iconUrl": "string_value",
        "sort": 1,
        "status": 1,
        "createBy": "string_value",
        "createTime": "2024-01-01T00:00:00",
        "updateBy": "string_value",
        "updateTime": "2024-01-01T00:00:00",
        "remark": "string_value"
      }
    ]
  }
  ```

---

#### 子系统获取用户角色关系集合{校验appToken}

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/app/getUserRoleList` |
| OperationId | `getUserRoleList` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `userId` | query | string | 否 | 用户ID |
| `roleId` | query | string | 否 | 角色ID |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseIPageSysUserRoleDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "size": 1,
      "current": 1,
      "records": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "userId": "...",
          "roleId": "..."
        }
      ],
      "total": 1,
      "pages": 1
    }
  }
  ```

---

#### 子系统获取用户信息集合{校验appToken}

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/app/getUserList` |
| OperationId | `getUserList` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `userId` | query | string | 否 | 用户ID |
| `deptId` | query | string | 是 | 部门ID |
| `dept.deptId` | query | string | 否 | 部门id |
| `dept.parentId` | query | string | 是 | 父部门id |
| `dept.parentName` | query | string | 否 | 父部门名称 |
| `dept.deptCode` | query | string | 否 | 部门编号 |
| `dept.parentCode` | query | string | 否 |  |
| `dept.levelType` | query | string | 否 | 部门级别：1-县级 2-乡镇级 3-县级部门 4-乡镇部门 |
| `dept.ancestors` | query | string | 否 | 祖级列表 |
| `dept.deptName` | query | string | 是 | 部门名称 |
| `dept.shortName` | query | string | 否 | 简称 |
| `dept.orderNum` | query | string | 否 | 显示顺序 |
| `dept.userSortNum` | query | string | 否 | 某用户在部门内的排序 |
| `dept.leader` | query | string | 否 | 负责人 |
| `dept.contact` | query | string | 否 |  |
| `dept.position` | query | string | 否 |  |
| `dept.phone` | query | string | 否 | 联系电话 |
| `dept.email` | query | string | 否 | 邮箱 |
| `dept.status` | query | string | 否 | 部门状态（1正常 0停用） |
| `dept.isCommandSystem` | query | string | 否 | 是否显示指挥体系 |
| `dept.delFlag` | query | string | 否 | 删除标志（0代表存在1代表删除） |
| `dept.createBy` | query | string | 否 | 创建者 |
| `dept.createTime` | query | string | 否 | 创建时间 |
| `dept.updateBy` | query | string | 否 | 更新者 |
| `dept.updateTime` | query | string | 否 | 更新时间 |
| `dept.typeCode` | query | string | 否 |  |
| `dept.typeName` | query | string | 否 |  |
| `dept.address` | query | string | 否 |  |
| `dept.divisionCode` | query | string | 否 |  |
| `dept.institutionCode` | query | string | 否 |  |
| `dept.unifiedSocialCreditCode` | query | string | 否 |  |
| `dept.institutionLevelCode` | query | string | 否 |  |
| `dept.isSync` | query | boolean | 否 |  |
| `dept.sourceType` | query | integer(int32) | 否 |  |
| `dept.zzdStatus` | query | string | 否 |  |
| `dept.children` | query | array<`SysDeptDO`> | 否 |  |
| `dept.posJob` | query | string | 否 |  |
| `dept.leaderName` | query | string | 否 |  |
| `dept.streetName` | query | string | 否 |  |
| `dept.hasChildren` | query | boolean | 否 |  |
| `dept.beginTime` | query | string | 否 |  |
| `dept.endTime` | query | string | 否 |  |
| `deptList` | query | string | 否 | 多个部门 |
| `authUserIds` | query | string | 否 | 当前授权的所有用户id |
| `authDeptIds` | query | string | 否 | 当前授权的所有部门id |
| `selectDeptId` | query | string | 否 | 当前选择部门id |
| `userDeptList` | query | string | 否 | 多个部门 |
| `account` | query | string | 是 | 用户账号 |
| `userName` | query | string | 是 | 用户名称 |
| `employeeCode` | query | string | 否 | 员工Code |
| `empPoliticalStatusCode` | query | string | 否 | 政治面貌，具体参见‘人员数据字典表’ |
| `empJobLevelCode` | query | string | 否 | 职级，具体参见‘人员数据字典表’ |
| `empBudgetedPostCode` | query | string | 否 | 编制，具体参见‘人员数据字典表’ |
| `nickName` | query | string | 是 | 昵称 |
| `email` | query | string | 否 | 用户邮箱 |
| `phoneNum` | query | string | 否 | 手机号码 |
| `sex` | query | string | 否 | 用户性别（0男 1女 2未知） |
| `avatar` | query | string | 否 | 头像地址 |
| `password` | query | string | 否 | 密码 |
| `passwordTime` | query | string | 否 | 上次设置密码时间 |
| `smsCodeTime` | query | string | 否 | 上次验证码登录时间 |
| `loginFailCount` | query | string | 否 | 登录失败次数计数 |
| `loginLockTime` | query | string | 否 | 登录失败锁定终止时间 |
| `isSmsLogin` | query | string | 否 | 是否需要验证码登录 |
| `status` | query | string | 是 | 帐号状态（1正常 0停用 2 注销） |
| `isSync` | query | boolean | 否 |  |
| `sourceType` | query | integer(int32) | 否 |  |
| `zzdStatus` | query | string | 否 |  |
| `loginIp` | query | string | 否 | 最后登陆IP |
| `loginTime` | query | string | 否 | 最后登陆时间 |
| `expireTime` | query | string(date-time) | 否 |  |
| `delFlag` | query | string | 否 | 删除标志：0-未删除，1-已删除 |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 更新者 |
| `updateTime` | query | string | 否 | 更新时间 |
| `idCard` | query | string | 否 | 身份证号 |
| `remark` | query | string | 否 | 备注 |
| `dhUserCode` | query | string | 否 | 大华用户编码 |
| `dhUserName` | query | string | 否 | 大华用户名 |
| `dhUserPassword` | query | string | 否 | 大华用户登录密码 |
| `token` | query | string | 否 |  |
| `phoneNotNull` | query | boolean | 否 |  |
| `keyword` | query | string | 否 |  |
| `deptName` | query | string | 否 |  |
| `roles` | query | array<`SysRoleDO`> | 否 |  |
| `apps` | query | array<`SysAppDO`> | 否 |  |
| `roleId` | query | integer(int64) | 否 |  |
| `roleIds` | query | array<integer(int64)> | 否 |  |
| `postIds` | query | array<integer(int64)> | 否 |  |
| `roleNames` | query | string | 否 |  |
| `permissions` | query | array<string> | 否 |  |
| `postNames` | query | string | 否 |  |
| `posJob` | query | string | 否 |  |
| `deptNames` | query | string | 否 |  |
| `streetDeptId` | query | integer(int64) | 否 |  |
| `streetCode` | query | string | 否 |  |
| `streetName` | query | string | 否 |  |
| `gpsX` | query | number(double) | 否 |  |
| `gpsY` | query | number(double) | 否 |  |
| `passwordRemind` | query | boolean | 否 |  |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseIPageSysUserDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "size": 1,
      "current": 1,
      "records": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "userId": "...",
          "deptId": "...",
          "dept": "...",
          "deptList": "...",
          "authUserIds": "...",
          "authDeptIds": "...",
          "selectDeptId": "...",
          "userDeptList": "...",
          "account": "...",
          "userName": "...",
          "employeeCode": "...",
          "empPoliticalStatusCode": "...",
          "empJobLevelCode": "...",
          "empBudgetedPostCode": "...",
          "nickName": "...",
          "email": "...",
          "phoneNum": "...",
          "sex": "...",
          "avatar": "...",
          "password": "...",
          "passwordTime": "...",
          "smsCodeTime": "...",
          "loginFailCount": "...",
          "loginLockTime": "...",
          "isSmsLogin": "...",
          "status": "...",
          "isSync": "...",
          "sourceType": "...",
          "zzdStatus": "...",
          "loginIp": "...",
          "loginTime": "...",
          "expireTime": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "idCard": "...",
          "remark": "...",
          "dhUserCode": "...",
          "dhUserName": "...",
          "dhUserPassword": "...",
          "token": "...",
          "phoneNotNull": "...",
          "keyword": "...",
          "deptName": "...",
          "roles": "...",
          "apps": "...",
          "roleId": "...",
          "roleIds": "...",
          "postIds": "...",
          "roleNames": "...",
          "appPerms": "...",
          "permissions": "...",
          "postNames": "...",
          "posJob": "...",
          "deptNames": "...",
          "streetDeptId": "...",
          "streetCode": "...",
          "streetName": "...",
          "gpsX": "...",
          "gpsY": "...",
          "passwordRemind": "...",
          "admin": "..."
        }
      ],
      "total": 1,
      "pages": 1
    }
  }
  ```

---

#### 子系统获取角色资源关系集合{校验appToken}

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/app/getRoleMenuList` |
| OperationId | `getRoleMenuList` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `roleId` | query | string | 否 | 角色ID |
| `menuId` | query | string | 否 | 菜单ID |
| `perms` | query | string | 否 | 权限标识 |
| `appKey` | query | string | 否 | 应用KEY |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseIPageSysRoleMenuDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "size": 1,
      "current": 1,
      "records": [
        {
          "roleId": "...",
          "menuId": "...",
          "perms": "...",
          "appKey": "..."
        }
      ],
      "total": 1,
      "pages": 1
    }
  }
  ```

---

#### 子系统获取角色信息集合{校验appToken}

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/app/getRoleList` |
| OperationId | `getRoleList` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `roleId` | query | string | 否 | 角色ID |
| `roleName` | query | string | 否 | 角色名称 |
| `roleGroup` | query | string | 否 | 角色组 |
| `roleKey` | query | string | 否 | 角色权限字符串 |
| `roleSort` | query | string | 否 | 显示顺序 |
| `dataScope` | query | string | 否 | 数据范围（1：全部数据权限 2：自定数据权限 3：本部门数据权限 4：本部门及以下数据权限） |
| `status` | query | string | 否 | 角色状态（1正常 0停用） |
| `delFlag` | query | string | 否 | 删除标志（0代表存在1代表删除） |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 更新者 |
| `updateTime` | query | string | 否 | 更新时间 |
| `remark` | query | string | 否 | 备注 |
| `isApprover` | query | string | 否 | 飞行任务审批权限 |
| `flag` | query | boolean | 否 |  |
| `appKeys` | query | string | 否 | 选中的应用 |
| `menuIds` | query | array<integer(int64)> | 否 |  |
| `deptIds` | query | array<integer(int64)> | 否 |  |
| `permissions` | query | array<string> | 否 |  |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseIPageSysRoleDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "size": 1,
      "current": 1,
      "records": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "roleId": "...",
          "roleName": "...",
          "roleGroup": "...",
          "roleKey": "...",
          "roleSort": "...",
          "dataScope": "...",
          "status": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "remark": "...",
          "isApprover": "...",
          "flag": "...",
          "appKeys": "...",
          "menuIds": "...",
          "deptIds": "...",
          "permissions": "...",
          "admin": "..."
        }
      ],
      "total": 1,
      "pages": 1
    }
  }
  ```

---

#### 子系统获取菜单信息集合{校验appToken}

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/app/getMenuList` |
| OperationId | `getMenuList` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `menuId` | query | string | 否 | 菜单ID |
| `menuName` | query | string | 否 | 菜单名称 |
| `perms` | query | string | 否 | 权限标识 |
| `parentId` | query | string | 否 | 父菜单ID |
| `parentPerms` | query | string | 否 | 父权限标识 |
| `orderNum` | query | string | 否 | 显示顺序 |
| `path` | query | string | 否 | 路由地址 |
| `component` | query | string | 否 | 组件路径 |
| `isFrame` | query | string | 否 | 是否为外链（1是 0否） |
| `menuType` | query | string | 否 | 菜单类型（M目录 C菜单 F按钮） |
| `visible` | query | string | 否 | 菜单状态（1显示 0隐藏） |
| `status` | query | string | 否 | 菜单状态（1正常 0停用） |
| `icon` | query | string | 否 | 菜单图标 |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 更新者 |
| `updateTime` | query | string | 否 | 更新时间 |
| `remark` | query | string | 否 | 备注 |
| `appKey` | query | string | 否 | 应用appKey |
| `query` | query | string | 否 | 路由参数 |
| `roleId` | query | string | 否 | 角色ID |
| `children` | query | array<`SysMenuDO`> | 否 |  |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseIPageSysMenuDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "size": 1,
      "current": 1,
      "records": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "menuId": "...",
          "menuName": "...",
          "perms": "...",
          "parentId": "...",
          "parentPerms": "...",
          "orderNum": "...",
          "path": "...",
          "component": "...",
          "isFrame": "...",
          "menuType": "...",
          "visible": "...",
          "status": "...",
          "icon": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "remark": "...",
          "appKey": "...",
          "query": "...",
          "roleId": "..."
        }
      ],
      "total": 1,
      "pages": 1
    }
  }
  ```

---

#### 子系统获取组织集合{校验appToken}

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/app/getDeptList` |
| OperationId | `getDeptList` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `deptId` | query | string | 否 | 部门id |
| `parentId` | query | string | 是 | 父部门id |
| `parentName` | query | string | 否 | 父部门名称 |
| `deptCode` | query | string | 否 | 部门编号 |
| `parentCode` | query | string | 否 |  |
| `levelType` | query | string | 否 | 部门级别：1-县级 2-乡镇级 3-县级部门 4-乡镇部门 |
| `ancestors` | query | string | 否 | 祖级列表 |
| `deptName` | query | string | 是 | 部门名称 |
| `shortName` | query | string | 否 | 简称 |
| `orderNum` | query | string | 否 | 显示顺序 |
| `userSortNum` | query | string | 否 | 某用户在部门内的排序 |
| `leader` | query | string | 否 | 负责人 |
| `contact` | query | string | 否 |  |
| `position` | query | string | 否 |  |
| `phone` | query | string | 否 | 联系电话 |
| `email` | query | string | 否 | 邮箱 |
| `status` | query | string | 否 | 部门状态（1正常 0停用） |
| `isCommandSystem` | query | string | 否 | 是否显示指挥体系 |
| `delFlag` | query | string | 否 | 删除标志（0代表存在1代表删除） |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 更新者 |
| `updateTime` | query | string | 否 | 更新时间 |
| `typeCode` | query | string | 否 |  |
| `typeName` | query | string | 否 |  |
| `address` | query | string | 否 |  |
| `divisionCode` | query | string | 否 |  |
| `institutionCode` | query | string | 否 |  |
| `unifiedSocialCreditCode` | query | string | 否 |  |
| `institutionLevelCode` | query | string | 否 |  |
| `isSync` | query | boolean | 否 |  |
| `sourceType` | query | integer(int32) | 否 |  |
| `zzdStatus` | query | string | 否 |  |
| `children` | query | array<`SysDeptDO`> | 否 |  |
| `posJob` | query | string | 否 |  |
| `leaderName` | query | string | 否 |  |
| `streetName` | query | string | 否 |  |
| `hasChildren` | query | boolean | 否 |  |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseIPageSysDeptDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "size": 1,
      "current": 1,
      "records": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "deptId": "...",
          "parentId": "...",
          "parentName": "...",
          "deptCode": "...",
          "parentCode": "...",
          "levelType": "...",
          "ancestors": "...",
          "deptName": "...",
          "shortName": "...",
          "orderNum": "...",
          "userSortNum": "...",
          "leader": "...",
          "contact": "...",
          "position": "...",
          "phone": "...",
          "email": "...",
          "status": "...",
          "isCommandSystem": "...",
          "delFlag": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "typeCode": "...",
          "typeName": "...",
          "address": "...",
          "divisionCode": "...",
          "institutionCode": "...",
          "unifiedSocialCreditCode": "...",
          "institutionLevelCode": "...",
          "isSync": "...",
          "sourceType": "...",
          "zzdStatus": "...",
          "children": "...",
          "parent": "...",
          "posJob": "...",
          "leaderName": "...",
          "streetName": "...",
          "hasChildren": "..."
        }
      ],
      "total": 1,
      "pages": 1
    }
  }
  ```

---

#### 应用集合

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/app/getAppList` |
| OperationId | `selectListByPage` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `appId` | query | string | 否 | 应用ID |
| `appName` | query | string | 否 | 应用名称 |
| `type` | query | string | 否 | 应用类型{1-内部子系统;2-外部子系统;3-第三方系统} |
| `types` | query | string | 否 | 查询多个类型 |
| `appKey` | query | string | 否 | app key |
| `appSecret` | query | string | 否 | 应用秘钥 |
| `pcUrl` | query | string | 否 | 应用地址 |
| `iconUrl` | query | string | 否 | 应用图标 |
| `sort` | query | string | 否 | 排序 |
| `status` | query | string | 否 | 应用状态:{1-上架;2-下架} |
| `createBy` | query | string | 否 | 创建者 |
| `createTime` | query | string | 否 | 创建时间 |
| `updateBy` | query | string | 否 | 最后修改人 |
| `updateTime` | query | string | 否 | 最后修改时间 |
| `remark` | query | string | 否 | 备注 |
| `beginTime` | query | string | 否 |  |
| `endTime` | query | string | 否 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseIPageSysAppDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "size": 1,
      "current": 1,
      "records": [
        {
          "beginTime": "...",
          "endTime": "...",
          "params": "...",
          "appId": "...",
          "appName": "...",
          "type": "...",
          "types": "...",
          "appKey": "...",
          "appSecret": "...",
          "pcUrl": "...",
          "iconUrl": "...",
          "sort": "...",
          "status": "...",
          "createBy": "...",
          "createTime": "...",
          "updateBy": "...",
          "updateTime": "...",
          "remark": "..."
        }
      ],
      "total": 1,
      "pages": 1
    }
  }
  ```

---

#### 应用详情

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/app/detail` |
| OperationId | `detail` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `appId` | query | integer(int64) | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseSysAppDO`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": {
      "beginTime": "string_value",
      "endTime": "string_value",
      "params": {},
      "appId": 1,
      "appName": "示例名称",
      "type": 1,
      "types": [
        1
      ],
      "appKey": "string_value",
      "appSecret": "string_value",
      "pcUrl": "http://example.com",
      "iconUrl": "string_value",
      "sort": 1,
      "status": 1,
      "createBy": "string_value",
      "createTime": "2024-01-01T00:00:00",
      "updateBy": "string_value",
      "updateTime": "2024-01-01T00:00:00",
      "remark": "string_value"
    }
  }
  ```

---

### 短信接口

#### 发送登录验证码

| 属性 | 值 |
|------|------|
| 请求方法 | `GET` |
| 请求路径 | `/system/sms/sendLoginSms` |
| OperationId | `sendLoginSms` |

**请求参数：**

| 参数名 | 位置 | 类型 | 必填 | 描述 |
|--------|------|------|------|------|
| `phoneNum` | query | string | 是 |  |

**响应：**

- **200**: OK
  - Content-Type: `*/*`
  - Schema: `ResponseBoolean`

  **响应示例：**
  ```json
  {
    "code": 1,
    "msg": "string_value",
    "requestId": "string_value",
    "requestTime": "string_value",
    "data": true
  }
  ```

---
