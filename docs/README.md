# MOFSimBench 文档中心

欢迎使用 MOFSimBench 文档。本文档中心包含系统架构、开发指南、部署运维、API 参考等完整文档。

---

## 📁 文档目录结构

```
docs/
├── README.md                          # 文档索引（本文件）
├── CHANGELOG.md                       # 变更日志
├── project_analysis_report.md         # 项目分析报告
├── engineering_requirements.md        # 工程化需求规格说明书
│
├── architecture/                      # 架构与设计
│   ├── architecture_design.md         # 系统架构设计
│   ├── database_design.md             # 数据库设计
│   ├── api_design.md                  # API 详细设计
│   ├── task_lifecycle.md              # 任务生命周期
│   └── gpu_scheduler_design.md        # GPU 调度器设计
│
├── development/                       # 开发指南
│   ├── development_guide.md           # 开发环境与规范
│   ├── coding_standards.md            # 代码规范
│   ├── testing_guide.md               # 测试指南
│   ├── adding_new_task.md             # 添加新任务类型
│   └── adding_new_model.md            # 集成新模型
│
├── deployment/                        # 部署与运维
│   ├── deployment_guide.md            # 部署指南
│   ├── configuration_reference.md     # 配置参考
│   ├── operations_manual.md           # 运维手册
│   ├── troubleshooting.md             # 故障排查
│   ├── monitoring_setup.md            # 监控配置
│   └── backup_recovery.md             # 备份与恢复
│
├── api/                               # API 与 SDK
│   ├── api_reference.md               # API 完整参考
│   ├── error_codes.md                 # 错误码列表
│   ├── sdk_quickstart.md              # SDK 快速入门
│   ├── sdk_reference.md               # SDK 完整参考
│   └── webhook_integration.md         # Webhook 集成
│
├── user/                              # 用户指南
│   ├── user_guide.md                  # 使用指南
│   ├── task_types_reference.md        # 任务类型参考
│   ├── model_catalog.md               # 模型目录
│   ├── custom_model_guide.md          # 自定义模型指南
│   └── best_practices.md              # 最佳实践
│
└── operations/                        # 安全与运维
    ├── security_guide.md              # 安全指南
    ├── api_authentication.md          # API 认证
    ├── logging_reference.md           # 日志参考
    ├── alert_rules_reference.md       # 告警规则
    └── migration_guide.md             # 迁移指南
```

---

## 🚀 快速导航

### 新用户入门
1. [用户使用指南](user/user_guide.md) - 了解系统功能和基本使用
2. [SDK 快速入门](api/sdk_quickstart.md) - 快速上手 Python SDK
3. [任务类型参考](user/task_types_reference.md) - 了解支持的任务类型

### 开发者
1. [开发环境指南](development/development_guide.md) - 搭建开发环境
2. [系统架构设计](architecture/architecture_design.md) - 理解系统架构
3. [API 设计文档](architecture/api_design.md) - API 详细规范
4. [添加新任务](development/adding_new_task.md) - 扩展任务类型

### 运维人员
1. [部署指南](deployment/deployment_guide.md) - 系统部署步骤
2. [配置参考](deployment/configuration_reference.md) - 配置项详解
3. [监控配置](deployment/monitoring_setup.md) - 设置监控告警
4. [故障排查](deployment/troubleshooting.md) - 问题诊断

---

## 📋 文档版本

| 文档 | 版本 | 更新日期 |
|------|------|---------|
| 需求规格说明书 | v2.0 | 2025-12-30 |
| 项目分析报告 | v1.0 | 2025-12-30 |
| 其他文档 | v1.0 | 2025-12-30 |

---

## 📞 获取帮助

- **问题反馈**：请提交 GitHub Issue
- **文档改进**：欢迎提交 Pull Request

---

*文档最后更新：2025年12月30日*
