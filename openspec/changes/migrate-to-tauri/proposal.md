# Migrate to Tauri

## Summary

将 LiangMu Dev 从 Flet (Python) 完全重写为 Tauri (Rust + React)，以获得更好的性能、更小的体积和更原生的体验。

## Motivation

### 当前问题

1. **性能瓶颈**: Python 扫描大量历史记录文件较慢，尤其是 Codex 的按日期分目录结构
2. **体积过大**: PyInstaller 打包后约 100MB+
3. **内存占用高**: Flet 运行时约 150-200MB
4. **Flet 框架不稳定**: 存在多个 BUG，文档不完善

### 迁移收益

1. **性能提升**: Rust 并行扫描历史记录，预计提升 10-50 倍
2. **体积减小**: Tauri 打包约 5-10MB
3. **内存优化**: 预计 < 50MB
4. **更好的原生体验**: 系统托盘、全局快捷键等更稳定
5. **为后续 IDE 开发打基础**: React 生态更适合复杂 UI

## Scope

### 包含

- 所有现有功能的完整复现
- 历史记录管理性能优化
- 新增功能：
  - 更快的历史扫描
  - 更好的搜索/过滤
  - 批量操作（删除、导出、归档）
  - 跨 CLI 统一管理

### 不包含

- IDE 功能（后续迭代）
- 新的 CLI 工具支持（后续迭代）

## Success Criteria

1. 所有现有功能正常工作
2. 历史记录扫描速度提升 10 倍以上
3. 打包体积 < 15MB
4. 内存占用 < 80MB
5. 启动时间 < 1 秒

## Dependencies

- Tauri 2.x
- React 18+
- TypeScript 5+
- Rust 1.75+
- rusqlite
- walkdir + rayon (并行文件扫描)
- serde_json (JSON 解析)

## Risks

1. **学习曲线**: 需要学习 Rust 和 Tauri
2. **迁移周期**: 完整重写需要较长时间
3. **兼容性**: 需确保配置文件格式兼容

## Related Changes

- [api-keys](specs/api-keys/spec.md) - API Keys 管理模块
- [history](specs/history/spec.md) - 历史记录管理模块
- [mcp](specs/mcp/spec.md) - MCP 服务器管理模块
- [prompts](specs/prompts/spec.md) - 提示词管理模块
- [system](specs/system/spec.md) - 系统功能模块
