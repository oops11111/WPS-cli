# 接口说明

## 认证

所有请求需在请求头携带 `Authorization: Bearer <token>`。

## 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /v1/reports | 列出报告 |
| POST | /v1/reports | 创建报告 |
| DELETE | /v1/reports/{id} | 删除报告 |

### 错误码

1. `400`：参数错误
2. `401`：未认证
3. `404`：资源不存在

```json
{"code": 404, "message": "not found"}
```
